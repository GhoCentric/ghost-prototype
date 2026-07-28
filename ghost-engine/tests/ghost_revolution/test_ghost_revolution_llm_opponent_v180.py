from pathlib import Path


def test_opponent_observation_is_limited_and_legal_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    assert observation["selection_required"] is True
    assert observation["selection_key"] == (
        "king_phase_one:0"
    )
    assert observation["enemy_actor"] == "king"

    assert observation["legal_intents"] == [
        "royal_lunge",
        "crown_guard",
        "overextended_recovery",
    ]

    assert "player_health" not in observation
    assert "king_health" not in observation
    assert "clean_king_victory_possible" not in observation

    assert observation["state_owner"] == "Ghost"
    assert observation["llm_role"] == (
        "opponent_intent_proposal_only"
    )


def test_ghost_accepts_one_legal_opponent_intent_v180():
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
            "crown_guard",
            selection_key=(
                observation[
                    "selection_key"
                ]
            ),
            provider_called=True,
            parser_reason="accepted",
        )
    )

    assert audit["accepted"] is True
    assert audit["fallback_used"] is False
    assert audit["selected_intent"] == (
        "crown_guard"
    )
    assert game.king_fight["intent"] == (
        "crown_guard"
    )


def test_ghost_rejects_illegal_intent_and_uses_fallback_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    deterministic_fallback = observation[
        "fallback_intent"
    ]

    audit = (
        game.apply_king_fight_opponent_intent(
            "summon_dragon",
            selection_key=(
                observation[
                    "selection_key"
                ]
            ),
            provider_called=True,
            parser_reason="illegal_intent",
        )
    )

    assert audit["accepted"] is False
    assert audit["fallback_used"] is True
    assert audit["reason"] == "illegal_intent"
    assert audit["selected_intent"] == (
        deterministic_fallback
    )
    assert game.king_fight["intent"] == (
        deterministic_fallback
    )


def test_opponent_intent_cannot_reroll_same_exchange_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    first = (
        game.apply_king_fight_opponent_intent(
            "crown_guard",
            selection_key=(
                observation[
                    "selection_key"
                ]
            ),
            provider_called=True,
            parser_reason="accepted",
        )
    )

    second = (
        game.apply_king_fight_opponent_intent(
            "overextended_recovery",
            selection_key=(
                observation[
                    "selection_key"
                ]
            ),
            provider_called=True,
            parser_reason="accepted",
        )
    )

    assert first == second
    assert second["selected_intent"] == (
        "crown_guard"
    )
    assert game.king_fight["intent"] == (
        "crown_guard"
    )


def test_opponent_selection_pauses_for_parry_opening_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    game.king_fight["parry_opening"] = {
        "source": "player_parry",
        "damage_bonus": 1,
        "guaranteed_next_attack": True,
        "allowed_moves": (
            "heavy",
            "light",
        ),
    }

    observation = (
        game.king_fight_opponent_observation()
    )

    assert observation["selection_required"] is False
    assert observation["locked_reason"] == (
        "parry_opening_pending"
    )


def test_opponent_parser_accepts_strict_json_v180():
    from ghost.examples.ghost_revolution.opponent_ai import (
        parse_king_fight_opponent_intent,
    )

    parsed = (
        parse_king_fight_opponent_intent(
            '{"intent":"crown_guard"}',
            (
                "royal_lunge",
                "crown_guard",
                "overextended_recovery",
            ),
        )
    )

    assert parsed["accepted"] is True
    assert parsed["intent"] == "crown_guard"
    assert parsed["reason"] == "accepted"


def test_opponent_parser_rejects_illegal_choice_v180():
    from ghost.examples.ghost_revolution.opponent_ai import (
        parse_king_fight_opponent_intent,
    )

    parsed = (
        parse_king_fight_opponent_intent(
            '{"intent":"summon_dragon"}',
            (
                "royal_lunge",
                "crown_guard",
                "overextended_recovery",
            ),
        )
    )

    assert parsed["accepted"] is False
    assert parsed["intent"] is None
    assert parsed["candidate"] == (
        "summon_dragon"
    )
    assert parsed["reason"] == (
        "illegal_intent"
    )


