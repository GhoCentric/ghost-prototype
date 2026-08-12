from __future__ import annotations

import builtins
import sys
from types import SimpleNamespace

import pytest

from ghost.examples.ghost_revolution.llm_bridge import (
    AMBIENT_ROLE,
    DeterministicCrownMockClient,
    GhostRevolutionLLMBridge,
    LLMBridgeConfig,
    NullLLMClient,
    OpenAIResponsesClient,
    build_crown_loop_prompt,
    build_crown_stance_packet,
    build_king_fight_scene_stance_packet,
    build_king_fight_stance_packet,
    config_for_role,
    generate_king_fight_adapter_fallback_narration,
    generate_king_fight_adapter_fallback_scene_beat,
    measured_llm_cost,
    normalize_client_result,
    rough_token_count,
)


def _exchange_packet(**overrides):
    exchange = {
        "intent": "royal_lunge",
        "move": "heavy",
        "result": "correct_read",
        "message": "Resolved exchange.",
        "king_damage": 3,
        "player_damage": 0,
        "valid_responses": ["heavy"],
    }
    exchange.update(overrides.pop("exchange", {}))
    packet = {
        "stage": "king",
        "outcome": "exchange",
        "exchange": exchange,
        "player_health": 20,
        "king_health": 20,
        "castle_timer": 5,
        "tell": "Upcoming tell",
    }
    packet.update(overrides)
    return packet


def _crown_packet(*, npc_marker="present", rule="uncertain", fate="none", reaction="uncertainty", world_numbers=True):
    context = {
        "ruler_profile": {
            "rule": rule,
            "fate": fate,
            "fear_score": 1,
            "mercy_score": 2,
            "followers": 3,
            "food": 4,
            "gold": 5,
            "weapon_caches": 6,
            "armor": 1,
            "heat": 2,
            "guards_defeated": 3,
            "king_control": 4,
        },
        "town": "Ashfield",
        "location": "square",
        "mode": "dialogue",
    }
    if npc_marker == "present":
        context["npc"] = {
            "name": "Elder",
            "role": "elder",
            "reaction": reaction,
            "dialogue_hook": "Speak plainly.",
        }
    elif npc_marker == "available":
        context["available_npcs"] = [
            {
                "name": "Guard",
                "role": "guard",
                "reaction": reaction,
            }
        ]
    if world_numbers:
        context["world_numbers"] = {"followers": 3}
    else:
        context["world_numbers"] = []
    return {"llm_context": context}


def _scene_packet(*, profile=None, stats=None, **extra):
    packet = _exchange_packet()
    if profile is not None:
        packet["player_profile"] = profile
    if stats is not None:
        packet["kingdom_stats"] = stats
    packet.update(extra)
    return packet


