from copy import deepcopy

import pytest

from ghost import GhostAPI
from ghost.engine import GhostEngine


class ConstructorBlockedEngine(
    GhostEngine
):
    def __init__(
        self,
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "engine constructor must not run "
            "during restoration"
        )


class ConstructorBlockedAPI(
    GhostAPI
):
    def __init__(
        self,
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "API constructor must not run "
            "during restoration"
        )


def test_engine_construction_keeps_configuration_behavior_v180():
    config = {
        "state": {
            "mood": 0.90,
        },
        "custom_set": {
            "a",
            1,
        },
    }

    engine = GhostEngine(
        config
    )

    config["state"]["mood"] = 0.10

    assert engine.state()[
        "state"
    ]["mood"] == 0.90

    assert engine.snapshot()[
        "custom_set"
    ] == [
        "a",
        1,
    ]


def test_engine_restoration_bypasses_constructor_v180():
    source = GhostEngine()

    source.apply_event(
        "player",
        "merchant",
        "betrayal",
    )

    snapshot = source.snapshot()

    restored = (
        ConstructorBlockedEngine
        .from_snapshot(
            deepcopy(
                snapshot
            )
        )
    )

    assert isinstance(
        restored,
        ConstructorBlockedEngine,
    )

    assert restored.snapshot() == snapshot


def test_engine_restoration_detaches_snapshot_input_v180():
    source = GhostEngine()

    source.apply_event(
        "player",
        "merchant",
        "help",
    )

    snapshot = source.snapshot()

    restored = (
        GhostEngine.from_snapshot(
            snapshot
        )
    )

    snapshot["relationships"][
        "merchant|player"
    ]["pos"] = 999.0

    assert restored.snapshot()[
        "relationships"
    ]["merchant|player"]["pos"] != 999.0


def test_engine_restoration_rejects_non_dict_boundary_v180():
    for invalid in (
        None,
        [],
        "snapshot",
        123,
    ):
        with pytest.raises(
            ValueError,
            match=(
                "engine snapshot must be a dict"
            ),
        ):
            GhostEngine.from_snapshot(
                invalid
            )


def test_api_restoration_bypasses_api_constructor_v180():
    source = GhostAPI()

    source.apply_event(
        "player",
        "merchant",
        {
            "type": "betrayal",
        },
    )

    source.apply_world_effects(
        {
            "pressure_delta": 0.40,
            "fear_delta": 0.10,
        }
    )

    snapshot = source.snapshot()

    restored = (
        ConstructorBlockedAPI
        .from_snapshot(
            deepcopy(
                snapshot
            )
        )
    )

    assert isinstance(
        restored,
        ConstructorBlockedAPI,
    )

    assert restored.snapshot() == snapshot


def test_api_restoration_uses_engine_restoration_boundary_v180(
    monkeypatch,
):
    source = GhostAPI()

    snapshot = source.snapshot()

    calls = {
        "count": 0,
    }

    original = (
        GhostEngine
        .from_snapshot
        .__func__
    )

    def tracked_from_snapshot(
        cls,
        engine_snapshot,
    ):
        calls["count"] += 1

        return original(
            cls,
            engine_snapshot,
        )

    monkeypatch.setattr(
        GhostEngine,
        "from_snapshot",
        classmethod(
            tracked_from_snapshot
        ),
    )

    restored = GhostAPI.from_snapshot(
        snapshot
    )

    assert calls["count"] == 1

    assert restored.snapshot() == snapshot


def test_in_place_restore_remains_exact_after_split_v180():
    source = GhostAPI()

    source.apply_event(
        "player",
        "merchant",
        {
            "type": "help",
        },
    )

    snapshot = source.snapshot()

    target = GhostAPI()

    assert target.restore_snapshot(
        snapshot
    ) == snapshot

    assert target.snapshot() == snapshot
