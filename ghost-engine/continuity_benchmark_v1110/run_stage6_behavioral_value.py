"""Stage 6 — final-curtain behavioral payoff experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
import time

from .stage6_behavior_policy import STAGE5_CHECKPOINT_SHA256, seeded_int
from .stage6_behavior_scenarios import event, factory, run_quality

STAGE = "npc_continuity_stage6_behavioral_value"
HISTORICAL_SCORE = {"baseline": "62/62", "ghost": "60/62", "rescored": False}


def _workload(kind: str, root: Path) -> dict:
    system = factory(kind, root, f"{kind}-engineering")
    try:
        count = seeded_int("engineering:episodes", 180, 220)
        episode_ids = []
        start = time.perf_counter_ns()
        for index in range(count):
            dimension = ("respect", "threat", "betrayal")[index % 3]
            emotion = {"hope": .08} if dimension == "respect" else ({"fear": .08} if dimension == "threat" else {"anger": .08})
            consequence = .002 if dimension == "respect" else (-.002 if dimension == "betrayal" else 0.0)
            row = event(system, f"engineering-{index}", dimension, .006, emotion, consequence)
            episode_ids.append(row["episode_id"])
        event_ns = time.perf_counter_ns() - start
        start = time.perf_counter_ns(); system.tick("npc", 100); tick_ns = time.perf_counter_ns() - start
        snapshot = system.snapshot()
        snapshot_bytes = len(json.dumps(snapshot, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())
        sample = episode_ids[::max(1, len(episode_ids) // 40)]
        start = time.perf_counter_ns()
        for episode_id in sample:
            system.recall_episode(episode_id, .25)
        recall_ns = time.perf_counter_ns() - start
        return {
            "episodes": count,
            "snapshot_bytes": snapshot_bytes,
            "archive_bytes": system.archive.path.stat().st_size,
            "event_avg_us": event_ns / count / 1000.0,
            "tick_avg_us": tick_ns / 100 / 1000.0,
            "recall_avg_us": recall_ns / len(sample) / 1000.0,
        }
    finally:
        system.close()


def _ratio(numerator: float, denominator: float) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _baseline_only_failures(baseline: dict, ghost: dict) -> list[str]:
    failures = []
    for scenario, baseline_packet in baseline["scenarios"].items():
        ghost_checks = ghost["scenarios"][scenario]["checks"]
        for check, baseline_pass in baseline_packet["checks"].items():
            if baseline_pass and not ghost_checks[check]:
                failures.append(f"{scenario} :: {check}")
    return failures


def _ghost_only_passes(baseline: dict, ghost: dict) -> list[str]:
    wins = []
    for scenario, baseline_packet in baseline["scenarios"].items():
        ghost_checks = ghost["scenarios"][scenario]["checks"]
        for check, baseline_pass in baseline_packet["checks"].items():
            if not baseline_pass and ghost_checks[check]:
                wins.append(f"{scenario} :: {check}")
    return wins


def _foreground_ablation(baseline: dict, ghost: dict) -> dict:
    b_episode = baseline["scenarios"]["episode_specific_affect"]["ablation"]["fear_without_foreground"]
    g_episode = ghost["scenarios"]["episode_specific_affect"]["ablation"]["fear_without_foreground"]
    b_modes = baseline["scenarios"]["betrayal_affect_mode_resolution"]["ablation"]
    g_modes = ghost["scenarios"]["betrayal_affect_mode_resolution"]["ablation"]
    equalized = (
        b_episode["policy_passes"] == g_episode["policy_passes"]
        and b_modes["fear_without_foreground"]["policy_passes"] == g_modes["fear_without_foreground"]["policy_passes"]
        and b_modes["grief_without_foreground"]["policy_passes"] == g_modes["grief_without_foreground"]["policy_passes"]
    )
    return {
        "equalized_without_foreground": equalized,
        "baseline": {"episode_fear": b_episode, **b_modes},
        "ghost": {"episode_fear": g_episode, **g_modes},
    }


def build_result(root: str | Path, *, include_engineering: bool = True) -> dict:
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    baseline = run_quality("baseline", root / "baseline-quality")
    ghost = run_quality("ghost", root / "ghost-quality")
    baseline_rerun = run_quality("baseline", root / "baseline-quality-rerun")
    ghost_rerun = run_quality("ghost", root / "ghost-quality-rerun")
    deterministic = baseline == baseline_rerun and ghost == ghost_rerun
    ghost_wins = _ghost_only_passes(baseline, ghost)
    ghost_losses = _baseline_only_failures(baseline, ghost)
    ablation = _foreground_ablation(baseline, ghost)
    engineering = None
    ratios = None
    if include_engineering:
        baseline_eng = _workload("baseline", root / "baseline-engineering")
        ghost_eng = _workload("ghost", root / "ghost-engineering")
        keys = ("snapshot_bytes", "archive_bytes", "event_avg_us", "tick_avg_us", "recall_avg_us")
        ratios = {key: _ratio(ghost_eng[key], baseline_eng[key]) for key in keys}
        engineering = {"baseline": baseline_eng, "ghost": ghost_eng, "ghost_to_baseline_ratios": ratios}

    advantage = ghost["passed"] - baseline["passed"]
    if ghost["passed"] < baseline["passed"] or ghost_losses:
        verdict = "GHOST_BEHAVIORAL_VALUE_DISADVANTAGE"
    elif advantage >= 2 and ablation["equalized_without_foreground"]:
        verdict = "LIMITED_GHOST_BEHAVIORAL_ADVANTAGE_DEMONSTRATED_CROSS_LAYER_FOREGROUND_CAUSALLY_CONTRIBUTES"
    elif advantage > 0:
        verdict = "GHOST_BEHAVIORAL_EDGE_OBSERVED_BUT_CAUSAL_ADVANTAGE_NOT_ESTABLISHED"
    elif include_engineering and ratios and ratios["snapshot_bytes"] is not None and ratios["snapshot_bytes"] >= 2.0:
        verdict = "NO_GHOST_BEHAVIORAL_ADVANTAGE_SIMPLER_BASELINE_HAS_ENGINEERING_ADVANTAGE"
    else:
        verdict = "NO_CLEAR_BEHAVIORAL_WINNER"

    return {
        "stage": STAGE,
        "seed_source": {"stage5_checkpoint_sha256": STAGE5_CHECKPOINT_SHA256},
        "historical_stage1_score_preserved": HISTORICAL_SCORE,
        "quality": {
            "baseline": baseline,
            "ghost": ghost,
            "difference_ghost_minus_baseline": advantage,
            "ghost_only_passes": ghost_wins,
            "baseline_only_passes": ghost_losses,
        },
        "foreground_ablation": ablation,
        "deterministic_rerun": deterministic,
        "engineering": engineering,
        "strict_verdict": verdict,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root")
    parser.add_argument("--out")
    parser.add_argument("--no-engineering", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root) if args.root else Path(tempfile.mkdtemp(prefix="ghost-stage6-"))
    result = build_result(root, include_engineering=not args.no_engineering)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
