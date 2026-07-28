"""Boundary and normalization contracts for scenario configuration."""

from __future__ import annotations

import json

import pytest

from ghost.scenario import (
    load_scenario_config,
    validate_scenario_config,
)


def valid_config() -> dict:
    return {
        "scenario_id": "market_trust_demo",
        "npc_roles": {
            "shopkeeper": "shopkeeper",
            "guard": "guard",
            "elder": "town_elder",
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
        },
        "relationships": [
            {
                "source": "shopkeeper",
                "target": "guard",
                "trust": 0.30,
            },
        ],
        "propagation_weights": {
            "guard": 1.0,
            "town_elder": 0.70,
        },
        "economy": {
            "base_prices": {
                "bread": 10,
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
        ],
        "fail_conditions": [
            "guard_arrests_player",
        ],
    }


def replace_path(
    config: dict,
    path: tuple,
    value,
) -> None:
    container = config

    for key in path[:-1]:
        container = container[key]

    container[path[-1]] = value


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (
            ("scenario_id",),
            None,
            "scenario_id must be a string",
        ),
        (
            ("scenario_id",),
            "   ",
            "scenario_id must not be empty",
        ),
        (
            ("npc_roles",),
            {},
            "npc_roles must contain at least one role",
        ),
        (
            ("npcs", "shopkeeper", "temperament"),
            {},
            "temperament vector must not be empty",
        ),
        (
            ("npcs", "shopkeeper", "temperament"),
            [],
            "temperament must be a preset string or vector dict",
        ),
        (
            ("npcs", "shopkeeper", "personality"),
            7,
            "personality must be a string",
        ),
        (
            ("relationships",),
            {},
            "relationships must be a list",
        ),
        (
            ("relationships", 0, "target"),
            "shopkeeper",
            "cannot target itself",
        ),
        (
            ("relationships", 0, "source"),
            "missing",
            "source is unknown",
        ),
        (
            ("relationships", 0, "trust"),
            1.01,
            "trust must be in",
        ),
        (
            ("propagation_weights",),
            {"missing": 0.50},
            "propagation_weights references unknown NPC",
        ),
        (
            ("economy", "base_prices"),
            {},
            "economy.base_prices must contain at least one item",
        ),
        (
            ("quest", "trust_required"),
            1.01,
            "quest.trust_required must be in",
        ),
        (
            ("quest", "pressure_max"),
            5.01,
            "quest.pressure_max must be in",
        ),
        (
            ("thresholds", "pressure_crisis"),
            -0.01,
            "thresholds.pressure_crisis must be in",
        ),
        (
            ("quest", "pressure_max"),
            3.50,
            "quest.pressure_max must be lower than",
        ),
        (
            ("win_conditions",),
            [],
            "win_conditions must contain at least one condition",
        ),
        (
            ("win_conditions",),
            ["same", "same"],
            "win_conditions must not contain duplicates",
        ),
    ],
)
def test_scenario_config_rejects_reachable_invalid_boundaries(
    path,
    value,
    message,
):
    config = valid_config()
    replace_path(config, path, value)

    with pytest.raises(ValueError, match=message):
        validate_scenario_config(config)


def test_scenario_config_rejects_non_dict_root():
    with pytest.raises(
        ValueError,
        match="scenario config must be a dict",
    ):
        validate_scenario_config([])


def test_scenario_config_rejects_missing_role_npc():
    config = valid_config()
    del config["npcs"]["shopkeeper"]

    with pytest.raises(
        ValueError,
        match="npcs is missing role NPC: shopkeeper",
    ):
        validate_scenario_config(config)


def test_scenario_config_normalizes_and_deep_copies_caller_data():
    config = valid_config()

    config["scenario_id"] = "  market_trust_demo  "

    config["npc_roles"] = {
        " shopkeeper ": " shopkeeper ",
        " guard ": " guard ",
        " elder ": " town_elder ",
    }

    config["npcs"]["town_elder"]["temperament"] = {
        " warmth ": 0.70,
        " suspicion ": 0.30,
    }

    loaded = load_scenario_config(config)

    assert loaded["scenario_id"] == "market_trust_demo"

    assert loaded["npc_roles"] == {
        "shopkeeper": "shopkeeper",
        "guard": "guard",
        "elder": "town_elder",
    }

    assert loaded["npcs"]["town_elder"]["temperament"] == {
        "warmth": 0.70,
        "suspicion": 0.30,
    }

    loaded["npcs"]["town_elder"]["temperament"][
        "warmth"
    ] = 0.0

    loaded["relationships"][0]["trust"] = -1.0

    loaded["economy"]["base_prices"]["bread"] = 999.0

    assert config["npcs"]["town_elder"]["temperament"] == {
        " warmth ": 0.70,
        " suspicion ": 0.30,
    }

    assert config["relationships"][0]["trust"] == 0.30

    assert config["economy"]["base_prices"]["bread"] == 10

    json.dumps(loaded, sort_keys=True)
