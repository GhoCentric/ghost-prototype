import json

import pytest

from ghost.agents import AgentRegistry
from ghost.api import GhostAPI
from ghost.engine import GhostEngine
from ghost.events import RelationshipEvent
from ghost.temperament import interpret_relationship


BAD_FLOATS = [
    float("nan"),
    float("inf"),
    float("-inf"),
]


def assert_strict_json_safe(packet):
    json.dumps(packet, allow_nan=False)


@pytest.mark.parametrize("bad_value", BAD_FLOATS + [-0.1, 1.1, 100.0])
def test_engine_apply_event_rejects_out_of_range_intensity(bad_value):
    engine = GhostEngine()

    with pytest.raises(ValueError):
        engine.apply_event(
            "player",
            "shopkeeper",
            RelationshipEvent.BETRAYAL,
            intensity=bad_value,
        )


@pytest.mark.parametrize("bad_value", BAD_FLOATS + [-0.1, 1.1, 100.0])
def test_api_apply_event_rejects_out_of_range_intensity(bad_value):
    api = GhostAPI()

    with pytest.raises(ValueError):
        api.apply_event(
            "player",
            "shopkeeper",
            {
                "type": "help",
                "intensity": bad_value,
            },
        )


@pytest.mark.parametrize("bad_value", BAD_FLOATS)
def test_world_effects_reject_non_finite_values(bad_value):
    api = GhostAPI()

    with pytest.raises(ValueError):
        api.apply_world_effects(
            {
                "pressure_delta": bad_value,
            }
        )


@pytest.mark.parametrize("bad_value", BAD_FLOATS + [-0.1, 1.1])
def test_world_social_heat_rejects_invalid_values(bad_value):
    api = GhostAPI()

    with pytest.raises(ValueError):
        api.propagate_social_effect(
            source_event="betrayal",
            faction_heat=bad_value,
        )


@pytest.mark.parametrize("bad_value", BAD_FLOATS)
def test_temperament_custom_profile_rejects_non_finite_values(bad_value):
    relationship = {
        "trust": 0.0,
        "state": "neutral",
        "diagnostics": {
            "severity": 0.0,
            "delta": 0.0,
            "pressure": "stable",
            "direction": "stable",
        },
    }

    with pytest.raises(ValueError):
        interpret_relationship(
            npc="guard",
            relationship=relationship,
            temperament={
                "name": "broken",
                "anxiety": bad_value,
            },
        )


@pytest.mark.parametrize("bad_value", BAD_FLOATS)
def test_temperament_relationship_input_rejects_non_finite_trust(bad_value):
    with pytest.raises(ValueError):
        interpret_relationship(
            npc="guard",
            relationship={
                "trust": bad_value,
                "state": "neutral",
                "diagnostics": {},
            },
            temperament="calm",
        )


@pytest.mark.parametrize("bad_value", BAD_FLOATS)
def test_temperament_relationship_input_rejects_non_finite_diagnostics(bad_value):
    with pytest.raises(ValueError):
        interpret_relationship(
            npc="guard",
            relationship={
                "trust": 0.0,
                "state": "neutral",
                "diagnostics": {
                    "severity": bad_value,
                    "delta": 0.0,
                },
            },
            temperament="calm",
        )

    with pytest.raises(ValueError):
        interpret_relationship(
            npc="guard",
            relationship={
                "trust": 0.0,
                "state": "neutral",
                "diagnostics": {
                    "severity": 0.0,
                    "delta": bad_value,
                },
            },
            temperament="calm",
        )


def test_agent_registry_validates_ids_and_returns_safe_copies():
    ctx = {}
    agents = AgentRegistry(ctx)

    live = agents.ensure(" player ")
    live["mood"] = 0.25

    read = agents.get("player")
    read["mood"] = 999.0

    assert agents.get("player")["mood"] == 0.25

    all_agents = agents.all()
    all_agents["player"]["mood"] = 888.0

    assert agents.get("player")["mood"] == 0.25

    with pytest.raises(ValueError):
        agents.ensure("")

    with pytest.raises(ValueError):
        agents.ensure("bad|id")


@pytest.mark.parametrize(
    "key,bad_value",
    [
        ("pos_gain", float("inf")),
        ("neg_gain", float("nan")),
        ("pos_decay", 1.1),
        ("neg_decay", -0.1),
        ("max_reservoir", 0.0),
        ("volatility", float("-inf")),
        ("positive_volatility", -0.1),
        ("negative_volatility", float("nan")),
        ("maturity_gain", 1.1),
        ("maturity_cap", -0.1),
    ],
)
def test_relationship_graph_rejects_bad_constructor_params(key, bad_value):
    with pytest.raises(ValueError):
        GhostEngine(
            {
                key: bad_value,
            }
        )


@pytest.mark.parametrize(
    "key,bad_value",
    [
        ("pos_decay", 1.1),
        ("neg_decay", -0.1),
        ("max_reservoir", 0.0),
        ("volatility", float("inf")),
        ("maturity_cap", 1.1),
    ],
)
def test_relationship_set_params_rejects_bad_values(key, bad_value):
    engine = GhostEngine()

    with pytest.raises(ValueError):
        engine.relationships.set_params(
            "player",
            "shopkeeper",
            **{
                key: bad_value,
            },
        )


def test_valid_public_numeric_boundaries_remain_strict_json_safe():
    api = GhostAPI()

    packet = api.apply_event(
        "player",
        "shopkeeper",
        {
            "type": "betrayal",
            "intensity": 1.0,
        },
    )

    world = api.apply_world_effects(
        {
            "pressure_delta": 0.5,
            "fear_delta": 0.25,
            "order_delta": -0.10,
            "commerce_delta": -0.05,
            "resentment_delta": 0.20,
        }
    )

    temperament = api.interpret_npc_relationship(
        npc="guard",
        source="player",
        target="shopkeeper",
        temperament="volatile",
    )

    assert packet["mode"] == "canonical_relationship_event"
    assert world["status"] in ("normal", "tense", "crisis")
    assert temperament["temperament"] == "volatile"

    assert_strict_json_safe(packet)
    assert_strict_json_safe(world)
    assert_strict_json_safe(temperament)