def test_opponent_prompt_is_policy_only_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )
    from ghost.examples.ghost_revolution.opponent_ai import (
        build_king_fight_opponent_intent_prompt,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    prompt = (
        build_king_fight_opponent_intent_prompt(
            observation
        )
    )

    assert "Choose exactly one value" in prompt
    assert '"intent":"LEGAL_INTENT"' in prompt
    assert "Ghost owns" in prompt
    assert "do not decide hits" in prompt.lower()
    assert "vivid, cinematic" not in prompt
    assert "fight narrator" not in prompt.lower()


def test_opponent_bridge_uses_same_configured_model_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )
    from ghost.examples.ghost_revolution.llm_bridge import (
        LLMBridgeConfig,
    )
    from ghost.examples.ghost_revolution.opponent_ai import (
        GhostFightOpponentBridge,
    )

    seen = {}

    class FakeClient:
        def __call__(
            self,
            prompt,
            *,
            config,
        ):
            seen["prompt"] = prompt
            seen["model"] = config.model
            seen["max_output_tokens"] = (
                config.max_output_tokens
            )
            return '{"intent":"crown_guard"}'

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    bridge = GhostFightOpponentBridge(
        client=FakeClient(),
        config=LLMBridgeConfig(
            model="same-model-as-narrator"
        ),
    )

    result = (
        bridge
        .generate_king_fight_opponent_intent(
            observation
        )
    )

    assert result["provider_called"] is True
    assert result["proposed_intent"] == (
        "crown_guard"
    )
    assert result["parser"]["accepted"] is True
    assert seen["model"] == (
        "same-model-as-narrator"
    )
    assert seen["max_output_tokens"] <= 768
    assert "OPPONENT_OBSERVATION" in (
        seen["prompt"]
    )


def test_presentation_has_ai_opponent_hook_v180():
    source = Path(
        "ghost/examples/ghost_revolution/"
        "presentation.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "def _king_fight_llm_opponent_enabled"
        in source
    )

    assert (
        "def _select_king_fight_llm_opponent_intent"
        in source
    )

    assert (
        "_select_king_fight_llm_opponent_intent("
        in source
    )

    assert (
        "LLM strategy / Ghost state authority"
        in source
    )


def test_ai_opponent_launchers_exist_v180():
    dev = Path(
        "run-llm-ai-dev.sh"
    )

    cinematic = Path(
        "run-llm-ai-cinematic.sh"
    )

    assert dev.is_file()
    assert cinematic.is_file()

    dev_source = dev.read_text(
        encoding="utf-8"
    )

    cinematic_source = cinematic.read_text(
        encoding="utf-8"
    )

    for source in (
        dev_source,
        cinematic_source,
    ):
        assert "GHOST_REAL_LLM=1" in source
        assert "GHOST_LLM_OPPONENT=1" in source
        assert 'GHOST_LLM_STRATEGY_MODEL="gpt-5.6-sol"' in source
        assert 'GHOST_LLM_NARRATION_MODEL="gpt-5.6-terra"' in source
        assert 'GHOST_LLM_AMBIENT_MODEL="gpt-5.6-luna"' in source

    assert (
        "GHOST_LLM_OPPONENT_DEBUG=1"
        in dev_source
    )


def test_ai_public_tell_hides_internal_crown_guard_name_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    game.apply_king_fight_opponent_intent(
        "crown_guard",
        selection_key=(
            observation["selection_key"]
        ),
    )

    public_tell = (
        game.king_fight_opponent_public_tell()
    )

    text = public_tell["tell"].lower()

    assert public_tell["intent_hidden"] is True
    assert public_tell["clarity"] == "ambiguous"
    assert "crown_guard" not in text
    assert "crown guard" not in text
    assert "royal guard" not in text


def test_opponent_observation_contains_resolved_tactical_evidence_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    first_observation = (
        game.king_fight_opponent_observation()
    )

    game.apply_king_fight_opponent_intent(
        "crown_guard",
        selection_key=(
            first_observation[
                "selection_key"
            ]
        ),
    )

    game.resolve_king_fight_move(
        "feint_heavy"
    )

    next_observation = (
        game.king_fight_opponent_observation()
    )

    evidence = next_observation[
        "previous_exchange_evidence"
    ]

    assert evidence["enemy_intent"] == (
        "crown_guard"
    )
    assert evidence["enemy_intent_label"] == (
        "Crown Guard"
    )
    assert evidence["player_move"] == (
        "feint_heavy"
    )
    assert evidence["result"] == (
        "correct_read"
    )
    assert evidence["intent_was_countered"] is True
    assert (
        evidence["damage_suffered_by_enemy"]
        > 0
    )


def test_champion_player_move_reaches_strategy_history_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "elite_knight"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    game.apply_king_fight_opponent_intent(
        "shield_wall",
        selection_key=(
            observation["selection_key"]
        ),
    )

    game.resolve_king_fight_move(
        "feint_heavy"
    )

    next_observation = (
        game.king_fight_opponent_observation()
    )

    assert (
        next_observation[
            "recent_player_moves"
        ][-1]
        == "feint_heavy"
    )

    assert (
        next_observation[
            "previous_exchange_evidence"
        ]["intent_was_countered"]
        is True
    )


