"""Behavior contracts for extracted GuardSystem guard-down policy."""

from __future__ import annotations

from copy import deepcopy

import pytest

from ghost.examples.ghost_revolution.demo import (
    GhostRevolutionRun,
)
from ghost.examples.ghost_revolution.guard import (
    GuardSystem,
)


@pytest.mark.parametrize(
    (
        "choice",
        "conduct",
        "trust",
        "fear",
        "witnesses",
        "expected_outcome",
        "gold_delta",
        "heat_delta",
        "alert_delta",
        "fear_delta",
        "ghost_event",
        "memory_response",
    ),
    [
        (
            "spare",
            1,
            0.12,
            2,
            3,
            "leave_support",
            6,
            1,
            1,
            -1,
            "help",
            None,
        ),
        (
            "loot",
            0,
            0.0,
            2,
            1,
            "leave_neutral",
            6,
            1,
            1,
            0,
            None,
            None,
        ),
        (
            "execute",
            2,
            0.35,
            1,
            3,
            "execution_accepted",
            0,
            2,
            2,
            -1,
            "help",
            None,
        ),
        (
            "execute",
            0,
            0.0,
            2,
            3,
            "execution_rejected",
            0,
            2,
            2,
            1,
            "insult",
            "rejected",
        ),
        (
            "execute",
            0,
            0.20,
            2,
            3,
            "execution_uncertain",
            0,
            2,
            2,
            1,
            None,
            "uncertain",
        ),
    ],
)
def test_guard_down_policy_is_deterministic(
    choice,
    conduct,
    trust,
    fear,
    witnesses,
    expected_outcome,
    gold_delta,
    heat_delta,
    alert_delta,
    fear_delta,
    ghost_event,
    memory_response,
):
    guards = GuardSystem()

    outcome = guards.resolve_guard_down_outcome(
        choice=choice,
        conduct=conduct,
        trust=trust,
        fear=fear,
        witnesses=witnesses,
    )

    assert outcome["outcome"] == expected_outcome
    assert outcome["gold_delta"] == gold_delta
    assert outcome["heat_delta"] == heat_delta
    assert outcome["royal_alert_delta"] == alert_delta
    assert outcome["fear_delta"] == fear_delta
    assert outcome["ghost_event"] == ghost_event
    assert (
        outcome["execution_memory_response"]
        == memory_response
    )


@pytest.mark.parametrize(
    "choice",
    (
        "mercy",
        "",
        "  ",
        None,
    ),
)
def test_guard_down_policy_rejects_unknown_choices(choice):
    guards = GuardSystem()

    with pytest.raises(
        ValueError,
        match=r"^Choose leave or execute\.$",
    ):
        guards.resolve_guard_down_outcome(
            choice=choice,
            conduct=0,
            trust=0.0,
            fear=2,
            witnesses=2,
        )


def test_guard_down_policy_returns_fresh_packets():
    guards = GuardSystem()

    first = guards.resolve_guard_down_outcome(
        choice="leave",
        conduct=1,
        trust=0.12,
        fear=2,
        witnesses=3,
    )

    first["outcome"] = "mutated"

    second = guards.resolve_guard_down_outcome(
        choice="leave",
        conduct=1,
        trust=0.12,
        fear=2,
        witnesses=3,
    )

    assert second["outcome"] == "leave_support"


def test_facade_rejects_invalid_choice_without_mutation():
    game = GhostRevolutionRun(seed=7)
    game.location = "millcross"

    guard = game.active_guard("millcross")
    assert guard is not None

    game.guard_combat = {
        "stage": "down",
        "town": "millcross",
        "guard_id": guard["id"],
        "guard_rank": guard["rank"],
        "guard_label": guard["label"],
        "conduct": 0,
        "witnesses": 1,
    }

    before_combat = deepcopy(game.guard_combat)
    before_town = deepcopy(game.towns["millcross"])
    before_memory = game._town_memory.snapshot()
    before_gold = game.gold
    before_heat = game.heat
    before_alert = game.royal_alert
    before_actions = game.actions
    before_defeated = game.guards_defeated
    before_weapons = deepcopy(game.weapon_stock)
    before_packet = deepcopy(game.last_packet)

    assert game.resolve_guard_down("mercy") is None

    assert game.guard_combat == before_combat
    assert game.towns["millcross"] == before_town
    assert game._town_memory.snapshot() == before_memory
    assert game.gold == before_gold
    assert game.heat == before_heat
    assert game.royal_alert == before_alert
    assert game.actions == before_actions
    assert game.guards_defeated == before_defeated
    assert game.weapon_stock == before_weapons
    assert game.last_packet == before_packet
    assert "Choose leave or execute." in game.last_action_note



def test_facade_applies_rejected_execution_policy_effects():
    game = GhostRevolutionRun(seed=7)
    game.location = "millcross"

    guard = game.active_guard("millcross")
    assert guard is not None

    fear_before = game.towns["millcross"]["fear"]
    heat_before = game.heat
    alert_before = game.royal_alert

    game.guard_combat = {
        "stage": "down",
        "town": "millcross",
        "guard_id": guard["id"],
        "guard_rank": guard["rank"],
        "guard_label": guard["label"],
        "conduct": 0,
        "witnesses": 3,
    }

    packet = game.resolve_guard_down("execute")

    assert packet is not None
    assert packet["action"]["type"] == "insult"
    assert game.guard_combat is None
    assert game.guard_count("millcross") == 1
    assert game.has_active_guard("millcross") is True

    assert game.towns["millcross"]["fear"] == min(
        5,
        fear_before + 1,
    )

    assert game.heat == heat_before + 2
    assert game.royal_alert == alert_before + 2
    assert game.town_execution_memory("millcross") == 3

    assert "people pull away from you in fear" in (
        game.last_action_note
    )

