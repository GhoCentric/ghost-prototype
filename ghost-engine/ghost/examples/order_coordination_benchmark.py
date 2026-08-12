"""
Deterministic fault-injection benchmark for Ghost order coordination.

This harness does not call a live language model and does not claim a raw
LLM accuracy rate. It feeds the same scripted coordination faults through
(1) a transcript-only state reconstruction and (2) the Ghost-backed
OrderCoordinator, then scores whether each workflow contains the fault.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from ghost.examples.order_coordination import (
    OrderCoordinator,
    OrderSubmissionBlocked,
)


ORDER_COORDINATION_BENCHMARK_SCHEMA_VERSION = "1.0"
BENCHMARK_KIND = "deterministic_coordination_fault_injection"

FAMILY_CLEAN = "clean_control"
FAMILY_AMBIGUOUS = "ambiguous_target_guess"
FAMILY_CORRECTION = "forgotten_correction"
FAMILY_STALE = "stale_confirmation"
FAMILY_DUPLICATE = "duplicate_submission"
FAMILY_QUANTITY = "quantity_reconstruction_error"
FAMILY_CONTRADICTION = "contradictory_agent_merge"

FAMILY_ORDER = (
    FAMILY_CLEAN,
    FAMILY_AMBIGUOUS,
    FAMILY_CORRECTION,
    FAMILY_STALE,
    FAMILY_DUPLICATE,
    FAMILY_QUANTITY,
    FAMILY_CONTRADICTION,
)

METRIC_KEYS = (
    "correct_final_orders",
    "wrong_modifier_targets",
    "forgotten_corrections",
    "unresolved_ambiguity_submitted",
    "stale_confirmation_accepted",
    "duplicate_submissions",
    "incorrect_quantities",
    "contradictory_final_states",
    "incorrect_final_orders",
    "unsafe_attempts_blocked",
)

PRODUCT_PAIRS = (
    ("burger", "chicken_sandwich"),
    ("taco", "burrito"),
    ("coffee", "latte"),
    ("pizza_slice", "calzone"),
    ("salad", "wrap"),
    ("bagel", "croissant"),
    ("hot_dog", "bratwurst"),
    ("pancakes", "waffles"),
    ("sub", "panini"),
    ("rice_bowl", "noodle_bowl"),
    ("smoothie", "milkshake"),
    ("fish_sandwich", "shrimp_roll"),
    ("baked_potato", "loaded_fries"),
    ("quesadilla", "nachos"),
    ("muffin", "cinnamon_roll"),
)

MODIFIERS = (
    "add_bacon",
    "no_onion",
    "extra_cheese",
    "no_pickle",
    "add_avocado",
    "light_sauce",
    "extra_hot",
    "no_tomato",
    "add_mushroom",
    "gluten_free",
    "oat_milk",
    "no_mayo",
    "extra_crispy",
    "add_jalapeno",
    "sauce_on_side",
)


@dataclass(frozen=True)
class BenchmarkScenario:
    scenario_id: str
    family: str
    first_product: str
    second_product: str
    modifier: str
    first_quantity: int
    expected_modifier_target: int

    def packet(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "family": self.family,
            "first_product": self.first_product,
            "second_product": self.second_product,
            "modifier": self.modifier,
            "first_quantity": self.first_quantity,
            "expected_modifier_target": self.expected_modifier_target,
        }


def _json_copy(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def build_scenarios() -> list[BenchmarkScenario]:
    """Return the fixed 100-case benchmark matrix."""
    scenarios: list[BenchmarkScenario] = []

    for index in range(10):
        first, second = PRODUCT_PAIRS[index]
        scenarios.append(
            BenchmarkScenario(
                scenario_id=f"clean_{index + 1:03d}",
                family=FAMILY_CLEAN,
                first_product=first,
                second_product=second,
                modifier=MODIFIERS[index],
                first_quantity=1,
                expected_modifier_target=2,
            )
        )

    fault_families = FAMILY_ORDER[1:]

    for family_index, family in enumerate(fault_families):
        for variant in range(15):
            product_index = (
                variant + (family_index * 3)
            ) % len(PRODUCT_PAIRS)
            modifier_index = (
                variant + (family_index * 5)
            ) % len(MODIFIERS)
            first, second = PRODUCT_PAIRS[product_index]
            expected_target = (
                1
                if family in {FAMILY_CORRECTION, FAMILY_STALE}
                else 2
            )
            first_quantity = (
                2 + (variant % 3)
                if family == FAMILY_QUANTITY
                else 1
            )
            scenarios.append(
                BenchmarkScenario(
                    scenario_id=(
                        f"{family}_{variant + 1:03d}"
                    ),
                    family=family,
                    first_product=first,
                    second_product=second,
                    modifier=MODIFIERS[modifier_index],
                    first_quantity=first_quantity,
                    expected_modifier_target=expected_target,
                )
            )

    if len(scenarios) != 100:
        raise RuntimeError("benchmark matrix must contain 100 scenarios")

    if len({item.scenario_id for item in scenarios}) != 100:
        raise RuntimeError("benchmark scenario ids must be unique")

    return scenarios


def _expected_order(scenario: BenchmarkScenario) -> dict[str, Any]:
    items = [
        {
            "item_id": "item_001",
            "product": scenario.first_product,
            "quantity": scenario.first_quantity,
            "modifiers": [],
        },
        {
            "item_id": "item_002",
            "product": scenario.second_product,
            "quantity": 1,
            "modifiers": [],
        },
    ]
    items[scenario.expected_modifier_target - 1][
        "modifiers"
    ] = [scenario.modifier]

    return {"items": items}


def _normalize_order(order: dict[str, Any]) -> dict[str, Any]:
    normalized = []

    for item in order["items"]:
        normalized.append(
            {
                "item_id": item["item_id"],
                "product": item["product"],
                "quantity": item["quantity"],
                "modifiers": sorted(item["modifiers"]),
            }
        )

    normalized.sort(key=lambda item: item["item_id"])
    return {"items": normalized}


class _TranscriptOnlyRuntime:
    """Minimal latest-summary-wins transcript reconstruction."""

    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []
        self.confirmed = False
        self.submission_count = 0
        self.unresolved = False
        self.unresolved_submitted = False
        self.stale_confirmation_accepted = False
        self.blocked_attempts = 0

    def add_item(self, product: str, quantity: int = 1) -> str:
        item_id = f"item_{len(self.items) + 1:03d}"
        self.items.append(
            {
                "item_id": item_id,
                "product": product,
                "quantity": quantity,
                "modifiers": [],
            }
        )
        self.confirmed = False
        return item_id

    def _item(self, item_id: str) -> dict[str, Any]:
        for item in self.items:
            if item["item_id"] == item_id:
                return item
        raise ValueError(f"unknown item: {item_id}")

    def set_modifier_target(
        self,
        modifier: str,
        target_item_id: str,
    ) -> None:
        for item in self.items:
            if modifier in item["modifiers"]:
                item["modifiers"].remove(modifier)
        target = self._item(target_item_id)
        target["modifiers"].append(modifier)
        target["modifiers"].sort()
        self.confirmed = False

    def merge_modifier_target(
        self,
        modifier: str,
        target_item_id: str,
    ) -> None:
        target = self._item(target_item_id)
        if modifier not in target["modifiers"]:
            target["modifiers"].append(modifier)
            target["modifiers"].sort()
        self.confirmed = False

    def replace_quantity(self, item_id: str, quantity: int) -> None:
        self._item(item_id)["quantity"] = quantity
        self.confirmed = False

    def confirm(self) -> None:
        self.confirmed = True

    def submit(self, *, after_correction: bool = False) -> None:
        if self.unresolved:
            self.unresolved_submitted = True
        if after_correction and self.confirmed:
            self.stale_confirmation_accepted = True
        self.submission_count += 1

    def order(self) -> dict[str, Any]:
        return _normalize_order({"items": deepcopy(self.items)})


def _base_transcript_runtime(
    scenario: BenchmarkScenario,
) -> tuple[_TranscriptOnlyRuntime, str, str]:
    runtime = _TranscriptOnlyRuntime()
    first_id = runtime.add_item(
        scenario.first_product,
        scenario.first_quantity,
    )
    second_id = runtime.add_item(scenario.second_product, 1)
    return runtime, first_id, second_id


def _run_transcript_only(
    scenario: BenchmarkScenario,
) -> dict[str, Any]:
    runtime, first_id, second_id = _base_transcript_runtime(
        scenario
    )
    correction_received = False

    if scenario.family == FAMILY_CLEAN:
        runtime.set_modifier_target(scenario.modifier, second_id)
        runtime.confirm()
        runtime.submit()

    elif scenario.family == FAMILY_AMBIGUOUS:
        runtime.unresolved = True
        runtime.set_modifier_target(scenario.modifier, first_id)
        runtime.confirm()
        runtime.submit()

    elif scenario.family == FAMILY_CORRECTION:
        runtime.set_modifier_target(scenario.modifier, second_id)
        correction_received = True
        runtime.set_modifier_target(scenario.modifier, first_id)
        # A later verifier reconstructs the stale pre-correction summary.
        runtime.set_modifier_target(scenario.modifier, second_id)
        runtime.confirm()
        runtime.submit()

    elif scenario.family == FAMILY_STALE:
        runtime.set_modifier_target(scenario.modifier, second_id)
        runtime.confirm()
        # The customer correction changes the order, but this baseline
        # does not bind confirmation to a revision.
        runtime.set_modifier_target(scenario.modifier, first_id)
        runtime.confirmed = True
        runtime.submit(after_correction=True)

    elif scenario.family == FAMILY_DUPLICATE:
        runtime.set_modifier_target(scenario.modifier, second_id)
        runtime.confirm()
        runtime.submit()
        runtime.submit()

    elif scenario.family == FAMILY_QUANTITY:
        runtime.set_modifier_target(scenario.modifier, second_id)
        # A handoff summary collapses the original quantity to one.
        runtime.replace_quantity(first_id, 1)
        runtime.confirm()
        runtime.submit()

    elif scenario.family == FAMILY_CONTRADICTION:
        runtime.set_modifier_target(scenario.modifier, second_id)
        # Two agent summaries are merged additively instead of resolved.
        runtime.merge_modifier_target(scenario.modifier, first_id)
        runtime.confirm()
        runtime.submit()

    else:
        raise ValueError(f"unsupported scenario family: {scenario.family}")

    return {
        "mode": "transcript_only",
        "final_order": runtime.order(),
        "submission_count": runtime.submission_count,
        "unresolved_ambiguity_submitted": (
            runtime.unresolved_submitted
        ),
        "stale_confirmation_accepted": (
            runtime.stale_confirmation_accepted
        ),
        "blocked_attempts": runtime.blocked_attempts,
        "correction_received": correction_received,
    }


def _base_ghost_runtime(
    scenario: BenchmarkScenario,
) -> tuple[OrderCoordinator, str, str]:
    runtime = OrderCoordinator()
    first = runtime.add_item(
        f"{scenario.scenario_id}:add_1",
        scenario.first_product,
        scenario.first_quantity,
    )["result"]["item"]
    second = runtime.add_item(
        f"{scenario.scenario_id}:add_2",
        scenario.second_product,
        1,
    )["result"]["item"]
    return runtime, first["item_id"], second["item_id"]


def _ghost_submit(
    runtime: OrderCoordinator,
    operation_id: str,
) -> bool:
    runtime.submit(operation_id)
    return True


def _run_ghost_backed(
    scenario: BenchmarkScenario,
) -> dict[str, Any]:
    runtime, first_id, second_id = _base_ghost_runtime(scenario)
    prefix = scenario.scenario_id
    blocked_attempts = 0
    accepted_submissions = 0
    unresolved_accepted = False
    stale_accepted = False
    correction_received = False

    if scenario.family == FAMILY_CLEAN:
        runtime.propose_modifier(
            f"{prefix}:modifier",
            scenario.modifier,
            [second_id],
            "Apply the modifier to the second item.",
        )

    elif scenario.family == FAMILY_AMBIGUOUS:
        opened = runtime.propose_modifier(
            f"{prefix}:ambiguous",
            scenario.modifier,
            [first_id, second_id],
            "Put it on the other one.",
        )["result"]
        try:
            _ghost_submit(runtime, f"{prefix}:unsafe_submit")
            unresolved_accepted = True
        except OrderSubmissionBlocked:
            blocked_attempts += 1
        runtime.resolve_ambiguity(
            f"{prefix}:clarify",
            opened["ambiguity"]["ambiguity_id"],
            second_id,
            "The second item.",
        )

    elif scenario.family == FAMILY_CORRECTION:
        runtime.propose_modifier(
            f"{prefix}:modifier",
            scenario.modifier,
            [second_id],
            "Apply it to the second item.",
        )
        correction_received = True
        runtime.correct_modifier(
            f"{prefix}:correction",
            scenario.modifier,
            second_id,
            first_id,
            "Actually, move it to the first item.",
        )
        # A stale verifier summary is non-authoritative and cannot
        # overwrite the coordinator's corrected state.

    elif scenario.family == FAMILY_STALE:
        runtime.propose_modifier(
            f"{prefix}:modifier",
            scenario.modifier,
            [second_id],
            "Apply it to the second item.",
        )
        runtime.confirm_order(
            f"{prefix}:confirm_before",
            "Yes, that is correct.",
        )
        runtime.correct_modifier(
            f"{prefix}:correction",
            scenario.modifier,
            second_id,
            first_id,
            "Move it to the first item.",
        )
        try:
            _ghost_submit(runtime, f"{prefix}:stale_submit")
            stale_accepted = True
        except OrderSubmissionBlocked:
            blocked_attempts += 1

    elif scenario.family == FAMILY_DUPLICATE:
        runtime.propose_modifier(
            f"{prefix}:modifier",
            scenario.modifier,
            [second_id],
            "Apply it to the second item.",
        )

    elif scenario.family == FAMILY_QUANTITY:
        runtime.propose_modifier(
            f"{prefix}:modifier",
            scenario.modifier,
            [second_id],
            "Apply it to the second item.",
        )
        # The erroneous quantity summary is only a proposal. It does not
        # mutate the authoritative quantity established by add_item.

    elif scenario.family == FAMILY_CONTRADICTION:
        runtime.propose_modifier(
            f"{prefix}:modifier",
            scenario.modifier,
            [second_id],
            "Apply it to the second item.",
        )
        opened = runtime.propose_modifier(
            f"{prefix}:conflict",
            scenario.modifier,
            [first_id, second_id],
            "One agent says first; another says second.",
        )["result"]
        try:
            _ghost_submit(runtime, f"{prefix}:conflict_submit")
            unresolved_accepted = True
        except OrderSubmissionBlocked:
            blocked_attempts += 1
        runtime.resolve_ambiguity(
            f"{prefix}:resolve_conflict",
            opened["ambiguity"]["ambiguity_id"],
            second_id,
            "Keep it on the second item.",
        )

    else:
        raise ValueError(f"unsupported scenario family: {scenario.family}")

    if runtime.status()["confirmed_revision"] != runtime.status()[
        "revision"
    ]:
        runtime.confirm_order(
            f"{prefix}:final_confirm",
            "The current revision is correct.",
        )

    submitted = runtime.submit(f"{prefix}:submit")
    accepted_submissions += 1

    if scenario.family == FAMILY_DUPLICATE:
        repeated = runtime.submit(f"{prefix}:submit")
        if repeated != submitted:
            raise RuntimeError("idempotent replay changed submit result")
        try:
            runtime.submit(f"{prefix}:duplicate_submit")
            accepted_submissions += 1
        except RuntimeError:
            blocked_attempts += 1

    return {
        "mode": "ghost_backed",
        "final_order": _normalize_order(
            submitted["result"]["order"]
        ),
        "submission_count": accepted_submissions,
        "unresolved_ambiguity_submitted": unresolved_accepted,
        "stale_confirmation_accepted": stale_accepted,
        "blocked_attempts": blocked_attempts,
        "correction_received": correction_received,
        "epistemic_record_count": len(
            runtime.snapshot()["ghost"]["epistemic"]["records"]
        ),
        "ledger_record_count": len(runtime.snapshot()["ledger"]),
    }


def _modifier_targets(
    order: dict[str, Any],
    modifier: str,
) -> list[str]:
    return [
        item["item_id"]
        for item in order["items"]
        if modifier in item["modifiers"]
    ]


def _score_run(
    scenario: BenchmarkScenario,
    run: dict[str, Any],
) -> dict[str, Any]:
    expected = _expected_order(scenario)
    actual = _normalize_order(run["final_order"])
    expected_targets = _modifier_targets(
        expected,
        scenario.modifier,
    )
    actual_targets = _modifier_targets(
        actual,
        scenario.modifier,
    )
    expected_quantities = {
        item["item_id"]: item["quantity"]
        for item in expected["items"]
    }
    actual_quantities = {
        item["item_id"]: item["quantity"]
        for item in actual["items"]
    }
    incorrect_final = actual != expected

    metrics = {
        "wrong_modifier_target": actual_targets != expected_targets,
        "forgotten_correction": (
            scenario.family == FAMILY_CORRECTION
            and run["correction_received"]
            and actual_targets != expected_targets
        ),
        "unresolved_ambiguity_submitted": bool(
            run["unresolved_ambiguity_submitted"]
        ),
        "stale_confirmation_accepted": bool(
            run["stale_confirmation_accepted"]
        ),
        "duplicate_submission": run["submission_count"] > 1,
        "incorrect_quantity": actual_quantities != expected_quantities,
        "contradictory_final_state": (
            len(actual_targets) > len(expected_targets)
        ),
        "incorrect_final_order": incorrect_final,
        "correct_final_order": not incorrect_final,
        "unsafe_attempts_blocked": run["blocked_attempts"],
    }

    packet = {
        "scenario": scenario.packet(),
        "mode": run["mode"],
        "expected_order": expected,
        "final_order": actual,
        "submission_count": run["submission_count"],
        "metrics": metrics,
    }

    for optional in (
        "epistemic_record_count",
        "ledger_record_count",
    ):
        if optional in run:
            packet[optional] = run[optional]

    return _json_copy(packet)


def _aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    metrics = {
        "correct_final_orders": sum(
            1
            for result in results
            if result["metrics"]["correct_final_order"]
        ),
        "wrong_modifier_targets": sum(
            1
            for result in results
            if result["metrics"]["wrong_modifier_target"]
        ),
        "forgotten_corrections": sum(
            1
            for result in results
            if result["metrics"]["forgotten_correction"]
        ),
        "unresolved_ambiguity_submitted": sum(
            1
            for result in results
            if result["metrics"][
                "unresolved_ambiguity_submitted"
            ]
        ),
        "stale_confirmation_accepted": sum(
            1
            for result in results
            if result["metrics"][
                "stale_confirmation_accepted"
            ]
        ),
        "duplicate_submissions": sum(
            1
            for result in results
            if result["metrics"]["duplicate_submission"]
        ),
        "incorrect_quantities": sum(
            1
            for result in results
            if result["metrics"]["incorrect_quantity"]
        ),
        "contradictory_final_states": sum(
            1
            for result in results
            if result["metrics"][
                "contradictory_final_state"
            ]
        ),
        "incorrect_final_orders": sum(
            1
            for result in results
            if result["metrics"]["incorrect_final_order"]
        ),
        "unsafe_attempts_blocked": sum(
            result["metrics"]["unsafe_attempts_blocked"]
            for result in results
        ),
    }

    if set(metrics) != set(METRIC_KEYS):
        raise RuntimeError("aggregate metric schema drifted")

    return {
        "scenario_count": total,
        "metrics": metrics,
    }


def run_benchmark() -> dict[str, Any]:
    scenarios = build_scenarios()
    transcript_results = []
    ghost_results = []

    for scenario in scenarios:
        transcript_results.append(
            _score_run(
                scenario,
                _run_transcript_only(scenario),
            )
        )
        ghost_results.append(
            _score_run(
                scenario,
                _run_ghost_backed(scenario),
            )
        )

    family_counts = {
        family: sum(
            1 for scenario in scenarios if scenario.family == family
        )
        for family in FAMILY_ORDER
    }
    report = {
        "schema_version": (
            ORDER_COORDINATION_BENCHMARK_SCHEMA_VERSION
        ),
        "benchmark_kind": BENCHMARK_KIND,
        "claim_boundary": (
            "No live LLM calls are made. Results measure deterministic "
            "coordination-fault containment, not natural model accuracy."
        ),
        "scenario_count": len(scenarios),
        "clean_control_count": family_counts[FAMILY_CLEAN],
        "injected_fault_count": (
            len(scenarios) - family_counts[FAMILY_CLEAN]
        ),
        "family_counts": family_counts,
        "modes": {
            "transcript_only": _aggregate(transcript_results),
            "ghost_backed": _aggregate(ghost_results),
        },
        "results": {
            "transcript_only": transcript_results,
            "ghost_backed": ghost_results,
        },
    }
    return _json_copy(report)


def write_report(
    report: dict[str, Any],
    path: str | Path,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination


def print_summary(report: dict[str, Any]) -> None:
    print("=== GHOST ORDER COORDINATION BENCHMARK ===")
    print()
    print("Deterministic coordination fault injection.")
    print("No live LLM calls are made.")
    print("This measures containment, not raw model accuracy.")
    print()
    print("Scenarios:", report["scenario_count"])
    print("  clean controls:", report["clean_control_count"])
    print("  injected faults:", report["injected_fault_count"])

    labels = (
        ("correct_final_orders", "correct final orders"),
        ("wrong_modifier_targets", "wrong modifier targets"),
        ("forgotten_corrections", "forgotten corrections"),
        (
            "unresolved_ambiguity_submitted",
            "unresolved ambiguity submitted",
        ),
        (
            "stale_confirmation_accepted",
            "stale confirmation accepted",
        ),
        ("duplicate_submissions", "duplicate submissions"),
        ("incorrect_quantities", "incorrect quantities"),
        (
            "contradictory_final_states",
            "contradictory final states",
        ),
        ("incorrect_final_orders", "incorrect final orders"),
        ("unsafe_attempts_blocked", "unsafe attempts blocked"),
    )

    for mode, title in (
        ("transcript_only", "Transcript-only"),
        ("ghost_backed", "Ghost-backed"),
    ):
        metrics = report["modes"][mode]["metrics"]
        print()
        print(title + ":")
        for key, label in labels:
            print(f"  {label}: {metrics[key]}")


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(
        description=(
            "Run the deterministic Ghost order-coordination benchmark."
        )
    )
    parser.add_argument(
        "--json",
        default="order_coordination_benchmark_report.json",
        help="JSON report destination",
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="print the summary without writing a report",
    )
    args = parser.parse_args(argv)
    report = run_benchmark()
    print_summary(report)

    if not args.no_json:
        destination = write_report(report, args.json)
        print()
        print("JSON report:", destination)

    return report


if __name__ == "__main__":
    main()
