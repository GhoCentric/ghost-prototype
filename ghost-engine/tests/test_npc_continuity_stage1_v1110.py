from __future__ import annotations

import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from continuity_benchmark_v1110 import contract_digest, scenario_manifest
from continuity_benchmark_v1110.contract import (
    ArchiveMismatchError,
    CapacityBackpressureError,
    contract_packet,
)
from continuity_benchmark_v1110.metrics import source_metrics, storage_probe
from continuity_benchmark_v1110.purpose_built import (
    BaselineCapacityError,
    BaselineIntegrityError,
    PurposeBuiltContinuity,
    SimpleEpisodeArchive,
)
from continuity_benchmark_v1110.run_stage1_baseline import _factory, build_report
from continuity_benchmark_v1110.scenario_runner import run_frozen_suite


def test_frozen_contract_shape_and_digest_are_stable():
    manifest = scenario_manifest()
    assert len(manifest) == 16
    assert sum(len(row["checks"]) for row in manifest) == 62
    assert sum(row["class"] == "competence" for row in manifest) == 8
    assert sum(row["class"] == "discriminator" for row in manifest) == 8
    assert contract_digest() == "73f5cc5573091cabfdae6372e074def395d5e573a5facb587b85c3c592342653"
    packet = contract_packet()
    assert packet["scenario_policy"]["automatic_forgetting_allowed"] is False
    assert packet["scenario_policy"]["silent_eviction_allowed"] is False
    manifest[0]["checks"] = ()
    assert len(scenario_manifest()[0]["checks"]) == 4


def test_purpose_built_baseline_clears_full_frozen_bar_and_is_deterministic(tmp_path):
    first = run_frozen_suite(_factory, tmp_path / "first", "baseline")
    second = run_frozen_suite(_factory, tmp_path / "second", "baseline")
    assert first["scenario_count"] == 16
    assert first["competence"] == {"passes": 32, "total": 32}
    assert first["discriminators"] == {"passes": 30, "total": 30}
    assert first["all_checks"] == {"passes": 62, "total": 62}
    assert first["deterministic_digest"] == second["deterministic_digest"]
    assert first["deterministic_digest"] == "60f51c928e03a01c444ef0ed99cd3c86e1259ff5e769a5b2a1116e048945b217"


def test_archive_integrity_capacity_identity_and_lookup_contracts(tmp_path):
    path = tmp_path / "episodes.sqlite"
    archive = SimpleEpisodeArchive(path, max_records=2)
    first = archive.add(
        agent="npc", dimension="betrayal", source="one", meaning_delta=0.4,
        emotion_profile={"anger": 0.5}, consequence=-0.2,
    )
    second = archive.add(
        agent="npc", dimension="betrayal", source="two", meaning_delta=0.4,
        emotion_profile={"fear": 0.5}, consequence=-0.2,
    )
    assert first["episode_id"] != second["episode_id"]
    assert archive.get(first["episode_id"]) == first
    assert archive.get("missing") is None
    assert archive.resolve_dimension("npc", "missing") == {
        "status": "missing", "candidate_count": 0, "record": None,
    }
    ambiguous = archive.resolve_dimension("npc", "betrayal")
    assert ambiguous["status"] == "ambiguous"
    assert ambiguous["candidate_count"] == 2
    assert archive.for_dimension("npc", "betrayal") == [first, second]
    single_archive = SimpleEpisodeArchive(tmp_path / "single.sqlite")
    single = single_archive.add(
        agent="npc", dimension="respect", source="single", meaning_delta=0.2,
        emotion_profile={"hope": 0.2}, consequence=0.1,
    )
    assert single_archive.resolve_dimension("npc", "respect") == {
        "status": "unique", "candidate_count": 1, "record": single,
    }
    single_archive.close()
    manifest = archive.manifest()
    archive.verify_manifest(copy.deepcopy(manifest))
    with pytest.raises(BaselineIntegrityError):
        archive.verify_manifest({**manifest, "record_count": 999})
    with pytest.raises(BaselineCapacityError):
        archive.add(
            agent="npc", dimension="respect", source="three", meaning_delta=0.1,
            emotion_profile={}, consequence=0.0,
        )
    assert isinstance(BaselineCapacityError(), CapacityBackpressureError)
    assert isinstance(BaselineIntegrityError(), ArchiveMismatchError)
    archive.close()

    con = sqlite3.connect(path)
    con.execute("UPDATE episodes SET record_hash='0' WHERE episode_id=?", (first["episode_id"],))
    con.commit(); con.close()
    archive = SimpleEpisodeArchive(path)
    with pytest.raises(BaselineIntegrityError):
        archive.get(first["episode_id"])
    archive.close()


