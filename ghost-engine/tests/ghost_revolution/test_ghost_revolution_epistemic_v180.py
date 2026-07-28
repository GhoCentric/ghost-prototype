from collections import deque
import json

from ghost.examples.ghost_revolution.config import (
    build_revolution_scenario,
    military_camp_for,
)
from ghost.examples.ghost_revolution.demo import (
    GhostRevolutionRun,
)
from ghost.examples.ghost_revolution.presentation import (
    scout_intel_menu,
)
from ghost.examples.ghost_revolution.social import (
    GhostRevolutionSocialBridge,
)


def test_successful_scout_routes_fact_observation_belief_report_v180():
    game = GhostRevolutionRun(seed=7)
    game.followers = 1
    game.food = 10

    assert game.set_combat_role("scouts", 1) is True

    result = game.end_day()
    summary = game.information_summary()

    assert len(result["day_report"]["scout_reports"]) == 1
    assert len(summary["entries"]) == 1

    entry = summary["entries"][0]

    assert entry["kind"] == "scout_report"
    assert entry["town"] == "ashfield"
    assert entry["player_belief"][
        "dominant_candidate"
    ] == "light_presence"

    fact = game.runtime.api.get_fact(entry["fact_id"])

    assert fact["attributes"]["garrison"] == 25
    assert fact["attributes"]["town"] == "ashfield"

    player_belief = game.runtime.api.get_belief(
        "player",
        entry["subject"],
    )

    assert player_belief["id"] == entry["player_belief_id"]
    assert player_belief["previous_belief_id"] is None

    report = next(
        record
        for record in game.runtime.api.epistemic.records()
        if record["id"] == entry["report_id"]
    )

    assert report["kind"] == "report"
    assert report["audience"] == ["player"]
    assert report["source_belief_id"] == entry[
        "scout_belief_id"
    ]

    json.dumps(summary, allow_nan=False, sort_keys=True)


def test_scout_bands_revisions_and_capture_remain_separate_v180():
    bridge = GhostRevolutionSocialBridge(
        build_revolution_scenario()
    )

    ashfield_first = bridge.record_scout_report(
        town_id="ashfield",
        camp=military_camp_for("ashfield"),
        intel_level=1,
        phase_number=1,
        phase_day=1,
    )

    ashfield_second = bridge.record_scout_report(
        town_id="ashfield",
        camp=military_camp_for("ashfield"),
        intel_level=2,
        phase_number=1,
        phase_day=2,
    )

    millcross = bridge.record_scout_report(
        town_id="millcross",
        camp=military_camp_for("millcross"),
        intel_level=1,
        phase_number=1,
        phase_day=2,
    )

    crownmarket = bridge.record_scout_report(
        town_id="crownmarket",
        camp=military_camp_for("crownmarket"),
        intel_level=1,
        phase_number=1,
        phase_day=2,
    )

    capture = bridge.record_scout_capture(
        town_id="crownmarket",
        risk=45,
        phase_number=1,
        phase_day=2,
    )

    assert ashfield_first["player_belief"][
        "dominant_candidate"
    ] == "light_presence"

    assert ashfield_second["player_belief"][
        "dominant_candidate"
    ] == "light_presence"

    assert millcross["player_belief"][
        "dominant_candidate"
    ] == "moderate_presence"

    assert crownmarket["player_belief"][
        "dominant_candidate"
    ] == "heavy_presence"

    player_belief = bridge.runtime.api.get_belief(
        "player",
        ashfield_second["subject"],
    )

    assert player_belief["id"] == ashfield_second[
        "player_belief_id"
    ]
    assert player_belief["previous_belief_id"] == (
        ashfield_first["player_belief_id"]
    )

    summary = bridge.information_summary()

    assert summary["latest_scout_beliefs"]["ashfield"][
        "dominant_candidate"
    ] == "light_presence"

    assert capture["kind"] == "scout_capture"
    assert "player_belief_id" not in capture
    assert len(summary["entries"]) == 5

    json.dumps(summary, allow_nan=False, sort_keys=True)


def test_crownmarket_capture_enters_game_information_ledger_v180():
    class FixedRNG:
        def randint(self, low, high):
            assert (low, high) == (1, 100)
            return 1

    game = GhostRevolutionRun(seed=7)
    game.followers = 1
    game.food = 10
    game.scout_intel["ashfield"] = 3
    game.scout_intel["millcross"] = 3
    game.rng = FixedRNG()

    assert game.set_combat_role("scouts", 1) is True

    result = game.end_day()
    entry = game.information_summary()["entries"][0]

    assert "Crownmarket scout captured" in (
        result["day_report"]["scout_reports"][0]
    )
    assert entry["kind"] == "scout_capture"
    assert entry["town"] == "crownmarket"
    assert game.scouts_captured == 1
    assert game.followers == 0


def test_scout_menu_labels_player_beliefs_as_report_based_v180(
    capsys,
):
    game = GhostRevolutionRun(seed=7)

    scout_intel_menu(game, deque())

    empty_output = capsys.readouterr().out

    assert "PLAYER BELIEFS (REPORT-BASED):" in empty_output
    assert "No scout report has been evaluated yet." in (
        empty_output
    )

    game._social.record_scout_report(
        town_id="ashfield",
        camp=military_camp_for("ashfield"),
        intel_level=1,
        phase_number=1,
        phase_day=1,
    )

    scout_intel_menu(game, deque())

    belief_output = capsys.readouterr().out

    assert "Ashfield: light presence" in belief_output
    assert "PLAYER BELIEFS (REPORT-BASED):" in belief_output

