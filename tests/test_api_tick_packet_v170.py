import json

from ghost.api import GhostAPI
from ghost.events import APIEvent, RelationshipEvent


def test_api_tick_returns_public_packet():
    api = GhostAPI()

    api.engine.apply_event(
        "player",
        "shopkeeper",
        RelationshipEvent.BETRAYAL,
    )

    packet = api.tick()

    assert packet["event"] == "tick"
    assert isinstance(packet["relationships"], list)
    assert isinstance(packet["world"], dict)

    assert len(packet["relationships"]) == 1

    relationship = packet["relationships"][0]

    assert relationship["diagnostics"]["event"] == "tick"
    assert relationship["diagnostics"]["channel"] == "decay"

    json.dumps(packet)


def test_api_tick_packet_matches_engine_relationship_readback():
    api = GhostAPI()

    api.engine.apply_event(
        "player",
        "shopkeeper",
        RelationshipEvent.BETRAYAL,
    )

    packet = api.tick()

    tick_relationship = packet["relationships"][0]
    readback = api.engine.get_relationship(
        "player",
        "shopkeeper",
    )

    assert tick_relationship["trust"] == readback["trust"]
    assert tick_relationship["state"] == readback["state"]

    assert (
        tick_relationship["diagnostics"]["pressure"]
        ==
        readback["diagnostics"]["pressure"]
    )


def test_api_tick_packet_includes_world_schema():
    api = GhostAPI()

    packet = api.tick()
    world = packet["world"]

    assert set(world.keys()) >= {
        "mood",
        "events",
        "global_pressure",
        "status",
    }

    assert set(world["mood"].keys()) >= {
        "fear",
        "order",
        "commerce",
        "resentment",
    }

    json.dumps(packet)


def test_api_tick_world_state_decays_after_world_effects():
    api = GhostAPI()

    api.apply_world_effects(
        {
            "pressure_delta": 1.0,
            "fear_delta": 0.5,
            "resentment_delta": 0.5,
            "order_delta": -0.2,
        }
    )

    before = api.world_state()

    packet = api.tick()

    after = packet["world"]

    assert after["global_pressure"] < before["global_pressure"]
    assert after["mood"]["fear"] < before["mood"]["fear"]
    assert after["mood"]["resentment"] < before["mood"]["resentment"]
    assert after["status"] in ("normal", "tense", "crisis")

    json.dumps(packet)


def test_api_tick_works_after_api_apply_event():
    api = GhostAPI()

    api.apply_event(
        "player",
        "shopkeeper",
        {
            "type": APIEvent.THEFT,
            "intensity": 1.0,
        },
    )

    packet = api.tick()

    assert packet["event"] == "tick"
    assert "relationships" in packet
    assert "world" in packet

    json.dumps(packet)
