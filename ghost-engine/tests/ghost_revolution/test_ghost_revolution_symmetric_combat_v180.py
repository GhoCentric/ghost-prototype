from pathlib import Path

from ghost.examples.ghost_revolution.dev_shortcuts import (
    create_fight_stage_shortcut,
)
from ghost.examples.ghost_revolution.opponent_ai import (
    OPPONENT_STRUCTURED_OUTPUT_SCHEMA,
    build_king_fight_opponent_intent_prompt,
    parse_king_fight_opponent_intent,
)


class NoRandomDraw:
    def randint(self, low, high):
        raise AssertionError("symmetric combat must not use random draws")


def _prepared(stage="prepared_king"):
    game, _packet = create_fight_stage_shortcut(stage)
    game.rng = NoRandomDraw()
    return game


def _lock(
    game,
    *,
    intent,
    reaction,
    combat_action,
    prediction="none",
):
    game.king_fight["intent"] = intent
    observation = game.king_fight_opponent_observation()
    audit = game.apply_king_fight_opponent_intent(
        intent,
        proposed_reaction_plan=reaction,
        proposed_combat_action=combat_action,
        proposed_feint_prediction=prediction,
        proposed_forced_response_read="dodge",
        selection_key=observation["selection_key"],
        provider_called=True,
    )
    assert audit["combat_action_accepted"] is True
    assert audit["selected_combat_action"] == combat_action
    return audit


def test_schema_requires_real_combat_action_v180():
    properties = OPPONENT_STRUCTURED_OUTPUT_SCHEMA["properties"]
    required = OPPONENT_STRUCTURED_OUTPUT_SCHEMA["required"]

    assert "combat_action" in properties
    assert "combat_action" in required
    assert properties["combat_action"]["enum"] == [
        "heavy",
        "light",
        "feint_heavy",
        "feint_light",
        "feint_bait",
        "parry",
        "deflect",
        "dodge",
    ]


def test_observation_and_prompt_give_enemy_player_action_space_v180():
    game = _prepared()
    observation = game.king_fight_opponent_observation()

    assert observation["legal_combat_actions"] == [
        "heavy",
        "light",
        "feint_heavy",
        "feint_light",
        "feint_bait",
        "parry",
        "deflect",
        "dodge",
    ]

    prompt = build_king_fight_opponent_intent_prompt(observation)
    assert "combat_action is the opponent's real physical move" in prompt
    assert "feint_prediction and combat_action are separate" in prompt
    assert '"combat_action":' in prompt


def test_parser_validates_combat_action_independently_v180():
    parsed = parse_king_fight_opponent_intent(
        (
            '{"intent":"crown_guard",'
            '"reaction_plan":"read_feint_bait",'
            '"combat_action":"light",'
            '"feint_prediction":"feint_bait",'
            '"forced_response_read":"dodge",'
            '"intent_reason":"Repeated bait pattern.",'
            '"reaction_reason":"Punish the recovery."}'
        ),
        ("crown_guard",),
        {"crown_guard": ("read_feint_bait",)},
    )

    assert parsed["combat_action"] == "light"
    assert parsed["combat_action_accepted"] is True
    assert parsed["feint_prediction"] == "feint_bait"


def test_provider_failure_uses_semantic_action_fallback_v180():
    game = _prepared()
    observation = game.king_fight_opponent_observation()

    audit = game.apply_king_fight_opponent_intent(
        None,
        proposed_reaction_plan=None,
        proposed_combat_action=None,
        proposed_feint_prediction=None,
        proposed_forced_response_read=None,
        selection_key=observation["selection_key"],
        provider_called=True,
        parser_reason="empty_response",
        reaction_parser_reason="empty_response",
    )

    assert audit["combat_action_accepted"] is False
    assert audit["combat_action_fallback_used"] is True
    assert audit["selected_reaction_plan"] == "commit_attack"
    assert audit["selected_combat_action"] == "heavy"

    packet = game.resolve_king_fight_move("light")
    assert packet["exchange"]["resolution_source"] == "symmetric_action_matrix"
    assert packet["exchange"]["opponent_combat_action"] == "heavy"


def test_normal_reaction_prediction_is_audited_separately_v180():
    game = _prepared()
    _lock(
        game,
        intent="overextended_recovery",
        reaction="parry_heavy",
        combat_action="dodge",
    )

    packet = game.resolve_king_fight_move("heavy")
    exchange = packet["exchange"]

    assert exchange["expected"] == "heavy"
    assert exchange["predicted_feint_subtype"] is None
    assert exchange["reaction_plan_predictive"] is True
    assert exchange["reaction_plan_matched"] is True
    assert exchange["opponent_combat_action"] == "dodge"


def test_wrong_bait_prediction_light_interrupts_feint_heavy_v180():
    game = _prepared()
    _lock(
        game,
        intent="crown_guard",
        reaction="read_feint_bait",
        combat_action="light",
        prediction="feint_bait",
    )

    packet = game.resolve_king_fight_move("feint_heavy")
    exchange = packet["exchange"]

    assert exchange["predicted_feint_subtype"] == "feint_bait"
    assert exchange["reaction_plan_missed"] is True
    assert exchange["opponent_combat_action"] == "light"
    assert exchange["opponent_action_effective"] is True
    assert exchange["result"] == "enemy_action_interrupts"
    assert exchange["king_damage"] == 0
    assert exchange["player_damage"] == 2
    assert exchange["resolution_source"] == "symmetric_action_matrix"
    assert exchange["initiative_after"]["state"] == "enemy_advantage"


