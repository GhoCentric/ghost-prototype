import json
import math

from ghost import GhostAPI


def assert_strict_json_safe(packet):
    json.dumps(packet, allow_nan=False)


def run_ghost(personality=None):
    ghost = GhostAPI()

    if personality:
        ghost.engine.relationships.set_personality("A", "B", personality)

    sequence = [-0.3, 0.3] * 10
    results = []

    for value in sequence:
        event_type = "insult" if value < 0 else "help"

        packet = ghost.apply_event(
            "A",
            "B",
            {
                "type": event_type,
                "intensity": abs(value),
            },
        )

        ghost.engine.relationships.tick()

        relationship = ghost.get_relationship("A", "B")

        assert packet["mode"] == "canonical_relationship_event"
        assert_strict_json_safe(packet)
        assert_strict_json_safe(relationship)

        results.append(relationship["trust"])

    return results


def run_baseline():
    trust = 0.0
    results = []
    alpha = 0.2

    for value in [-0.3, 0.3] * 10:
        trust = trust * (1 - alpha) + value * alpha
        trust = max(min(trust, 1.0), -1.0)
        results.append(trust)

    return results


def test_oscillation_graph_data_contracts():
    baseline = run_baseline()

    assert len(baseline) == 20

    for value in baseline:
        assert math.isfinite(value)
        assert -1.0 <= value <= 1.0

    personality_results = {}

    for personality in ("balanced", "forgiving", "resentful", "volatile"):
        results = run_ghost(personality)
        personality_results[personality] = results

        assert len(results) == 20

        for value in results:
            assert math.isfinite(value)
            assert -5.0 <= value <= 5.0

    assert len({tuple(v) for v in personality_results.values()}) > 1
