"""Runnable business-state proof for Ghost order coordination."""

from __future__ import annotations

from ghost.examples.order_coordination import (
    OrderCoordinator,
    OrderSubmissionBlocked,
)


def _print_status(runtime: OrderCoordinator) -> None:
    status = runtime.status()
    print(
        "  submission_allowed:",
        status["submission_allowed"],
    )
    print("  blockers:", status["blockers"])
    print("  order:", runtime.order()["items"])
    print()


def run_demo() -> dict:
    runtime = OrderCoordinator()

    print("=== GHOST ORDER COORDINATION DEMO ===")
    print()
    print("LLMs may propose meaning.")
    print("Ghost-backed state decides what is accepted.")
    print()

    first = runtime.add_item(
        "op_001",
        "burger",
    )["result"]["item"]
    second = runtime.add_item(
        "op_002",
        "burger",
    )["result"]["item"]

    print("[1] Two similar items exist")
    _print_status(runtime)

    ambiguous = runtime.propose_modifier(
        "op_003",
        modifier="add_bacon",
        candidate_item_ids=[
            first["item_id"],
            second["item_id"],
        ],
        source_text="Put bacon on the other one.",
    )["result"]
    ambiguity_id = ambiguous["ambiguity"]["ambiguity_id"]

    print("[2] Ambiguous modifier target")
    print("  customer: Put bacon on the other one.")
    print("  outcome:", ambiguous["outcome"])
    print("  ambiguity_id:", ambiguity_id)
    _print_status(runtime)

    try:
        runtime.submit("op_004")
    except OrderSubmissionBlocked as exc:
        print("[3] Unsafe submission is refused")
        print(" ", exc)
        print()

    resolved = runtime.resolve_ambiguity(
        "op_005",
        ambiguity_id=ambiguity_id,
        target_item_id=second["item_id"],
        source_text="The second burger.",
    )["result"]

    print("[4] Customer clarification resolves the target")
    print(
        "  belief confidence:",
        resolved["belief"]["dimensions"]["target"][
            "confidence"
        ],
    )
    _print_status(runtime)

    runtime.confirm_order(
        "op_006",
        "Yes, that order is correct.",
    )

    print("[5] Current revision is confirmed")
    _print_status(runtime)

    runtime.correct_modifier(
        "op_007",
        modifier="add_bacon",
        from_item_id=second["item_id"],
        to_item_id=first["item_id"],
        source_text=(
            "Actually, move the bacon to the first burger."
        ),
    )

    print("[6] Correction invalidates stale confirmation")
    _print_status(runtime)

    runtime.confirm_order(
        "op_008",
        "Yes, the corrected order is right.",
    )
    submitted = runtime.submit("op_009")

    print("[7] Confirmed corrected order is submitted")
    _print_status(runtime)

    snapshot = runtime.snapshot()
    epistemic_records = snapshot["ghost"]["epistemic"][
        "records"
    ]
    print("  epistemic records:", len(epistemic_records))
    print("  ledger records:", len(snapshot["ledger"]))

    return {
        "submitted": submitted["result"]["order"],
        "status": runtime.status(),
        "snapshot": snapshot,
    }


if __name__ == "__main__":
    run_demo()
