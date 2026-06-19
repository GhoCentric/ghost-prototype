import copy
import json

import pytest

from ghost import GhostAPI
from ghost.events import (
    RelationshipEvent,
    TemperamentPreset,
    normalize_event,
    normalize_temperament,
)


def test_v171_release_contract_snapshot_tick_enums_and_temperament():
    api = GhostAPI()

    packet = api.apply_event(
        "player",
        "npc_contract",
        {
            "type": RelationshipEvent.BETRAYAL,
            "intensity": 1.0,
        },
    )

    assert packet["event"]["type"] == "betrayal"
    assert packet["source"] == "player"
    assert packet["target"] == "npc_contract"
    assert "relationship" in packet
    assert "state" in packet
    assert "trust" in packet

    tick_packet = api.tick()

    assert tick_packet["event"] == "tick"
    assert isinstance(tick_packet["relationships"], list)
    assert isinstance(tick_packet["world"], dict)

    snapshot = api.snapshot()

    assert snapshot["ghost_version"]
    assert snapshot["schema_version"]
    assert snapshot["engine"]["ghost_version"] == snapshot["ghost_version"]
    assert snapshot["engine"]["schema_version"] == snapshot["schema_version"]

    json.dumps(snapshot)

    relationship_before = copy.deepcopy(
        api.get_relationship("player", "npc_contract")
    )

    interpretation = api.interpret_relationship_packet(
        npc="npc_contract",
        relationship=relationship_before,
        temperament=TemperamentPreset.SUSPICIOUS,
    )

    relationship_after = api.get_relationship("player", "npc_contract")

    assert isinstance(interpretation, dict)
    assert relationship_after == relationship_before

    assert normalize_event(RelationshipEvent.BETRAYAL) == "betrayal"
    assert normalize_temperament(TemperamentPreset.SUSPICIOUS) == "suspicious"


def test_v171_release_contract_rejects_bad_public_ids():
    api = GhostAPI()

    bad_ids = [
        "",
        "   ",
        None,
        "player|npc",
    ]

    for bad_id in bad_ids:
        with pytest.raises(ValueError):
            api.apply_event(
                bad_id,
                "npc_contract",
                {
                    "type": RelationshipEvent.HELP,
                    "intensity": 1.0,
                },
            )

        with pytest.raises(ValueError):
            api.apply_event(
                "player",
                bad_id,
                {
                    "type": RelationshipEvent.HELP,
                    "intensity": 1.0,
                },
            )
