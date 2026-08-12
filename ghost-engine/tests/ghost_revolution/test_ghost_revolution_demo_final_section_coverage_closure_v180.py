"""Coverage closure for the final demo.py section."""

from __future__ import annotations

import runpy
import warnings

import pytest

from ghost.examples.ghost_revolution.demo import (
    GhostRevolutionRun,
)


class _FixedRng:
    def __init__(self, value: int = 1):
        self.value = value

    def randint(self, _low: int, _high: int) -> int:
        return self.value

    def choice(self, values):
        return values[0]


def _feared_game() -> GhostRevolutionRun:
    game = GhostRevolutionRun(seed=191)
    game.heat = 10
    game.guards_defeated = 4
    game.king_fight = {
        "king_fate": "execute_king",
    }
    return game


def _trusted_game() -> GhostRevolutionRun:
    game = GhostRevolutionRun(seed=192)
    game.followers = 60
    game.food = 20
    game.heat = 0
    game.guards_defeated = 0
    game.king_fight = {
        "king_fate": "jail_king",
    }
    return game


def test_capture_and_camp_output_cover_active_paths_v180():
    captured = GhostRevolutionRun(seed=193)
    captured.heat = 8
    captured.rng = _FixedRng(1)

    captured._check_capture()

    assert captured.captured is True
    assert captured.alive is False
    assert "patrol net" in captured.ending

    escaped = GhostRevolutionRun(seed=194)
    escaped.heat = 8
    escaped.rng = _FixedRng(100)

    escaped._check_capture()

    assert escaped.captured is False
    assert escaped.alive is True

    camp = GhostRevolutionRun(seed=195)
    camp.assignments.update(
        {
            "farmers": 0,
            "foragers": 0,
            "trainers": 2,
            "smiths": 2,
            "scouts": 0,
        }
    )
    camp.food = 1
    swords_before = camp.weapon_stock["sword"]

    packet = camp._camp_output()

    assert packet["weapon_gain"] == 1
    assert camp.weapon_stock["sword"] == swords_before + 2
    assert camp.food == 0


def test_king_response_covers_reinforcement_lockdown_and_rebel_pressure_v180():
    game = GhostRevolutionRun(seed=196)

    for town in game.towns.values():
        town["guard_roster"] = []
        town["recruited"] = 0

    game.towns["ashfield"]["recruited"] = 5
    game.followers = 15
    game.rng = _FixedRng(1)

    events = game._king_response()

    assert game.knight_town == "ashfield"
    assert game.has_active_guard("ashfield") is True
    assert game.has_active_guard("millcross") is True
    assert game.has_active_guard("crownmarket") is True
    assert (
        game.active_guard("crownmarket")["rank"]
        == "crown_guard"
    )
    assert game.towns["ashfield"]["locked"] is True
    assert game.king_control == 9
    assert any("reinforces Crownmarket" in event for event in events)
    assert any("locks down Ashfield" in event for event in events)
    assert any("weaken royal control" in event for event in events)


def test_crown_normalization_and_all_location_rule_narratives_v180():
    game = GhostRevolutionRun(seed=197)

    with pytest.raises(ValueError, match="Choose a crown-loop town"):
        game._normalize_crown_town("")

    with pytest.raises(ValueError, match="Choose a crown-loop town"):
        game._normalize_crown_town(None)

    assert game._normalize_crown_town("ash") == "Ashfield"

    with pytest.raises(ValueError, match="Unknown crown-loop town"):
        game._normalize_crown_town("nowhere")

    with pytest.raises(ValueError, match="Choose a crown-loop location"):
        game._normalize_crown_location("")

    with pytest.raises(ValueError, match="Unknown crown-loop location"):
        game._normalize_crown_location("palace roof")

    uncertain_blacksmith = game.crown_visit_location(
        "Ashfield",
        "blacksmith",
    )
    uncertain_square = game.crown_visit_location(
        "Ashfield",
        "town_square",
    )

    feared = _feared_game()
    feared_goods = feared.crown_visit_location(
        "Millcross",
        "goods_stall",
    )
    feared_event = feared.crown_visit_location(
        "Millcross",
        "public_event",
    )
    feared_square = feared.crown_visit_location(
        "Millcross",
        "town_square",
    )

    trusted = _trusted_game()
    trusted_goods = trusted.crown_visit_location(
        "Crownmarket",
        "goods_stall",
    )
    trusted_event = trusted.crown_visit_location(
        "Crownmarket",
        "public_event",
    )
    trusted_square = trusted.crown_visit_location(
        "Crownmarket",
        "town_square",
    )

    assert uncertain_blacksmith["crown_profile"]["rule"] == "uncertain"
    assert len(uncertain_square["npcs"]) == 3
    assert feared_goods["crown_profile"]["rule"] == "feared"
    assert feared_event["crown_profile"]["rule"] == "feared"
    assert feared_square["crown_profile"]["rule"] == "feared"
    assert trusted_goods["crown_profile"]["rule"] == "trusted"
    assert trusted_event["crown_profile"]["rule"] == "trusted"
    assert trusted_square["crown_profile"]["rule"] == "trusted"


def test_crown_npc_interaction_covers_validation_and_greet_rules_v180():
    game = GhostRevolutionRun(seed=198)

    with pytest.raises(
        ValueError,
        match="Unknown crown-loop NPC action",
    ):
        game.crown_npc_interaction(
            "Ashfield",
            "blacksmith",
            "blacksmith",
            "attack",
        )

    with pytest.raises(
        ValueError,
        match="Unknown crown-loop NPC",
    ):
        game.crown_npc_interaction(
            "Ashfield",
            "public_event",
            "missing_npc",
            "greet",
        )

    feared = _feared_game()
    feared_packet = feared.crown_npc_interaction(
        "Millcross",
        "goods_stall",
        "stall_keeper",
        "greet",
    )

    trusted = _trusted_game()
    trusted_packet = trusted.crown_npc_interaction(
        "Crownmarket",
        "goods_stall",
        "stall_keeper",
        "greet",
    )

    assert "dangerous crown" in feared_packet["narrative"]
    assert "may be different" in trusted_packet["narrative"]


def test_demo_main_and_module_entry_delegate_to_presentation_v180(
    monkeypatch,
):
    from ghost.examples.ghost_revolution import demo
    from ghost.examples.ghost_revolution import opponent_ai
    from ghost.examples.ghost_revolution import presentation

    calls = []

    monkeypatch.setattr(
        presentation,
        "run_presentation",
        lambda: calls.append("run"),
    )

    demo.main()

    monkeypatch.setattr(
        opponent_ai,
        "install_layered_feint",
        lambda _run_type: None,
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        runpy.run_module(
            "ghost.examples.ghost_revolution.demo",
            run_name="__main__",
        )

    assert calls == ["run", "run"]
