"""Behavior contracts for Ghost Revolution guard rosters."""

from __future__ import annotations

from ghost.examples.ghost_revolution.demo import (
    GhostRevolutionRun,
)
from ghost.examples.ghost_revolution.guard import (
    GuardSystem,
)


class FixedRNG:
    def randint(self, low: int, high: int) -> int:
        assert low <= 1 <= high
        return 1


def test_guard_system_builds_fresh_ranked_guard_packets():
    guards = GuardSystem()

    first = guards.new_guard(
        guard_id="millcross-guard-1",
        rank="watchman",
    )
    first["label"] = "mutated"

    second = guards.new_guard(
        guard_id="millcross-guard-1",
        rank="watchman",
    )

    assert second == {
        "id": "millcross-guard-1",
        "rank": "watchman",
        "label": "Royal Watchman",
    }


def test_starting_rosters_are_explicit_and_counted():
    game = GhostRevolutionRun()

    assert game.guard_count("ashfield") == 0
    assert game.guard_count("millcross") == 2
    assert game.guard_count("crownmarket") == 3

    assert game.has_active_guard("ashfield") is False
    assert game.has_active_guard("millcross") is True

    assert game.active_guard_label("millcross") == (
        "Royal Watchman"
    )
    assert game.active_guard_label("crownmarket") == (
        "Crown Guard"
    )

    assert "guard" not in game.towns["millcross"]
    assert len(game.towns["millcross"]["guard_roster"]) == 2


def test_active_guard_view_does_not_mutate_roster_state():
    game = GhostRevolutionRun()

    first = game.active_guard("millcross")
    assert first is not None

    first["label"] = "changed"

    second = game.active_guard("millcross")

    assert second is not None
    assert second["label"] == "Royal Watchman"


def test_successful_defection_removes_only_one_guard():
    game = GhostRevolutionRun()
    game.location = "millcross"
    game.rng = FixedRNG()

    first = game.active_guard("millcross")
    assert first is not None

    packet = game.recruit_guard()

    assert packet is not None
    assert packet["action"]["type"] == "help"
    assert game.guard_count("millcross") == 1
    assert game.has_active_guard("millcross") is True
    assert game.followers == 1

    next_guard = game.active_guard("millcross")
    assert next_guard is not None
    assert next_guard["id"] != first["id"]


def test_guard_down_removes_only_the_fought_guard():
    game = GhostRevolutionRun()
    game.location = "millcross"

    first = game.active_guard("millcross")
    assert first is not None

    game.guard_combat = {
        "stage": "down",
        "town": "millcross",
        "guard_id": first["id"],
        "guard_rank": first["rank"],
        "guard_label": first["label"],
        "conduct": 0,
        "witnesses": 1,
    }

    packet = game.resolve_guard_down("leave")

    assert packet is None
    assert game.guard_combat is None
    assert game.guard_count("millcross") == 1
    assert game.has_active_guard("millcross") is True

    next_guard = game.active_guard("millcross")
    assert next_guard is not None
    assert next_guard["id"] != first["id"]


def test_fight_binds_one_named_guard_to_combat_state():
    class ChoiceRNG:
        def choice(self, options):
            assert "open_line" in options
            return "open_line"

    game = GhostRevolutionRun()
    game.location = "millcross"
    game.rng = ChoiceRNG()

    first = game.active_guard("millcross")
    assert first is not None

    assert game.fight_guard() is None

    status = game.guard_combat_status()
    assert status is not None

    assert status["guard_id"] == first["id"]
    assert status["guard_rank"] == "watchman"
    assert status["guard_label"] == "Royal Watchman"
    assert status["guards_remaining"] == 2
    assert status["player_health"] == 10
    assert status["guard_health"] == 10


def test_victory_note_names_the_bound_guard():
    class ScriptedRNG:
        def __init__(self, intents):
            self.intents = list(intents)

        def choice(self, options):
            intent = self.intents.pop(0)
            assert intent in options
            return intent

    game = GhostRevolutionRun()
    game.location = "millcross"
    game.rng = ScriptedRNG(
        (
            "open_line",
            "open_line",
            "open_line",
            "open_line",
        )
    )

    assert game.fight_guard() is None

    for _ in range(4):
        assert game.resolve_guard_combat_move("heavy") is None

    assert game.guard_combat is not None
    assert game.guard_combat["stage"] == "down"
    assert "royal watchman to the stones" in (
        game.last_action_note
    )
    assert "{combat.get(" not in game.last_action_note

