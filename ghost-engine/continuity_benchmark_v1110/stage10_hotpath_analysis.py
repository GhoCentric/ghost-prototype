"""Pure analysis rules for Stage-10 production hot-path autopsy."""
from __future__ import annotations
from typing import Any

EVENT_LIMIT = 0.95
RECALL_LIMIT = 1.75


def ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0.0:
        raise ValueError("denominator must be positive")
    return float(numerator) / float(denominator)


def classify_hotpath(result: dict[str, Any]) -> str:
    base = result["baseline"]["totals"]
    cand = result["candidate"]["totals"]
    toggles = result["candidate"]["toggles"]
    event_profile = result["candidate"]["event_profile"]
    recall_profile = result["candidate"]["recall_profile"]
    durability = result["candidate"]["durability_probe_us"]

    event_ratio = ratio(cand["event_us"], base["event_us"])
    recall_ratio = ratio(cand["recall_us"], base["recall_us"])
    event_regressed = event_ratio > EVENT_LIMIT
    recall_regressed = recall_ratio > RECALL_LIMIT
    event_compact_share = event_profile["top_level_share"].get("history_compaction", 0.0)
    recall_compact_share = recall_profile["top_level_share"].get("history_compaction", 0.0)
    no_comp_event = ratio(toggles["no_compaction_event_us"], base["event_us"])
    no_comp_recall = ratio(toggles["no_compaction_recall_us"], base["recall_us"])
    compaction_restores_gate = (
        no_comp_event <= EVENT_LIMIT and no_comp_recall <= RECALL_LIMIT
    )
    full = durability["full_delete_store_batch_us"]
    off = durability["off_delete_store_batch_us"]
    sync_tax = ratio(full, off) if off > 0.0 else float("inf")

    if (
        event_regressed
        and recall_regressed
        and compaction_restores_gate
        and event_compact_share >= 0.20
        and recall_compact_share >= 0.15
        and sync_tax >= 2.0
    ):
        return "COLD_HISTORY_DURABLE_COMMIT_DOMINATES_EVENT_AND_RECALL_HOT_PATH"
    if event_regressed and recall_regressed and compaction_restores_gate:
        return "COLD_HISTORY_HOTPATH_COMPACTION_IS_SUFFICIENT_CAUSE_OF_PRODUCTION_GATE_FAILURE"
    if event_compact_share >= 0.35 and recall_compact_share >= 0.35:
        return "COLD_HISTORY_COMPACTION_DOMINATES_EVENT_AND_RECALL_HOT_PATH"
    if event_compact_share >= 0.35:
        return "COLD_HISTORY_COMPACTION_DOMINATES_EVENT_HOT_PATH_ONLY"
    if recall_compact_share >= 0.35:
        return "COLD_HISTORY_COMPACTION_DOMINATES_RECALL_HOT_PATH_ONLY"
    return "HOT_PATH_COST_DISTRIBUTED_NO_SINGLE_DOMINANT_ROOT"


def build_summary(result: dict[str, Any]) -> dict[str, Any]:
    base = result["baseline"]["totals"]
    cand = result["candidate"]["totals"]
    toggles = result["candidate"]["toggles"]
    return {
        "event_ratio": ratio(cand["event_us"], base["event_us"]),
        "recall_ratio": ratio(cand["recall_us"], base["recall_us"]),
        "candidate_event_without_compaction_ratio": ratio(
            toggles["no_compaction_event_us"], base["event_us"]
        ),
        "candidate_recall_without_compaction_ratio": ratio(
            toggles["no_compaction_recall_us"], base["recall_us"]
        ),
        "candidate_event_sync_off_ratio": ratio(
            toggles["sync_off_event_us"], base["event_us"]
        ),
        "candidate_recall_sync_off_ratio": ratio(
            toggles["sync_off_recall_us"], base["recall_us"]
        ),
        "deferred_event_hot_ratio": ratio(
            toggles["deferred_event_hot_us"], base["event_us"]
        ),
        "deferred_recall_hot_ratio": ratio(
            toggles["deferred_recall_hot_us"], base["recall_us"]
        ),
        "event_compaction_share": result["candidate"]["event_profile"][
            "top_level_share"
        ].get("history_compaction", 0.0),
        "recall_compaction_share": result["candidate"]["recall_profile"][
            "top_level_share"
        ].get("history_compaction", 0.0),
    }
