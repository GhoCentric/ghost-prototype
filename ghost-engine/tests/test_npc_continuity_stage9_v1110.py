from __future__ import annotations

import json
from pathlib import Path

import pytest

import continuity_benchmark_v1110.run_stage9_candidate_selection as runner


def _stage8_packet():
    variants = list(runner.VARIANTS)
    return {
        "strict_verdict": "LOSSLESS_COLD_COMPACTION_PRESERVES_STAGE6_VALUE_AND_BEATS_CURRENT_GHOST_TOTAL_PERSISTENT_COST",
        "variants_meeting_value_and_total_storage_target": variants,
        "quality": {kind: {"passed": 25, "total": 26} for kind in variants},
        "preservation": {kind: {"a": True, "b": True} for kind in variants},
        "lossless_equivalence": {"full_cold_records_exact": True, "restore_observation_exact": True},
        "integrity": {
            "manifest_mismatch_detected": True,
            "payload_tamper_detected": True,
            "projection_tamper_detected": True,
        },
        "ratios_to_stage7_lazy_sparse": {kind: {"total_vs_current_ghost": .9} for kind in variants},
    }


def _seed_records():
    out = {}
    for subsystem, field in (
        ("interpretation", "transitions"),
        ("emotion", "effective_impulses"),
        ("attention", "underlying_salience"),
    ):
        rows = []
        for sequence in range(1, 65):
            rows.append({"sequence": sequence, field: {"threat": {"after": .5} if field == "transitions" else .5}})
        out[subsystem] = rows
    return out


def test_helpers_real_archive_workload_memory_and_determinism(tmp_path):
    real_seed = runner._seed_records(tmp_path / "real-seed")
    assert {name: len(rows) for name, rows in real_seed.items()} == {"interpretation": 64, "emotion": 64, "attention": 64}
    records = _seed_records()
    assert runner._ratio(2, 0) is None
    assert runner._ratio(2, 4) == .5
    assert runner._median_us(lambda: None, repeats=2) >= 0
    with pytest.raises(ValueError, match="records_per_agent"):
        runner._subset(records, 12)
    subset = runner._subset(records, 24)
    assert all(len(rows) == 8 for rows in subset.values())
    assert runner._sample_agents(1) == ["npc-0000"]
    assert runner._sample_agents(4) == ["npc-0000", "npc-0002", "npc-0003"]

    row = runner._write_workload(tmp_path / "work", "ghost_compact_fast", 1, 24, records)
    assert row["records"] == 24
    assert row["manifest_records"] == 24

    from continuity_benchmark_v1110.stage8_cold_history_variants import CompactColdHistoryArchive
    archive = CompactColdHistoryArchive(tmp_path / "lookup.sqlite", compression_level=1)
    try:
        assert runner._exact_lookup(archive, "interpretation", "n", 1) is None
    finally:
        archive.close()

    mem = runner._memory_probe("ghost_compact_fast", tmp_path / "memory", records)
    assert mem["python_peak_bytes"] >= mem["python_current_bytes"] >= 0
    assert runner._deterministic_archive_probe("ghost_compact_fast", tmp_path / "det", records)


def test_inherited_eligibility_and_selection_paths():
    packet = _stage8_packet()
    all_true = runner._inherited_eligibility(packet, "ghost_compact_fast")
    assert all(all_true.values())
    broken = json.loads(json.dumps(packet))
    broken["quality"]["ghost_compact_fast"]["passed"] = 24
    broken["preservation"]["ghost_compact_fast"] = {}
    broken["lossless_equivalence"]["full_cold_records_exact"] = False
    broken["lossless_equivalence"]["restore_observation_exact"] = False
    broken["integrity"]["payload_tamper_detected"] = False
    broken["variants_meeting_value_and_total_storage_target"].remove("ghost_compact_fast")
    assert not all(runner._inherited_eligibility(broken, "ghost_compact_fast").values())

    lifecycle = {kind: {"restore_observation_exact": True, "save_median_us": 1., "restore_median_us": 1., "projection_median_us": 1., "recall_avg_us": 1.} for kind in runner.VARIANTS}
    base_row = {"bytes": 100, "write_total_us": 10., "manifest_us": 1., "exact_lookup_total_us": 1., "projection_read_total_us": 1., "full_read_total_us": 1.}
    probes = {"w": {kind: dict(base_row) for kind in runner.VARIANTS}}
    eligibility = {kind: {"ok": True} for kind in runner.VARIANTS}

    result = runner._select_candidate(eligibility, probes, lifecycle)
    assert result["selected"] == "ghost_compact_fast"
    assert "runtime tie" in result["reason"]

    lifecycle2 = json.loads(json.dumps(lifecycle))
    probes2 = {"w": {kind: dict(base_row) for kind in runner.VARIANTS}}
    probes2["w"]["ghost_compact_balanced"]["write_total_us"] = 1.
    probes2["w"]["ghost_compact_fast"]["write_total_us"] = 100.
    probes2["w"]["ghost_compact_dense"]["write_total_us"] = 100.
    result = runner._select_candidate(eligibility, probes2, lifecycle2)
    assert result["selected"] == "ghost_compact_balanced"
    assert "lowest aggregate" in result["reason"]

    no_eligible = {kind: {"ok": False} for kind in runner.VARIANTS}
    assert runner._select_candidate(no_eligible, probes, lifecycle)["selected"] is None

    too_large = {"w": {kind: dict(base_row) for kind in runner.VARIANTS}}
    # Different best candidate in each workload forces every candidate outside the 5% envelope somewhere.
    too_large["x"] = {kind: dict(base_row) for kind in runner.VARIANTS}
    too_large["y"] = {kind: dict(base_row) for kind in runner.VARIANTS}
    for kind in runner.VARIANTS:
        for label in too_large:
            too_large[label][kind]["bytes"] = 200
    too_large["w"]["ghost_compact_fast"]["bytes"] = 100
    too_large["x"]["ghost_compact_balanced"]["bytes"] = 100
    too_large["y"]["ghost_compact_dense"]["bytes"] = 100
    assert runner._select_candidate(eligibility, too_large, lifecycle)["selected"] is None
