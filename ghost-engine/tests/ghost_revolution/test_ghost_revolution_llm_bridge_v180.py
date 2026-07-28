from pathlib import Path

from ghost.examples.ghost_revolution.dev_shortcuts import (
    create_endgame_shortcut,
)
from ghost.examples.ghost_revolution.llm_bridge import (
    GhostRevolutionLLMBridge,
    LLMBridgeConfig,
    NullLLMClient,
    build_crown_loop_prompt,
    estimate_llm_cost,
    rough_token_count,
)


def test_crown_loop_prompt_uses_ghost_state_v180():
    game, _packet = create_endgame_shortcut("crown_execute")

    packet = game.crown_npc_interaction(
        "Ashfield",
        "public_event",
        "town_elder",
        "open_dialogue",
    )

    prompt = build_crown_loop_prompt(packet)

    assert "Ghost owns the deterministic world state" in prompt
    assert "Ashfield Elder" in prompt
    assert "Role: elder" in prompt
    assert "Reaction:" in prompt
    assert "Crown fate: execute_king" in prompt
    assert "Weapon caches:" in prompt
    assert "Do not treat spoken claims as automatic truth" in prompt


def test_cost_estimate_is_deterministic_v180():
    prompt = "hello world"

    first = estimate_llm_cost(
        prompt,
        expected_output_tokens=100,
        config=LLMBridgeConfig(
            input_cost_per_million_tokens=1.0,
            output_cost_per_million_tokens=2.0,
        ),
    )

    second = estimate_llm_cost(
        prompt,
        expected_output_tokens=100,
        config=LLMBridgeConfig(
            input_cost_per_million_tokens=1.0,
            output_cost_per_million_tokens=2.0,
        ),
    )

    assert first == second
    assert first["input_tokens_estimate"] == rough_token_count(prompt)
    assert first["total_cost_estimate"] > 0


def test_null_bridge_does_not_call_external_provider_v180():
    game, _packet = create_endgame_shortcut("crown_jail")

    packet = game.crown_npc_interaction(
        "Millcross",
        "public_event",
        "former_guard",
        "open_dialogue",
    )

    bridge = GhostRevolutionLLMBridge(
        client=NullLLMClient(),
    )

    result = bridge.generate_crown_dialogue(packet)

    assert result["provider_called"] is False
    assert "[LLM disabled]" in result["text"]
    assert "Millcross Former Guard" in result["prompt"]
    assert "cost_estimate" in result


def test_custom_client_receives_prompt_v180():
    seen = {}

    def fake_client(prompt, *, config):
        seen["prompt"] = prompt
        seen["model"] = config.model
        return "custom npc response"

    game, _packet = create_endgame_shortcut("crown_jail")

    packet = game.crown_npc_interaction(
        "Crownmarket",
        "goods_stall",
        "stall_keeper",
        "open_dialogue",
    )

    bridge = GhostRevolutionLLMBridge(
        client=fake_client,
        config=LLMBridgeConfig(model="test-model"),
    )

    result = bridge.generate_crown_dialogue(packet)

    assert result["provider_called"] is True
    assert result["text"] == "custom npc response"
    assert seen["model"] == "test-model"
    assert "Crownmarket Stall Keeper" in seen["prompt"]


def test_output_token_limit_is_capped_v180():
    from ghost.examples.ghost_revolution.llm_bridge import (
        LLMBridgeConfig,
        effective_output_token_limit,
        estimate_llm_cost,
    )

    config = LLMBridgeConfig(
        max_output_tokens=999,
        hard_max_output_tokens=300,
    )

    assert effective_output_token_limit(config) == 300

    estimate = estimate_llm_cost(
        "hello",
        expected_output_tokens=999,
        config=config,
    )

    assert estimate["output_tokens_estimate"] == 300
    assert estimate["requested_output_tokens"] == 999
    assert estimate["cost_warning"]


def test_openai_responses_client_requires_explicit_env_v180(
    monkeypatch,
):
    from ghost.examples.ghost_revolution.llm_bridge import (
        LLMBridgeConfig,
        OpenAIResponsesClient,
    )

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    client = OpenAIResponsesClient()

    try:
        client(
            "hello",
            config=LLMBridgeConfig(),
        )
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError(
            "OpenAIResponsesClient should refuse to run "
            "without OPENAI_API_KEY."
        )

    assert "OPENAI_API_KEY is not set" in message
    assert "off by default" in message


def test_openai_model_can_be_read_from_environment_v180(
    monkeypatch,
):
    from ghost.examples.ghost_revolution.llm_bridge import (
        LLMBridgeConfig,
        config_from_environment,
    )

    monkeypatch.setenv(
        "OPENAI_MODEL",
        "test-env-model",
    )

    config = config_from_environment(
        base=LLMBridgeConfig(model="base-model"),
    )

    assert config.model == "test-env-model"


def test_openai_client_is_not_default_v180():
    from ghost.examples.ghost_revolution.llm_bridge import (
        GhostRevolutionLLMBridge,
        NullLLMClient,
    )

    bridge = GhostRevolutionLLMBridge()

    assert isinstance(bridge.client, NullLLMClient)


def test_openai_responses_client_uses_httpx_not_sdk_v180():
    source = Path(
        "ghost/examples/ghost_revolution/llm_bridge.py"
    ).read_text(
        encoding="utf-8",
    )

    assert "import httpx" in source
    assert "api.openai.com/v1/responses" in source
    assert "from openai import OpenAI" not in source


def test_crown_loop_prompt_contains_hallucination_guardrails_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_endgame_shortcut,
    )
    from ghost.examples.ghost_revolution.llm_bridge import (
        build_crown_loop_prompt,
    )

    game, _packet = create_endgame_shortcut("crown_execute")

    packet = game.crown_npc_interaction(
        "Ashfield",
        "public_event",
        "town_elder",
        "open_dialogue",
    )

    prompt = build_crown_loop_prompt(packet)

    assert "Town memory:" in prompt
    assert "No confirmed town memories provided." in prompt
    assert "Do not invent past town events." in prompt
    assert "NPC known history with player:" in prompt
    assert "No direct prior conversation recorded." in prompt
    assert "NPC knowledge limits:" in prompt
    assert "NPC does not know exact scores or hidden counters." in prompt
    assert "must not mention fear score" in prompt
    assert "must not know the exact number of weapon caches" in prompt
    assert "Output format:" in prompt
    assert "Return only the NPC dialogue line." in prompt
    assert "Maximum 60 words." in prompt


def test_crown_loop_prompt_explains_uncertainty_reaction_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_endgame_shortcut,
    )
    from ghost.examples.ghost_revolution.llm_bridge import (
        build_crown_loop_prompt,
    )

    game, _packet = create_endgame_shortcut("crown_execute")

    packet = game.crown_npc_interaction(
        "Ashfield",
        "public_event",
        "town_elder",
        "open_dialogue",
    )

    prompt = build_crown_loop_prompt(packet)

    assert "Reaction meaning:" in prompt
    assert "Cautious respect mixed with unresolved fear" in prompt
    assert "should not pledge full loyalty yet" in prompt
    assert "should not openly rebel" in prompt


