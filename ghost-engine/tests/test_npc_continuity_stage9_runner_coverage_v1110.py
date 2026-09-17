from __future__ import annotations

import json
import runpy
import sys

import pytest

import continuity_benchmark_v1110.run_stage9_candidate_selection as runner


def _stage8_packet():
    variants = list(runner.VARIANTS)
    return {
        "strict_verdict": "LOSSLESS_COLD_COMPACTION_PRESERVES_STAGE6_VALUE_AND_BEATS_CURRENT_GHOST_TOTAL_PERSISTENT_COST",
        "variants_meeting_value_and_total_storage_target": variants,
        "quality": {kind: {"passed": 25, "total": 26} for kind in variants},
        "preservation": {kind: {"a": True} for kind in variants},
        "lossless_equivalence": {"full_cold_records_exact": True, "restore_observation_exact": True},
        "integrity": {"manifest_mismatch_detected": True, "payload_tamper_detected": True, "projection_tamper_detected": True},
        "ratios_to_stage7_lazy_sparse": {kind: {"total_vs_current_ghost": .9} for kind in variants},
    }


def _workrow(kind):
    return {
        "agents": 1, "records_per_agent": 24, "records": 24,
        "bytes": 100 if kind != "ghost_compact_fast" else 102,
        "write_total_us": {"ghost_compact_fast": 8., "ghost_compact_balanced": 10., "ghost_compact_dense": 12.}[kind],
        "manifest_us": 1., "exact_lookup_total_us": 1., "exact_lookup_count": 1,
        "projection_read_total_us": 1., "projection_rows_read": 1,
        "full_read_total_us": 1., "full_records_read": 1,
        "manifest_records": 24, "manifest_digest": kind,
    }


def test_build_result_and_precondition_failures(tmp_path, monkeypatch):
    packet = _stage8_packet()
    records = {name: [{"sequence": i} for i in range(1, 65)] for name in ("interpretation", "emotion", "attention")}
    monkeypatch.setattr(runner, "_seed_records", lambda root: records)
    monkeypatch.setattr(runner, "WORKLOADS", (("agent_scale_500_short", 1, 24),))
    monkeypatch.setattr(runner, "_write_workload", lambda root, kind, agents, depth, records: _workrow(kind))
    monkeypatch.setattr(runner, "_adapter_lifecycle", lambda kind, root: {
        "save_median_us": 1., "restore_median_us": 1., "recall_avg_us": 1., "projection_median_us": 1., "restore_observation_exact": True,
    })
    monkeypatch.setattr(runner, "_memory_probe", lambda kind, root, records: {"python_current_bytes": 1, "python_peak_bytes": 2})
    monkeypatch.setattr(runner, "_deterministic_archive_probe", lambda kind, root, records: True)
    result = runner.build_result(tmp_path / "ok", packet)
    assert result["selected_candidate"] == "ghost_compact_fast"
    assert result["strict_verdict"].endswith("GHOST_COMPACT_FAST")
    assert result["storage_summary"]["ghost_compact_fast"]["largest_agent_scale_vs_best"] is not None

    with pytest.raises(RuntimeError, match="successful Stage-8"):
        runner.build_result(tmp_path / "bad", {**packet, "strict_verdict": "no"})
    with pytest.raises(RuntimeError, match="all three"):
        runner.build_result(tmp_path / "bad2", {**packet, "variants_meeting_value_and_total_storage_target": ["ghost_compact_fast"]})

    monkeypatch.setattr(runner, "_select_candidate", lambda *args: {"selected": None, "eligible": [], "storage_near_best": [], "runtime_tie_set": [], "reason": "none"})
    result = runner.build_result(tmp_path / "none", packet)
    assert result["strict_verdict"] == "NO_STAGE9_PRODUCTION_CANDIDATE_SELECTED"
    assert result["selected_compression_level"] is None


