from copy import deepcopy

import pytest

from ghost.examples.order_coordination import OrderCoordinator


def _snapshot(*, two_corrections: bool = False) -> dict:
    runtime = OrderCoordinator()
    first = runtime.add_item(
        "add_1",
        "burger",
    )["result"]["item"]
    second = runtime.add_item(
        "add_2",
        "burger",
    )["result"]["item"]

    runtime.propose_modifier(
        "modifier_1",
        modifier="add_bacon",
        candidate_item_ids=[second["item_id"]],
        source_text="Put bacon on the second burger.",
    )
    runtime.confirm_order(
        "confirm_1",
        "Yes, that order is correct.",
    )
    runtime.correct_modifier(
        "correct_1",
        modifier="add_bacon",
        from_item_id=second["item_id"],
        to_item_id=first["item_id"],
        source_text="Move the bacon to the first burger.",
    )

    if two_corrections:
        runtime.correct_modifier(
            "correct_2",
            modifier="add_bacon",
            from_item_id=first["item_id"],
            to_item_id=second["item_id"],
            source_text="Move the bacon back to the second burger.",
        )

    runtime.confirm_order(
        "confirm_2",
        "Yes, the corrected order is right.",
    )
    return runtime.snapshot()


def _fact_id(snapshot: dict) -> str:
    return next(
        record["id"]
        for record in snapshot["ghost"]["epistemic"]["records"]
        if record["kind"] == "fact"
    )


def test_snapshot_hardening_accepts_valid_correction_confirmation_state_v180():
    snapshot = _snapshot()
    restored = OrderCoordinator.from_snapshot(deepcopy(snapshot))

    assert restored.snapshot() == snapshot


@pytest.mark.parametrize(
    "replacement",
    [
        [],
        {"correction_id": "correction_001"},
    ],
)
def test_snapshot_hardening_rejects_invalid_correction_schema_v180(
    replacement,
):
    snapshot = _snapshot()
    snapshot["corrections"][0] = replacement

    with pytest.raises(ValueError, match="correction schema is invalid"):
        OrderCoordinator.from_snapshot(snapshot)


def test_snapshot_hardening_rejects_duplicate_correction_ids_v180():
    snapshot = _snapshot()
    snapshot["corrections"].append(
        deepcopy(snapshot["corrections"][0])
    )

    with pytest.raises(ValueError, match="correction ids must be unique"):
        OrderCoordinator.from_snapshot(snapshot)


def test_snapshot_hardening_rejects_same_correction_source_and_target_v180():
    snapshot = _snapshot()
    correction = snapshot["corrections"][0]
    correction["to_item_id"] = correction["from_item_id"]

    with pytest.raises(
        ValueError,
        match="correction source and target must differ",
    ):
        OrderCoordinator.from_snapshot(snapshot)


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("from_item_id", "unknown source item"),
        ("to_item_id", "unknown target item"),
    ],
)
def test_snapshot_hardening_rejects_unknown_correction_item_refs_v180(
    field,
    message,
):
    snapshot = _snapshot()
    snapshot["corrections"][0][field] = "item_999"

    with pytest.raises(ValueError, match=message):
        OrderCoordinator.from_snapshot(snapshot)


def test_snapshot_hardening_rejects_unknown_correction_observation_v180():
    snapshot = _snapshot()
    snapshot["corrections"][0]["observation_id"] = "epistemic_999999"

    with pytest.raises(ValueError, match="unknown observation"):
        OrderCoordinator.from_snapshot(snapshot)


def test_snapshot_hardening_rejects_non_observation_correction_reference_v180():
    snapshot = _snapshot()
    snapshot["corrections"][0]["observation_id"] = _fact_id(snapshot)

    with pytest.raises(
        ValueError,
        match="reference is not an observation",
    ):
        OrderCoordinator.from_snapshot(snapshot)


def test_snapshot_hardening_rejects_unknown_correction_belief_v180():
    snapshot = _snapshot()
    snapshot["corrections"][0]["belief_id"] = "epistemic_999999"

    with pytest.raises(ValueError, match="unknown belief"):
        OrderCoordinator.from_snapshot(snapshot)


def test_snapshot_hardening_rejects_non_belief_correction_reference_v180():
    snapshot = _snapshot()
    snapshot["corrections"][0]["belief_id"] = _fact_id(snapshot)

    with pytest.raises(
        ValueError,
        match="reference is not a belief",
    ):
        OrderCoordinator.from_snapshot(snapshot)


@pytest.mark.parametrize(
    "replacement",
    [
        [],
        {"confirmation_id": "confirmation_001"},
    ],
)
def test_snapshot_hardening_rejects_invalid_confirmation_schema_v180(
    replacement,
):
    snapshot = _snapshot()
    snapshot["confirmations"][0] = replacement

    with pytest.raises(ValueError, match="confirmation schema is invalid"):
        OrderCoordinator.from_snapshot(snapshot)


