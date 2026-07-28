import json
from pathlib import Path
import runpy

from ghost.examples.epistemic_api_smoke_demo import run_demo


ROOT = Path(__file__).resolve().parents[1]

DEMO = (
    ROOT
    / "ghost"
    / "examples"
    / "epistemic_api_smoke_demo.py"
)


def test_epistemic_api_smoke_demo_uses_public_api_only_v180(
    capsys,
):
    result = run_demo()

    output = capsys.readouterr().out

    assert result["checks"] == {
        "fact_did_not_create_player_belief": True,
        "report_did_not_force_player_belief": True,
        "ledger_revised_player_belief": True,
        "tick_did_not_rewrite_belief": True,
        "snapshot_round_trip_matches": True,
        "restored_belief_matches": True,
    }

    assert result["report"]["claim"]["statement"] == (
        "They took everything."
    )
    assert result["player_revised_belief"][
        "previous_belief_id"
    ] == result["player_initial_belief"]["id"]

    assert (
        result["player_revised_belief"]["dimensions"][
            "quantity"
        ]["dominant_candidate"]
        == "some_food_taken"
    )

    assert "=== GHOST EPISTEMIC API SMOKE DEMO ===" in output
    assert "[3] EXAGGERATED REPORT" in output
    assert "[5] NEW EVIDENCE REVISES BELIEF" in output
    assert "[PASS] snapshot_round_trip_matches" in output

    source = DEMO.read_text(encoding="utf-8")

    assert "from ghost import GhostAPI" in source
    assert "EpistemicRuntime" not in source
    assert ".epistemic" not in source

    json.dumps(result, allow_nan=False, sort_keys=True)


def test_epistemic_api_smoke_demo_module_entrypoint_v180(capsys):
    runpy.run_path(
        str(DEMO),
        run_name="__main__",
    )

    output = capsys.readouterr().out

    assert "Public API only:" in output
    assert "report is a claim, not fact or forced belief" in output
    assert output.count("[PASS]") == 6