def test_wrong_bait_prediction_parry_still_catches_committed_heavy_v180():
    game = _prepared()
    _lock(
        game,
        intent="crown_guard",
        reaction="read_feint_bait",
        combat_action="parry",
        prediction="feint_bait",
    )

    packet = game.resolve_king_fight_move("feint_heavy")
    exchange = packet["exchange"]

    assert exchange["reaction_plan_missed"] is True
    assert exchange["opponent_combat_action"] == "parry"
    assert exchange["result"] == "enemy_parry"
    assert exchange["king_damage"] == 0
    assert exchange["player_damage"] == 0
    assert packet["forced_response"] is not None
    assert exchange["initiative_after"]["state"] == "enemy_advantage"


def test_exact_bait_prediction_light_punishes_recovery_v180():
    game = _prepared()
    _lock(
        game,
        intent="crown_guard",
        reaction="read_feint_bait",
        combat_action="light",
        prediction="feint_bait",
    )

    packet = game.resolve_king_fight_move("feint_bait")
    exchange = packet["exchange"]

    assert exchange["reaction_plan_matched"] is True
    assert exchange["result"] == "enemy_punishes_bait"
    assert exchange["player_damage"] == 2
    assert exchange["king_damage"] == 0
    assert packet["bait_response"] is None


def test_wrong_prediction_can_still_be_baited_when_action_commits_v180():
    game = _prepared()
    _lock(
        game,
        intent="crown_guard",
        reaction="read_feint_heavy",
        combat_action="parry",
        prediction="feint_heavy",
    )

    packet = game.resolve_king_fight_move("feint_bait")
    exchange = packet["exchange"]

    assert exchange["reaction_plan_missed"] is True
    assert exchange["result"] == "bait_setup"
    assert exchange["player_damage"] == 0
    assert exchange["king_damage"] == 0
    assert packet["bait_response"] is not None
    assert packet["initiative"]["state"] == "player_advantage"


def test_player_parry_catches_enemy_heavy_action_v180():
    game = _prepared()
    _lock(
        game,
        intent="royal_lunge",
        reaction="commit_attack",
        combat_action="heavy",
    )

    packet = game.resolve_king_fight_move("parry")
    exchange = packet["exchange"]

    assert exchange["opponent_combat_action"] == "heavy"
    assert exchange["result"] == "player_parry"
    assert exchange["player_damage"] == 0
    assert packet["parry_opening"] is not None
    assert packet["initiative"]["state"] == "player_advantage"


def test_player_parry_catches_enemy_feint_heavy_commitment_v180():
    game = _prepared()
    _lock(
        game,
        intent="royal_lunge",
        reaction="commit_attack",
        combat_action="feint_heavy",
    )

    packet = game.resolve_king_fight_move("parry")
    exchange = packet["exchange"]

    assert exchange["result"] == "player_parry"
    assert exchange["player_damage"] == 0
    assert exchange["king_damage"] == 0
    assert packet["parry_opening"] is not None


def test_enemy_feint_light_beats_mismatched_player_parry_v180():
    game = _prepared()
    _lock(
        game,
        intent="royal_lunge",
        reaction="commit_attack",
        combat_action="feint_light",
    )

    packet = game.resolve_king_fight_move("parry")
    exchange = packet["exchange"]

    assert exchange["result"] == "enemy_attack_beats_defense"
    assert exchange["player_damage"] == 2
    assert exchange["king_damage"] == 0


def test_attack_priority_is_symmetric_for_light_and_heavy_v180():
    enemy_fast = _prepared()
    _lock(
        enemy_fast,
        intent="royal_lunge",
        reaction="commit_attack",
        combat_action="light",
    )
    packet = enemy_fast.resolve_king_fight_move("heavy")
    assert packet["exchange"]["result"] == "enemy_action_interrupts"
    assert packet["exchange"]["player_damage"] == 2

    player_fast = _prepared()
    _lock(
        player_fast,
        intent="royal_lunge",
        reaction="commit_attack",
        combat_action="heavy",
    )
    packet = player_fast.resolve_king_fight_move("light")
    assert packet["exchange"]["result"] == "player_action_interrupts"
    assert packet["exchange"]["king_damage"] == 2


def test_enemy_pure_bait_wins_tempo_without_automatic_damage_v180():
    game = _prepared()
    _lock(
        game,
        intent="crown_guard",
        reaction="hold_center",
        combat_action="feint_bait",
    )

    packet = game.resolve_king_fight_move("heavy")
    exchange = packet["exchange"]

    assert exchange["result"] == "opponent_bait_succeeds"
    assert exchange["king_damage"] == 0
    assert exchange["player_damage"] == 0
    assert packet["initiative"]["state"] == "enemy_advantage"


def test_champion_uses_same_symmetric_action_matrix_v180():
    game = _prepared("champion")
    _lock(
        game,
        intent="shield_wall",
        reaction="read_feint_bait",
        combat_action="light",
        prediction="feint_bait",
    )

    packet = game.resolve_king_fight_move("feint_heavy")
    exchange = packet["exchange"]

    assert exchange["opponent_combat_action"] == "light"
    assert exchange["reaction_plan_missed"] is True
    assert exchange["elite_knight_damage"] == 0
    assert exchange["player_damage"] == 3


def test_terminal_selector_passes_combat_action_candidate_v180():
    source = Path(
        "ghost/examples/ghost_revolution/presentation.py"
    ).read_text(encoding="utf-8")

    assert "proposed_combat_action=(" in source
    assert '"proposed_combat_action_candidate"' in source
    assert "Previous combat action: " in source
