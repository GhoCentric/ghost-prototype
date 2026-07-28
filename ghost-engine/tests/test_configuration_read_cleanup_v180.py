from copy import deepcopy
import inspect

import pytest

from ghost.api import (
    DEFAULT_EVENT_MAP,
    GhostAPI,
)
from ghost.engine import GhostEngine
from ghost.world import WorldRuntime


def test_default_event_export_cannot_reconfigure_new_apis_v180(
    monkeypatch,
):
    expected = deepcopy(
        DEFAULT_EVENT_MAP
    )

    monkeypatch.setitem(
        DEFAULT_EVENT_MAP["help"],
        "trust",
        999.0,
    )

    api = GhostAPI()

    assert api.event_map == expected


def test_caller_event_map_is_copied_and_empty_map_is_authoritative_v180():
    custom = {
        "wave": {
            "trust": 0.25,
        },
    }

    api = GhostAPI(
        event_map=custom
    )

    custom["wave"]["trust"] = 1.0

    assert api.event_map == {
        "wave": {
            "trust": 0.25,
        },
    }

    empty = GhostAPI(
        event_map={}
    )

    assert empty.event_map == {}

    with pytest.raises(
        ValueError,
        match="Unknown event type",
    ):
        empty.apply_event(
            "player",
            "merchant",
            {
                "type": "help",
            },
        )


def test_caller_config_is_not_shared_with_engine_state_v180():
    config = {
        "custom_extension": {
            "enabled": True,
        },
    }

    api = GhostAPI(
        config=config
    )

    config["custom_extension"][
        "enabled"
    ] = False

    assert api.state()[
        "custom_extension"
    ]["enabled"] is True


def test_unknown_relationship_read_does_not_create_state_v180():
    engine = GhostEngine()
    before = engine.snapshot()

    relationship = engine.get_relationship(
        "player",
        "merchant",
    )

    assert relationship["trust"] == 0.0
    assert relationship["state"] == "neutral"
    assert engine.snapshot() == before
    assert engine.relationships.get(
        "player",
        "merchant",
    ) is None
    assert engine.relationships.neighbors(
        "player"
    ) == []


def test_existing_relationship_read_does_not_rewrite_storage_v180():
    engine = GhostEngine()

    engine.apply_event(
        "player",
        "merchant",
        "help",
    )

    before = engine.snapshot()

    packet = engine.get_relationship(
        "player",
        "merchant",
    )

    assert packet["trust"] > 0.0
    assert engine.snapshot() == before


def test_world_status_uses_one_authoritative_classifier_v180():
    apply_source = inspect.getsource(
        WorldRuntime.apply_effects
    )
    tick_source = inspect.getsource(
        WorldRuntime.tick
    )

    assert "_world_status_from_pressure" in apply_source
    assert "_world_status_from_pressure" in tick_source
    assert 'status = "crisis"' not in apply_source
    assert 'self.status = "crisis"' not in tick_source


def test_new_api_snapshots_do_not_emit_inert_transition_state_v180():
    api = GhostAPI()
    snapshot = api.snapshot()

    assert "transitions" not in snapshot
    assert not hasattr(
        api,
        "_transitions",
    )


def test_legacy_transition_state_is_validated_then_discarded_v180():
    snapshot = GhostAPI().snapshot()
    snapshot["transitions"] = {
        "obsolete": {
            "from": "neutral",
            "to": "friendly",
        },
    }

    restored = GhostAPI.from_snapshot(
        snapshot
    )

    assert "transitions" not in restored.snapshot()
    assert not hasattr(
        restored,
        "_transitions",
    )


def test_unused_api_relationship_configuration_aliases_are_retired_v180():
    assert not hasattr(
        GhostAPI,
        "STATE_THRESHOLDS",
    )
    assert not hasattr(
        GhostAPI,
        "APOLOGY_RECOVERY_FRACTION",
    )