def test_real_adapter_lifecycle_and_main_paths(tmp_path, monkeypatch, capsys):
    life = runner._adapter_lifecycle("ghost_compact_fast", tmp_path / "life")
    assert life["restore_observation_exact"]
    assert life["restore_median_us"] >= 0

    packet = _stage8_packet()
    report = tmp_path / "stage8.json"
    report.write_text(json.dumps(packet))
    fake = {"stage": "x", "strict_verdict": "ok"}
    monkeypatch.setattr(runner, "build_result", lambda root, stage8: fake)
    out = tmp_path / "out.json"
    assert runner.main(["--root", str(tmp_path / "root"), "--stage8-report", str(report), "--out", str(out)]) == 0
    assert json.loads(out.read_text()) == fake
    assert '"strict_verdict": "ok"' in capsys.readouterr().out
    assert runner.main(["--stage8-report", str(report)]) == 0

    bad_report = tmp_path / "bad-stage8.json"
    bad_report.write_text(json.dumps({"strict_verdict": "no"}))
    module_name = "continuity_benchmark_v1110.run_stage9_candidate_selection"
    saved = sys.modules.pop(module_name)
    old = sys.argv[:]
    sys.argv = ["run_stage9_candidate_selection", "--stage8-report", str(bad_report)]
    try:
        with pytest.raises(RuntimeError, match="successful Stage-8"):
            runpy.run_module(module_name, run_name="__main__")
    finally:
        sys.argv = old
        sys.modules[module_name] = saved


def test_failure_guards_are_executable(tmp_path, monkeypatch):
    class SeedSystem:
        def snapshot(self): return {}
        def close(self): pass
    monkeypatch.setattr(runner, "optimized_factory", lambda *args, **kwargs: SeedSystem())
    monkeypatch.setattr(runner, "_populate", lambda *args, **kwargs: [])
    monkeypatch.setattr(runner, "_cold_records", lambda system: {"interpretation": [], "emotion": [], "attention": []})
    with pytest.raises(RuntimeError, match="64/64/64"):
        runner._seed_records(tmp_path / "seed")

    records = {
        "interpretation": [{"sequence": i, "transitions": {"x": {"after": .1}}} for i in range(1, 65)],
        "emotion": [{"sequence": i, "effective_impulses": {"fear": .1}} for i in range(1, 65)],
        "attention": [{"sequence": i, "underlying_salience": {"emotion:fear": .1}} for i in range(1, 65)],
    }

    class FakeArchive:
        mode = "count"
        def __init__(self, *args, **kwargs): self._db = object()
        def put(self, *args): pass
        def count(self): return 0 if self.mode == "count" else 24
        def bytes(self): return 1
        def manifest(self): return {"records": 24, "digest": "x"}
        def projection_rows(self, subsystem, agent): return [] if self.mode == "projection" else [(i, []) for i in range(1, 9)]
        def records(self, subsystem, agent): return [] if self.mode == "full" else runner._subset(records, 24)[subsystem]
        def close(self): pass
    original_archive = runner.CompactColdHistoryArchive
    monkeypatch.setattr(runner, "CompactColdHistoryArchive", FakeArchive)
    with pytest.raises(RuntimeError, match="record count"):
        runner._write_workload(tmp_path / "count", "ghost_compact_fast", 1, 24, records)

    FakeArchive.mode = "exact"
    monkeypatch.setattr(runner, "_exact_lookup", lambda *args: {})
    with pytest.raises(RuntimeError, match="exact cold lookup"):
        runner._write_workload(tmp_path / "exact", "ghost_compact_fast", 1, 24, records)

    monkeypatch.setattr(runner, "_exact_lookup", lambda store, subsystem, agent, sequence: runner._subset(records, 24)[subsystem][-1])
    FakeArchive.mode = "projection"
    with pytest.raises(RuntimeError, match="projection index"):
        runner._write_workload(tmp_path / "projection", "ghost_compact_fast", 1, 24, records)

    FakeArchive.mode = "full"
    with pytest.raises(RuntimeError, match="full cold read"):
        runner._write_workload(tmp_path / "full", "ghost_compact_fast", 1, 24, records)
    monkeypatch.setattr(runner, "CompactColdHistoryArchive", original_archive)

    class RecallSystem:
        def observe(self, agent): return {"x": 1}
        def snapshot(self): return {"s": 1}
        def close(self): pass
        def recall_episode(self, episode_id, strength): return {"status": "wrong"}
        def working_projections(self, agent): return []
    monkeypatch.setattr(runner, "compact_factory", lambda *args, **kwargs: RecallSystem())
    monkeypatch.setattr(runner, "_populate", lambda system, count: ["e1"])
    with pytest.raises(RuntimeError, match="recall status"):
        runner._adapter_lifecycle("ghost_compact_fast", tmp_path / "recall")
