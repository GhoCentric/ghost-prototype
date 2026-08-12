"""Coverage closure for presentation primitives and base/raid panels."""

from __future__ import annotations

from collections import deque
from copy import deepcopy
from unittest.mock import PropertyMock, patch

import pytest

from ghost.examples.ghost_revolution.demo import GhostRevolutionRun
from ghost.examples.ghost_revolution import presentation as p


def _packet() -> dict:
    return {
        "relationship": {"trust": 0.25, "state": "warm"},
        "world_effects": {
            "state": {"global_pressure": 0.2, "status": "quiet"},
        },
        "propagation": {"propagated": ["a", "b"]},
        "commerce": {"service": {"sale_access": "open"}},
        "law": {"action": "none"},
    }


def test_cost_helpers_and_basic_formatting_cover_boundaries_v180():
    old = deepcopy(p._LLM_COST_LEDGER)
    try:
        for key in p._LLM_COST_LEDGER:
            p._LLM_COST_LEDGER[key] = 0.0

        assert p._record_llm_measured_cost("strategy", None) is None
        assert p._record_llm_measured_cost("strategy", {}) is None
        assert p._record_llm_measured_cost(
            "strategy", {"measured_cost": {"total_cost": "bad"}}
        ) is None
        assert p._record_llm_measured_cost(
            "unknown", {"measured_cost": {"total_cost": 1.0}}
        ) is None
        assert p._record_llm_measured_cost(
            " STRATEGY ", {"measured_cost": {"total_cost": 0.125}}
        ) == pytest.approx(0.125)
        assert p._llm_cost_total() == pytest.approx(0.125)

        unavailable = p._measured_cost_lines(None, "strategy")
        assert unavailable[0] == "Measured token cost: unavailable"

        estimated = p._measured_cost_lines(
            {"cost_estimate": {"total_cost_estimate": 0.5}},
            "strategy",
        )
        assert estimated[-1].endswith("0.5")

        measured = p._measured_cost_lines(
            {
                "measured_cost": {
                    "reasoning_effort": "medium",
                    "input_tokens": 10,
                    "cached_input_tokens": 2,
                    "output_tokens": 4,
                    "reasoning_tokens": 1,
                    "total_cost": 0.01,
                }
            },
            "narration",
        )
        assert measured[0] == "Role: narration"
        assert measured[-1].startswith("Run LLM total: $")

        assert p.line("-") == "-" * p.WIDTH
        assert p.panel_lines(["", "alpha\nbeta"]) == ["", "alpha", "beta"]
        assert p.meter(-5, 0, 4) == "░░░░"
        assert p.meter(99, 2, 4) == "████"
        assert p.stock_label({"sword": 0}) == "None"
        assert p.stock_label({"sword": 2, "axe": 0}) == "Sword 2"
        assert p.no_actions_message().startswith("No actions remain")

        game = GhostRevolutionRun(seed=701)
        assert p.town_status_label(game, "ashfield") == game.town_condition("ashfield")
        assert p.town_role_icon("ashfield") == "[FARM]"
        assert p.town_role_icon("millcross") == "[MARKET]"
        assert p.town_role_icon("crownmarket") == "[CROWN]"
        game.phase = "camp"
        assert "total" in p.action_summary(game)
    finally:
        p._LLM_COST_LEDGER.clear()
        p._LLM_COST_LEDGER.update(old)


def test_town_symbols_status_events_and_travel_cover_branches_v180(capsys):
    game = GhostRevolutionRun(seed=702)

    # Default marker.
    game.knight_town = None
    assert p.town_symbol(game, "ashfield")

    # Locked + one guard + knight + positive trust.
    game.towns["ashfield"]["locked"] = True
    with patch.object(game, "guard_count", return_value=1), patch.object(
        game, "town_trust", return_value=0.5
    ):
        game.knight_town = "ashfield"
        symbol = p.town_symbol(game, "ashfield")
    assert "[L]" in symbol and "[G]" in symbol and "[K]" in symbol and "[+]" in symbol

    # Multiple guards + negative trust.
    with patch.object(game, "guard_count", return_value=3), patch.object(
        game, "town_trust", return_value=-0.5
    ):
        game.knight_town = None
        symbol = p.town_symbol(game, "millcross")
    assert "[G3]" in symbol and "[!]" in symbol

    game.location = "base"
    base_status = p.render_status(game)
    assert "Location: Base" in base_status

    game.location = "ashfield"
    with patch.object(
        type(game),
        "active_raid",
        new_callable=PropertyMock,
        return_value={"town": "millcross", "force": 2},
    ):
        town_status = p.render_status(game)
    assert "Active Raid: millcross" in town_status
    assert "Ashfield:" in town_status

    events = deque(maxlen=6)
    p.print_recent_events(events)
    assert capsys.readouterr().out == ""
    p.add_event(events, "hello\nworld")
    assert events[0] == "hello world"
    p.print_recent_events(events)
    assert "RECENT EVENTS" in capsys.readouterr().out

    with patch.object(p, "sleep"):
        p.travel_animation("base", "ashfield", 0)
        p.travel_animation("base", "millcross", 2)
    out = capsys.readouterr().out
    assert "TRAVELING TO ASHFIELD" in out
    assert "[2/2]" in out


