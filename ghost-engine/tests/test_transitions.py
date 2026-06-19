import json
import math

from ghost import GhostAPI


def assert_strict_json_safe(packet):
    json.dumps(packet, allow_nan=False)


def normalize_transition(transition):
    if isinstance(transition, dict):
        return transition.get("from"), transition.get("to")

    if isinstance(transition, (list, tuple)) and len(transition) == 2:
        return transition[0], transition[1]

    raise AssertionError(f"Invalid transition shape: {transition!r}")


def test_transition_sequence_exposes_valid_public_transition_packets():
    ghost = GhostAPI()

    sequence = [
        ("betrayal", 1.0),
        ("help", 1.0),
        ("help", 1.0),
        ("help", 1.0),
        ("betrayal", 1.0),
    ]

    transitions = []

    for event_type, intensity in sequence:
        packet = ghost.apply_event(
            "A",
            "B",
            {
                "type": event_type,
                "intensity": intensity,
            },
        )

        relationship = ghost.get_relationship("A", "B")

        assert packet["relationship"] == relationship
        assert relationship["state"] in {"hostile", "neutral", "friendly"}
        assert math.isfinite(relationship["trust"])

        if relationship["transition"]:
            from_state, to_state = normalize_transition(
                relationship["transition"]
            )

            assert from_state in {"hostile", "neutral", "friendly"}
            assert to_state in {"hostile", "neutral", "friendly"}

            transitions.append(
                {
                    "from": from_state,
                    "to": to_state,
                }
            )

        if relationship["trigger"]:
            assert "event" in relationship["trigger"]

        assert_strict_json_safe(packet)
        assert_strict_json_safe(relationship)

    assert transitions
    assert any(item["to"] == "hostile" for item in transitions)
