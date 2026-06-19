import pytest

from ghost import GhostAPI
from ghost.events import RelationshipEvent


def test_ghostapi_apply_event_normalizes_public_ids_in_packet_and_storage():
    api = GhostAPI()

    packet = api.apply_event(
        "  player  ",
        "  shopkeeper  ",
        {
            "type": RelationshipEvent.HELP,
            "intensity": 1.0,
        },
    )

    assert packet["source"] == "player"
    assert packet["target"] == "shopkeeper"

    rel = api.get_relationship("player", "shopkeeper")

    assert rel["state"] == "friendly"


def test_ghostapi_apply_event_rejects_internal_delimiter_ids():
    api = GhostAPI()

    with pytest.raises(ValueError):
        api.apply_event(
            "player|fake",
            "shopkeeper",
            {
                "type": RelationshipEvent.HELP,
                "intensity": 1.0,
            },
        )

    with pytest.raises(ValueError):
        api.apply_event(
            "player",
            "shop|keeper",
            {
                "type": RelationshipEvent.HELP,
                "intensity": 1.0,
            },
        )


def test_ghostapi_propagate_event_normalizes_public_source_and_target():
    api = GhostAPI()

    packets = api.propagate_event(
        "  player  ",
        "  shopkeeper  ",
        {
            "type": RelationshipEvent.HELP,
            "intensity": 1.0,
        },
        network=["guard"],
        heat=1,
    )

    assert packets[0]["source"] == "player"
    assert packets[0]["target"] == "shopkeeper"