def test_siege_cards_packet_and_all_opening_bands_v180(capsys):
    game = GhostRevolutionRun(seed=703)

    game.followers = 5
    game.weapons = 4
    game.armor = 2
    game.king_control = 5
    game.guards_defeated = 0
    with patch.object(game, "town_trust", return_value=0.0):
        lines = p.siege_narration(game)
    assert "A handful of rebels gather beneath the castle walls." in lines

    game.followers = 20
    game.weapons = 1
    game.armor = 0
    game.king_control = 8
    game.guards_defeated = 3
    with patch.object(game, "town_trust", return_value=0.0):
        lines = p.siege_narration(game)
    assert "Dozens gather beneath the castle walls." in lines
    assert "Most rebels carry little more than courage." in lines
    assert "Few have armor when the arrows begin." in lines
    assert "The defenders stand confident behind royal banners." in lines
    assert "The castle has already felt the loss of its guards." in lines

    game.followers = 40
    game.weapons = 8
    game.armor = 4
    game.king_control = 2
    with patch.object(game, "town_trust", return_value=0.5):
        lines = p.siege_narration(game)
    assert "Weapons rise across the crowd like a forest of steel." in lines
    assert "Shields and armor give the front line a chance." in lines
    assert "The defenders look toward the gates with doubt." in lines
    assert "Voices inside the city answer your call." in lines

    with patch.object(p, "sleep"):
        p.siege_animation(game)
        p.king_response_card(["The king reacts."])
    p.camp_phase_card(game)
    p.print_legend()
    p.print_ghost_packet(None)
    p.print_ghost_packet(_packet())
    out = capsys.readouterr().out
    assert "THE SIEGE BEGINS" in out
    assert "KINGDOM RESPONSE" in out
    assert "CAMP PHASE" in out
    assert "PLAYER LEGEND" in out
    assert "GHOST CONSEQUENCE" in out


def test_hidden_base_menu_covers_every_dispatch_branch_v180(capsys):
    game = GhostRevolutionRun(seed=704)
    game.location = "base"
    events = deque(maxlen=6)

    branches = ["1", "3", "5", "x"]
    for first in branches:
        game.location = "base"
        with patch("builtins.input", side_effect=[first, "0"]), patch.object(
            p, "print_legend"
        ) as legend:
            p.hidden_base_menu(game, events)
        if first == "5":
            legend.assert_called_once()

    for first, attr in (("2", "follower_roles_menu"), ("4", "raid_town_menu"), ("6", "active_raid_panel")):
        game.location = "base"
        with patch("builtins.input", side_effect=[first, "0"]), patch.object(
            p, attr
        ) as called:
            p.hidden_base_menu(game, events)
        called.assert_called_once()

    game.location = "base"
    with patch("builtins.input", side_effect=["0"]):
        p.hidden_base_menu(game, events)

    game.location = "ashfield"
    p.hidden_base_menu(game, events)

    assert "Invalid base-menu choice." in events
    assert "CAMP ASSIGNMENTS" in capsys.readouterr().out


def test_follower_roles_menu_covers_invalid_valid_and_rejected_v180(capsys):
    game = GhostRevolutionRun(seed=705)
    game.location = "base"
    game.followers = 3
    events = deque(maxlen=6)

    with patch("builtins.input", side_effect=["x", "0"]):
        p.follower_roles_menu(game, events)

    with patch("builtins.input", side_effect=["1", "bad", "0"]):
        p.follower_roles_menu(game, events)

    with patch.object(game, "set_combat_role", return_value=True) as setter:
        game.last_action_note = "roles updated"
        with patch("builtins.input", side_effect=["1", "1", "0"]):
            p.follower_roles_menu(game, events)
        setter.assert_called_with("scouts", 1)

    with patch.object(game, "set_combat_role", return_value=False) as setter:
        game.last_action_note = "roles rejected"
        with patch("builtins.input", side_effect=["2", "9", "0"]):
            p.follower_roles_menu(game, events)
        setter.assert_called_with("warriors", 9)

    game.location = "ashfield"
    p.follower_roles_menu(game, events)

    out = capsys.readouterr().out
    assert "Unknown role option." in out
    assert "Enter a whole number." in out
    assert "roles updated" in out
    assert "roles rejected" in out


def test_active_raid_and_plan_panels_cover_none_active_ready_states_v180(capsys):
    game = GhostRevolutionRun(seed=706)

    with patch.object(game, "active_raid_summary", return_value=None):
        p.active_raid_panel(game)

    raid = {
        "town": "ashfield",
        "camp": "south",
        "force": 4,
        "weapon_issue": {"sword": 2, "axe": 1},
        "shield_issue": {"light": 1, "heavy": 1},
        "food_committed": 3,
        "intel_level": 2,
        "intel_bonus": 1,
        "odds": "good",
    }
    with patch.object(game, "active_raid_summary", return_value=raid):
        p.active_raid_panel(game)

    readiness = {
        "town": "ashfield",
        "condition": "open",
        "camp": "south",
        "knight": "absent",
        "warlord": "none",
        "garrison": 2,
        "warriors": 5,
        "recommended_warriors": 4,
        "food": 10,
        "food_required": 3,
        "issued_weapons": 5,
        "recommended_weapons": 4,
        "issued_shields": 2,
        "training_level": 1,
        "leader_weapon": "sword",
        "odds": "good",
        "ready": True,
    }
    with patch.object(game, "raid_readiness", return_value=readiness):
        p.raid_plan_panel(game, "ashfield")

    readiness["ready"] = False
    with patch.object(game, "raid_readiness", return_value=readiness):
        p.raid_plan_panel(game, "ashfield")

    out = capsys.readouterr().out
    assert "No rebel force is currently deployed." in out
    assert "Weapons deployed: 3" in out
    assert "READY FOR FUTURE RAID" in out
    assert "NOT READY FOR RAID" in out