def test_crown_loop_prompt_uses_provided_memory_without_inventing_v180():
    from copy import deepcopy

    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_endgame_shortcut,
    )
    from ghost.examples.ghost_revolution.llm_bridge import (
        build_crown_loop_prompt,
    )

    game, _packet = create_endgame_shortcut("crown_execute")

    packet = game.crown_npc_interaction(
        "Ashfield",
        "public_event",
        "town_elder",
        "open_dialogue",
    )

    packet = deepcopy(packet)
    packet["llm_context"]["town_memory"] = [
        "The market remembers the player distributing food.",
        "No confirmed civilian massacre.",
    ]
    packet["llm_context"]["npc_history"] = [
        "The elder has heard public reports but has not met the player directly.",
    ]

    prompt = build_crown_loop_prompt(packet)

    assert "The market remembers the player distributing food." in prompt
    assert "No confirmed civilian massacre." in prompt
    assert "has not met the player directly" in prompt
    assert "No confirmed town memories provided." not in prompt
    assert "No direct prior conversation recorded." not in prompt


def test_deterministic_crown_mock_client_returns_dialogue_line_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_endgame_shortcut,
    )
    from ghost.examples.ghost_revolution.llm_bridge import (
        DeterministicCrownMockClient,
        LLMBridgeConfig,
        build_crown_loop_prompt,
    )

    game, _packet = create_endgame_shortcut("crown_execute")

    packet = game.crown_npc_interaction(
        "Ashfield",
        "public_event",
        "town_elder",
        "open_dialogue",
    )

    prompt = build_crown_loop_prompt(packet)
    client = DeterministicCrownMockClient()
    config = LLMBridgeConfig(max_output_tokens=120)

    first = client(prompt, config=config)
    second = client(prompt, config=config)

    assert first == second
    assert first
    assert len(first.split()) <= 60
    assert not first.startswith("Ashfield Elder:")
    assert "fear score" not in first.lower()
    assert "mercy score" not in first.lower()
    assert "king_control" not in first.lower()


def test_deterministic_crown_mock_client_has_no_provider_dependency_v180():
    from ghost.examples.ghost_revolution.llm_bridge import (
        DeterministicCrownMockClient,
        LLMBridgeConfig,
    )

    client = DeterministicCrownMockClient()

    text = client(
        "- Reaction: uncertainty\n"
        "- Crown fate: execute_king\n"
        "- Rule profile: uncertain\n",
        config=LLMBridgeConfig(max_output_tokens=120),
    )

    assert "old king" in text
    assert "execution" in text
    assert "OpenAI" not in text
    assert "provider" not in text.lower()


def test_crown_packet_converts_to_generic_llm_adapter_stance_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_endgame_shortcut,
    )
    from ghost.examples.ghost_revolution.llm_bridge import (
        build_crown_stance_packet,
    )

    game, _packet = create_endgame_shortcut("crown_execute")

    packet = game.crown_npc_interaction(
        "Ashfield",
        "public_event",
        "town_elder",
        "open_dialogue",
    )

    stance = build_crown_stance_packet(packet)

    assert stance["scene_moment"] == "crown_uncertain_execution"
    assert stance["state_owner"] == "Ghost"
    assert stance["llm_role"] == "voice_renderer_only"
    assert stance["facts"]["town"] == "Ashfield"
    assert stance["facts"]["npc_role"] == "elder"
    assert stance["facts"]["crown_fate"] == "execute_king"
    assert stance["limits"]["dialogue_only"] is True
    assert stance["limits"]["no_invented_history"] is True
    assert "exact weapon caches" in stance["limits"]["may_not_mention"]


def test_crown_voice_contract_uses_existing_llm_adapter_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_endgame_shortcut,
    )
    from ghost.examples.ghost_revolution.llm_bridge import (
        build_crown_voice_contract_prompt,
    )

    game, _packet = create_endgame_shortcut("crown_execute")

    packet = game.crown_npc_interaction(
        "Ashfield",
        "public_event",
        "town_elder",
        "open_dialogue",
    )

    prompt = build_crown_voice_contract_prompt(packet)

    assert "SYSTEM: You are an NPC voice renderer." in prompt
    assert "SYSTEM: You do not decide world state." in prompt
    assert "SYSTEM: You do not invent facts." in prompt
    assert "SYSTEM: You must obey the STANCE_PACKET." in prompt
    assert "crown_uncertain_execution" in prompt
    assert "voice_renderer_only" in prompt


def test_crown_adapter_fallback_returns_safe_dialogue_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_endgame_shortcut,
    )
    from ghost.examples.ghost_revolution.llm_bridge import (
        generate_crown_adapter_fallback_dialogue,
    )

    game, _packet = create_endgame_shortcut("crown_execute")

    packet = game.crown_npc_interaction(
        "Ashfield",
        "public_event",
        "town_elder",
        "open_dialogue",
    )

    result = generate_crown_adapter_fallback_dialogue(packet)

    text = result["text"]

    assert result["provider_called"] is False
    assert result["provider"] == "ghost.llm_adapter.fallback_from_stance"
    assert "old king" in text
    assert "execution" in text
    assert len(text.split()) <= 60
    assert "fear score" not in text.lower()
    assert "mercy score" not in text.lower()
    assert "king_control" not in text.lower()
    assert not text.startswith("Ashfield Elder:")


def test_try_crown_dialogue_script_exists_and_imports_bridge_v180():
    from pathlib import Path

    script = Path("scripts/try_crown_dialogue.py")

    assert script.is_file()

    source = script.read_text(encoding="utf-8")

    assert "GhostRevolutionLLMBridge" in source
    assert "OpenAIResponsesClient" in source
    assert "generate_crown_adapter_fallback_dialogue" in source
    assert "create_endgame_shortcut" in source
    assert "GHOST_REAL_LLM" in source


def test_try_crown_dialogue_script_uses_real_bridge_constructor_v180():
    from pathlib import Path

    script = Path("scripts/try_crown_dialogue.py")

    assert script.is_file()

    source = script.read_text(encoding="utf-8")

    assert "config_from_environment" in source
    assert "OpenAIResponsesClient()" in source
    assert "OpenAIResponsesClient.from_environment()" not in source
    assert "OpenAIResponsesClient(api_key=api_key)" not in source
    assert "GhostRevolutionLLMBridge(" in source


def test_try_crown_dialogue_script_prints_request_estimate_v180():
    from pathlib import Path

    script = Path("scripts/try_crown_dialogue.py")

    assert script.is_file()

    source = script.read_text(encoding="utf-8")

    assert "build_crown_voice_contract_prompt" in source
    assert "estimate_llm_cost" in source
    assert "=== REQUEST ESTIMATE ===" in source
    assert "max_output_tokens" in source
    assert "pricing_note" in source
    assert "result.get('model')" not in source
    assert "result.get('total_cost_estimate')" not in source


