"""Coverage closure for base king/Champion transition continuations."""

from __future__ import annotations

from ghost.examples.ghost_revolution import opponent_ai as oa
from ghost.examples.ghost_revolution.dev_shortcuts import (
    create_fight_stage_shortcut,
)


def _prepared_king():
    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )
    return game


def _elite_knight():
    game, _packet = create_fight_stage_shortcut(
        "elite_knight"
    )
    return game


def _opening(*, intent="royal_lunge"):
    return {
        "source": "player_parry",
        "intent": intent,
        "damage_bonus": 1,
        "guaranteed_next_attack": True,
        "allowed_moves": ("heavy", "light"),
    }


def _prepare_base_king_transition(game):
    game.king_fight["king_health"] = 14
    game.king_fight["intent"] = "overextended_recovery"
    game.king_fight["parry_opening"] = None
    game._consume_king_fight_opponent_reaction_plan = (
        lambda _intent: None
    )
    game._king_defense_reaction = (
        lambda *_args, **_kwargs: None
    )


def test_base_king_phase_transition_covers_collapse_and_empty_tell_v180(
    monkeypatch,
):
    collapse_game = _prepared_king()
    _prepare_base_king_transition(collapse_game)

    collapse = {
        "outcome": "castle_collapse_legend",
    }

    monkeypatch.setattr(
        collapse_game,
        "_advance_castle_timer",
        lambda: collapse,
    )

    packet = oa._GHOST_ORIGINAL_RESOLVE_KING_PHASE_MOVE(
        collapse_game,
        "heavy",
    )

    assert packet is collapse

    transition_game = _prepared_king()
    _prepare_base_king_transition(transition_game)

    monkeypatch.setattr(
        transition_game,
        "_advance_castle_timer",
        lambda: None,
    )
    monkeypatch.setattr(
        transition_game,
        "_transition_to_elite_knight",
        lambda: {
            "outcome": "elite_knight_called",
            "tell": "",
        },
    )

    packet = oa._GHOST_ORIGINAL_RESOLVE_KING_PHASE_MOVE(
        transition_game,
        "heavy",
    )

    assert packet["tell"] == packet["narrative"]
    assert transition_game.last_action_note == packet["tell"]

    non_dict_game = _prepared_king()
    _prepare_base_king_transition(non_dict_game)

    monkeypatch.setattr(
        non_dict_game,
        "_advance_castle_timer",
        lambda: None,
    )
    monkeypatch.setattr(
        non_dict_game,
        "_transition_to_elite_knight",
        lambda: None,
    )

    assert (
        oa._GHOST_ORIGINAL_RESOLVE_KING_PHASE_MOVE(
            non_dict_game,
            "heavy",
        )
        is None
    )


def test_base_elite_parry_opening_covers_defeat_and_collapse_v180(
    monkeypatch,
):
    defeated = _elite_knight()
    defeated.king_fight["elite_knight_health"] = 5
    defeated.king_fight["parry_opening"] = _opening(
        intent="shield_wall"
    )

    monkeypatch.setattr(
        defeated,
        "_advance_castle_timer",
        lambda: None,
    )

    packet = oa._GHOST_ORIGINAL_RESOLVE_ELITE_KNIGHT_MOVE(
        defeated,
        "heavy",
    )

    assert packet["outcome"] == "elite_knight_defeated"
    assert packet["stage"] == "king_phase_two"
    assert defeated.king_fight["elite_knight_health"] == 0

    collapse_game = _elite_knight()
    collapse_game.king_fight["elite_knight_health"] = 5
    collapse_game.king_fight["parry_opening"] = _opening(
        intent="shield_wall"
    )

    collapse = {
        "outcome": "castle_collapse_legend",
    }

    monkeypatch.setattr(
        collapse_game,
        "_advance_castle_timer",
        lambda: collapse,
    )

    packet = oa._GHOST_ORIGINAL_RESOLVE_ELITE_KNIGHT_MOVE(
        collapse_game,
        "heavy",
    )

    assert packet is collapse


def test_base_elite_parry_opening_regular_exchange_returns_collapse_v180(
    monkeypatch,
):
    game = _elite_knight()
    game.king_fight["elite_knight_health"] = 20
    game.king_fight["parry_opening"] = _opening(
        intent="shield_wall"
    )

    collapse = {
        "outcome": "castle_collapse_legend",
    }

    monkeypatch.setattr(
        game,
        "_advance_castle_timer",
        lambda: collapse,
    )

    packet = oa._GHOST_ORIGINAL_RESOLVE_ELITE_KNIGHT_MOVE(
        game,
        "light",
    )

    assert packet is collapse
    assert game.king_fight["elite_knight_health"] == 17