def test_opponent_history_reports_same_intent_streak_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    for _index in range(2):
        observation = (
            game.king_fight_opponent_observation()
        )

        game.apply_king_fight_opponent_intent(
            "crown_guard",
            selection_key=(
                observation[
                    "selection_key"
                ]
            ),
        )

        game.resolve_king_fight_move(
            "heavy"
        )

    observation = (
        game.king_fight_opponent_observation()
    )

    assert observation[
        "recent_opponent_intents"
    ] == [
        "crown_guard",
        "crown_guard",
    ]

    assert observation[
        "same_intent_streak"
    ] == 2


def test_opponent_parser_preserves_non_authoritative_reason_v180():
    from ghost.examples.ghost_revolution.opponent_ai import (
        parse_king_fight_opponent_intent,
    )

    parsed = (
        parse_king_fight_opponent_intent(
            (
                '{"intent":"royal_lunge",'
                '"reason":"The player has repeated '
                'heavy attacks."}'
            ),
            (
                "royal_lunge",
                "crown_guard",
                "overextended_recovery",
            ),
        )
    )

    assert parsed["accepted"] is True
    assert parsed["intent"] == "royal_lunge"
    assert parsed["proposal_reason"] == (
        "The player has repeated heavy attacks."
    )


def test_opponent_prompt_explains_countered_tactics_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )
    from ghost.examples.ghost_revolution.opponent_ai import (
        build_king_fight_opponent_intent_prompt,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    prompt = (
        build_king_fight_opponent_intent_prompt(
            observation
        )
    )

    assert "intent_was_countered" in prompt
    assert "same_intent_streak" in prompt
    assert (
        "Do not immediately repeat a countered intent"
        in prompt
    )
    assert (
        '"intent_reason":"brief reason for intent"'
        in prompt
    )

    assert (
        '"reaction_reason":"brief prediction reason"'
        in prompt
    )


def test_ai_opponent_presentation_uses_observed_tell_v180():
    source = Path(
        "ghost/examples/ghost_revolution/"
        "presentation.py"
    ).read_text(
        encoding="utf-8"
    )

    assert "Observed tell" in source
    assert (
        "king_fight_opponent_public_tell"
        in source
    )
    assert "Proposed tactic:" in source
    assert "Selected tactic:" in source


def test_ai_debug_launcher_uses_frontier_model_routing_v180():
    source = Path(
        "run-llm-ai-dev.sh"
    ).read_text(
        encoding="utf-8"
    )

    assert 'GHOST_LLM_STRATEGY_MODEL="gpt-5.6-sol"' in source
    assert 'GHOST_LLM_STRATEGY_REASONING="medium"' in source
    assert 'GHOST_LLM_NARRATION_MODEL="gpt-5.6-terra"' in source
    assert 'GHOST_LLM_NARRATION_REASONING="none"' in source
    assert 'GHOST_LLM_AMBIENT_MODEL="gpt-5.6-luna"' in source
    assert 'GHOST_LLM_AMBIENT_REASONING="none"' in source
    assert "GHOST_LLM_DEBUG=1" in source


def test_observation_exposes_legal_reactions_by_intent_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    assert observation[
        "legal_reaction_plans_by_intent"
    ]["crown_guard"] == [
        "hold_center",
        "read_feint_heavy",
        "read_feint_light",
        "read_feint_bait",
    ]

    assert observation[
        "legal_reaction_plans_by_intent"
    ]["overextended_recovery"] == [
        "genuine_opening",
        "parry_heavy",
        "deflect_light",
        "dodge_heavy",
    ]


def test_ghost_locks_valid_hidden_reaction_plan_v180():
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
            "crown_guard",
            proposed_reaction_plan=(
                "read_feint_heavy"
            ),
            selection_key=(
                observation["selection_key"]
            ),
        )
    )

    assert audit["accepted"] is True

    assert (
        audit["reaction_plan_accepted"]
        is True
    )

    assert audit[
        "selected_reaction_plan"
    ] == "read_feint_heavy"

    assert game.king_fight[
        "llm_opponent_reaction_plan"
    ] == "read_feint_heavy"


def test_illegal_reaction_uses_ghost_fallback_v180():
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
            "crown_guard",
            proposed_reaction_plan=(
                "summon_dragon"
            ),
            selection_key=(
                observation["selection_key"]
            ),
        )
    )

    assert audit["accepted"] is True

    assert (
        audit["reaction_plan_accepted"]
        is False
    )

    assert (
        audit[
            "reaction_plan_fallback_used"
        ]
        is True
    )

    assert audit[
        "selected_reaction_plan"
    ] == "hold_center"


