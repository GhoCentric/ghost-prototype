"""Behavior contracts for extracted Ghost Revolution town memory."""

from __future__ import annotations

import pytest

from ghost.examples.ghost_revolution.demo import (
    GhostRevolutionRun,
)
from ghost.examples.ghost_revolution.town_memory import (
    TownMemory,
)


@pytest.mark.parametrize(
    ("town_ids", "message"),
    [
        (
            (),
            "town memory needs at least one town",
        ),
        (
            ("ashfield", "ashfield"),
            "town ids must be unique",
        ),
        (
            (None,),
            "town id must be a string",
        ),
        (
            ("   ",),
            "town id must not be empty",
        ),
    ],
)
def test_town_memory_rejects_invalid_town_collections(
    town_ids,
    message,
):
    with pytest.raises(ValueError, match=message):
        TownMemory(town_ids)


def test_execution_memory_preserves_the_strongest_recent_scar():
    memory = TownMemory(
        ("ashfield", "millcross")
    )

    assert memory.record_execution(
        "ashfield",
        "accepted",
    ) == 0

    assert memory.record_execution(
        "ashfield",
        "uncertain",
    ) == 2

    assert memory.record_execution(
        "ashfield",
        "rejected",
    ) == 3

    assert memory.record_execution(
        "ashfield",
        "uncertain",
    ) == 3

    assert memory.remaining("ashfield") == 3
    assert memory.remaining("millcross") == 0


def test_execution_memory_labels_and_daily_decay_effects():
    memory = TownMemory(
        ("ashfield", "millcross")
    )

    assert memory.label("ashfield") == "none"

    memory.record_execution(
        "ashfield",
        "rejected",
    )

    assert memory.label("ashfield") == (
        "Execution remembered (3 days)"
    )

    assert memory.advance_day() == {
        "ashfield": 2,
    }

    assert memory.remaining("ashfield") == 2

    assert memory.advance_day() == {
        "ashfield": 2,
    }

    assert memory.remaining("ashfield") == 1

    assert memory.label("ashfield") == (
        "Execution remembered (fading)"
    )

    assert memory.advance_day() == {
        "ashfield": 1,
    }

    assert memory.remaining("ashfield") == 0

    assert memory.advance_day() == {}


def test_invalid_memory_requests_are_atomic():
    memory = TownMemory(("ashfield",))

    memory.record_execution(
        "ashfield",
        "rejected",
    )

    before = memory.snapshot()

    town_cases = (
        (None, "town id must be a string"),
        ("   ", "town id must not be empty"),
        ("missing", "unknown town id: missing"),
    )

    for town_id, message in town_cases:
        with pytest.raises(ValueError, match=message):
            memory.remaining(town_id)

        assert memory.snapshot() == before

    response_cases = (
        (None, "execution response must be a string"),
        ("   ", "execution response must not be empty"),
        (
            "violent",
            "unknown execution response: violent",
        ),
    )

    for response, message in response_cases:
        with pytest.raises(ValueError, match=message):
            memory.record_execution(
                "ashfield",
                response,
            )

        assert memory.snapshot() == before


def test_snapshot_is_copy_safe():
    memory = TownMemory(("ashfield",))

    memory.record_execution(
        "ashfield",
        "rejected",
    )

    snapshot = memory.snapshot()

    snapshot["execution_memory"]["ashfield"] = 0

    assert memory.remaining("ashfield") == 3


def test_game_facade_delegates_memory_to_extracted_domain():
    game = GhostRevolutionRun(seed=7)

    assert game.town_execution_memory("missing") == 0
    assert game.town_memory_label("missing") == "none"

    game._record_town_execution_memory(
        "ashfield",
        "rejected",
    )

    assert game.town_execution_memory("ashfield") == 3
    assert game.town_memory_label("ashfield") == (
        "Execution remembered (3 days)"
    )

    assert game.towns["ashfield"]["execution_memory"] == 3

    game._advance_town_memories()

    assert game.town_execution_memory("ashfield") == 2
    assert game.towns["ashfield"]["execution_memory"] == 2
    assert game.towns["ashfield"]["fear"] >= 2
