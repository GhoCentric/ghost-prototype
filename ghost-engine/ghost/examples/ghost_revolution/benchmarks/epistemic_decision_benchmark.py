"""
Ghost Revolution provenance decision benchmark v0.

Question:
Can a policy that distinguishes reports from belief and evidence avoid
an otherwise costly real game action under the same seeded world state?

Scope:
- one reproducible Millcross encounter,
- one intentionally false scout dispatch,
- one real guard investigation,
- one actual game consequence comparison.

This is not a claim of general intelligence or universal superiority.
It is a controlled, auditable benchmark slice that can be expanded into
a larger scenario matrix.
"""

from __future__ import annotations

from copy import deepcopy
import json

from ghost import GhostAPI
from ghost.examples.ghost_revolution.demo import (
    GhostRevolutionRun,
)


SCENARIO_ID = "millcross_false_scout_dispatch_v0"
TARGET = "millcross"
SUBJECT = "royal_presence:millcross"


def _shared_scout_report() -> dict:
    """
    Return the identical public report given to every non-oracle policy.

    The report is intentionally false in this benchmark scenario.
    """
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


def _objective_world() -> dict:
    """
    Benchmark-director truth.

    Policies do not receive this packet. It exists only to configure and
    audit the deterministic game environment.
    """
    return {
        "town": TARGET,
        "knight_present": True,
        "active_guards": 2,
        "royal_cache_exposed": False,
    }


def _prepare_game(seed: int) -> GhostRevolutionRun:
    """
    Construct the same game world for every policy.

    The knight placement is controlled scenario setup, not knowledge
    provided to the naive or provenance-aware policies.
    """
    game = GhostRevolutionRun(seed=seed)
    game.knight_town = TARGET

    if not game.travel(TARGET):
        raise RuntimeError(
            "Benchmark setup could not travel to Millcross."
        )

    return game


def _state_fingerprint(
    game: GhostRevolutionRun,
) -> dict:
    """
    Return the comparable game state used by the benchmark auditor.

    Policies never receive this full packet.
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
        "weapon_stock_total": game.weapon_stock_total(),
        "heat": game.heat,
        "royal_alert": game.royal_alert,
        "town_fear": town["fear"],
        "active_guards": game.guard_count(TARGET),
        "knight_town": game.knight_town,
        "alive": game.alive,
        "captured": game.captured,
    }


def _outcome(
    before: dict,
    game: GhostRevolutionRun,
) -> dict:
    """
    Measure raw game deltas plus a narrow exposure-cost metric.

    Exposure cost deliberately measures only crown response risk:
    capture, heat, and town fear. Loot and gold remain visible as raw
    deltas rather than being hidden inside an arbitrary total-utility
    score.
    """
    after = _state_fingerprint(game)

    heat_delta = after["heat"] - before["heat"]
    fear_delta = after["town_fear"] - before["town_fear"]

    exposure_cost = (
        (100 if after["captured"] else 0)
        + (max(0, heat_delta) * 10)
        + (max(0, fear_delta) * 5)
    )

    return {
        "after": after,
        "actions_spent": before["actions"] - after["actions"],
        "gold_delta": after["gold"] - before["gold"],
        "food_delta": after["food"] - before["food"],
        "weapon_delta": (
            after["weapon_stock_total"]
            - before["weapon_stock_total"]
        ),
        "heat_delta": heat_delta,
        "fear_delta": fear_delta,
        "captured": after["captured"],
        "alive": after["alive"],
        "exposure_cost": exposure_cost,
    }


def naive_report_truth_policy(
    report: dict,
) -> str:
    """
    Baseline: treat a scout report's claim as ground truth.
    """
    if report["claim"]["knight_status"] == "absent":
        return "seize_royal_supplies"

    return "secure_work"


def provenance_initial_policy(
    belief: dict,
) -> str:
    """
    Ghost policy before investigation.

    Low direct observation or high deception likelihood forces an
    investigation rather than immediate action on the claim.
    """
    quality = belief["report_quality"]

    if (
        quality["direct_observation"] < 0.50
        or quality["deception_likely"] >= 0.50
    ):
        return "investigate_guard"

    presence = belief["dimensions"]["royal_presence"]

    if presence["dominant_candidate"] == "knight_absent":
        return "seize_royal_supplies"

    return "secure_work"


def provenance_revised_policy(
    belief: dict,
) -> str:
    """
    Ghost policy after accessible evidence has revised belief.
    """
    presence = belief["dimensions"]["royal_presence"]

    if (
        presence["dominant_candidate"] == "knight_absent"
        and presence["confidence"] >= 0.65
    ):
        return "seize_royal_supplies"

    return "secure_work"


def oracle_diagnostic_policy(
    objective: dict,
) -> str:
    """
    Diagnostic upper bound only.

    This policy intentionally receives objective truth and therefore is
    never compared as a fair in-world decision maker.
    """
    if objective["knight_present"]:
        return "secure_work"

    return "seize_royal_supplies"


def _execute_seizure(
    game: GhostRevolutionRun,
) -> None:
    before_actions = game.actions

    game.seize_royal_supplies()

    if game.actions != before_actions - 1:
        raise RuntimeError(
            "Expected real supply seizure to spend one action."
        )

    if "Royal cache seized:" not in game.last_action_note:
        raise RuntimeError(
            "Expected real supply-seizure consequence text."
        )


def _execute_guard_investigation(
    game: GhostRevolutionRun,
) -> None:
    before_actions = game.actions

    game.question_guard()

    if game.actions != before_actions - 1:
        raise RuntimeError(
            "Expected real guard investigation to spend one action."
        )

    if "knight's patrols" not in game.last_action_note:
        raise RuntimeError(
            "Controlled benchmark expected a knight-presence guard read."
        )


def _execute_secure_work(
    game: GhostRevolutionRun,
) -> None:
    before_actions = game.actions

    packet = game.earn_honest_gold()

    if packet is None:
        raise RuntimeError(
            "Expected real Millcross work action to resolve."
        )

    if game.actions != before_actions - 1:
        raise RuntimeError(
            "Expected real work action to spend one action."
        )


def _build_epistemic_case(
    report: dict,
) -> tuple[GhostAPI, dict]:
    """
    Construct a separate public GhostAPI cognitive ledger.

    The objective fact is stored for audit only. The policy receives no
    get_fact() access and acts only on reports, beliefs, and evidence.
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


