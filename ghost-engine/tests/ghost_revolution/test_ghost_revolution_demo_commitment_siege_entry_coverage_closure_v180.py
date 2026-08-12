"""Coverage closure for demo opponent commitment and siege entry."""

from __future__ import annotations

from copy import deepcopy

from ghost.examples.ghost_revolution.demo import (
    GhostRevolutionRun,
)
from ghost.examples.ghost_revolution.dev_shortcuts import (
    create_fight_stage_shortcut,
)


def _prepared_game() -> GhostRevolutionRun:
    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )
    return game


def test_public_tell_covers_lock_states_and_stage_boundaries_v180():
    no_fight = GhostRevolutionRun(seed=181)
    assert no_fight.king_fight_opponent_public_tell() is None

    forced = _prepared_game()
    forced.king_fight["forced_response"] = {
        "allowed_moves": ("light", "dodge"),
    }
    assert (
        forced.king_fight_opponent_public_tell()["source"]
        == "forced_response_observation"
    )

    opening = _prepared_game()
    opening.king_fight["parry_opening"] = {
        "allowed_moves": ("heavy", "light"),
    }
    assert (
        opening.king_fight_opponent_public_tell()["source"]
        == "parry_opening_observation"
    )

    king = _prepared_game()
    king.king_fight["intent"] = "crown_guard"
    tell = king.king_fight_opponent_public_tell()
    assert tell["enemy_actor"] == "king"

    elite = _prepared_game()
    elite.king_fight["stage"] = "elite_knight"
    elite.king_fight["intent"] = "shield_wall"
    tell = elite.king_fight_opponent_public_tell()
    assert tell["enemy_actor"] == "elite_knight"

    invalid_stage = _prepared_game()
    invalid_stage.king_fight["stage"] = "unknown"
    assert (
        invalid_stage.king_fight_opponent_public_tell()
        is None
    )

    unknown_intent = _prepared_game()
    unknown_intent.king_fight["intent"] = "unknown"
    assert (
        unknown_intent.king_fight_opponent_public_tell()
        is None
    )


def test_apply_opponent_intent_covers_no_fight_stale_and_locked_v180():
    no_fight = GhostRevolutionRun(seed=182)
    audit = no_fight.apply_king_fight_opponent_intent(
        "royal_lunge",
        selection_key="none",
    )
    assert audit["reason"] == "no_active_fight"

    stale = _prepared_game()
    audit = stale.apply_king_fight_opponent_intent(
        "royal_lunge",
        selection_key="stale",
    )
    assert audit["reason"] == "stale_selection_key"

    locked = _prepared_game()
    locked.king_fight["parry_opening"] = {
        "allowed_moves": ("heavy", "light"),
    }
    observation = locked.king_fight_opponent_observation()
    audit = locked.apply_king_fight_opponent_intent(
        "royal_lunge",
        selection_key=observation["selection_key"],
    )
    assert audit["reason"] == "parry_opening_pending"


def test_apply_opponent_intent_repairs_metadata_and_history_v180(
    monkeypatch,
):
    game = _prepared_game()
    observation = deepcopy(
        game.king_fight_opponent_observation()
    )
    observation["intent_labels"] = []
    observation["reaction_plan_labels"] = "invalid"

    monkeypatch.setattr(
        game,
        "king_fight_opponent_observation",
        lambda: deepcopy(observation),
    )

    game.king_fight["llm_opponent_history"] = {
        "damaged": True,
    }

    audit = game.apply_king_fight_opponent_intent(
        "royal_lunge",
        selection_key=observation["selection_key"],
        proposed_reaction_plan="hold_center",
        intent_explanation="   ",
        reaction_explanation="\t",
    )

    assert audit["accepted"] is True
    assert audit["intent_reason"] is None
    assert audit["reaction_reason"] is None
    assert isinstance(
        game.king_fight["llm_opponent_history"],
        list,
    )
    assert game.king_fight["llm_opponent_history"][-1] == audit


def test_king_status_and_duplicate_siege_boundaries_v180():
    game = GhostRevolutionRun(seed=183)
    assert game.king_fight_status() is None

    for stage, expected in (
        ("fate_choice", "execute_king"),
        ("crown_loop", "retire it"),
    ):
        game.king_fight = {
            "stage": stage,
            "forced_response": None,
        }
        status = game.king_fight_status()
        assert expected in status["tell"]

    game.king_fight = {
        "stage": "unknown",
        "forced_response": None,
    }
    status = game.king_fight_status()
    assert "tell" not in status

    game.ending = ""
    denied = game.siege_castle()
    assert denied is None
    assert "already underway" in game.last_action_note
