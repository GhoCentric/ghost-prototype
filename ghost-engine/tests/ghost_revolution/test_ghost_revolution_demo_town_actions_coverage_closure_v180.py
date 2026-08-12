"""Coverage closure for Ghost Revolution town action methods."""

from __future__ import annotations

import pytest

from ghost.examples.ghost_revolution.demo import GhostRevolutionRun


def _packet(trust: float = 0.0) -> dict:
    return {
        "relationship": {"trust": trust},
        "action": {"type": "help"},
    }


def _stub_resolution(monkeypatch, game, trust: float = 0.0) -> None:
    monkeypatch.setattr(
        game,
        "_resolve",
        lambda action, target: _packet(trust),
    )
    monkeypatch.setattr(
        game,
        "_check_capture",
        lambda: None,
    )


def test_honest_work_reward_fallback_and_denials(monkeypatch):
    game = GhostRevolutionRun()
    game.location = "base"

    assert game.honest_work_reward() == (0, 0)

    game.phase = "camp"
    assert game.earn_honest_gold() is None
    assert "only available" in game.last_action_note

    game.phase = "rebellion"
    assert game.earn_honest_gold() is None
    assert "no town work" in game.last_action_note

    game.location = "ashfield"
    game.towns["ashfield"]["locked"] = True
    assert game.earn_honest_gold() is None
    assert "lockdown" in game.last_action_note

    game.towns["ashfield"]["locked"] = False
    game.daily_activity["ashfield"]["work"] = True
    assert game.earn_honest_gold() is None
    assert "already worked" in game.last_action_note

    game.daily_activity["ashfield"]["work"] = False
    game.actions = 0
    assert game.earn_honest_gold() is None
    assert "No actions remain" in game.last_action_note

    game.actions = 1
    monkeypatch.setattr(
        game,
        "town_trust",
        lambda town_id: -0.25,
    )
    assert game.earn_honest_gold() is None
    assert "trusts you" in game.last_action_note


def test_honest_work_high_trust_and_spend_failure(monkeypatch):
    game = GhostRevolutionRun()
    game.location = "millcross"
    _stub_resolution(monkeypatch, game, trust=0.55)

    monkeypatch.setattr(
        game,
        "town_trust",
        lambda town_id: 0.55,
    )

    gold_before = game.gold
    packet = game.earn_honest_gold()

    assert packet is not None
    assert game.gold == gold_before + 9
    assert "Market labor" in game.last_action_note

    blocked = GhostRevolutionRun()
    blocked.location = "ashfield"
    monkeypatch.setattr(
        blocked,
        "town_trust",
        lambda town_id: 0.0,
    )
    monkeypatch.setattr(
        blocked,
        "_spend_action",
        lambda amount=1: False,
    )

    assert blocked.earn_honest_gold() is None
    assert "No actions remain" in blocked.last_action_note


def test_recruit_quietly_denial_paths(monkeypatch):
    game = GhostRevolutionRun()

    game.phase = "camp"
    assert game.recruit_quietly() is None
    assert "only available" in game.last_action_note

    game.phase = "rebellion"
    game.location = "base"
    assert game.recruit_quietly() is None
    assert "no town" in game.last_action_note

    game.location = "ashfield"
    game.towns["ashfield"]["locked"] = True
    assert game.recruit_quietly() is None
    assert "lockdown" in game.last_action_note

    game.towns["ashfield"]["locked"] = False
    game.actions = 0
    assert game.recruit_quietly() is None
    assert "No actions remain" in game.last_action_note

    game.actions = 1
    game.towns["ashfield"]["recruited"] = (
        game.towns["ashfield"]["population"]
    )
    assert game.recruit_quietly() is None
    assert "no people left" in game.last_action_note


def test_recruit_quietly_knight_paths(monkeypatch):
    game = GhostRevolutionRun()
    game.location = "ashfield"
    game.knight_town = "ashfield"

    monkeypatch.setattr(
        game,
        "_spend_action",
        lambda amount=1: False,
    )

    assert game.recruit_quietly() is None
    assert "No actions remain" in game.last_action_note

    success = GhostRevolutionRun()
    success.location = "ashfield"
    success.knight_town = "ashfield"
    _stub_resolution(monkeypatch, success)

    packet = success.recruit_quietly()

    assert packet is not None
    assert success.heat == 1
    assert "knight's presence" in success.last_action_note


def test_recruit_quietly_regular_spend_failure(monkeypatch):
    game = GhostRevolutionRun()
    game.location = "ashfield"
    game.knight_town = "crownmarket"

    monkeypatch.setattr(
        game,
        "_spend_action",
        lambda amount=1: False,
    )

    assert game.recruit_quietly() is None
    assert "No actions remain" in game.last_action_note


@pytest.mark.parametrize(
    ("trust", "memory", "expected_gain", "note_piece"),
    (
        (0.60, 0, 3, "join the rebellion"),
        (0.30, 1, 1, "execution still makes"),
        (0.00, 1, 0, "No one is willing"),
    ),
)
def test_recruit_quietly_trust_and_memory_paths(
    monkeypatch,
    trust,
    memory,
    expected_gain,
    note_piece,
):
    game = GhostRevolutionRun()
    game.location = "ashfield"
    game.knight_town = "crownmarket"

    _stub_resolution(monkeypatch, game, trust=trust)
    monkeypatch.setattr(
        game,
        "town_execution_memory",
        lambda town_id: memory,
    )
    monkeypatch.setattr(
        game,
        "recruitment_available_today",
        lambda town_id: 5,
    )
    monkeypatch.setattr(
        game,
        "town_people_left",
        lambda town_id: 5,
    )

    followers_before = game.followers
    packet = game.recruit_quietly()

    assert packet is not None
    assert game.followers == followers_before + expected_gain
    assert note_piece in game.last_action_note