def test_role_base_empty_tokens_and_normalizers_cover_fallbacks(monkeypatch):
    monkeypatch.delenv("GHOST_LLM_AMBIENT_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("GHOST_LLM_MODEL", raising=False)

    base = LLMBridgeConfig(
        model="custom-base",
        input_cost_per_million_tokens=7.0,
        cached_input_cost_per_million_tokens=2.0,
        output_cost_per_million_tokens=9.0,
        max_output_tokens=12,
        hard_max_output_tokens=13,
        prompt_cache_key="custom-cache",
    )
    config = config_for_role(AMBIENT_ROLE, base=base)

    assert config.max_output_tokens == 12
    assert config.hard_max_output_tokens == 13
    assert config.prompt_cache_key == "custom-cache"
    assert rough_token_count("") == 0
    assert normalize_client_result(42)["text"] == "42"

    with pytest.raises(ValueError, match="packet must be a mapping"):
        build_crown_loop_prompt([])


def test_measured_cost_handles_invalid_details_and_unknown_pricing():
    config = LLMBridgeConfig(
        model="unknown-model",
        input_cost_per_million_tokens=2.0,
        cached_input_cost_per_million_tokens=1.0,
        output_cost_per_million_tokens=3.0,
    )
    cost = measured_llm_cost(
        {
            "input_tokens": "bad",
            "output_tokens": -4,
            "total_tokens": None,
            "input_tokens_details": [],
            "output_tokens_details": "bad",
        },
        config=config,
    )

    assert cost["input_tokens"] == 0
    assert cost["output_tokens"] == 0
    assert cost["total_tokens"] == 0
    assert cost["total_cost"] == 0


def test_crown_prompt_npc_fallbacks_and_world_number_fallback():
    available = build_crown_loop_prompt(
        _crown_packet(npc_marker="available", world_numbers=False)
    )
    unknown = build_crown_loop_prompt(
        _crown_packet(npc_marker="missing", world_numbers=False)
    )

    assert "Name: Guard" in available
    assert "Name: Unknown NPC" in unknown
    assert "Weapon caches: 6" in unknown


def test_deterministic_crown_mock_all_remaining_routes():
    client = DeterministicCrownMockClient()
    config = LLMBridgeConfig()

    jail = client(
        "- Reaction: trust\n- Crown fate: jail_king\n- Rule profile: uncertain",
        config=config,
    )
    feared = client(
        "- Reaction: fear\n- Crown fate: none\n- Rule profile: uncertain",
        config=config,
    )
    trusted = client(
        "- Reaction: neutral\n- Crown fate: none\n- Rule profile: trusted",
        config=config,
    )
    generic = client("unlabeled prompt", config=config)

    assert "Sparing" in jail
    assert "not test your crown" in feared
    assert "cautious hope" in trusted
    assert "waiting to see" in generic


def test_openai_client_import_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    original = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name == "httpx":
            raise ImportError("blocked")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)

    with pytest.raises(RuntimeError, match="httpx is required"):
        OpenAIResponsesClient()("prompt", config=LLMBridgeConfig())


class _Response:
    def __init__(self, data, *, status=200, text="response"):
        self._data = data
        self.status_code = status
        self.text = text

    def json(self):
        return self._data


def _install_httpx(monkeypatch, response, captured=None):
    def post(endpoint, *, headers, json, timeout):
        if captured is not None:
            captured.update(
                endpoint=endpoint,
                headers=headers,
                payload=json,
                timeout=timeout,
            )
        return response

    monkeypatch.setitem(sys.modules, "httpx", SimpleNamespace(post=post))
    monkeypatch.setenv("OPENAI_API_KEY", "key")


def test_openai_client_minimal_payload_http_error_and_output_fallbacks(monkeypatch):
    captured = {}
    _install_httpx(
        monkeypatch,
        _Response({"output_text": "ok"}),
        captured,
    )
    config = LLMBridgeConfig(
        model="custom",
        reasoning_effort=None,
        prompt_cache_key=None,
        structured_output_name=None,
        structured_output_schema=None,
    )
    result = OpenAIResponsesClient()("prompt", config=config)

    assert result["text"] == "ok"
    assert "prompt_cache_key" not in captured["payload"]
    assert "reasoning" not in captured["payload"]
    assert "text" not in captured["payload"]

    _install_httpx(monkeypatch, _Response({}, status=429, text="slow down"))
    with pytest.raises(RuntimeError, match="HTTP 429: slow down"):
        OpenAIResponsesClient()("prompt", config=config)

    _install_httpx(
        monkeypatch,
        _Response(
            {
                "output": [
                    {"content": [{"text": "first"}, {"text": ""}]},
                    {"content": [{"text": "second"}]},
                ]
            }
        ),
    )
    assert OpenAIResponsesClient()("prompt", config=config)["text"] == "first\nsecond"

    raw = {"output": [{"content": [{"type": "refusal"}]}]}
    _install_httpx(monkeypatch, _Response(raw))
    assert OpenAIResponsesClient()("prompt", config=config)["text"] == str(raw)


