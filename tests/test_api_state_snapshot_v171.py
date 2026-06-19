import json

from ghost import GhostAPI


def test_ghostapi_state_is_live_mutable_engine_state():
    api = GhostAPI()

    live_state = api.state()
    live_state["v171_live_marker"] = "present"

    assert api.state()["v171_live_marker"] == "present"


def test_ghostapi_snapshot_is_json_safe_copy_with_metadata():
    api = GhostAPI()

    api.state()["v171_snapshot_marker"] = {
        "nested": ["safe", "copy"],
    }

    snapshot = api.snapshot()

    assert snapshot["ghost_version"]
    assert snapshot["schema_version"]
    assert "engine" in snapshot
    assert "world" in snapshot

    json.dumps(snapshot)

    snapshot["engine"]["v171_snapshot_marker"]["nested"].append("mutated")

    fresh_snapshot = api.snapshot()

    assert fresh_snapshot["engine"]["v171_snapshot_marker"]["nested"] == [
        "safe",
        "copy",
    ]


def test_ghostapi_snapshot_exposes_engine_snapshot_metadata_too():
    api = GhostAPI()

    snapshot = api.snapshot()
    engine_snapshot = snapshot["engine"]

    assert engine_snapshot["ghost_version"] == snapshot["ghost_version"]
    assert engine_snapshot["schema_version"] == snapshot["schema_version"]
