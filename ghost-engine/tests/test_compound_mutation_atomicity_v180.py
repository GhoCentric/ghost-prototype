from copy import deepcopy

import pytest

from ghost.engine import GhostEngine
from ghost.world import (
    TownMood,
    WorldRuntime,
)


def test_social_weights_are_prevalidated_before_direct_mutation_v180():
    engine = GhostEngine()

    before = deepcopy(
        engine.snapshot()
    )

    with pytest.raises(
        ValueError,
        match=(
            "social propagation weight "
            "for elder must be finite"
        ),
    ):
        engine.propagate_social_event(
            source="player",
            target="shopkeeper",
            event="betrayal",
            observers=[
                "guard",
                "elder",
            ],
            weights={
                "guard": 1.0,
                "elder": float("nan"),
            },
        )

    assert engine.snapshot() == before

    assert (
        engine
        .relationships
        .propagation_log()
        == []
    )

    assert engine.relationships.get(
        "player",
        "shopkeeper",
    ) is None

    assert engine.relationships.get(
        "player",
        "guard",
    ) is None


def test_social_observer_ids_are_prevalidated_before_mutation_v180():
    engine = GhostEngine()

    before = deepcopy(
        engine.snapshot()
    )

    with pytest.raises(
        ValueError,
        match=(
            "social observer id "
            "cannot contain"
        ),
    ):
        engine.propagate_social_event(
            source="player",
            target="shopkeeper",
            event="betrayal",
            observers=[
                "guard",
                "bad|observer",
            ],
            weights={
                "guard": 1.0,
            },
        )

    assert engine.snapshot() == before

    assert (
        engine
        .relationships
        .propagation_log()
        == []
    )


def test_social_propagation_rolls_back_late_runtime_failure_v180(
    monkeypatch,
):
    engine = GhostEngine()

    engine.apply_event(
        "player",
        "ally",
        "help",
    )

    engine.propagate_social_event(
        source="ally",
        target="merchant",
        event="greet",
        observers=["witness"],
    )

    before = deepcopy(
        engine.snapshot()
    )

    log_before = (
        engine
        .relationships
        .propagation_log()
    )

    graph = engine.relationships

    original = (
        graph._apply_social_delta
    )

    calls = {
        "count": 0,
    }

    def fail_second_observer(
        **kwargs,
    ):
        calls["count"] += 1

        if calls["count"] == 2:
            raise RuntimeError(
                "forced late observer failure"
            )

        return original(
            **kwargs
        )

    monkeypatch.setattr(
        graph,
        "_apply_social_delta",
        fail_second_observer,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "forced late observer failure"
        ),
    ):
        engine.propagate_social_event(
            source="player",
            target="shopkeeper",
            event="betrayal",
            observers=[
                "guard",
                "elder",
            ],
            weights={
                "guard": 1.0,
                "elder": 1.0,
            },
        )

    assert calls["count"] == 2

    assert engine.snapshot() == before

    assert (
        graph.propagation_log()
        == log_before
    )

    assert graph.get(
        "player",
        "shopkeeper",
    ) is None

    assert graph.get(
        "player",
        "guard",
    ) is None

    assert graph.get(
        "player",
        "elder",
    ) is None


def test_successful_social_propagation_still_commits_v180():
    engine = GhostEngine()

    before = deepcopy(
        engine.snapshot()
    )

    packet = engine.propagate_social_event(
        source="player",
        target="shopkeeper",
        event="betrayal",
        observers=[
            "guard",
            "elder",
        ],
        weights={
            "guard": 1.0,
            "elder": 0.5,
        },
    )

    assert engine.snapshot() != before

    assert packet["direct"]["trust"] < 0.0

    assert [
        item["affected"]
        for item in packet["propagated"]
    ] == [
        "guard",
        "elder",
    ]

    assert len(
        engine
        .relationships
        .propagation_log()
    ) == 1


def test_town_mood_rejects_late_invalid_effect_atomically_v180():
    mood = TownMood(
        fear=0.20,
        order=0.70,
        commerce=0.80,
        resentment=0.10,
    )

    before = mood.to_dict()

    with pytest.raises(
        ValueError,
        match=(
            "world effect resentment_delta "
            "must be finite"
        ),
    ):
        mood.apply(
            {
                "fear_delta": 0.20,
                "order_delta": -0.10,
                "commerce_delta": -0.20,
                "resentment_delta": (
                    float("nan")
                ),
            }
        )

    assert mood.to_dict() == before


def test_world_rejects_late_invalid_effect_atomically_v180():
    world = WorldRuntime(
        mood=TownMood(
            fear=0.20,
            order=0.70,
            commerce=0.80,
            resentment=0.10,
        ),
        global_pressure=0.80,
        status="normal",
    )

    before = world.to_dict()

    with pytest.raises(
        ValueError,
        match=(
            "world effect commerce_delta "
            "must be finite"
        ),
    ):
        world.apply_effects(
            {
                "pressure_delta": 0.50,
                "fear_delta": 0.20,
                "order_delta": -0.10,
                "commerce_delta": (
                    float("nan")
                ),
                "resentment_delta": 0.30,
            }
        )

    assert world.to_dict() == before


def test_valid_world_effect_bundle_commits_together_v180():
    world = WorldRuntime(
        mood=TownMood(
            fear=0.20,
            order=0.70,
            commerce=0.80,
            resentment=0.10,
        ),
        global_pressure=0.80,
        status="normal",
    )

    world.apply_effects(
        {
            "pressure_delta": 0.50,
            "fear_delta": 0.20,
            "order_delta": -0.10,
            "commerce_delta": -0.20,
            "resentment_delta": 0.30,
        }
    )

    assert world.global_pressure == (
        pytest.approx(1.30)
    )

    assert world.status == "tense"

    assert world.mood.fear == (
        pytest.approx(0.40)
    )

    assert world.mood.order == (
        pytest.approx(0.60)
    )

    assert world.mood.commerce == (
        pytest.approx(0.60)
    )

    assert world.mood.resentment == (
        pytest.approx(0.40)
    )
