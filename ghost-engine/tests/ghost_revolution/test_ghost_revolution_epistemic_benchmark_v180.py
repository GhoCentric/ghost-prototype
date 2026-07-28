import inspect
import json
from pathlib import Path
import runpy

from ghost.examples.ghost_revolution.benchmarks.epistemic_decision_benchmark import (
    _outcome,
    naive_report_truth_policy,
    oracle_diagnostic_policy,
    provenance_initial_policy,
    provenance_revised_policy,
    run_false_scout_report_benchmark,
)


ROOT = Path(__file__).resolve().parents[2]

BENCHMARK = (
    ROOT
    / "ghost"
    / "examples"
    / "ghost_revolution"
    / "benchmarks"
    / "epistemic_decision_benchmark.py"
)


def test_provenance_benchmark_holds_world_and_report_constant_v180():
    result = run_false_scout_report_benchmark()

    assert all(result["checks"].values())

    naive = result["naive"]
    ghost = result["ghost_provenance"]
    oracle = result["oracle_diagnostic"]

    assert naive["initial_state"] == ghost["initial_state"]
    assert ghost["initial_state"] == oracle["initial_state"]

    initial = naive["initial_state"]

    assert initial["location"] == "millcross"
    assert initial["actions"] == 4
    assert initial["active_guards"] == 2
    assert initial["knight_town"] == "millcross"

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


def test_provenance_policy_revises_and_avoids_costly_action_v180():
    result = run_false_scout_report_benchmark()

    naive = result["naive"]
    ghost = result["ghost_provenance"]
    oracle = result["oracle_diagnostic"]

    assert naive["decision_path"] == [
        "seize_royal_supplies",
    ]
    assert ghost["decision_path"] == [
        "investigate_guard",
        "secure_work",
    ]
    assert oracle["decision_path"] == [
        "secure_work",
    ]

    assert naive["wrong_risk_action"] is True
    assert ghost["wrong_risk_action"] is False

    assert ghost["beliefs"]["initial"][
        "dominant_candidate"
    ] == "knight_absent"

    assert ghost["beliefs"]["revised"][
        "dominant_candidate"
    ] == "knight_present"

    assert ghost["beliefs"]["revised"][
        "previous_belief_id"
    ] is not None

    assert naive["outcome"]["heat_delta"] == 4
    assert naive["outcome"]["fear_delta"] == 2

    assert ghost["outcome"]["heat_delta"] == 1
    assert ghost["outcome"]["fear_delta"] == 0

    assert (
        naive["outcome"]["exposure_cost"]
        == 50
    )
    assert (
        ghost["outcome"]["exposure_cost"]
        == 10
    )

    assert result["comparison"] == {
        "naive_exposure_cost": 50,
        "ghost_exposure_cost": 10,
        "avoidable_exposure_cost": 40,
    }

    assert ghost["audit"][
        "snapshot_round_trip_matches"
    ] is True
    assert ghost["audit"][
        "restored_belief_matches"
    ] is True


def test_benchmark_policies_are_information_bounded_v180():
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
            oracle_diagnostic_policy
        ).parameters
    ) == ("objective",)

    assert naive_report_truth_policy(
        {
            "claim": {
                "knight_status": "present",
            },
        }
    ) == "secure_work"

    assert provenance_initial_policy(
        {
            "report_quality": {
                "direct_observation": 0.90,
                "deception_likely": 0.10,
            },
            "dimensions": {
                "royal_presence": {
                    "dominant_candidate": "knight_absent",
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

    captured = _outcome(
        {
            "actions": 3,
            "gold": 0,
            "food": 0,
            "weapon_stock_total": 0,
            "heat": 1,
            "town_fear": 1,
        },
        type(
            "CapturedGame",
            (),
            {
                "location": "millcross",
                "phase": "rebellion",
                "phase_number": 1,
                "phase_day": 1,
                "actions": 2,
                "followers": 0,
                "gold": 0,
                "food": 0,
                "weapon_stock_total": lambda self: 0,
                "heat": 2,
                "royal_alert": 0,
                "towns": {
                    "millcross": {
                        "fear": 1,
                    },
                },
                "guard_count": lambda self, town_id: 2,
                "knight_town": "millcross",
                "alive": False,
                "captured": True,
            },
        )(),
    )

    assert captured["exposure_cost"] == 110


def test_benchmark_is_deterministic_and_module_runnable_v180(
    capsys,
):
    left = run_false_scout_report_benchmark()
    right = run_false_scout_report_benchmark()

    assert left == right

    source = BENCHMARK.read_text(encoding="utf-8")

    assert ".runtime" not in source
    assert ".get_fact(" not in source
    assert "GhostRevolutionRun" in source
    assert "GhostAPI" in source

    runpy.run_path(
        str(BENCHMARK),
        run_name="__main__",
    )

    output = capsys.readouterr().out

    assert "PROVENANCE BENCHMARK v0" in output
    assert "Naive reports = truth" in output
    assert "Ghost provenance policy" in output
    assert "Avoidable exposure cost: 40" in output
    assert output.count("[PASS]") == 7

