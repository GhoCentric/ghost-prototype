import json

import pytest

from ghost.scenario_runtime import ScenarioRuntime


def valid_config():
    return {
        "scenario_id": "market_trust_demo",
        "npc_roles": {
            "shopkeeper": "shopkeeper",
            "guard": "guard",
            "elder": "town_elder",
            "rival": "rival_merchant",
            "witness": "witness",
        },
        "npcs": {
            "shopkeeper": {
                "personality": "resentful",
                "temperament": "resentful",
            },
            "guard": {
                "personality": "balanced",
                "temperament": "suspicious",
            },
            "town_elder": {
                "personality": "forgiving",
                "temperament": "calm",
            },
            "rival_merchant": {
                "personality": "volatile",
                "temperament": "volatile",
            },
            "witness": {
                "personality": "balanced",
                "temperament": "calm",
            },
        },
        "relationships": [
            {
                "source": "shopkeeper",
                "target": "guard",
                "trust": 0.30,
            },
            {
                "source": "guard",
                "target": "town_elder",
                "trust": 0.20,
            },
        ],
        "propagation_weights": {
            "guard": 1.0,
            "town_elder": 0.70,
            "rival_merchant": 0.50,
            "witness": 0.35,
        },
        "economy": {
            "base_prices": {
                "bread": 10,
                "fruit": 8,
            },
        },
        "quest": {
            "trust_required": 0.20,
            "pressure_max": 1.25,
        },
        "thresholds": {
            "pressure_crisis": 2.0,
            "pressure_expulsion": 3.5,
            "arrest_severity": 0.85,
        },
        "win_conditions": [
            "restore_shopkeeper_trust",
            "complete_market_quest",
        ],
        "fail_conditions": [
            "guard_arrests_player",
            "town_expels_player",
        ],
    }


def test_runtime_seeds_scenario_relationships():
    runtime = ScenarioRuntime(valid_config())

    relationship = runtime.api.get_relationship(
        "shopkeeper",
        "guard",
    )

    assert relationship["trust"] == 0.30


def test_resolve_action_returns_complete_packet():
    runtime = ScenarioRuntime(valid_config())

    packet = runtime.resolve_action(
        {
            "type": "help",
            "target": "shopkeeper",
            "item": "bread",
        }
    )

    assert set(packet) == {
        "scenario_id",
        "action",
        "relationship",
        "propagation",
        "world_effects",
        "commerce",
        "law",
        "quest",
        "reintegration",
        "win_fail",
        "snapshot",
    }

    assert packet["action"]["type"] == "help"
    assert packet["action"]["target"] == "shopkeeper"
    assert packet["commerce"]["price"]["item"] == "bread"
    assert packet["quest"]["available"] is False

    json.dumps(packet, sort_keys=True)


def test_negative_action_propagates_and_changes_world():
    runtime = ScenarioRuntime(valid_config())

    packet = runtime.resolve_action(
        {
            "type": "steal",
            "target": "shopkeeper",
            "item": "bread",
        }
    )

    assert packet["action"]["type"] == "theft"
    assert packet["propagation"]["event"] == "theft"
    assert packet["propagation"]["propagated"]
    assert packet["world_effects"]["applied"]["pressure_delta"] > 0
    assert packet["law"]["severity"] > 0


def test_runtime_is_deterministic_for_same_config_and_action():
    left = ScenarioRuntime(valid_config())
    right = ScenarioRuntime(valid_config())

    action = {
        "type": "threat",
        "target": "shopkeeper",
        "item": "fruit",
    }

    assert left.resolve_action(action) == right.resolve_action(action)


def test_quest_completion_requires_available_quest():
    runtime = ScenarioRuntime(valid_config())

    runtime.resolve_action(
        {
            "type": "help",
            "target": "shopkeeper",
        }
    )

    runtime.resolve_action(
        {
            "type": "help",
            "target": "shopkeeper",
        }
    )

    runtime.resolve_action(
        {
            "type": "help",
            "target": "shopkeeper",
        }
    )

    packet = runtime.resolve_action(
        {
            "type": "complete_quest",
            "target": "shopkeeper",
        }
    )

    assert packet["quest"]["completed"] is True
    assert "complete_market_quest" in packet["win_fail"]["won"]


def test_unknown_item_and_target_are_rejected():
    runtime = ScenarioRuntime(valid_config())

    with pytest.raises(ValueError):
        runtime.resolve_action(
            {
                "type": "help",
                "target": "missing",
            }
        )

    with pytest.raises(ValueError):
        runtime.resolve_action(
            {
                "type": "help",
                "target": "shopkeeper",
                "item": "sword",
            }
        )
