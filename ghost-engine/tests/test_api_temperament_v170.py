import json

from ghost.api import GhostAPI


def test_api_interprets_existing_relationship_packet():
    api = GhostAPI()

    relationship = api.engine.apply_event(
        "player",
        "shopkeeper",
        "betrayal",
    )

    packet = api.interpret_relationship_packet(
        npc="guard",
        relationship=relationship,
        temperament="anxious",
    )

    assert packet["npc"] == "guard"
    assert packet["temperament"] == "anxious"
    assert packet["relationship_state"] == "hostile"
    assert packet["interpretation"]["fear"] > 0.0

    json.dumps(packet)


def test_api_reads_and_interprets_engine_relationship():
    api = GhostAPI()

    api.engine.apply_event(
        "player",
        "shopkeeper",
        "betrayal",
    )

    packet = api.interpret_npc_relationship(
        npc="guard",
        source="player",
        target="shopkeeper",
        temperament="suspicious",
    )

    assert packet["npc"] == "guard"
    assert packet["temperament"] == "suspicious"
    assert packet["relationship_state"] == "hostile"
    assert packet["interpretation"]["suspicion"] > 0.0

    json.dumps(packet)


def test_api_interprets_social_packet_observer():
    api = GhostAPI()

    social_packet = api.engine.propagate_social_event(
        source="player",
        target="shopkeeper",
        event="betrayal",
        observers=["guard", "elder"],
        weights={
            "guard": 1.0,
            "elder": 0.5,
        },
    )

    interpreted = api.interpret_social_packet(
        npc="guard",
        packet=social_packet,
        temperament="resentful",
    )

    assert interpreted["npc"] == "guard"
    assert interpreted["temperament"] == "resentful"
    assert interpreted["relationship_state"] == "neutral"
    assert interpreted["interpretation"]["anger"] > 0.0

    json.dumps(interpreted)


def test_api_temperament_interpretation_is_deterministic():
    def run():
        api = GhostAPI()

        api.engine.apply_event(
            "player",
            "shopkeeper",
            "betrayal",
        )

        return api.interpret_npc_relationship(
            npc="guard",
            source="player",
            target="shopkeeper",
            temperament="volatile",
        )

    assert run() == run()
