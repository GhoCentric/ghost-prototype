"""Coverage closure for demo timer, transition, patterns, and reactions."""

from __future__ import annotations

from ghost.examples.ghost_revolution import opponent_ai as oa
from ghost.examples.ghost_revolution.demo import GhostRevolutionRun
from ghost.examples.ghost_revolution.dev_shortcuts import (
    create_fight_stage_shortcut,
)


def _prepared_game() -> GhostRevolutionRun:
    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )
    return game


def test_timer_and_final_ending_helpers_cover_absent_and_non_dict_fights_v180():
    no_fight = GhostRevolutionRun(seed=191)
    assert no_fight._advance_castle_timer() is None

    champion = GhostRevolutionRun(seed=192)
    champion.king_fight = "truthy-non-dict"
    packet = champion._finish_player_death(
        killer="elite_knight"
    )
    assert packet["outcome"] == "player_killed_by_champion"

    king = GhostRevolutionRun(seed=193)
    king.king_fight = "truthy-non-dict"
    packet = king._finish_player_death(
        killer="king"
    )
    assert packet["outcome"] == "player_killed_by_king"

    last_breath = GhostRevolutionRun(seed=194)
    last_breath.king_fight = "truthy-non-dict"
    packet = last_breath._finish_last_breath_king_victory()
    assert packet["outcome"] == "last_breath_king_victory"
    assert packet["stage"] == "last_breath_king_victory"
    assert packet["castle_timer"] is None


def test_transition_to_elite_knight_covers_non_damage_final_exchange_v180():
    game = _prepared_game()
    fight = game.king_fight
    fight["king_health"] = fight["king_half_health"]
    fight["last_exchange"] = {
        "stage": "king_phase_one",
        "move": "parry",
        "intent": "royal_lunge",
        "result": "parry_success",
        "message": "The king yields ground.",
        "king_damage": 0,
        "player_damage": 0,
    }

    packet = game._transition_to_elite_knight()

    trigger = packet["transition_trigger"]
    assert trigger["last_attack_landed"] is False
    assert trigger["damage_target"] is None
    assert "without inventing a new wound" in trigger["reaction_truth"]


def test_pattern_state_repairs_and_light_pattern_bonus_v180():
    no_fight = GhostRevolutionRun(seed=195)
    assert no_fight._ensure_king_fight_pattern_state() == {}

    game = _prepared_game()
    game.king_fight["player_patterns"] = {
        "heavy_count": 0,
        "light_count": 4,
        "parry_count": 0,
        "deflect_count": 0,
        "dodge_count": 0,
        "last_moves": "damaged",
    }

    patterns = game._ensure_king_fight_pattern_state()
    assert patterns["last_moves"] == []

    patterns["last_moves"] = [
        "light",
        "light",
        "heavy",
        "light",
    ]
    bonus = game._king_pattern_bonus_for_move("light")
    assert bonus >= 30


def test_reaction_catalog_consumption_and_prediction_boundaries_v180():
    game = _prepared_game()

    assert oa._GHOST_ORIGINAL_REACTION_CATALOG(
        game,
        "king_phase_one",
        "unknown",
    ) == ("commit_attack",)
    labels = oa._GHOST_ORIGINAL_REACTION_LABELS(game)
    assert labels["track_dodge"] == "Track Dodge"

    no_fight = GhostRevolutionRun(seed=196)
    assert (
        no_fight._consume_king_fight_opponent_reaction_plan(
            "royal_lunge"
        )
        is None
    )

    fight = game.king_fight
    stage = fight["stage"]
    exchange = fight["exchange_count"]
    fight["llm_opponent_reaction_selection_key"] = (
        f"{stage}:{exchange}"
    )
    fight["llm_opponent_reaction_plan"] = "illegal"

    consumed = game._consume_king_fight_opponent_reaction_plan(
        "royal_lunge"
    )
    assert consumed == "commit_attack"

    non_predictive = oa._GHOST_ORIGINAL_PREDICTION_STATUS(
        game,
        "hold_center",
        "heavy",
    )
    assert non_predictive == {
        "predictive": False,
        "matched": None,
        "missed": None,
        "predicted_moves": [],
    }

    predictive = oa._GHOST_ORIGINAL_PREDICTION_STATUS(
        game,
        "parry_heavy",
        "heavy",
    )
    assert predictive == {
        "predictive": True,
        "matched": True,
        "missed": False,
        "predicted_moves": ["heavy"],
    }
