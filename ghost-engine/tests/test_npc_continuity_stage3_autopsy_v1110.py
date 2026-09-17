from copy import deepcopy
import json
from pathlib import Path

import pytest

from continuity_benchmark_v1110.run_stage3_failure_autopsy import (
    STAGE2_EXPECTED_FAILED,
    _contains_equal_subtree,
    _contract_state_diff,
    _paths_for_key,
    build_autopsy,
    validate_stage2_report,
    write_autopsy,
)


def _stage2_report() -> dict:
    return {
        "stage": "npc_continuity_stage2_frozen_head_to_head",
        "baseline_result": {"all_checks": {"passes": 62, "total": 62}},
        "ghost_result": {"all_checks": {"passes": 58, "total": 62}},
        "raw_comparison": {"failed_checks": deepcopy(STAGE2_EXPECTED_FAILED)},
        "ghost_deterministic_rerun": True,
        "stage1_baseline_replay_exact": True,
        "strict_stage2_verdict": "GHOST_DOES_NOT_MATCH_FROZEN_COMPETENT_BASELINE",
    }


def test_validation_rejects_any_stage2_drift():
    good = _stage2_report()
    validate_stage2_report(good)
    mutations = [
        ("stage", "wrong"),
        ("baseline_result", {"all_checks": {"passes": 61, "total": 62}}),
        ("ghost_result", {"all_checks": {"passes": 59, "total": 62}}),
        ("raw_comparison", {"failed_checks": {}}),
        ("ghost_deterministic_rerun", False),
        ("stage1_baseline_replay_exact", False),
        ("strict_stage2_verdict", "wrong"),
    ]
    for key, value in mutations:
        bad = deepcopy(good)
        bad[key] = value
        with pytest.raises(ValueError):
            validate_stage2_report(bad)


def test_helpers_cover_nested_dict_list_and_scalar_paths():
    before = {"a": 1, "b": {"x": 2}}
    after = {"a": 2, "b": {"x": 2}}
    assert _contract_state_diff(before, after) == ["a"]
    nested = {"outer": [{"source": "x"}, 3], "other": {"source": "y"}}
    assert _paths_for_key(nested, "source") == ["outer.0.source", "other.source"]
    assert _paths_for_key(4, "source") == []
    assert _contains_equal_subtree(nested, {"source": "x"})
    assert _contains_equal_subtree(nested, "y")
    assert not _contains_equal_subtree(nested, "missing")


def test_stage3_autopsy_reproduces_and_classifies_without_rescoring(tmp_path):
    result = build_autopsy(_stage2_report(), tmp_path / "work")
    assert result["raw_stage2_result_unchanged"]["ghost"] == {"passes": 58, "total": 62}
    assert result["raw_stage2_result_unchanged"]["rescored"] is False
    assert result["unique_production_defect_roots"] == 1
    assert result["raw_checks_affected_by_production_defect"] == 2
    assert result["raw_checks_affected_by_projection_mismatch"] == 2
    assert result["strict_conclusion"] == "ONE_GHOST_PRODUCTION_DEFECT_ROOT_CONFIRMED_TWO_FROZEN_PROJECTION_MISMATCHES_PRESERVED"

    two = result["autopsy"]["ambiguity_two"]
    fifty = result["autopsy"]["ambiguity_fifty"]
    for probe, count in ((two, 2), (fifty, 50)):
        assert probe["candidate_count"] == count
        assert probe["direct_lookup_status"] == "ambiguous"
        assert probe["direct_lookup_hot_state_unchanged"]
        assert probe["api_lookup_status"] == "ambiguous"
        assert probe["continuity_recall_call_count"] == 1
        assert "activation" in probe["changed_contract_state_fields"]
        assert probe["activation_after"] > probe["activation_before"]
        assert probe["meaning_unchanged"]
        assert probe["emotion_unchanged"]
        assert probe["trust_unchanged"]
        assert probe["episode_count_unchanged"]

    snap = result["autopsy"]["snapshot"]
    assert snap["raw_frozen_literal_passes"] is False
    assert snap["emotion_profile_key_absent"]
    assert snap["episode_id_absent"]
    assert snap["exact_episode_record_absent"]
    assert snap["continuity_packet_keys"] == ["episode_archive", "runtime"]
    assert snap["continuity_archive_is_manifest_only"]
    assert snap["all_source_paths_are_source_owned_history"]
    assert len(snap["source_paths"]) == 3

    stale = result["autopsy"]["stale_foreground"]
    assert stale["old_betrayal_is_not_foreground"]
    assert stale["old_betrayal_is_numerically_stale"]
    assert stale["recent_emotion_wins_cross_layer_competition"]
    assert stale["interpretation_respect_wins_when_recent_emotion_removed"]
    assert stale["frozen_stream"]["foreground"] == "emotion:hope"
    assert stale["control_without_recent_emotion"]["foreground"] == "respect"

    assert two["changed_contract_state_fields"] == ["activation"]
    assert fifty["changed_contract_state_fields"] == ["activation", "foreground"]

    classes = {row["classification"]: row for row in result["classifications"]}
    assert classes["genuine_production_semantic_defect"]["production_fix_justified"] is True
    assert classes["frozen_literal_projection_mismatch"]["production_fix_justified"] is False
    assert classes["cross_layer_foreground_projection_mismatch"]["production_fix_justified"] is False


