"""Coverage closure for Ghost Revolution guard-combat facade paths."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ghost.examples.ghost_revolution.demo import GhostRevolutionRun


class ScriptedRNG:
    def __init__(
        self,
        *,
        choices: tuple[str, ...] = (),
        rolls: tuple[int, ...] = (),
    ) -> None:
        self.choices = list(choices)
        self.rolls = list(rolls)

    def choice(self, options):
        if not self.choices:
            raise AssertionError("Scripted RNG ran out of choices.")

        value = self.choices.pop(0)
        assert value in options
        return value

    def randint(self, low: int, high: int) -> int:
        if not self.rolls:
            raise AssertionError("Scripted RNG ran out of rolls.")

        value = self.rolls.pop(0)
        assert low <= value <= high
        return value


def _combat(
    game: GhostRevolutionRun,
    **overrides,
) -> dict:
    guard = game.active_guard("millcross")
    assert guard is not None

    combat = {
        "stage": "combat",
        "town": "millcross",
        "guard_id": guard["id"],
        "guard_rank": guard["rank"],
        "guard_label": guard["label"],
        "player_health": 10,
        "player_max_health": 10,
        "guard_health": 10,
        "guard_max_health": 10,
        "intent": "open_line",
        "exchange_count": 0,
        "free_attack": False,
        "conduct": 0,
        "correct_reads": 0,
        "wrong_reads": 0,
        "witnesses": 1,
        "combat_noise": 0,
    }
    combat.update(overrides)
    game.guard_combat = combat
    return combat


def _down_outcome(name: str = "leave_neutral") -> dict:
    return {
        "outcome": name,
        "gold_delta": 6,
        "heat_delta": 1,
        "royal_alert_delta": 1,
        "fear_delta": 0,
        "execution_memory_response": None,
        "ghost_event": None,
    }


def test_guard_combat_witness_boundaries_and_empty_status(monkeypatch):
    game = GhostRevolutionRun()

    assert game.guard_combat_status() is None

    game.towns["ashfield"]["fear"] = 0
    game.towns["ashfield"]["population"] = 25
    monkeypatch.setattr(game, "town_trust", lambda _town_id: 0.12)

    assert game._guard_combat_witnesses("ashfield") == 5

    game.towns["ashfield"]["fear"] = 5
    game.towns["ashfield"]["population"] = 10
    monkeypatch.setattr(game, "town_trust", lambda _town_id: 0.0)

    assert game._guard_combat_witnesses("ashfield") == 1
    assert "One figure" in game._guard_witness_phrase(-10)
    assert "whole street" in game._guard_witness_phrase(99)


def test_guard_combat_status_uses_fallback_guard_identity():
    game = GhostRevolutionRun()
    game.guard_combat = {
        "town": "ashfield",
        "player_health": 8,
        "player_max_health": 10,
        "guard_health": 4,
        "guard_max_health": 8,
        "intent": "open_line",
        "free_attack": True,
    }

    status = game.guard_combat_status()

    assert status is not None
    assert status["guard_id"] == ""
    assert status["guard_rank"] == "watchman"
    assert status["guard_label"] == "Royal Guard"
    assert status["free_attack"] is True
    assert "free attack" in status["guard_tell"]


def test_guard_combat_finish_helpers_deny_without_combat():
    game = GhostRevolutionRun()

    assert game._finish_guard_combat_victory() is None
    assert "no active guard combat" in game.last_action_note.lower()

    assert game._finish_guard_combat_loss() is None
    assert "no active guard combat" in game.last_action_note.lower()


@pytest.mark.parametrize(
    ("outcome_name", "alive", "captured", "note_fragment"),
    (
        ("escape", True, False, "escape into the streets"),
        ("death", False, False, "final strike"),
    ),
)
def test_guard_combat_loss_resolves_escape_and_death(
    monkeypatch,
    outcome_name,
    alive,
    captured,
    note_fragment,
):
    game = GhostRevolutionRun()
    game.location = "millcross"
    _combat(game, player_health=0)

    monkeypatch.setattr(
        game._guards,
        "resolve_player_loss_outcome",
        lambda **_kwargs: {"outcome": outcome_name},
    )

    assert game._finish_guard_combat_loss() is None
    assert game.guard_combat is None
    assert game.alive is alive
    assert game.captured is captured
    assert note_fragment in game.last_action_note

    if outcome_name == "death":
        assert "kills you" in game.ending


def test_guard_down_rejects_inactive_and_unknown_outcomes(monkeypatch):
    game = GhostRevolutionRun()

    assert game.resolve_guard_down("leave") is None
    assert "no defeated guard" in game.last_action_note.lower()

    _combat(game, stage="down")
    monkeypatch.setattr(
        game._guards,
        "resolve_guard_down_outcome",
        lambda **_kwargs: {"outcome": "impossible"},
    )

    with pytest.raises(
        RuntimeError,
        match="unknown guard-down outcome: impossible",
    ):
        game.resolve_guard_down("leave")


def test_guard_down_falls_back_to_active_guard_id(monkeypatch):
    game = GhostRevolutionRun()
    game.location = "millcross"
    before = game.guard_count("millcross")

    _combat(game, stage="down")
    game.guard_combat.pop("guard_id")

    monkeypatch.setattr(
        game._guards,
        "resolve_guard_down_outcome",
        lambda **_kwargs: _down_outcome(),
    )

    assert game.resolve_guard_down("leave") is None
    assert game.guard_count("millcross") == before - 1
    assert game.guard_combat is None


def test_guard_down_requires_a_fallback_active_guard(monkeypatch):
    game = GhostRevolutionRun()
    game.towns["ashfield"]["guard_roster"] = []
    game.guard_combat = {
        "stage": "down",
        "town": "ashfield",
        "conduct": 0,
        "witnesses": 1,
    }

    monkeypatch.setattr(
        game._guards,
        "resolve_guard_down_outcome",
        lambda **_kwargs: _down_outcome(),
    )

    with pytest.raises(
        RuntimeError,
        match="guard-down resolution has no active guard",
    ):
        game.resolve_guard_down("leave")


def test_guard_retreat_and_move_deny_without_active_combat():
    game = GhostRevolutionRun()

    assert game.retreat_guard_combat() is None
    assert "no active guard combat" in game.last_action_note.lower()

    assert game.resolve_guard_combat_move("heavy") is None
    assert "no active guard combat" in game.last_action_note.lower()

    _combat(game, stage="down")

    assert game.resolve_guard_combat_move("heavy") is None
    assert "guard is down" in game.last_action_note.lower()


def test_guard_move_adds_technique_roll_and_opens_free_attack(monkeypatch):
    game = GhostRevolutionRun()
    combat = _combat(game)
    game.rng = ScriptedRNG(rolls=(42,))
    observed = {}

    def resolve_exchange(**kwargs):
        observed.update(kwargs)
        return {
            "guard_damage": 0,
            "player_damage": 0,
            "conduct_delta": 0,
            "correct_reads_delta": 0,
            "wrong_reads_delta": 0,
            "message": "The guard loses his footing.",
            "free_attack": True,
        }

    monkeypatch.setattr(
        game._guards,
        "resolve_tactical_exchange",
        resolve_exchange,
    )

    assert game.resolve_guard_combat_move("  PARRY  ") is None
    assert observed["player_move"] == "parry"
    assert observed["technique_roll"] == 42
    assert combat["free_attack"] is True
    assert game.last_action_note == "The guard loses his footing."


@pytest.mark.parametrize(
    ("case", "expected"),
    (
        ("active", "already in a guard combat"),
        ("phase", "only available during rebellion"),
        ("location", "no royal guard to confront here"),
        ("empty_roster", "no active royal guard"),
        ("knight", "knight controls this street"),
        ("passage", "looking the other way"),
        ("weapon", "need your personal weapon"),
        ("actions", "no actions remain"),
    ),
)
def test_fight_guard_preflight_denials(monkeypatch, case, expected):
    game = GhostRevolutionRun()
    game.location = "millcross"

    if case == "active":
        _combat(game)
    elif case == "phase":
        game.phase = "camp"
    elif case == "location":
        game.location = "base"
    elif case == "empty_roster":
        game.location = "ashfield"
    elif case == "knight":
        game.location = "crownmarket"
    elif case == "passage":
        monkeypatch.setattr(
            game,
            "guard_passage_active",
            lambda _town_id: True,
        )
    elif case == "weapon":
        game.primary_weapon = ""
    elif case == "actions":
        game.actions = 0
    else:
        raise AssertionError(f"unknown test case: {case}")

    assert game.fight_guard() is None
    assert expected in game.last_action_note.lower()
