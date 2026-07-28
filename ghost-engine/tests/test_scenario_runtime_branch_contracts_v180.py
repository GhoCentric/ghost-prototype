"""Branch contracts for ScenarioRuntime behavior."""

from __future__ import annotations

from copy import deepcopy

import pytest

from ghost.scenario_runtime import (
    ScenarioRuntime,
    _copy_effects,
)


def valid_config() -> dict:
    return {
        "scenario_id": "scenario_runtime_branch_contracts",
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
                "temperament": "calm",
            },
        },
        "relationships": [],
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
        ],
        "fail_conditions": [
            "guard_arrests_player",
            "town_expels_player",
        ],
    }


def fingerprint(runtime: ScenarioRuntime) -> dict:
    return {
        "api": runtime.api.snapshot(),
        "warning_count": runtime.warning_count,
        "arrest_count": runtime.arrest_count,
        "served_punishment": runtime.served_punishment,
        "resistance_remaining": runtime.resistance_remaining,
        "quest_completed": runtime.quest_completed,
        "price_records": deepcopy(runtime.price_records),
    }


@pytest.mark.parametrize(
    ("action", "message"),
    [
        (
            {
                "type": [],
                "target": "shopkeeper",
            },
            "action.type must be a string",
        ),
        (
            {
                "type": "   ",
                "target": "shopkeeper",
            },
            "action.type must not be empty",
        ),
        (
            {
                "type": "help",
                "target": [],
            },
            "action.target must be a string",
        ),
        (
            {
                "type": "help",
                "target": "   ",
            },
            "action.target must not be empty",
        ),
    ],
)
def test_invalid_action_fields_are_rejected_atomically(
    action,
    message,
):
    runtime = ScenarioRuntime(valid_config())
    before = fingerprint(runtime)

    with pytest.raises(ValueError, match=message):
        runtime.resolve_action(action)

    assert fingerprint(runtime) == before


def test_unknown_world_effect_action_is_rejected():
    with pytest.raises(
        ValueError,
        match="unsupported scenario action: not_an_action",
    ):
        _copy_effects("not_an_action", 1.0)


def test_direct_npc_id_neutral_action_skips_world_mutation():
    runtime = ScenarioRuntime(valid_config())
    before_world = deepcopy(runtime.api.world_state())

    packet = runtime.resolve_action(
        {
            "type": "neutral",
            "target": "town_elder",
        }
    )

    assert packet["action"]["type"] == "neutral"
    assert packet["action"]["target"] == "town_elder"
    assert packet["world_effects"]["applied"] == {}
    assert runtime.api.world_state() == before_world


def test_greet_has_social_result_without_direct_world_effects():
    runtime = ScenarioRuntime(valid_config())
    before_world = deepcopy(runtime.api.world_state())

    packet = runtime.resolve_action(
        {
            "type": "greet",
            "target": "shopkeeper",
        }
    )

    assert packet["propagation"]["event"] == "greet"
    assert packet["world_effects"]["applied"] == {}
    assert runtime.api.world_state() == before_world


def test_town_status_uses_configured_crisis_and_expulsion_thresholds():
    config = valid_config()
    config["quest"]["pressure_max"] = 0.04
    config["thresholds"]["pressure_crisis"] = 0.05
    config["thresholds"]["pressure_expulsion"] = 0.20

    runtime = ScenarioRuntime(config)

    runtime.api.apply_world_effects(
        {
            "pressure_delta": 0.10,
        }
    )

    assert runtime._town_status() == "crisis"

    runtime.api.apply_world_effects(
        {
            "pressure_delta": 0.10,
        }
    )

    assert runtime._town_status() == "expelled"


def test_betrayal_detention_updates_punishment_state():
    runtime = ScenarioRuntime(valid_config())

    packet = runtime.resolve_action(
        {
            "type": "betrayal",
            "target": "shopkeeper",
        }
    )

    assert packet["law"]["action"] == "detain"
    assert runtime.served_punishment is True
    assert runtime.arrest_count == 1
