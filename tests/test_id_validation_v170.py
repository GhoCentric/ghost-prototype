import pytest

from ghost.engine import GhostEngine
from ghost.events import RelationshipEvent
from ghost.ids import normalize_id, normalize_pair_ids


def test_normalize_id_accepts_normal_strings():
    assert normalize_id("player") == "player"
    assert normalize_id("shopkeeper") == "shopkeeper"


def test_normalize_id_strips_surrounding_whitespace():
    assert normalize_id("  player  ") == "player"


def test_normalize_id_rejects_empty_string():
    with pytest.raises(ValueError):
        normalize_id("")


def test_normalize_id_rejects_whitespace_only_string():
    with pytest.raises(ValueError):
        normalize_id("   ")


def test_normalize_id_rejects_none():
    with pytest.raises(ValueError):
        normalize_id(None)


def test_normalize_id_rejects_delimiter():
    with pytest.raises(ValueError):
        normalize_id("player|shopkeeper")


def test_normalize_id_accepts_safely_stringable_values():
    assert normalize_id(123) == "123"


def test_normalize_pair_ids_normalizes_both_sides():
    assert normalize_pair_ids(
        "  player  ",
        "  shopkeeper  ",
    ) == ("player", "shopkeeper")


def test_engine_apply_event_rejects_empty_actor_id():
    ghost = GhostEngine()

    with pytest.raises(ValueError):
        ghost.apply_event(
            "",
            "shopkeeper",
            RelationshipEvent.HELP,
        )


def test_engine_apply_event_rejects_empty_target_id():
    ghost = GhostEngine()

    with pytest.raises(ValueError):
        ghost.apply_event(
            "player",
            "",
            RelationshipEvent.HELP,
        )


def test_engine_apply_event_rejects_delimiter_in_actor_id():
    ghost = GhostEngine()

    with pytest.raises(ValueError):
        ghost.apply_event(
            "player|fake",
            "shopkeeper",
            RelationshipEvent.HELP,
        )


def test_engine_apply_event_rejects_delimiter_in_target_id():
    ghost = GhostEngine()

    with pytest.raises(ValueError):
        ghost.apply_event(
            "player",
            "shop|keeper",
            RelationshipEvent.HELP,
        )


def test_engine_apply_event_strips_ids_before_storage():
    ghost = GhostEngine()

    ghost.apply_event(
        "  player  ",
        "  shopkeeper  ",
        RelationshipEvent.HELP,
    )

    rel = ghost.get_relationship(
        "player",
        "shopkeeper",
    )

    assert rel["state"] == "friendly"

    state = ghost.state()

    assert "player|shopkeeper" in state["relationships"]
    assert "  player  |  shopkeeper  " not in state["relationships"]


def test_neighbors_use_normalized_ids():
    ghost = GhostEngine()

    ghost.apply_event(
        "  player  ",
        "  shopkeeper  ",
        RelationshipEvent.HELP,
    )

    neighbors = ghost.relationships.neighbors(" player ")

    assert neighbors == ["shopkeeper"]
