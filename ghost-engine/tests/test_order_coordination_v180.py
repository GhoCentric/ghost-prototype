from copy import deepcopy
import json

import pytest

from ghost.examples.order_coordination import (
    OrderCoordinator,
    OrderSubmissionBlocked,
)


def _two_item_order():
    runtime = OrderCoordinator()
    first = runtime.add_item(
        "add_1",
        "burger",
    )["result"]["item"]
    second = runtime.add_item(
        "add_2",
        "burger",
    )["result"]["item"]

    return runtime, first, second


def test_ambiguous_modifier_does_not_mutate_and_blocks_submit_v180():
    runtime, first, second = _two_item_order()

    packet = runtime.propose_modifier(
        "modifier_1",
        modifier="add_bacon",
        candidate_item_ids=[
            first["item_id"],
            second["item_id"],
        ],
        source_text="Put bacon on the other one.",
    )

    assert packet["result"]["outcome"] == (
        "clarification_required"
    )
    assert all(
        item["modifiers"] == []
        for item in runtime.order()["items"]
    )
    assert runtime.status()["submission_allowed"] is False
    assert runtime.status()["unresolved_ambiguities"] == [
        "ambiguity_001"
    ]

    with pytest.raises(
        OrderSubmissionBlocked,
        match="unresolved_ambiguity:ambiguity_001",
    ):
        runtime.submit("submit_1")


def test_customer_clarification_revises_belief_and_applies_exact_v180():
    runtime, first, second = _two_item_order()
    opened = runtime.propose_modifier(
        "modifier_1",
        modifier="add_bacon",
        candidate_item_ids=[
            first["item_id"],
            second["item_id"],
        ],
        source_text="Put bacon on the other one.",
    )["result"]

    resolved = runtime.resolve_ambiguity(
        "resolve_1",
        ambiguity_id=opened["ambiguity"]["ambiguity_id"],
        target_item_id=second["item_id"],
        source_text="The second burger.",
    )["result"]

    target = resolved["belief"]["dimensions"]["target"]

    assert target["dominant_candidate"] == second["item_id"]
    assert target["confidence"] == pytest.approx(1.0)

    items = {
        item["item_id"]: item
        for item in runtime.order()["items"]
    }

    assert items[first["item_id"]]["modifiers"] == []
    assert items[second["item_id"]]["modifiers"] == [
        "add_bacon"
    ]
    assert runtime.status()["unresolved_ambiguities"] == []
    assert runtime.status()["submission_allowed"] is False
    assert runtime.status()["blockers"] == [
        "current_revision_not_confirmed"
    ]


def test_correction_invalidates_confirmation_and_moves_modifier_v180():
    runtime, first, second = _two_item_order()
    runtime.propose_modifier(
        "modifier_1",
        modifier="add_bacon",
        candidate_item_ids=[second["item_id"]],
        source_text="Bacon on the second burger.",
    )
    runtime.confirm_order(
        "confirm_1",
        "Yes, that is correct.",
    )

    assert runtime.status()["submission_allowed"] is True

    runtime.correct_modifier(
        "correct_1",
        modifier="add_bacon",
        from_item_id=second["item_id"],
        to_item_id=first["item_id"],
        source_text="Move bacon to the first burger.",
    )

    items = {
        item["item_id"]: item
        for item in runtime.order()["items"]
    }

    assert items[first["item_id"]]["modifiers"] == [
        "add_bacon"
    ]
    assert items[second["item_id"]]["modifiers"] == []
    assert runtime.status()["confirmed_revision"] is None
    assert runtime.status()["submission_allowed"] is False

    runtime.confirm_order(
        "confirm_2",
        "The corrected order is right.",
    )
    submitted = runtime.submit("submit_1")

    assert submitted["result"]["outcome"] == "order_submitted"
    assert runtime.status()["submitted"] is True

    with pytest.raises(
        RuntimeError,
        match="submitted orders are immutable",
    ):
        runtime.add_item("add_3", "fries")


def test_operation_ids_are_idempotent_and_conflict_guarded_v180():
    runtime = OrderCoordinator()

    first = runtime.add_item("same", "burger")
    second = runtime.add_item("same", "burger")

    assert first == second
    assert runtime.status()["item_count"] == 1

    with pytest.raises(
        ValueError,
        match="reused with different input",
    ):
        runtime.add_item("same", "fries")


def test_snapshot_restore_is_json_safe_copied_and_deterministic_v180():
    runtime, first, second = _two_item_order()
    opened = runtime.propose_modifier(
        "modifier_1",
        modifier="add_bacon",
        candidate_item_ids=[
            first["item_id"],
            second["item_id"],
        ],
        source_text="Put bacon on the other one.",
    )["result"]
    runtime.resolve_ambiguity(
        "resolve_1",
        ambiguity_id=opened["ambiguity"]["ambiguity_id"],
        target_item_id=second["item_id"],
        source_text="The second burger.",
    )

    snapshot = runtime.snapshot()
    json.dumps(snapshot, allow_nan=False, sort_keys=True)
    restored = OrderCoordinator.from_snapshot(
        deepcopy(snapshot)
    )

    assert restored.snapshot() == snapshot

    snapshot["items"][0]["product"] = "tampered"
    snapshot["ghost"]["epistemic"]["records"][0][
        "visible_features"
    ] = ["tampered"]

    assert runtime.order()["items"][0]["product"] == "burger"
    assert restored.order()["items"][0]["product"] == "burger"

    for coordinator in (runtime, restored):
        coordinator.confirm_order(
            "confirm_1",
            "Yes, submit it.",
        )
        coordinator.submit("submit_1")

    assert runtime.snapshot() == restored.snapshot()


def test_failed_operation_rolls_back_epistemic_and_order_state_v180():
    runtime, first, second = _two_item_order()
    runtime.propose_modifier(
        "modifier_1",
        modifier="add_bacon",
        candidate_item_ids=[second["item_id"]],
        source_text="Bacon on the second burger.",
    )
    before = runtime.snapshot()

    with pytest.raises(
        ValueError,
        match="source item does not contain modifier",
    ):
        runtime.correct_modifier(
            "bad_correction",
            modifier="add_bacon",
            from_item_id=first["item_id"],
            to_item_id=second["item_id"],
            source_text="Move it.",
        )

    assert runtime.snapshot() == before
