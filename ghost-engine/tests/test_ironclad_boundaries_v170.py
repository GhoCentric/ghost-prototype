import json
import math

import pytest

import ghost
from ghost.api import GhostAPI
from ghost.engine import (
    GHOST_SNAPSHOT_SCHEMA_VERSION,
    GHOST_VERSION,
    GhostEngine,
)
from ghost.events import RelationshipEvent


def assert_strict_json_safe(packet):
    json.dumps(packet, allow_nan=False)


def test_ghost_api_relationship_events_use_engine_canonical_packet():
    api = GhostAPI()

    packet = api.apply_event(
        "player",
        "shopkeeper",
        {
            "type": RelationshipEvent.INSULT,
        },
    )

    direct = api.engine.get_relationship(
        "player",
        "shopkeeper",
    )

    via_api = api.get_relationship(
        "player",
        "shopkeeper",
    )

    assert packet["mode"] == "canonical_relationship_event"
    assert packet["relationship"] == direct
    assert via_api == direct

    assert packet["state"] == direct["state"]
    assert packet["trust"] == direct["trust"]
    assert packet["diagnostics"] == direct["diagnostics"]


def test_ghost_api_legacy_delta_events_are_explicitly_marked():
    api = GhostAPI()

    packet = api.apply_event(
        "player",
        "shopkeeper",
        {
            "type": "cooperate",
        },
    )

    assert packet["mode"] == "legacy_delta_event"
    assert packet["relationship"] == api.get_relationship(
        "player",
        "shopkeeper",
    )


@pytest.mark.parametrize(
    "bad_value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_api_rejects_non_finite_event_intensity(bad_value):
    api = GhostAPI()

    with pytest.raises(ValueError):
        api.apply_event(
            "player",
            "shopkeeper",
            {
                "type": "help",
                "intensity": bad_value,
            },
        )


def test_api_rejects_negative_event_intensity():
    api = GhostAPI()

    with pytest.raises(ValueError):
        api.apply_event(
            "player",
            "shopkeeper",
            {
                "type": "help",
                "intensity": -1.0,
            },
        )


@pytest.mark.parametrize(
    "bad_value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_relationship_graph_rejects_non_finite_deltas(bad_value):
    engine = GhostEngine()

    with pytest.raises(ValueError):
        engine.relationships.apply_delta(
            "player",
            "shopkeeper",
            {
                "trust": bad_value,
            },
        )


@pytest.mark.parametrize(
    "bad_value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_social_propagation_rejects_non_finite_weights(bad_value):
    engine = GhostEngine()

    with pytest.raises(ValueError):
        engine.propagate_social_event(
            source="player",
            target="shopkeeper",
            event=RelationshipEvent.BETRAYAL,
            observers=["guard"],
            weights={
                "guard": bad_value,
            },
        )


def test_snapshot_is_strict_json_safe_after_many_events():
    engine = GhostEngine()

    for index in range(100):
        engine.apply_event(
            "player",
            f"npc_{index}",
            RelationshipEvent.BETRAYAL,
        )

    snapshot = engine.snapshot()

    assert snapshot["ghost_version"] == "1.7.5"
    assert snapshot["schema_version"] == "1.7.5"

    assert_strict_json_safe(snapshot)


def test_snapshot_rejects_non_finite_existing_state():
    engine = GhostEngine()

    engine.state()["poison"] = float("inf")

    with pytest.raises(ValueError):
        engine.snapshot()


def test_mixed_set_snapshot_is_still_json_safe():
    engine = GhostEngine(
        {
            "custom_set": {
                1,
                "a",
            },
        }
    )

    snapshot = engine.snapshot()

    assert snapshot["custom_set"] == ["a", 1]

    assert_strict_json_safe(snapshot)


def test_engine_context_is_detached_from_caller_dict():
    context = {
        "npc": {
            "threat_level": 0.0,
        }
    }

    engine = GhostEngine(context)

    context["npc"]["threat_level"] = 999.0

    assert engine.state()["npc"]["threat_level"] != 999.0


def test_neighbors_returns_safe_copy():
    engine = GhostEngine()

    engine.apply_event(
        "player",
        "shopkeeper",
        RelationshipEvent.HELP,
    )

    neighbors = engine.relationships.neighbors("player")
    neighbors.append("corruption")

    assert "corruption" not in engine.relationships.neighbors("player")


def test_relationships_all_returns_safe_copy():
    engine = GhostEngine()

    engine.apply_event(
        "player",
        "shopkeeper",
        RelationshipEvent.HELP,
    )

    relationships = engine.relationships.all()
    key = next(iter(relationships))

    relationships[key]["pos"] = 999.0

    live = engine.get_relationship(
        "player",
        "shopkeeper",
    )

    assert live["trust"] != 999.0


def test_version_constants_are_synced():
    assert ghost.__version__ == "1.7.5"
    assert GHOST_VERSION == "1.7.5"
    assert GHOST_SNAPSHOT_SCHEMA_VERSION == "1.7.5"


def test_engine_apply_event_accepts_intensity_without_breaking_schema():
    engine = GhostEngine()

    packet = engine.apply_event(
        "player",
        "shopkeeper",
        RelationshipEvent.BETRAYAL,
        intensity=0.5,
    )

    assert packet["diagnostics"]["event"] == "betrayal"
    assert packet["diagnostics"]["base_amount"] == 0.70
    assert packet["trust"] < 0.0

    assert_strict_json_safe(packet)
