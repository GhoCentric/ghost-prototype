"""Stage-2 head-to-head: frozen purpose-built baseline versus production Ghost.

Stage 1 froze the contract, runner, baseline, tests, and baseline result before
this module or the Ghost adapter existed.  Stage 2 does not change those files.
It replays the frozen baseline as an integrity check, runs production Ghost twice
through the same frozen runner, and reports the raw contract result separately
from diagnostic interpretation of any failures.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile

from .contract import contract_digest
from .ghost_adapter import ghost_factory
from .metrics import source_metrics
from .purpose_built import PurposeBuiltContinuity
from .scenario_runner import run_frozen_suite


STAGE1_BASELINE_RESULT_SHA256 = (
    "d87d577214a51130c8e9bf85133e874db18a1713a728ac1b74e0150294774f61"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _baseline_factory(root: Path, label: str, *, max_records=None, snapshot=None):
    return PurposeBuiltContinuity(
        root / f"{label}.sqlite",
        max_records=max_records,
        snapshot=snapshot,
    )


def _failed_checks(result: dict) -> dict[str, list[str]]:
    return {
        scenario_id: [name for name, passed in row["checks"].items() if not passed]
        for scenario_id, row in result["scenarios"].items()
        if not all(row["checks"].values())
    }


def _snapshot_diagnostic(work_root: Path) -> dict:
    system = ghost_factory(work_root, "snapshot-diagnostic")
    try:
        system.event(
            "npc",
            source="betrayal-1",
            dimension="betrayal",
            meaning_delta=0.9,
            relevance=0.9,
            emotion_profile={"anger": 0.8},
            consequence=-1.0,
        )
        snapshot = system.snapshot()
        encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
        continuity_packet = snapshot["ghost"]["continuity"]
        return {
            "raw_frozen_literal_source_absent": "source" not in encoded,
            "episode_emotion_profile_absent": "emotion_profile" not in encoded,
            "continuity_packet_keys": sorted(continuity_packet),
            "continuity_archive_manifest_only": (
                set(continuity_packet) == {"runtime", "episode_archive"}
                and continuity_packet["episode_archive"]["record_count"] == 1
            ),
            "non_episode_source_history_present": (
                bool(snapshot["ghost"]["emotions"]["agents"]["npc"]["history"])
                and "source" in snapshot["ghost"]["emotions"]["agents"]["npc"]["history"][0]
            ),
        }
    finally:
        system.close()


def _ambiguity_diagnostic(work_root: Path) -> dict:
    system = ghost_factory(work_root, "ambiguity-diagnostic")
    try:
        system.event(
            "npc", source="a", dimension="betrayal", meaning_delta=0.4,
            relevance=0.8, emotion_profile={"anger": 0.6}, consequence=-0.2,
        )
        system.event(
            "npc", source="b", dimension="betrayal", meaning_delta=0.4,
            relevance=0.8, emotion_profile={"fear": 0.6}, consequence=-0.2,
        )
        before = system.observe("npc")
        lookup = system.recall_dimension("npc", "betrayal", 0.5)
        after = system.observe("npc")
        changed = [
            key for key in ("meaning", "activation", "emotion", "trust", "episode_count")
            if after[key] != before[key]
        ]
        return {
            "lookup_status": lookup["status"],
            "candidate_count": lookup["candidate_count"],
            "changed_contract_state_fields": changed,
            "activation_before": before["activation"]["betrayal"],
            "activation_after": after["activation"]["betrayal"],
        }
    finally:
        system.close()


def _stale_foreground_diagnostic(work_root: Path) -> dict:
    system = ghost_factory(work_root, "stale-diagnostic")
    try:
        system.event(
            "npc", source="betrayal-old", dimension="betrayal", meaning_delta=0.9,
            relevance=1.0, emotion_profile={"anger": 1.0}, consequence=-1.0,
        )
        system.tick("npc", 24)
        for index in range(30):
            system.event(
                "npc", source=f"respect-{index}", dimension="respect",
                meaning_delta=0.002, relevance=0.25,
                emotion_profile={"hope": 0.1}, consequence=0.02,
            )
            system.tick("npc", 1)
        state = system.observe("npc")
        raw = system._ghost.continuity_state("npc")
        assert raw is not None
        return {
            "contract_projected_foreground": state["foreground"],
            "production_current_leader": raw["current_leader"],
            "betrayal_activation": state["activation"]["betrayal"],
            "respect_activation": state["activation"]["respect"],
            "hope_level": state["emotion"]["hope"],
            "old_interpretation_is_stale_relative_to_recent": (
                state["activation"]["respect"] > state["activation"]["betrayal"]
            ),
        }
    finally:
        system.close()


def _diagnoses(ghost_result: dict, diagnostics: dict) -> list[dict]:
    failed = _failed_checks(ghost_result)
    rows = []
    ambiguity_checks = {
        "same_dimension_identity_and_ambiguity": {
            "ambiguous_dimension_recall_does_not_mutate_hot_state"
        },
        "large_ambiguity_safety": {"ambiguous_recall_leaves_relevance_unchanged"},
    }
    for scenario_id, expected in ambiguity_checks.items():
        actual = set(failed.get(scenario_id, []))
        if actual & expected:
            rows.append({
                "scenario": scenario_id,
                "classification": "production_semantic_mismatch",
                "root": "ambiguous_dimension_recall_reactivates_interpretation_before_identity_is_unique",
                "evidence": deepcopy(diagnostics["ambiguity"]),
                "raw_check_remains_failed": True,
            })
    if "hot_snapshot_excludes_episode_payloads" in failed.get("snapshot_archive_pairing", []):
        rows.append({
            "scenario": "snapshot_archive_pairing",
            "classification": "frozen_literal_projection_mismatch",
            "root": "frozen check rejects any source key, while Ghost hot subsystem histories contain non-episode source provenance",
            "evidence": deepcopy(diagnostics["snapshot"]),
            "raw_check_remains_failed": True,
        })
    if "recent_concern_can_displace_old_concern" in failed.get("stale_dominance_resistance", []):
        rows.append({
            "scenario": "stale_dominance_resistance",
            "classification": "cross_layer_foreground_projection_mismatch",
            "root": "frozen baseline foreground is interpretation-only; Ghost current_leader may legitimately be an emotion",
            "evidence": deepcopy(diagnostics["stale_foreground"]),
            "raw_check_remains_failed": True,
        })
    return rows


def _engineering_packet(package_root: Path, frozen: dict, ghost_result: dict) -> dict:
    return {
        "source": {
            "purpose_built.py": source_metrics(package_root / "purpose_built.py"),
            "ghost_adapter.py": source_metrics(package_root / "ghost_adapter.py"),
            "ghost_continuity.py": source_metrics(package_root.parent / "ghost" / "continuity.py"),
            "ghost_episode_store.py": source_metrics(package_root.parent / "ghost" / "episode_store.py"),
        },
        "frozen_snapshot_bytes": {
            "baseline": frozen["baseline_result"]["scenarios"]["snapshot_archive_pairing"]["measures"]["snapshot_bytes"],
            "ghost_adapter": ghost_result["scenarios"]["snapshot_archive_pairing"]["measures"]["snapshot_bytes"],
        },
    }


def _base_report(
    frozen: dict,
    ghost_result: dict,
    diagnostics: dict,
    package_root: Path,
) -> dict:
    failed = _failed_checks(ghost_result)
    baseline_checks = frozen["baseline_result"]["all_checks"]
    ghost_checks = ghost_result["all_checks"]
    strict_competence = (
        ghost_result["competence"]["passes"] == ghost_result["competence"]["total"]
    )
    return {
        "stage": "npc_continuity_stage2_frozen_head_to_head",
        "contract_digest": contract_digest(),
        "stage1_frozen_result_sha256": STAGE1_BASELINE_RESULT_SHA256,
        "stage1_baseline_replay_exact": True,
        "baseline_result": deepcopy(frozen["baseline_result"]),
        "ghost_result": deepcopy(ghost_result),
        "ghost_deterministic_rerun": True,
        "raw_comparison": {
            "baseline_checks": deepcopy(baseline_checks),
            "ghost_checks": deepcopy(ghost_checks),
            "ghost_minus_baseline_passes": ghost_checks["passes"] - baseline_checks["passes"],
            "ghost_strict_competence_gate": strict_competence,
            "failed_checks": failed,
        },
        "diagnostics_do_not_rescore_frozen_checks": True,
        "diagnostics": diagnostics,
        "failure_diagnoses": _diagnoses(ghost_result, diagnostics),
        "engineering": _engineering_packet(package_root, frozen, ghost_result),
        "strict_stage2_verdict": (
            "GHOST_DOES_NOT_MATCH_FROZEN_COMPETENT_BASELINE"
            if not strict_competence
            else "GHOST_MATCHES_FROZEN_COMPETENCE_GATE"
        ),
        "claims_supported": [
            "The frozen purpose-built baseline remains 62/62 and deterministic.",
            "Production Ghost can be run deterministically against the same frozen contract.",
            "Any raw Stage-2 failed check remains failed even when a diagnostic identifies a projection mismatch.",
        ],
        "claims_not_established": [
            "Ghost superiority",
            "NPC believability superiority",
            "developer productivity",
            "market value",
            "novelty or prior-art status",
            "human psychological accuracy",
            "multi-year investment justification",
        ],
        "next_stage_rule": (
            "Do not modify the frozen Stage-1 benchmark to erase Stage-2 failures. "
            "Any production correction must be proposed against the diagnosed behavior first, "
            "then rerun as a new explicitly versioned stage."
        ),
    }


def build_report(work_root: Path, package_root: Path) -> dict:
    frozen_path = package_root / "stage1_baseline_frozen.json"
    if _sha256(frozen_path) != STAGE1_BASELINE_RESULT_SHA256:
        raise RuntimeError("Stage-1 frozen baseline result hash drifted")
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))

    baseline = run_frozen_suite(_baseline_factory, work_root / "baseline", "baseline")
    if baseline != frozen["baseline_result"]:
        raise RuntimeError("Stage-1 baseline replay no longer matches frozen result")

    ghost_first = run_frozen_suite(ghost_factory, work_root / "ghost1", "ghost")
    ghost_second = run_frozen_suite(ghost_factory, work_root / "ghost2", "ghost")
    if ghost_first != ghost_second:
        raise RuntimeError("production Ghost result is nondeterministic under frozen suite")

    diagnostics = {
        "ambiguity": _ambiguity_diagnostic(work_root / "diagnostics"),
        "snapshot": _snapshot_diagnostic(work_root / "diagnostics"),
        "stale_foreground": _stale_foreground_diagnostic(work_root / "diagnostics"),
    }
    return _base_report(frozen, ghost_first, diagnostics, package_root)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    package_root = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="ghost_npc_continuity_stage2_") as temp:
        report = build_report(Path(temp), package_root)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(text, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(args.output)
    return 0