def test_reaction_plan_cannot_reroll_same_exchange_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    first = (
        game.apply_king_fight_opponent_intent(
            "crown_guard",
            proposed_reaction_plan=(
                "read_feint_heavy"
            ),
            selection_key=(
                observation["selection_key"]
            ),
        )
    )

    second = (
        game.apply_king_fight_opponent_intent(
            "crown_guard",
            proposed_reaction_plan=(
                "hold_center"
            ),
            selection_key=(
                observation["selection_key"]
            ),
        )
    )

    assert first == second

    assert second[
        "selected_reaction_plan"
    ] == "read_feint_heavy"


def test_precommitted_read_feint_counters_player_feint_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    game.apply_king_fight_opponent_intent(
        "crown_guard",
        proposed_reaction_plan=(
            "read_feint_heavy"
        ),
        selection_key=(
            observation["selection_key"]
        ),
    )

    packet = game.resolve_king_fight_move(
        "feint_heavy"
    )

    exchange = packet["exchange"]

    assert exchange["result"] == (
        "king_feint_parry"
    )

    assert exchange["king_damage"] == 0
    assert exchange["player_damage"] == 0

    assert (
        exchange["reaction_plan_triggered"]
        is True
    )

    assert packet[
        "forced_response"
    ] is None


def test_hold_center_does_not_magically_counter_feint_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    game.apply_king_fight_opponent_intent(
        "crown_guard",
        proposed_reaction_plan=(
            "hold_center"
        ),
        selection_key=(
            observation["selection_key"]
        ),
    )

    packet = game.resolve_king_fight_move(
        "feint_heavy"
    )

    exchange = packet["exchange"]

    assert exchange["result"] == (
        "correct_read"
    )

    assert exchange["king_damage"] > 0

    assert (
        exchange["reaction_plan_triggered"]
        is False
    )


def test_precommitted_king_parry_counters_heavy_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    game.apply_king_fight_opponent_intent(
        "overextended_recovery",
        proposed_reaction_plan=(
            "parry_heavy"
        ),
        selection_key=(
            observation["selection_key"]
        ),
    )

    packet = game.resolve_king_fight_move(
        "heavy"
    )

    exchange = packet["exchange"]

    assert exchange["result"] == (
        "king_parry"
    )

    assert exchange["king_damage"] == 0

    assert packet[
        "forced_response"
    ] is not None


def test_precommitted_king_deflect_counters_light_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    game.apply_king_fight_opponent_intent(
        "overextended_recovery",
        proposed_reaction_plan=(
            "deflect_light"
        ),
        selection_key=(
            observation["selection_key"]
        ),
    )

    packet = game.resolve_king_fight_move(
        "light"
    )

    exchange = packet["exchange"]

    assert exchange["result"] == (
        "king_deflect"
    )

    assert exchange["king_damage"] == 0


def test_precommitted_king_dodge_avoids_heavy_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    game.apply_king_fight_opponent_intent(
        "overextended_recovery",
        proposed_reaction_plan=(
            "dodge_heavy"
        ),
        selection_key=(
            observation["selection_key"]
        ),
    )

    packet = game.resolve_king_fight_move(
        "heavy"
    )

    exchange = packet["exchange"]

    assert exchange["result"] == (
        "king_dodge"
    )

    assert exchange["king_damage"] == 0
    assert exchange["player_damage"] == 0

    assert packet[
        "forced_response"
    ] is None


def test_wrong_king_prediction_changes_initiative_not_damage_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    game.apply_king_fight_opponent_intent(
        "overextended_recovery",
        proposed_reaction_plan=(
            "parry_heavy"
        ),
        selection_key=(
            observation["selection_key"]
        ),
    )

    packet = game.resolve_king_fight_move(
        "light"
    )

    exchange = packet["exchange"]

    assert exchange["result"] == (
        "correct_read"
    )

    assert exchange[
        "reaction_miss_bonus"
    ] == 0

    assert exchange["king_damage"] == 2
    assert exchange["initiative_event"] == (
        "prediction_missed_player_hit"
    )
    assert exchange["initiative_after"]["state"] == (
        "player_advantage"
    )

    assert (
        exchange["reaction_plan_missed"]
        is True
    )