def test_real_crown_dialogue_path_uses_voice_contract_prompt_v180():
    import inspect

    from ghost.examples.ghost_revolution.llm_bridge import (
        GhostRevolutionLLMBridge,
    )

    prepare_source = inspect.getsource(
        GhostRevolutionLLMBridge.prepare_crown_dialogue
    )

    generate_source = inspect.getsource(
        GhostRevolutionLLMBridge.generate_crown_dialogue
    )

    assert "build_crown_voice_contract_prompt(packet)" in prepare_source
    assert "build_crown_loop_prompt(packet)" not in prepare_source
    assert "self.prepare_crown_dialogue(packet)" in generate_source


def test_king_fight_voice_contract_prompt_uses_root_llm_adapter_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )
    from ghost.examples.ghost_revolution.llm_bridge import (
        build_king_fight_stance_packet,
        build_king_fight_voice_contract_prompt,
    )

    game, _packet = create_fight_stage_shortcut("king_phase_two")
    packet = game.resolve_king_fight_move("heavy")

    stance = build_king_fight_stance_packet(packet)
    prompt = build_king_fight_voice_contract_prompt(packet)

    assert stance["state_owner"] == "Ghost"
    assert stance["llm_role"] == "fight_narrator_only"
    assert "STANCE_PACKET:" in prompt
    assert "Ghost Fight Narrator" in prompt
    assert "You do not decide world state" in prompt


def test_king_fight_bridge_generates_sanitized_narration_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )
    from ghost.examples.ghost_revolution.llm_bridge import (
        GhostRevolutionLLMBridge,
    )

    class FakeClient:
        def __call__(self, prompt, *, config):
            assert "STANCE_PACKET:" in prompt
            return "Narrator: The king recoils through the smoke."

    game, _packet = create_fight_stage_shortcut("king_phase_two")
    packet = game.resolve_king_fight_move("heavy")

    bridge = GhostRevolutionLLMBridge(client=FakeClient())
    result = bridge.generate_king_fight_narration(packet)

    assert result["provider_called"] is True
    assert result["text"] == "The king recoils through the smoke."
    assert result["parser"]["accepted"] is True


def test_king_fight_bridge_fallback_blocks_hidden_counter_leaks_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )
    from ghost.examples.ghost_revolution.llm_bridge import (
        GhostRevolutionLLMBridge,
        generate_king_fight_adapter_fallback_narration,
    )

    class BadClient:
        def __call__(self, prompt, *, config):
            return "The hidden counter says fear score 99."

    game, _packet = create_fight_stage_shortcut("king_phase_two")
    packet = game.resolve_king_fight_move("heavy")

    fallback = generate_king_fight_adapter_fallback_narration(packet)
    bridge = GhostRevolutionLLMBridge(client=BadClient())
    result = bridge.generate_king_fight_narration(packet)

    assert result["text"] == fallback["text"]
    assert result["parser"]["used_fallback"] is True


def test_king_fight_menu_has_llm_narration_hook_v180():
    from pathlib import Path

    source = Path(
        "ghost/examples/ghost_revolution/presentation.py"
    ).read_text(encoding="utf-8")

    assert "_print_king_fight_llm_narration(packet)" in source
    assert "REAL LLM FIGHT BEAT" in source
    assert "GHOST_REAL_LLM" in source


def test_parse_voice_response_strips_narrator_label_for_fight_v180():
    from ghost.llm_adapter import parse_voice_response

    parsed = parse_voice_response(
        "Narrator: The king recoils through the smoke.",
        fallback_text="fallback",
        max_words=75,
    )

    assert parsed["text"] == "The king recoils through the smoke."
    assert parsed["accepted"] is True


def test_king_fight_llm_failure_falls_back_safely_v180():
    from pathlib import Path

    source = Path(
        "ghost/examples/ghost_revolution/presentation.py"
    ).read_text(encoding="utf-8")

    assert "LLM FAILED - SAFE FIGHT BEAT" in source
    assert "Real provider failed safely." in source
    assert "except Exception as exc" in source
    assert "generate_king_fight_adapter_fallback_narration" in source


def test_king_fight_menu_accepts_q_quit_back_v180():
    from pathlib import Path

    source = Path(
        "ghost/examples/ghost_revolution/presentation.py"
    ).read_text(encoding="utf-8")

    assert 'choice in ("q", "quit", "back")' in source
    assert "Leaving the fight panel." in source


def test_king_fight_prompt_hides_next_tell_from_narrator_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )
    from ghost.examples.ghost_revolution.llm_bridge import (
        build_king_fight_voice_contract_prompt,
    )

    game, _packet = create_fight_stage_shortcut("king_phase_two")
    packet = game.resolve_king_fight_move("heavy")

    prompt = build_king_fight_voice_contract_prompt(packet)

    assert "next tell" in prompt.lower()
    assert "facts.tell" in prompt
    assert packet["tell"] not in prompt


def test_king_fight_fallback_does_not_duplicate_ui_tell_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )
    from ghost.examples.ghost_revolution.llm_bridge import (
        generate_king_fight_adapter_fallback_narration,
    )

    game, _packet = create_fight_stage_shortcut("king_phase_two")
    packet = game.resolve_king_fight_move("heavy")

    result = generate_king_fight_adapter_fallback_narration(packet)

    assert "Next tell:" not in result["text"]
    assert packet["tell"] not in result["text"]


def test_king_fight_panel_uses_fight_beat_language_v180():
    from pathlib import Path

    source = Path(
        "ghost/examples/ghost_revolution/presentation.py"
    ).read_text(encoding="utf-8")

    assert "REAL LLM FIGHT BEAT" in source
    assert "ADAPTER FIGHT BEAT" in source
    assert "REAL LLM FIGHT NARRATION" not in source


def test_king_fight_llm_mode_suppresses_raw_packet_output_v180():
    from pathlib import Path

    source = Path(
        "ghost/examples/ghost_revolution/presentation.py"
    ).read_text(encoding="utf-8")

    assert "def _king_fight_llm_enabled()" in source
    assert "if _king_fight_llm_enabled():" in source
    assert "_print_king_fight_llm_narration(packet)" in source
    assert "else:\n            print(message)" in source


def test_king_fight_llm_metadata_requires_debug_flag_v180():
    from pathlib import Path

    source = Path(
        "ghost/examples/ghost_revolution/presentation.py"
    ).read_text(encoding="utf-8")

    assert "GHOST_LLM_DEBUG" in source
    assert 'lines = [\n                result.get("text", ""),\n            ]' in source
    assert 'lines = [\n            result.get("text", ""),\n        ]' in source


