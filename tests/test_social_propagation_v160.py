import json

from ghost.engine import GhostEngine


def propagate_social_event(engine, **kwargs):
    propagate = getattr(
        engine,
        "propagate_social_event",
    )

    return propagate(**kwargs)


def raw_relationship(engine, a, b):
    relationships = getattr(
        engine,
        "relationships",
    )

    get_relationship = getattr(
        relationships,
        "get",
    )

    return get_relationship(a, b)


def test_near_break_pressure_is_exposed():
    g = GhostEngine()

    sequence = [
        "greet",
        "help",
        "help",
        "insult",
        "apologize",
        "gift",
        "threat",
        "help",
        "betrayal",
    ]

    rel = None

    for event in sequence:
        rel = g.apply_event("player", "shopkeeper", event)

    assert rel is not None

    d = rel["diagnostics"]

    assert rel["state"] == "neutral"
    assert -0.55 < rel["trust"] <= -0.45
    assert d["pressure"] == "near_break"
    assert d["near_break"] is True
    assert d["direction"] == "negative"


def test_social_propagation_affects_observers():
    g = GhostEngine()

    packet = propagate_social_event(
        g,
        source="player",
        target="shopkeeper",
        event="betrayal",
        observers=["guard", "elder"],
    )

    assert packet["direct"]["state"] == "hostile"
    assert packet["pressure"] == "relationship_broken"
    assert packet["heat"] > 0
    assert len(packet["propagated"]) == 2

    guard_rel = g.get_relationship("player", "guard")
    elder_rel = g.get_relationship("player", "elder")

    assert guard_rel["trust"] < 0
    assert elder_rel["trust"] < 0


def test_social_propagation_does_not_touch_unlisted_npc():
    g = GhostEngine()

    propagate_social_event(
        g,
        source="player",
        target="shopkeeper",
        event="betrayal",
        observers=["guard"],
    )

    assert raw_relationship(g, "player", "bystander") is None


def test_social_propagation_uses_weights():
    g = GhostEngine()

    packet = propagate_social_event(
        g,
        source="player",
        target="shopkeeper",
        event="betrayal",
        observers=["guard", "elder"],
        weights={
            "guard": 1.0,
            "elder": 0.25,
        },
    )

    guard = None
    elder = None

    for item in packet["propagated"]:
        if item["affected"] == "guard":
            guard = item

        if item["affected"] == "elder":
            elder = item

    assert guard is not None
    assert elder is not None
    assert abs(guard["trust_delta"]) > abs(elder["trust_delta"])


def test_social_propagation_is_deterministic():
    def run():
        g = GhostEngine()

        return propagate_social_event(
            g,
            source="player",
            target="shopkeeper",
            event="betrayal",
            observers=["guard", "elder"],
            weights={
                "guard": 1.0,
                "elder": 0.5,
            },
        )

    assert run() == run()


def test_social_propagation_packet_is_json_safe():
    g = GhostEngine()

    packet = propagate_social_event(
        g,
        source="player",
        target="shopkeeper",
        event="betrayal",
        observers=["guard", "elder"],
    )

    json.dumps(packet)


def test_near_break_creates_less_heat_than_full_break():
    near_break_engine = GhostEngine()

    sequence = [
        "greet",
        "help",
        "help",
        "insult",
        "apologize",
        "gift",
        "threat",
        "help",
    ]

    for event in sequence:
        near_break_engine.apply_event("player", "shopkeeper", event)

    near_break_packet = propagate_social_event(
        near_break_engine,
        source="player",
        target="shopkeeper",
        event="betrayal",
        observers=["guard"],
    )

    break_engine = GhostEngine()

    break_engine.apply_event("player", "shopkeeper", "help")
    break_engine.apply_event("player", "shopkeeper", "help")

    break_packet = propagate_social_event(
        break_engine,
        source="player",
        target="shopkeeper",
        event="betrayal",
        observers=["guard"],
    )

    assert near_break_packet["pressure"] == "near_break"
    assert break_packet["pressure"] == "relationship_broken"
    assert near_break_packet["heat"] < break_packet["heat"]
