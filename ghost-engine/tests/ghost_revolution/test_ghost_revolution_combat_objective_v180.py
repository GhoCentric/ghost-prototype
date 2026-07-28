from pathlib import Path

from ghost.examples.ghost_revolution.dev_shortcuts import (
    create_fight_stage_shortcut,
)
from ghost.examples.ghost_revolution.opponent_ai import (
    build_king_fight_opponent_intent_prompt,
)


def test_king_observation_contains_ghost_combat_objective_v180():
    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    objective = observation[
        "combat_objective"
    ]

    assert objective["state_owner"] == "Ghost"
    assert objective["actor"] == "king"
    assert objective["target"] == "player"
    assert objective["primary_goal"] == (
        "Defeat player before castle collapse."
    )

    tactical = objective[
        "tactical_state"
    ]

    assert tactical["actor_health"] == 20
    assert tactical["target_health"] == 10
    assert tactical["turns_remaining"] == 20


def test_wounded_player_creates_finishing_objective_v180():
    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    game.king_fight[
        "player_health"
    ] = 4

    objective = (
        game.king_fight_opponent_observation()
        ["combat_objective"]
    )

    tactical = objective[
        "tactical_state"
    ]

    assert tactical[
        "successful_exchanges_to_defeat_target"
    ] == 2

    assert tactical[
        "finishing_opportunity"
    ] is True

    assert tactical[
        "future_exchange_required_for_standard_finish"
    ] is True


def test_champion_receives_same_ghost_objective_contract_v180():
    game, _packet = create_fight_stage_shortcut(
        "elite_knight"
    )

    objective = (
        game.king_fight_opponent_observation()
        ["combat_objective"]
    )

    assert objective["actor"] == (
        "elite_knight"
    )

    assert objective["target"] == "player"
    assert objective["outcome_authority"] == (
        "Ghost"
    )


def test_opponent_prompt_requires_fight_level_optimization_v180():
    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    game.king_fight[
        "player_health"
    ] = 4

    observation = (
        game.king_fight_opponent_observation()
    )

    prompt = (
        build_king_fight_opponent_intent_prompt(
            observation
        )
    )

    assert (
        "combat_objective is authoritative"
        in prompt
    )

    assert (
        "current and future exchanges"
        in prompt
    )

    assert (
        "target receives another action"
        in prompt
    )

    assert (
        "finishing_opportunity=true"
        in prompt
    )

    assert (
        "genuine_opening is a real punishable"
        in prompt
    )

    assert (
        '"primary_goal":"Defeat player before '
        'castle collapse."'
        in prompt
    )


def test_open_recovery_is_not_described_as_free_testing_v180():
    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    description = observation[
        "intent_options"
    ]["overextended_recovery"]

    assert "real punishable opening" in (
        description
    )

    assert "test whether" not in (
        description
    )


def test_ghost_revolution_routes_objective_through_ghost_v180():
    demo_source = Path(
        "ghost/examples/ghost_revolution/"
        "demo.py"
    ).read_text(
        encoding="utf-8"
    )

    social_source = Path(
        "ghost/examples/ghost_revolution/"
        "social.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "self._social.build_combat_objective("
        in demo_source
    )

    assert (
        "self._runtime.api.build_combat_objective("
        in social_source
    )