def test_stance_packet_damage_types_and_resolution_routes():
    bad = build_king_fight_stance_packet(
        _exchange_packet(
            exchange={
                "king_damage": "bad",
                "player_damage": object(),
                "intent": "royal_lunge",
                "move": "heavy",
                "result": "correct_read",
            }
        )
    )
    assert bad["facts"]["enemy_damage"] == 0
    assert bad["facts"]["player_damage"] == 0

    generic_feint = build_king_fight_stance_packet(
        _exchange_packet(
            exchange={
                "intent": "royal_lunge",
                "move": "feint_heavy",
                "result": "correct_read",
                "king_damage": 2,
            }
        )
    )
    assert "uses a feint" in generic_feint["facts"]["resolved_exchange_truth"]["required_actor_action_target"]

    dodge = build_king_fight_stance_packet(
        _exchange_packet(exchange={"move": "dodge", "result": "correct_read"})
    )
    assert "takes no damage" in dodge["facts"]["resolved_exchange_truth"]["required_actor_action_target"]

    hit = build_king_fight_stance_packet(
        _exchange_packet(exchange={"result": "king_hit", "player_damage": 4})
    )
    assert "hits the player" in hit["facts"]["resolved_exchange_truth"]["required_actor_action_target"]

    clean = build_king_fight_stance_packet(_exchange_packet(outcome="clean_king_victory"))
    collapse = build_king_fight_stance_packet(_exchange_packet(outcome="castle_collapse"))
    assert clean["scene_moment"] == "king_fight_clean_victory"
    assert collapse["scene_moment"] == "king_fight_castle_collapse"


def test_fight_narration_fallback_all_remaining_routes():
    packets = [
        ({"ending": "Final ending."}, "Final ending."),
        ({"outcome": "player_death"}, "final opening"),
        ({"outcome": "clean_king_victory"}, "one knee"),
        ({"outcome": "uncertain_king_fall"}, "falls as the castle"),
        (_exchange_packet(exchange={"resolution_source": "reaction_plan", "message": None}), "committed reaction"),
        (_exchange_packet(exchange={"result": "king_hit"}), "misread the king"),
        (_exchange_packet(exchange={"result": "other", "message": "Packet message"}), "Packet message"),
        ({"exchange": {}, "tell": "Tell text"}, "Tell text"),
        ({"exchange": []}, "Steel moves through smoke"),
    ]

    for packet, expected in packets:
        text = generate_king_fight_adapter_fallback_narration(packet)["text"]
        assert expected in text


def test_scene_stance_optional_metadata_and_non_transition_mapping():
    packet = _scene_packet(
        profile={"strength": 50},
        stats={"followers": 10},
        developer_preset="brutal",
        ending="Done",
        transition_trigger={"player_move": "heavy"},
    )
    stance = build_king_fight_scene_stance_packet(packet, "phase_two_start")

    assert stance["facts"]["developer_preset"] == "brutal"
    assert stance["facts"]["ending"] == "Done"
    assert stance["facts"]["transition_trigger"]["player_move"] == "heavy"
    assert "required_transition_sequence" not in stance["facts"]


def test_scene_fallback_movement_profiles_and_phase_one_routes():
    cases = [
        ({"wounded_start": True}, {"heat": 0}, "already hurt"),
        ({"strength": 90}, {"heat": 8}, "warlord"),
        ({"strength": 70, "prepared_assault": True}, {"heat": 1}, "prepared"),
        ({"armor": 3}, {"heat": 1}, "armor catches"),
        ({"guards_defeated": 5}, {"heat": 1}, "every guard"),
    ]
    for profile, stats, expected in cases:
        text = generate_king_fight_adapter_fallback_scene_beat(
            _scene_packet(profile=profile, stats=stats),
            "phase_two_start",
        )["text"]
        assert expected in text

    hot = generate_king_fight_adapter_fallback_scene_beat(
        _scene_packet(stats={"heat": 7, "followers": 1}),
        "phase_one_start",
    )["text"]
    army = generate_king_fight_adapter_fallback_scene_beat(
        _scene_packet(stats={"heat": 1, "followers": 40}),
        "phase_one_start",
    )["text"]
    default = generate_king_fight_adapter_fallback_scene_beat(
        _scene_packet(stats={"heat": 1, "followers": 1}),
        "phase_one_start",
    )["text"]
    assert "kingdom behind you is scarred" in hot
    assert "rebellion large enough" in army
    assert "one final path" in default


