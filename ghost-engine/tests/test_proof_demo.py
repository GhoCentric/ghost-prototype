import json
import math

from ghost import GhostAPI


def assert_strict_json_safe(packet):
    json.dumps(packet, allow_nan=False)


def baseline_step(previous, value, alpha=0.2):
    trust = previous * (1 - alpha) + value * alpha
    return max(min(trust, 1.0), -1.0)


def test_proof_demo_emotional_inertia_contract():
    ghost = GhostAPI()

    sequence = [
        ("help", 0.3),
        ("help", 0.3),
        ("insult", -0.5),
        ("help", 0.3),
        ("help", 0.3),
        ("betrayal", -1.0),
        ("help", 0.3),
    ]

    baseline = 0.0
    ghost_values = []

    for event_type, value in sequence:
        baseline = baseline_step(baseline, value)

        packet = ghost.apply_event(
            "Player",
            "Villager",
            {
                "type": event_type,
                "intensity": abs(value),
            },
        )

        relationship_before_tick = ghost.get_relationship(
            "Player",
            "Villager",
        )

        assert packet["relationship"] == relationship_before_tick

        tick_packet = ghost.tick()

        relationship_after_tick = ghost.get_relationship(
            "Player",
            "Villager",
        )

        assert relationship_after_tick["state"] in {
            "hostile",
            "neutral",
            "friendly",
        }
        assert math.isfinite(relationship_after_tick["trust"])

        assert_strict_json_safe(packet)
        assert_strict_json_safe(tick_packet)
        assert_strict_json_safe(relationship_before_tick)
        assert_strict_json_safe(relationship_after_tick)

        ghost_values.append(relationship_after_tick["trust"])

    assert min(ghost_values) < 0.0
    assert ghost_values[-1] <= baseline
