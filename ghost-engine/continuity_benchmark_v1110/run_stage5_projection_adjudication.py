"""Stage-5 adjudication of the two raw Stage-4 projection mismatches.

Stage 5 is diagnostic only.  It does not modify Ghost production code, the
frozen Stage-1 benchmark, or historical Stage-2/3/4 evidence.  The raw frozen
score remains baseline 62/62 versus Ghost 60/62.

The two questions are narrower than the frozen literal checks:

1. Does Ghost's hot snapshot actually duplicate durable causal episodes or grow
   without bound as the archive grows, or is the failure caused by bounded
   source-owned provenance/history that the Stage-1 literal also rejects?
2. Does the stale-dominance failure show an old concern controlling the present,
   or does Ghost's cross-layer foreground follow recent state through an emotion
   channel that the interpretation-only baseline cannot represent?
"""

from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
from typing import Any, Callable

from .ghost_adapter import ghost_factory
from .purpose_built import PurposeBuiltContinuity


STAGE4_EXPECTED_FAILED = {
    "snapshot_archive_pairing": ["hot_snapshot_excludes_episode_payloads"],
    "stale_dominance_resistance": ["recent_concern_can_displace_old_concern"],
}
_HISTORY_CHANNELS = ("interpretations", "emotions", "attention")
_EPS = 1e-12


def validate_stage4_report(report: dict[str, Any]) -> None:
    """Refuse to adjudicate anything except the exact Stage-4 frozen outcome."""
    if report.get("stage") != "npc_continuity_stage4_ambiguity_correction_rerun":
        raise ValueError("not the Stage-4 ambiguity-correction report")
    if report.get("pre_patch", {}).get("ghost") != {"passes": 58, "total": 62}:
        raise ValueError("Stage-4 pre-patch Ghost result drifted")
    post = report.get("post_patch", {})
    if post.get("baseline") != {"passes": 62, "total": 62}:
        raise ValueError("Stage-4 baseline result is not exact 62/62")
    if post.get("ghost") != {"passes": 60, "total": 62}:
        raise ValueError("Stage-4 Ghost result is not exact 60/62")
    if post.get("competence") != {"passes": 31, "total": 32}:
        raise ValueError("Stage-4 competence result drifted")
    if post.get("discriminators") != {"passes": 29, "total": 30}:
        raise ValueError("Stage-4 discriminator result drifted")
    if report.get("ghost_pass_delta") != 2:
        raise ValueError("Stage-4 Ghost pass delta drifted")
    if report.get("remaining_raw_failures") != STAGE4_EXPECTED_FAILED:
        raise ValueError("Stage-4 remaining failed-check set drifted")
    if report.get("ghost_deterministic_rerun") is not True:
        raise ValueError("Stage-4 Ghost deterministic rerun did not pass")
    if report.get("stage1_baseline_replay_exact") is not True:
        raise ValueError("Stage-4 frozen Stage-1 replay is not exact")
    if report.get("frozen_benchmark_modified") is not False:
        raise ValueError("Stage-4 says the frozen benchmark changed")
    if report.get("strict_conclusion") != (
        "CONFIRMED_AMBIGUOUS_RECALL_DEFECT_CORRECTED_GHOST_MOVES_58_TO_60_"
        "TWO_FROZEN_PROJECTION_MISMATCHES_REMAIN"
    ):
        raise ValueError("Stage-4 strict conclusion drifted")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _contains_equal_subtree(value: Any, target: Any) -> bool:
    if value == target:
        return True
    if isinstance(value, dict):
        return any(_contains_equal_subtree(child, target) for child in value.values())
    if isinstance(value, list):
        return any(_contains_equal_subtree(child, target) for child in value)
    return False


def _baseline_factory(root: Path, label: str) -> PurposeBuiltContinuity:
    root.mkdir(parents=True, exist_ok=True)
    return PurposeBuiltContinuity(root / f"{label}.sqlite")


