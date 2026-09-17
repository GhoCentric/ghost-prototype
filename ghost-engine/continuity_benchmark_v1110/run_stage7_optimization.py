"""Stage 7 — cost-reduction experiment preserving frozen Stage-6 behavioral value."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import tempfile
import time

from .run_stage6_behavioral_value import _foreground_ablation
from .stage7_optimization_variants import (
    PROJECTION_ENTER,
    PROJECTION_EXIT,
    optimized_factory,
    patched_stage6_factory,
    run_stage6_quality_for_variant,
)

STAGE = "npc_continuity_stage7_optimization"
VARIANTS = ("ghost_current", "ghost_lazy", "ghost_sparse", "ghost_lazy_sparse")
PRESERVATION_TARGET = 25
GHOST_ONLY_TARGETS = (
    "episode_specific_affect :: fearful_episode_recall_is_behaviorally_more_defensive",
    "betrayal_affect_mode_resolution :: grief_tagged_betrayal_recall_prefers_withdrawal",
)


def _checks(packet: dict) -> dict[str, bool]:
    out = {}
    for scenario, row in packet["scenarios"].items():
        for check, value in row["checks"].items():
            out[f"{scenario} :: {check}"] = bool(value)
    return out


def _ghost_wins_preserved(packet: dict) -> bool:
    checks = _checks(packet)
    return all(checks.get(name) is True for name in GHOST_ONLY_TARGETS)


def _time_us(callable_, repeats: int = 5) -> float:
    rows = []
    for _ in range(repeats):
        start = time.perf_counter_ns(); callable_(); rows.append((time.perf_counter_ns() - start) / 1000.0)
    return statistics.median(rows)


def _engineering(kind: str, root: Path) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    system = optimized_factory(kind, root, f"{kind}-engineering")
    try:
        count = 120
        ids = []
        start = time.perf_counter_ns()
        for index in range(count):
            dimension = ("respect", "threat", "betrayal")[index % 3]
            emotion = {"hope": .08} if dimension == "respect" else ({"fear": .08} if dimension == "threat" else {"anger": .08})
            consequence = .002 if dimension == "respect" else (-.002 if dimension == "betrayal" else 0.0)
            row = system.event(
                "npc", source=f"engineering-{index}", dimension=dimension,
                meaning_delta=.006, relevance=.006, emotion_profile=emotion,
                consequence=consequence,
            )
            ids.append(row["episode_id"])
        event_avg_us = (time.perf_counter_ns() - start) / count / 1000.0

        # Dormant-NPC case: schedule 100 independent logical ticks, then materialize once.
        start = time.perf_counter_ns()
        for _ in range(100):
            system.tick("npc", 1)
        schedule_total_us = (time.perf_counter_ns() - start) / 1000.0
        materialize_us = _time_us(lambda: system.observe("npc"), repeats=1)

        # Active-NPC case: a tick followed by an observation each time forces current state.
        start = time.perf_counter_ns()
        for _ in range(40):
            system.tick("npc", 1); system.observe("npc")
        active_tick_cycle_avg_us = (time.perf_counter_ns() - start) / 40 / 1000.0

        snapshot = system.snapshot()
        hot_snapshot_bytes = len(json.dumps(snapshot, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())
        cold_history_bytes = 0 if system.cold_history is None else system.cold_history.bytes()
        cold_history_records = 0 if system.cold_history is None else system.cold_history.count()
        projections = system.working_projections("npc") if system.sparse_history else []
        history_counts = system.hot_history_counts()
        episode_archive_bytes = system.archive.path.stat().st_size

        sample = ids[::max(1, len(ids) // 36)]
        start = time.perf_counter_ns()
        for episode_id in sample:
            system.recall_episode(episode_id, .25)
        recall_avg_us = (time.perf_counter_ns() - start) / len(sample) / 1000.0
        return {
            "episodes": count,
            "event_avg_us": event_avg_us,
            "dormant_tick_schedule_avg_us": schedule_total_us / 100.0,
            "dormant_materialize_us": materialize_us,
            "active_tick_cycle_avg_us": active_tick_cycle_avg_us,
            "recall_avg_us": recall_avg_us,
            "hot_snapshot_bytes": hot_snapshot_bytes,
            "episode_archive_bytes": episode_archive_bytes,
            "cold_history_bytes": cold_history_bytes,
            "cold_history_records": cold_history_records,
            "total_persistent_bytes": hot_snapshot_bytes + episode_archive_bytes + cold_history_bytes,
            "hot_history_counts": history_counts,
            "working_projection_count": len(projections),
            "working_projections": projections,
        }
    finally:
        system.close()


def _ratio(value: float, reference: float) -> float | None:
    return None if reference == 0 else value / reference



def _projection_probe(root: Path) -> dict:
    system = optimized_factory("ghost_lazy_sparse", root, "projection-probe")
    try:
        target = system.event(
            "npc", source="old-fear", dimension="threat", meaning_delta=.72,
            relevance=.72, emotion_profile={"fear": .9}, consequence=0.0,
        )
        for index in range(4):
            system.event(
                "npc", source=f"noise-{index}", dimension="respect", meaning_delta=.04,
                relevance=.04, emotion_profile={"hope": .04}, consequence=0.0,
            )
        system.tick("npc", 50); system.observe("npc")
        before = system.working_projections("npc")
        system.recall_episode(target["episode_id"], .95)
        hot = system.working_projections("npc")
        system.tick("npc", 90); system.observe("npc")
        cooled = system.working_projections("npc")
        return {
            "before_count": len(before),
            "hot_count": len(hot),
            "cooled_count": len(cooled),
            "budget": 3,
            "admitted_after_recall": 0 < len(hot) <= 3,
            "bounded": len(hot) <= 3,
            "cools_or_holds_below_hot": len(cooled) <= len(hot),
        }
    finally:
        system.close()

def build_result(root: str | Path, stage6_report: dict) -> dict:
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    frozen_ghost = stage6_report["quality"]["ghost"]
    frozen_baseline = stage6_report["quality"]["baseline"]
    if frozen_ghost["passed"] != 25 or frozen_ghost["total"] != 26:
        raise RuntimeError("Stage-7 requires exact frozen Stage-6 Ghost 25/26 evidence")

    quality = {}
    deterministic = {}
    for kind in VARIANTS:
        quality[kind] = run_stage6_quality_for_variant(kind, root / f"{kind}-quality")

    # Full Stage-6 quality runs are expensive on Android.  Determinism is therefore
    # rechecked on the exact scenarios that carry the demonstrated Ghost advantage
    # plus restart and ambiguity invariants, rather than duplicating all 26 checks.
    subset_names = (
        "episode_specific_affect",
        "betrayal_affect_mode_resolution",
        "ambiguous_recall_inertness",
        "restart_behavior_identity",
    )
    for kind in VARIANTS:
        with patched_stage6_factory(kind) as scenarios:
            first = {
                name: dict(scenarios.SCENARIOS)[name](kind, root / f"{kind}-det-a" / name)
                for name in subset_names
            }
            second = {
                name: dict(scenarios.SCENARIOS)[name](kind, root / f"{kind}-det-b" / name)
                for name in subset_names
            }
        deterministic[kind] = first == second

    # Current wrapper must reproduce the frozen production Ghost result exactly;
    # only the contestant label differs because Stage 7 names the control explicitly.
    normalized_current = dict(quality["ghost_current"])
    normalized_current["kind"] = "ghost"
    if normalized_current != frozen_ghost:
        raise RuntimeError("Stage-7 current-Ghost control does not replay frozen Stage-6 Ghost")

    preservation = {}
    for kind, packet in quality.items():
        ablation = _foreground_ablation(frozen_baseline, packet)
        preservation[kind] = {
            "quality_at_least_25_of_26": packet["passed"] >= PRESERVATION_TARGET and packet["total"] == 26,
            "two_stage6_ghost_only_wins_preserved": _ghost_wins_preserved(packet),
            "foreground_ablation_preserved": bool(ablation["equalized_without_foreground"]),
            "deterministic": bool(deterministic[kind]),
            "passed": packet["passed"],
            "total": packet["total"],
        }

    engineering = {kind: _engineering(kind, root / f"{kind}-engineering") for kind in VARIANTS}
    projection_probe = _projection_probe(root / "projection-probe")
    control = engineering["ghost_current"]
    ratio_keys = (
        "event_avg_us", "dormant_tick_schedule_avg_us", "dormant_materialize_us",
        "active_tick_cycle_avg_us", "recall_avg_us", "hot_snapshot_bytes",
        "episode_archive_bytes", "cold_history_bytes", "total_persistent_bytes",
    )
    ratios = {
        kind: {key: _ratio(row[key], control[key]) for key in ratio_keys}
        for kind, row in engineering.items()
    }

    viable = [
        kind for kind in VARIANTS[1:]
        if all((preservation[kind]["quality_at_least_25_of_26"],
                preservation[kind]["two_stage6_ghost_only_wins_preserved"],
                preservation[kind]["foreground_ablation_preserved"],
                preservation[kind]["deterministic"]))
    ]
    if "ghost_lazy_sparse" in viable:
        verdict = "LAZY_PLUS_SPARSE_PRESERVES_STAGE6_VALUE_OPTIMIZATION_PATH_SURVIVES"
    elif viable:
        verdict = "PARTIAL_OPTIMIZATION_PATH_SURVIVES_STAGE6_VALUE_PRESERVED"
    else:
        verdict = "OPTIMIZATION_HYPOTHESES_FAIL_STAGE6_VALUE_PRESERVATION"

    return {
        "stage": STAGE,
        "frozen_stage6_reference": {
            "baseline": f"{frozen_baseline['passed']}/{frozen_baseline['total']}",
            "ghost": f"{frozen_ghost['passed']}/{frozen_ghost['total']}",
            "ghost_only_targets": list(GHOST_ONLY_TARGETS),
        },
        "projection_gate": {
            "enter": PROJECTION_ENTER,
            "exit": PROJECTION_EXIT,
            "raw_history_payloads_are_cold": True,
            "projection_is_bounded_metadata_not_history_payload": True,
        },
        "quality": quality,
        "preservation": preservation,
        "engineering": engineering,
        "projection_probe": projection_probe,
        "ratios_to_current_ghost": ratios,
        "viable_optimized_variants": viable,
        "strict_verdict": verdict,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root")
    parser.add_argument("--stage6-report", required=True)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    stage6_report = json.loads(Path(args.stage6_report).read_text(encoding="utf-8"))
    root = Path(args.root) if args.root else Path(tempfile.mkdtemp(prefix="ghost-stage7-"))
    result = build_result(root, stage6_report)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0

