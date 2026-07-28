import inspect
import json
from pathlib import Path
import runpy

from ghost.examples.ghost_revolution.benchmarks.epistemic_fair_fork_benchmark import (
    ACTION_BUDGET,
    naive_report_truth_policy,
    oracle_budget_matched_policy,
    provenance_initial_policy,
    provenance_revised_policy,
    run_fair_fork_benchmark,
)


ROOT = Path(__file__).resolve().parents[2]

BENCHMARK = (
    ROOT
    / "ghost"
    / "examples"
    / "ghost_revolution"
    / "benchmarks"
    / "epistemic_fair_fork_benchmark.py"
)


def test_fair_fork_benchmark_restores_one_exact_snapshot_v180():
    result = run_fair_fork_benchmark()

    assert all(result["checks"].values())
    assert result["action_budget"] == ACTION_BUDGET == 2
    assert result["fork"]["state_actions"] == 2
    assert len(result["fork"]["snapshot_sha256"]) == 64

    branches = [
        result["naive"],
        result["ghost_provenance"],
        result["oracle_diagnostic"],
    ]

    assert all(
        branch["restored_exactly"] is True
        for branch in branches
    )
    assert {
        branch["fork_snapshot_sha256"]
        for branch in branches
    } == {
        result["fork"]["snapshot_sha256"],
    }
    assert (
        branches[0]["initial_state"]
        == branches[1]["initial_state"]
        == branches[2]["initial_state"]
    )

    assert result["shared_scout_report"]["claim"] == {
        "statement": (
            "The knight has left Millcross. "
            "The royal cache is exposed."
        ),
        "town": "millcross",
        "knight_status": "absent",
        "recommended_action": "seize_royal_supplies",
    }

    json.dumps(result, allow_nan=False, sort_keys=True)


def test_fair_fork_holds_action_budget_and_exposes_raw_tradeoff_v180():
    result = run_fair_fork_benchmark()

    naive = result["naive"]
    ghost = result["ghost_provenance"]
    oracle = result["oracle_diagnostic"]

    assert naive["decision_path"] == [
        "seize_royal_supplies",
        "secure_work",
    ]
    assert ghost["decision_path"] == [
        "investigate_guard",
        "secure_work",
    ]
    assert oracle["decision_path"] == [
        "secure_work",
        "investigate_guard",
    ]

    for branch in (naive, ghost, oracle):
        assert branch["outcome"]["actions_spent"] == 2
        assert branch["outcome"]["actions_remaining"] == 0
        assert branch["outcome"]["captured"] is False
        assert branch["outcome"]["alive"] is True

    assert naive["outcome"]["gold_delta"] == 4
    assert ghost["outcome"]["gold_delta"] == 4
    assert oracle["outcome"]["gold_delta"] == 4

    assert naive["outcome"]["weapon_delta"] == 1
    assert ghost["outcome"]["weapon_delta"] == 0
    assert oracle["outcome"]["weapon_delta"] == 0

    assert naive["outcome"]["heat_delta"] == 5
    assert naive["outcome"]["fear_delta"] == 2
    assert ghost["outcome"]["heat_delta"] == 1
    assert ghost["outcome"]["fear_delta"] == 0
    assert oracle["outcome"]["heat_delta"] == 1
    assert oracle["outcome"]["fear_delta"] == 0

    assert result["raw_differences"] == {
        "naive_minus_ghost": {
            "actions_spent": 0,
            "gold_delta": 0,
            "food_delta": 0,
            "weapon_delta": 1,
            "heat_delta": 4,
            "fear_delta": 2,
            "royal_alert_delta": 0,
            "trust_delta": 0.0,
        },
        "ghost_minus_oracle": {
            "actions_spent": 0,
            "gold_delta": 0,
            "food_delta": 0,
            "weapon_delta": 0,
            "heat_delta": 0,
            "fear_delta": 0,
            "royal_alert_delta": 0,
            "trust_delta": 0.0,
        },
    }


def test_fair_fork_policy_access_and_belief_revision_v180():
    assert tuple(
        inspect.signature(
            naive_report_truth_policy
        ).parameters
    ) == ("report",)

    assert tuple(
        inspect.signature(
            provenance_initial_policy
        ).parameters
    ) == ("belief",)

    assert tuple(
        inspect.signature(
            provenance_revised_policy
        ).parameters
    ) == ("belief",)

    assert tuple(
        inspect.signature(
            oracle_budget_matched_policy
        ).parameters
    ) == ("objective",)

    assert naive_report_truth_policy(
        {
            "claim": {
                "knight_status": "present",
            },
        }
    ) == (
        "secure_work",
        "investigate_guard",
    )

    assert provenance_initial_policy(
        {
            "report_quality": {
                "direct_observation": 0.90,
                "deception_likely": 0.10,
            },
            "dimensions": {
                "royal_presence": {
                    "dominant_candidate": "knight_absent",
                    "confidence": 0.90,
                },
            },
        }
    ) == "seize_royal_supplies"

    assert provenance_revised_policy(
        {
            "dimensions": {
                "royal_presence": {
                    "dominant_candidate": "unknown",
                    "confidence": 0.90,
                },
            },
        }
    ) == "secure_work"

    result = run_fair_fork_benchmark()
    beliefs = result["ghost_provenance"]["beliefs"]

    assert beliefs["initial"][
        "dominant_candidate"
    ] == "knight_absent"
    assert beliefs["revised"][
        "dominant_candidate"
    ] == "knight_present"
    assert beliefs["revised"][
        "previous_belief_id"
    ] is not None

    audit = result["ghost_provenance"]["audit"]

    assert audit["snapshot_round_trip_matches"] is True
    assert audit["restored_belief_matches"] is True


def test_fair_fork_benchmark_is_deterministic_and_runnable_v180(
    capsys,
):
    left = run_fair_fork_benchmark()
    right = run_fair_fork_benchmark()

    assert left == right

    source = BENCHMARK.read_text(encoding="utf-8")

    assert ".runtime" not in source
    assert ".get_fact(" not in source
    assert "GhostRevolutionRun.from_snapshot" in source
    assert ".snapshot()" in source
    assert "input(" not in source

    runpy.run_path(
        str(BENCHMARK),
        run_name="__main__",
    )

    output = capsys.readouterr().out

    assert "FAIR-FORK BENCHMARK v1" in output
    assert "Action budget per branch: 2" in output
    assert "RAW TRADEOFF: NAIVE MINUS GHOST" in output
    assert "heat +4, fear +2, actions +0" in output
    assert "Exposure cost" not in output
    assert output.count("[PASS]") == 8