def _populate_snapshot_system(
    factory: Callable,
    root: Path,
    label: str,
    count: int,
) -> tuple[Any, dict[str, Any], list[dict[str, Any]]]:
    root.mkdir(parents=True, exist_ok=True)
    system = factory(root, label)
    rows: list[dict[str, Any]] = []
    try:
        for index in range(count):
            rows.append(system.event(
                "npc",
                source=f"STAGE5-SOURCE-{index:04d}",
                dimension="respect",
                meaning_delta=0.001,
                relevance=0.25,
                emotion_profile={"hope": 0.01},
                consequence=0.0,
            ))
        return system, system.snapshot(), rows
    except Exception:
        system.close()
        raise


def _snapshot_size(factory: Callable, root: Path, label: str, count: int) -> dict[str, Any]:
    system, snapshot, rows = _populate_snapshot_system(factory, root, label, count)
    try:
        return {
            "count": count,
            "snapshot_bytes": len(_canonical_bytes(snapshot)),
            "manifest_bytes": len(_canonical_bytes(system.archive_manifest())),
            "archive_count": system.archive_manifest()["record_count"],
            "first_episode_id": rows[0]["episode_id"],
            "last_episode_id": rows[-1]["episode_id"],
        }
    finally:
        system.close()


def _snapshot_probe(root: Path) -> dict[str, Any]:
    ghost_80 = _snapshot_size(ghost_factory, root / "ghost-80", "ghost", 80)
    ghost_system, ghost_160_snapshot, rows = _populate_snapshot_system(
        ghost_factory, root / "ghost-160", "ghost", 160
    )
    baseline_500 = _snapshot_size(_baseline_factory, root / "baseline-160", "baseline", 160)
    try:
        ghost_160_bytes = len(_canonical_bytes(ghost_160_snapshot))
        manifest = ghost_system.archive_manifest()
        history_lengths = {
            channel: len(ghost_160_snapshot["ghost"][channel]["agents"]["npc"]["history"])
            for channel in _HISTORY_CHANNELS
        }
        encoded = json.dumps(ghost_160_snapshot, sort_keys=True)
        first_record = ghost_system.get_episode(rows[0]["episode_id"])
        last_record = ghost_system.get_episode(rows[-1]["episode_id"])
        continuity_packet = ghost_160_snapshot["ghost"]["continuity"]
        plateau_ratio = ghost_160_bytes / ghost_80["snapshot_bytes"]
        baseline_ratio = ghost_160_bytes / baseline_500["snapshot_bytes"]
        semantic_checks = {
            "archive_reaches_160_records": manifest["record_count"] == 160,
            "continuity_archive_is_manifest_only": (
                set(continuity_packet) == {"runtime", "episode_archive"}
                and set(continuity_packet["episode_archive"]) == {
                    "schema", "archive_schema", "record_count", "content_digest"
                }
            ),
            "emotion_profile_key_absent_from_hot_snapshot": "emotion_profile" not in encoded,
            "first_episode_id_absent_from_hot_snapshot": not _contains_equal_subtree(
                ghost_160_snapshot, rows[0]["episode_id"]
            ),
            "last_episode_id_absent_from_hot_snapshot": not _contains_equal_subtree(
                ghost_160_snapshot, rows[-1]["episode_id"]
            ),
            "first_exact_episode_record_absent_from_hot_snapshot": not _contains_equal_subtree(
                ghost_160_snapshot, first_record
            ),
            "last_exact_episode_record_absent_from_hot_snapshot": not _contains_equal_subtree(
                ghost_160_snapshot, last_record
            ),
            "old_source_provenance_ages_out_of_hot_history": "STAGE5-SOURCE-0000" not in encoded,
            "recent_source_provenance_remains_in_hot_history": "STAGE5-SOURCE-0159" in encoded,
            "source_owned_histories_are_bounded": max(history_lengths.values()) <= 64,
            "hot_snapshot_plateaus_while_archive_grows": plateau_ratio <= 1.10,
        }
        return {
            "semantic_checks": semantic_checks,
            "all_semantic_checks_pass": all(semantic_checks.values()),
            "history_lengths_at_160": history_lengths,
            "ghost_snapshot_bytes_80": ghost_80["snapshot_bytes"],
            "ghost_snapshot_bytes_160": ghost_160_bytes,
            "ghost_80_to_160_snapshot_ratio": plateau_ratio,
            "baseline_snapshot_bytes_160": baseline_500["snapshot_bytes"],
            "ghost_to_baseline_snapshot_bytes_at_160": baseline_ratio,
            "ghost_manifest_bytes_160": len(_canonical_bytes(manifest)),
            "bounded_hot_provenance_overhead_is_real": baseline_ratio > 10.0,
            "raw_stage1_literal_still_fails": "source" in encoded,
        }
    finally:
        ghost_system.close()


