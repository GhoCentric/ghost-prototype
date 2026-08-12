"""Coverage closure for opponent observation in demo.py."""

from ghost.examples.ghost_revolution.dev_shortcuts import (
    create_fight_stage_shortcut,
)


def test_opponent_observation_returns_none_after_ending_v180():
    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )
    game.ending = "player_death"

    assert game.king_fight_opponent_observation() is None


def test_opponent_observation_rejects_unknown_stage_v180():
    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )
    game.king_fight["stage"] = "unknown_stage"

    assert game.king_fight_opponent_observation() is None


def test_opponent_observation_repairs_fallback_history_and_bands_v180():
    game, _packet = create_fight_stage_shortcut(
        "elite_knight"
    )
    fight = game.king_fight

    fight["exchange_count"] = 1
    fight["intent"] = "illegal_intent"
    fight["elite_knight_health"] = (
        fight["elite_knight_max_health"] // 2
    )
    fight["castle_timer"] = 5
    fight["king_morale_ticks"] = 3
    fight["llm_opponent_history"] = {
        "damaged": True,
    }

    observation = game.king_fight_opponent_observation()

    assert observation["fallback_intent"] == (
        observation["legal_intents"][1]
    )
    assert observation["enemy_health_band"] == "wounded"
    assert observation["castle_timer_band"] == "urgent"
    assert observation["king_morale_band"] == "high"
    assert observation["recent_opponent_intents"] == []
    assert fight["llm_opponent_history"] == []


def test_opponent_observation_streak_stops_at_changed_intent_v180():
    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )
    game.king_fight["llm_opponent_history"] = [
        {
            "stage": "king_phase_one",
            "selected_intent": "royal_lunge",
        },
        {
            "stage": "king_phase_one",
            "selected_intent": "crown_guard",
        },
        {
            "stage": "king_phase_one",
            "selected_intent": "crown_guard",
        },
    ]

    observation = game.king_fight_opponent_observation()

    assert observation["recent_opponent_intents"] == [
        "royal_lunge",
        "crown_guard",
        "crown_guard",
    ]
    assert observation["same_intent_streak"] == 2
