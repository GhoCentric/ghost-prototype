from copy import deepcopy

import pytest

from ghost.api import GhostAPI
from ghost.engine import GhostEngine
from ghost.scenario_runtime import ScenarioRuntime


def valid_config() -> dict:
    return {
        "scenario_id": "scenario_intensity_authority",
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


def _observer(packet: dict, npc_id: str) -> dict:
    for item in packet["propagated"]:
        if item["affected"] == npc_id:
            return item

    raise AssertionError(
        f"Missing propagated observer: {npc_id}"
    )


def test_social_intensity_controls_direct_observer_and_world_packets_v180():
    low_api = GhostAPI()
    high_api = GhostAPI()

    low = low_api.propagate_social_event(
        source="player",
        target="shopkeeper",
        event="betrayal",
        observers=["guard"],
        weights={"guard": 1.0},
        intensity=0.25,
    )

    high = high_api.propagate_social_event(
        source="player",
        target="shopkeeper",
        event="betrayal",
        observers=["guard"],
        weights={"guard": 1.0},
        intensity=1.0,
    )

    assert low["intensity"] == 0.25
    assert high["intensity"] == 1.0

    low_direct = low["direct"]["diagnostics"]
    high_direct = high["direct"]["diagnostics"]

    assert (
        low_direct["abs_delta"]
        < high_direct["abs_delta"]
    )

    assert (
        low_direct["severity"]
        < high_direct["severity"]
    )

    assert low["heat"] < high["heat"]

    low_guard = _observer(
        low,
        "guard",
    )

    high_guard = _observer(
        high,
        "guard",
    )

    assert abs(
        low_guard["trust_delta"]
    ) < abs(
        high_guard["trust_delta"]
    )

    for key in (
        "pressure_delta",
        "fear_delta",
        "resentment_delta",
        "order_delta",
        "guard_suspicion_delta",
    ):
        assert abs(
            low["world_effects"][key]
        ) < abs(
            high["world_effects"][key]
        )


def test_zero_social_intensity_has_zero_social_consequence_v180():
    api = GhostAPI()

    packet = api.propagate_social_event(
        source="player",
        target="shopkeeper",
        event="betrayal",
        observers=["guard"],
        weights={"guard": 1.0},
        intensity=0.0,
    )

    assert packet["intensity"] == 0.0
    assert packet["direct"]["trust"] == 0.0

    assert packet["direct"]["diagnostics"][
        "severity"
    ] == 0.0

    assert packet["heat"] == 0.0
    assert packet["propagated"] == []

    assert all(
        value == 0.0
        for value in packet[
            "world_effects"
        ].values()
    )

    assert api.engine.relationships.get(
        "player",
        "guard",
    ) is None


def test_scenario_intensity_controls_social_world_and_law_paths_v180():
    low_runtime = ScenarioRuntime(
        valid_config()
    )

    high_runtime = ScenarioRuntime(
        valid_config()
    )

    low = low_runtime.resolve_action(
        {
            "type": "threat",
            "target": "shopkeeper",
            "item": "bread",
            "intensity": 0.25,
        }
    )

    high = high_runtime.resolve_action(
        {
            "type": "threat",
            "target": "shopkeeper",
            "item": "bread",
            "intensity": 1.0,
        }
    )

    assert low["action"]["intensity"] == 0.25

    assert low["propagation"][
        "intensity"
    ] == 0.25

    assert high["propagation"][
        "intensity"
    ] == 1.0

    assert abs(
        low["relationship"]["trust"]
    ) < abs(
        high["relationship"]["trust"]
    )

    low_guard = _observer(
        low["propagation"],
        "guard",
    )

    high_guard = _observer(
        high["propagation"],
        "guard",
    )

    assert abs(
        low_guard["trust_delta"]
    ) < abs(
        high_guard["trust_delta"]
    )

    assert (
        low["propagation"]["heat"]
        < high["propagation"]["heat"]
    )

    assert low["world_effects"]["applied"][
        "pressure_delta"
    ] < high["world_effects"]["applied"][
        "pressure_delta"
    ]

    assert (
        low["law"]["severity"]
        < high["law"]["severity"]
    )


def test_manual_scenario_packets_preserve_validated_intensity_v180():
    runtime = ScenarioRuntime(
        valid_config()
    )

    packet = runtime.resolve_action(
        {
            "type": "neutral",
            "target": "shopkeeper",
            "intensity": 0.40,
        }
    )

    assert packet["action"][
        "intensity"
    ] == 0.40

    assert packet["propagation"][
        "intensity"
    ] == 0.40


def test_invalid_social_intensity_is_rejected_before_mutation_v180():
    for bad_intensity in (
        -0.01,
        1.01,
        float("nan"),
        float("inf"),
        float("-inf"),
    ):
        api = GhostAPI()
        before = deepcopy(
            api.snapshot()
        )

        with pytest.raises(ValueError):
            api.propagate_social_event(
                source="player",
                target="shopkeeper",
                event="betrayal",
                observers=["guard"],
                intensity=bad_intensity,
            )

        assert api.snapshot() == before


def test_engine_social_intensity_matches_public_api_v180():
    engine = GhostEngine()

    packet = engine.propagate_social_event(
        source="player",
        target="shopkeeper",
        event="insult",
        observers=["guard"],
        intensity=0.50,
    )

    assert packet["intensity"] == 0.50

    assert packet["direct"]["diagnostics"][
        "severity"
    ] > 0.0

    assert packet["propagated"]