def test_archive_schema_and_metadata_corruption_fail_closed(tmp_path):
    bad_schema = tmp_path / "bad_schema.sqlite"
    archive = SimpleEpisodeArchive(bad_schema)
    archive._con.execute("UPDATE metadata SET value='bad' WHERE key='schema'")
    archive._con.commit(); archive.close()
    with pytest.raises(BaselineIntegrityError):
        SimpleEpisodeArchive(bad_schema)

    missing_meta = tmp_path / "missing_meta.sqlite"
    archive = SimpleEpisodeArchive(missing_meta)
    archive._con.execute("DELETE FROM metadata WHERE key='schema'")
    archive._con.commit()
    with pytest.raises(BaselineIntegrityError):
        archive._meta("schema")
    archive.close()


def test_runtime_snapshot_validation_exact_recall_and_missing_episode(tmp_path):
    path = tmp_path / "runtime.sqlite"
    system = PurposeBuiltContinuity(path)
    row = system.event(
        "npc", source="one", dimension="betrayal", meaning_delta=0.8,
        relevance=0.8, emotion_profile={"anger": 0.7}, consequence=-0.5,
    )
    assert system.get_episode(row["episode_id"]) == row
    assert system.archive_manifest()["record_count"] == 1
    assert system.episodes_for_dimension("npc", "betrayal") == [row]
    before = system.observe("npc")
    system.tick("npc", 1)
    system.revise("npc", "betrayal", -0.1)
    assert system.observe("npc") != before
    snap = system.snapshot()
    system.close()

    restored = PurposeBuiltContinuity(path, snapshot=snap)
    assert restored.snapshot() == snap
    with pytest.raises(KeyError):
        restored.recall_episode("missing", 0.5)
    missing_before = restored.observe("npc")
    missing = restored.recall_dimension("npc", "respect", 0.5)
    assert missing["status"] == "missing"
    assert restored.observe("npc") == missing_before
    unique = restored.recall_dimension("npc", "betrayal", 0.5)
    assert unique["status"] == "unique"
    assert unique["recall"]["episode_id"] == row["episode_id"]
    restored.close()

    with pytest.raises(BaselineIntegrityError):
        PurposeBuiltContinuity(path, snapshot=[])
    with pytest.raises(BaselineIntegrityError):
        PurposeBuiltContinuity(path, snapshot={"schema": "bad", "agents": {}, "episode_archive": snap["episode_archive"]})


def test_event_rolls_hot_state_back_if_archive_write_raises(tmp_path, monkeypatch):
    system = PurposeBuiltContinuity(tmp_path / "rollback.sqlite")
    system.event(
        "npc", source="one", dimension="betrayal", meaning_delta=0.5,
        relevance=0.5, emotion_profile={}, consequence=-0.2,
    )
    before = system.observe("npc")

    def boom(**kwargs):
        raise RuntimeError("forced write failure")

    monkeypatch.setattr(system.archive, "add", boom)
    with pytest.raises(RuntimeError, match="forced write failure"):
        system.event(
            "npc", source="two", dimension="respect", meaning_delta=0.5,
            relevance=0.5, emotion_profile={}, consequence=0.2,
        )
    assert system.observe("npc") == before
    system.close()


def test_near_tie_trace_and_foreground_zero_vector(tmp_path):
    system = PurposeBuiltContinuity(tmp_path / "tie.sqlite")
    trace = system.near_tie_trace(10)
    assert trace == ["anger"] * 10
    state = system._agent("zero")
    state["activation"] = {"x": 0.0}
    system._resolve_foreground(state)
    assert state["foreground"] is None
    system.close()


