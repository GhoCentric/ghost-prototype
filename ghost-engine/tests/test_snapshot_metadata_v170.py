import json

from ghost.engine import GhostEngine
from ghost.events import RelationshipEvent


def test_snapshot_contains_version_metadata():
    ghost = GhostEngine()

    snapshot = ghost.snapshot()

    assert snapshot["ghost_version"] == "1.7.3"
    assert snapshot["schema_version"] == "1.7.3"

    json.dumps(snapshot)


def test_snapshot_keeps_existing_engine_state_shape():
    ghost = GhostEngine()

    snapshot = ghost.snapshot()

    assert "cycles" in snapshot
    assert "input" in snapshot
    assert "last_step" in snapshot
    assert "npc" in snapshot
    assert "relationships" in snapshot
    assert "agents" in snapshot

    assert "threat_level" in snapshot["npc"]
    assert "last_intent" in snapshot["npc"]

    json.dumps(snapshot)


def test_snapshot_metadata_survives_after_relationship_event():
    ghost = GhostEngine()

    ghost.apply_event(
        "player",
        "shopkeeper",
        RelationshipEvent.BETRAYAL,
    )

    snapshot = ghost.snapshot()

    assert snapshot["ghost_version"] == "1.7.3"
    assert snapshot["schema_version"] == "1.7.3"

    assert "player|shopkeeper" in snapshot["relationships"]

    json.dumps(snapshot)


def test_snapshot_is_immutable_copy_not_live_state():
    ghost = GhostEngine()

    snapshot = ghost.snapshot()
    snapshot["npc"]["threat_level"] = 999

    live_state = ghost.state()

    assert live_state["npc"]["threat_level"] != 999


def test_snapshot_keeps_metadata_without_mutating_live_state():
    ghost = GhostEngine()

    snapshot = ghost.snapshot()
    live_state = ghost.state()

    assert "ghost_version" in snapshot
    assert "schema_version" in snapshot

    assert "ghost_version" not in live_state
    assert "schema_version" not in live_state


def test_snapshot_after_tick_is_json_safe_and_versioned():
    ghost = GhostEngine()

    ghost.apply_event(
        "player",
        "shopkeeper",
        RelationshipEvent.BETRAYAL,
    )

    ghost.tick()

    snapshot = ghost.snapshot()

    assert snapshot["ghost_version"] == "1.7.3"
    assert snapshot["schema_version"] == "1.7.3"

    json.dumps(snapshot)
