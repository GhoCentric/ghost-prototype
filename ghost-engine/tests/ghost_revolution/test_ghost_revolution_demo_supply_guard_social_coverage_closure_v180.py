"""Coverage closure for Ghost Revolution supply and guard-social methods."""

from __future__ import annotations

import pytest

from ghost.examples.ghost_revolution.demo import GhostRevolutionRun


def _fixed_loot() -> dict:
    return {
        "composition": "food",
        "food": 3,
        "gold": 0,
        "weapons": [],
        "summary": "+3 food",
    }


def _prepare_supply_game(monkeypatch) -> GhostRevolutionRun:
    game = GhostRevolutionRun()
    game.location = "ashfield"
    game.knight_town = "crownmarket"
    monkeypatch.setattr(
        game,
        "_roll_royal_cache_loot",
        _fixed_loot,
    )
    monkeypatch.setattr(
        game,
        "_check_capture",
        lambda: None,
    )
    return game


def test_seize_royal_supplies_phase_location_and_action_denials(monkeypatch):
    game = GhostRevolutionRun()
    game.phase = "camp"

    assert game.seize_royal_supplies() is None
    assert "only available" in game.last_action_note

    game.phase = "rebellion"
    game.location = "base"

    assert game.seize_royal_supplies() is None
    assert "no royal supplies" in game.last_action_note

    game.location = "ashfield"
    monkeypatch.setattr(
        game,
        "_spend_action",
        lambda amount=1: False,
    )

    assert game.seize_royal_supplies() is None
    assert "No actions remain" in game.last_action_note


def test_seize_royal_supplies_supported_guard_branch(monkeypatch):
    game = _prepare_supply_game(monkeypatch)
    game.towns["ashfield"]["fear"] = 1

    monkeypatch.setattr(
        game,
        "has_active_guard",
        lambda town_id: True,
    )
    monkeypatch.setattr(
        game,
        "guard_passage_active",
        lambda town_id: False,
    )
    monkeypatch.setattr(
        game,
        "town_trust",
        lambda town_id: 0.35,
    )
    monkeypatch.setattr(
        game,
        "_resolve",
        lambda action, target: {"action": {"type": action}},
    )

    packet = game.seize_royal_supplies()

    assert packet == {"action": {"type": "help"}}
    assert "Local allies hide" in game.last_action_note


def test_seize_royal_supplies_fear_branch(monkeypatch):
    game = _prepare_supply_game(monkeypatch)
    game.towns["ashfield"]["fear"] = 3

    monkeypatch.setattr(
        game,
        "has_active_guard",
        lambda town_id: False,
    )
    monkeypatch.setattr(
        game,
        "town_trust",
        lambda town_id: 0.0,
    )

    assert game.seize_royal_supplies() is None
    assert game.heat == 2
    assert "too afraid to cheer" in game.last_action_note


@pytest.mark.parametrize(
    ("chance", "expected"),
    (
        (50, "could defect"),
        (30, "A bribe or stronger town support"),
    ),
)
def test_question_guard_middle_read_branches(
    monkeypatch,
    chance,
    expected,
):
    game = GhostRevolutionRun()
    game.location = "ashfield"
    game.knight_town = "crownmarket"

    monkeypatch.setattr(
        game,
        "has_active_guard",
        lambda town_id: True,
    )
    monkeypatch.setattr(
        game,
        "guard_defection_chance",
        lambda: chance,
    )

    assert game.question_guard() is None
    assert expected in game.last_action_note


def test_question_guard_denial_paths(monkeypatch):
    game = GhostRevolutionRun()
    game.phase = "camp"

    assert game.question_guard() is None
    assert "only available" in game.last_action_note

    game.phase = "rebellion"
    game.location = "base"

    assert game.question_guard() is None
    assert "no royal guard" in game.last_action_note

    game.location = "ashfield"
    monkeypatch.setattr(
        game,
        "has_active_guard",
        lambda town_id: False,
    )

    assert game.question_guard() is None
    assert "no active royal guard" in game.last_action_note

    monkeypatch.setattr(
        game,
        "has_active_guard",
        lambda town_id: True,
    )
    monkeypatch.setattr(
        game,
        "_spend_action",
        lambda amount=1: False,
    )

    assert game.question_guard() is None
    assert "No actions remain" in game.last_action_note


def test_bribe_guard_all_denial_paths(monkeypatch):
    game = GhostRevolutionRun()
    game.phase = "camp"

    assert game.bribe_guard() is None
    assert "only available" in game.last_action_note

    game.phase = "rebellion"
    game.location = "base"

    assert game.bribe_guard() is None
    assert "no royal guard" in game.last_action_note

    game.location = "ashfield"
    monkeypatch.setattr(
        game,
        "has_active_guard",
        lambda town_id: False,
    )

    assert game.bribe_guard() is None
    assert "no active royal guard" in game.last_action_note

    monkeypatch.setattr(
        game,
        "has_active_guard",
        lambda town_id: True,
    )
    game.knight_town = "ashfield"

    assert game.bribe_guard() is None
    assert "watches Crownmarket" in game.last_action_note
    assert "too closely" in game.last_action_note

    game.knight_town = "crownmarket"
    game.daily_activity["ashfield"]["guard_bribe"] = True

    assert game.bribe_guard() is None
    assert "already looking" in game.last_action_note

    game.daily_activity["ashfield"]["guard_bribe"] = False
    game.gold = 5

    assert game.bribe_guard() is None
    assert "need 6 gold" in game.last_action_note

    game.gold = 6
    monkeypatch.setattr(
        game,
        "_spend_action",
        lambda amount=1: False,
    )

    assert game.bribe_guard() is None
    assert "No actions remain" in game.last_action_note


def test_recruit_guard_all_preflight_denials(monkeypatch):
    game = GhostRevolutionRun()
    game.phase = "camp"

    assert game.recruit_guard() is None
    assert "only available" in game.last_action_note

    game.phase = "rebellion"
    game.location = "base"

    assert game.recruit_guard() is None
    assert "no royal guard" in game.last_action_note

    game.location = "ashfield"
    monkeypatch.setattr(
        game,
        "active_guard",
        lambda town_id: None,
    )

    assert game.recruit_guard() is None
    assert "no active royal guard" in game.last_action_note

    guard = {"id": "guard-1", "label": "Royal Guard"}
    monkeypatch.setattr(
        game,
        "active_guard",
        lambda town_id: guard,
    )
    game.knight_town = "ashfield"

    assert game.recruit_guard() is None
    assert "direct control" in game.last_action_note

    game.knight_town = "crownmarket"
    game.daily_activity["ashfield"]["guard_recruit"] = True

    assert game.recruit_guard() is None
    assert "already tested" in game.last_action_note

    game.daily_activity["ashfield"]["guard_recruit"] = False
    monkeypatch.setattr(
        game,
        "_spend_action",
        lambda amount=1: False,
    )

    assert game.recruit_guard() is None
    assert "No actions remain" in game.last_action_note
