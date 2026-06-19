import json

import pytest

from ghost.api import GhostAPI
from ghost.engine import GhostEngine
from ghost.events import (
    APIEvent,
    PressureLabel,
    RelationshipEvent,
    RelationshipState,
    TemperamentPreset,
    normalize_event,
    normalize_pressure,
    normalize_relationship_state,
    normalize_temperament,
)
from ghost.temperament import interpret_relationship


def test_relationship_event_enum_works_with_engine_apply_event():
    ghost = GhostEngine()

    rel = ghost.apply_event(
        "player",
        "shopkeeper",
        RelationshipEvent.BETRAYAL,
    )

    assert rel["diagnostics"]["event"] == "betrayal"
    assert rel["state"] == "hostile"

    json.dumps(rel)


def test_relationship_event_string_still_works_with_engine_apply_event():
    ghost = GhostEngine()

    rel = ghost.apply_event(
        "player",
        "shopkeeper",
        "betrayal",
    )

    assert rel["diagnostics"]["event"] == "betrayal"
    assert rel["state"] == "hostile"

    json.dumps(rel)


def test_relationship_event_enum_works_with_social_propagation():
    ghost = GhostEngine()

    packet = ghost.propagate_social_event(
        source="player",
        target="shopkeeper",
        event=RelationshipEvent.BETRAYAL,
        observers=["guard"],
    )

    assert packet["event"] == "betrayal"
    assert packet["pressure"] == "relationship_broken"
    assert packet["propagated"][0]["affected"] == "guard"

    json.dumps(packet)


def test_api_event_enum_works_with_ghost_api_dict_event():
    api = GhostAPI()

    packet = api.apply_event(
        "player",
        "shopkeeper",
        {
            "type": APIEvent.THEFT,
            "intensity": 1.0,
        },
    )

    assert packet["event"]["type"] == "theft"
    assert packet["event"]["intensity"] == 1.0
    assert packet["deltas"]["trust"] < 0

    json.dumps(packet)


def test_api_event_string_still_works_with_ghost_api_dict_event():
    api = GhostAPI()

    packet = api.apply_event(
        "player",
        "shopkeeper",
        {
            "type": "theft",
            "intensity": 1.0,
        },
    )

    assert packet["event"]["type"] == "theft"
    assert packet["event"]["intensity"] == 1.0
    assert packet["deltas"]["trust"] < 0

    json.dumps(packet)


def test_temperament_enum_works_with_interpret_relationship():
    ghost = GhostEngine()

    rel = ghost.apply_event(
        "player",
        "shopkeeper",
        RelationshipEvent.BETRAYAL,
    )

    packet = interpret_relationship(
        npc="guard",
        relationship=rel,
        temperament=TemperamentPreset.ANXIOUS,
    )

    assert packet["temperament"] == "anxious"
    assert packet["interpretation"]["fear"] > 0

    json.dumps(packet)


def test_temperament_string_still_works_with_interpret_relationship():
    ghost = GhostEngine()

    rel = ghost.apply_event(
        "player",
        "shopkeeper",
        "betrayal",
    )

    packet = interpret_relationship(
        npc="guard",
        relationship=rel,
        temperament="anxious",
    )

    assert packet["temperament"] == "anxious"
    assert packet["interpretation"]["fear"] > 0

    json.dumps(packet)


def test_normalizers_return_plain_strings():
    assert normalize_event(RelationshipEvent.BETRAYAL) == "betrayal"
    assert normalize_event("BETRAYAL") == "betrayal"

    assert normalize_temperament(TemperamentPreset.VOLATILE) == "volatile"
    assert normalize_temperament("VOLATILE") == "volatile"

    assert normalize_pressure(PressureLabel.NEAR_BREAK) == "near_break"
    assert normalize_pressure("NEAR_BREAK") == "near_break"

    assert normalize_relationship_state(RelationshipState.HOSTILE) == "hostile"
    assert normalize_relationship_state("HOSTILE") == "hostile"


def test_unknown_string_event_still_fails():
    ghost = GhostEngine()

    with pytest.raises(ValueError):
        ghost.apply_event(
            "player",
            "shopkeeper",
            "dance",
        )