def _revise_from_guard_investigation(
    ghost: GhostAPI,
    previous_belief: dict,
) -> dict:
    """
    Record the player-visible guard read and revise the player's belief.
    """
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
            "reason": "guard behavior reveals nearby knight patrols",
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
        "report_quality": deepcopy(belief["report_quality"]),
        "previous_belief_id": belief["previous_belief_id"],
    }


def _run_naive_policy(
    seed: int,
    report: dict,
) -> dict:
    game = _prepare_game(seed)
    initial_state = _state_fingerprint(game)

    action = naive_report_truth_policy(report)

    if action == "seize_royal_supplies":
        _execute_seizure(game)
    else:
        _execute_secure_work(game)

    outcome = _outcome(initial_state, game)

    return {
        "label": "Naive reports = truth",
        "initial_state": initial_state,
        "decision_path": [action],
        "wrong_risk_action": action == "seize_royal_supplies",
        "outcome": outcome,
    }


def _run_provenance_policy(
    seed: int,
    report: dict,
) -> dict:
    game = _prepare_game(seed)
    initial_state = _state_fingerprint(game)

    ghost, audit = _build_epistemic_case(report)
    initial_belief = audit["initial_belief"]

    first_action = provenance_initial_policy(initial_belief)

    if first_action != "investigate_guard":
        raise RuntimeError(
            "Benchmark expected low-provenance report to trigger "
            "guard investigation."
        )

    _execute_guard_investigation(game)

    revision = _revise_from_guard_investigation(
        ghost,
        initial_belief,
    )

    revised_belief = revision["revised_belief"]
    second_action = provenance_revised_policy(revised_belief)

    if second_action == "seize_royal_supplies":
        _execute_seizure(game)
    else:
        _execute_secure_work(game)

    snapshot = ghost.snapshot()
    restored = GhostAPI.from_snapshot(snapshot)

    outcome = _outcome(initial_state, game)

    return {
        "label": "Ghost provenance policy",
        "initial_state": initial_state,
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
                restored.snapshot() == snapshot
            ),
            "restored_belief_matches": (
                restored.get_belief("player", SUBJECT)
                == revised_belief
            ),
        },
        "outcome": outcome,
    }


def _run_oracle_diagnostic(
    seed: int,
    objective: dict,
) -> dict:
    game = _prepare_game(seed)
    initial_state = _state_fingerprint(game)

    action = oracle_diagnostic_policy(objective)

    if action == "seize_royal_supplies":
        _execute_seizure(game)
    else:
        _execute_secure_work(game)

    outcome = _outcome(initial_state, game)

    return {
        "label": "Oracle diagnostic ceiling",
        "initial_state": initial_state,
        "decision_path": [action],
        "wrong_risk_action": action == "seize_royal_supplies",
        "outcome": outcome,
    }


