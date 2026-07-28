from ghost.examples.ghost_revolution.config import (
    KING_FIGHT_PLAYER_DAMAGE,
)
from ghost.examples.ghost_revolution.dev_shortcuts import (
    create_fight_stage_shortcut,
)


class NoRandomDraw:
    def randint(self, low, high):
        raise AssertionError(
            "LLM-committed combat must not use a random counter draw"
        )


def _prepared_game():
    game, packet = create_fight_stage_shortcut(
        "prepared_king"
    )
    game.rng = NoRandomDraw()
    return game, packet


def _lock_plan(
    game,
    intent,
    reaction_plan,
    forced_read="dodge",
):
    game.king_fight["intent"] = intent
    observation = game.king_fight_opponent_observation()

    audit = game.apply_king_fight_opponent_intent(
        intent,
        proposed_reaction_plan=reaction_plan,
        proposed_forced_response_read=forced_read,
        selection_key=observation["selection_key"],
        provider_called=True,
    )

    assert audit["selected_intent"] == intent
    return audit


def test_player_damage_contract_is_explicit_and_bounded_v180():
    assert KING_FIGHT_PLAYER_DAMAGE["normal"] == {
        "heavy": 4,
        "light": 2,
        "feint_heavy": 4,
        "feint_light": 2,
        "deflect": 2,
    }
    assert KING_FIGHT_PLAYER_DAMAGE["parry_opening"] == {
        "heavy": 5,
        "light": 3,
    }
    assert KING_FIGHT_PLAYER_DAMAGE["forced_recovery"] == {
        "light": 1,
        "dodge": 0,
    }


def test_prepared_assault_no_longer_multiplies_duel_damage_v180():
    game, packet = _prepared_game()

    assert packet["prepared_assault"] is True
    assert packet["damage_bonus_percent"] == 0
    assert game.king_fight["damage_bonus_percent"] == 0
    assert game.king_fight["castle_timer"] == 20


def test_normal_heavy_and_light_deal_four_and_two_v180():
    heavy_game, _packet = _prepared_game()
    _lock_plan(
        heavy_game,
        "overextended_recovery",
        "genuine_opening",
    )
    heavy = heavy_game.resolve_king_fight_move("heavy")

    light_game, _packet = _prepared_game()
    _lock_plan(
        light_game,
        "overextended_recovery",
        "genuine_opening",
    )
    light = light_game.resolve_king_fight_move("light")

    assert heavy["exchange"]["king_damage"] == 4
    assert light["exchange"]["king_damage"] == 2


def test_feint_followups_use_normal_attack_damage_v180():
    heavy_game, _packet = _prepared_game()
    _lock_plan(
        heavy_game,
        "crown_guard",
        "hold_center",
    )
    heavy = heavy_game.resolve_king_fight_move("feint_heavy")

    light_game, _packet = _prepared_game()
    _lock_plan(
        light_game,
        "crown_guard",
        "hold_center",
    )
    light = light_game.resolve_king_fight_move("feint_light")

    assert heavy["exchange"]["king_damage"] == 4
    assert light["exchange"]["king_damage"] == 2


def test_successful_parry_opens_exact_five_or_three_damage_v180():
    heavy_game, _packet = _prepared_game()
    _lock_plan(
        heavy_game,
        "royal_lunge",
        "commit_attack",
    )
    first = heavy_game.resolve_king_fight_move("parry")
    heavy = heavy_game.resolve_king_fight_move("heavy")

    light_game, _packet = _prepared_game()
    _lock_plan(
        light_game,
        "royal_lunge",
        "commit_attack",
    )
    second = light_game.resolve_king_fight_move("parry")
    light = light_game.resolve_king_fight_move("light")

    assert first["exchange"]["king_damage"] == 0
    assert second["exchange"]["king_damage"] == 0
    assert heavy["exchange"]["king_damage"] == 5
    assert light["exchange"]["king_damage"] == 3


def test_forced_read_is_hidden_until_player_commits_v180():
    game, _packet = _prepared_game()
    _lock_plan(
        game,
        "overextended_recovery",
        "parry_heavy",
        forced_read="light",
    )

    first = game.resolve_king_fight_move("heavy")
    forced = first["forced_response"]

    assert forced["random_used"] is False
    assert forced["recovery_read"]["locked"] is True
    assert forced["recovery_read"]["hidden_until_resolution"] is True
    assert "selected_move" not in forced["recovery_read"]


def test_matched_forced_light_read_denies_damage_v180():
    game, _packet = _prepared_game()
    _lock_plan(
        game,
        "overextended_recovery",
        "parry_heavy",
        forced_read="light",
    )
    game.resolve_king_fight_move("heavy")

    resolved = game.resolve_king_fight_move("light")
    exchange = resolved["exchange"]

    assert exchange["forced_response_read"] == "light"
    assert exchange["forced_response_read_matched"] is True
    assert exchange["result"] == "forced_recovery_denied"
    assert exchange["king_damage"] == 0
    assert exchange["player_damage"] == 0
    assert exchange["initiative_after"]["state"] == "enemy_advantage"


def test_missed_dodge_read_allows_one_damage_light_v180():
    game, _packet = _prepared_game()
    _lock_plan(
        game,
        "overextended_recovery",
        "parry_heavy",
        forced_read="dodge",
    )
    game.resolve_king_fight_move("heavy")

    resolved = game.resolve_king_fight_move("light")
    exchange = resolved["exchange"]

    assert exchange["forced_response_read"] == "dodge"
    assert exchange["forced_response_read_matched"] is False
    assert exchange["result"] == "forced_light_landed"
    assert exchange["king_damage"] == 1
    assert exchange["player_damage"] == 0
    assert exchange["initiative_after"]["state"] == "player_advantage"


def test_missed_light_read_allows_damage_free_dodge_v180():
    game, _packet = _prepared_game()
    _lock_plan(
        game,
        "overextended_recovery",
        "parry_heavy",
        forced_read="light",
    )
    game.resolve_king_fight_move("heavy")

    resolved = game.resolve_king_fight_move("dodge")
    exchange = resolved["exchange"]

    assert exchange["forced_response_read"] == "light"
    assert exchange["forced_response_read_matched"] is False
    assert exchange["result"] == "forced_dodge_escaped"
    assert exchange["king_damage"] == 0
    assert exchange["player_damage"] == 0
    assert exchange["initiative_after"]["state"] == "neutral"


def test_wrong_prediction_changes_tempo_without_bonus_damage_v180():
    game, _packet = _prepared_game()
    _lock_plan(
        game,
        "overextended_recovery",
        "deflect_light",
    )

    resolved = game.resolve_king_fight_move("heavy")
    exchange = resolved["exchange"]

    assert exchange["reaction_plan_missed"] is True
    assert exchange["reaction_miss_bonus"] == 0
    assert exchange["king_damage"] == 4
    assert exchange["initiative_event"] == (
        "prediction_missed_player_hit"
    )
    assert exchange["initiative_after"]["state"] == (
        "player_advantage"
    )
