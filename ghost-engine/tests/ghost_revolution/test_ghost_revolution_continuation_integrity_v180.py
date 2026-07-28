"""Regression coverage for Ghost-owned combat continuation integrity."""

from collections import deque
from copy import deepcopy

from ghost.examples.ghost_revolution.dev_shortcuts import (
    create_fight_stage_shortcut,
)
from ghost.examples.ghost_revolution.presentation import (
    _print_king_fight_transition_receipt,
    king_fight_menu,
)


def _lock_commit_attack(
    game,
    intent,
    *,
    intent_reason="Maintain pressure toward victory.",
    reaction_reason="Commit without inventing a later response.",
):
    game.king_fight["intent"] = intent
    observation = game.king_fight_opponent_observation()

    audit = game.apply_king_fight_opponent_intent(
        intent,
        proposed_reaction_plan="commit_attack",
        proposed_forced_response_read="dodge",
        selection_key=observation["selection_key"],
        provider_called=True,
        intent_explanation=intent_reason,
        reaction_explanation=reaction_reason,
    )

    assert audit["accepted"] is True
    assert audit["selected_intent"] == intent
    assert audit["selected_reaction_plan"] == "commit_attack"


def test_king_parry_opening_rejects_illegal_move_without_mutation_v180():
    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )
    _lock_commit_attack(game, "royal_lunge")

    first = game.resolve_king_fight_move("parry")
    opening = first["parry_opening"]

    assert opening["source_commitment"]["intent"] == (
        "royal_lunge"
    )

    before = deepcopy(game.king_fight)
    denied = game.resolve_king_fight_move(
        "feint_heavy"
    )

    assert denied["outcome"] == (
        "parry_opening_move_denied"
    )
    assert denied["attempted_move"] == "feint_heavy"
    assert denied["allowed_moves"] == ["heavy", "light"]
    assert denied["state_mutated"] is False
    assert denied["parry_opening"] == opening
    assert game.king_fight == before
    assert "opening remains available" in (
        game.last_action_note
    )


def test_king_parry_continuation_preserves_llm_commitment_v180():
    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )
    _lock_commit_attack(
        game,
        "royal_lunge",
        intent_reason="Drive the player backward.",
        reaction_reason="Keep the attack committed.",
    )

    game.resolve_king_fight_move("parry")
    packet = game.resolve_king_fight_move("heavy")
    exchange = packet["exchange"]

    assert exchange["intent"] == "royal_lunge"
    assert exchange["result"] == "parry_opening_hit"
    assert exchange["king_damage"] == 5
    assert exchange["valid_responses"] == [
        "heavy",
        "light",
    ]
    assert exchange["resolution_source"] == (
        "parry_opening"
    )
    assert exchange["opponent_control_source"] == (
        "ghost_parry_continuation"
    )
    assert exchange["opponent_reaction_plan"] == (
        "commit_attack"
    )
    assert exchange[
        "opponent_reaction_plan_label"
    ] == "Commit Attack"
    assert exchange["opponent_intent_reason"] == (
        "Drive the player backward."
    )
    assert exchange["opponent_reaction_reason"] == (
        "Keep the attack committed."
    )
    assert exchange[
        "source_opponent_commitment"
    ]["intent"] == "royal_lunge"

    observation = game.king_fight_opponent_observation()
    previous = observation["previous_exchange_evidence"]

    assert previous["enemy_intent"] == "royal_lunge"
    assert previous["enemy_intent_label"] == (
        "Royal Lunge"
    )
    assert previous["opponent_control_source"] == (
        "ghost_parry_continuation"
    )


def test_legacy_king_opening_without_source_still_resolves_v180():
    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )
    fight = game.king_fight
    fight["parry_opening"] = {
        "source": "player_parry",
        "intent": "royal_lunge",
        "damage_bonus": 1,
        "guaranteed_next_attack": True,
        "allowed_moves": ("heavy", "light"),
    }

    packet = game.resolve_king_fight_move("light")
    exchange = packet["exchange"]

    assert exchange["intent"] == "royal_lunge"
    assert exchange["king_damage"] == 3
    assert exchange["source_opponent_commitment"] == {}
    assert exchange["opponent_reaction_plan"] is None
    assert exchange["opponent_control_source"] == (
        "ghost_parry_continuation"
    )


def test_elite_parry_opening_rejects_illegal_move_without_mutation_v180():
    game, _packet = create_fight_stage_shortcut(
        "elite_knight"
    )
    _lock_commit_attack(game, "champion_lunge")

    first = game.resolve_king_fight_move("parry")
    opening = first["parry_opening"]

    assert opening["source_commitment"]["intent"] == (
        "champion_lunge"
    )

    before = deepcopy(game.king_fight)
    denied = game.resolve_king_fight_move(
        "deflect"
    )

    assert denied["outcome"] == (
        "parry_opening_move_denied"
    )
    assert denied["stage"] == "elite_knight"
    assert denied["elite_knight_health"] == (
        before["elite_knight_health"]
    )
    assert game.king_fight == before


