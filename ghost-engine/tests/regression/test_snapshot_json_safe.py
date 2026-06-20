import json

import pytest

from ghost.engine import GhostEngine


def test_snapshot_json_safe_strict_mode():
    engine = GhostEngine()

    engine.step(
        {
            "source": "runtime",
            "intent": "threat",
            "actor": "a",
            "target": "b",
            "intensity": 0.5,
        }
    )

    snapshot = engine.snapshot()

    assert snapshot["ghost_version"] == "1.7.2"
    assert snapshot["schema_version"] == "1.7.2"

    json.dumps(snapshot, allow_nan=False)


def test_snapshot_rejects_non_finite_state_in_strict_mode():
    engine = GhostEngine()

    engine.state()["poison"] = float("inf")

    with pytest.raises(ValueError):
        engine.snapshot()
