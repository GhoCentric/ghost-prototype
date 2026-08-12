"""Coverage closure for Ghost Revolution shops, taverns, and camp actions."""

from __future__ import annotations

import pytest

from ghost.examples.ghost_revolution.demo import GhostRevolutionRun


def test_legacy_scout_commands_redirect_to_assignment_system():
    game = GhostRevolutionRun()

    assert game.scout_target("ashfield") is False
    assert "assigned scouts" in game.last_action_note

    assert game.scout() is False
    assert "Assign followers as scouts" in game.last_action_note


@pytest.mark.parametrize(
    ("case", "expected_note"),
    (
        ("phase", ""),
        ("location", ""),
        ("item", ""),
        ("locked", "lockdown"),
        ("gold", "enough gold"),
        ("actions", "No actions remain"),
    ),
)
def test_buy_food_preflight_and_resource_denials(case, expected_note):
    game = GhostRevolutionRun()
    game.location = "ashfield"
    game.gold = 100

    item = "bread"

    if case == "phase":
        game.phase = "camp"
    elif case == "location":
        game.location = "base"
    elif case == "item":
        item = "stone"
    elif case == "locked":
        game.towns["ashfield"]["locked"] = True
    elif case == "gold":
        game.gold = 0
    elif case == "actions":
        game.actions = 0
    else:
        raise AssertionError(case)

    assert game.buy_food(item) is False

    if expected_note:
        assert expected_note.lower() in game.last_action_note.lower()


def test_buy_food_success_spends_gold_action_and_adds_food():
    game = GhostRevolutionRun()
    game.location = "ashfield"
    game.gold = 100
    game.food = 0
    game.actions = 3

    assert game.buy_food("meat") is True
    assert game.gold == 86
    assert game.food == 3
    assert game.actions == 2


@pytest.mark.parametrize(
    ("case", "expected_note"),
    (
        ("phase", ""),
        ("location", ""),
        ("item", ""),
        ("gold", "enough gold"),
        ("actions", "No actions remain"),
    ),
)
def test_blacksmith_buy_preflight_denials(case, expected_note):
    game = GhostRevolutionRun()
    game.location = "ashfield"
    game.gold = 100

    item = "repair"

    if case == "phase":
        game.phase = "camp"
    elif case == "location":
        game.location = "base"
    elif case == "item":
        item = "helmet"
    elif case == "gold":
        game.gold = 0
    elif case == "actions":
        game.actions = 0
    else:
        raise AssertionError(case)

    assert game.blacksmith_buy(item) is False

    if expected_note:
        assert expected_note.lower() in game.last_action_note.lower()


def test_blacksmith_buy_repair_and_shield_paths():
    repair = GhostRevolutionRun()
    repair.location = "ashfield"
    repair.gold = 100
    repair.armor = 0

    assert repair.blacksmith_buy("repair") is True
    assert repair.gold == 94
    assert repair.armor == 1
    assert repair.armor_item == "repaired armor"

    shield = GhostRevolutionRun()
    shield.location = "ashfield"
    shield.gold = 100
    shield.armor = 0

    assert shield.blacksmith_buy("shield") is True
    assert shield.gold == 90
    assert shield.shield_stock["light"] == 1
    assert shield.armor == 1
    assert shield.armor_item == "light shield"


@pytest.mark.parametrize(
    "case",
    ("phase", "location", "item", "gold", "actions"),
)
def test_common_goods_preflight_denials(case):
    game = GhostRevolutionRun()
    game.location = "ashfield"
    game.gold = 100

    item = "seeds"

    if case == "phase":
        game.phase = "camp"
    elif case == "location":
        game.location = "base"
    elif case == "item":
        item = "rope"
    elif case == "gold":
        game.gold = 0
    elif case == "actions":
        game.actions = 0
    else:
        raise AssertionError(case)

    assert game.buy_common_goods(item) is False


def test_common_goods_seed_and_cooking_kit_success_paths():
    seeds = GhostRevolutionRun()
    seeds.location = "ashfield"
    seeds.gold = 100

    assert seeds.buy_common_goods("seeds") is True
    assert seeds.gold == 92
    assert seeds.seeds == 1

    kit = GhostRevolutionRun()
    kit.location = "ashfield"
    kit.gold = 100

    assert kit.buy_common_goods("cooking_kit") is True
    assert kit.gold == 90
    assert kit.cooking_kits == 1


def test_bar_rumor_covers_denials_cap_and_success(monkeypatch):
    phase = GhostRevolutionRun()
    phase.phase = "camp"
    assert phase.bar_rumor() is None
    assert "closed outside rebellion" in phase.last_action_note

    location = GhostRevolutionRun()
    location.location = "base"
    assert location.bar_rumor() is None
    assert "no bar" in location.last_action_note.lower()

    capped = GhostRevolutionRun()
    capped.location = "ashfield"
    monkeypatch.setattr(
        capped,
        "_daily_cap_available",
        lambda *_args: False,
    )
    assert capped.bar_rumor() is None

    exhausted = GhostRevolutionRun()
    exhausted.location = "ashfield"
    exhausted.actions = 0
    assert exhausted.bar_rumor() is None
    assert "No actions remain" in exhausted.last_action_note

    success = GhostRevolutionRun()
    success.location = "ashfield"
    success.heat = 2
    packet = {"resolved": True}
    monkeypatch.setattr(success, "_resolve", lambda *_args: packet)

    assert success.bar_rumor() is packet
    assert success.heat == 1
    assert success.daily_activity["ashfield"]["bar"] is True


