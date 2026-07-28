"""Behavior contracts for Ghost's explicit WorldRuntime."""

from __future__ import annotations

import pytest

from ghost.world import TownMood, WorldRuntime


def test_town_mood_rejects_non_dict_effects_atomically():
    mood = TownMood()
    before = mood.to_dict()

    with pytest.raises(
        ValueError,
        match="world effects must be a dict",
    ):
        mood.apply([])

    assert mood.to_dict() == before


def test_world_event_history_is_bounded_to_latest_twenty_five():
    world = WorldRuntime()

    for index in range(26):
        world.record_event(
            "coverage_event",
            details={"index": index},
        )

    assert len(world.events) == 25
    assert world.events[0]["details"] == {"index": 1}
    assert world.events[-1]["details"] == {"index": 25}


def test_world_runtime_rejects_non_dict_effects_atomically():
    world = WorldRuntime()
    before = world.to_dict()

    with pytest.raises(
        ValueError,
        match="world effects must be a dict",
    ):
        world.apply_effects(["bad"])

    assert world.to_dict() == before


def test_apply_effects_enters_crisis_at_pressure_threshold():
    world = WorldRuntime()

    world.apply_effects(
        {
            "pressure_delta": 2.0,
            "fear_delta": 0.25,
        }
    )

    assert world.global_pressure == pytest.approx(2.0)
    assert world.status == "crisis"
    assert world.mood.fear == pytest.approx(0.25)


@pytest.mark.parametrize(
    ("starting_pressure", "expected_pressure", "status"),
    [
        (0.5, 0.49, "normal"),
        (1.1, 1.078, "tense"),
        (2.1, 2.058, "crisis"),
    ],
)
def test_tick_recalculates_status_from_decayed_pressure(
    starting_pressure,
    expected_pressure,
    status,
):
    world = WorldRuntime(global_pressure=starting_pressure)

    world.tick()

    assert world.global_pressure == pytest.approx(
        expected_pressure
    )
    assert world.status == status


def test_social_propagation_applies_effects_and_records_evidence():
    world = WorldRuntime()

    effects = world.propagate_social_effect(
        "market_theft",
        faction_heat=0.5,
    )

    assert effects == {
        "pressure_delta": 0.05,
        "fear_delta": 0.02,
        "resentment_delta": 0.02,
        "order_delta": -0.01,
    }

    assert world.global_pressure == pytest.approx(0.05)
    assert world.mood.fear == pytest.approx(0.02)
    assert world.mood.resentment == pytest.approx(0.02)
    assert world.mood.order == pytest.approx(0.49)

    assert world.events[-1] == {
        "type": "social_propagation",
        "actor": "",
        "target": "",
        "details": {
            "source_event": "market_theft",
            "heat": 0.5,
            "effects": effects,
        },
    }


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            [],
            "world snapshot must be a dict",
        ),
        (
            {"mood": []},
            "world snapshot mood must be a dict",
        ),
        (
            {"events": {}},
            "world snapshot events must be a list",
        ),
        (
            {"events": [{"valid": True}, "bad"]},
            "world snapshot events must contain only dicts",
        ),
        (
            {"global_pressure": 5.1},
            "world snapshot global pressure must be in",
        ),
    ],
)
def test_from_dict_rejects_invalid_public_snapshot_shapes(
    payload,
    message,
):
    with pytest.raises(ValueError, match=message):
        WorldRuntime.from_dict(payload)


@pytest.mark.parametrize(
    ("pressure", "expected_status"),
    [
        (0.25, "normal"),
        (1.0, "tense"),
        (2.0, "crisis"),
    ],
)
def test_from_dict_recalculates_status_from_pressure(
    pressure,
    expected_status,
):
    restored = WorldRuntime.from_dict(
        {
            "mood": {
                "fear": 0.0,
                "order": 0.5,
                "commerce": 1.0,
                "resentment": 0.0,
            },
            "events": [],
            "global_pressure": pressure,
            "status": "contradictory_saved_value",
        }
    )

    assert restored.global_pressure == pressure
    assert restored.status == expected_status
