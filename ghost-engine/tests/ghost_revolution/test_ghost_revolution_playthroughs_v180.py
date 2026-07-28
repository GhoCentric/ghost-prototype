import json
from pathlib import Path
import runpy

from ghost.examples.ghost_revolution.scripted_playthroughs import (
    run_seven_day_survival_and_scout_playthrough,
)


ROOT = Path(__file__).resolve().parents[2]

RUNNER = (
    ROOT
    / "ghost"
    / "examples"
    / "ghost_revolution"
    / "scripted_playthroughs.py"
)


def test_seven_day_survival_and_scout_route_reaches_camp_v180():
    result = run_seven_day_survival_and_scout_playthrough()

    assert result["route"] == (
        "seven_day_survival_and_scout"
    )
    assert len(result["days"]) == 7

    assert all(
        day["starved"] is False
        for day in result["days"]
    )

    assert all(
        result["days"][0]["actions"].values()
    )
    assert all(
        result["days"][1]["actions"].values()
    )
    assert all(
        result["days"][3]["actions"].values()
    )
    assert all(
        result["days"][5]["actions"].values()
    )

    final = result["final"]

    assert final["alive"] is True
    assert final["captured"] is False
    assert final["ending"] == ""
    assert final["phase"] == "camp"
    assert final["phase_number"] == 1
    assert final["phase_day"] == 1
    assert final["location"] == "base"
    assert final["followers"] == 4
    assert final["food"] == 0
    assert final["roles"]["scouts"] == 0

    assert result["days"][6]["end_day"][
        "phase_change"
    ] == "camp"

    json.dumps(result, allow_nan=False, sort_keys=True)


def test_playthrough_gathers_report_based_scout_beliefs_v180():
    result = run_seven_day_survival_and_scout_playthrough()

    first_day_reports = result["days"][0][
        "scout_reports"
    ]

    assert len(first_day_reports) == 2
    assert "Ashfield report 1/3" in first_day_reports[0]
    assert "Millcross report 1/3" in first_day_reports[1]

    assert all(
        day["scout_reports"] == []
        for day in result["days"][1:]
    )

    information = result["information"]
    entries = information["entries"]
    beliefs = information["latest_scout_beliefs"]

    assert len(entries) == 2
    assert entries[0]["kind"] == "scout_report"
    assert entries[1]["kind"] == "scout_report"
    assert entries[0]["town"] == "ashfield"
    assert entries[1]["town"] == "millcross"

    assert beliefs["ashfield"][
        "dominant_candidate"
    ] == "light_presence"

    assert beliefs["millcross"][
        "dominant_candidate"
    ] == "moderate_presence"

    assert 0 < beliefs["ashfield"]["confidence"] < 1
    assert 0 < beliefs["millcross"]["confidence"] < 1

    assert result["final"]["scout_intel"] == {
        "ashfield": 1,
        "millcross": 1,
        "crownmarket": 0,
    }


def test_playthrough_is_deterministic_and_module_runnable_v180(
    capsys,
):
    left = run_seven_day_survival_and_scout_playthrough()
    right = run_seven_day_survival_and_scout_playthrough()

    assert left == right

    source = RUNNER.read_text(encoding="utf-8")

    assert "GhostRevolutionRun" in source
    assert ".runtime" not in source
    assert "input(" not in source

    runpy.run_path(
        str(RUNNER),
        run_name="__main__",
    )

    output = capsys.readouterr().out

    assert "SCRIPTED PLAYTHROUGH" in output
    assert "Ashfield: light presence" in output
    assert "Millcross: moderate presence" in output
    assert "survived rebellion phase -> camp" in output

