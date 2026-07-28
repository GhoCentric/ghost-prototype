def test_break_parry_does_not_grant_player_opening_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    audit = (
        game.apply_king_fight_opponent_intent(
            "royal_lunge",
            proposed_reaction_plan=(
                "break_parry"
            ),
            selection_key=(
                observation["selection_key"]
            ),
        )
    )

    assert audit["accepted"] is True
    assert audit[
        "selected_reaction_plan"
    ] == "break_parry"

    packet = game.resolve_king_fight_move(
        "parry"
    )

    exchange = packet["exchange"]

    assert exchange["result"] == (
        "king_breaks_parry"
    )

    assert exchange["player_damage"] > 0
    assert exchange["king_damage"] == 0

    assert (
        exchange["reaction_plan_matched"]
        is True
    )

    assert (
        exchange["reaction_plan_triggered"]
        is True
    )

    assert exchange[
        "resolution_source"
    ] == "reaction_plan"

    assert exchange["parry_opening"] is None
    assert packet["parry_opening"] is None

    assert game.king_fight[
        "parry_opening"
    ] is None


def test_unbroken_parry_still_grants_player_opening_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    packet = game.resolve_king_fight_move(
        "parry"
    )

    exchange = packet["exchange"]
    opening = packet["parry_opening"]

    assert exchange["result"] == (
        "correct_read"
    )

    assert exchange["player_damage"] == 0
    assert exchange["king_damage"] == 0

    assert isinstance(opening, dict)

    assert opening[
        "guaranteed_next_attack"
    ] is True

    assert opening["damage_bonus"] == 1

    assert game.king_fight[
        "parry_opening"
    ] == opening
