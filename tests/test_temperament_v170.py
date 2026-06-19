import json

import pytest

from ghost.engine import GhostEngine
from ghost.temperament import (
    get_temperament_profile,
    interpret_relationship,
    interpret_social_packet,
)


def hostile_relationship():
    ghost = GhostEngine()

    return ghost.apply_event(
        "player",
        "shopkeeper",
        "betrayal",
    )


def near_break_relationship():
    ghost = GhostEngine()

    ghost.apply_event("player", "shopkeeper", "help")
    ghost.apply_event("player", "shopkeeper", "help")
    ghost.apply_event("player", "shopkeeper", "greet")

    return ghost.apply_event(
        "player",
        "shopkeeper",
        "betrayal",
    )


def test_same_relationship_and_temperament_is_deterministic():
    rel = hostile_relationship()

    first = interpret_relationship(
        npc="guard",
        relationship=rel,
        temperament="anxious",
    )

    second = interpret_relationship(
        npc="guard",
        relationship=rel,
        temperament="anxious",
    )

    assert first == second


def test_different_temperaments_produce_different_interpretations():
    rel = hostile_relationship()

    anxious = interpret_relationship(
        npc="guard",
        relationship=rel,
        temperament="anxious",
    )

    confident = interpret_relationship(
        npc="guard",
        relationship=rel,
        temperament="confident",
    )

    assert anxious != confident

    assert (
        anxious["interpretation"]["fear"]
        >
        confident["interpretation"]["fear"]
    )

    assert (
        confident["interpretation"]["confidence"]
        >
        anxious["interpretation"]["confidence"]
    )


def test_suspicious_temperament_reads_more_suspicion_than_calm():
    rel = hostile_relationship()

    calm = interpret_relationship(
        npc="elder",
        relationship=rel,
        temperament="calm",
    )

    suspicious = interpret_relationship(
        npc="elder",
        relationship=rel,
        temperament="suspicious",
    )

    assert (
        suspicious["interpretation"]["suspicion"]
        >
        calm["interpretation"]["suspicion"]
    )


def test_resentful_temperament_reads_more_anger_than_calm():
    rel = hostile_relationship()

    calm = interpret_relationship(
        npc="rival",
        relationship=rel,
        temperament="calm",
    )

    resentful = interpret_relationship(
        npc="rival",
        relationship=rel,
        temperament="resentful",
    )

    assert (
        resentful["interpretation"]["anger"]
        >
        calm["interpretation"]["anger"]
    )


def test_near_break_relationship_interprets_as_guarded():
    rel = near_break_relationship()

    packet = interpret_relationship(
        npc="guard",
        relationship=rel,
        temperament="anxious",
    )

    assert packet["near_break"] is True
    assert packet["pressure"] == "near_break"
    assert packet["interpretation"]["stance"] == "guarded"


def test_interpretation_output_is_json_safe():
    rel = hostile_relationship()

    packet = interpret_relationship(
        npc="guard",
        relationship=rel,
        temperament="volatile",
    )

    json.dumps(packet)


def test_interpret_relationship_does_not_mutate_relationship_packet():
    rel = hostile_relationship()
    before = json.dumps(rel, sort_keys=True)

    interpret_relationship(
        npc="guard",
        relationship=rel,
        temperament="anxious",
    )

    after = json.dumps(rel, sort_keys=True)

    assert before == after


def test_custom_temperament_dict_is_supported():
    rel = hostile_relationship()

    packet = interpret_relationship(
        npc="custom_npc",
        relationship=rel,
        temperament={
            "name": "custom_test",
            "anxiety": 1.0,
            "confidence": 0.1,
            "suspicion": 0.8,
            "forgiveness": 0.2,
            "aggression": 0.4,
            "loyalty": 0.2,
            "attachment_bias": 0.2,
            "threat_sensitivity": 1.4,
            "social_sensitivity": 1.2,
            "pressure_sensitivity": 1.3,
            "authority_sensitivity": 1.0,
            "betrayal_sensitivity": 1.2,
            "recovery_bias": 0.2,
        },
    )

    assert packet["temperament"] == "custom_test"


def test_unknown_temperament_raises_value_error():
    with pytest.raises(ValueError):
        get_temperament_profile("does_not_exist")


def test_social_packet_observer_can_be_interpreted():
    ghost = GhostEngine()

    packet = ghost.propagate_social_event(
        source="player",
        target="shopkeeper",
        event="betrayal",
        observers=["guard", "elder"],
        weights={
            "guard": 1.0,
            "elder": 0.5,
        },
    )

    interpreted = interpret_social_packet(
        npc="guard",
        packet=packet,
        temperament="suspicious",
    )

    assert interpreted["npc"] == "guard"
    assert interpreted["temperament"] == "suspicious"
    assert interpreted["relationship_state"] == "neutral"
    assert interpreted["interpretation"]["suspicion"] > 0.0


def test_missing_social_packet_observer_raises_value_error():
    ghost = GhostEngine()

    packet = ghost.propagate_social_event(
        source="player",
        target="shopkeeper",
        event="betrayal",
        observers=["guard"],
    )

    with pytest.raises(ValueError):
        interpret_social_packet(
            npc="elder",
            packet=packet,
            temperament="calm",
        )
