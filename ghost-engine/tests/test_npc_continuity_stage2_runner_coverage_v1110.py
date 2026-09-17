"""Fast branch-complete unit coverage for the Stage-2 report harness."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

import continuity_benchmark_v1110.run_stage2_head_to_head as stage2


class _SnapshotFake:
    def __init__(self):
        self.closed = False

    def event(self, *args, **kwargs):
        return None

    def snapshot(self):
        return {
            "ghost": {
                "continuity": {
                    "runtime": {},
                    "episode_archive": {"record_count": 1},
                },
                "emotions": {
                    "agents": {"npc": {"history": [{"source": "not-an-episode"}]}}
                },
            }
        }

    def close(self):
        self.closed = True


class _AmbiguityFake:
    def __init__(self):
        self.closed = False
        self.observations = 0

    def event(self, *args, **kwargs):
        return None

    def observe(self, agent):
        self.observations += 1
        activation = 0.8 if self.observations == 1 else 0.9
        return {
            "meaning": {"betrayal": 0.8},
            "activation": {"betrayal": activation},
            "emotion": {"anger": 0.4},
            "trust": -0.4,
            "episode_count": 2,
        }

    def recall_dimension(self, *args):
        return {"status": "ambiguous", "candidate_count": 2}

    def close(self):
        self.closed = True


class _RawGhost:
    def continuity_state(self, agent):
        return {"current_leader": "emotion:hope"}


class _StaleFake:
    def __init__(self):
        self.closed = False
        self._ghost = _RawGhost()

    def event(self, *args, **kwargs):
        return None

    def tick(self, *args, **kwargs):
        return None

    def observe(self, agent):
        return {
            "foreground": "emotion:hope",
            "activation": {"betrayal": 1e-15, "respect": 0.002},
            "emotion": {"hope": 0.5},
        }

    def close(self):
        self.closed = True


def _ghost_result(*, competence=(30, 32), failed=True):
    scenarios = {
        "same_dimension_identity_and_ambiguity": {
            "checks": {
                "ambiguous_dimension_recall_does_not_mutate_hot_state": not failed,
            }
        },
        "large_ambiguity_safety": {
            "checks": {"ambiguous_recall_leaves_relevance_unchanged": not failed}
        },
        "snapshot_archive_pairing": {
            "checks": {"hot_snapshot_excludes_episode_payloads": not failed},
            "measures": {"snapshot_bytes": 7000},
        },
        "stale_dominance_resistance": {
            "checks": {"recent_concern_can_displace_old_concern": not failed}
        },
    }
    return {
        "all_checks": {"passes": 58 if failed else 62, "total": 62},
        "competence": {"passes": competence[0], "total": competence[1]},
        "scenarios": scenarios,
    }


def _frozen():
    return {
        "baseline_result": {
            "all_checks": {"passes": 62, "total": 62},
            "scenarios": {
                "snapshot_archive_pairing": {"measures": {"snapshot_bytes": 332}}
            },
        }
    }


def test_small_helpers_and_real_baseline_factory(tmp_path):
    file = tmp_path / "x"
    file.write_bytes(b"abc")
    assert stage2._sha256(file) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    system = stage2._baseline_factory(tmp_path, "baseline", max_records=2)
    try:
        assert system.archive.max_records == 2
    finally:
        system.close()
    assert stage2._failed_checks({"scenarios": {"ok": {"checks": {"a": True}}, "bad": {"checks": {"a": True, "b": False}}}}) == {"bad": ["b"]}


def test_diagnostic_helpers_with_fake_contract_systems(monkeypatch, tmp_path):
    made = []

    def factory(root, label):
        if label == "snapshot-diagnostic":
            obj = _SnapshotFake()
        elif label == "ambiguity-diagnostic":
            obj = _AmbiguityFake()
        else:
            obj = _StaleFake()
        made.append(obj)
        return obj

    monkeypatch.setattr(stage2, "ghost_factory", factory)
    snapshot = stage2._snapshot_diagnostic(tmp_path)
    assert snapshot == {
        "raw_frozen_literal_source_absent": False,
        "episode_emotion_profile_absent": True,
        "continuity_packet_keys": ["episode_archive", "runtime"],
        "continuity_archive_manifest_only": True,
        "non_episode_source_history_present": True,
    }
    ambiguity = stage2._ambiguity_diagnostic(tmp_path)
    assert ambiguity["changed_contract_state_fields"] == ["activation"]
    assert ambiguity["activation_before"] == 0.8
    assert ambiguity["activation_after"] == 0.9
    stale = stage2._stale_foreground_diagnostic(tmp_path)
    assert stale["production_current_leader"] == "emotion:hope"
    assert stale["old_interpretation_is_stale_relative_to_recent"] is True
    assert all(obj.closed for obj in made)


def test_diagnoses_covers_failure_and_no_failure_branches():
    diagnostics = {"ambiguity": {"x": 1}, "snapshot": {"x": 2}, "stale_foreground": {"x": 3}}
    rows = stage2._diagnoses(_ghost_result(failed=True), diagnostics)
    assert len(rows) == 4
    assert sum(row["classification"] == "production_semantic_mismatch" for row in rows) == 2
    assert all(row["raw_check_remains_failed"] is True for row in rows)
    assert stage2._diagnoses(_ghost_result(competence=(32, 32), failed=False), diagnostics) == []


def test_engineering_and_base_report_cover_both_verdict_branches(monkeypatch, tmp_path):
    monkeypatch.setattr(stage2, "source_metrics", lambda path: {"name": Path(path).name})
    frozen = _frozen()
    failed = _ghost_result(failed=True)
    engineering = stage2._engineering_packet(tmp_path, frozen, failed)
    assert engineering["frozen_snapshot_bytes"] == {"baseline": 332, "ghost_adapter": 7000}
    assert set(engineering["source"]) == {
        "purpose_built.py", "ghost_adapter.py", "ghost_continuity.py", "ghost_episode_store.py"
    }

    diagnostics = {"ambiguity": {}, "snapshot": {}, "stale_foreground": {}}
    monkeypatch.setattr(stage2, "_engineering_packet", lambda *args: {"ok": True})
    report = stage2._base_report(frozen, failed, diagnostics, tmp_path)
    assert report["strict_stage2_verdict"] == "GHOST_DOES_NOT_MATCH_FROZEN_COMPETENT_BASELINE"
    assert report["raw_comparison"]["ghost_minus_baseline_passes"] == -4
    passed = _ghost_result(competence=(32, 32), failed=False)
    report2 = stage2._base_report(frozen, passed, diagnostics, tmp_path)
    assert report2["strict_stage2_verdict"] == "GHOST_MATCHES_FROZEN_COMPETENCE_GATE"
    assert report2["raw_comparison"]["ghost_strict_competence_gate"] is True


def test_build_report_success_and_guard_failures(monkeypatch, tmp_path):
    package = tmp_path / "pkg"
    package.mkdir()
    frozen = _frozen()
    frozen_path = package / "stage1_baseline_frozen.json"
    frozen_path.write_text(json.dumps(frozen), encoding="utf-8")

    monkeypatch.setattr(stage2, "_sha256", lambda path: stage2.STAGE1_BASELINE_RESULT_SHA256)
    baseline = frozen["baseline_result"]
    ghost = _ghost_result(failed=True)
    calls = iter([baseline, ghost, ghost])
    monkeypatch.setattr(stage2, "run_frozen_suite", lambda *args, **kwargs: next(calls))
    monkeypatch.setattr(stage2, "_ambiguity_diagnostic", lambda root: {"a": 1})
    monkeypatch.setattr(stage2, "_snapshot_diagnostic", lambda root: {"s": 1})
    monkeypatch.setattr(stage2, "_stale_foreground_diagnostic", lambda root: {"f": 1})
    monkeypatch.setattr(stage2, "_base_report", lambda f, g, d, p: {"ok": f == frozen and g is ghost, "d": d})
    report = stage2.build_report(tmp_path / "work", package)
    assert report["ok"] is True
    assert set(report["d"]) == {"ambiguity", "snapshot", "stale_foreground"}

    monkeypatch.setattr(stage2, "_sha256", lambda path: "drift")
    with pytest.raises(RuntimeError, match="hash drifted"):
        stage2.build_report(tmp_path / "hash", package)

    monkeypatch.setattr(stage2, "_sha256", lambda path: stage2.STAGE1_BASELINE_RESULT_SHA256)
    monkeypatch.setattr(stage2, "run_frozen_suite", lambda *args, **kwargs: {"wrong": True})
    with pytest.raises(RuntimeError, match="baseline replay"):
        stage2.build_report(tmp_path / "baseline-mismatch", package)

    calls = iter([baseline, {"g": 1}, {"g": 2}])
    monkeypatch.setattr(stage2, "run_frozen_suite", lambda *args, **kwargs: next(calls))
    with pytest.raises(RuntimeError, match="nondeterministic"):
        stage2.build_report(tmp_path / "ghost-mismatch", package)


def test_main_stdout_and_output_file_branches(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(stage2, "build_report", lambda *args: {"ok": True})
    monkeypatch.setattr(sys, "argv", ["stage2"])
    assert stage2.main() == 0
    assert '"ok": true' in capsys.readouterr().out

    output = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", ["stage2", "--output", str(output)])
    assert stage2.main() == 0
    assert json.loads(output.read_text(encoding="utf-8")) == {"ok": True}
    assert str(output) in capsys.readouterr().out