def test_king_fight_prompt_is_not_lazy_placeholder_style_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )
    from ghost.examples.ghost_revolution.llm_bridge import (
        build_king_fight_voice_contract_prompt,
    )

    game, _packet = create_fight_stage_shortcut("king_phase_two")
    packet = game.resolve_king_fight_move("heavy")
    prompt = build_king_fight_voice_contract_prompt(packet)

    assert "vivid, cinematic" in prompt
    assert "Do not sound like a debug log" in prompt
    assert "Do not merely copy" in prompt
    assert "facts.ending" in prompt


def test_king_fight_stance_includes_final_ending_text_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )
    from ghost.examples.ghost_revolution.llm_bridge import (
        build_king_fight_stance_packet,
    )

    game, _packet = create_fight_stage_shortcut("king_phase_two")

    fight = game.king_fight
    fight["king_has_hit_player"] = True
    fight["clean_king_victory_possible"] = False
    fight["king_health"] = 0

    packet = game._finish_uncertain_king_victory()
    stance = build_king_fight_stance_packet(packet)

    assert stance["facts"]["ending"] == packet["ending"]
    assert stance["scene_moment"] == "king_fight_uncertain_victory"


def test_king_fight_prompt_contains_stronger_voice_contract_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )
    from ghost.examples.ghost_revolution.llm_bridge import (
        build_king_fight_voice_contract_prompt,
    )

    game, _packet = create_fight_stage_shortcut("king_phase_two")
    packet = game.resolve_king_fight_move("heavy")

    prompt = build_king_fight_voice_contract_prompt(packet)

    assert "vivid, cinematic" in prompt
    assert "Do not sound like a debug log" in prompt
    assert "Do not merely copy" in prompt
    assert "next tell" in prompt.lower()
    assert "facts.ending" in prompt
    assert packet["tell"] not in prompt


def test_king_fight_prompt_uses_active_stronger_contract_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )
    from ghost.examples.ghost_revolution.llm_bridge import (
        KING_FIGHT_VOICE_CONTRACT,
        build_king_fight_voice_contract_prompt,
    )

    game, _packet = create_fight_stage_shortcut("king_phase_two")
    packet = game.resolve_king_fight_move("heavy")

    source_contract = "\n".join(KING_FIGHT_VOICE_CONTRACT)
    prompt = build_king_fight_voice_contract_prompt(packet)

    assert "vivid, cinematic" in source_contract
    assert "Do not merely copy" in source_contract
    assert "next tell" in source_contract.lower()

    assert "vivid, cinematic" in prompt
    assert "Do not merely copy" in prompt
    assert "next tell" in prompt.lower()
    assert packet["tell"] not in prompt


def test_king_fight_prompt_contract_is_inside_stance_packet_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )
    from ghost.examples.ghost_revolution.llm_bridge import (
        build_king_fight_stance_packet,
        build_king_fight_voice_contract_prompt,
    )

    game, _packet = create_fight_stage_shortcut("king_phase_two")
    packet = game.resolve_king_fight_move("heavy")

    stance = build_king_fight_stance_packet(packet)
    prompt = build_king_fight_voice_contract_prompt(packet)

    contract = stance["facts"]["voice_contract"]

    assert stance["limits"]["must_follow_voice_contract"] is True
    assert any("vivid, cinematic" in line for line in contract)
    assert any("next tell" in line.lower() for line in contract)
    assert any("Do not merely copy" in line for line in contract)

    assert "voice_contract" in prompt
    assert "vivid, cinematic" in prompt
    assert "next tell" in prompt.lower()
    assert "Do not merely copy" in prompt
    assert packet["tell"] not in prompt


def test_king_fight_scene_beat_prompt_uses_state_contract_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )
    from ghost.examples.ghost_revolution.llm_bridge import (
        build_king_fight_scene_stance_packet,
        build_king_fight_scene_voice_contract_prompt,
    )

    game, _packet = create_fight_stage_shortcut("king_phase_two")
    packet = game.king_fight_status()
    packet["kingdom_stats"] = game._final_kingdom_stats()

    stance = build_king_fight_scene_stance_packet(
        packet,
        "phase_two_start",
    )
    prompt = build_king_fight_scene_voice_contract_prompt(
        packet,
        "phase_two_start",
    )

    assert stance["facts"]["scene_reason"] == "phase_two_start"
    assert stance["limits"]["scene_transition_only"] is True
    assert stance["limits"]["must_follow_scene_contract"] is True
    assert stance["llm_role"] == "fight_scene_narrator_only"
    assert "scene_contract" in prompt
    assert "vivid cinematic scene-transition beat" in prompt
    assert "phase_two_start" in prompt
    assert "kingdom_stats" in prompt


def test_king_fight_scene_fallbacks_cover_major_moments_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )
    from ghost.examples.ghost_revolution.llm_bridge import (
        generate_king_fight_adapter_fallback_scene_beat,
    )

    game, _packet = create_fight_stage_shortcut("king_phase_two")
    packet = game.king_fight_status()
    packet["kingdom_stats"] = game._final_kingdom_stats()

    phase_two = generate_king_fight_adapter_fallback_scene_beat(
        packet,
        "phase_two_start",
    )

    assert "king" in phase_two["text"].lower()
    assert phase_two["reason"] == "phase_two_start"
    assert phase_two["provider_called"] is False

    final_packet = {
        "outcome": "player_killed_by_king",
        "ending": "The king kills you in the burning castle.",
    }

    final = generate_king_fight_adapter_fallback_scene_beat(
        final_packet,
        "fight_end",
    )

    assert final["text"] == final_packet["ending"]


def test_king_fight_menu_has_scene_beat_hooks_v180():
    from pathlib import Path

    source = Path(
        "ghost/examples/ghost_revolution/presentation.py"
    ).read_text(encoding="utf-8")

    assert "def _king_fight_scene_reason_for_stage" in source
    assert "phase_one_start" in source
    assert "elite_knight_start" in source
    assert "phase_two_start" in source
    assert "_print_king_fight_scene_beat(" in source
    assert '_print_king_fight_scene_beat(packet, "fight_end")' in source
    assert "REAL LLM SCENE BEAT" in source
    assert "ADAPTER SCENE BEAT" in source


def test_king_fight_scene_packet_includes_player_profile_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )
    from ghost.examples.ghost_revolution.presentation import (
        _king_fight_player_profile,
        _king_fight_scene_packet_from_status,
    )

    game, _packet = create_fight_stage_shortcut("prepared_king")
    status = game.king_fight_status()

    profile = _king_fight_player_profile(game)
    packet = _king_fight_scene_packet_from_status(
        game,
        status,
        "phase_one_start",
    )

    assert "strength" in profile
    assert "followers" in profile
    assert "armor" in profile
    assert "guards_defeated" in profile
    assert packet["player_profile"] == profile


