from __future__ import annotations

import json
from pathlib import Path

import pytest

import continuity_benchmark_v1110.run_stage8_cold_compaction as runner


def test_helpers_and_main(tmp_path, monkeypatch, capsys):
    packet = {"scenarios": {"a": {"checks": {"x": True}}}}
    monkeypatch.setattr(runner, "GHOST_ONLY_TARGETS", ("a :: x",))
    assert runner._wins_preserved(packet)
    assert runner._ratio(2, 0) is None
    assert runner._ratio(2, 4) == .5
    assert runner._time_us(lambda: None, repeats=2) >= 0

    fake = {
        "stage": "x",
        "strict_verdict": "ok",
    }
    s6 = tmp_path / "s6.json"; s6.write_text("{}")
    s7 = tmp_path / "s7.json"; s7.write_text("{}")
    out = tmp_path / "out.json"
    monkeypatch.setattr(runner, "build_result", lambda root, stage6, stage7: fake)
    assert runner.main(["--root", str(tmp_path / "r"), "--stage6-report", str(s6), "--stage7-report", str(s7), "--out", str(out)]) == 0
    assert json.loads(out.read_text()) == fake
    assert '"strict_verdict": "ok"' in capsys.readouterr().out


def test_build_result_verdict_paths(tmp_path, monkeypatch):
    stage6 = {"quality": {"baseline": {"passed": 23, "total": 26}}}
    base_engineering = {
        "event_avg_us": 10.0,
        "dormant_materialize_us": 10.0,
        "active_tick_cycle_avg_us": 10.0,
        "recall_avg_us": 10.0,
        "hot_snapshot_bytes": 100,
        "episode_archive_bytes": 100,
        "cold_history_bytes": 100,
        "total_persistent_bytes": 300,
    }
    stage7 = {
        "strict_verdict": "LAZY_PLUS_SPARSE_PRESERVES_STAGE6_VALUE_OPTIMIZATION_PATH_SURVIVES",
        "engineering": {"ghost_lazy_sparse": dict(base_engineering), "ghost_current": {**base_engineering, "total_persistent_bytes": 400}},
        "projection_gate": {},
    }
    quality = {"passed": 25, "total": 26, "scenarios": {"a": {"checks": {"x": True}}}}
    monkeypatch.setattr(runner, "GHOST_ONLY_TARGETS", ("a :: x",))
    monkeypatch.setattr(runner, "run_stage6_quality_for_compact", lambda kind, root: quality)
    monkeypatch.setattr(runner, "patched_stage6_factory", _fake_context)
    monkeypatch.setattr(runner, "_foreground_ablation", lambda baseline, packet: {"equalized_without_foreground": True})
    monkeypatch.setattr(runner, "_engineering", lambda kind, root: {**base_engineering, "cold_history_records": 1, "hot_history_counts": {}, "manifest": {}})
    monkeypatch.setattr(runner, "_lossless_equivalence", lambda root: {"a": True})
    monkeypatch.setattr(runner, "_integrity_probe", lambda root: {"a": True})
    result = runner.build_result(tmp_path, stage6, stage7)
    assert result["strict_verdict"].startswith("LOSSLESS")

    monkeypatch.setattr(runner, "_engineering", lambda kind, root: {**base_engineering, "total_persistent_bytes": 500, "cold_history_records": 1, "hot_history_counts": {}, "manifest": {}})
    result = runner.build_result(tmp_path / "b", stage6, stage7)
    assert result["strict_verdict"].startswith("COLD_COMPACTION_PRESERVES")

    bad_quality = {**quality, "passed": 24}
    monkeypatch.setattr(runner, "run_stage6_quality_for_compact", lambda kind, root: bad_quality)
    result = runner.build_result(tmp_path / "c", stage6, stage7)
    assert result["strict_verdict"].startswith("COLD_COMPACTION_FAILS")

    with pytest.raises(RuntimeError, match="requires successful Stage-7"):
        runner.build_result(tmp_path / "d", stage6, {**stage7, "strict_verdict": "no"})


class _FakeScenarios:
    SCENARIOS = (
        ("episode_specific_affect", lambda kind, root: {"same": 1}),
        ("betrayal_affect_mode_resolution", lambda kind, root: {"same": 2}),
        ("ambiguous_recall_inertness", lambda kind, root: {"same": 3}),
        ("restart_behavior_identity", lambda kind, root: {"same": 4}),
    )


class _fake_context:
    def __init__(self, kind):
        self.kind = kind
    def __enter__(self):
        return _FakeScenarios
    def __exit__(self, *args):
        return False


def test_real_engineering_lossless_integrity_and_cold_none(tmp_path):
    from continuity_benchmark_v1110.stage8_cold_history_variants import compact_factory
    system = compact_factory("ghost_compact_fast", tmp_path / "none", "n")
    try:
        original = system.cold_history
        system.cold_history = None
        assert runner._cold_records(system) == {}
        system.cold_history = original
    finally:
        system.close()
    row = runner._engineering("ghost_compact_fast", tmp_path / "eng")
    assert row["episodes"] == 120
    assert row["cold_history_records"] == 192
    assert all(runner._lossless_equivalence(tmp_path / "lossless").values())
    assert all(runner._integrity_probe(tmp_path / "integrity").values())
    scale = runner._scale_probe(tmp_path / "scale", agents=1)
    assert scale["expected_records"] == 192
    assert scale["stage7_json"]["records"] == 192
    assert all(row["records"] == 192 for row in scale["compact"].values())


def test_main_without_out_and_dunder_main(tmp_path, monkeypatch, capsys):
    import runpy, sys
    s6 = tmp_path / "s6.json"; s6.write_text("{}")
    s7 = tmp_path / "s7.json"; s7.write_text("{}")
    monkeypatch.setattr(runner, "build_result", lambda root, stage6, stage7: {"stage": "x"})
    assert runner.main(["--stage6-report", str(s6), "--stage7-report", str(s7)]) == 0
    assert '"stage": "x"' in capsys.readouterr().out

    # Cover the normal module entrypoint without running the expensive real build.
    module_name = "continuity_benchmark_v1110.run_stage8_cold_compaction"
    saved_module = sys.modules.pop(module_name)
    old = sys.argv[:]
    sys.argv = ["run_stage8_cold_compaction", "--stage6-report", str(s6), "--stage7-report", str(s7)]
    try:
        with pytest.raises(RuntimeError, match="requires successful Stage-7"):
            runpy.run_module(module_name, run_name="__main__")
    finally:
        sys.argv = old
        sys.modules[module_name] = saved_module
