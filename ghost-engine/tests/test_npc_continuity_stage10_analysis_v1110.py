import pytest
from continuity_benchmark_v1110.stage10_hotpath_analysis import (
    build_summary,
    classify_hotpath,
    ratio,
)


def result(*, event=2.0, recall=2.0, ne=0.8, nr=1.2, se=0.7, sr=1.1,
           de=0.75, dr=1.15, es=0.5, rs=0.5, full=1000.0, off=100.0):
    return {
        "baseline": {"totals": {"event_us": 100.0, "recall_us": 100.0}},
        "candidate": {
            "totals": {"event_us": 100.0 * event, "recall_us": 100.0 * recall},
            "toggles": {
                "no_compaction_event_us": 100.0 * ne,
                "no_compaction_recall_us": 100.0 * nr,
                "sync_off_event_us": 100.0 * se,
                "sync_off_recall_us": 100.0 * sr,
                "deferred_event_hot_us": 100.0 * de,
                "deferred_recall_hot_us": 100.0 * dr,
            },
            "event_profile": {"top_level_share": {"history_compaction": es}},
            "recall_profile": {"top_level_share": {"history_compaction": rs}},
            "durability_probe_us": {
                "full_delete_store_batch_us": full,
                "off_delete_store_batch_us": off,
            },
        },
    }


def test_ratio_and_summary():
    assert ratio(2, 4) == 0.5
    with pytest.raises(ValueError, match="denominator must be positive"):
        ratio(1, 0)
    r = result()
    s = build_summary(r)
    assert s == {
        "event_ratio": 2.0,
        "recall_ratio": 2.0,
        "candidate_event_without_compaction_ratio": 0.8,
        "candidate_recall_without_compaction_ratio": 1.2,
        "candidate_event_sync_off_ratio": 0.7,
        "candidate_recall_sync_off_ratio": 1.1,
        "deferred_event_hot_ratio": 0.75,
        "deferred_recall_hot_ratio": 1.15,
        "event_compaction_share": 0.5,
        "recall_compaction_share": 0.5,
    }
    r["candidate"]["event_profile"]["top_level_share"].clear()
    r["candidate"]["recall_profile"]["top_level_share"].clear()
    s = build_summary(r)
    assert s["event_compaction_share"] == 0.0
    assert s["recall_compaction_share"] == 0.0


def test_classification_ladder():
    assert classify_hotpath(result()) == (
        "COLD_HISTORY_DURABLE_COMMIT_DOMINATES_EVENT_AND_RECALL_HOT_PATH"
    )
    assert classify_hotpath(result(off=0.0)) == (
        "COLD_HISTORY_DURABLE_COMMIT_DOMINATES_EVENT_AND_RECALL_HOT_PATH"
    )
    assert classify_hotpath(result(full=150.0, off=100.0)) == (
        "COLD_HISTORY_HOTPATH_COMPACTION_IS_SUFFICIENT_CAUSE_OF_PRODUCTION_GATE_FAILURE"
    )
    assert classify_hotpath(result(ne=1.2, nr=2.0, es=0.5, rs=0.5)) == (
        "COLD_HISTORY_COMPACTION_DOMINATES_EVENT_AND_RECALL_HOT_PATH"
    )
    assert classify_hotpath(result(event=0.5, recall=1.0, ne=1.2, nr=2.0, es=0.5, rs=0.1)) == (
        "COLD_HISTORY_COMPACTION_DOMINATES_EVENT_HOT_PATH_ONLY"
    )
    assert classify_hotpath(result(event=0.5, recall=1.0, ne=1.2, nr=2.0, es=0.1, rs=0.5)) == (
        "COLD_HISTORY_COMPACTION_DOMINATES_RECALL_HOT_PATH_ONLY"
    )
    assert classify_hotpath(result(event=0.5, recall=1.0, ne=1.2, nr=2.0, es=0.1, rs=0.1)) == (
        "HOT_PATH_COST_DISTRIBUTED_NO_SINGLE_DOMINANT_ROOT"
    )