def test_king_fight_scene_stance_carries_player_profile_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )
    from ghost.examples.ghost_revolution.llm_bridge import (
        build_king_fight_scene_stance_packet,
    )
    from ghost.examples.ghost_revolution.presentation import (
        _king_fight_scene_packet_from_status,
    )

    game, _packet = create_fight_stage_shortcut("prepared_king")
    status = game.king_fight_status()
    packet = _king_fight_scene_packet_from_status(
        game,
        status,
        "phase_one_start",
    )

    stance = build_king_fight_scene_stance_packet(
        packet,
        "phase_one_start",
    )

    assert "player_profile" in stance["facts"]
    assert "strength" in stance["facts"]["player_profile"]
    assert "player combat profile" in "\\n".join(
        stance["facts"]["scene_contract"]
    )


def test_dev_shortcuts_hides_initial_king_packet_in_llm_mode_v180():
    from pathlib import Path

    source = Path(
        "ghost/examples/ghost_revolution/dev_shortcuts.py"
    ).read_text(encoding="utf-8")

    assert "opens_king_fight" in source
    assert "llm_fight_mode" in source
    assert 'os.environ.get("GHOST_LLM_DEBUG") != "1"' in source
    assert "return" in source



def test_king_parry_counters_center_line_lunge_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut("prepared_king")
    packet = game.resolve_king_fight_move("parry")
    exchange = packet["exchange"]

    assert exchange["intent"] == "royal_lunge"
    assert exchange["move"] == "parry"
    assert exchange["result"] == "correct_read"
    assert exchange["player_damage"] == 0
    assert exchange["king_damage"] == 0
    assert "parry" in exchange["valid_responses"]


def test_king_lunge_allows_parry_deflect_or_dodge_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    for move in ("parry", "deflect", "dodge"):
        game, _packet = create_fight_stage_shortcut("prepared_king")
        packet = game.resolve_king_fight_move(move)
        exchange = packet["exchange"]

        assert exchange["intent"] == "royal_lunge"
        assert exchange["result"] == "correct_read"
        assert exchange["player_damage"] == 0
        assert move in exchange["valid_responses"]


def test_elite_lunge_allows_parry_deflect_or_dodge_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    for move in ("parry", "deflect", "dodge"):
        game, _packet = create_fight_stage_shortcut("elite_knight")

        # First Champion intent is shield_wall. Advance to champion_lunge.
        first = game.resolve_king_fight_move("heavy")
        assert first["stage"] == "elite_knight"

        second = game.resolve_king_fight_move(move)
        exchange = second["exchange"]

        assert exchange["intent"] == "champion_lunge"
        assert exchange["result"] == "correct_read"
        assert exchange["player_damage"] == 0
        assert move in exchange["valid_responses"]


def test_fight_prompt_allows_llm_to_render_tells_without_changing_intent_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )
    from ghost.examples.ghost_revolution.llm_bridge import (
        build_king_fight_stance_packet,
        build_king_fight_voice_contract_prompt,
    )

    game, _packet = create_fight_stage_shortcut("prepared_king")
    packet = game.resolve_king_fight_move("parry")

    stance = build_king_fight_stance_packet(packet)
    prompt = build_king_fight_voice_contract_prompt(packet)
    facts = stance["facts"]

    assert facts["intent"] == "royal_lunge"
    assert facts["martial_tell_profile"]["mechanical_truth"] == (
        "committed center-line thrust"
    )
    assert "rear heel plants" in facts["martial_tell_profile"]["safe_rendering_space"]
    assert "fresh medieval combat language" in prompt
    assert "must not create a new intent" in prompt
    assert "valid_responses" in prompt



def test_king_heavy_can_be_parried_into_forced_response_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    class LowRoll:
        def randint(self, low, high):
            return 1

    game, _packet = create_fight_stage_shortcut("prepared_king")
    game.rng = LowRoll()
    game.king_fight["adaptive_defense_enabled"] = True
    game.king_fight["intent"] = "overextended_recovery"

    packet = game.resolve_king_fight_move("heavy")
    exchange = packet["exchange"]

    assert exchange["result"] == "king_parry"
    assert exchange["king_damage"] == 0
    assert exchange["player_damage"] == 0
    assert exchange["king_defense"]["type"] == "king_parry"
    assert packet["forced_response"]["allowed_moves"] == (
        "dodge",
        "light",
    )


def test_king_light_can_be_deflected_into_forced_response_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    class LowRoll:
        def randint(self, low, high):
            return 1

    game, _packet = create_fight_stage_shortcut("prepared_king")
    game.rng = LowRoll()
    game.king_fight["adaptive_defense_enabled"] = True
    game.king_fight["intent"] = "overextended_recovery"

    packet = game.resolve_king_fight_move("light")
    exchange = packet["exchange"]

    assert exchange["result"] == "king_deflect"
    assert exchange["king_damage"] == 0
    assert exchange["player_damage"] == 0
    assert exchange["king_defense"]["type"] == "king_deflect"
    assert packet["forced_response"]["allowed_moves"] == (
        "dodge",
        "light",
    )


def test_forced_response_restricts_recovery_options_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut("prepared_king")
    observation = game.king_fight_opponent_observation()

    game.apply_king_fight_opponent_intent(
        "overextended_recovery",
        proposed_reaction_plan="parry_heavy",
        proposed_forced_response_read="light",
        selection_key=observation["selection_key"],
    )

    first = game.resolve_king_fight_move("heavy")
    forced = first["forced_response"]

    assert forced["allowed_moves"] == ("dodge", "light")
    assert forced["random_used"] is False
    assert "selected_move" not in forced["recovery_read"]

    denied = game.resolve_king_fight_move("heavy")

    assert denied["outcome"] == "forced_response_denied"
    assert "off balance" in denied["message"]

    second = game.resolve_king_fight_move("light")
    exchange = second["exchange"]

    assert exchange["result"] == "forced_recovery_denied"
    assert exchange["forced_response_read"] == "light"
    assert exchange["forced_response_read_matched"] is True
    assert exchange["king_damage"] == 0
    assert exchange["player_damage"] == 0
    assert second["forced_response"] is None


def test_king_defense_chance_learns_repeated_heavies_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut("prepared_king")
    game.king_fight["player_patterns"] = {
        "heavy_count": 4,
        "light_count": 0,
        "parry_count": 0,
        "deflect_count": 0,
        "dodge_count": 0,
        "last_moves": [
            "heavy",
            "heavy",
            "light",
            "heavy",
        ],
    }

    bonus = game._king_pattern_bonus_for_move("heavy")

    assert bonus >= 30


def test_llm_fight_prompt_includes_king_defense_state_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )
    from ghost.examples.ghost_revolution.llm_bridge import (
        build_king_fight_stance_packet,
        build_king_fight_voice_contract_prompt,
    )

    class LowRoll:
        def randint(self, low, high):
            return 1

    game, _packet = create_fight_stage_shortcut("prepared_king")
    game.rng = LowRoll()
    game.king_fight["adaptive_defense_enabled"] = True
    game.king_fight["intent"] = "overextended_recovery"

    packet = game.resolve_king_fight_move("heavy")

    stance = build_king_fight_stance_packet(packet)
    prompt = build_king_fight_voice_contract_prompt(packet)

    assert stance["facts"]["king_defense"]["type"] == "king_parry"
    assert stance["facts"]["forced_response"]["allowed_moves"] == (
        "dodge",
        "light",
    )
    assert "king_defense" in prompt
    assert "forced_response" in prompt
    assert "resolved reaction" in prompt


