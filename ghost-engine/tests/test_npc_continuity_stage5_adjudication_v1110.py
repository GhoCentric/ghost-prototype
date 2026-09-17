from __future__ import annotations

from copy import deepcopy
import json

import pytest

import continuity_benchmark_v1110.run_stage5_projection_adjudication as module
from continuity_benchmark_v1110.run_stage5_projection_adjudication import (
    STAGE4_EXPECTED_FAILED,
    build_adjudication,
    validate_stage4_report,
    write_adjudication,
)


def _stage4_report() -> dict:
    return {
        "stage": "npc_continuity_stage4_ambiguity_correction_rerun",
        "pre_patch": {
            "baseline": {"passes": 62, "total": 62},
            "ghost": {"passes": 58, "total": 62},
        },
        "post_patch": {
            "baseline": {"passes": 62, "total": 62},
            "ghost": {"passes": 60, "total": 62},
            "competence": {"passes": 31, "total": 32},
            "discriminators": {"passes": 29, "total": 30},
        },
        "ghost_pass_delta": 2,
        "remaining_raw_failures": deepcopy(STAGE4_EXPECTED_FAILED),
        "ghost_deterministic_rerun": True,
        "stage1_baseline_replay_exact": True,
        "frozen_benchmark_modified": False,
        "strict_conclusion": (
            "CONFIRMED_AMBIGUOUS_RECALL_DEFECT_CORRECTED_GHOST_MOVES_58_TO_60_"
            "TWO_FROZEN_PROJECTION_MISMATCHES_REMAIN"
        ),
    }


def test_stage5_real_adjudication_preserves_score_and_resolves_semantics(tmp_path):
    result = build_adjudication(_stage4_report(), tmp_path)
    assert result["raw_frozen_score_unchanged"]["ghost"] == {"passes": 60, "total": 62}
    assert result["raw_frozen_score_unchanged"]["rescored"] is False
    assert result["new_production_correctness_defects_confirmed"] == 0
    assert result["ghost_production_modified"] is False
    assert result["frozen_benchmark_modified"] is False

    snapshot = result["snapshot_adjudication"]
    assert snapshot["all_semantic_checks_pass"] is True
    assert snapshot["raw_stage1_literal_still_fails"] is True
    assert snapshot["bounded_hot_provenance_overhead_is_real"] is True
    assert snapshot["ghost_80_to_160_snapshot_ratio"] <= 1.10
    assert snapshot["ghost_to_baseline_snapshot_bytes_at_160"] > 10.0
    assert max(snapshot["history_lengths_at_160"].values()) <= 64

    foreground = result["foreground_adjudication"]
    assert foreground["all_semantic_checks_pass"] is True
    assert foreground["raw_stage1_literal_still_fails"] is True
    assert foreground["old_plus_recent_hope"]["foreground"] == "emotion:hope"
    assert foreground["recent_hope_without_old_event"]["foreground"] == "emotion:hope"
    assert foreground["old_plus_recent_without_emotion"]["foreground"] == "respect"
    assert foreground["old_plus_recent_fear"]["foreground"] == "emotion:fear"
    assert result["strict_conclusion"] == (
        "NO_NEW_PRODUCTION_CORRECTNESS_DEFECT_CONFIRMED_TWO_RAW_FAILURES_REMAIN_"
        "FROZEN_BOUNDED_SNAPSHOT_OVERHEAD_FLAGGED"
    )


def test_stage4_report_validation_rejects_every_boundary():
    base = _stage4_report()
    bad_values = []
    bad = deepcopy(base); bad["stage"] = "wrong"; bad_values.append(bad)
    bad = deepcopy(base); bad["pre_patch"]["ghost"] = {"passes": 57, "total": 62}; bad_values.append(bad)
    bad = deepcopy(base); bad["post_patch"]["baseline"] = {"passes": 61, "total": 62}; bad_values.append(bad)
    bad = deepcopy(base); bad["post_patch"]["ghost"] = {"passes": 59, "total": 62}; bad_values.append(bad)
    bad = deepcopy(base); bad["post_patch"]["competence"] = {"passes": 30, "total": 32}; bad_values.append(bad)
    bad = deepcopy(base); bad["post_patch"]["discriminators"] = {"passes": 28, "total": 30}; bad_values.append(bad)
    for key, value in {
        "ghost_pass_delta": 1,
        "remaining_raw_failures": {},
        "ghost_deterministic_rerun": False,
        "stage1_baseline_replay_exact": False,
        "frozen_benchmark_modified": True,
        "strict_conclusion": "wrong",
    }.items():
        bad = deepcopy(base); bad[key] = value; bad_values.append(bad)
    for bad in bad_values:
        with pytest.raises(ValueError):
            validate_stage4_report(bad)


def test_write_adjudication_serializes_builder_result(monkeypatch, tmp_path):
    source = tmp_path / "stage4.json"
    output = tmp_path / "stage5.json"
    source.write_text(json.dumps(_stage4_report()), encoding="utf-8")
    expected = {"stage": "fake", "ok": True}
    monkeypatch.setattr(module, "build_adjudication", lambda report, root: expected)
    assert write_adjudication(source, output, tmp_path / "work") == expected
    assert json.loads(output.read_text(encoding="utf-8")) == expected


def test_adjudication_fails_closed_when_semantic_probes_fail(monkeypatch, tmp_path):
    monkeypatch.setattr(module, "_snapshot_probe", lambda root: {
        "all_semantic_checks_pass": False,
        "bounded_hot_provenance_overhead_is_real": True,
    })
    monkeypatch.setattr(module, "_foreground_probe", lambda root: {
        "all_semantic_checks_pass": False,
    })
    result = module.build_adjudication(_stage4_report(), tmp_path)
    assert result["new_production_correctness_defects_confirmed"] == 2
    assert result["strict_conclusion"] == (
        "ADJUDICATION_FOUND_POSSIBLE_PRODUCTION_DEFECT_DO_NOT_PATCH_UNTIL_REVIEWED"
    )
    assert all(row["production_correctness_patch_justified"] for row in result["classifications"])

def test_private_snapshot_helpers_cover_equality_and_cleanup(tmp_path):
    assert module._contains_equal_subtree({"a": [1, {"b": 2}]}, 2) is True

    class BrokenSystem:
        def __init__(self):
            self.closed = False
        def event(self, *args, **kwargs):
            raise RuntimeError("forced")
        def close(self):
            self.closed = True

    opened = []
    def factory(root, label):
        system = BrokenSystem()
        opened.append(system)
        return system

    with pytest.raises(RuntimeError, match="forced"):
        module._populate_snapshot_system(factory, tmp_path, "broken", 1)
    assert opened[0].closed is True