def test_runner_rejects_contract_check_drift(tmp_path):
    class DriftSystem(PurposeBuiltContinuity):
        pass

    def factory(root: Path, label: str, *, max_records=None, snapshot=None):
        return DriftSystem(root / f"{label}.sqlite", max_records=max_records, snapshot=snapshot)

    import continuity_benchmark_v1110.scenario_runner as runner
    original = runner._SCENARIO_FUNCS["moving_on_without_erasure"]

    def drift(*args, **kwargs):
        value = original(*args, **kwargs)
        value["checks"] = {"wrong": True}
        return value

    runner._SCENARIO_FUNCS["moving_on_without_erasure"] = drift
    try:
        with pytest.raises(AssertionError, match="scenario check contract drifted"):
            run_frozen_suite(factory, tmp_path / "drift", "x")
    finally:
        runner._SCENARIO_FUNCS["moving_on_without_erasure"] = original



def test_frozen_baseline_evidence_matches_runtime_before_ghost_adapter(tmp_path):
    frozen_path = (
        Path(__file__).resolve().parents[1]
        / "continuity_benchmark_v1110"
        / "stage1_baseline_frozen.json"
    )
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    live = run_frozen_suite(_factory, tmp_path / "frozen-evidence", "baseline")
    assert frozen["generated_before_ghost_adapter"] is True
    assert frozen["contract_digest"] == contract_digest()
    assert frozen["baseline_result"] == live
    assert frozen["next_stage_rule"].startswith("Stage 2 may add a Ghost adapter only")


def test_build_report_and_engineering_probes(tmp_path):
    package_root = Path(__file__).resolve().parents[1] / "continuity_benchmark_v1110"
    report = build_report(tmp_path / "report", package_root)
    assert report["deterministic_rerun"] is True
    assert report["baseline_result"]["all_checks"] == {"passes": 62, "total": 62}
    assert report["engineering"]["storage_probe"]["episodes"] == 10_000
    assert report["engineering"]["storage_probe"]["dimension_index_used"] is True
    assert report["engineering"]["storage_probe"]["hot_snapshot_bytes"] < 10_000
    metrics = source_metrics(package_root / "purpose_built.py")
    assert metrics["functions"] > 0
    assert metrics["largest_function_lines"] > 0


def test_cli_writes_report(tmp_path):
    output = tmp_path / "report.json"
    proc = subprocess.run(
        [sys.executable, "-m", "continuity_benchmark_v1110.run_stage1_baseline", "--output", str(output)],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout
    assert str(output) in proc.stdout
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["baseline_result"]["competence"] == {"passes": 32, "total": 32}


def test_build_report_rejects_nondeterminism_and_incompetence(tmp_path, monkeypatch):
    import continuity_benchmark_v1110.run_stage1_baseline as mod

    good = {
        "deterministic_digest": "same",
        "competence": {"passes": 1, "total": 1},
        "all_checks": {"passes": 1, "total": 1},
    }
    calls = []

    def nondeterministic(*args, **kwargs):
        calls.append(1)
        value = copy.deepcopy(good)
        value["deterministic_digest"] = str(len(calls))
        return value

    monkeypatch.setattr(mod, "run_frozen_suite", nondeterministic)
    with pytest.raises(RuntimeError, match="nondeterministic"):
        mod.build_report(tmp_path / "nd", Path(mod.__file__).resolve().parent)

    calls.clear()

    def incompetent(*args, **kwargs):
        value = copy.deepcopy(good)
        value["competence"] = {"passes": 0, "total": 1}
        return value

    monkeypatch.setattr(mod, "run_frozen_suite", incompetent)
    with pytest.raises(RuntimeError, match="minimum-competence"):
        mod.build_report(tmp_path / "bad", Path(mod.__file__).resolve().parent)


def test_main_stdout_and_module_entrypoint(tmp_path, monkeypatch, capsys):
    import runpy
    import continuity_benchmark_v1110.run_stage1_baseline as mod

    fake = {
        "baseline_result": {"competence": {"passes": 1, "total": 1}},
        "deterministic_rerun": True,
    }
    monkeypatch.setattr(mod, "build_report", lambda *args, **kwargs: copy.deepcopy(fake))
    monkeypatch.setattr(sys, "argv", ["stage1"] )
    assert mod.main() == 0
    assert '"deterministic_rerun": true' in capsys.readouterr().out

    output = tmp_path / "entry.json"
    sys.modules.pop("continuity_benchmark_v1110.run_stage1_baseline", None)
    monkeypatch.setattr(sys, "argv", ["stage1", "--output", str(output)])
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("continuity_benchmark_v1110.run_stage1_baseline", run_name="__main__")
    assert exc.value.code == 0
    assert json.loads(output.read_text(encoding="utf-8"))["deterministic_rerun"] is True
