import json
import math

from ghost import GhostAPI


def assert_strict_json_safe(packet):
    json.dumps(packet, allow_nan=False)


def test_api_demo_sequence_is_contract_checked():
    ghost = GhostAPI()

    sequence = [
        {"type": "insult", "intensity": 1.0},
        {"type": "help", "intensity": 1.0},
    ] * 5

    trust_values = []

    for event in sequence:
        packet = ghost.apply_event("Alice", "Bob", event)
        relationship = ghost.get_relationship("Alice", "Bob")

        assert packet["mode"] == "canonical_relationship_event"
        assert packet["relationship"] == relationship
        assert relationship["state"] in {"hostile", "neutral", "friendly"}
        assert math.isfinite(relationship["trust"])

        assert_strict_json_safe(packet)
        assert_strict_json_safe(relationship)

        trust_values.append(relationship["trust"])

    assert len(trust_values) == len(sequence)
    assert len(set(trust_values)) > 1