def test_write_autopsy_roundtrip(tmp_path):
    source = tmp_path / "stage2.json"
    output = tmp_path / "stage3.json"
    source.write_text(json.dumps(_stage2_report()), encoding="utf-8")
    result = write_autopsy(source, output, tmp_path / "work")
    assert json.loads(output.read_text(encoding="utf-8")) == result


def test_build_autopsy_fails_closed_when_any_diagnosis_does_not_reproduce(tmp_path, monkeypatch):
    import continuity_benchmark_v1110.run_stage3_failure_autopsy as mod

    valid = (
        {"direct_lookup_status": "ambiguous", "direct_lookup_hot_state_unchanged": True, "api_lookup_status": "ambiguous", "continuity_recall_call_count": 1, "changed_contract_state_fields": ["activation"]},
        {"direct_lookup_status": "ambiguous", "direct_lookup_hot_state_unchanged": True, "api_lookup_status": "ambiguous", "continuity_recall_call_count": 1, "changed_contract_state_fields": ["activation"]},
        {"raw_frozen_literal_passes": False, "emotion_profile_key_absent": True, "episode_id_absent": True, "exact_episode_record_absent": True, "continuity_archive_is_manifest_only": True, "all_source_paths_are_source_owned_history": True},
        {"old_betrayal_is_not_foreground": True, "old_betrayal_is_numerically_stale": True, "recent_emotion_wins_cross_layer_competition": True, "interpretation_respect_wins_when_recent_emotion_removed": True},
    )

    def install(rows):
        monkeypatch.setattr(mod, "_ambiguity_probe", lambda root, *, count, tick_each: deepcopy(rows[0] if count == 2 else rows[1]))
        monkeypatch.setattr(mod, "_snapshot_probe", lambda root: deepcopy(rows[2]))
        monkeypatch.setattr(mod, "_stale_probe", lambda root: deepcopy(rows[3]))

    rows = [deepcopy(x) for x in valid]
    rows[0]["continuity_recall_call_count"] = 0
    install(rows)
    with pytest.raises(RuntimeError, match="ambiguous-recall"):
        build_autopsy(_stage2_report(), tmp_path / "a")

    rows = [deepcopy(x) for x in valid]
    rows[2]["episode_id_absent"] = False
    install(rows)
    with pytest.raises(RuntimeError, match="snapshot projection"):
        build_autopsy(_stage2_report(), tmp_path / "b")

    rows = [deepcopy(x) for x in valid]
    rows[3]["old_betrayal_is_not_foreground"] = False
    install(rows)
    with pytest.raises(RuntimeError, match="foreground projection"):
        build_autopsy(_stage2_report(), tmp_path / "c")
