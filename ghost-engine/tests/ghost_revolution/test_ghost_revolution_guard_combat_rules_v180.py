"""Behavior contracts for tactical GuardSystem combat rules."""

from __future__ import annotations

from copy import deepcopy

import pytest

from ghost.examples.ghost_revolution.demo import (
    GhostRevolutionRun,
)
from ghost.examples.ghost_revolution.guard import (
    GuardSystem,
)


def test_combat_intents_expose_strict_physical_tells():
    guards = GuardSystem()

    assert guards.combat_intents() == (
        "tight_defense",
        "open_line",
        "recovering",
        "committed_heavy",
        "wide_cut",
        "driving_lunge",
    )

    heavy = guards.combat_intent("committed_heavy")
    wide = guards.combat_intent("wide_cut")
    lunge = guards.combat_intent("driving_lunge")

    assert "hips begin to turn" in heavy["tell"]
    assert "flat of the weapon" in wide["tell"]
    assert "armor gap" in lunge["tell"]


def test_unread_feint_breaks_tight_defense():
    exchange = GuardSystem().resolve_tactical_exchange(
        rank="watchman",
        intent="tight_defense",
        player_move="feint_heavy",
        feint_read_roll=26,
        counter_roll=100,
    )

    assert exchange["result"] == "feint_lands"
    assert exchange["guard_damage"] == 3
    assert exchange["player_damage"] == 0
    assert exchange["correct_reads_delta"] == 1


def test_read_feint_can_land_light_counter():
    exchange = GuardSystem().resolve_tactical_exchange(
        rank="watchman",
        intent="tight_defense",
        player_move="feint_light",
        feint_read_roll=25,
        counter_roll=20,
    )

    assert exchange["result"] == "feint_read"
    assert exchange["guard_damage"] == 0
    assert exchange["player_damage"] == 2
    assert exchange["wrong_reads_delta"] == 1


def test_parry_can_open_one_free_attack():
    guards = GuardSystem()

    success = guards.resolve_tactical_exchange(
        rank="watchman",
        intent="committed_heavy",
        player_move="parry",
        technique_roll=75,
    )

    assert success["result"] == "parry_success"
    assert success["player_damage"] == 0
    assert success["free_attack"] is True

    follow_up = guards.resolve_tactical_exchange(
        rank="watchman",
        intent="committed_heavy",
        player_move="heavy",
        free_attack=True,
    )

    assert follow_up["result"] == "free_attack"
    assert follow_up["guard_damage"] == 3


def test_deflect_ripostes_and_dodge_is_required_for_lunge():
    guards = GuardSystem()

    deflect = guards.resolve_tactical_exchange(
        rank="watchman",
        intent="wide_cut",
        player_move="deflect",
        technique_roll=70,
    )

    assert deflect["result"] == "deflect_success"
    assert deflect["guard_damage"] == 1
    assert deflect["player_damage"] == 0

    dodge = guards.resolve_tactical_exchange(
        rank="crown_guard",
        intent="driving_lunge",
        player_move="dodge",
    )

    assert dodge["result"] == "dodge_success"
    assert dodge["player_damage"] == 0

    punished = guards.resolve_tactical_exchange(
        rank="crown_guard",
        intent="driving_lunge",
        player_move="heavy",
    )

    assert punished["result"] == "lunge_punish"
    assert punished["player_damage"] == 4


def test_tactical_exchange_rejects_unknown_moves_and_bad_rolls():
    guards = GuardSystem()

    with pytest.raises(
        ValueError,
        match="Choose heavy, light",
    ):
        guards.resolve_tactical_exchange(
            rank="watchman",
            intent="open_line",
            player_move="rush",
        )

    with pytest.raises(
        ValueError,
        match="feint_read_roll must be an integer",
    ):
        guards.resolve_tactical_exchange(
            rank="watchman",
            intent="tight_defense",
            player_move="feint_light",
            feint_read_roll=None,
            counter_roll=1,
        )


def test_tactical_exchange_returns_fresh_packets():
    guards = GuardSystem()

    first = guards.resolve_tactical_exchange(
        rank="watchman",
        intent="open_line",
        player_move="heavy",
    )
    first["message"] = "mutated"

    second = guards.resolve_tactical_exchange(
        rank="watchman",
        intent="open_line",
        player_move="heavy",
    )

    assert "open line" in second["message"]


@pytest.mark.parametrize(
    (
        "rank",
        "roll",
        "expected",
    ),
    [
        ("watchman", 1, "death"),
        ("watchman", 3, "escape"),
        ("watchman", 25, "detention"),
        ("crown_guard", 1, "death"),
        ("crown_guard", 6, "escape"),
        ("crown_guard", 18, "detention"),
    ],
)
def test_loss_outcomes_are_ranked_and_seeded(
    rank,
    roll,
    expected,
):
    outcome = GuardSystem().resolve_player_loss_outcome(
        rank=rank,
        roll=roll,
        trust=0.0,
        fear=2,
        witnesses=1,
        royal_alert=0,
        execution_memory=0,
    )

    assert outcome["outcome"] == expected


def test_social_context_changes_loss_aftermath_odds_openly():
    guards = GuardSystem()

    calm = guards.resolve_player_loss_outcome(
        rank="watchman",
        roll=100,
        trust=0.0,
        fear=2,
        witnesses=1,
        royal_alert=0,
        execution_memory=0,
    )

    pressured = guards.resolve_player_loss_outcome(
        rank="watchman",
        roll=100,
        trust=-0.40,
        fear=4,
        witnesses=1,
        royal_alert=4,
        execution_memory=3,
    )

    assert pressured["escape_chance"] < calm["escape_chance"]
    assert pressured["death_chance"] > calm["death_chance"]
    assert (
        pressured["detention_chance"]
        > calm["detention_chance"]
    )


def test_facade_rejects_invalid_combat_move_without_mutation():
    class ScriptedRNG:
        def choice(self, options):
            return "open_line"

    game = GhostRevolutionRun(seed=7)
    game.location = "millcross"
    game.rng = ScriptedRNG()

    assert game.fight_guard() is None

    before = deepcopy(game.guard_combat)

    assert game.resolve_guard_combat_move("rush") is None

    assert game.guard_combat == before
    assert "Choose heavy, light" in game.last_action_note
