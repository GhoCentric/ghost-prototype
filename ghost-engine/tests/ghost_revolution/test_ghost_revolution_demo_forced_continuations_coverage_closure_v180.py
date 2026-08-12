"""Coverage closure for king reaction and parry continuations."""

from __future__ import annotations

from ghost.examples.ghost_revolution.dev_shortcuts import (
    create_fight_stage_shortcut,
)


def _prepared_game():
    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )
    return game


def _phase_two_game():
    game, _packet = create_fight_stage_shortcut(
        "king_phase_two"
    )
    return game


def _opening(game, *, intent="royal_lunge"):
    game.king_fight["parry_opening"] = {
        "source": "player_parry",
        "intent": intent,
        "damage_bonus": 1,
        "guaranteed_next_attack": True,
        "allowed_moves": ("heavy", "light"),
    }


def test_adaptive_king_defense_covers_non_attack_and_failed_roll_v180(
    monkeypatch,
):
    game = _prepared_game()
    game.king_fight["adaptive_defense_enabled"] = True

    assert (
        game._king_defense_reaction(
            "parry",
            "royal_lunge",
        )
        is None
    )

    monkeypatch.setattr(
        game.rng,
        "randint",
        lambda _low, _high: 100,
    )

    assert (
        game._king_defense_reaction(
            "heavy",
            "royal_lunge",
        )
        is None
    )


def test_forced_response_repairs_invalid_packet_v180(
    monkeypatch,
):
    game = _prepared_game()
    game.king_fight["forced_response"] = []

    expected = {"outcome": "delegated"}

    monkeypatch.setattr(
        game,
        "_resolve_king_phase_move",
        lambda move: {
            **expected,
            "move": move,
        },
    )

    packet = game._resolve_king_forced_response(
        "light"
    )

    assert packet == {
        "outcome": "delegated",
        "move": "light",
    }
    assert game.king_fight["forced_response"] is None


def test_forced_response_rebuilds_read_and_returns_collapse_v180(
    monkeypatch,
):
    game = _prepared_game()
    game.king_fight["forced_response"] = {
        "reason": "king_parry",
        "source_move": "heavy",
        "allowed_moves": ("dodge", "light"),
        "next_intent": "royal_lunge",
        "message": "The king breaks your footing.",
        "random_used": False,
    }

    read_packet = {
        "predicted_move": "dodge",
    }

    monkeypatch.setattr(
        game._social,
        "lock_combat_recovery_read",
        lambda **_kwargs: read_packet,
    )

    monkeypatch.setattr(
        game._social,
        "resolve_combat_recovery",
        lambda **_kwargs: {
            "damage_to_opponent": 1,
            "damage_to_player": 0,
            "result": "forced_light_landed",
            "initiative_event": "player_attack_hit",
            "predicted_move": "dodge",
            "matched": False,
        },
    )

    collapse = {
        "outcome": "castle_collapsed",
    }

    monkeypatch.setattr(
        game,
        "_advance_castle_timer",
        lambda: collapse,
    )

    packet = game._resolve_king_forced_response(
        "light"
    )

    assert packet is collapse
    assert game.king_fight["forced_response"] is None
    assert game.king_fight["last_exchange"][
        "forced_response_read"
    ] == "dodge"


def test_parry_opening_transition_covers_collapse_and_non_dict_packet_v180(
    monkeypatch,
):
    collapse_game = _prepared_game()
    collapse_game.king_fight["king_health"] = 12
    _opening(collapse_game)

    collapse = {
        "outcome": "castle_collapsed",
    }

    monkeypatch.setattr(
        collapse_game,
        "_advance_castle_timer",
        lambda: collapse,
    )

    assert (
        collapse_game._resolve_king_phase_move(
            "heavy"
        )
        is collapse
    )

    transition_game = _prepared_game()
    transition_game.king_fight["king_health"] = 12
    _opening(transition_game)

    monkeypatch.setattr(
        transition_game,
        "_advance_castle_timer",
        lambda: None,
    )
    monkeypatch.setattr(
        transition_game,
        "_transition_to_elite_knight",
        lambda: None,
    )

    assert (
        transition_game._resolve_king_phase_move(
            "heavy"
        )
        is None
    )


def test_parry_opening_transition_covers_empty_tell_v180(
    monkeypatch,
):
    game = _prepared_game()
    game.king_fight["king_health"] = 12
    _opening(game)

    monkeypatch.setattr(
        game,
        "_advance_castle_timer",
        lambda: None,
    )
    monkeypatch.setattr(
        game,
        "_transition_to_elite_knight",
        lambda: {
            "outcome": "elite_knight_called",
            "tell": "",
        },
    )

    packet = game._resolve_king_phase_move(
        "heavy"
    )

    assert packet["outcome"] == "elite_knight_called"
    assert packet["tell"] == packet["narrative"]
    assert game.last_action_note == packet["tell"]


def test_parry_opening_phase_two_covers_both_victory_endings_v180(
    monkeypatch,
):
    clean = _phase_two_game()
    clean.king_fight["king_health"] = 2
    clean.king_fight[
        "clean_king_victory_possible"
    ] = True
    _opening(clean)

    clean_packet = {
        "outcome": "king_fate_choice",
    }
    monkeypatch.setattr(
        clean,
        "_enter_king_fate_choice",
        lambda: clean_packet,
    )

    assert (
        clean._resolve_king_phase_move(
            "heavy"
        )
        is clean_packet
    )

    uncertain = _phase_two_game()
    uncertain.king_fight["king_health"] = 2
    uncertain.king_fight[
        "clean_king_victory_possible"
    ] = False
    _opening(uncertain)

    uncertain_packet = {
        "outcome": "king_defeated_uncertain",
    }
    monkeypatch.setattr(
        uncertain,
        "_finish_uncertain_king_victory",
        lambda: uncertain_packet,
    )

    assert (
        uncertain._resolve_king_phase_move(
            "heavy"
        )
        is uncertain_packet
    )


def test_parry_opening_regular_exchange_returns_collapse_v180(
    monkeypatch,
):
    game = _prepared_game()
    game.king_fight["king_health"] = 20
    _opening(game)

    collapse = {
        "outcome": "castle_collapsed",
    }

    monkeypatch.setattr(
        game,
        "_advance_castle_timer",
        lambda: collapse,
    )

    assert (
        game._resolve_king_phase_move(
            "light"
        )
        is collapse
    )
