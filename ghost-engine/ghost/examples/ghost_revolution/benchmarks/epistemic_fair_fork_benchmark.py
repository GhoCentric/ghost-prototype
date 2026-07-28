"""
Ghost Revolution fair-fork provenance benchmark v1.

Question:
When every policy starts from one exact game snapshot and receives the
same two-action horizon, does report -> belief -> evidence -> revision
change a real game decision and its measurable tradeoff?

This benchmark does not use a composite "win score." It reports raw
resource, heat, fear, action, and survival deltas side by side.
"""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

from ghost import GhostAPI
from ghost.examples.ghost_revolution.demo import (
    GhostRevolutionRun,
)


SCENARIO_ID = "millcross_false_scout_dispatch_fair_fork_v1"
TARGET = "millcross"
SUBJECT = "royal_presence:millcross"
ACTION_BUDGET = 2


def _json_copy(value, label: str):
    try:
        return json.loads(
            json.dumps(
                value,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"{label} must be JSON-safe"
        ) from error


def _snapshot_digest(snapshot: dict) -> str:
    payload = json.dumps(
        snapshot,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return sha256(payload).hexdigest()


def _shared_false_report() -> dict:
    """Return the same public report given to non-oracle policies."""
    return {
        "speaker": "scout_17",
        "confidence": 0.92,
        "claim": {
            "statement": (
                "The knight has left Millcross. "
                "The royal cache is exposed."
            ),
            "town": TARGET,
            "knight_status": "absent",
            "recommended_action": "seize_royal_supplies",
        },
    }


def _audit_truth() -> dict:
    """
    Director-only scenario truth.

    The naive and Ghost policies never receive this packet.
    """
    return {
        "town": TARGET,
        "knight_present": True,
        "active_guards": 2,
        "royal_cache_exposed": False,
    }


def _create_decision_fork(
    seed: int,
) -> dict:
    """
    Build one exact Millcross decision point and snapshot it.

    The scenario director sets the knight location and a two-action
    horizon before the snapshot. Policies receive only their permitted
    information after restoration.
    """
    game = GhostRevolutionRun(seed=seed)
    game.knight_town = TARGET

    if not game.travel(TARGET):
        raise RuntimeError(
            "Benchmark setup could not travel to Millcross."
        )

    game.actions = ACTION_BUDGET

    snapshot = game.snapshot()

    if snapshot["state"]["actions"] != ACTION_BUDGET:
        raise RuntimeError(
            "Benchmark snapshot action budget is invalid."
        )

    return snapshot


def _state_view(
    game: GhostRevolutionRun,
) -> dict:
    """
    Return audit fields only.

    Policies do not receive this view; it is collected after decisions
    to compare branches.
    """
    town = game.towns[TARGET]

    return {
        "location": game.location,
        "phase": game.phase,
        "phase_number": game.phase_number,
        "phase_day": game.phase_day,
        "actions": game.actions,
        "followers": game.followers,
        "gold": game.gold,
        "food": game.food,
        "weapons": game.weapon_stock_total(),
        "heat": game.heat,
        "royal_alert": game.royal_alert,
        "town_fear": town["fear"],
        "town_trust": game.town_trust(TARGET),
        "active_guards": game.guard_count(TARGET),
        "knight_town": game.knight_town,
        "alive": game.alive,
        "captured": game.captured,
    }


def _raw_outcome(
    before: dict,
    game: GhostRevolutionRun,
) -> dict:
    """Return raw deltas without assigning an arbitrary utility score."""
    after = _state_view(game)

    return {
        "after": after,
        "actions_spent": before["actions"] - after["actions"],
        "actions_remaining": after["actions"],
        "gold_delta": after["gold"] - before["gold"],
        "food_delta": after["food"] - before["food"],
        "weapon_delta": after["weapons"] - before["weapons"],
        "heat_delta": after["heat"] - before["heat"],
        "fear_delta": after["town_fear"] - before["town_fear"],
        "royal_alert_delta": (
            after["royal_alert"] - before["royal_alert"]
        ),
        "trust_delta": after["town_trust"] - before["town_trust"],
        "captured": after["captured"],
        "alive": after["alive"],
    }


def _execute_action(
    game: GhostRevolutionRun,
    action: str,
) -> None:
    """Run one real game facade action and verify one action was spent."""
    before_actions = game.actions

    if action == "seize_royal_supplies":
        game.seize_royal_supplies()

        if "Royal cache seized:" not in game.last_action_note:
            raise RuntimeError(
                "Expected real supply-seizure consequence text."
            )

    elif action == "investigate_guard":
        game.question_guard()

        if "Guard read" not in game.last_action_note:
            raise RuntimeError(
                "Expected real guard-investigation consequence text."
            )

    elif action == "secure_work":
        packet = game.earn_honest_gold()

        if packet is None:
            raise RuntimeError(
                "Expected real Millcross work action to resolve."
            )

    else:
        raise ValueError(
            f"Unsupported benchmark action: {action}"
        )

    if game.actions != before_actions - 1:
        raise RuntimeError(
            "Expected benchmark action to spend exactly one action."
        )


def naive_report_truth_policy(
    report: dict,
) -> tuple[str, str]:
    """Baseline: turn the report's literal claim directly into action."""
    if report["claim"]["knight_status"] == "absent":
        return (
            "seize_royal_supplies",
            "secure_work",
        )

    return (
        "secure_work",
        "investigate_guard",
    )


def provenance_initial_policy(
    belief: dict,
) -> str:
    """
    Decide whether the report warrants investigation before risk.

    The policy only receives an actor-owned belief packet.
    """
    quality = belief["report_quality"]

    if (
        quality["direct_observation"] < 0.50
        or quality["deception_likely"] >= 0.50
    ):
        return "investigate_guard"

    presence = belief["dimensions"]["royal_presence"]

    if (
        presence["dominant_candidate"] == "knight_absent"
        and presence["confidence"] >= 0.65
    ):
        return "seize_royal_supplies"

    return "secure_work"


def provenance_revised_policy(
    belief: dict,
) -> str:
    """Choose the second action after accessible evidence is evaluated."""
    presence = belief["dimensions"]["royal_presence"]

    if (
        presence["dominant_candidate"] == "knight_absent"
        and presence["confidence"] >= 0.65
    ):
        return "seize_royal_supplies"

    return "secure_work"


def oracle_budget_matched_policy(
    objective: dict,
) -> tuple[str, str]:
    """
    Diagnostic only, not a fair in-world policy.

    It sees hidden truth. The safe guard read is included solely to fill
    the same fixed two-action horizon used by the other branches.
    """
    if objective["knight_present"]:
        return (
            "secure_work",
            "investigate_guard",
        )

    return (
        "seize_royal_supplies",
        "secure_work",
    )


def _build_epistemic_case(
    report: dict,
) -> tuple[GhostAPI, dict]:
    """
    Create a separate public GhostAPI information ledger.

    Objective truth is stored for audit, but the Ghost policy receives
    only report-derived belief followed by player-accessible evidence.
    """
    ghost = GhostAPI()

    fact = ghost.record_fact(
        fact_id="millcross_knight_presence_001",
        source="benchmark_director",
        subject=SUBJECT,
        predicate="knight_present",
        object="true",
        attributes={
            "town": TARGET,
            "purpose": "hidden_benchmark_truth",
        },
    )

    report_record = ghost.report(
        speaker=report["speaker"],
        audience="player",
        claim=deepcopy(report["claim"]),
        confidence=report["confidence"],
        provenance={
            "channel": "scout_dispatch",
            "scenario_id": SCENARIO_ID,
        },
    )

    initial_belief = ghost.evaluate_beliefs(
        holder="player",
        subject=SUBJECT,
        candidates={
            "royal_presence": {
                "knight_absent": 0.80,
                "knight_present": 0.10,
                "unknown": 0.10,
            },
        },
        report_quality={
            "direct_observation": 0.10,
            "deception_likely": 0.65,
            "rumor_repetition_likely": 0.55,
        },
        evidence_ids=[report_record["id"]],
        provenance={
            "basis": "unverified scout dispatch",
            "scenario_id": SCENARIO_ID,
        },
    )

    return ghost, {
        "fact_id": fact["fact_id"],
        "fact_record_id": fact["id"],
        "report_id": report_record["id"],
        "initial_belief": initial_belief,
    }


def _revise_from_guard_read(
    ghost: GhostAPI,
    previous_belief: dict,
    game_note: str,
) -> dict:
    """Append player-visible guard evidence and revise belief."""
    observation = ghost.observe(
        observer="player",
        kind="guard_read",
        visible_features=[
            "guard_glances_toward_knight_patrols",
            "guard_defection_unlikely",
        ],
        reliability=0.85,
        subject=SUBJECT,
        provenance={
            "town": TARGET,
            "action": "question_guard",
            "game_note": game_note,
        },
    )

    evidence = ghost.add_evidence(
        evidence_type="guard_visual_read",
        source="player_guard_read",
        subject=SUBJECT,
        available_to="player",
        supports={
            "royal_presence": {
                "knight_present": 0.90,
            },
            "report_quality": {
                "direct_observation": 0.75,
            },
        },
        contradicts={
            "royal_presence": {
                "knight_absent": 0.70,
            },
            "report_quality": {
                "deception_likely": 0.45,
            },
        },
        provenance={
            "town": TARGET,
            "action": "question_guard",
            "game_note": game_note,
        },
    )

    revised = ghost.evaluate_beliefs(
        holder="player",
        subject=SUBJECT,
        previous_belief_id=previous_belief["id"],
        evidence_ids=[
            observation["id"],
            evidence["id"],
        ],
        provenance={
            "basis": "guard investigation",
            "scenario_id": SCENARIO_ID,
        },
    )

    return {
        "observation_id": observation["id"],
        "evidence_id": evidence["id"],
        "revised_belief": revised,
    }


def _belief_summary(
    belief: dict,
) -> dict:
    presence = belief["dimensions"]["royal_presence"]

    return {
        "dominant_candidate": presence["dominant_candidate"],
        "confidence": presence["confidence"],
        "uncertainty": presence["uncertainty"],
        "previous_belief_id": belief["previous_belief_id"],
        "report_quality": deepcopy(belief["report_quality"]),
    }


def _run_action_path(
    snapshot: dict,
    actions: tuple[str, str],
) -> dict:
    """Restore one exact game fork and execute exactly two actions."""
    game = GhostRevolutionRun.from_snapshot(
        deepcopy(snapshot)
    )
    restored_exactly = game.snapshot() == snapshot
    before = _state_view(game)

    if not restored_exactly:
        raise RuntimeError(
            "Benchmark branch did not restore exact snapshot state."
        )

    if before["actions"] != ACTION_BUDGET:
        raise RuntimeError(
            "Benchmark branch action budget is invalid."
        )

    for action in actions:
        _execute_action(game, action)

    outcome = _raw_outcome(before, game)

    if (
        outcome["actions_spent"] != ACTION_BUDGET
        or outcome["actions_remaining"] != 0
    ):
        raise RuntimeError(
            "Benchmark branch did not exhaust fixed action budget."
        )

    return {
        "fork_snapshot_sha256": _snapshot_digest(snapshot),
        "restored_exactly": restored_exactly,
        "initial_state": before,
        "decision_path": list(actions),
        "outcome": outcome,
    }


def _run_naive_branch(
    snapshot: dict,
    report: dict,
) -> dict:
    actions = naive_report_truth_policy(report)
    result = _run_action_path(snapshot, actions)

    result.update(
        {
            "label": "Naive reports = truth",
            "wrong_risk_action": (
                actions[0] == "seize_royal_supplies"
            ),
        }
    )

    return result


def _run_ghost_branch(
    snapshot: dict,
    report: dict,
) -> dict:
    ghost, audit = _build_epistemic_case(report)
    initial_belief = audit["initial_belief"]
    first_action = provenance_initial_policy(initial_belief)

    if first_action != "investigate_guard":
        raise RuntimeError(
            "Benchmark expected low-provenance report to investigate."
        )

    game = GhostRevolutionRun.from_snapshot(
        deepcopy(snapshot)
    )
    restored_exactly = game.snapshot() == snapshot
    before = _state_view(game)

    if not restored_exactly:
        raise RuntimeError(
            "Benchmark branch did not restore exact snapshot state."
        )

    _execute_action(game, first_action)

    revision = _revise_from_guard_read(
        ghost,
        initial_belief,
        game.last_action_note,
    )
    revised_belief = revision["revised_belief"]
    second_action = provenance_revised_policy(revised_belief)

    _execute_action(game, second_action)

    outcome = _raw_outcome(before, game)

    if (
        outcome["actions_spent"] != ACTION_BUDGET
        or outcome["actions_remaining"] != 0
    ):
        raise RuntimeError(
            "Benchmark branch did not exhaust fixed action budget."
        )

    epistemic_snapshot = ghost.snapshot()
    restored_epistemic = GhostAPI.from_snapshot(
        epistemic_snapshot
    )

    return {
        "label": "Ghost provenance policy",
        "fork_snapshot_sha256": _snapshot_digest(snapshot),
        "restored_exactly": restored_exactly,
        "initial_state": before,
        "decision_path": [
            first_action,
            second_action,
        ],
        "wrong_risk_action": (
            second_action == "seize_royal_supplies"
        ),
        "beliefs": {
            "initial": _belief_summary(initial_belief),
            "revised": _belief_summary(revised_belief),
        },
        "audit": {
            "fact_id": audit["fact_id"],
            "fact_record_id": audit["fact_record_id"],
            "report_id": audit["report_id"],
            "observation_id": revision["observation_id"],
            "evidence_id": revision["evidence_id"],
            "snapshot_round_trip_matches": (
                restored_epistemic.snapshot()
                == epistemic_snapshot
            ),
            "restored_belief_matches": (
                restored_epistemic.get_belief(
                    "player",
                    SUBJECT,
                )
                == revised_belief
            ),
        },
        "outcome": outcome,
    }


def _run_oracle_branch(
    snapshot: dict,
    objective: dict,
) -> dict:
    actions = oracle_budget_matched_policy(objective)
    result = _run_action_path(snapshot, actions)

    result.update(
        {
            "label": "Oracle budget-matched diagnostic",
            "wrong_risk_action": (
                actions[0] == "seize_royal_supplies"
            ),
        }
    )

    return result


def _delta_difference(
    left: dict,
    right: dict,
) -> dict:
    """Return left minus right for raw comparable outcome fields."""
    return {
        field: (
            left["outcome"][field]
            - right["outcome"][field]
        )
        for field in (
            "actions_spent",
            "gold_delta",
            "food_delta",
            "weapon_delta",
            "heat_delta",
            "fear_delta",
            "royal_alert_delta",
            "trust_delta",
        )
    }


def run_fair_fork_benchmark(
    seed: int = 7,
) -> dict:
    """
    Run the same report through exact snapshot forks.

    The benchmark snapshot supplies a fixed two-action horizon. The
    oracle is an explicit audit control, not a fair in-world competitor.
    """
    report = _shared_false_report()
    objective = _audit_truth()
    fork_snapshot = _create_decision_fork(seed)
    fork_hash = _snapshot_digest(fork_snapshot)

    naive = _run_naive_branch(
        fork_snapshot,
        deepcopy(report),
    )
    ghost = _run_ghost_branch(
        fork_snapshot,
        deepcopy(report),
    )
    oracle = _run_oracle_branch(
        fork_snapshot,
        deepcopy(objective),
    )

    branches = [naive, ghost, oracle]

    checks = {
        "one_exact_snapshot_forked_three_times": all(
            branch["restored_exactly"]
            and branch["fork_snapshot_sha256"] == fork_hash
            for branch in branches
        ),
        "identical_initial_state_after_restore": (
            naive["initial_state"]
            == ghost["initial_state"]
            == oracle["initial_state"]
        ),
        "same_false_report_for_non_oracle_policies": (
            report == _shared_false_report()
        ),
        "equal_two_action_budget": all(
            branch["outcome"]["actions_spent"]
            == ACTION_BUDGET
            and branch["outcome"]["actions_remaining"] == 0
            for branch in branches
        ),
        "naive_takes_report_as_truth": (
            naive["wrong_risk_action"] is True
        ),
        "ghost_revises_before_second_action": (
            ghost["decision_path"] == [
                "investigate_guard",
                "secure_work",
            ]
            and ghost["beliefs"]["revised"][
                "dominant_candidate"
            ] == "knight_present"
        ),
        "ghost_matches_oracle_safety_deltas": (
            ghost["outcome"]["heat_delta"]
            == oracle["outcome"]["heat_delta"]
            and ghost["outcome"]["fear_delta"]
            == oracle["outcome"]["fear_delta"]
            and ghost["outcome"]["captured"]
            == oracle["outcome"]["captured"]
            and ghost["outcome"]["alive"]
            == oracle["outcome"]["alive"]
        ),
        "epistemic_snapshot_audits": (
            ghost["audit"]["snapshot_round_trip_matches"]
            and ghost["audit"]["restored_belief_matches"]
        ),
    }

    return {
        "benchmark": "ghost_revolution_fair_fork_provenance_v1",
        "scenario_id": SCENARIO_ID,
        "seed": seed,
        "action_budget": ACTION_BUDGET,
        "scope": (
            "Raw action, resource, heat, fear, and survival deltas "
            "are reported separately. No composite utility score "
            "is used."
        ),
        "fork": {
            "snapshot_sha256": fork_hash,
            "snapshot_schema_version": (
                fork_snapshot["schema_version"]
            ),
            "state_actions": fork_snapshot["state"]["actions"],
        },
        "shared_scout_report": report,
        "objective_truth_for_audit_only": objective,
        "naive": naive,
        "ghost_provenance": ghost,
        "oracle_diagnostic": oracle,
        "raw_differences": {
            "naive_minus_ghost": _delta_difference(
                naive,
                ghost,
            ),
            "ghost_minus_oracle": _delta_difference(
                ghost,
                oracle,
            ),
        },
        "checks": checks,
    }


def _belief_line(
    belief: dict,
) -> str:
    return (
        belief["dominant_candidate"].replace("_", " ")
        + f" ({belief['confidence']:.0%})"
    )


def _print_policy_row(
    branch: dict,
) -> None:
    outcome = branch["outcome"]

    print(branch["label"])
    print("  Decisions:", " -> ".join(branch["decision_path"]))
    print(
        "  Raw deltas:"
        f" gold {outcome['gold_delta']:+d},"
        f" food {outcome['food_delta']:+d},"
        f" weapons {outcome['weapon_delta']:+d},"
        f" heat {outcome['heat_delta']:+d},"
        f" fear {outcome['fear_delta']:+d},"
        f" alert {outcome['royal_alert_delta']:+d}"
    )
    print(
        "  Budget:"
        f" spent {outcome['actions_spent']},"
        f" remaining {outcome['actions_remaining']}"
        f" | Captured: {outcome['captured']}"
    )


def print_fair_fork_benchmark(
    result: dict,
) -> None:
    """Print the benchmark without hiding its tradeoffs."""
    report = result["shared_scout_report"]
    truth = result["objective_truth_for_audit_only"]
    ghost = result["ghost_provenance"]
    difference = result["raw_differences"]["naive_minus_ghost"]

    print("=== GHOST REVOLUTION FAIR-FORK BENCHMARK v1 ===")
    print()
    print("Scenario:", result["scenario_id"])
    print("Seed:", result["seed"])
    print("Exact fork SHA-256:", result["fork"]["snapshot_sha256"])
    print("Action budget per branch:", result["action_budget"])
    print()
    print("CONTROLLED INPUT")
    print(
        "  Shared scout report:",
        report["claim"]["statement"],
    )
    print(
        "  Audit-only world truth:",
        "knight present"
        if truth["knight_present"]
        else "knight absent",
    )
    print(
        "  Access: naive sees report; Ghost sees report -> belief "
        "-> evidence; oracle sees hidden truth only as a diagnostic."
    )
    print()
    print("POLICY OUTCOMES")

    _print_policy_row(result["naive"])
    _print_policy_row(ghost)
    _print_policy_row(result["oracle_diagnostic"])

    print()
    print("GHOST BELIEF REVISION")
    print(
        "  Before investigation:",
        _belief_line(ghost["beliefs"]["initial"]),
    )
    print(
        "  After guard evidence:",
        _belief_line(ghost["beliefs"]["revised"]),
    )
    print(
        "  Revision links to:",
        ghost["beliefs"]["revised"][
            "previous_belief_id"
        ],
    )
    print()
    print("RAW TRADEOFF: NAIVE MINUS GHOST")
    print(
        "  "
        f"gold {difference['gold_delta']:+d}, "
        f"food {difference['food_delta']:+d}, "
        f"weapons {difference['weapon_delta']:+d}, "
        f"heat {difference['heat_delta']:+d}, "
        f"fear {difference['fear_delta']:+d}, "
        f"actions {difference['actions_spent']:+d}"
    )
    print(
        "  Interpretation: the benchmark reports this tradeoff "
        "without converting it into a hidden total score."
    )
    print()
    print("=== BENCHMARK CHECKS ===")

    for name, passed in result["checks"].items():
        prefix = "[PASS]" if passed else "[FAIL]"
        print(prefix, name)


def main() -> None:
    """Run the fair-fork provenance benchmark."""
    print_fair_fork_benchmark(
        run_fair_fork_benchmark()
    )


if __name__ == "__main__":
    main()