def test_king_can_break_player_parry_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    game.apply_king_fight_opponent_intent(
        "royal_lunge",
        proposed_reaction_plan=(
            "break_parry"
        ),
        selection_key=(
            observation["selection_key"]
        ),
    )

    packet = game.resolve_king_fight_move(
        "parry"
    )

    exchange = packet["exchange"]

    assert exchange["result"] == (
        "king_breaks_parry"
    )

    assert exchange["player_damage"] == 3

    assert (
        game.king_fight[
            "clean_king_victory_possible"
        ]
        is False
    )


def test_king_can_track_player_dodge_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    game.apply_king_fight_opponent_intent(
        "royal_lunge",
        proposed_reaction_plan=(
            "track_dodge"
        ),
        selection_key=(
            observation["selection_key"]
        ),
    )

    packet = game.resolve_king_fight_move(
        "dodge"
    )

    exchange = packet["exchange"]

    assert exchange["result"] == (
        "king_tracks_dodge"
    )

    assert exchange["player_damage"] == 3


def test_champion_can_precommit_to_read_feint_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "elite_knight"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    game.apply_king_fight_opponent_intent(
        "shield_wall",
        proposed_reaction_plan=(
            "read_feint_heavy"
        ),
        selection_key=(
            observation["selection_key"]
        ),
    )

    packet = game.resolve_king_fight_move(
        "feint_heavy"
    )

    exchange = packet["exchange"]

    assert exchange["result"] == (
        "champion_feint_parry"
    )

    assert exchange[
        "elite_knight_damage"
    ] == 0

    assert exchange["player_damage"] == 0


def test_champion_can_parry_player_heavy_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "elite_knight"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    game.apply_king_fight_opponent_intent(
        "open_recovery",
        proposed_reaction_plan=(
            "parry_heavy"
        ),
        selection_key=(
            observation["selection_key"]
        ),
    )

    packet = game.resolve_king_fight_move(
        "heavy"
    )

    exchange = packet["exchange"]

    assert exchange["result"] == (
        "champion_parry"
    )

    assert exchange[
        "elite_knight_damage"
    ] == 0


def test_champion_can_track_player_dodge_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "elite_knight"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    game.apply_king_fight_opponent_intent(
        "champion_lunge",
        proposed_reaction_plan=(
            "track_dodge"
        ),
        selection_key=(
            observation["selection_key"]
        ),
    )

    packet = game.resolve_king_fight_move(
        "dodge"
    )

    exchange = packet["exchange"]

    assert exchange["result"] == (
        "champion_tracks_dodge"
    )

    assert exchange["player_damage"] == 3

    assert exchange[
        "elite_knight_damage"
    ] == 0


def test_resolved_reaction_reaches_next_observation_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    game.apply_king_fight_opponent_intent(
        "crown_guard",
        proposed_reaction_plan=(
            "read_feint_heavy"
        ),
        proposal_reason=(
            "The player has repeated feints."
        ),
        selection_key=(
            observation["selection_key"]
        ),
    )

    game.resolve_king_fight_move(
        "feint_heavy"
    )

    next_observation = (
        game.king_fight_opponent_observation()
    )

    evidence = next_observation[
        "previous_exchange_evidence"
    ]

    assert evidence[
        "opponent_reaction_plan"
    ] == "read_feint_heavy"

    assert evidence[
        "opponent_reaction_plan_label"
    ] == "Read Feint Heavy"

    assert (
        evidence[
            "reaction_plan_triggered"
        ]
        is True
    )

    assert evidence[
        "opponent_proposal_reason"
    ] == "The player has repeated feints."


def test_opponent_parser_accepts_hidden_reaction_commitment_v180():
    from ghost.examples.ghost_revolution.opponent_ai import (
        parse_king_fight_opponent_intent,
    )

    parsed = (
        parse_king_fight_opponent_intent(
            (
                '{"intent":"crown_guard",'
                '"reason":"The player repeats feints.",'
                '"reaction_plan":"read_feint_heavy"}'
            ),
            (
                "royal_lunge",
                "crown_guard",
                "overextended_recovery",
            ),
            {
                "crown_guard": (
                    "hold_center",
                    "read_feint_heavy",
                ),
            },
        )
    )

    assert parsed["accepted"] is True
    assert parsed["intent"] == "crown_guard"

    assert (
        parsed["reaction_plan_accepted"]
        is True
    )

    assert parsed["reaction_plan"] == (
        "read_feint_heavy"
    )

    assert parsed["reaction_candidate"] == (
        "read_feint_heavy"
    )


