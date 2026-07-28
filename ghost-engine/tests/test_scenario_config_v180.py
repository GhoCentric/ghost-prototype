import json

import pytest

from ghost.scenario import (
    load_scenario_config,
    validate_scenario_config,
)


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
                "temperament": {
                    "warmth": 0.70,
                    "suspicion": 0.30,
                },
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
            "trust_required": 0.25,
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


def test_valid_scenario_config_is_normalized_and_json_safe():
    config = valid_config()

    loaded = load_scenario_config(config)

    assert loaded == validate_scenario_config(config)
    assert loaded is not config
    assert loaded["economy"]["base_prices"]["bread"] == 10.0

    json.dumps(loaded, sort_keys=True)


def test_duplicate_role_assignment_is_rejected():
    config = valid_config()
    config["npc_roles"]["guard"] = "shopkeeper"

    with pytest.raises(ValueError):
        validate_scenario_config(config)


def test_unknown_relationship_npc_is_rejected():
    config = valid_config()
    config["relationships"][0]["target"] = "missing_npc"

    with pytest.raises(ValueError):
        validate_scenario_config(config)


def test_invalid_price_and_weight_are_rejected():
    config = valid_config()
    config["economy"]["base_prices"]["bread"] = 0

    with pytest.raises(ValueError):
        validate_scenario_config(config)

    config = valid_config()
    config["propagation_weights"]["guard"] = 1.5

    with pytest.raises(ValueError):
        validate_scenario_config(config)


def test_impossible_threshold_ordering_is_rejected():
    config = valid_config()
    config["thresholds"]["pressure_crisis"] = 3.5
    config["thresholds"]["pressure_expulsion"] = 3.5

    with pytest.raises(ValueError):
        validate_scenario_config(config)


def test_overlapping_win_fail_conditions_are_rejected():
    config = valid_config()
    config["fail_conditions"].append(
        "restore_shopkeeper_trust"
    )

    with pytest.raises(ValueError):
        validate_scenario_config(config)
