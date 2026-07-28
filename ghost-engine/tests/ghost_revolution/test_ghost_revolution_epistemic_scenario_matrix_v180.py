import inspect
import json
from pathlib import Path
import runpy

import pytest

from ghost.examples.ghost_revolution.benchmarks.epistemic_scenario_matrix_benchmark import (
    ACTION_BUDGET,
    MATRIX_TOWNS,
    SCENARIOS,
    SEEDS,
    naive_report_truth_policy,
    oracle_budget_matched_policy,
    provenance_initial_policy,
    provenance_revised_policy,
    run_scenario_matrix_benchmark,
)


ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = ROOT / "ghost" / "examples" / "ghost_revolution" / "benchmarks" / "epistemic_scenario_matrix_benchmark.py"


def test_matrix_covers_guarded_towns_seeds_and_scenarios_v180():
    result = run_scenario_matrix_benchmark()
    assert all(result["checks"].values())
    assert result["action_budget"] == ACTION_BUDGET == 2
    assert result["towns"] == list(MATRIX_TOWNS)
    assert result["seeds"] == list(SEEDS)
    assert result["scenario_ids"] == [s["id"] for s in SCENARIOS]
    assert len(result["trials"]) == len(SCENARIOS) * len(MATRIX_TOWNS) * len(SEEDS) == 42
    assert {(t["scenario_id"], t["town"], t["seed"]) for t in result["trials"]} == {(s["id"], town, seed) for s in SCENARIOS for town in MATRIX_TOWNS for seed in SEEDS}
    json.dumps(result, allow_nan=False, sort_keys=True)


def test_every_matrix_trial_is_a_fair_exact_fork_v180():
    for trial in run_scenario_matrix_benchmark()["trials"]:
        assert all(trial["checks"].values())
        branches = [trial["naive"], trial["ghost_provenance"], trial["oracle_diagnostic"]]
        assert all(branch["restored_exactly"] is True for branch in branches)
        assert {branch["fork_snapshot_sha256"] for branch in branches} == {trial["fork_snapshot_sha256"]}
        assert branches[0]["initial_state"] == branches[1]["initial_state"] == branches[2]["initial_state"]
        assert all(branch["outcome"]["actions_spent"] == 2 and branch["outcome"]["actions_remaining"] == 0 for branch in branches)
        assert len(trial["shared_reports_sha256"]) == 64


def test_matrix_exposes_calibration_and_cost_not_a_hidden_score_v180():
    result, a = run_scenario_matrix_benchmark(), run_scenario_matrix_benchmark()["aggregate"]
    summaries = result["scenario_summaries"]
    assert a["trials"] == 42 and a["present_truth_trials"] == 30
    assert a["naive_unsafe_seizures"] == 24 and a["ghost_unsafe_seizures"] == 0
    assert a["ghost_explicit_patrol_revisions"] == 24
    assert a["high_provenance_absence_trials"] == 6 and a["ghost_acts_on_high_provenance_absence"] == 6
    assert a["high_provenance_presence_trials"] == 6 and a["ghost_avoids_on_high_provenance_presence"] == 6
    assert a["low_provenance_trials"] == 30 and a["ghost_investigates_low_provenance"] == 30
    assert a["truthful_low_provenance_deferrals"] == 6
    assert summaries["truthful_high_provenance_absence"]["ghost_first_actions"] == {"seize_royal_supplies": 6}
    assert summaries["truthful_high_provenance_presence"]["ghost_first_actions"] == {"secure_work": 6}
    assert summaries["truthful_low_provenance_absence"]["ghost_first_actions"] == {"investigate_guard": 6}
    naive, ghost = a["naive_raw_totals"], a["ghost_raw_totals"]
    assert naive["weapon_delta"] > ghost["weapon_delta"]
    assert naive["heat_delta"] > ghost["heat_delta"]
    assert naive["fear_delta"] > ghost["fear_delta"]
    assert naive["gold_delta"] >= ghost["gold_delta"]


def test_matrix_policies_are_information_bounded_v180():
    assert tuple(inspect.signature(naive_report_truth_policy).parameters) == ("reports",)
    assert tuple(inspect.signature(provenance_initial_policy).parameters) == ("belief",)
    assert tuple(inspect.signature(provenance_revised_policy).parameters) == ("belief",)
    assert tuple(inspect.signature(oracle_budget_matched_policy).parameters) == ("objective",)
    assert naive_report_truth_policy([
        {"speaker": "a", "confidence": .20, "claim": {"knight_status": "absent"}},
        {"speaker": "b", "confidence": .80, "claim": {"knight_status": "present"}},
    ]) == ("secure_work", "investigate_guard")
    assert provenance_initial_policy({"report_quality": {"direct_observation": .95, "deception_likely": .05, "rumor_repetition_likely": .05, "contradictory_sources": 0.0}, "dimensions": {"royal_presence": {"dominant_candidate": "knight_absent", "confidence": .90, "uncertainty": .10}}}) == "seize_royal_supplies"
    assert provenance_initial_policy({"report_quality": {"direct_observation": .95, "deception_likely": .05, "rumor_repetition_likely": .05, "contradictory_sources": .80}, "dimensions": {"royal_presence": {"dominant_candidate": "knight_absent", "confidence": .90, "uncertainty": .10}}}) == "investigate_guard"
    assert provenance_revised_policy({"report_quality": {"direct_observation": .90, "deception_likely": .10, "rumor_repetition_likely": .10, "contradictory_sources": 0.0}, "dimensions": {"royal_presence": {"dominant_candidate": "knight_present", "confidence": .90}}}) == "secure_work"


def test_matrix_rejects_unsupported_population_inputs_v180():
    with pytest.raises(ValueError, match="seeds"):
        run_scenario_matrix_benchmark(seeds=())
    with pytest.raises(ValueError, match="guarded matrix towns"):
        run_scenario_matrix_benchmark(towns=("ashfield",))


def test_matrix_is_deterministic_and_module_runnable_v180(capsys):
    assert run_scenario_matrix_benchmark() == run_scenario_matrix_benchmark()
    source = BENCHMARK.read_text(encoding="utf-8")
    assert ".runtime" not in source and ".get_fact(" not in source
    assert "GhostRevolutionRun.from_snapshot" in source
    assert "input(" not in source and "MATRIX_TOWNS" in source
    runpy.run_path(str(BENCHMARK), run_name="__main__")
    output = capsys.readouterr().out
    assert "SCENARIO MATRIX v2" in output and "Trials: 42" in output
    assert "naive 24 / 30, Ghost 0 / 30" in output
    assert "Truthful low-provenance opportunity deferrals: 6" in output
    assert output.count("[PASS]") == 10
