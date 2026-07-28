"""Controlled Ghost Revolution provenance scenario matrix."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

from ghost import GhostAPI
from ghost.examples.ghost_revolution.demo import GhostRevolutionRun


ACTION_BUDGET = 2
SEEDS = (7, 17, 29)
MATRIX_TOWNS = ("millcross", "crownmarket")

# Ashfield is intentionally excluded: it begins without an active guard, while
# this benchmark's only investigation action is the real public guard read.
SCENARIOS = (
    {
        "id": "truthful_high_provenance_absence",
        "label": "Truthful high-provenance absence",
        "knight_present": False,
        "reports": (("scout_17", .95, "absent", "I watched the patrol route. The knight left {town}."),),
        "candidates": {"knight_absent": .90, "knight_present": .05, "unknown": .05},
        "quality": {"direct_observation": .95, "deception_likely": .05, "rumor_repetition_likely": .05, "contradictory_sources": 0.0},
        "mode": "act",
    },
    {
        "id": "truthful_low_provenance_absence",
        "label": "Truthful low-provenance absence",
        "knight_present": False,
        "reports": (("traveler_08", .58, "absent", "Road talk says the knight may have left {town}."),),
        "candidates": {"knight_absent": .80, "knight_present": .10, "unknown": .10},
        "quality": {"direct_observation": .10, "deception_likely": .10, "rumor_repetition_likely": .80, "contradictory_sources": 0.0},
        "mode": "investigate",
    },
    {
        "id": "truthful_high_provenance_presence",
        "label": "Truthful high-provenance presence",
        "knight_present": True,
        "reports": (("scout_21", .95, "present", "I saw the knight enter {town} with the patrol."),),
        "candidates": {"knight_absent": .05, "knight_present": .90, "unknown": .05},
        "quality": {"direct_observation": .95, "deception_likely": .05, "rumor_repetition_likely": .05, "contradictory_sources": 0.0},
        "mode": "avoid",
    },
    {
        "id": "deceptive_false_absence",
        "label": "Deceptive false absence",
        "knight_present": True,
        "reports": (("unknown_runner", .92, "absent", "The knight left {town}. The cache is exposed."),),
        "candidates": {"knight_absent": .80, "knight_present": .10, "unknown": .10},
        "quality": {"direct_observation": .10, "deception_likely": .85, "rumor_repetition_likely": .55, "contradictory_sources": 0.0},
        "mode": "investigate",
    },
    {
        "id": "weak_evidence_false_absence",
        "label": "Weak-evidence false absence",
        "knight_present": True,
        "reports": (("market_rumor", .55, "absent", "A market rumor says the knight may have left {town}."),),
        "candidates": {"knight_absent": .55, "knight_present": .20, "unknown": .25},
        "quality": {"direct_observation": .10, "deception_likely": .10, "rumor_repetition_likely": .90, "contradictory_sources": 0.0},
        "mode": "investigate",
    },
    {
        "id": "ambiguous_false_absence",
        "label": "Ambiguous false absence",
        "knight_present": True,
        "reports": (("scout_34", .64, "absent", "I could not confirm the knight remains in {town}; patrols looked thinner."),),
        "candidates": {"knight_absent": .46, "knight_present": .42, "unknown": .12},
        "quality": {"direct_observation": .65, "deception_likely": .10, "rumor_repetition_likely": .10, "contradictory_sources": 0.0},
        "mode": "investigate",
    },
    {
        "id": "contradictory_sources_false_absence",
        "label": "Contradictory sources false absence",
        "knight_present": True,
        "reports": (
            ("scout_55", .92, "absent", "The knight left {town}; the cache should be exposed."),
            ("courier_12", .70, "present", "A courier saw the knight's colors moving into {town}."),
        ),
        "candidates": {"knight_absent": .55, "knight_present": .35, "unknown": .10},
        "quality": {"direct_observation": .80, "deception_likely": .05, "rumor_repetition_likely": .05, "contradictory_sources": .75},
        "mode": "investigate",
    },
)

LOW_PROVENANCE_IDS = {s["id"] for s in SCENARIOS if s["mode"] == "investigate"}


def _digest(value) -> str:
    return sha256(json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _reports(scenario: dict, town: str) -> list[dict]:
    out = []
    for speaker, confidence, status, text in scenario["reports"]:
        out.append({
            "speaker": speaker,
            "confidence": confidence,
            "claim": {
                "statement": text.format(town=town.title()),
                "town": town,
                "knight_status": status,
                "recommended_action": "seize_royal_supplies" if status == "absent" else "secure_work",
            },
        })
    return out


def _objective(scenario: dict, town: str) -> dict:
    return {"town": town, "knight_present": scenario["knight_present"]}


def _fork(seed: int, town: str, knight_present: bool) -> dict:
    game = GhostRevolutionRun(seed=seed)
    game.knight_town = town if knight_present else "castle"
    if not game.travel(town):
        raise RuntimeError("Matrix setup could not travel to target town.")
    game.actions = ACTION_BUDGET
    snapshot = game.snapshot()
    if snapshot["state"]["actions"] != ACTION_BUDGET:
        raise RuntimeError("Matrix fork action budget is invalid.")
    return snapshot


def _view(game: GhostRevolutionRun, town: str) -> dict:
    state = game.towns[town]
    return {
        "location": game.location, "actions": game.actions,
        "gold": game.gold, "food": game.food,
        "weapons": game.weapon_stock_total(), "heat": game.heat,
        "royal_alert": game.royal_alert, "town_fear": state["fear"],
        "town_trust": game.town_trust(town),
        "active_guards": game.guard_count(town),
        "knight_town": game.knight_town,
        "alive": game.alive, "captured": game.captured,
    }


def _outcome(before: dict, game: GhostRevolutionRun, town: str) -> dict:
    after = _view(game, town)
    return {
        "after": after,
        "actions_spent": before["actions"] - after["actions"],
        "actions_remaining": after["actions"],
        "gold_delta": after["gold"] - before["gold"],
        "food_delta": after["food"] - before["food"],
        "weapon_delta": after["weapons"] - before["weapons"],
        "heat_delta": after["heat"] - before["heat"],
        "fear_delta": after["town_fear"] - before["town_fear"],
        "royal_alert_delta": after["royal_alert"] - before["royal_alert"],
        "trust_delta": after["town_trust"] - before["town_trust"],
        "captured": after["captured"], "alive": after["alive"],
    }


def _act(game: GhostRevolutionRun, action: str) -> None:
    before = game.actions
    if action == "seize_royal_supplies":
        game.seize_royal_supplies()
        required = "Royal cache seized:"
    elif action == "investigate_guard":
        game.question_guard()
        required = "Guard read"
    elif action == "secure_work":
        if game.earn_honest_gold() is None:
            raise RuntimeError("Expected town work action to resolve.")
        required = None
    else:
        raise ValueError(f"Unsupported matrix action: {action}")
    if required and required not in game.last_action_note:
        raise RuntimeError(f"Expected action evidence text: {required}")
    if game.actions != before - 1:
        raise RuntimeError("Matrix action did not spend exactly one action.")


def naive_report_truth_policy(reports: list[dict]) -> tuple[str, str]:
    """Act on the highest-confidence literal report, without provenance analysis."""
    if not reports:
        raise ValueError("naive policy requires at least one report")
    report = sorted(reports, key=lambda item: (-item["confidence"], item["speaker"]))[0]
    return (("seize_royal_supplies", "secure_work") if report["claim"]["knight_status"] == "absent" else ("secure_work", "investigate_guard"))


def _quality_requires_check(quality: dict, uncertainty: float | None = None) -> bool:
    return (
        quality["direct_observation"] < .50
        or quality["deception_likely"] >= .50
        or quality["rumor_repetition_likely"] >= .50
        or quality["contradictory_sources"] >= .25
        or (uncertainty is not None and uncertainty >= .45)
    )


def provenance_initial_policy(belief: dict) -> str:
    """Investigate low-quality, contradictory, or uncertain claims before risk."""
    p = belief["dimensions"]["royal_presence"]
    if _quality_requires_check(belief["report_quality"], p["uncertainty"]):
        return "investigate_guard"
    return "seize_royal_supplies" if p["dominant_candidate"] == "knight_absent" and p["confidence"] >= .65 else "secure_work"


def provenance_revised_policy(belief: dict) -> str:
    """Risk only after evidence leaves both quality and absence strong enough."""
    p = belief["dimensions"]["royal_presence"]
    if _quality_requires_check(belief["report_quality"]):
        return "secure_work"
    return "seize_royal_supplies" if p["dominant_candidate"] == "knight_absent" and p["confidence"] >= .65 else "secure_work"


def oracle_budget_matched_policy(objective: dict) -> tuple[str, str]:
    """Audit-only upper bound that intentionally sees hidden truth."""
    return (("secure_work", "investigate_guard") if objective["knight_present"] else ("seize_royal_supplies", "secure_work"))


def _belief_summary(belief: dict) -> dict:
    p = belief["dimensions"]["royal_presence"]
    return {
        "dominant_candidate": p["dominant_candidate"],
        "confidence": p["confidence"], "uncertainty": p["uncertainty"],
        "previous_belief_id": belief["previous_belief_id"],
        "report_quality": deepcopy(belief["report_quality"]),
    }


def _epistemic_case(scenario: dict, town: str, reports: list[dict]) -> tuple[GhostAPI, dict]:
    ghost = GhostAPI()
    subject = f"royal_presence:{town}"
    fact = ghost.record_fact(
        fact_id=f"matrix_knight_presence_{scenario['id']}_{town}",
        source="benchmark_director", subject=subject,
        predicate="knight_presence", object="present" if scenario["knight_present"] else "absent",
        attributes={"town": town, "purpose": "hidden_benchmark_truth"},
    )
    records = [ghost.report(
        speaker=report["speaker"], audience="player", claim=deepcopy(report["claim"]),
        confidence=report["confidence"], provenance={"channel": "matrix_report", "scenario_id": scenario["id"], "town": town},
    ) for report in reports]
    belief = ghost.evaluate_beliefs(
        holder="player", subject=subject,
        candidates={"royal_presence": deepcopy(scenario["candidates"])},
        report_quality=deepcopy(scenario["quality"]),
        evidence_ids=[record["id"] for record in records],
        provenance={"basis": "scenario report set", "scenario_id": scenario["id"], "town": town},
    )
    return ghost, {"subject": subject, "fact_id": fact["fact_id"], "fact_record_id": fact["id"], "report_ids": [r["id"] for r in records], "belief": belief}


def _revise_from_guard_read(ghost: GhostAPI, subject: str, belief: dict, note: str, scenario_id: str, town: str) -> dict:
    """Use only an explicit in-game knight-patrol cue as evidence of presence."""
    patrol = "knight's patrols" in note
    observation = ghost.observe(
        observer="player", kind="guard_read",
        visible_features=["knight_patrol_cue"] if patrol else ["guard_read_without_knight_patrol_cue"],
        reliability=.85 if patrol else .25, subject=subject,
        provenance={"action": "question_guard", "town": town, "scenario_id": scenario_id, "game_note": note},
    )
    if patrol:
        evidence = ghost.add_evidence(
            evidence_type="guard_patrol_cue", source="player_guard_read", subject=subject, available_to="player",
            supports={"royal_presence": {"knight_present": .90}, "report_quality": {"direct_observation": .75}},
            contradicts={"royal_presence": {"knight_absent": .70}, "report_quality": {"deception_likely": .45, "rumor_repetition_likely": .40}},
            provenance={"action": "question_guard", "town": town, "game_note": note},
        )
    else:
        evidence = ghost.add_evidence(
            evidence_type="guard_read_inconclusive", source="player_guard_read", subject=subject, available_to="player",
            supports={"royal_presence": {"unknown": .15}},
            provenance={"action": "question_guard", "town": town, "game_note": note},
        )
    revised = ghost.evaluate_beliefs(
        holder="player", subject=subject, previous_belief_id=belief["id"],
        evidence_ids=[observation["id"], evidence["id"]],
        provenance={"basis": "guard investigation", "scenario_id": scenario_id, "town": town},
    )
    return {"patrol_cue": patrol, "observation_id": observation["id"], "evidence_id": evidence["id"], "belief": revised}


def _run_actions(snapshot: dict, town: str, actions: tuple[str, str]) -> dict:
    game = GhostRevolutionRun.from_snapshot(deepcopy(snapshot))
    exact, before = game.snapshot() == snapshot, _view(game, town)
    if not exact:
        raise RuntimeError("Matrix branch did not restore exact snapshot state.")
    for action in actions:
        _act(game, action)
    outcome = _outcome(before, game, town)
    if outcome["actions_spent"] != ACTION_BUDGET or outcome["actions_remaining"] != 0:
        raise RuntimeError("Matrix branch did not exhaust the fixed action budget.")
    return {"fork_snapshot_sha256": _digest(snapshot), "restored_exactly": exact, "initial_state": before, "decision_path": list(actions), "outcome": outcome}


def _naive(snapshot: dict, town: str, reports: list[dict]) -> dict:
    actions = naive_report_truth_policy(reports)
    branch = _run_actions(snapshot, town, actions)
    branch.update(label="Naive reports = truth", first_action=actions[0])
    return branch


def _ghost(snapshot: dict, scenario: dict, town: str, reports: list[dict]) -> dict:
    ghost, audit = _epistemic_case(scenario, town, reports)
    initial, first = audit["belief"], provenance_initial_policy(audit["belief"])
    game = GhostRevolutionRun.from_snapshot(deepcopy(snapshot))
    exact, before = game.snapshot() == snapshot, _view(game, town)
    if not exact:
        raise RuntimeError("Matrix branch did not restore exact snapshot state.")
    revision = None
    if first == "investigate_guard":
        _act(game, first)
        revision = _revise_from_guard_read(ghost, audit["subject"], initial, game.last_action_note, scenario["id"], town)
        final, second = revision["belief"], provenance_revised_policy(revision["belief"])
    elif first == "seize_royal_supplies":
        _act(game, first)
        final, second = initial, "secure_work"
    else:
        _act(game, first)
        final, second = initial, "investigate_guard"
    _act(game, second)
    outcome = _outcome(before, game, town)
    if outcome["actions_spent"] != ACTION_BUDGET or outcome["actions_remaining"] != 0:
        raise RuntimeError("Matrix branch did not exhaust the fixed action budget.")
    epistemic_snapshot = ghost.snapshot()
    restored = GhostAPI.from_snapshot(epistemic_snapshot)
    return {
        "label": "Ghost provenance policy", "fork_snapshot_sha256": _digest(snapshot),
        "restored_exactly": exact, "initial_state": before, "first_action": first,
        "decision_path": [first, second],
        "beliefs": {"initial": _belief_summary(initial), "final": _belief_summary(final)},
        "revision": None if revision is None else {k: revision[k] for k in ("patrol_cue", "observation_id", "evidence_id")},
        "audit": {
            "fact_id": audit["fact_id"], "fact_record_id": audit["fact_record_id"], "report_ids": audit["report_ids"],
            "snapshot_round_trip_matches": restored.snapshot() == epistemic_snapshot,
            "restored_belief_matches": restored.get_belief("player", audit["subject"]) == final,
        },
        "outcome": outcome,
    }


def _oracle(snapshot: dict, town: str, objective: dict) -> dict:
    actions = oracle_budget_matched_policy(objective)
    branch = _run_actions(snapshot, town, actions)
    branch.update(label="Oracle diagnostic", first_action=actions[0])
    return branch


def _trial(scenario: dict, town: str, seed: int) -> dict:
    reports, objective = _reports(scenario, town), _objective(scenario, town)
    snapshot = _fork(seed, town, objective["knight_present"])
    naive, ghost, oracle = _naive(snapshot, town, deepcopy(reports)), _ghost(snapshot, scenario, town, deepcopy(reports)), _oracle(snapshot, town, deepcopy(objective))
    branches, fork_hash = [naive, ghost, oracle], _digest(snapshot)
    return {
        "scenario_id": scenario["id"], "scenario_label": scenario["label"], "expected_mode": scenario["mode"],
        "town": town, "seed": seed, "objective_truth_for_audit_only": objective,
        "shared_reports": reports, "shared_reports_sha256": _digest(reports), "fork_snapshot_sha256": fork_hash,
        "naive": naive, "ghost_provenance": ghost, "oracle_diagnostic": oracle,
        "checks": {
            "exact_snapshot_fork": all(b["restored_exactly"] and b["fork_snapshot_sha256"] == fork_hash for b in branches),
            "identical_initial_state": naive["initial_state"] == ghost["initial_state"] == oracle["initial_state"],
            "equal_action_budget": all(b["outcome"]["actions_spent"] == ACTION_BUDGET and b["outcome"]["actions_remaining"] == 0 for b in branches),
            "epistemic_snapshot_audit": ghost["audit"]["snapshot_round_trip_matches"] and ghost["audit"]["restored_belief_matches"],
        },
    }


def _action_counts(trials: list[dict], key: str) -> dict:
    counts = {}
    for trial in trials:
        action = trial[key]["first_action"]
        counts[action] = counts.get(action, 0) + 1
    return dict(sorted(counts.items()))


def _totals(trials: list[dict], key: str) -> dict:
    fields = ("gold_delta", "food_delta", "weapon_delta", "heat_delta", "fear_delta", "royal_alert_delta", "trust_delta")
    return {field: sum(t[key]["outcome"][field] for t in trials) for field in fields}


def _summary(scenario: dict, trials: list[dict]) -> dict:
    present = scenario["knight_present"]
    unsafe = lambda key: sum(t[key]["first_action"] == "seize_royal_supplies" and t["objective_truth_for_audit_only"]["knight_present"] for t in trials)
    return {
        "label": scenario["label"], "expected_mode": scenario["mode"], "objective_knight_present": present, "trials": len(trials),
        "naive_first_actions": _action_counts(trials, "naive"), "ghost_first_actions": _action_counts(trials, "ghost_provenance"),
        "naive_unsafe_seizures": unsafe("naive"), "ghost_unsafe_seizures": unsafe("ghost_provenance"),
        "ghost_patrol_revisions": sum(t["ghost_provenance"]["revision"] is not None and t["ghost_provenance"]["revision"]["patrol_cue"] for t in trials),
    }


def _aggregate(trials: list[dict]) -> dict:
    choose = lambda scenario_id: [t for t in trials if t["scenario_id"] == scenario_id]
    present = [t for t in trials if t["objective_truth_for_audit_only"]["knight_present"]]
    high_abs, high_pres = choose("truthful_high_provenance_absence"), choose("truthful_high_provenance_presence")
    low = [t for t in trials if t["scenario_id"] in LOW_PROVENANCE_IDS]
    low_true = choose("truthful_low_provenance_absence")
    return {
        "trials": len(trials), "present_truth_trials": len(present),
        "naive_unsafe_seizures": sum(t["naive"]["first_action"] == "seize_royal_supplies" for t in present),
        "ghost_unsafe_seizures": sum(t["ghost_provenance"]["first_action"] == "seize_royal_supplies" for t in present),
        "ghost_explicit_patrol_revisions": sum(t["ghost_provenance"]["revision"] is not None and t["ghost_provenance"]["revision"]["patrol_cue"] for t in present),
        "high_provenance_absence_trials": len(high_abs),
        "ghost_acts_on_high_provenance_absence": sum(t["ghost_provenance"]["first_action"] == "seize_royal_supplies" for t in high_abs),
        "high_provenance_presence_trials": len(high_pres),
        "ghost_avoids_on_high_provenance_presence": sum(t["ghost_provenance"]["first_action"] != "seize_royal_supplies" for t in high_pres),
        "low_provenance_trials": len(low),
        "ghost_investigates_low_provenance": sum(t["ghost_provenance"]["first_action"] == "investigate_guard" for t in low),
        "truthful_low_provenance_deferrals": sum(t["ghost_provenance"]["first_action"] == "investigate_guard" and "seize_royal_supplies" not in t["ghost_provenance"]["decision_path"] for t in low_true),
        "naive_raw_totals": _totals(trials, "naive"), "ghost_raw_totals": _totals(trials, "ghost_provenance"),
    }


def run_scenario_matrix_benchmark(seeds: tuple[int, ...] = SEEDS, towns: tuple[str, ...] = MATRIX_TOWNS) -> dict:
    """Run the fixed matrix over guarded towns and deterministic seeds."""
    seeds, towns = tuple(seeds), tuple(towns)
    if not seeds or not all(isinstance(seed, int) and not isinstance(seed, bool) for seed in seeds):
        raise ValueError("seeds must be a non-empty tuple of integers")
    if not towns or any(town not in MATRIX_TOWNS for town in towns):
        raise ValueError("towns must be guarded matrix towns")
    trials = [_trial(scenario, town, seed) for scenario in SCENARIOS for town in towns for seed in seeds]
    summaries = {s["id"]: _summary(s, [t for t in trials if t["scenario_id"] == s["id"]]) for s in SCENARIOS}
    aggregate = _aggregate(trials)
    checks = {
        "full_scenario_town_seed_matrix": len(trials) == len(SCENARIOS) * len(towns) * len(seeds),
        "every_trial_exactly_forked": all(t["checks"]["exact_snapshot_fork"] for t in trials),
        "every_trial_same_branch_start": all(t["checks"]["identical_initial_state"] for t in trials),
        "every_trial_equal_two_action_budget": all(t["checks"]["equal_action_budget"] for t in trials),
        "every_trial_epistemic_snapshot_audited": all(t["checks"]["epistemic_snapshot_audit"] for t in trials),
        "ghost_reduces_unsafe_seizures": aggregate["ghost_unsafe_seizures"] < aggregate["naive_unsafe_seizures"],
        "ghost_acts_on_high_provenance_absence": aggregate["ghost_acts_on_high_provenance_absence"] == aggregate["high_provenance_absence_trials"],
        "ghost_avoids_on_high_provenance_presence": aggregate["ghost_avoids_on_high_provenance_presence"] == aggregate["high_provenance_presence_trials"],
        "ghost_investigates_low_provenance_inputs": aggregate["ghost_investigates_low_provenance"] == aggregate["low_provenance_trials"],
        "explicit_patrol_evidence_revises_present_cases": aggregate["ghost_explicit_patrol_revisions"] == aggregate["naive_unsafe_seizures"],
    }
    return {
        "benchmark": "ghost_revolution_epistemic_scenario_matrix_v2", "action_budget": ACTION_BUDGET,
        "seeds": list(seeds), "towns": list(towns), "scenario_ids": [s["id"] for s in SCENARIOS],
        "scope": "Each trial uses an exact snapshot fork and equal action budget. Raw resource, heat, fear, alert, trust, and survival deltas remain separate.",
        "scenario_summaries": summaries, "aggregate": aggregate, "trials": trials, "checks": checks,
    }


def _format(counts: dict) -> str:
    return ", ".join(f"{name}={count}" for name, count in counts.items())


def print_scenario_matrix_benchmark(result: dict) -> None:
    """Print compact matrix evidence without a composite score."""
    a = result["aggregate"]
    print("=== GHOST REVOLUTION SCENARIO MATRIX v2 ===\n")
    print("Scenarios:", len(result["scenario_ids"]))
    print("Towns:", ", ".join(result["towns"]))
    print("Seeds:", ", ".join(map(str, result["seeds"])))
    print("Trials:", a["trials"])
    print("Action budget per branch:", result["action_budget"], "\n")
    print("SCENARIO SUMMARY")
    for scenario_id in result["scenario_ids"]:
        s = result["scenario_summaries"][scenario_id]
        print("-", s["label"])
        print("  Truth:", "knight present" if s["objective_knight_present"] else "knight absent", "| expected Ghost mode:", s["expected_mode"])
        print("  Naive first actions:", _format(s["naive_first_actions"]))
        print("  Ghost first actions:", _format(s["ghost_first_actions"]))
        print(f"  Unsafe seizures naive={s['naive_unsafe_seizures']}, Ghost={s['ghost_unsafe_seizures']} | patrol revisions={s['ghost_patrol_revisions']}")
    print("\nAGGREGATE DECISION METRICS")
    print(f"  Unsafe first-action seizures when knight present: naive {a['naive_unsafe_seizures']} / {a['present_truth_trials']}, Ghost {a['ghost_unsafe_seizures']} / {a['present_truth_trials']}")
    print(f"  High-provenance truthful absence acted on by Ghost: {a['ghost_acts_on_high_provenance_absence']} / {a['high_provenance_absence_trials']}")
    print(f"  High-provenance truthful presence avoided by Ghost: {a['ghost_avoids_on_high_provenance_presence']} / {a['high_provenance_presence_trials']}")
    print(f"  Low-provenance / ambiguous / contradictory inputs investigated by Ghost: {a['ghost_investigates_low_provenance']} / {a['low_provenance_trials']}")
    print("  Truthful low-provenance opportunity deferrals:", a["truthful_low_provenance_deferrals"])
    print("\nRAW TOTALS ACROSS ALL TRIALS")
    for label, totals in (("Naive", a["naive_raw_totals"]), ("Ghost", a["ghost_raw_totals"])):
        print(f"  {label}: gold {totals['gold_delta']:+.0f}, food {totals['food_delta']:+.0f}, weapons {totals['weapon_delta']:+.0f}, heat {totals['heat_delta']:+.0f}, fear {totals['fear_delta']:+.0f}, alert {totals['royal_alert_delta']:+.0f}, trust {totals['trust_delta']:+.3f}")
    print("\n=== MATRIX CHECKS ===")
    for name, passed in result["checks"].items():
        print("[PASS]" if passed else "[FAIL]", name)


def main() -> None:
    print_scenario_matrix_benchmark(run_scenario_matrix_benchmark())


if __name__ == "__main__":
    main()
