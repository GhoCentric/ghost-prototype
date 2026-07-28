"""Behavior contracts for GuardSystem."""

from __future__ import annotations

import pytest

from ghost.examples.ghost_revolution.demo import (
    GhostRevolutionRun,
)
from ghost.examples.ghost_revolution.guard import (
    GuardSystem,
)


@pytest.mark.parametrize(
    (
        "trust",
        "fear",
        "royal_alert",
        "execution_memory",
        "knight_occupied",
        "expected",
    ),
    [
        (0.0, 0, 0, 0, False, 44),
        (0.5, 2, 1, 1, False, 43),
        (1.0, 0, 0, 0, False, 75),
        (-0.8, 5, 5, 3, True, 5),
    ],
)
def test_defection_chance_is_bounded_and_deterministic(
    trust,
    fear,
    royal_alert,
    execution_memory,
    knight_occupied,
    expected,
):
    guards = GuardSystem()

    assert guards.defection_chance(
        trust=trust,
        fear=fear,
        royal_alert=royal_alert,
        execution_memory=execution_memory,
        knight_occupied=knight_occupied,
    ) == expected


def test_facade_uses_guard_system_with_town_memory():
    game = GhostRevolutionRun(seed=7)
    game.location = "millcross"
    game.towns["millcross"]["fear"] = 0
    game.royal_alert = 0

    game._record_town_execution_memory(
        "millcross",
        "uncertain",
    )

    expected = game._guards.defection_chance(
        trust=game.town_trust("millcross"),
        fear=game.towns["millcross"]["fear"],
        royal_alert=game.royal_alert,
        execution_memory=2,
        knight_occupied=False,
    )

    assert game.guard_defection_chance() == expected


def test_facade_returns_zero_outside_a_town():
    game = GhostRevolutionRun(seed=7)
    game.location = "base"

    assert game.guard_defection_chance() == 0