def test_king_forced_response_menu_source_exists_v180():
    from pathlib import Path

    source = Path(
        "ghost/examples/ghost_revolution/presentation.py"
    ).read_text(encoding="utf-8")

    assert "def king_fight_move_menu_lines" in source
    assert "You are off balance." in source
    assert "Only these reactions are available:" in source



def test_player_parry_creates_opening_without_direct_damage_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut("prepared_king")
    packet = game.resolve_king_fight_move("parry")
    exchange = packet["exchange"]

    assert exchange["intent"] == "royal_lunge"
    assert exchange["move"] == "parry"
    assert exchange["result"] == "correct_read"
    assert exchange["king_damage"] == 0
    assert exchange["player_damage"] == 0
    assert packet["parry_opening"]["damage_bonus"] == 1
    assert packet["parry_opening"]["guaranteed_next_attack"] is True


def test_player_parry_opening_guarantees_next_attack_plus_one_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut("prepared_king")

    first = game.resolve_king_fight_move("parry")
    assert first["parry_opening"]["damage_bonus"] == 1

    second = game.resolve_king_fight_move("heavy")
    exchange = second["exchange"]

    assert exchange["intent"] == "royal_lunge"
    assert exchange["move"] == "heavy"
    assert exchange["result"] == "parry_opening_hit"
    assert exchange["king_damage"] > 0
    assert exchange["player_damage"] == 0
    assert exchange["parry_opening_used"]["damage_bonus"] == 1
    assert second["parry_opening"] is None


def test_llm_prompt_carries_player_parry_opening_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )
    from ghost.examples.ghost_revolution.llm_bridge import (
        build_king_fight_stance_packet,
        build_king_fight_voice_contract_prompt,
    )

    game, _packet = create_fight_stage_shortcut("prepared_king")
    packet = game.resolve_king_fight_move("parry")

    stance = build_king_fight_stance_packet(packet)
    prompt = build_king_fight_voice_contract_prompt(packet)

    assert stance["facts"]["parry_opening"]["damage_bonus"] == 1
    assert "parry_opening" in prompt
    assert "player's parry as control" in prompt



def test_king_fight_voice_contract_does_not_force_next_tell_v180():
    from ghost.examples.ghost_revolution.llm_bridge import (
        KING_FIGHT_VOICE_CONTRACT,
        build_king_fight_stance_packet,
    )

    joined = " ".join(KING_FIGHT_VOICE_CONTRACT)

    assert "UI will print the next tell separately" in joined
    assert "Do not narrate facts.tell as if it already happened" in joined
    assert "complete sentence" in joined

    stance = build_king_fight_stance_packet(
        {
            "outcome": "king_exchange",
            "stage": "king_phase_one",
            "exchange": {
                "intent": "royal_lunge",
                "move": "parry",
                "result": "correct_read",
                "message": "Parry opened the king.",
            },
            "tell": "The king hides behind a perfect royal guard.",
        }
    )

    assert stance["limits"]["max_words"] == 65


def test_king_fight_scene_limit_is_tighter_v180():
    from ghost.examples.ghost_revolution.llm_bridge import (
        build_king_fight_scene_stance_packet,
    )

    stance = build_king_fight_scene_stance_packet(
        {
            "outcome": "elite_knight_called",
            "stage": "elite_knight",
            "tell": "The Champion sets his shield.",
        },
        "elite_knight_start",
    )

    assert stance["limits"]["max_words"] == 70


def test_king_fight_menu_marks_transition_scene_seen_v180(monkeypatch):
    from collections import deque

    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )
    from ghost.examples.ghost_revolution import presentation

    game, _packet = create_fight_stage_shortcut("prepared_king")

    # Force the first successful hit to trigger the Champion transition.
    game.king_fight["king_health"] = game.king_fight["king_half_health"] + 1
    game.king_fight["intent"] = "crown_guard"

    inputs = iter(["3", "1", "q"])

    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt="": next(inputs),
    )
    monkeypatch.setenv("GHOST_DEV_LLM_NARRATION", "1")

    presentation.king_fight_menu(game, deque())

    seen = getattr(game, "_ghost_llm_scene_beats_seen", set())

    assert "elite_knight_start" in seen



def test_king_fight_transition_scene_seen_helper_marks_next_stage_v180():
    from ghost.examples.ghost_revolution import presentation

    class DummyGame:
        pass

    game = DummyGame()

    presentation._king_fight_mark_transition_scene_seen(
        game,
        {
            "outcome": "elite_knight_called",
            "stage": "elite_knight",
        },
    )

    assert "elite_knight_start" in game._ghost_llm_scene_beats_seen

    presentation._king_fight_mark_transition_scene_seen(
        game,
        {
            "outcome": "elite_knight_defeated",
            "stage": "king_phase_two",
        },
    )

    assert "phase_two_start" in game._ghost_llm_scene_beats_seen


def test_king_fight_packet_final_scene_includes_last_breath_v180():
    from ghost.examples.ghost_revolution.presentation import (
        _king_fight_packet_is_final_scene,
    )

    assert _king_fight_packet_is_final_scene(
        {"outcome": "last_breath_king_victory"}
    ) is True


def test_king_fight_scene_stance_hides_future_tell_v180():
    from ghost.examples.ghost_revolution.llm_bridge import (
        build_king_fight_scene_stance_packet,
    )

    stance = build_king_fight_scene_stance_packet(
        {
            "outcome": "phase_one_start",
            "stage": "king_phase_one",
            "tell": (
                "The king drives his blade "
                "toward your center line."
            ),
        },
        "phase_one_start",
    )

    assert stance["facts"]["tell"] is None


def test_forced_recovery_stance_drops_old_attack_v180():
    from ghost.examples.ghost_revolution.llm_bridge import (
        build_king_fight_stance_packet,
    )

    stance = build_king_fight_stance_packet(
        {
            "outcome": "king_forced_response",
            "stage": "king_phase_one",
            "exchange": {
                "move": "dodge",
                "intent": "royal_lunge",
                "result": "forced_recovered",
                "message": (
                    "You recover with a hard dodge."
                ),
                "king_defense": {
                    "type": "king_deflect",
                },
                "forced_response": {
                    "source_move": "heavy",
                    "correct_move": "dodge",
                },
            },
        }
    )

    facts = stance["facts"]

    assert facts["move"] == "dodge"
    assert facts["intent"] is None
    assert facts["king_defense"] is None
    assert facts["forced_response"] is None
    assert facts["martial_tell_profile"] is None
    assert facts["forced_recovery_resolved"] is True