def test_elite_parry_continuation_preserves_llm_commitment_v180():
    game, _packet = create_fight_stage_shortcut(
        "elite_knight"
    )
    _lock_commit_attack(
        game,
        "champion_lunge",
        intent_reason="Protect the king by driving forward.",
        reaction_reason="Commit shield and blade together.",
    )

    game.resolve_king_fight_move("parry")
    packet = game.resolve_king_fight_move("light")
    exchange = packet["exchange"]

    assert exchange["intent"] == "champion_lunge"
    assert exchange["elite_knight_damage"] == 3
    assert exchange["valid_responses"] == [
        "heavy",
        "light",
    ]
    assert exchange["resolution_source"] == (
        "parry_opening"
    )
    assert exchange["opponent_control_source"] == (
        "ghost_parry_continuation"
    )
    assert exchange["opponent_reaction_plan"] == (
        "commit_attack"
    )
    assert exchange["opponent_intent_reason"] == (
        "Protect the king by driving forward."
    )


def test_legacy_elite_opening_without_source_still_resolves_v180():
    game, _packet = create_fight_stage_shortcut(
        "elite_knight"
    )
    fight = game.king_fight
    fight["intent"] = "open_recovery"
    fight["parry_opening"] = {
        "source": "player_parry",
        "intent": "champion_lunge",
        "target": "elite_knight",
        "damage_bonus": 1,
        "guaranteed_next_attack": True,
        "allowed_moves": ("heavy", "light"),
    }

    packet = game.resolve_king_fight_move("light")
    exchange = packet["exchange"]

    assert exchange["intent"] == "champion_lunge"
    assert exchange["elite_knight_damage"] == 3
    assert exchange["source_opponent_commitment"] == {}


def test_terminal_parry_menu_rejects_hidden_feint_choice_v180(
    monkeypatch,
    capsys,
):
    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )
    _lock_commit_attack(game, "royal_lunge")
    game.resolve_king_fight_move("parry")

    before = deepcopy(game.king_fight)
    choices = iter(("3", "q"))

    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt="": next(choices),
    )
    monkeypatch.delenv(
        "GHOST_LLM_OPPONENT",
        raising=False,
    )
    monkeypatch.delenv(
        "GHOST_REAL_LLM",
        raising=False,
    )

    king_fight_menu(game, deque())

    output = capsys.readouterr().out

    assert "parry opening only allows" in output
    assert "Feint follow-up" not in output
    assert game.king_fight == before


def test_terminal_forced_menu_rejects_hidden_heavy_choice_v180(
    monkeypatch,
    capsys,
):
    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )
    game.king_fight["forced_response"] = {
        "allowed_moves": ("dodge", "light"),
        "next_intent": "royal_lunge",
        "message": "Recover.",
        "random_used": False,
    }

    before = deepcopy(game.king_fight)
    choices = iter(("1", "q"))

    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt="": next(choices),
    )
    monkeypatch.delenv(
        "GHOST_LLM_OPPONENT",
        raising=False,
    )
    monkeypatch.delenv(
        "GHOST_REAL_LLM",
        raising=False,
    )

    king_fight_menu(game, deque())

    output = capsys.readouterr().out

    assert "While off balance" in output
    assert game.king_fight == before


def test_transition_receipt_exposes_exact_damage_and_half_health(
    monkeypatch,
    capsys,
):
    packet = {
        "transition_trigger": {
            "player_move": "heavy",
            "king_damage": 5,
            "king_health_after_final_attack": 10,
            "king_half_health": 10,
        },
    }

    monkeypatch.delenv(
        "GHOST_LLM_OPPONENT_DEBUG",
        raising=False,
    )
    monkeypatch.delenv(
        "GHOST_LLM_DEBUG",
        raising=False,
    )

    _print_king_fight_transition_receipt(packet)
    assert capsys.readouterr().out == ""

    monkeypatch.setenv(
        "GHOST_LLM_OPPONENT_DEBUG",
        "1",
    )

    _print_king_fight_transition_receipt({})
    assert capsys.readouterr().out == ""

    _print_king_fight_transition_receipt(packet)
    output = capsys.readouterr().out

    assert "GHOST PHASE RECEIPT" in output
    assert "Resolved move: heavy" in output
    assert "Damage dealt to king: 5" in output
    assert "King HP after strike: 10" in output
    assert "Champion threshold: 10 HP" in output
    assert "king remains alive" in output


def test_phase_one_transition_reports_five_not_fifteen_damage_v180():
    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )
    fight = game.king_fight
    fight["king_health"] = 15
    fight["parry_opening"] = {
        "source": "player_parry",
        "intent": "royal_lunge",
        "damage_bonus": 1,
        "guaranteed_next_attack": True,
        "allowed_moves": ("heavy", "light"),
    }

    packet = game.resolve_king_fight_move("heavy")
    trigger = packet["transition_trigger"]

    assert packet["outcome"] == "elite_knight_called"
    assert trigger["king_damage"] == 5
    assert trigger[
        "king_health_after_final_attack"
    ] == 10
    assert trigger["king_half_health"] == 10
    assert packet["king_health"] == 10