def test_scene_fallback_elite_transition_move_and_reaction_matrix():
    moves = {
        "feint_heavy": "heavy follow-up",
        "feint_light": "light follow-up",
        "heavy": "heavy strike",
        "light": "light strike",
        "deflect": "deflection",
        "parry": "final phase-one answer",
    }
    for move, expected in moves.items():
        packet = _scene_packet(
            transition_trigger={
                "player_move": move,
                "last_attack_landed": move != "parry",
                "king_damage": 2,
                "player_damage": 0,
                "king_intent": "royal_lunge",
                "result": "correct_read",
                "last_attack_message": "Resolved.",
            }
        )
        text = generate_king_fight_adapter_fallback_scene_beat(
            packet,
            "elite_knight_start",
        )["text"]
        assert expected in text
        if move == "parry":
            assert "yields ground" in text
        else:
            assert "recoils through the smoke" in text

    no_trigger = generate_king_fight_adapter_fallback_scene_beat(
        _scene_packet(),
        "elite_knight_start",
    )["text"]
    assert "champion steps through" in no_trigger


def test_scene_fallback_end_and_unknown_routes():
    assert "champion falls" in generate_king_fight_adapter_fallback_scene_beat({}, "elite_knight_end")["text"]

    cases = [
        ({"ending": "Explicit ending"}, "Explicit ending"),
        ({"outcome": "player_killed_by_king"}, "last exchange closes"),
        ({"outcome": "clean_king_victory"}, "beaten cleanly"),
        ({"outcome": "uncertain_king_fall"}, "falls as the castle"),
        ({"outcome": "other"}, "final turn"),
    ]
    for packet, expected in cases:
        assert expected in generate_king_fight_adapter_fallback_scene_beat(packet, "fight_end")["text"]

    assert "scene moves forward" in generate_king_fight_adapter_fallback_scene_beat({}, "unknown_reason")["text"]


def test_bridge_scene_prepare_and_generate_with_usage():
    class Client:
        def __call__(self, prompt, *, config):
            assert "STANCE_PACKET:" in prompt
            return {
                "text": "Narrator: A complete scene beat lands.",
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "model": "custom-model",
                "id": "resp_scene",
            }

    bridge = GhostRevolutionLLMBridge(
        client=Client(),
        config=LLMBridgeConfig(
            model="custom-model",
            max_output_tokens=50,
            hard_max_output_tokens=60,
        ),
    )
    packet = _scene_packet()
    prepared = bridge.prepare_king_fight_scene_beat(packet, "phase_two_start")
    generated = bridge.generate_king_fight_scene_beat(packet, "phase_two_start")

    assert prepared["provider_called"] is False
    assert generated["provider_called"] is True
    assert generated["text"] == "A complete scene beat lands."
    assert generated["response_id"] == "resp_scene"
    assert generated["measured_cost"]["input_tokens"] == 10


def test_crown_stance_missing_npc_and_scene_priority_routes():
    available = build_crown_stance_packet(
        _crown_packet(npc_marker="available", rule="uncertain", fate="none", reaction="neutral")
    )
    unknown = build_crown_stance_packet(
        _crown_packet(npc_marker="missing", rule="uncertain", fate="none", reaction="neutral")
    )
    feared = build_crown_stance_packet(
        _crown_packet(rule="feared", fate="none", reaction="neutral")
    )
    trusted = build_crown_stance_packet(
        _crown_packet(rule="trusted", fate="none", reaction="neutral")
    )

    assert available["facts"]["npc_name"] == "Guard"
    assert unknown["facts"]["npc_name"] == "Unknown NPC"
    assert feared["scene_moment"] == "crown_feared_rule"
    assert trusted["scene_moment"] == "crown_trusted_rule"
