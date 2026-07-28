import sys
from types import SimpleNamespace

import pytest

from ghost.examples.ghost_revolution.dev_shortcuts import (
    create_fight_stage_shortcut,
)
from ghost.examples.ghost_revolution.llm_bridge import (
    AMBIENT_ROLE,
    NARRATION_ROLE,
    STRATEGY_ROLE,
    LLMBridgeConfig,
    OpenAIResponsesClient,
    config_for_role,
    measured_llm_cost,
)
from ghost.examples.ghost_revolution.opponent_ai import (
    GhostFightOpponentBridge,
)


def test_frontier_role_defaults_are_authoritative_v180(monkeypatch):
    for name in (
        "OPENAI_MODEL",
        "GHOST_LLM_MODEL",
        "GHOST_LLM_STRATEGY_MODEL",
        "GHOST_LLM_NARRATION_MODEL",
        "GHOST_LLM_AMBIENT_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)

    strategy = config_for_role(STRATEGY_ROLE)
    narration = config_for_role(NARRATION_ROLE)
    ambient = config_for_role(AMBIENT_ROLE)

    assert strategy.model == "gpt-5.6-sol"
    assert strategy.reasoning_effort == "medium"
    assert strategy.max_output_tokens == 768
    assert strategy.hard_max_output_tokens == 1024
    assert strategy.input_cost_per_million_tokens == 5.0
    assert strategy.cached_input_cost_per_million_tokens == 0.5
    assert strategy.output_cost_per_million_tokens == 30.0

    assert narration.model == "gpt-5.6-terra"
    assert narration.reasoning_effort == "none"
    assert narration.input_cost_per_million_tokens == 2.5
    assert narration.cached_input_cost_per_million_tokens == 0.25
    assert narration.output_cost_per_million_tokens == 15.0

    assert ambient.model == "gpt-5.6-luna"
    assert ambient.reasoning_effort == "none"
    assert ambient.input_cost_per_million_tokens == 1.0
    assert ambient.cached_input_cost_per_million_tokens == 0.1
    assert ambient.output_cost_per_million_tokens == 6.0


def test_role_specific_environment_overrides_are_isolated_v180(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "legacy-model")
    monkeypatch.setenv("GHOST_LLM_STRATEGY_MODEL", "strategy-model")
    monkeypatch.setenv("GHOST_LLM_NARRATION_MODEL", "narration-model")
    monkeypatch.setenv("GHOST_LLM_AMBIENT_MODEL", "ambient-model")
    monkeypatch.setenv("GHOST_LLM_STRATEGY_REASONING", "high")

    assert config_for_role("strategy").model == "strategy-model"
    assert config_for_role("strategy").reasoning_effort == "high"
    assert config_for_role("narration").model == "narration-model"
    assert config_for_role("ambient").model == "ambient-model"


def test_invalid_role_and_reasoning_are_rejected_v180(monkeypatch):
    with pytest.raises(ValueError):
        config_for_role("judge")

    monkeypatch.setenv("GHOST_LLM_STRATEGY_REASONING", "infinite")

    with pytest.raises(ValueError):
        config_for_role("strategy")


def test_measured_cost_uses_cached_and_reasoning_usage_v180():
    cost = measured_llm_cost(
        {
            "input_tokens": 2000,
            "input_tokens_details": {"cached_tokens": 1200},
            "output_tokens": 400,
            "output_tokens_details": {"reasoning_tokens": 250},
            "total_tokens": 2400,
        },
        config=config_for_role("strategy"),
        response_model="gpt-5.6-sol",
    )

    assert cost is not None
    assert cost["input_tokens"] == 2000
    assert cost["cached_input_tokens"] == 1200
    assert cost["uncached_input_tokens"] == 800
    assert cost["reasoning_tokens"] == 250
    assert cost["visible_output_tokens"] == 150
    assert cost["total_cost"] == 0.0166


def test_openai_client_sends_reasoning_schema_and_cache_key_v180(
    monkeypatch,
):
    captured = {}

    class FakeResponse:
        status_code = 200
        text = "ok"

        def json(self):
            return {
                "id": "resp_test",
                "model": "gpt-5.6-sol",
                "output_text": (
                    '{"intent":"royal_lunge",'
                    '"reaction_plan":"commit_attack",'
                    '"forced_response_read":"dodge",'
                    '"intent_reason":"pressure",'
                    '"reaction_reason":"no read"}'
                ),
                "usage": {
                    "input_tokens": 100,
                    "input_tokens_details": {"cached_tokens": 20},
                    "output_tokens": 50,
                    "output_tokens_details": {"reasoning_tokens": 30},
                    "total_tokens": 150,
                },
            }

    def fake_post(endpoint, *, headers, json, timeout):
        captured["endpoint"] = endpoint
        captured["headers"] = headers
        captured["payload"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setitem(
        sys.modules,
        "httpx",
        SimpleNamespace(post=fake_post),
    )

    game, _packet = create_fight_stage_shortcut("prepared_king")
    observation = game.king_fight_opponent_observation()

    bridge = GhostFightOpponentBridge(
        client=OpenAIResponsesClient(),
        config=config_for_role("strategy"),
    )
    result = bridge.generate_king_fight_opponent_intent(observation)

    payload = captured["payload"]
    assert payload["model"] == "gpt-5.6-sol"
    assert payload["reasoning"] == {"effort": "medium"}
    assert payload["max_output_tokens"] == 768
    assert payload["store"] is False
    assert payload["prompt_cache_key"] == (
        "ghost-revolution-strategy-v180"
    )
    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["text"]["format"]["strict"] is True
    assert result["proposed_intent"] == "royal_lunge"
    assert result["response_model"] == "gpt-5.6-sol"
    assert result["measured_cost"]["source"] == "response_usage"
    assert result["measured_cost"]["reasoning_tokens"] == 30


def test_narration_role_does_not_request_structured_strategy_json_v180(
    monkeypatch,
):
    captured = {}

    class FakeResponse:
        status_code = 200
        text = "ok"

        def json(self):
            return {
                "id": "resp_narration",
                "model": "gpt-5.6-terra",
                "output_text": "The blade rings through the hall.",
                "usage": {
                    "input_tokens": 80,
                    "output_tokens": 12,
                    "total_tokens": 92,
                },
            }

    def fake_post(endpoint, *, headers, json, timeout):
        captured["payload"] = json
        return FakeResponse()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setitem(
        sys.modules,
        "httpx",
        SimpleNamespace(post=fake_post),
    )

    result = OpenAIResponsesClient()(
        "Narrate this resolved event.",
        config=config_for_role("narration"),
    )

    assert result["text"] == "The blade rings through the hall."
    assert captured["payload"]["model"] == "gpt-5.6-terra"
    assert captured["payload"]["reasoning"] == {"effort": "none"}
    assert "text" not in captured["payload"]
    assert result["usage"]["total_tokens"] == 92


def test_strategy_bridge_preserves_string_client_compatibility_v180():
    class StringClient:
        def __call__(self, prompt, *, config):
            del prompt, config
            return (
                '{"intent":"crown_guard",'
                '"reaction_plan":"hold_center",'
                '"forced_response_read":"light",'
                '"intent_reason":"recover control",'
                '"reaction_reason":"stay broad"}'
            )

    game, _packet = create_fight_stage_shortcut("prepared_king")
    observation = game.king_fight_opponent_observation()
    result = GhostFightOpponentBridge(
        client=StringClient(),
        config=config_for_role("strategy"),
    ).generate_king_fight_opponent_intent(observation)

    assert result["proposed_intent"] == "crown_guard"
    assert result["measured_cost"] is None
    assert result["usage"] is None
