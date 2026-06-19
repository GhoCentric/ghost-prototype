import json

from ghost.api import GhostAPI
from ghost.engine import GhostEngine
from ghost.events import RelationshipEvent, TemperamentPreset
from ghost.temperament import interpret_relationship


def assert_has_keys(packet, required_keys):
    missing = set(required_keys) - set(packet.keys())

    assert not missing, f"Missing keys: {sorted(missing)}"


def assert_json_safe(packet):
    json.dumps(packet)


def betrayal_relationship_packet():
    ghost = GhostEngine()

    return ghost.apply_event(
        "player",
        "shopkeeper",
        RelationshipEvent.BETRAYAL,
    )


def test_relationship_packet_schema_is_stable():
    packet = betrayal_relationship_packet()

    assert_has_keys(
        packet,
        {
            "trust",
            "state",
            "transition",
            "trigger",
            "diagnostics",
            "maturity",
            "volatility",
            "positive_volatility",
            "negative_volatility",
        },
    )

    assert isinstance(packet["diagnostics"], dict)

    assert_json_safe(packet)


def test_relationship_diagnostics_schema_is_stable():
    packet = betrayal_relationship_packet()
    diagnostics = packet["diagnostics"]

    assert_has_keys(
        diagnostics,
        {
            "event",
            "channel",
            "base_amount",
            "effective_gain",
            "from_state",
            "to_state",
            "trust_before",
            "trust_after",
            "delta",
            "abs_delta",
            "direction",
            "severity",
            "maturity",
            "maturity_modifier",
            "volatility",
            "positive_volatility",
            "negative_volatility",
            "transition",
            "trigger",
            "pressure",
            "near_break",
        },
    )

    assert_json_safe(diagnostics)


def test_tick_packet_schema_is_stable():
    ghost = GhostEngine()

    ghost.apply_event(
        "player",
        "shopkeeper",
        RelationshipEvent.BETRAYAL,
    )

    packet = ghost.tick()

    assert_has_keys(
        packet,
        {
            "event",
            "relationships",
        },
    )

    assert packet["event"] == "tick"
    assert isinstance(packet["relationships"], list)
    assert packet["relationships"]

    relationship = packet["relationships"][0]

    assert_has_keys(
        relationship,
        {
            "a",
            "b",
            "trust",
            "state",
            "transition",
            "trigger",
            "diagnostics",
            "maturity",
            "volatility",
            "positive_volatility",
            "negative_volatility",
        },
    )

    diagnostics = relationship["diagnostics"]

    assert_has_keys(
        diagnostics,
        {
            "event",
            "channel",
            "trust_before",
            "trust_after",
            "delta",
            "direction",
            "pressure",
            "near_break",
        },
    )

    assert_json_safe(packet)


def test_social_propagation_packet_schema_is_stable():
    ghost = GhostEngine()

    packet = ghost.propagate_social_event(
        source="player",
        target="shopkeeper",
        event=RelationshipEvent.BETRAYAL,
        observers=["guard", "elder"],
        weights={
            "guard": 1.0,
            "elder": 0.5,
        },
    )

    assert_has_keys(
        packet,
        {
            "source",
            "target",
            "event",
            "heat",
            "severity",
            "pressure",
            "direct",
            "propagated",
            "world_effects",
        },
    )

    assert isinstance(packet["direct"], dict)
    assert isinstance(packet["propagated"], list)
    assert isinstance(packet["world_effects"], dict)

    assert_has_keys(
        packet["direct"],
        {
            "trust",
            "state",
            "transition",
            "trigger",
            "diagnostics",
            "maturity",
            "volatility",
            "positive_volatility",
            "negative_volatility",
        },
    )

    observer = packet["propagated"][0]

    assert_has_keys(
        observer,
        {
            "affected",
            "source_event",
            "source_pressure",
            "heat",
            "trust_delta",
            "relationship",
        },
    )

    assert_has_keys(
        observer["relationship"],
        {
            "trust",
            "state",
        },
    )

    assert_has_keys(
        packet["world_effects"],
        {
            "pressure_delta",
            "fear_delta",
            "resentment_delta",
            "order_delta",
            "guard_suspicion_delta",
        },
    )

    assert_json_safe(packet)


def test_temperament_packet_schema_is_stable():
    relationship = betrayal_relationship_packet()

    packet = interpret_relationship(
        npc="guard",
        relationship=relationship,
        temperament=TemperamentPreset.ANXIOUS,
    )

    assert_has_keys(
        packet,
        {
            "npc",
            "temperament",
            "relationship_state",
            "trust",
            "pressure",
            "near_break",
            "source_event",
            "interpretation",
        },
    )

    assert isinstance(packet["interpretation"], dict)

    assert_has_keys(
        packet["interpretation"],
        {
            "emotional_read",
            "stance",
            "fear",
            "suspicion",
            "anger",
            "confidence",
            "loyalty",
            "relief",
            "intensity",
        },
    )

    assert_json_safe(packet)


def test_public_packet_schema_values_are_plain_public_types():
    relationship = betrayal_relationship_packet()

    temperament = interpret_relationship(
        npc="guard",
        relationship=relationship,
        temperament=TemperamentPreset.RESENTFUL,
    )

    social = GhostEngine().propagate_social_event(
        source="player",
        target="shopkeeper",
        event=RelationshipEvent.BETRAYAL,
        observers=["guard"],
    )

    for packet in (relationship, temperament, social):
        encoded = json.dumps(packet)
        decoded = json.loads(encoded)

        assert isinstance(decoded, dict)


def test_schema_tests_do_not_lock_exact_numeric_values():
    relationship = betrayal_relationship_packet()

    assert isinstance(relationship["trust"], float)
    assert isinstance(relationship["diagnostics"]["delta"], float)
    assert isinstance(relationship["diagnostics"]["severity"], float)

    temperament = interpret_relationship(
        npc="guard",
        relationship=relationship,
        temperament=TemperamentPreset.ANXIOUS,
    )

    assert isinstance(temperament["interpretation"]["fear"], float)
    assert isinstance(temperament["interpretation"]["suspicion"], float)
    assert isinstance(temperament["interpretation"]["anger"], float)

def test_ghost_api_tick_packet_schema_is_stable():
    api = GhostAPI()

    api.engine.apply_event(
        "player",
        "shopkeeper",
        RelationshipEvent.BETRAYAL,
    )

    packet = api.tick()

    assert_has_keys(
        packet,
        {
            "event",
            "relationships",
            "world",
        },
    )

    assert packet["event"] == "tick"
    assert isinstance(packet["relationships"], list)
    assert isinstance(packet["world"], dict)

    assert packet["relationships"]

    relationship = packet["relationships"][0]

    assert_has_keys(
        relationship,
        {
            "a",
            "b",
            "trust",
            "state",
            "transition",
            "trigger",
            "diagnostics",
            "maturity",
            "volatility",
            "positive_volatility",
            "negative_volatility",
        },
    )

    assert isinstance(relationship["diagnostics"], dict)

    assert_has_keys(
        packet["world"],
        {
            "mood",
            "events",
            "global_pressure",
            "status",
        },
    )

    assert_has_keys(
        packet["world"]["mood"],
        {
            "fear",
            "order",
            "commerce",
            "resentment",
        },
    )

    assert_json_safe(packet)