def test_public_speech_unavailable_spend_failure_and_knight(monkeypatch):
    game = GhostRevolutionRun()
    game.location = "ashfield"

    monkeypatch.setattr(
        game,
        "public_event_action_available",
        lambda action_name: False,
    )
    assert game.speak_publicly() is None

    blocked = GhostRevolutionRun()
    blocked.location = "ashfield"
    monkeypatch.setattr(
        blocked,
        "public_event_action_available",
        lambda action_name: True,
    )
    monkeypatch.setattr(
        blocked,
        "_spend_action",
        lambda amount=1: False,
    )
    assert blocked.speak_publicly() is None
    assert "No actions remain" in blocked.last_action_note

    knight = GhostRevolutionRun()
    knight.location = "ashfield"
    knight.knight_town = "ashfield"
    knight.public_event_state["ashfield"]["open"] = True
    monkeypatch.setattr(
        knight,
        "public_event_action_available",
        lambda action_name: True,
    )
    _stub_resolution(monkeypatch, knight)

    packet = knight.speak_publicly()

    assert packet is not None
    assert knight.towns["ashfield"]["fear"] == 2
    assert knight.heat == 2
    assert "turns your public speech" in knight.last_action_note


def test_public_rally_unavailable_spend_failure_and_knight(monkeypatch):
    game = GhostRevolutionRun()
    game.location = "ashfield"

    monkeypatch.setattr(
        game,
        "public_event_action_available",
        lambda action_name: False,
    )
    assert game.rally_people() is None

    blocked = GhostRevolutionRun()
    blocked.location = "ashfield"
    monkeypatch.setattr(
        blocked,
        "public_event_action_available",
        lambda action_name: True,
    )
    monkeypatch.setattr(
        blocked,
        "_spend_action",
        lambda amount=1: False,
    )
    assert blocked.rally_people() is None
    assert "No actions remain" in blocked.last_action_note

    knight = GhostRevolutionRun()
    knight.location = "ashfield"
    knight.knight_town = "ashfield"
    knight.public_event_state["ashfield"]["open"] = True
    monkeypatch.setattr(
        knight,
        "public_event_action_available",
        lambda action_name: True,
    )
    _stub_resolution(monkeypatch, knight)

    packet = knight.rally_people()

    assert packet is not None
    assert knight.towns["ashfield"]["fear"] == 2
    assert knight.heat == 2
    assert "Royal pressure" in knight.last_action_note


def test_recruit_openly_and_speech_alias_paths(monkeypatch):
    game = GhostRevolutionRun()
    game.location = "ashfield"

    monkeypatch.setattr(
        game,
        "public_event_action_available",
        lambda action_name: False,
    )
    assert game.recruit_openly() is None

    no_packet = GhostRevolutionRun()
    no_packet.location = "ashfield"
    monkeypatch.setattr(
        no_packet,
        "public_event_action_available",
        lambda action_name: True,
    )
    monkeypatch.setattr(
        no_packet,
        "recruit_quietly",
        lambda: None,
    )
    assert no_packet.recruit_openly() is None

    unchanged = GhostRevolutionRun()
    unchanged.location = "ashfield"
    monkeypatch.setattr(
        unchanged,
        "public_event_action_available",
        lambda action_name: True,
    )
    monkeypatch.setattr(
        unchanged,
        "recruit_quietly",
        lambda: _packet(),
    )
    monkeypatch.setattr(
        unchanged,
        "_mark_public_event_action",
        lambda action_name: None,
    )

    packet = unchanged.recruit_openly()

    assert packet is not None
    assert unchanged.heat == 0

    increased = GhostRevolutionRun()
    increased.location = "ashfield"
    monkeypatch.setattr(
        increased,
        "public_event_action_available",
        lambda action_name: True,
    )
    monkeypatch.setattr(
        increased,
        "recruit_quietly",
        lambda: (
            setattr(increased, "followers", 1)
            or _packet()
        ),
    )
    monkeypatch.setattr(
        increased,
        "_mark_public_event_action",
        lambda action_name: None,
    )

    packet = increased.recruit_openly()

    assert packet is not None
    assert increased.heat == 1
    assert "Open recruitment" in increased.last_action_note

    sentinel = {"ok": True}
    monkeypatch.setattr(
        increased,
        "speak_publicly",
        lambda: sentinel,
    )
    assert increased.give_speech() is sentinel


def test_bribe_network_all_gate_paths_and_success(monkeypatch):
    game = GhostRevolutionRun()

    game.phase = "camp"
    assert game.bribe_network() is None
    assert "only available" in game.last_action_note

    game.phase = "rebellion"
    game.location = "base"
    assert game.bribe_network() is None
    assert "no town network" in game.last_action_note

    game.location = "ashfield"
    game.towns["ashfield"]["locked"] = True
    assert game.bribe_network() is None
    assert "lockdown" in game.last_action_note

    game.towns["ashfield"]["locked"] = False
    game.gold = 7
    assert game.bribe_network() is None
    assert "need 8 gold" in game.last_action_note

    game.gold = 8
    monkeypatch.setattr(
        game,
        "_spend_action",
        lambda amount=1: False,
    )
    assert game.bribe_network() is None
    assert "No actions remain" in game.last_action_note

    success = GhostRevolutionRun()
    success.location = "ashfield"
    success.gold = 8
    success.heat = 2
    success.towns["ashfield"]["fear"] = 2
    _stub_resolution(monkeypatch, success)

    packet = success.bribe_network()

    assert packet is not None
    assert success.gold == 0
    assert success.heat == 1
    assert success.towns["ashfield"]["fear"] == 1
    assert "Coins change hands" in success.last_action_note