def run_false_scout_report_benchmark(
    seed: int = 7,
) -> dict:
    """
    Execute the full controlled comparison.

    Every policy starts from a fresh same-seed game instance and receives
    the same public scout claim, except the oracle diagnostic which is
    explicitly given hidden objective truth as an upper bound.
    """
    report = _shared_scout_report()
    objective = _objective_world()

    naive = _run_naive_policy(
        seed,
        deepcopy(report),
    )
    provenance = _run_provenance_policy(
        seed,
        deepcopy(report),
    )
    oracle = _run_oracle_diagnostic(
        seed,
        deepcopy(objective),
    )

    initial_states = [
        naive["initial_state"],
        provenance["initial_state"],
        oracle["initial_state"],
    ]

    identical_initial_state = (
        initial_states[0]
        == initial_states[1]
        == initial_states[2]
    )

    naive_cost = naive["outcome"]["exposure_cost"]
    ghost_cost = provenance["outcome"]["exposure_cost"]

    checks = {
        "identical_seeded_start_state": identical_initial_state,
        "identical_shared_scout_report": (
            report == _shared_scout_report()
        ),
        "naive_took_false_report_risk": (
            naive["wrong_risk_action"] is True
        ),
        "ghost_revised_before_risk_action": (
            provenance["wrong_risk_action"] is False
            and provenance["beliefs"]["revised"][
                "dominant_candidate"
            ] == "knight_present"
        ),
        "ghost_reduced_exposure_cost": ghost_cost < naive_cost,
        "ghost_matches_oracle_final_action": (
            provenance["decision_path"][-1]
            == oracle["decision_path"][-1]
        ),
        "epistemic_snapshot_audits": (
            provenance["audit"][
                "snapshot_round_trip_matches"
            ]
            and provenance["audit"][
                "restored_belief_matches"
            ]
        ),
    }

    return {
        "benchmark": "ghost_revolution_provenance_v0",
        "scenario_id": SCENARIO_ID,
        "seed": seed,
        "scope": (
            "Exposure cost measures capture, heat, and town fear. "
            "Raw loot and gold deltas remain separate."
        ),
        "shared_scout_report": report,
        "objective_truth_for_audit_only": objective,
        "naive": naive,
        "ghost_provenance": provenance,
        "oracle_diagnostic": oracle,
        "comparison": {
            "naive_exposure_cost": naive_cost,
            "ghost_exposure_cost": ghost_cost,
            "avoidable_exposure_cost": naive_cost - ghost_cost,
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
    result: dict,
) -> None:
    outcome = result["outcome"]

    print(result["label"])
    print("  Decisions:", " -> ".join(result["decision_path"]))
    print(
        "  Deltas:"
        f" gold {outcome['gold_delta']:+d},"
        f" weapons {outcome['weapon_delta']:+d},"
        f" heat {outcome['heat_delta']:+d},"
        f" fear {outcome['fear_delta']:+d}"
    )
    print(
        "  Exposure cost:",
        outcome["exposure_cost"],
        "| Captured:",
        outcome["captured"],
    )


def print_benchmark(
    result: dict,
) -> None:
    """Render one readable benchmark report."""
    report = result["shared_scout_report"]
    truth = result["objective_truth_for_audit_only"]
    ghost = result["ghost_provenance"]

    print("=== GHOST REVOLUTION PROVENANCE BENCHMARK v0 ===")
    print()
    print("Scenario:", result["scenario_id"])
    print("Seed:", result["seed"])
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
        "  Policy access rule: naive sees report; "
        "Ghost sees report -> belief -> evidence; "
        "oracle sees truth only as a ceiling."
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
    print("COMPARISON")
    print(
        "  Avoidable exposure cost:",
        result["comparison"]["avoidable_exposure_cost"],
    )
    print(
        "  Scope:",
        result["scope"],
    )
    print()
    print("=== BENCHMARK CHECKS ===")

    for name, passed in result["checks"].items():
        prefix = "[PASS]" if passed else "[FAIL]"
        print(prefix, name)


def main() -> None:
    """Run the controlled provenance decision benchmark."""
    print_benchmark(
        run_false_scout_report_benchmark()
    )


if __name__ == "__main__":
    main()

