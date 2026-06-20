import json

from ghost.engine import GhostEngine
from ghost.events import RelationshipEvent, TemperamentPreset
from ghost.temperament import interpret_relationship


def assert_json_safe(packet):
    json.dumps(packet)


def build_many_relationships(count=100):
    ghost = GhostEngine()

    for index in range(count):
        ghost.apply_event(
            "player",
            f"npc_{index}",
            RelationshipEvent.HELP,
        )

        if index % 3 == 0:
            ghost.apply_event(
                "player",
                f"npc_{index}",
                RelationshipEvent.INSULT,
            )

        if index % 10 == 0:
            ghost.apply_event(
                "player",
                f"npc_{index}",
                RelationshipEvent.BETRAYAL,
            )

    return ghost


def test_many_relationships_do_not_break_snapshot():
    ghost = build_many_relationships(count=100)

    snapshot = ghost.snapshot()

    assert snapshot["ghost_version"] == "1.7.2"
    assert snapshot["schema_version"] == "1.7.2"

    assert len(snapshot["relationships"]) == 100

    assert_json_safe(snapshot)


def test_many_relationships_do_not_break_tick_packet():
    ghost = build_many_relationships(count=100)

    packet = ghost.tick()

    assert packet["event"] == "tick"
    assert isinstance(packet["relationships"], list)

    assert len(packet["relationships"]) == 100

    for relationship in packet["relationships"]:
        assert "trust" in relationship
        assert "state" in relationship
        assert "diagnostics" in relationship
        assert relationship["diagnostics"]["event"] == "tick"

    assert_json_safe(packet)


def test_many_relationships_tick_is_deterministic():
    def run():
        ghost = build_many_relationships(count=100)

        return ghost.tick()

    assert run() == run()


def test_many_observers_do_not_break_social_propagation_json_safety():
    ghost = GhostEngine()

    observers = [
        f"observer_{index}"
        for index in range(100)
    ]

    weights = {
        observer: 1.0
        for observer in observers
    }

    packet = ghost.propagate_social_event(
        source="player",
        target="shopkeeper",
        event=RelationshipEvent.BETRAYAL,
        observers=observers,
        weights=weights,
    )

    assert packet["event"] == "betrayal"
    assert packet["pressure"] == "relationship_broken"
    assert len(packet["propagated"]) == 100

    assert_json_safe(packet)


def test_many_observers_social_propagation_is_deterministic():
    observers = [
        f"observer_{index}"
        for index in range(100)
    ]

    weights = {
        observer: 1.0
        for observer in observers
    }

    def run():
        ghost = GhostEngine()

        return ghost.propagate_social_event(
            source="player",
            target="shopkeeper",
            event=RelationshipEvent.BETRAYAL,
            observers=observers,
            weights=weights,
        )

    assert run() == run()


def test_many_temperament_interpretations_stay_deterministic():
    ghost = GhostEngine()

    relationship = ghost.apply_event(
        "player",
        "shopkeeper",
        RelationshipEvent.BETRAYAL,
    )

    temperaments = [
        TemperamentPreset.CALM,
        TemperamentPreset.ANXIOUS,
        TemperamentPreset.CONFIDENT,
        TemperamentPreset.SUSPICIOUS,
        TemperamentPreset.RESENTFUL,
        TemperamentPreset.LOYAL,
        TemperamentPreset.VOLATILE,
    ]

    def run():
        packets = []

        for index in range(100):
            temperament = temperaments[index % len(temperaments)]

            packets.append(
                interpret_relationship(
                    npc=f"npc_{index}",
                    relationship=relationship,
                    temperament=temperament,
                )
            )

        return packets

    first = run()
    second = run()

    assert first == second
    assert len(first) == 100

    for packet in first:
        assert "interpretation" in packet
        assert "temperament" in packet

    assert_json_safe(first)


def test_many_temperament_interpretations_remain_distinct():
    ghost = GhostEngine()

    relationship = ghost.apply_event(
        "player",
        "shopkeeper",
        RelationshipEvent.BETRAYAL,
    )

    anxious = interpret_relationship(
        npc="guard",
        relationship=relationship,
        temperament=TemperamentPreset.ANXIOUS,
    )

    confident = interpret_relationship(
        npc="guard",
        relationship=relationship,
        temperament=TemperamentPreset.CONFIDENT,
    )

    resentful = interpret_relationship(
        npc="guard",
        relationship=relationship,
        temperament=TemperamentPreset.RESENTFUL,
    )

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

    assert (
        resentful["interpretation"]["anger"]
        >
        anxious["interpretation"]["anger"]
    )


def test_scale_snapshot_after_social_propagation_and_tick_is_json_safe():
    ghost = GhostEngine()

    observers = [
        f"observer_{index}"
        for index in range(50)
    ]

    ghost.propagate_social_event(
        source="player",
        target="shopkeeper",
        event=RelationshipEvent.BETRAYAL,
        observers=observers,
    )

    ghost.tick()

    snapshot = ghost.snapshot()

    assert snapshot["ghost_version"] == "1.7.2"
    assert snapshot["schema_version"] == "1.7.2"

    assert len(snapshot["relationships"]) == 51

    assert_json_safe(snapshot)
