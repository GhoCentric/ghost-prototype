import json
from copy import deepcopy

import pytest

from ghost import GhostAPI


def apply_replay_sequence(api: GhostAPI):
    api.apply_event(
        "player",
        "shopkeeper",
        {"type": "threat"},
    )

    api.propagate_social_event(
        "player",
        "shopkeeper",
        "theft",
        observers=["guard"],
        weights={"guard": 1.0},
    )

    api.apply_world_effects(
        {
            "pressure_delta": 0.20,
            "fear_delta": 0.10,
            "resentment_delta": 0.05,
            "order_delta": -0.05,
            "commerce_delta": -0.02,
        }
    )

    api.tick()

    return api.snapshot()


def test_snapshot_restores_exact_public_state():
    api = GhostAPI()

    api.apply_event(
        "player",
        "shopkeeper",
        {"type": "help"},
    )

    api.apply_world_effects(
        {
            "pressure_delta": 0.30,
            "fear_delta": 0.10,
        }
    )

    snapshot = api.snapshot()
    restored = GhostAPI.from_snapshot(snapshot)

    assert restored.snapshot() == snapshot


def test_restored_api_replays_deterministically():
    original = GhostAPI()

    original.apply_event(
        "player",
        "shopkeeper",
        {"type": "help"},
    )

    original.apply_world_effects(
        {
            "pressure_delta": 0.15,
            "fear_delta": 0.05,
        }
    )

    checkpoint = original.snapshot()
    restored = GhostAPI.from_snapshot(checkpoint)

    original_final = apply_replay_sequence(original)
    restored_final = apply_replay_sequence(restored)

    assert original_final == restored_final


def test_restore_snapshot_mutates_existing_api_in_place():
    source = GhostAPI()

    source.apply_event(
        "player",
        "shopkeeper",
        {"type": "betrayal"},
    )

    source.apply_world_effects(
        {
            "pressure_delta": 0.80,
            "fear_delta": 0.20,
        }
    )

    snapshot = source.snapshot()

    target = GhostAPI()
    restored_snapshot = target.restore_snapshot(snapshot)

    assert restored_snapshot == snapshot
    assert target.snapshot() == snapshot


def test_snapshot_restore_rejects_invalid_packets():
    with pytest.raises(ValueError):
        GhostAPI.from_snapshot([])

    bad_engine = GhostAPI().snapshot()
    bad_engine["engine"] = []

    with pytest.raises(ValueError):
        GhostAPI.from_snapshot(bad_engine)

    bad_world = GhostAPI().snapshot()
    bad_world["world"]["mood"]["fear"] = 2.0

    with pytest.raises(ValueError):
        GhostAPI.from_snapshot(bad_world)

    bad_schema = GhostAPI().snapshot()
    bad_schema["schema_version"] = "not-supported"

    with pytest.raises(ValueError):
        GhostAPI.from_snapshot(bad_schema)


def test_snapshot_restore_stays_json_safe():
    api = GhostAPI()

    api.apply_event(
        "player",
        "shopkeeper",
        {"type": "help"},
    )

    restored = GhostAPI.from_snapshot(
        deepcopy(api.snapshot())
    )

    json.dumps(restored.snapshot(), sort_keys=True)
