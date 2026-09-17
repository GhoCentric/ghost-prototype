"""Stage-3 autopsy of the four frozen Stage-2 Ghost continuity failures.

Stage 3 is diagnostic only. It does not modify Ghost production code and it does
not alter, rescore, or replace any frozen Stage-1 check. The raw Stage-2 result
remains 58/62. This module asks a narrower question: which raw failures are
actual production semantic defects, and which are representation/projection
mismatches between the frozen purpose-built contract and Ghost's richer state?
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from .ghost_adapter import ghost_factory


STAGE2_EXPECTED_FAILED = {
    "large_ambiguity_safety": ["ambiguous_recall_leaves_relevance_unchanged"],
    "same_dimension_identity_and_ambiguity": [
        "ambiguous_dimension_recall_does_not_mutate_hot_state"
    ],
    "snapshot_archive_pairing": ["hot_snapshot_excludes_episode_payloads"],
    "stale_dominance_resistance": ["recent_concern_can_displace_old_concern"],
}


def validate_stage2_report(report: dict[str, Any]) -> None:
    """Refuse to autopsy anything except the exact frozen Stage-2 outcome."""
    if report.get("stage") != "npc_continuity_stage2_frozen_head_to_head":
        raise ValueError("not the frozen Stage-2 continuity report")
    if report.get("baseline_result", {}).get("all_checks") != {"passes": 62, "total": 62}:
        raise ValueError("Stage-2 baseline result is not exact 62/62")
    if report.get("ghost_result", {}).get("all_checks") != {"passes": 58, "total": 62}:
        raise ValueError("Stage-2 Ghost result is not exact 58/62")
    if report.get("raw_comparison", {}).get("failed_checks") != STAGE2_EXPECTED_FAILED:
        raise ValueError("Stage-2 failed-check set drifted")
    if report.get("ghost_deterministic_rerun") is not True:
        raise ValueError("Stage-2 Ghost deterministic rerun did not pass")
    if report.get("stage1_baseline_replay_exact") is not True:
        raise ValueError("Stage-1 frozen replay is not exact")
    if report.get("strict_stage2_verdict") != "GHOST_DOES_NOT_MATCH_FROZEN_COMPETENT_BASELINE":
        raise ValueError("Stage-2 strict verdict drifted")


def _contract_state_diff(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    return sorted(key for key in before if before[key] != after[key])


def _contains_equal_subtree(value: Any, target: Any) -> bool:
    if value == target:
        return True
    if isinstance(value, dict):
        return any(_contains_equal_subtree(child, target) for child in value.values())
    if isinstance(value, list):
        return any(_contains_equal_subtree(child, target) for child in value)
    return False


def _paths_for_key(value: Any, key: str, prefix: tuple[str, ...] = ()) -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for raw_name, child in value.items():
            name = str(raw_name)
            child_prefix = prefix + (name,)
            if name == key:
                paths.append(".".join(child_prefix))
            paths.extend(_paths_for_key(child, key, child_prefix))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(_paths_for_key(child, key, prefix + (str(index),)))
    return paths


def _ambiguity_probe(root: Path, *, count: int, tick_each: bool) -> dict[str, Any]:
    system = ghost_factory(root, f"ambiguity-{count}")
    try:
        for index in range(count):
            system.event(
                "npc",
                source=f"betrayal-{index}",
                dimension="betrayal",
                meaning_delta=0.01 if count > 2 else 0.45,
                relevance=0.1 if count > 2 else 0.8,
                emotion_profile={"anger": 0.01} if count > 2 else ({"anger": 0.8} if index == 0 else {"fear": 0.6}),
                consequence=0.0 if count > 2 else -0.5,
            )
            if tick_each:
                system.tick("npc", 1)

        before_lookup = system.observe("npc")
        direct_lookup = system.archive.resolve_dimension("npc", "betrayal")
        after_lookup = system.observe("npc")

        original_recall = system._ghost.continuity.recall
        calls: list[tuple[str, str, float]] = []

        def tracked_recall(agent: str, dimension: str, strength: float) -> dict[str, Any]:
            calls.append((agent, dimension, float(strength)))
            return original_recall(agent, dimension, strength)

        system._ghost.continuity.recall = tracked_recall
        try:
            packet = system.recall_dimension("npc", "betrayal", 1.0 if count > 2 else 0.5)
        finally:
            system._ghost.continuity.recall = original_recall
        after_api = system.observe("npc")

        return {
            "candidate_count": direct_lookup["candidate_count"],
            "direct_lookup_status": direct_lookup["status"],
            "direct_lookup_hot_state_unchanged": after_lookup == before_lookup,
            "api_lookup_status": packet["status"],
            "continuity_recall_call_count": len(calls),
            "changed_contract_state_fields": _contract_state_diff(after_lookup, after_api),
            "activation_before": before_lookup["activation"]["betrayal"],
            "activation_after": after_api["activation"]["betrayal"],
            "meaning_unchanged": after_api["meaning"] == before_lookup["meaning"],
            "emotion_unchanged": after_api["emotion"] == before_lookup["emotion"],
            "trust_unchanged": after_api["trust"] == before_lookup["trust"],
            "episode_count_unchanged": after_api["episode_count"] == before_lookup["episode_count"],
        }
    finally:
        system.close()


def _snapshot_probe(root: Path) -> dict[str, Any]:
    system = ghost_factory(root, "snapshot")
    try:
        row = system.event(
            "npc",
            source="betrayal-1",
            dimension="betrayal",
            meaning_delta=0.9,
            relevance=0.9,
            emotion_profile={"anger": 0.8},
            consequence=-1.0,
        )
        snapshot = system.snapshot()
        record = system.get_episode(row["episode_id"])
        encoded = json.dumps(snapshot, sort_keys=True)
        continuity_packet = snapshot["ghost"]["continuity"]
        source_paths = _paths_for_key(snapshot, "source")
        return {
            "raw_frozen_literal_passes": "emotion_profile" not in encoded and "source" not in encoded,
            "emotion_profile_key_absent": not _paths_for_key(snapshot, "emotion_profile"),
            "episode_id_absent": not _contains_equal_subtree(snapshot, row["episode_id"]),
            "exact_episode_record_absent": not _contains_equal_subtree(snapshot, record),
            "continuity_packet_keys": sorted(continuity_packet),
            "continuity_archive_is_manifest_only": set(continuity_packet["episode_archive"]) == {
                "schema", "archive_schema", "record_count", "content_digest"
            },
            "source_paths": source_paths,
            "all_source_paths_are_source_owned_history": all(
                path.startswith((
                    "ghost.emotions.agents.npc.history.",
                    "ghost.interpretations.agents.npc.history.",
                    "ghost.attention.agents.npc.history.",
                ))
                for path in source_paths
            ),
        }
    finally:
        system.close()


def _run_stale_stream(root: Path, label: str, recent_emotion: dict[str, float]) -> dict[str, Any]:
    system = ghost_factory(root, label)
    try:
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
                source=f"respect-{index}",
                dimension="respect",
                meaning_delta=0.002,
                relevance=0.25,
                emotion_profile=recent_emotion,
                consequence=0.02,
            )
            system.tick("npc", 1)
        observed = system.observe("npc")
        attention = system._ghost.attention_state("npc")
        assert attention is not None
        latest = attention["history"][-1]
        return {
            "foreground": observed["foreground"],
            "betrayal_activation": observed["activation"]["betrayal"],
            "respect_activation": observed["activation"]["respect"],
            "hope_level": observed["emotion"]["hope"],
            "latest_attended_salience": deepcopy(latest["attended_salience"]),
        }
    finally:
        system.close()


def _stale_probe(root: Path) -> dict[str, Any]:
    frozen_stream = _run_stale_stream(root, "stale-frozen", {"hope": 0.1})
    no_recent_emotion = _run_stale_stream(root, "stale-no-recent-emotion", {})
    return {
        "frozen_stream": frozen_stream,
        "control_without_recent_emotion": no_recent_emotion,
        "old_betrayal_is_not_foreground": frozen_stream["foreground"] != "betrayal",
        "old_betrayal_is_numerically_stale": frozen_stream["betrayal_activation"] < 1e-6,
        "recent_emotion_wins_cross_layer_competition": frozen_stream["foreground"] == "emotion:hope",
        "interpretation_respect_wins_when_recent_emotion_removed": no_recent_emotion["foreground"] == "respect",
    }


def _classify_evidence(
    ambiguity_two: dict[str, Any],
    ambiguity_fifty: dict[str, Any],
    snapshot: dict[str, Any],
    stale: dict[str, Any],
) -> tuple[bool, bool, bool]:
    ambiguity_defect = all((
        ambiguity_two["direct_lookup_status"] == "ambiguous",
        ambiguity_two["direct_lookup_hot_state_unchanged"],
        ambiguity_two["api_lookup_status"] == "ambiguous",
        ambiguity_two["continuity_recall_call_count"] == 1,
        "activation" in ambiguity_two["changed_contract_state_fields"],
        ambiguity_fifty["direct_lookup_status"] == "ambiguous",
        ambiguity_fifty["direct_lookup_hot_state_unchanged"],
        ambiguity_fifty["api_lookup_status"] == "ambiguous",
        ambiguity_fifty["continuity_recall_call_count"] == 1,
        "activation" in ambiguity_fifty["changed_contract_state_fields"],
    ))
    snapshot_projection = all((
        not snapshot["raw_frozen_literal_passes"],
        snapshot["emotion_profile_key_absent"],
        snapshot["episode_id_absent"],
        snapshot["exact_episode_record_absent"],
        snapshot["continuity_archive_is_manifest_only"],
        snapshot["all_source_paths_are_source_owned_history"],
    ))
    stale_projection = all((
        stale["old_betrayal_is_not_foreground"],
        stale["old_betrayal_is_numerically_stale"],
        stale["recent_emotion_wins_cross_layer_competition"],
        stale["interpretation_respect_wins_when_recent_emotion_removed"],
    ))
    return ambiguity_defect, snapshot_projection, stale_projection


def _classification_rows() -> list[dict[str, Any]]:
    return [
        {
            "raw_failures": [
                "same_dimension_identity_and_ambiguity :: ambiguous_dimension_recall_does_not_mutate_hot_state",
                "large_ambiguity_safety :: ambiguous_recall_leaves_relevance_unchanged",
            ],
            "classification": "genuine_production_semantic_defect",
            "unique_root": "ambiguous dimension recall mutates interpretation activation before causal episode identity is unique",
            "production_fix_justified": True,
        },
        {
            "raw_failures": ["snapshot_archive_pairing :: hot_snapshot_excludes_episode_payloads"],
            "classification": "frozen_literal_projection_mismatch",
            "unique_root": "the frozen literal bans every source key, including non-episode source-owned provenance",
            "production_fix_justified": False,
        },
        {
            "raw_failures": ["stale_dominance_resistance :: recent_concern_can_displace_old_concern"],
            "classification": "cross_layer_foreground_projection_mismatch",
            "unique_root": "Ghost foreground competes interpretation and emotion while the frozen baseline foreground is interpretation-only",
            "production_fix_justified": False,
        },
    ]


def _result_packet(
    ambiguity_two: dict[str, Any],
    ambiguity_fifty: dict[str, Any],
    snapshot: dict[str, Any],
    stale: dict[str, Any],
) -> dict[str, Any]:
    return {
        "stage": "npc_continuity_stage3_failure_autopsy",
        "raw_stage2_result_unchanged": {
            "baseline": {"passes": 62, "total": 62},
            "ghost": {"passes": 58, "total": 62},
            "failed_checks": deepcopy(STAGE2_EXPECTED_FAILED),
            "rescored": False,
        },
        "autopsy": {
            "ambiguity_two": ambiguity_two,
            "ambiguity_fifty": ambiguity_fifty,
            "snapshot": snapshot,
            "stale_foreground": stale,
        },
        "classifications": _classification_rows(),
        "unique_production_defect_roots": 1,
        "raw_checks_affected_by_production_defect": 2,
        "raw_checks_affected_by_projection_mismatch": 2,
        "strict_conclusion": "ONE_GHOST_PRODUCTION_DEFECT_ROOT_CONFIRMED_TWO_FROZEN_PROJECTION_MISMATCHES_PRESERVED",
        "next_stage_rule": (
            "The frozen Stage-1 benchmark remains unchanged. A next production patch may address only the ambiguous-recall "
            "mutation root, then rerun the frozen head-to-head as a new stage. The two projection failures remain raw failures "
            "and may not be erased by editing the frozen benchmark."
        ),
    }


def build_autopsy(report: dict[str, Any], work_root: Path) -> dict[str, Any]:
    validate_stage2_report(report)
    ambiguity_two = _ambiguity_probe(work_root / "ambiguity-two", count=2, tick_each=False)
    ambiguity_fifty = _ambiguity_probe(work_root / "ambiguity-fifty", count=50, tick_each=True)
    snapshot = _snapshot_probe(work_root / "snapshot")
    stale = _stale_probe(work_root / "stale")
    ambiguity_defect, snapshot_projection, stale_projection = _classify_evidence(
        ambiguity_two, ambiguity_fifty, snapshot, stale
    )
    if not ambiguity_defect:
        raise RuntimeError("Stage-3 evidence did not reproduce the ambiguous-recall production defect")
    if not snapshot_projection:
        raise RuntimeError("Stage-3 evidence did not support the snapshot projection diagnosis")
    if not stale_projection:
        raise RuntimeError("Stage-3 evidence did not support the foreground projection diagnosis")
    return _result_packet(ambiguity_two, ambiguity_fifty, snapshot, stale)

def write_autopsy(stage2_report_path: Path, output_path: Path, work_root: Path) -> dict[str, Any]:
    report = json.loads(Path(stage2_report_path).read_text(encoding="utf-8"))
    result = build_autopsy(report, Path(work_root))
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result
