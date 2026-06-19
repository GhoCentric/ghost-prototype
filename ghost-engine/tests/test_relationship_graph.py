import json

import pytest

from ghost.engine import GhostEngine


def assert_strict_json_safe(packet):
    json.dumps(packet, allow_nan=False)


def test_relationship_delta_updates_and_is_json_safe():
    engine = GhostEngine()

    relationship = engine.relationships.apply_delta(
        "Alice",
        "Bob",
        {
            "trust": 0.3,
        },
    )

    readback = engine.relationships.get("Alice", "Bob")

    assert readback["trust"] == 0.3
    assert relationship == readback

    assert_strict_json_safe(readback)


def test_relationship_pair_symmetry_and_safe_copies():
    engine = GhostEngine()

    engine.relationships.apply_delta(
        "Alice",
        "Bob",
        {
            "trust": 0.5,
        },
    )

    rel_1 = engine.relationships.get("Alice", "Bob")
    rel_2 = engine.relationships.get("Bob", "Alice")

    assert rel_1 == rel_2

    neighbors = engine.relationships.neighbors("Alice")
    neighbors.append("corruption")

    assert "corruption" not in engine.relationships.neighbors("Alice")

    relationships = engine.relationships.all()
    key = next(iter(relationships))
    relationships[key]["pos"] = 999.0

    assert engine.relationships.get("Alice", "Bob")["trust"] != 999.0


@pytest.mark.parametrize(
    "bad_delta",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_relationship_delta_rejects_non_finite_values(bad_delta):
    engine = GhostEngine()

    with pytest.raises(ValueError):
        engine.relationships.apply_delta(
            "Alice",
            "Bob",
            {
                "trust": bad_delta,
            },
        )


@pytest.mark.parametrize(
    "bad_id",
    [
        "",
        " ",
        "bad|id",
        None,
    ],
)
def test_relationship_graph_rejects_invalid_ids(bad_id):
    engine = GhostEngine()

    with pytest.raises(ValueError):
        engine.relationships.apply_delta(
            bad_id,
            "Bob",
            {
                "trust": 0.1,
            },
        )
