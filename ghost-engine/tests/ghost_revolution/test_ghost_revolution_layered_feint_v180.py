
from copy import deepcopy

from ghost.examples.ghost_revolution.dev_shortcuts import (
    create_fight_stage_shortcut,
)


class NoRandomDraw:
    def randint(self, low, high):
        raise AssertionError("layered feint combat must not use random draws")


def _prepared_game():
    game, _packet = create_fight_stage_shortcut("prepared_king")
    game.rng = NoRandomDraw()
    return game


def _lock(
    game,
    intent,
    reaction,
    forced_read="dodge",
    combat_action=None,
):
    default_actions = {
        "read_feint_heavy": "parry",
        "read_feint_light": "deflect",
        "read_feint_bait": "parry",
    }
    game.king_fight["intent"] = intent
    observation = game.king_fight_opponent_observation()
    audit = game.apply_king_fight_opponent_intent(
        intent,
        proposed_reaction_plan=reaction,
        proposed_combat_action=(
            combat_action or default_actions.get(reaction, "dodge")
        ),
        proposed_feint_prediction=(
            reaction.removeprefix("read_")
            if reaction.startswith("read_feint_")
            else "none"
        ),
        proposed_forced_response_read=forced_read,
        selection_key=observation["selection_key"],
        provider_called=True,
    )
    assert audit["accepted"] is True
    assert audit["selected_reaction_plan"] == reaction
    return audit


def test_observation_requires_exact_feint_reaction_plans_v180():
    game = _prepared_game()
    observation = game.king_fight_opponent_observation()

    assert observation["legal_reaction_plans_by_intent"]["crown_guard"] == [
        "hold_center",
        "read_feint_heavy",
        "read_feint_light",
        "read_feint_bait",
    ]
    assert "read_feint" not in observation[
        "legal_reaction_plans_by_intent"
    ]["crown_guard"]
    assert observation["legal_feint_predictions"] == [
        "feint_heavy",
        "feint_light",
        "feint_bait",
    ]


def test_generic_read_feint_is_rejected_by_ghost_v180():
    game = _prepared_game()
    observation = game.king_fight_opponent_observation()

    audit = game.apply_king_fight_opponent_intent(
        "crown_guard",
        proposed_reaction_plan="read_feint",
        selection_key=observation["selection_key"],
    )

    assert audit["reaction_plan_accepted"] is False
    assert audit["selected_reaction_plan"] == "hold_center"


def test_exact_heavy_feint_read_uses_locked_physical_defense_v180():
    game = _prepared_game()
    _lock(
        game,
        "crown_guard",
        "read_feint_heavy",
        combat_action="parry",
    )

    packet = game.resolve_king_fight_move("feint_heavy")
    exchange = packet["exchange"]

    assert exchange["predicted_feint_subtype"] == "feint_heavy"
    assert exchange["reaction_plan_matched"] is True
    assert exchange["reaction_plan_triggered"] is True
    assert exchange["opponent_combat_action"] == "parry"
    assert exchange["result"] == "enemy_parry"
    assert exchange["king_damage"] == 0
    assert exchange["player_damage"] == 0
    assert exchange["initiative_after"]["state"] == "enemy_advantage"
    assert packet["forced_response"] is not None


def test_wrong_feint_subtype_preserves_locked_defense_v180():
    game = _prepared_game()
    _lock(
        game,
        "crown_guard",
        "read_feint_light",
        combat_action="deflect",
    )

    packet = game.resolve_king_fight_move("feint_heavy")
    exchange = packet["exchange"]

    assert exchange["predicted_feint_subtype"] == "feint_light"
    assert exchange["reaction_plan_matched"] is False
    assert exchange["reaction_plan_missed"] is True
    assert exchange["opponent_combat_action"] == "deflect"
    assert exchange["king_damage"] == 4
    assert exchange["player_damage"] == 0
    assert exchange["resolution_source"] == "symmetric_action_matrix"


def test_correct_bait_prediction_can_refuse_commitment_v180():
    game = _prepared_game()
    _lock(
        game,
        "crown_guard",
        "read_feint_bait",
        combat_action="parry",
    )

    packet = game.resolve_king_fight_move("feint_bait")
    exchange = packet["exchange"]

    assert exchange["predicted_feint_subtype"] == "feint_bait"
    assert exchange["reaction_plan_matched"] is True
    assert exchange["opponent_combat_action"] == "parry"
    assert exchange["bait_result"] == "enemy_reads_bait"
    assert exchange["king_damage"] == 0
    assert exchange["player_damage"] == 0
    assert packet["bait_response"] is None
    assert exchange["initiative_after"]["state"] == "enemy_advantage"