def test_snapshot_hardening_rejects_duplicate_confirmation_ids_v180():
    snapshot = _snapshot()
    snapshot["confirmations"].append(
        deepcopy(snapshot["confirmations"][-1])
    )

    with pytest.raises(ValueError, match="confirmation ids must be unique"):
        OrderCoordinator.from_snapshot(snapshot)


def test_snapshot_hardening_rejects_confirmation_revision_beyond_runtime_v180():
    snapshot = _snapshot()
    snapshot["confirmations"][-1]["revision"] = snapshot["revision"] + 1

    with pytest.raises(
        ValueError,
        match="confirmation revision exceeds runtime revision",
    ):
        OrderCoordinator.from_snapshot(snapshot)


def test_snapshot_hardening_rejects_decreasing_confirmation_revisions_v180():
    snapshot = _snapshot()
    snapshot["confirmations"][0]["revision"] = snapshot["revision"]
    snapshot["confirmations"][1]["revision"] = snapshot["revision"] - 1

    with pytest.raises(
        ValueError,
        match="confirmation revisions must be non-decreasing",
    ):
        OrderCoordinator.from_snapshot(snapshot)


def test_snapshot_hardening_rejects_unknown_confirmation_observation_v180():
    snapshot = _snapshot()
    snapshot["confirmations"][0]["observation_id"] = "epistemic_999999"

    with pytest.raises(ValueError, match="unknown observation"):
        OrderCoordinator.from_snapshot(snapshot)


def test_snapshot_hardening_rejects_non_observation_confirmation_reference_v180():
    snapshot = _snapshot()
    snapshot["confirmations"][0]["observation_id"] = _fact_id(snapshot)

    with pytest.raises(
        ValueError,
        match="reference is not an observation",
    ):
        OrderCoordinator.from_snapshot(snapshot)


def test_snapshot_hardening_rejects_stale_non_null_confirmed_revision_v180():
    snapshot = _snapshot()
    snapshot["confirmed_revision"] = snapshot["revision"] - 1

    with pytest.raises(
        ValueError,
        match="confirmed revision must equal current revision",
    ):
        OrderCoordinator.from_snapshot(snapshot)


def test_snapshot_hardening_requires_confirmation_for_confirmed_revision_v180():
    snapshot = _snapshot()
    snapshot["confirmations"] = []

    with pytest.raises(
        ValueError,
        match="confirmed revision requires a confirmation record",
    ):
        OrderCoordinator.from_snapshot(snapshot)


def test_snapshot_hardening_requires_latest_confirmation_revision_match_v180():
    snapshot = _snapshot()
    snapshot["confirmations"][-1]["revision"] = snapshot["revision"] - 1

    with pytest.raises(
        ValueError,
        match="confirmed revision must match latest confirmation",
    ):
        OrderCoordinator.from_snapshot(snapshot)


def test_snapshot_hardening_rejects_unconfirmed_current_revision_record_v180():
    snapshot = _snapshot()
    snapshot["confirmed_revision"] = None

    with pytest.raises(
        ValueError,
        match="current-revision confirmation cannot be unconfirmed",
    ):
        OrderCoordinator.from_snapshot(snapshot)


def test_snapshot_hardening_requires_confirmation_ledger_exact_match_v180():
    snapshot = _snapshot()
    ledger_confirmation = next(
        record
        for record in snapshot["ledger"]
        if record["event"] == "order_confirmed"
    )
    ledger_confirmation["data"]["source_text"] = "tampered"

    with pytest.raises(
        ValueError,
        match="confirmation records do not match confirmation ledger",
    ):
        OrderCoordinator.from_snapshot(snapshot)


def test_snapshot_hardening_requires_correction_ledger_exact_ids_v180():
    snapshot = _snapshot()
    ledger_correction = next(
        record
        for record in snapshot["ledger"]
        if record["event"] == "modifier_corrected"
    )
    ledger_correction["data"]["correction_id"] = "correction_999"

    with pytest.raises(
        ValueError,
        match="correction records do not match correction ledger",
    ):
        OrderCoordinator.from_snapshot(snapshot)


def test_snapshot_hardening_requires_correction_ledger_revisions_increase_v180():
    snapshot = _snapshot(two_corrections=True)
    correction_records = [
        record
        for record in snapshot["ledger"]
        if record["event"] == "modifier_corrected"
    ]
    correction_records[1]["revision"] = correction_records[0]["revision"]

    with pytest.raises(
        ValueError,
        match="correction ledger revisions must increase",
    ):
        OrderCoordinator.from_snapshot(snapshot)