def test_bar_recruitment_covers_location_cap_and_packet_paths(monkeypatch):
    location = GhostRevolutionRun()
    location.location = "base"
    assert location.bar_recruit_quietly() is None
    assert "no bar" in location.last_action_note.lower()

    capped = GhostRevolutionRun()
    capped.location = "ashfield"
    monkeypatch.setattr(
        capped,
        "_daily_cap_available",
        lambda *_args: False,
    )
    assert capped.bar_recruit_quietly() is None

    denied = GhostRevolutionRun()
    denied.location = "ashfield"
    monkeypatch.setattr(denied, "recruit_quietly", lambda: None)
    assert denied.bar_recruit_quietly() is None
    assert denied.daily_activity["ashfield"]["bar"] is False

    success = GhostRevolutionRun()
    success.location = "ashfield"
    packet = {"recruited": 1}
    monkeypatch.setattr(success, "recruit_quietly", lambda: packet)
    assert success.bar_recruit_quietly() is packet
    assert success.daily_activity["ashfield"]["bar"] is True


def test_bar_local_work_covers_location_cap_and_packet_paths(monkeypatch):
    location = GhostRevolutionRun()
    location.location = "base"
    assert location.bar_local_work() is None
    assert "no bar" in location.last_action_note.lower()

    capped = GhostRevolutionRun()
    capped.location = "ashfield"
    monkeypatch.setattr(
        capped,
        "_daily_cap_available",
        lambda *_args: False,
    )
    assert capped.bar_local_work() is None

    denied = GhostRevolutionRun()
    denied.location = "ashfield"
    monkeypatch.setattr(denied, "earn_honest_gold", lambda: None)
    assert denied.bar_local_work() is None
    assert denied.daily_activity["ashfield"]["bar"] is False

    success = GhostRevolutionRun()
    success.location = "ashfield"
    packet = {"earned": 4}
    monkeypatch.setattr(success, "earn_honest_gold", lambda: packet)
    assert success.bar_local_work() is packet
    assert success.daily_activity["ashfield"]["bar"] is True


def test_public_event_alias_delegates_to_public_speech(monkeypatch):
    game = GhostRevolutionRun()
    packet = {"public": True}
    monkeypatch.setattr(game, "speak_publicly", lambda: packet)

    assert game.public_event() is packet


def test_set_assignment_rejects_unknown_and_invalid_amounts():
    game = GhostRevolutionRun()
    game.phase = "camp"

    assert game.set_assignment("miners", 1) is False
    assert game.set_assignment("farmers", -1) is False
    assert game.set_assignment("farmers", True) is False


@pytest.mark.parametrize(
    "case",
    ("phase", "followers", "food", "actions"),
)
def test_train_rebels_preflight_denials(case):
    game = GhostRevolutionRun()
    game.phase = "camp"
    game.followers = 3
    game.food = 1
    game.actions = 1

    if case == "phase":
        game.phase = "rebellion"
    elif case == "followers":
        game.followers = 2
    elif case == "food":
        game.food = 0
    elif case == "actions":
        game.actions = 0
    else:
        raise AssertionError(case)

    assert game.train_rebels() is False


def test_castle_pressure_preflight_and_strength_paths(monkeypatch):
    phase = GhostRevolutionRun()
    phase.phase = "camp"
    assert phase.castle_pressure() is None

    location = GhostRevolutionRun()
    location.location = "ashfield"
    assert location.castle_pressure() is None

    exhausted = GhostRevolutionRun()
    exhausted.location = "castle"
    exhausted.actions = 0
    assert exhausted.castle_pressure() is None

    low = GhostRevolutionRun()
    low.location = "castle"
    low.followers = 10
    low.heat = 8
    low.king_control = 5
    packet = {"pressure": "low"}
    capture_calls = []
    monkeypatch.setattr(low, "_resolve", lambda *_args: packet)
    monkeypatch.setattr(low, "_check_capture", lambda: capture_calls.append(True))

    assert low.castle_pressure() is packet
    assert low.heat == 10
    assert low.followers == 10
    assert low.king_control == 5
    assert capture_calls == [True]

    high = GhostRevolutionRun()
    high.location = "castle"
    high.followers = 35
    high.king_control = 2
    packet = {"pressure": "high"}
    monkeypatch.setattr(high, "_resolve", lambda *_args: packet)
    monkeypatch.setattr(high, "_check_capture", lambda: None)

    assert high.castle_pressure() is packet
    assert high.followers == 38
    assert high.king_control == 1