def test_opponent_parser_rejects_illegal_reaction_plan_v180():
    from ghost.examples.ghost_revolution.opponent_ai import (
        parse_king_fight_opponent_intent,
    )

    parsed = (
        parse_king_fight_opponent_intent(
            (
                '{"intent":"crown_guard",'
                '"reason":"Try something impossible.",'
                '"reaction_plan":"summon_dragon"}'
            ),
            (
                "royal_lunge",
                "crown_guard",
                "overextended_recovery",
            ),
            {
                "crown_guard": (
                    "hold_center",
                    "read_feint_heavy",
                ),
            },
        )
    )

    assert parsed["accepted"] is True

    assert (
        parsed["reaction_plan_accepted"]
        is False
    )

    assert parsed["reaction_plan"] is None

    assert parsed["reaction_candidate"] == (
        "summon_dragon"
    )

    assert parsed["reaction_plan_reason"] == (
        "illegal_reaction_plan"
    )


def test_opponent_prompt_requires_locked_hidden_reaction_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    from ghost.examples.ghost_revolution.opponent_ai import (
        build_king_fight_opponent_intent_prompt,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    prompt = (
        build_king_fight_opponent_intent_prompt(
            observation
        )
    )

    assert "one hidden reaction_plan" in prompt

    assert (
        "locked before the player's move"
        in prompt
    )

    assert (
        "legal_reaction_plans_by_intent"
        in prompt
    )

    assert (
        '"reaction_plan":"LEGAL_REACTION_PLAN"'
        in prompt
    )

    assert "read_feint_heavy predicts feint_heavy" in prompt
    assert "track_dodge predicts a dodge" in prompt


def test_opponent_bridge_returns_reaction_candidate_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    from ghost.examples.ghost_revolution.llm_bridge import (
        LLMBridgeConfig,
    )

    from ghost.examples.ghost_revolution.opponent_ai import (
        GhostFightOpponentBridge,
    )

    class FakeClient:
        def __call__(
            self,
            prompt,
            *,
            config,
        ):
            assert (
                "legal_reaction_plans_by_intent"
                in prompt
            )

            return (
                '{"intent":"crown_guard",'
                '"reason":"The player repeats feints.",'
                '"reaction_plan":"read_feint_heavy"}'
            )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    bridge = GhostFightOpponentBridge(
        client=FakeClient(),
        config=LLMBridgeConfig(
            model="test-reaction-model"
        ),
    )

    result = (
        bridge
        .generate_king_fight_opponent_intent(
            observation
        )
    )

    assert result["proposed_candidate"] == (
        "crown_guard"
    )

    assert result[
        "proposed_reaction_plan"
    ] == "read_feint_heavy"

    assert result[
        "proposed_reaction_candidate"
    ] == "read_feint_heavy"

    assert (
        result["parser"][
            "reaction_plan_accepted"
        ]
        is True
    )


def test_selector_passes_reaction_candidate_to_ghost_source_v180():
    source = Path(
        "ghost/examples/ghost_revolution/"
        "presentation.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        'proposed_reaction_plan=('
        in source
    )

    assert (
        '"proposed_reaction_candidate"'
        in source
    )

    assert (
        "reaction_parser_reason="
        in source
    )


def test_debug_audit_hides_current_commitment_v180():
    source = Path(
        "ghost/examples/ghost_revolution/"
        "presentation.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "Proposed tactic: hidden until resolution"
        in source
    )

    assert (
        "Selected tactic: hidden until resolution"
        in source
    )

    assert (
        "Current reaction plan: locked by Ghost"
        in source
    )

    assert (
        "Intent reason: hidden until resolution"
        in source
    )

    assert (
        "Reaction reason: hidden until resolution"
        in source
    )

    assert (
        "Model reason: hidden until resolution"
        not in source
    )

    assert (
        "Previous model reason:"
        not in source
    )

    assert "Previous hidden reaction:" in source
    assert "Previous reaction triggered:" in source
    assert "Previous prediction missed:" in source


def test_strategy_output_budget_supports_reaction_json_v180():
    from ghost.examples.ghost_revolution import (
        opponent_ai,
    )

    assert opponent_ai.OPPONENT_OUTPUT_TOKENS == 768

    assert (
        opponent_ai.OPPONENT_HARD_OUTPUT_TOKENS
        == 1024
    )


def test_failed_prediction_is_distinct_from_exposure_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "elite_knight"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    game.apply_king_fight_opponent_intent(
        "champion_lunge",
        proposed_reaction_plan=(
            "break_parry"
        ),
        intent_explanation=(
            "Use direct pressure."
        ),
        reaction_explanation=(
            "The player may parry."
        ),
        selection_key=(
            observation["selection_key"]
        ),
    )

    packet = game.resolve_king_fight_move(
        "feint_heavy"
    )

    exchange = packet["exchange"]

    assert exchange["result"] == (
        "failed_knight_read"
    )

    assert exchange["player_damage"] == 3

    assert (
        exchange["reaction_plan_predictive"]
        is True
    )

    assert (
        exchange["reaction_plan_matched"]
        is False
    )

    assert (
        exchange["reaction_plan_missed"]
        is True
    )

    assert (
        exchange["reaction_miss_exposed_enemy"]
        is False
    )

    assert exchange[
        "reaction_miss_bonus"
    ] == 0

    assert exchange[
        "resolution_source"
    ] == "base_intent"

    assert exchange[
        "opponent_intent_reason"
    ] == "Use direct pressure."

    assert exchange[
        "opponent_reaction_reason"
    ] == "The player may parry."


def test_non_predictive_reaction_is_not_a_prediction_miss_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    game.apply_king_fight_opponent_intent(
        "crown_guard",
        proposed_reaction_plan=(
            "hold_center"
        ),
        selection_key=(
            observation["selection_key"]
        ),
    )

    packet = game.resolve_king_fight_move(
        "feint_heavy"
    )

    exchange = packet["exchange"]

    assert (
        exchange["reaction_plan_predictive"]
        is False
    )

    assert (
        exchange["reaction_plan_matched"]
        is None
    )

    assert (
        exchange["reaction_plan_missed"]
        is None
    )

    assert exchange[
        "resolution_source"
    ] == "player_counter"


def test_matched_reaction_owns_resolution_source_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "elite_knight"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    game.apply_king_fight_opponent_intent(
        "champion_lunge",
        proposed_reaction_plan=(
            "track_dodge"
        ),
        selection_key=(
            observation["selection_key"]
        ),
    )

    packet = game.resolve_king_fight_move(
        "dodge"
    )

    exchange = packet["exchange"]

    assert (
        exchange["reaction_plan_matched"]
        is True
    )

    assert (
        exchange["reaction_plan_missed"]
        is False
    )

    assert exchange[
        "resolution_source"
    ] == "reaction_plan"


def test_observation_reports_prediction_and_resolution_truth_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "elite_knight"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    game.apply_king_fight_opponent_intent(
        "champion_lunge",
        proposed_reaction_plan=(
            "break_parry"
        ),
        selection_key=(
            observation["selection_key"]
        ),
    )

    game.resolve_king_fight_move(
        "feint_heavy"
    )

    next_observation = (
        game.king_fight_opponent_observation()
    )

    evidence = next_observation[
        "previous_exchange_evidence"
    ]

    assert (
        evidence["reaction_plan_predictive"]
        is True
    )

    assert (
        evidence["reaction_plan_matched"]
        is False
    )

    assert (
        evidence["reaction_plan_missed"]
        is True
    )

    assert (
        evidence[
            "reaction_miss_exposed_enemy"
        ]
        is False
    )

    assert evidence[
        "resolution_source"
    ] == "base_intent"


def test_split_strategist_reasons_round_trip_v180():
    from ghost.examples.ghost_revolution.opponent_ai import (
        parse_king_fight_opponent_intent,
    )

    parsed = (
        parse_king_fight_opponent_intent(
            (
                '{"intent":"champion_lunge",'
                '"intent_reason":"Pressure the player.",'
                '"reaction_plan":"break_parry",'
                '"reaction_reason":"The player may parry."}'
            ),
            (
                "shield_wall",
                "champion_lunge",
            ),
            {
                "champion_lunge": (
                    "commit_attack",
                    "break_parry",
                ),
            },
        )
    )

    assert parsed["accepted"] is True

    assert parsed["intent_reason"] == (
        "Pressure the player."
    )

    assert parsed["reaction_reason"] == (
        "The player may parry."
    )

    assert parsed["proposal_reason"] == (
        "Pressure the player."
    )


def test_strategy_prompt_requires_two_reasons_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    from ghost.examples.ghost_revolution.opponent_ai import (
        build_king_fight_opponent_intent_prompt,
    )

    game, _packet = create_fight_stage_shortcut(
        "elite_knight"
    )

    prompt = (
        build_king_fight_opponent_intent_prompt(
            game.king_fight_opponent_observation()
        )
    )

    assert '"intent_reason":' in prompt
    assert '"reaction_reason":' in prompt

    assert (
        "reaction_reason must explain"
        in prompt
    )

    assert (
        "prediction miss and an exposure bonus "
        "are separate facts"
        in prompt
    )


def test_opponent_bridge_returns_split_reasons_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    from ghost.examples.ghost_revolution.llm_bridge import (
        LLMBridgeConfig,
    )

    from ghost.examples.ghost_revolution.opponent_ai import (
        GhostFightOpponentBridge,
    )

    class FakeClient:
        def __call__(
            self,
            prompt,
            *,
            config,
        ):
            return (
                '{"intent":"champion_lunge",'
                '"intent_reason":"Apply pressure.",'
                '"reaction_plan":"break_parry",'
                '"reaction_reason":"A parry is likely."}'
            )

    game, _packet = create_fight_stage_shortcut(
        "elite_knight"
    )

    bridge = GhostFightOpponentBridge(
        client=FakeClient(),
        config=LLMBridgeConfig(
            model="split-reason-test"
        ),
    )

    result = (
        bridge
        .generate_king_fight_opponent_intent(
            game.king_fight_opponent_observation()
        )
    )

    assert result["intent_reason"] == (
        "Apply pressure."
    )

    assert result["reaction_reason"] == (
        "A parry is likely."
    )


def test_debug_audit_reports_resolution_truth_v180():
    source = Path(
        "ghost/examples/ghost_revolution/"
        "presentation.py"
    ).read_text(
        encoding="utf-8"
    )

    assert "Previous reaction predictive:" in source
    assert "Previous reaction matched:" in source
    assert "Previous prediction missed:" in source
    assert "Previous miss exposed enemy:" in source
    assert "Previous resolution source:" in source
    assert "Previous intent reason:" in source
    assert "Previous reaction reason:" in source


def test_prompt_distinguishes_predictive_and_nonpredictive_reasons_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    from ghost.examples.ghost_revolution.opponent_ai import (
        build_king_fight_opponent_intent_prompt,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    prompt = (
        build_king_fight_opponent_intent_prompt(
            game.king_fight_opponent_observation()
        )
    )

    assert (
        "For predictive reaction plans"
        in prompt
    )

    assert (
        "For hold_center, genuine_opening, or "
        "commit_attack"
        in prompt
    )

    assert (
        "Do not pretend that a nonpredictive "
        "reaction predicted a particular move"
        in prompt
    )


def test_prompt_discourages_repeating_missed_prediction_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    from ghost.examples.ghost_revolution.opponent_ai import (
        build_king_fight_opponent_intent_prompt,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    prompt = (
        build_king_fight_opponent_intent_prompt(
            game.king_fight_opponent_observation()
        )
    )

    assert (
        "previous predictive reaction missed"
        in prompt
    )

    assert (
        "new concrete evidence"
        in prompt
    )

    assert (
        "Mere speculation that the player may "
        "switch moves is not concrete evidence"
        in prompt
    )


def test_nonpredictive_audit_uses_not_applicable_v180():
    source = Path(
        "ghost/examples/ghost_revolution/"
        "presentation.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        'triggered_display = "Not applicable"'
        in source
    )

    assert (
        'exposed_display = "Not applicable"'
        in source
    )


def test_layered_feint_structured_schema_requires_feint_prediction_v180():
    from ghost.examples.ghost_revolution.opponent_ai import (
        OPPONENT_STRUCTURED_OUTPUT_SCHEMA,
    )

    properties = OPPONENT_STRUCTURED_OUTPUT_SCHEMA["properties"]
    required = OPPONENT_STRUCTURED_OUTPUT_SCHEMA["required"]

    assert "feint_prediction" in properties
    assert set(required) == set(properties)
    assert properties["feint_prediction"]["enum"] == [
        "feint_heavy",
        "feint_light",
        "feint_bait",
        "none",
    ]


def test_layered_feint_prompt_requires_feint_prediction_field_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )
    from ghost.examples.ghost_revolution.opponent_ai import (
        build_king_fight_opponent_intent_prompt,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )
    prompt = build_king_fight_opponent_intent_prompt(
        game.king_fight_opponent_observation()
    )

    assert "feint_prediction must always be present" in prompt
    assert "\"feint_prediction\":" in prompt
    assert "feint_heavy|feint_light|feint_bait|none" in prompt


def test_layered_feint_audit_records_exact_feint_prediction_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )
    observation = game.king_fight_opponent_observation()

    audit = game.apply_king_fight_opponent_intent(
        "crown_guard",
        proposed_reaction_plan="read_feint_heavy",
        proposed_feint_prediction="feint_heavy",
        selection_key=observation["selection_key"],
    )

    assert audit["proposed_feint_prediction"] == "feint_heavy"
    assert audit["expected_feint_prediction"] == "feint_heavy"
    assert audit["feint_prediction_accepted"] is True
    assert audit["feint_prediction_reason"] == "accepted"
