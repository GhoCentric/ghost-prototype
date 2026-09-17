"""Frozen contract for the Ghost-vs-simple NPC continuity comparison.

Stage 1 freezes the problem before a Ghost adapter is allowed to exist.  The
contract deliberately gives the purpose-built baseline several techniques that
Ghost also uses (durable exact episode IDs, an external archive, and pairwise
foreground hysteresis) so the later comparison is not "Ghost vs a toy that
forgets everything".
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json


CONTRACT_VERSION = "1.0"
BASELINE_RELEASE_RATE = 0.48
BASELINE_SWITCH_THRESHOLD = 0.05
BASELINE_EMOTION_RETENTION = {
    "anger": 0.88,
    "fear": 0.86,
    "grief": 0.94,
    "hope": 0.92,
}

class CapacityBackpressureError(RuntimeError):
    """Neutral benchmark signal for explicit no-eviction capacity failure."""


class ArchiveMismatchError(RuntimeError):
    """Neutral benchmark signal for snapshot/archive integrity mismatch."""


# "competence" scenarios are minimum requirements for a baseline worth using.
# "discriminator" scenarios remain frozen but are not used to tune the later
# Ghost adapter.  Stage 2 must run both systems against these exact checks.
_SCENARIOS = (
    {
        "id": "moving_on_without_erasure",
        "class": "competence",
        "categories": ("retention", "relevance", "affect"),
        "checks": (
            "meaning_persists",
            "relevance_releases",
            "old_concern_not_foreground",
            "associated_affect_relaxes",
        ),
    },
    {
        "id": "exact_recall_without_replay",
        "class": "competence",
        "categories": ("recall", "causal_integrity", "affect"),
        "checks": (
            "meaning_unchanged",
            "consequence_unchanged",
            "target_relevance_rises",
            "target_becomes_current_again",
            "episode_affect_reexpresses",
        ),
    },
    {
        "id": "same_dimension_identity_and_ambiguity",
        "class": "competence",
        "categories": ("identity", "recall", "causal_integrity"),
        "checks": (
            "episode_ids_are_distinct",
            "dimension_lookup_is_ambiguous",
            "ambiguous_dimension_recall_does_not_mutate_hot_state",
            "exact_second_recall_uses_second_episode_affect",
        ),
    },
    {
        "id": "revision_without_rewind",
        "class": "competence",
        "categories": ("revision", "causal_integrity", "recall"),
        "checks": (
            "meaning_revises_down",
            "consequence_does_not_rewind",
            "affect_does_not_rewind_instantly",
            "old_episode_recall_does_not_restore_old_meaning",
        ),
    },
    {
        "id": "snapshot_archive_pairing",
        "class": "competence",
        "categories": ("persistence", "identity", "causal_integrity"),
        "checks": (
            "hot_snapshot_excludes_episode_payloads",
            "snapshot_contains_archive_manifest",
            "matching_archive_restores_exact_hot_state",
            "wrong_archive_is_rejected",
            "exact_recall_works_after_restart",
        ),
    },
    {
        "id": "capacity_no_silent_eviction",
        "class": "competence",
        "categories": ("retention", "causal_integrity", "persistence"),
        "checks": (
            "capacity_failure_is_explicit",
            "existing_episode_survives",
            "archive_count_does_not_change",
            "failed_event_does_not_partially_mutate_hot_state",
        ),
    },
    {
        "id": "near_tie_hysteresis",
        "class": "competence",
        "categories": ("stability",),
        "checks": (
            "alternating_near_tie_does_not_flip",
            "trace_is_deterministic",
        ),
    },
    {
        "id": "multi_agent_isolation",
        "class": "competence",
        "categories": ("isolation",),
        "checks": (
            "other_agent_meaning_unchanged",
            "other_agent_relevance_unchanged",
            "other_agent_affect_unchanged",
            "other_agent_consequence_unchanged",
        ),
    },
    {
        "id": "long_history_selective_old_recall",
        "class": "discriminator",
        "categories": ("identity", "recall", "retention"),
        "checks": (
            "old_episode_still_exists",
            "old_episode_profile_is_exact",
            "old_exact_recall_does_not_change_meaning",
            "old_exact_recall_raises_only_target_dimension",
            "all_history_remains_counted",
        ),
    },
    {
        "id": "same_dimension_episode_specific_affect",
        "class": "discriminator",
        "categories": ("identity", "affect", "recall"),
        "checks": (
            "older_exact_recall_prefers_older_affect",
            "newer_exact_recall_prefers_newer_affect",
            "older_and_newer_ids_remain_distinct",
            "meaning_is_unchanged_by_both_recalls",
        ),
    },
    {
        "id": "repeated_recall_load",
        "class": "discriminator",
        "categories": ("recall", "affect", "relevance"),
        "checks": (
            "repeated_recall_increases_relevance_load",
            "repeated_recall_increases_affect_load",
        ),
    },
    {
        "id": "stale_dominance_resistance",
        "class": "discriminator",
        "categories": ("relevance", "retention", "recall"),
        "checks": (
            "recent_concern_can_displace_old_concern",
            "old_meaning_is_not_erased",
            "old_relevance_becomes_small",
            "exact_old_recall_can_restore_old_relevance",
        ),
    },
    {
        "id": "repeated_restart_stability",
        "class": "discriminator",
        "categories": ("persistence", "identity", "determinism"),
        "checks": (
            "hot_state_survives_twenty_restarts",
            "archive_manifest_survives_twenty_restarts",
            "episode_ids_survive_twenty_restarts",
            "restart_cycles_do_not_duplicate_episodes",
        ),
    },
    {
        "id": "causal_duplication_torture",
        "class": "discriminator",
        "categories": ("causal_integrity", "recall"),
        "checks": (
            "one_hundred_recalls_do_not_change_consequence",
            "one_hundred_recalls_do_not_duplicate_episode",
            "one_hundred_recalls_do_not_rewrite_meaning",
        ),
    },
    {
        "id": "revision_then_old_recall",
        "class": "discriminator",
        "categories": ("revision", "recall", "causal_integrity"),
        "checks": (
            "revised_meaning_stays_revised",
            "old_episode_can_become_relevant_again",
            "old_recall_does_not_rewind_consequence",
            "old_recall_uses_historical_episode_affect",
        ),
    },
    {
        "id": "large_ambiguity_safety",
        "class": "discriminator",
        "categories": ("identity", "recall", "causal_integrity"),
        "checks": (
            "fifty_same_dimension_episodes_are_reported_ambiguous",
            "ambiguous_recall_leaves_meaning_unchanged",
            "ambiguous_recall_leaves_relevance_unchanged",
            "ambiguous_recall_leaves_affect_unchanged",
        ),
    },
)


def scenario_manifest() -> tuple[dict, ...]:
    return tuple(deepcopy(row) for row in _SCENARIOS)


def contract_packet() -> dict:
    return {
        "contract_version": CONTRACT_VERSION,
        "baseline_shared_defaults": {
            "release_rate": BASELINE_RELEASE_RATE,
            "switch_threshold": BASELINE_SWITCH_THRESHOLD,
            "emotion_retention": dict(sorted(BASELINE_EMOTION_RETENTION.items())),
        },
        "scenario_policy": {
            "competence_must_pass": True,
            "discriminators_are_frozen_before_ghost_adapter": True,
            "automatic_forgetting_allowed": False,
            "silent_eviction_allowed": False,
            "llm_calls_allowed": False,
            "oracle_access_by_system_implementation": False,
        },
        "scenarios": scenario_manifest(),
    }


def contract_digest() -> str:
    text = json.dumps(
        contract_packet(),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
