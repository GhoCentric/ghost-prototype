import json
import math

import pytest

from ghost.engine import GhostEngine


def assert_strict_json_safe(packet):
    json.dumps(packet, allow_nan=False)


def test_engine_sequence_is_deterministic_and_strict_json_safe():
    steps = [
        {
            "source": "npc_engine",
            "intent": "greet",
            "actor": "npc_1",
            "target": "npc_2",
            "intensity": 0.5,
        },
        {
            "source": "npc_engine",
            "intent": "help",
            "actor": "npc_2",
            "target": "npc_3",
            "intensity": 0.7,
        },
        {
            "source": "npc_engine",
            "intent": "threat",
            "actor": "npc_1",
            "target": "npc_2",
            "intensity": 0.6,
        },
    ]

    engine_a = GhostEngine()
    engine_b = GhostEngine()

    for step in steps:
        engine_a.step(step)
        engine_b.step(dict(step))

    snap_a = engine_a.snapshot()
    snap_b = engine_b.snapshot()

    assert snap_a == snap_b
    assert snap_a["cycles"] == 3
    assert snap_a["ghost_version"] == "1.7.3"
    assert snap_a["schema_version"] == "1.7.3"

    assert_strict_json_safe(snap_a)


def test_engine_step_clamps_large_positive_intensity():
    engine = GhostEngine()

    engine.step(
        {
            "source": "npc_engine",
            "intent": "threat",
            "actor": "npc_A",
            "target": "npc_B",
            "intensity": 5.0,
        }
    )

    snapshot = engine.snapshot()

    for agent_id in ("npc_A", "npc_B"):
        agent = snapshot["agents"][agent_id]

        assert 0.0 <= agent["mood"] <= 1.0
        assert 0.0 <= agent["tension"] <= 1.0

    assert 0.0 <= snapshot["npc"]["threat_level"] <= 1.0
    assert_strict_json_safe(snapshot)


@pytest.mark.parametrize(
    "bad_intensity",
    [
        -0.1,
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_engine_step_rejects_bad_intensity_without_poisoning_state(bad_intensity):
    engine = GhostEngine()

    with pytest.raises(ValueError):
        engine.step(
            {
                "source": "npc_engine",
                "intent": "threat",
                "actor": "npc_A",
                "target": "npc_B",
                "intensity": bad_intensity,
            }
        )

    snapshot = engine.snapshot()

    assert snapshot["cycles"] == 0
    assert_strict_json_safe(snapshot)
