"""
Ghost Epistemic Public API Smoke Demo.

This module intentionally uses only:

    from ghost import GhostAPI

It demonstrates that:
- facts remain objective runtime state,
- observations remain actor-limited,
- reports do not become truth or forced belief,
- evidence can revise an explicit belief,
- tick does not rewrite belief into truth,
- snapshots restore deterministic epistemic state.
"""

from __future__ import annotations

from ghost import GhostAPI


SUBJECT = "millcross_food_loss"


def _dimension_line(
    belief: dict,
    dimension: str,
) -> str:
    packet = belief["dimensions"][dimension]

    return (
        f"{dimension}="
        f"{packet['dominant_candidate']} "
        f"({packet['confidence']:.3f})"
    )


def _quality_line(belief: dict) -> str:
    return ", ".join(
        f"{name}={value:.2f}"
        for name, value in sorted(
            belief["report_quality"].items()
        )
    )


def _print_belief(
    label: str,
    belief: dict,
) -> None:
    print(label)
    print(
        "  "
        + _dimension_line(belief, "cause")
        + " | "
        + _dimension_line(belief, "quantity")
    )
    print("  report quality: " + _quality_line(belief))


def run_demo() -> dict:
    """
    Execute one deterministic epistemic scenario using GhostAPI only.

    Returns a JSON-safe summary for test and integration use.
    """
    ghost = GhostAPI()

    print("=== GHOST EPISTEMIC API SMOKE DEMO ===")
    print()
    print("Public API only:")
    print("  from ghost import GhostAPI")
    print()

    fact = ghost.record_fact(
        fact_id="millcross_food_001",
        source="game_rule",
        subject="royal_guard",
        predicate="confiscated",
        object="millcross_food",
        attributes={
            "quantity": 6,
            "location": "millcross_market",
        },
    )

    player_belief_before_anything = ghost.get_belief(
        "player",
        SUBJECT,
    )

    print("[1] OBJECTIVE FACT")
    print(
        "  Runtime fact: royal_guard confiscated "
        "6 food units at millcross_market."
    )
    print(
        "  Player belief before observation/report:",
        player_belief_before_anything,
    )
    print()

    observation = ghost.observe(
        observer="villager_3",
        kind="visual",
        visible_features=[
            "royal_guards",
            "food_carts",
            "guards_departing",
        ],
        reliability=0.65,
        subject=SUBJECT,
        provenance={
            "location": "millcross_market",
            "witness_distance": "near",
        },
    )

    villager_belief = ghost.evaluate_beliefs(
        holder="villager_3",
        subject=SUBJECT,
        candidates={
            "cause": {
                "royal_confiscation": 0.55,
                "rebel_theft": 0.10,
                "merchant_hoarding": 0.05,
                "unknown": 0.30,
            },
            "quantity": {
                "all_food_taken": 0.18,
                "some_food_taken": 0.76,
                "quantity_unknown": 0.06,
            },
        },
        report_quality={
            "direct_observation": 0.65,
            "exaggeration_likely": 0.25,
            "rumor_repetition_likely": 0.10,
        },
        evidence_ids=[observation["id"]],
        provenance={
            "reason": "villager saw guards and food carts leaving",
        },
    )

    print("[2] ACTOR-LIMITED OBSERVATION")
    print(
        "  villager_3 sees:",
        ", ".join(observation["visible_features"]),
    )
    _print_belief(
        "  villager_3 explicitly evaluates a belief:",
        villager_belief,
    )
    print()

    report = ghost.report(
        speaker="villager_3",
        audience="player",
        claim={
            "statement": "They took everything.",
            "cause": "royal_confiscation",
            "quantity": "all_food_taken",
        },
        confidence=0.82,
        source_belief_id=villager_belief["id"],
        provenance={
            "speech_act": "warning",
            "location": "millcross_market",
        },
    )

    player_belief_after_report = ghost.get_belief(
        "player",
        SUBJECT,
    )

    print("[3] EXAGGERATED REPORT")
    print('  villager_3 tells player: "They took everything."')
    print(
        "  Report record:",
        report["id"],
        "| linked belief:",
        report["source_belief_id"],
    )
    print(
        "  Player belief immediately after receiving report:",
        player_belief_after_report,
    )
    print("  Result: report is a claim, not fact or forced belief.")
    print()

    player_initial_belief = ghost.evaluate_beliefs(
        holder="player",
        subject=SUBJECT,
        candidates={
            "cause": {
                "royal_confiscation": 0.30,
                "rebel_theft": 0.10,
                "merchant_hoarding": 0.05,
                "unknown": 0.55,
            },
            "quantity": {
                "all_food_taken": 0.50,
                "some_food_taken": 0.25,
                "quantity_unknown": 0.25,
            },
        },
        report_quality={
            "direct_observation": 0.15,
            "exaggeration_likely": 0.70,
            "rumor_repetition_likely": 0.35,
        },
        evidence_ids=[report["id"]],
        provenance={
            "reason": "player heard villager_3 report",
        },
    )

    print("[4] PLAYER EXPLICITLY INTERPRETS REPORT")
    _print_belief(
        "  Player initial belief after evaluating the report:",
        player_initial_belief,
    )
    print()

    ledger_evidence = ghost.add_evidence(
        evidence_type="market_inventory_check",
        source="merchant_ledger",
        subject=SUBJECT,
        available_to="player",
        supports={
            "cause": {
                "royal_confiscation": 0.60,
            },
            "quantity": {
                "some_food_taken": 0.65,
            },
            "report_quality": {
                "direct_observation": 0.45,
            },
        },
        contradicts={
            "quantity": {
                "all_food_taken": 0.40,
            },
            "report_quality": {
                "exaggeration_likely": 0.40,
            },
        },
        provenance={
            "ledger_count": 6,
            "warehouse_stock_remaining": True,
        },
    )

    player_revised_belief = ghost.evaluate_beliefs(
        holder="player",
        subject=SUBJECT,
        previous_belief_id=player_initial_belief["id"],
        evidence_ids=[ledger_evidence["id"]],
        provenance={
            "reason": "player inspected merchant ledger",
        },
    )

    print("[5] NEW EVIDENCE REVISES BELIEF")
    print(
        "  Merchant ledger supports confiscation, "
        "but contradicts 'everything was taken.'"
    )
    _print_belief(
        "  Player revised belief:",
        player_revised_belief,
    )
    print(
        "  Original belief remains in history:",
        player_initial_belief["id"],
    )
    print(
        "  Revision points backward through:",
        player_revised_belief["previous_belief_id"],
    )
    print()

    belief_before_tick = ghost.get_belief(
        "player",
        SUBJECT,
    )

    tick_packet = ghost.tick()

    belief_after_tick = ghost.get_belief(
        "player",
        SUBJECT,
    )

    snapshot = ghost.snapshot()
    restored = GhostAPI.from_snapshot(snapshot)

    checks = {
        "fact_did_not_create_player_belief": (
            player_belief_before_anything is None
        ),
        "report_did_not_force_player_belief": (
            player_belief_after_report is None
        ),
        "ledger_revised_player_belief": (
            player_revised_belief["id"]
            != player_initial_belief["id"]
        ),
        "tick_did_not_rewrite_belief": (
            belief_after_tick == belief_before_tick
        ),
        "snapshot_round_trip_matches": (
            restored.snapshot() == snapshot
        ),
        "restored_belief_matches": (
            restored.get_belief(
                "player",
                SUBJECT,
            )
            == player_revised_belief
        ),
    }

    print("[6] TICK AND SNAPSHOT RESTORE")
    print(
        "  Epistemic tick record:",
        tick_packet["epistemic"]["id"],
    )
    print(
        "  Tick changed belief:",
        {
            True: "no",
            False: "yes",
        }[checks["tick_did_not_rewrite_belief"]],
    )
    print(
        "  Snapshot round-trip matches:",
        checks["snapshot_round_trip_matches"],
    )
    print()

    print("=== SMOKE CHECKS ===")

    for name, passed in checks.items():
        print(
            {
                True: "[PASS] ",
                False: "[FAIL] ",
            }[passed]
            + name
        )

    print()

    return {
        "fact": fact,
        "observation": observation,
        "villager_belief": villager_belief,
        "report": report,
        "player_initial_belief": player_initial_belief,
        "ledger_evidence": ledger_evidence,
        "player_revised_belief": player_revised_belief,
        "tick_packet": tick_packet,
        "snapshot": snapshot,
        "checks": checks,
    }


def main() -> None:
    """Run the public epistemic smoke demonstration."""
    run_demo()


if __name__ == "__main__":
    main()

