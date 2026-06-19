import json
import math

from ghost import GhostAPI


def assert_strict_json_safe(packet):
    json.dumps(packet, allow_nan=False)


def test_simple_demo_sequence_has_stable_public_packets():
    ghost = GhostAPI()

    sequence = [
        "insult",
        "insult",
        "insult",
        "help",
        "help",
    ]

    states = []
    trusts = []

    for event in sequence:
        event_packet = ghost.apply_event(
            "A",
            "B",
            {
                "type": event,
            },
        )
        tick_packet = ghost.tick()
        relationship = ghost.get_relationship("A", "B")

        assert event_packet["mode"] == "canonical_relationship_event"
        assert tick_packet["event"] == "tick"
        assert relationship["state"] in {"hostile", "neutral", "friendly"}
        assert math.isfinite(relationship["trust"])

        assert_strict_json_safe(event_packet)
        assert_strict_json_safe(tick_packet)
        assert_strict_json_safe(relationship)

        states.append(relationship["state"])
        trusts.append(relationship["trust"])

    assert len(states) == len(sequence)
    assert len(trusts) == len(sequence)
    assert min(trusts) < 0.0