def test_transition_packets_use_scene_narrator_v180():
    import inspect

    from ghost.examples.ghost_revolution import presentation

    source = inspect.getsource(
        presentation.king_fight_menu
    )

    assert 'outcome == "elite_knight_called"' in source
    assert '"elite_knight_start"' in source

    assert 'outcome == "elite_knight_defeated"' in source
    assert '"phase_two_start"' in source


def test_scene_status_packet_separates_upcoming_tell_v180():
    from ghost.examples.ghost_revolution import presentation

    class DummyGame:
        followers = 0
        gold = 0
        food = 0
        heat = 0
        king_control = 0
        guards_defeated = 0
        armor = 0
        leader_weapon_tier = "common"
        leader_weapon_name = "Sword"
        primary_weapon = "sword"

        def calculate_rebellion_strength(self):
            return {
                "strength": 0,
            }

    packet = (
        presentation
        ._king_fight_scene_packet_from_status(
            DummyGame(),
            {
                "stage": "king_phase_one",
                "tell": "Future attack.",
            },
            "phase_one_start",
        )
    )

    assert packet["tell"] is None
    assert packet["upcoming_tell"] == "Future attack."


def test_champion_shield_wall_feint_has_explicit_roles_v180():
    from ghost.examples.ghost_revolution.llm_bridge import (
        build_king_fight_stance_packet,
    )

    packet = {
        "outcome": "elite_knight_exchange",
        "stage": "elite_knight",
        "exchange": {
            "stage": "elite_knight",
            "intent": "shield_wall",
            "move": "feint_heavy",
            "expected": "feint_heavy",
            "valid_responses": [
                "feint_heavy",
                "feint_light",
            ],
            "result": "correct_read",
            "elite_knight_damage": 3,
            "player_damage": 0,
            "king_heal": 0,
            "message": (
                "You survive the Champion's read."
            ),
        },
        "player_health": 10,
        "elite_knight_health": 11,
        "king_health": 10,
        "castle_timer": 14,
        "tell": (
            "The Champion crouches low for "
            "the next attack."
        ),
    }

    stance = build_king_fight_stance_packet(
        packet
    )

    facts = stance["facts"]
    truth = facts["resolved_exchange_truth"]
    profile = facts["martial_tell_profile"]

    assert facts["elite_knight_damage"] == 3
    assert facts["enemy_damage"] == 3

    assert truth["enemy_actor"] == "elite_knight"
    assert truth["intent_owner"] == "elite_knight"
    assert truth["martial_profile_owner"] == "elite_knight"

    assert truth["player_move"] == "feint_heavy"
    assert truth["enemy_intent"] == "shield_wall"

    assert truth["damage_dealt_by_player"] == 3
    assert truth["damage_target"] == "elite_knight"
    assert truth["damage_received_by_player"] == 0

    assert (
        truth["player_uses_shield_in_this_exchange"]
        is False
    )

    assert (
        truth["enemy_uses_shield_in_this_exchange"]
        is True
    )

    assert (
        "shield wall belongs to the King's Champion"
        in truth["required_actor_action_target"]
    )

    assert profile["owner_actor"] == "elite_knight"
    assert (
        profile["owner_display_name"]
        == "the King's Champion"
    )

    assert facts["tell"] is None
    assert facts["upcoming_tell_hidden"] is True


def test_champion_feint_prompt_contains_role_ownership_v180():
    from ghost.examples.ghost_revolution.llm_bridge import (
        build_king_fight_voice_contract_prompt,
    )

    packet = {
        "outcome": "elite_knight_exchange",
        "stage": "elite_knight",
        "exchange": {
            "intent": "shield_wall",
            "move": "feint_heavy",
            "expected": "feint_heavy",
            "valid_responses": [
                "feint_heavy",
                "feint_light",
            ],
            "result": "correct_read",
            "elite_knight_damage": 3,
            "player_damage": 0,
            "message": (
                "The feint defeats the shield wall."
            ),
        },
        "tell": "Future Champion attack.",
    }

    prompt = build_king_fight_voice_contract_prompt(
        packet
    )

    assert '"enemy_actor": "elite_knight"' in prompt
    assert '"intent_owner": "elite_knight"' in prompt
    assert '"damage_target": "elite_knight"' in prompt

    assert (
        '"player_uses_shield_in_this_exchange": false'
        in prompt
    )

    assert (
        "shield wall belongs to the King's Champion"
        in prompt
    )

    assert "Future Champion attack." not in prompt


def test_champion_shield_wall_feint_fallback_preserves_roles_v180():
    from ghost.examples.ghost_revolution.llm_bridge import (
        generate_king_fight_adapter_fallback_narration,
    )

    packet = {
        "outcome": "elite_knight_exchange",
        "stage": "elite_knight",
        "exchange": {
            "intent": "shield_wall",
            "move": "feint_heavy",
            "expected": "feint_heavy",
            "valid_responses": [
                "feint_heavy",
                "feint_light",
            ],
            "result": "correct_read",
            "elite_knight_damage": 3,
            "player_damage": 0,
            "message": (
                "The feint defeats the shield wall."
            ),
        },
    }

    result = (
        generate_king_fight_adapter_fallback_narration(
            packet
        )
    )

    text = result["text"].lower()

    assert "champion" in text
    assert "feint" in text
    assert "shield" in text
    assert "your shield" not in text
    assert "you plant your shield" not in text