def _run_recent_stream(
    root: Path,
    label: str,
    *,
    include_old: bool,
    recent_dimension: str,
    recent_emotion: dict[str, float],
) -> dict[str, Any]:
    system = ghost_factory(root, label)
    try:
        if include_old:
            system.event(
                "npc",
                source="betrayal-old",
                dimension="betrayal",
                meaning_delta=0.9,
                relevance=1.0,
                emotion_profile={"anger": 1.0},
                consequence=-1.0,
            )
            system.tick("npc", 24)
        for index in range(30):
            system.event(
                "npc",
                source=f"recent-{index}",
                dimension=recent_dimension,
                meaning_delta=0.002,
                relevance=0.25,
                emotion_profile=recent_emotion,
                consequence=0.02,
            )
            system.tick("npc", 1)
        observed = system.observe("npc")
        raw = system._ghost.continuity_state("npc")
        assert raw is not None
        return {
            "foreground": observed["foreground"],
            "production_current_leader": raw["current_leader"],
            "activation": deepcopy(observed["activation"]),
            "emotion": deepcopy(observed["emotion"]),
            "meaning": deepcopy(observed["meaning"]),
        }
    finally:
        system.close()


def _close_enough(a: float, b: float) -> bool:
    return math.isclose(float(a), float(b), rel_tol=0.0, abs_tol=_EPS)


def _foreground_probe(root: Path) -> dict[str, Any]:
    old_hope = _run_recent_stream(
        root, "old-hope", include_old=True,
        recent_dimension="respect", recent_emotion={"hope": 0.1},
    )
    no_old_hope = _run_recent_stream(
        root, "no-old-hope", include_old=False,
        recent_dimension="respect", recent_emotion={"hope": 0.1},
    )
    old_no_emotion = _run_recent_stream(
        root, "old-no-emotion", include_old=True,
        recent_dimension="respect", recent_emotion={},
    )
    old_fear = _run_recent_stream(
        root, "old-fear", include_old=True,
        recent_dimension="respect", recent_emotion={"fear": 0.1},
    )
    semantic_checks = {
        "old_betrayal_activation_is_stale": old_hope["activation"]["betrayal"] < 1e-6,
        "old_betrayal_is_not_foreground": old_hope["foreground"] != "betrayal",
        "old_event_does_not_change_recent_foreground_winner": (
            old_hope["foreground"] == no_old_hope["foreground"] == "emotion:hope"
        ),
        "old_event_does_not_change_recent_respect_activation": _close_enough(
            old_hope["activation"]["respect"], no_old_hope["activation"]["respect"]
        ),
        "old_event_does_not_change_recent_hope_level": _close_enough(
            old_hope["emotion"]["hope"], no_old_hope["emotion"]["hope"]
        ),
        "removing_recent_emotion_exposes_recent_interpretation": (
            old_no_emotion["foreground"] == "respect"
        ),
        "changing_recent_emotion_changes_cross_layer_winner": (
            old_fear["foreground"] == "emotion:fear"
        ),
        "recent_respect_interpretation_remains_above_old_betrayal": (
            old_hope["activation"]["respect"] > old_hope["activation"]["betrayal"]
        ),
    }
    return {
        "semantic_checks": semantic_checks,
        "all_semantic_checks_pass": all(semantic_checks.values()),
        "old_plus_recent_hope": old_hope,
        "recent_hope_without_old_event": no_old_hope,
        "old_plus_recent_without_emotion": old_no_emotion,
        "old_plus_recent_fear": old_fear,
        "raw_stage1_literal_still_fails": old_hope["foreground"] != "respect",
    }


