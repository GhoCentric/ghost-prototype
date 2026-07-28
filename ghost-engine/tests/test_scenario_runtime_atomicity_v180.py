"""Atomic public-action contracts for ScenarioRuntime."""

from __future__ import annotations

from copy import deepcopy

import pytest

from ghost.scenario_runtime import ScenarioRuntime


def valid_config() -> dict:
    return {
        "scenario_id": "scenario_runtime_atomicity",
        "npc_roles": {
            "shopkeeper": "shopkeeper",
            "guard": "guard",
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
        },
        "relationships": [],
        "propagation_weights": {
            "guard": 1.0,
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


def test_rejected_quest_completion_is_fully_atomic():
    runtime = ScenarioRuntime(valid_config())
    before = fingerprint(runtime)

    with pytest.raises(
        ValueError,
        match="quest cannot be completed while unavailable",
    ):
        runtime.resolve_action(
            {
                "type": "complete_quest",
                "target": "shopkeeper",
            }
        )

    assert fingerprint(runtime) == before


@pytest.mark.parametrize(
    ("action", "message"),
    [
        (
            [],
            "action must be a dict",
        ),
        (
            {
                "type": "dance",
                "target": "shopkeeper",
            },
            "unsupported scenario action: dance",
        ),
        (
            {
                "type": "help",
                "target": "missing_npc",
            },
            "action.target is not a scenario role or NPC",
        ),
    ],
)
def test_rejected_public_actions_restore_every_mutable_component(
    action,
    message,
):
    runtime = ScenarioRuntime(valid_config())
    before = fingerprint(runtime)

    with pytest.raises(ValueError, match=message):
        runtime.resolve_action(action)

    assert fingerprint(runtime) == before


def test_successful_action_commits_instead_of_rolling_back():
    runtime = ScenarioRuntime(valid_config())
    before = fingerprint(runtime)

    packet = runtime.resolve_action(
        {
            "type": "help",
            "target": "shopkeeper",
        }
    )

    after = fingerprint(runtime)

    assert packet["action"]["type"] == "help"
    assert packet["relationship"]["trust"] > 0.0
    assert after != before
    assert after["api"] == packet["snapshot"]