def test_elite_transition_scene_uses_final_attack_truth_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    from ghost.examples.ghost_revolution.llm_bridge import (
        build_king_fight_scene_stance_packet,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    fight = game.king_fight

    fight["king_health"] = (
        fight["king_half_health"] + 2
    )

    fight["intent"] = "crown_guard"

    packet = game.resolve_king_fight_move(
        "feint_heavy"
    )

    stance = build_king_fight_scene_stance_packet(
        packet,
        "elite_knight_start",
    )

    facts = stance["facts"]
    trigger = facts["transition_trigger"]
    truth = facts["resolved_exchange_truth"]

    assert stance["scene_moment"] == (
        "elite_knight_transition_after_"
        "king_exchange"
    )

    assert trigger["player_move"] == (
        "feint_heavy"
    )

    assert trigger["king_damage"] > 0
    assert trigger["reaction_owner"] == "king"

    assert facts["move"] == "feint_heavy"
    assert facts["king_damage"] > 0

    assert truth["enemy_actor"] == "king"
    assert truth["intent_owner"] == "king"
    assert truth["damage_target"] == "king"

    assert (
        truth["damage_dealt_by_player"]
        > 0
    )

    assert (
        "king physically reacting"
        in facts["transition_rendering_rule"]
    )


def test_elite_transition_fallback_orders_attack_reaction_and_entry_v180():
    from ghost.examples.ghost_revolution.llm_bridge import (
        generate_king_fight_adapter_fallback_scene_beat,
    )

    packet = {
        "outcome": "elite_knight_called",
        "stage": "elite_knight",
        "transition_trigger": {
            "player_move": "feint_heavy",
            "king_damage": 5,
            "player_damage": 0,
            "last_attack_landed": True,
        },
    }

    result = (
        generate_king_fight_adapter_fallback_scene_beat(
            packet,
            "elite_knight_start",
        )
    )

    text = result["text"]

    attack_index = text.find("feint")
    reaction_index = text.find("recoils")
    summon_index = text.find(
        "raises two fingers"
    )
    champion_index = text.find(
        "King's Champion"
    )

    assert attack_index >= 0
    assert reaction_index > attack_index
    assert summon_index > reaction_index
    assert champion_index > summon_index


def test_base_intent_truth_does_not_credit_failed_reaction_v180():
    from ghost.examples.ghost_revolution.llm_bridge import (
        build_king_fight_stance_packet,
    )

    packet = {
        "outcome": "elite_knight_exchange",
        "stage": "elite_knight",
        "exchange": {
            "intent": "champion_lunge",
            "move": "feint_heavy",
            "result": "failed_knight_read",
            "elite_knight_damage": 0,
            "player_damage": 3,
            "opponent_reaction_plan": (
                "break_parry"
            ),
            "opponent_reaction_plan_label": (
                "Break Parry"
            ),
            "reaction_plan_predictive": True,
            "reaction_plan_matched": False,
            "reaction_plan_missed": True,
            "reaction_miss_exposed_enemy": False,
            "reaction_miss_bonus": 0,
            "resolution_source": (
                "base_intent"
            ),
            "message": (
                "The committed tactic defeats "
                "the response."
            ),
        },
    }

    stance = build_king_fight_stance_packet(
        packet
    )

    facts = stance["facts"]

    truth = facts[
        "resolved_exchange_truth"
    ]

    assert facts["resolution_source"] == (
        "base_intent"
    )

    assert (
        truth["reaction_plan_matched"]
        is False
    )

    assert (
        truth["reaction_plan_missed"]
        is True
    )

    rule = truth[
        "required_actor_action_target"
    ]

    assert (
        "committed Champion lunge"
        in rule
    )

    assert "champion_lunge" not in rule

    assert "did not match" in rule

    assert (
        "did not resolve the exchange"
        in rule
    )

    assert (
        "Do not mention or describe that hidden prediction"
        in rule
    )


def test_base_intent_fallback_does_not_invent_feint_read_v180():
    from ghost.examples.ghost_revolution.llm_bridge import (
        generate_king_fight_adapter_fallback_narration,
    )

    packet = {
        "outcome": "elite_knight_exchange",
        "stage": "elite_knight",
        "exchange": {
            "intent": "champion_lunge",
            "move": "feint_heavy",
            "result": "failed_knight_read",
            "elite_knight_damage": 0,
            "player_damage": 3,
            "opponent_reaction_plan": (
                "break_parry"
            ),
            "opponent_reaction_plan_label": (
                "Break Parry"
            ),
            "reaction_plan_predictive": True,
            "reaction_plan_matched": False,
            "reaction_plan_missed": True,
            "reaction_miss_exposed_enemy": False,
            "reaction_miss_bonus": 0,
            "resolution_source": (
                "base_intent"
            ),
        },
    }

    result = (
        generate_king_fight_adapter_fallback_narration(
            packet
        )
    )

    text = result["text"].lower()

    assert "committed lunge" in text
    assert "break parry" in text
    assert "prediction misses" in text

    assert "read your feint" not in text
    assert "reads the feint" not in text


def test_matched_reaction_may_receive_resolution_credit_v180():
    from ghost.examples.ghost_revolution.llm_bridge import (
        build_king_fight_stance_packet,
    )

    packet = {
        "outcome": "elite_knight_exchange",
        "stage": "elite_knight",
        "exchange": {
            "intent": "champion_lunge",
            "move": "dodge",
            "result": "champion_tracks_dodge",
            "elite_knight_damage": 0,
            "player_damage": 3,
            "opponent_reaction_plan": (
                "track_dodge"
            ),
            "opponent_reaction_plan_label": (
                "Track Dodge"
            ),
            "reaction_plan_predictive": True,
            "reaction_plan_matched": True,
            "reaction_plan_missed": False,
            "reaction_miss_exposed_enemy": False,
            "resolution_source": (
                "reaction_plan"
            ),
            "message": (
                "The Champion tracks the dodge."
            ),
        },
    }

    stance = build_king_fight_stance_packet(
        packet
    )

    truth = stance["facts"][
        "resolved_exchange_truth"
    ]

    assert truth["resolution_source"] == (
        "reaction_plan"
    )

    assert (
        truth["reaction_plan_matched"]
        is True
    )

    assert (
        "directly resolves the exchange"
        in truth[
            "required_actor_action_target"
        ]
    )


def test_base_intent_narration_contract_hides_internal_identifier_v180():
    from ghost.examples.ghost_revolution.llm_bridge import (
        build_king_fight_stance_packet,
    )

    packet = {
        "outcome": "king_exchange",
        "stage": "king_phase_one",
        "exchange": {
            "intent": "crown_guard",
            "move": "heavy",
            "result": "king_hit",
            "king_damage": 0,
            "player_damage": 2,
            "opponent_reaction_plan": (
                "read_feint"
            ),
            "opponent_reaction_plan_label": (
                "Read Feint"
            ),
            "reaction_plan_predictive": True,
            "reaction_plan_matched": False,
            "reaction_plan_missed": True,
            "reaction_miss_exposed_enemy": False,
            "resolution_source": "base_intent",
        },
    }

    stance = build_king_fight_stance_packet(
        packet
    )

    truth = stance["facts"][
        "resolved_exchange_truth"
    ]

    required = truth[
        "required_actor_action_target"
    ]

    assert "closed royal guard" in required
    assert "heavy attack" in required

    assert "crown_guard" not in required
    assert "read_feint" not in required
    assert "base_intent" not in required

    blocked = stance["limits"][
        "may_not_mention"
    ]

    assert "crown_guard" in blocked
    assert "read_feint" in blocked
    assert "base_intent" in blocked


def test_correct_read_fallback_uses_human_move_name_v180():
    from ghost.examples.ghost_revolution.llm_bridge import (
        generate_king_fight_adapter_fallback_narration,
    )

    packet = {
        "outcome": "king_exchange",
        "stage": "king_phase_one",
        "exchange": {
            "intent": "crown_guard",
            "move": "feint_heavy",
            "result": "correct_read",
            "king_damage": 5,
            "player_damage": 0,
            "resolution_source": (
                "player_counter"
            ),
        },
    }

    result = (
        generate_king_fight_adapter_fallback_narration(
            packet
        )
    )

    text = result["text"]

    assert (
        "heavy feint and follow-up"
        in text
    )

    assert "feint_heavy" not in text