def _classify(snapshot: dict[str, Any], foreground: dict[str, Any]) -> list[dict[str, Any]]:
    snapshot_classification = (
        "projection_mismatch_confirmed_with_bounded_hot_provenance_overhead"
        if snapshot["all_semantic_checks_pass"]
        else "possible_snapshot_architecture_defect_requires_production_review"
    )
    foreground_classification = (
        "cross_layer_projection_mismatch_confirmed_recent_state_controls_foreground"
        if foreground["all_semantic_checks_pass"]
        else "possible_stale_foreground_defect_requires_production_review"
    )
    return [
        {
            "raw_failure": "snapshot_archive_pairing :: hot_snapshot_excludes_episode_payloads",
            "classification": snapshot_classification,
            "production_correctness_patch_justified": not snapshot["all_semantic_checks_pass"],
            "engineering_cost_signal": snapshot["bounded_hot_provenance_overhead_is_real"],
        },
        {
            "raw_failure": "stale_dominance_resistance :: recent_concern_can_displace_old_concern",
            "classification": foreground_classification,
            "production_correctness_patch_justified": not foreground["all_semantic_checks_pass"],
            "engineering_cost_signal": False,
        },
    ]


def build_adjudication(stage4_report: dict[str, Any], work_root: Path) -> dict[str, Any]:
    validate_stage4_report(stage4_report)
    snapshot = _snapshot_probe(Path(work_root) / "snapshot")
    foreground = _foreground_probe(Path(work_root) / "foreground")
    classifications = _classify(snapshot, foreground)
    correctness_patch_count = sum(
        bool(row["production_correctness_patch_justified"]) for row in classifications
    )
    strict = (
        "NO_NEW_PRODUCTION_CORRECTNESS_DEFECT_CONFIRMED_TWO_RAW_FAILURES_REMAIN_"
        "FROZEN_BOUNDED_SNAPSHOT_OVERHEAD_FLAGGED"
        if correctness_patch_count == 0
        else "ADJUDICATION_FOUND_POSSIBLE_PRODUCTION_DEFECT_DO_NOT_PATCH_UNTIL_REVIEWED"
    )
    return {
        "stage": "npc_continuity_stage5_projection_adjudication",
        "raw_frozen_score_unchanged": {
            "baseline": {"passes": 62, "total": 62},
            "ghost": {"passes": 60, "total": 62},
            "remaining_raw_failures": deepcopy(STAGE4_EXPECTED_FAILED),
            "rescored": False,
        },
        "snapshot_adjudication": snapshot,
        "foreground_adjudication": foreground,
        "classifications": classifications,
        "new_production_correctness_defects_confirmed": correctness_patch_count,
        "strict_conclusion": strict,
        "frozen_benchmark_modified": False,
        "ghost_production_modified": False,
        "next_stage_rule": (
            "Preserve the Stage-1 60/62 raw result. Do not patch Ghost merely to satisfy either remaining literal. "
            "Any later cross-architecture benchmark must be additive/versioned and may measure semantic persistence, "
            "foreground recency, and engineering cost without rewriting Stage-1 history."
        ),
    }


def write_adjudication(stage4_report_path: Path, output_path: Path, work_root: Path) -> dict[str, Any]:
    report = json.loads(Path(stage4_report_path).read_text(encoding="utf-8"))
    result = build_adjudication(report, Path(work_root))
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result
