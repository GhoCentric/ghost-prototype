"""Behavior-focused coverage contracts for small Ghost core boundaries."""

from __future__ import annotations

import json

import pytest

import ghost as ghost_module
from ghost.agents import AgentRegistry
from ghost.engine import GhostEngine
from ghost.events import (
    RelationshipEvent,
    normalize_game_action,
)
from ghost.ids import normalize_id
from ghost.input import (
    contains_any,
    extract_mentioned_gold_price,
    extract_mentioned_number,
    normalize_text,
)
from ghost.llm_adapter import (
    build_voice_contract_prompt,
    fallback_from_stance,
)


class _Unstringable:
    def __str__(self) -> str:
        raise RuntimeError("string conversion failed")


def test_module_facade_enforces_lifecycle_and_snapshot_isolation():
    ghost_module.reset()

    try:
        with pytest.raises(RuntimeError):
            ghost_module.snapshot()

        with pytest.raises(RuntimeError):
            ghost_module.step()

        with pytest.raises(RuntimeError):
            ghost_module.state()

        engine = ghost_module.init(
            {
                "coverage_marker": {
                    "value": 1,
                },
            }
        )

        assert ghost_module.state() is engine.state()

        state = ghost_module.step()

        assert state["cycles"] == 1

        snapshot = ghost_module.snapshot()

        assert snapshot["coverage_marker"]["value"] == 1

        snapshot["coverage_marker"]["value"] = 999

        assert (
            ghost_module.snapshot()["coverage_marker"]["value"]
            == 1
        )
    finally:
        ghost_module.reset()


def test_agent_registry_unknown_reads_and_public_reads_are_isolated():
    registry = AgentRegistry({})

    assert registry.get("missing") is None

    live_agent = registry.ensure("  player  ")
    live_agent["memory"]["private_note"] = "original"

    public_agent = registry.get("player")

    assert public_agent["memory"]["private_note"] == "original"

    public_agent["memory"]["private_note"] = "mutated"

    assert (
        registry.get("player")["memory"]["private_note"]
        == "original"
    )

    public_all = registry.all()
    public_all["player"]["mood"] = 0.0

    assert registry.get("player")["mood"] == 0.5


def test_engine_rejects_unknown_step_type_without_mutating_state():
    engine = GhostEngine()
    before = engine.snapshot()

    with pytest.raises(TypeError, match="dict or GhostStep"):
        engine.step(object())

    assert engine.snapshot() == before


def test_normalize_id_converts_stringification_failures_to_value_error():
    with pytest.raises(ValueError, match="safely stringable"):
        normalize_id(_Unstringable(), "actor id")


def test_public_enum_string_and_empty_game_action_contracts():
    assert str(RelationshipEvent.HELP) == "help"

    with pytest.raises(ValueError, match="must not be empty"):
        normalize_game_action("   ")


def test_input_normalization_and_number_extraction_cover_real_text_paths():
    text = " plese!!! takwe coina. "

    assert normalize_text(text) == "please take coins"

    assert contains_any(
        "P1e@se help me",
        ("please", "help"),
    )

    assert not contains_any(
        "quiet departure",
        ("threat", "attack"),
    )

    assert extract_mentioned_number(
        "I can bring 42 supplies."
    ) == 42

    assert extract_mentioned_number(
        "I can bring 20 supplies."
    ) == 20

    assert extract_mentioned_number(
        "I can bring supplies."
    ) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", None),
        ("The price is 20 gold.", 20),
        ("I will pay 30.", 30),
        ("We found 40 apples.", None),
    ],
)
def test_gold_price_extraction_requires_money_or_price_context(
    text,
    expected,
):
    assert extract_mentioned_gold_price(text) == expected


def test_voice_contract_prompt_keeps_only_recent_five_lines():
    recent_lines = [
        f"line-{index}"
        for index in range(7)
    ]

    prompt = build_voice_contract_prompt(
        {
            "scene_moment": "normal",
        },
        npc_profile={
            "name": "shopkeeper",
        },
        recent_lines=recent_lines,
    )

    payload = json.loads(
        prompt.split("STANCE_PACKET:\n", 1)[1]
    )

    assert payload["npc_profile"]["name"] == "shopkeeper"
    assert payload["recent_lines_to_avoid"] == recent_lines[-5:]


@pytest.mark.parametrize(
    ("scene", "expected_fragment"),
    [
        ("authority_override", "secret orders"),
        ("narrator_override", "narrator notes"),
        ("emotional_extortion", "cannot verify"),
        ("threat", "Do not threaten"),
        ("insult", "Watch your mouth"),
        ("pressure", "terms do not change"),
    ],
)
def test_fallback_renderer_handles_each_governed_scene(
    scene,
    expected_fragment,
):
    line = fallback_from_stance(
        {
            "scene_moment": scene,
            "facts": {
                "item": "bread",
                "price": 25,
            },
        },
        item="sword",
        price=10,
    )

    assert expected_fragment in line


def test_fallback_renderer_has_a_normal_default_without_price():
    assert fallback_from_stance({}) == "What do you need?"