def test_bait_against_attacking_feint_prediction_opens_hidden_recovery_v180():
    game = _prepared_game()
    _lock(game, "crown_guard", "read_feint_heavy")

    packet = game.resolve_king_fight_move("feint_bait")
    exchange = packet["exchange"]
    bait = packet["bait_response"]

    assert exchange["reaction_plan_missed"] is True
    assert exchange["bait_result"] == "bait_setup"
    assert exchange["bait_hidden_recovery"] in {
        "quick_retaliation",
        "guard_recovery",
    }
    assert bait["bait_recovery"]["hidden_until_resolution"] is True
    assert "selected_recovery" not in bait["bait_recovery"]
    assert bait["allowed_moves"] == ["light", "parry", "pass"]
    assert packet["initiative"]["state"] == "player_advantage"


def test_invalid_bait_continuation_consumes_no_state_v180():
    game = _prepared_game()
    _lock(game, "crown_guard", "read_feint_heavy")
    game.resolve_king_fight_move("feint_bait")

    before = deepcopy(game.king_fight)
    denied = game.resolve_king_fight_move("heavy")

    assert denied["outcome"] == "bait_response_denied"
    assert denied["state_mutated"] is False
    assert game.king_fight == before


def test_guard_recovery_is_answered_by_light_attack_v180():
    game = _prepared_game()
    _lock(game, "crown_guard", "read_feint_heavy")
    game.resolve_king_fight_move("feint_bait")
    game.king_fight["bait_response"]["bait_recovery"]["selected_recovery"] = (
        "guard_recovery"
    )

    packet = game.resolve_king_fight_move("light")
    exchange = packet["exchange"]

    assert exchange["bait_hidden_recovery"] == "guard_recovery"
    assert exchange["bait_player_response"] == "light"
    assert exchange["bait_recovery_matched"] is True
    assert exchange["result"] == "bait_light_landed"
    assert exchange["king_damage"] == 2
    assert exchange["initiative_after"]["state"] == "player_advantage"


def test_quick_retaliation_is_answered_by_parry_v180():
    game = _prepared_game()
    _lock(game, "crown_guard", "read_feint_heavy")
    game.resolve_king_fight_move("feint_bait")
    game.king_fight["bait_response"]["bait_recovery"]["selected_recovery"] = (
        "quick_retaliation"
    )

    packet = game.resolve_king_fight_move("parry")
    exchange = packet["exchange"]

    assert exchange["bait_hidden_recovery"] == "quick_retaliation"
    assert exchange["bait_player_response"] == "parry"
    assert exchange["bait_recovery_matched"] is True
    assert exchange["result"] == "bait_parry_success"
    assert exchange["king_damage"] == 0
    assert packet["parry_opening"] is not None
    assert exchange["initiative_after"]["state"] == "player_advantage"


def test_wrong_bait_continuation_deals_no_damage_v180():
    game = _prepared_game()
    _lock(game, "crown_guard", "read_feint_heavy")
    game.resolve_king_fight_move("feint_bait")
    game.king_fight["bait_response"]["bait_recovery"]["selected_recovery"] = (
        "quick_retaliation"
    )

    packet = game.resolve_king_fight_move("light")
    exchange = packet["exchange"]

    assert exchange["bait_recovery_matched"] is False
    assert exchange["result"] == "bait_recovery_denied"
    assert exchange["king_damage"] == 0
    assert exchange["player_damage"] == 0
    assert exchange["initiative_after"]["state"] == "enemy_advantage"


def test_champion_exact_feint_read_uses_same_layered_contract_v180():
    game, _packet = create_fight_stage_shortcut("champion")
    game.rng = NoRandomDraw()
    game.king_fight["intent"] = "shield_wall"
    observation = game.king_fight_opponent_observation()
    audit = game.apply_king_fight_opponent_intent(
        "shield_wall",
        proposed_reaction_plan="read_feint_heavy",
        proposed_combat_action="parry",
        proposed_feint_prediction="feint_heavy",
        selection_key=observation["selection_key"],
        provider_called=True,
    )
    assert audit["selected_reaction_plan"] == "read_feint_heavy"

    packet = game.resolve_king_fight_move("feint_heavy")
    exchange = packet["exchange"]

    assert exchange["predicted_feint_subtype"] == "feint_heavy"
    assert exchange["reaction_plan_matched"] is True
    assert exchange["elite_knight_damage"] == 0
    assert exchange["player_damage"] == 0
    assert exchange["opponent_combat_action"] == "parry"
    assert exchange["result"] == "enemy_parry"
