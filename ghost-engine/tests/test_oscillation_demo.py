import json
import math

from ghost.engine import GhostEngine


def assert_strict_json_safe(packet):
    json.dumps(packet, allow_nan=False)


def run_sequence(engine, sequence):
    results = []

    for value in sequence:
        engine.relationships.apply_delta(
            "Alice",
            "Bob",
            {
                "trust": value,
            },
        )
        relationship = engine.relationships.get("Alice", "Bob")
        results.append(relationship["trust"])

    return results


def test_oscillation_sequence_is_deterministic_and_bounded():
    sequence = [-0.3, 0.3] * 10

    engine_a = GhostEngine()
    engine_b = GhostEngine()

    results_a = run_sequence(engine_a, sequence)
    results_b = run_sequence(engine_b, list(sequence))

    assert results_a == results_b
    assert len(results_a) == len(sequence)

    for value in results_a:
        assert math.isfinite(value)
        assert -5.0 <= value <= 5.0

    assert_strict_json_safe(engine_a.snapshot())
