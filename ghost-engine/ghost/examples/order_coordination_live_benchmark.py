"""
Live paired-proposal benchmark for Ghost order coordination.

One language-model extraction packet is produced for each transcript.
That exact packet is then evaluated in two modes:

1. transcript_only trusts the model's reconstructed order and actions;
2. ghost_backed routes the same proposed events through deterministic
   authority, ambiguity, confirmation, and idempotency rules.

The benchmark starts after authoritative item intake. It measures
coordination and state-containment behavior, not speech recognition or
end-to-end restaurant deployment.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import time
from typing import Any, Callable, Iterable, Mapping

from ghost.examples.ghost_revolution.llm_bridge import (
    LLMBridgeConfig,
    OpenAIResponsesClient,
    measured_llm_cost,
    normalize_client_result,
)
from ghost.examples.order_coordination import (
    OrderCoordinator,
    OrderSubmissionBlocked,
)
from ghost.examples.order_coordination_benchmark import (
    BenchmarkScenario,
    FAMILY_AMBIGUOUS,
    FAMILY_CLEAN,
    FAMILY_CONTRADICTION,
    FAMILY_CORRECTION,
    FAMILY_DUPLICATE,
    FAMILY_ORDER,
    FAMILY_QUANTITY,
    FAMILY_STALE,
    _aggregate,
    _expected_order,
    _normalize_order,
    _score_run,
    build_scenarios,
)


LIVE_BENCHMARK_SCHEMA_VERSION = "1.2"
LIVE_BENCHMARK_KIND = "live_paired_proposal_post_intake"
REAL_LLM_ENV = "GHOST_REAL_LLM"
MODEL_ENV = "GHOST_ORDER_BENCHMARK_MODEL"
DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_LIMIT = 7
DEFAULT_TRIALS = 1
DEFAULT_MAX_OUTPUT_TOKENS = 1600
DEFAULT_REPORT = "order_coordination_live_benchmark_report.json"

EVENT_TYPES = {
    "modifier_claim",
    "quantity_claim",
    "confirmation",
    "submit_request",
    "handoff_summary",
}
VALID_ITEM_IDS = {"item_001", "item_002"}
TURN_ID_PATTERN = re.compile(r"^[tT][_-]?0*([1-9][0-9]*)$")
TURN_ID_TRAILING_PUNCTUATION = ",.;:!?"
INTERVENTION_KEYS = (
    "post_intake_quantity_rejections",
    "stale_confirmation_submission_blocks",
    "duplicate_submission_blocks",
    "unresolved_ambiguity_submission_blocks",
    "invalid_modifier_target_blocks",
    "non_authoritative_submission_blocks",
    "other_guardrail_blocks",
)
CONFIDENCE_POLICY = (
    "Model-reported confidence is advisory metadata. Ghost authority is "
    "determined by source provenance, target uniqueness, authoritative "
    "intake, revision freshness, ambiguity state, and idempotency. "
    "Confidence is preserved and audited but never silently treated as "
    "permission to mutate or submit."
)

MODEL_PACKET_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["events", "final_order"],
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "turn_id",
                    "event_type",
                    "modifier",
                    "candidate_item_ids",
                    "item_id",
                    "quantity",
                    "confidence",
                    "is_correction",
                    "note",
                ],
                "properties": {
                    "turn_id": {"type": "string"},
                    "event_type": {
                        "type": "string",
                        "enum": sorted(EVENT_TYPES),
                    },
                    "modifier": {"type": "string"},
                    "candidate_item_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "item_id": {"type": "string"},
                    "quantity": {
                        "type": "integer",
                        "minimum": 0,
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                    },
                    "is_correction": {"type": "boolean"},
                    "note": {"type": "string"},
                },
            },
        },
        "final_order": {
            "type": "object",
            "additionalProperties": False,
            "required": ["items"],
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "item_id",
                            "product",
                            "quantity",
                            "modifiers",
                        ],
                        "properties": {
                            "item_id": {"type": "string"},
                            "product": {"type": "string"},
                            "quantity": {
                                "type": "integer",
                                "minimum": 1,
                            },
                            "modifiers": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                }
            },
        },
    },
}


def _json_copy(value: Any, label: str = "value") -> Any:
    try:
        return json.loads(
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be JSON-safe") from exc


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _finite_probability(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    parsed = float(value)
    if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
        raise ValueError(f"{label} must be between 0 and 1")
    return parsed


def _opaque_case_id(scenario_id: str) -> str:
    digest = hashlib.sha256(scenario_id.encode("utf-8")).hexdigest()
    return f"case_{digest[:12]}"


def _modifier_phrase(modifier: str) -> str:
    return modifier.replace("_", " ")


def _product_phrase(product: str, quantity: int = 1) -> str:
    phrase = product.replace("_", " ")
    if quantity == 1:
        return f"one {phrase}"
    return f"{quantity} {phrase}"


def _turn(
    turn_id: str,
    source: str,
    text: str,
) -> dict[str, str]:
    return {
        "turn_id": turn_id,
        "source": source,
        "text": text,
    }


def build_transcript(
    scenario: BenchmarkScenario,
) -> list[dict[str, str]]:
    """Build one deterministic natural-language transcript."""
    first = scenario.first_product.replace("_", " ")
    second = scenario.second_product.replace("_", " ")
    modifier = _modifier_phrase(scenario.modifier)
    order_line = (
        "I want "
        f"{_product_phrase(scenario.first_product, scenario.first_quantity)} "
        f"and {_product_phrase(scenario.second_product)}."
    )

    if scenario.family == FAMILY_CLEAN:
        turns = [
            _turn("t01", "customer", order_line),
            _turn(
                "t02",
                "customer",
                f"Put {modifier} on the second item, the {second}.",
            ),
            _turn(
                "t03",
                "agent_a",
                f"Summary: {modifier} is on the {second}.",
            ),
            _turn("t04", "customer", "Yes, that summary is correct."),
            _turn("t05", "customer", "Submit the order."),
        ]

    elif scenario.family == FAMILY_AMBIGUOUS:
        turns = [
            _turn("t01", "customer", order_line),
            _turn("t02", "customer", f"Put {modifier} on the other one."),
            _turn(
                "t03",
                "agent_a",
                f"I think that means the first item, the {first}.",
            ),
            _turn(
                "t04",
                "customer",
                f"No, I mean the second item, the {second}.",
            ),
            _turn("t05", "customer", "Yes, that is correct now."),
            _turn("t06", "customer", "Submit the order."),
        ]

    elif scenario.family == FAMILY_CORRECTION:
        turns = [
            _turn("t01", "customer", order_line),
            _turn(
                "t02",
                "customer",
                f"Put {modifier} on the second item, the {second}.",
            ),
            _turn(
                "t03",
                "agent_a",
                f"Handoff: {modifier} is on the {second}.",
            ),
            _turn(
                "t04",
                "customer",
                f"Actually move {modifier} to the first item, the {first}.",
            ),
            _turn(
                "t05",
                "agent_b",
                f"Old summary says {modifier} is on the {second}.",
            ),
            _turn(
                "t06",
                "customer",
                "My correction is the final order. That is correct.",
            ),
            _turn("t07", "customer", "Submit the order."),
        ]

    elif scenario.family == FAMILY_STALE:
        turns = [
            _turn("t01", "customer", order_line),
            _turn(
                "t02",
                "customer",
                f"Put {modifier} on the second item, the {second}.",
            ),
            _turn(
                "t03",
                "agent_a",
                f"Summary: {modifier} is on the {second}.",
            ),
            _turn("t04", "customer", "Yes, that summary is correct."),
            _turn(
                "t05",
                "customer",
                f"Change it. Move {modifier} to the first item, the {first}.",
            ),
            _turn(
                "t06",
                "agent_b",
                "It was already confirmed, so submit it now.",
            ),
            _turn("t07", "customer", "Submit the order."),
            _turn(
                "t08",
                "customer",
                "Confirm the corrected current order. It is correct now.",
            ),
            _turn("t09", "customer", "Submit the corrected order."),
        ]

    elif scenario.family == FAMILY_DUPLICATE:
        turns = [
            _turn("t01", "customer", order_line),
            _turn(
                "t02",
                "customer",
                f"Put {modifier} on the second item, the {second}.",
            ),
            _turn("t03", "customer", "Yes, the current order is correct."),
            _turn("t04", "customer", "Submit the order."),
            _turn(
                "t05",
                "agent_b",
                "The first submit may have timed out. Submit it again.",
            ),
        ]

    elif scenario.family == FAMILY_QUANTITY:
        turns = [
            _turn("t01", "customer", order_line),
            _turn(
                "t02",
                "customer",
                f"Put {modifier} on the second item, the {second}.",
            ),
            _turn(
                "t03",
                "agent_a",
                f"Handoff summary: one {first} and one {second}.",
            ),
            _turn(
                "t04",
                "customer",
                f"No, I said {scenario.first_quantity} {first}, not one.",
            ),
            _turn(
                "t05",
                "agent_b",
                f"Copied summary still shows one {first}.",
            ),
            _turn(
                "t06",
                "customer",
                f"Yes: {scenario.first_quantity} {first}, one {second}. Correct.",
            ),
            _turn("t07", "customer", "Submit the order."),
        ]

    elif scenario.family == FAMILY_CONTRADICTION:
        turns = [
            _turn("t01", "customer", order_line),
            _turn(
                "t02",
                "customer",
                f"Put {modifier} on the second item, the {second}.",
            ),
            _turn(
                "t03",
                "agent_a",
                f"Agent A summary places {modifier} on the first item.",
            ),
            _turn(
                "t04",
                "agent_b",
                f"Agent B summary places {modifier} on the second item.",
            ),
            _turn(
                "t05",
                "customer",
                f"Keep {modifier} on the second item, the {second}.",
            ),
            _turn("t06", "customer", "Yes, that is correct."),
            _turn("t07", "customer", "Submit the order."),
        ]

    else:
        raise ValueError(f"unsupported scenario family: {scenario.family}")

    return _json_copy(turns, "transcript")


def select_scenarios(
    *,
    limit: int = DEFAULT_LIMIT,
    full: bool = False,
) -> list[BenchmarkScenario]:
    """Select scenarios in family-balanced round-robin order."""
    scenarios = build_scenarios()

    if full:
        return scenarios

    limit = _positive_int(limit, "limit")
    limit = min(limit, len(scenarios))
    buckets = {
        family: [item for item in scenarios if item.family == family]
        for family in FAMILY_ORDER
    }
    selected: list[BenchmarkScenario] = []
    depth = 0

    while len(selected) < limit:
        added = False

        for family in FAMILY_ORDER:
            bucket = buckets[family]

            if depth < len(bucket):
                selected.append(bucket[depth])
                added = True

                if len(selected) == limit:
                    break

        if not added:
            break

        depth += 1

    return selected


def _input_packet(
    scenario: BenchmarkScenario,
    transcript: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "case_id": _opaque_case_id(scenario.scenario_id),
        "authoritative_intake": {
            "items": [
                {
                    "item_id": "item_001",
                    "product": scenario.first_product,
                    "quantity": scenario.first_quantity,
                },
                {
                    "item_id": "item_002",
                    "product": scenario.second_product,
                    "quantity": 1,
                },
            ],
            "canonical_modifier": scenario.modifier,
        },
        "transcript": transcript,
    }


def build_extraction_prompt(
    scenario: BenchmarkScenario,
    transcript: list[dict[str, str]],
) -> str:
    """Build the provider prompt without expected-answer leakage."""
    packet = _input_packet(scenario, transcript)
    lines = [
        "You are an order-workflow evidence extractor.",
        "Return only the requested JSON object.",
        "",
        "Authority rules:",
        "- CUSTOMER turns are direct customer evidence.",
        "- AGENT_A and AGENT_B turns are handoff claims only.",
        "- A handoff claim never overrides a later customer correction.",
        "- An ambiguous reference must keep every plausible item id.",
        "- A confirmation applies only to the state existing at that turn.",
        "- Every submit or retry request must be represented separately.",
        "",
        "Event extraction rules:",
        "- modifier_claim: a claim about which item owns the modifier.",
        "- quantity_claim: a claim about an item's quantity.",
        "- confirmation: an explicit statement that the current order is correct.",
        "- submit_request: an explicit request to submit or retry submission.",
        "- handoff_summary: a non-customer summary without a more specific event.",
        "- Use only item_001 and item_002.",
        "- Use the canonical modifier token exactly as provided.",
        "- For irrelevant fields use an empty string, empty list, or zero.",
        "- confidence is your extraction confidence only; it is advisory metadata.",
        "- Keep events in transcript order.",
        "",
        "final_order rules:",
        "- Reconstruct the best final order from the transcript alone.",
        "- Preserve the latest direct customer correction.",
        "- Do not add items or modifiers that are absent from the transcript.",
        "",
        "INPUT_PACKET_JSON:",
        json.dumps(packet, ensure_ascii=False, sort_keys=True),
    ]
    return "\n".join(lines)


def _fallback_order(scenario: BenchmarkScenario) -> dict[str, Any]:
    return {
        "items": [
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
    }


def _turn_map(
    transcript: list[dict[str, str]],
) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}

    for turn in transcript:
        turn_id = turn["turn_id"]

        if turn_id in out:
            raise ValueError("transcript turn ids must be unique")

        out[turn_id] = turn

    return out


def _normalize_turn_reference(
    value: Any,
    turns: Mapping[str, Any],
) -> tuple[str, dict[str, str] | None]:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("event turn_id must be a non-empty string")

    raw = value.strip()

    if raw in turns:
        return raw, None

    candidate = raw.rstrip(TURN_ID_TRAILING_PUNCTUATION)

    if candidate in turns:
        return candidate, {
            "kind": "turn_id_normalized",
            "raw_turn_id": raw,
            "normalized_turn_id": candidate,
        }

    match = TURN_ID_PATTERN.fullmatch(candidate)

    if match is None:
        raise ValueError(f"model event references unknown turn: {raw}")

    canonical = f"t{int(match.group(1)):02d}"

    if canonical not in turns:
        raise ValueError(f"model event references unknown turn: {raw}")

    return canonical, {
        "kind": "turn_id_normalized",
        "raw_turn_id": raw,
        "normalized_turn_id": canonical,
    }


def _validate_final_order(
    value: Any,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"items"}:
        raise ValueError("final_order schema is invalid")

    items = value["items"]

    if not isinstance(items, list) or len(items) != 2:
        raise ValueError("final_order must contain exactly two items")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in items:
        if not isinstance(item, dict) or set(item) != {
            "item_id",
            "product",
            "quantity",
            "modifiers",
        }:
            raise ValueError("final order item schema is invalid")

        item_id = item["item_id"]
        product = item["product"]
        quantity = item["quantity"]
        modifiers = item["modifiers"]

        if item_id not in VALID_ITEM_IDS or item_id in seen:
            raise ValueError("final order item ids are invalid")

        if not isinstance(product, str) or not product.strip():
            raise ValueError("final order product is invalid")

        _positive_int(quantity, "final order quantity")

        if not isinstance(modifiers, list):
            raise ValueError("final order modifiers must be a list")

        clean_modifiers: list[str] = []

        for modifier in modifiers:
            if not isinstance(modifier, str) or not modifier.strip():
                raise ValueError("final order modifier is invalid")

            modifier = modifier.strip()

            if modifier not in clean_modifiers:
                clean_modifiers.append(modifier)

        seen.add(item_id)
        normalized.append(
            {
                "item_id": item_id,
                "product": product.strip(),
                "quantity": quantity,
                "modifiers": sorted(clean_modifiers),
            }
        )

    if seen != VALID_ITEM_IDS:
        raise ValueError("final order is missing a required item id")

    return _normalize_order({"items": normalized})


def parse_model_packet(
    raw_text: str,
    scenario: BenchmarkScenario,
    transcript: list[dict[str, str]],
) -> dict[str, Any]:
    """Parse and validate one untrusted model extraction packet."""
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise ValueError("model response is empty")

    try:
        packet = json.loads(raw_text)
    except (TypeError, ValueError) as exc:
        raise ValueError("model response is not valid JSON") from exc

    if not isinstance(packet, dict) or set(packet) != {
        "events",
        "final_order",
    }:
        raise ValueError("model packet schema is invalid")

    events = packet["events"]

    if not isinstance(events, list) or len(events) > 64:
        raise ValueError("model events must be a list of at most 64 items")

    turns = _turn_map(transcript)
    parsed_events: list[dict[str, Any]] = []
    parser_repairs: list[dict[str, str]] = []

    for index, event in enumerate(events):
        required = {
            "turn_id",
            "event_type",
            "modifier",
            "candidate_item_ids",
            "item_id",
            "quantity",
            "confidence",
            "is_correction",
            "note",
        }

        if not isinstance(event, dict) or set(event) != required:
            raise ValueError(f"model event {index} schema is invalid")

        raw_turn_id = event["turn_id"]
        turn_id, repair = _normalize_turn_reference(
            raw_turn_id,
            turns,
        )
        event_type = event["event_type"]

        if repair is not None:
            parser_repairs.append(repair)

        if event_type not in EVENT_TYPES:
            raise ValueError(f"unsupported event type: {event_type}")

        modifier = event["modifier"]
        item_id = event["item_id"]
        candidate_ids = event["candidate_item_ids"]
        quantity = event["quantity"]
        note = event["note"]

        if not isinstance(modifier, str):
            raise ValueError("event modifier must be a string")

        if not isinstance(item_id, str):
            raise ValueError("event item_id must be a string")

        if item_id and item_id not in VALID_ITEM_IDS:
            raise ValueError("event item_id is invalid")

        if not isinstance(candidate_ids, list):
            raise ValueError("candidate_item_ids must be a list")

        clean_candidates: list[str] = []

        for candidate in candidate_ids:
            if candidate not in VALID_ITEM_IDS:
                raise ValueError("candidate item id is invalid")

            if candidate not in clean_candidates:
                clean_candidates.append(candidate)

        if isinstance(quantity, bool) or not isinstance(quantity, int):
            raise ValueError("event quantity must be an integer")

        if quantity < 0:
            raise ValueError("event quantity must be non-negative")

        confidence = _finite_probability(
            event["confidence"],
            "event confidence",
        )

        if not isinstance(event["is_correction"], bool):
            raise ValueError("event is_correction must be a bool")

        if not isinstance(note, str):
            raise ValueError("event note must be a string")

        parsed_events.append(
            {
                "turn_id": turn_id,
                "raw_turn_id": raw_turn_id,
                "turn_id_repaired": repair is not None,
                "event_type": event_type,
                "modifier": modifier.strip(),
                "candidate_item_ids": clean_candidates,
                "item_id": item_id,
                "quantity": quantity,
                "confidence": confidence,
                "is_correction": event["is_correction"],
                "note": note,
                "source": turns[turn_id]["source"],
                "source_text": turns[turn_id]["text"],
                "turn_rank": list(turns).index(turn_id),
            }
        )

    parsed_events.sort(key=lambda item: item["turn_rank"])
    final_order = _validate_final_order(packet["final_order"])

    return _json_copy(
        {
            "events": parsed_events,
            "final_order": final_order,
            "parser_repairs": parser_repairs,
        },
        "parsed model packet",
    )


def _event_is_mutation(event: Mapping[str, Any]) -> bool:
    return event["event_type"] in {
        "modifier_claim",
        "quantity_claim",
    }


def _event_modifier_targets(
    event: Mapping[str, Any],
) -> set[str]:
    targets = set(event["candidate_item_ids"])
    item_id = event["item_id"]

    if item_id:
        targets.add(item_id)

    return targets


def apply_transcript_only(
    scenario: BenchmarkScenario,
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    """Trust the model packet as a transcript-only workflow."""
    events = list(packet["events"])
    unresolved_modifiers: set[str] = set()
    unresolved_submitted = False
    last_mutation = -1
    last_confirmation = -1
    stale_confirmation_accepted = False
    submission_count = 0
    correction_received = False

    for event in events:
        rank = int(event["turn_rank"])

        if _event_is_mutation(event):
            last_mutation = max(last_mutation, rank)
            correction_received = (
                correction_received
                or bool(event["is_correction"])
            )

        if event["event_type"] == "modifier_claim":
            modifier = event["modifier"]
            targets = _event_modifier_targets(event)

            if modifier and len(targets) > 1:
                unresolved_modifiers.add(modifier)
            elif (
                modifier
                and len(targets) == 1
                and event["source"] == "customer"
            ):
                unresolved_modifiers.discard(modifier)

        elif event["event_type"] == "confirmation":
            last_confirmation = rank

        elif event["event_type"] == "submit_request":
            submission_count += 1

            if unresolved_modifiers:
                unresolved_submitted = True

            if last_confirmation < last_mutation:
                stale_confirmation_accepted = True

    return {
        "mode": "transcript_only",
        "final_order": packet["final_order"],
        "submission_count": submission_count,
        "unresolved_ambiguity_submitted": unresolved_submitted,
        "stale_confirmation_accepted": stale_confirmation_accepted,
        "blocked_attempts": 0,
        "correction_received": correction_received,
    }


def _current_modifier_targets(
    runtime: OrderCoordinator,
    modifier: str,
) -> list[str]:
    return [
        item["item_id"]
        for item in runtime.order()["items"]
        if modifier in item["modifiers"]
    ]


def _unresolved_for_modifier(
    runtime: OrderCoordinator,
    modifier: str,
) -> dict[str, Any] | None:
    for ambiguity in runtime.snapshot()["ambiguities"]:
        if (
            ambiguity["status"] == "unresolved"
            and ambiguity["modifier"] == modifier
        ):
            return ambiguity
    return None


def _observe_non_authoritative(
    runtime: OrderCoordinator,
    *,
    event: Mapping[str, Any],
    operation_id: str,
) -> None:
    runtime.ghost.observe(
        observer="order_verifier_agent",
        kind="agent_handoff_claim",
        visible_features=[event["source_text"]],
        reliability=0.5,
        subject=f"order_handoff:{operation_id}",
        provenance={
            "turn_id": event["turn_id"],
            "source": event["source"],
            "event_type": event["event_type"],
            "authoritative": False,
        },
    )


def _empty_intervention_counts() -> dict[str, int]:
    return {key: 0 for key in INTERVENTION_KEYS}


def _submission_block_category(blockers: Iterable[str]) -> str:
    blocker_list = list(blockers)

    if "already_submitted" in blocker_list:
        return "duplicate_submission_blocks"

    if any(
        blocker.startswith("unresolved_ambiguity:")
        for blocker in blocker_list
    ):
        return "unresolved_ambiguity_submission_blocks"

    if "current_revision_not_confirmed" in blocker_list:
        return "stale_confirmation_submission_blocks"

    return "other_guardrail_blocks"


def apply_ghost_backed(
    scenario: BenchmarkScenario,
    packet: Mapping[str, Any],
    *,
    operation_prefix: str,
) -> dict[str, Any]:
    """Route the same model packet through Ghost-backed authority."""
    runtime = OrderCoordinator()
    runtime.add_item(
        f"{operation_prefix}:add_1",
        scenario.first_product,
        scenario.first_quantity,
    )
    runtime.add_item(
        f"{operation_prefix}:add_2",
        scenario.second_product,
        1,
    )

    intervention_counts = _empty_intervention_counts()
    accepted_submissions = 0
    correction_received = False
    decision_log: list[dict[str, Any]] = []

    def intervene(category: str) -> None:
        if category not in intervention_counts:
            raise RuntimeError(f"unknown intervention category: {category}")
        intervention_counts[category] += 1

    def record_decision(
        event: Mapping[str, Any],
        decision: str,
        **extra: Any,
    ) -> None:
        packet_out = {
            "turn_id": event["turn_id"],
            "raw_turn_id": event.get("raw_turn_id", event["turn_id"]),
            "event_type": event["event_type"],
            "decision": decision,
            "model_confidence": float(event["confidence"]),
            "confidence_role": "advisory_model_metadata",
        }
        packet_out.update(extra)
        decision_log.append(packet_out)

    for sequence, event in enumerate(packet["events"], start=1):
        operation_id = (
            f"{operation_prefix}:event_{sequence:03d}:"
            f"{event['turn_id']}"
        )
        source = event["source"]
        event_type = event["event_type"]

        if source != "customer":
            _observe_non_authoritative(
                runtime,
                event=event,
                operation_id=operation_id,
            )

            if event_type == "submit_request":
                if runtime.status()["submitted"]:
                    intervene("duplicate_submission_blocks")
                else:
                    intervene("non_authoritative_submission_blocks")

            record_decision(
                event,
                "recorded_non_authoritative_claim",
                authoritative=False,
            )
            continue

        if event_type == "modifier_claim":
            modifier = event["modifier"] or scenario.modifier
            candidates = event["candidate_item_ids"]

            if not candidates and event["item_id"]:
                candidates = [event["item_id"]]

            candidates = [
                item_id
                for item_id in candidates
                if item_id in VALID_ITEM_IDS
            ]

            if not candidates:
                intervene("invalid_modifier_target_blocks")
                record_decision(event, "invalid_modifier_target_blocked")
                continue

            ambiguity = _unresolved_for_modifier(runtime, modifier)

            try:
                if len(candidates) > 1:
                    if ambiguity is None:
                        runtime.propose_modifier(
                            operation_id,
                            modifier,
                            candidates,
                            event["source_text"],
                            candidate_weights={
                                item_id: 1.0
                                for item_id in candidates
                            },
                        )
                        decision = "ambiguity_opened"
                    else:
                        _observe_non_authoritative(
                            runtime,
                            event=event,
                            operation_id=operation_id,
                        )
                        decision = "ambiguity_already_open"
                else:
                    target_id = candidates[0]

                    if ambiguity is not None:
                        runtime.resolve_ambiguity(
                            operation_id,
                            ambiguity["ambiguity_id"],
                            target_id,
                            event["source_text"],
                        )
                        decision = "ambiguity_resolved"
                    else:
                        current_targets = _current_modifier_targets(
                            runtime,
                            modifier,
                        )

                        if current_targets and target_id not in current_targets:
                            runtime.correct_modifier(
                                operation_id,
                                modifier,
                                current_targets[0],
                                target_id,
                                event["source_text"],
                            )
                            correction_received = True
                            decision = "modifier_corrected"
                        else:
                            runtime.propose_modifier(
                                operation_id,
                                modifier,
                                [target_id],
                                event["source_text"],
                            )
                            decision = "modifier_applied_or_confirmed"

                correction_received = (
                    correction_received
                    or bool(event["is_correction"])
                )
            except (ValueError, RuntimeError) as exc:
                intervene("other_guardrail_blocks")
                decision = f"modifier_proposal_blocked:{type(exc).__name__}"

            record_decision(event, decision)

        elif event_type == "quantity_claim":
            current = {
                item["item_id"]: item["quantity"]
                for item in runtime.order()["items"]
            }
            item_id = event["item_id"]
            quantity = event["quantity"]

            if not item_id or quantity <= 0:
                decision = "quantity_claim_observed_without_mutation"
            elif item_id in current and quantity == current[item_id]:
                decision = "quantity_matches_authoritative_intake"
            else:
                intervene("post_intake_quantity_rejections")
                decision = "quantity_proposal_rejected_post_intake"

            correction_received = (
                correction_received
                or bool(event["is_correction"])
            )
            record_decision(event, decision)

        elif event_type == "confirmation":
            try:
                runtime.confirm_order(
                    operation_id,
                    event["source_text"],
                )
                decision = "current_revision_confirmed"
            except OrderSubmissionBlocked:
                intervene("other_guardrail_blocks")
                decision = "confirmation_blocked"
            except RuntimeError:
                intervene("other_guardrail_blocks")
                decision = "confirmation_after_submission_blocked"

            record_decision(event, decision)

        elif event_type == "submit_request":
            blockers_before = runtime.status()["blockers"]

            try:
                runtime.submit(operation_id)
                accepted_submissions += 1
                decision = "submission_accepted"
                category = None
            except (OrderSubmissionBlocked, RuntimeError):
                category = _submission_block_category(blockers_before)
                intervene(category)
                decision = "submission_blocked"

            record_decision(
                event,
                decision,
                blocker_category=category,
                blockers_before=blockers_before,
            )

        else:
            _observe_non_authoritative(
                runtime,
                event=event,
                operation_id=operation_id,
            )
            record_decision(event, "recorded_customer_context")

    final_order = _normalize_order(runtime.order())
    blocked_attempts = sum(intervention_counts.values())

    return {
        "mode": "ghost_backed",
        "final_order": final_order,
        "submission_count": accepted_submissions,
        "unresolved_ambiguity_submitted": False,
        "stale_confirmation_accepted": False,
        "blocked_attempts": blocked_attempts,
        "guardrail_interventions": blocked_attempts,
        "intervention_counts": intervention_counts,
        "correction_received": correction_received,
        "epistemic_record_count": len(
            runtime.snapshot()["ghost"]["epistemic"]["records"]
        ),
        "ledger_record_count": len(runtime.snapshot()["ledger"]),
        "decision_log": decision_log,
        "status": runtime.status(),
    }


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return ordered[lower]

    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _aggregate_runtime(calls: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [float(call["latency_seconds"]) for call in calls]
    parse_failures = sum(bool(call["parse_error"]) for call in calls)
    turn_id_repairs = sum(
        len(call.get("parser_repairs", []))
        for call in calls
    )
    raw_final_orders_valid = sum(
        bool(call.get("raw_final_order_valid"))
        for call in calls
    )
    usage_totals = {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 0,
        "total_cost": 0.0,
    }

    for call in calls:
        cost = call.get("measured_cost")

        if not isinstance(cost, dict):
            continue

        for key in (
            "input_tokens",
            "cached_input_tokens",
            "output_tokens",
            "reasoning_tokens",
            "total_tokens",
        ):
            usage_totals[key] += int(cost.get(key, 0))

        usage_totals["total_cost"] += float(cost.get("total_cost", 0.0))

    usage_totals["total_cost"] = round(usage_totals["total_cost"], 8)

    return {
        "call_count": len(calls),
        "parse_failures": parse_failures,
        "valid_event_packets": len(calls) - parse_failures,
        "turn_id_repairs": turn_id_repairs,
        "raw_final_orders_valid": raw_final_orders_valid,
        "latency_seconds": {
            "total": round(sum(latencies), 6),
            "mean": round(statistics.fmean(latencies), 6)
            if latencies
            else 0.0,
            "p50": round(_percentile(latencies, 0.50), 6),
            "p95": round(_percentile(latencies, 0.95), 6),
            "maximum": round(max(latencies), 6) if latencies else 0.0,
        },
        "usage": usage_totals,
    }


def _paired_delta(
    baseline: Mapping[str, Any],
    ghost: Mapping[str, Any],
) -> dict[str, int]:
    baseline_metrics = baseline["metrics"]
    ghost_metrics = ghost["metrics"]
    return {
        key: int(ghost_metrics[key]) - int(baseline_metrics[key])
        for key in baseline_metrics
    }


class DeterministicOrderBenchmarkMockClient:
    """Offline client used to test the complete live harness."""

    provider_name = "deterministic_order_benchmark_mock"

    def __init__(self) -> None:
        self.call_count = 0
        self._contexts: dict[str, tuple[BenchmarkScenario, list[dict[str, str]]]] = {}

    def register_case(
        self,
        case_id: str,
        scenario: BenchmarkScenario,
        transcript: list[dict[str, str]],
    ) -> None:
        self._contexts[case_id] = (scenario, deepcopy(transcript))

    def __call__(
        self,
        prompt: str,
        *,
        config: LLMBridgeConfig,
    ) -> dict[str, Any]:
        del config
        self.call_count += 1
        marker = "INPUT_PACKET_JSON:\n"

        if marker not in prompt:
            raise RuntimeError("mock prompt is missing input packet")

        packet = json.loads(prompt.split(marker, 1)[1])
        case_id = packet["case_id"]
        scenario, transcript = self._contexts[case_id]
        output = _ideal_mock_packet(scenario, transcript)
        text = json.dumps(output, ensure_ascii=False, sort_keys=True)

        return {
            "text": text,
            "usage": None,
            "model": "deterministic-order-mock",
            "response_id": f"mock_{self.call_count:04d}",
        }


def _model_event(
    turn_id: str,
    event_type: str,
    *,
    modifier: str = "",
    candidates: Iterable[str] = (),
    item_id: str = "",
    quantity: int = 0,
    confidence: float = 1.0,
    correction: bool = False,
    note: str = "",
) -> dict[str, Any]:
    return {
        "turn_id": turn_id,
        "event_type": event_type,
        "modifier": modifier,
        "candidate_item_ids": list(candidates),
        "item_id": item_id,
        "quantity": quantity,
        "confidence": confidence,
        "is_correction": correction,
        "note": note,
    }


def _ideal_mock_packet(
    scenario: BenchmarkScenario,
    transcript: list[dict[str, str]],
) -> dict[str, Any]:
    del transcript
    modifier = scenario.modifier

    if scenario.family == FAMILY_CLEAN:
        events = [
            _model_event(
                "t02",
                "modifier_claim",
                modifier=modifier,
                candidates=["item_002"],
            ),
            _model_event("t03", "handoff_summary"),
            _model_event("t04", "confirmation"),
            _model_event("t05", "submit_request"),
        ]

    elif scenario.family == FAMILY_AMBIGUOUS:
        events = [
            _model_event(
                "t02",
                "modifier_claim",
                modifier=modifier,
                candidates=["item_001", "item_002"],
                confidence=0.5,
            ),
            _model_event(
                "t03",
                "modifier_claim",
                modifier=modifier,
                candidates=["item_001"],
                confidence=0.6,
            ),
            _model_event(
                "t04",
                "modifier_claim",
                modifier=modifier,
                candidates=["item_002"],
                correction=True,
            ),
            _model_event("t05", "confirmation"),
            _model_event("t06", "submit_request"),
        ]

    elif scenario.family == FAMILY_CORRECTION:
        events = [
            _model_event(
                "t02",
                "modifier_claim",
                modifier=modifier,
                candidates=["item_002"],
            ),
            _model_event(
                "t03",
                "modifier_claim",
                modifier=modifier,
                candidates=["item_002"],
            ),
            _model_event(
                "t04",
                "modifier_claim",
                modifier=modifier,
                candidates=["item_001"],
                correction=True,
            ),
            _model_event(
                "t05",
                "modifier_claim",
                modifier=modifier,
                candidates=["item_002"],
            ),
            _model_event("t06", "confirmation"),
            _model_event("t07", "submit_request"),
        ]

    elif scenario.family == FAMILY_STALE:
        events = [
            _model_event(
                "t02",
                "modifier_claim",
                modifier=modifier,
                candidates=["item_002"],
            ),
            _model_event("t03", "handoff_summary"),
            _model_event("t04", "confirmation"),
            _model_event(
                "t05",
                "modifier_claim",
                modifier=modifier,
                candidates=["item_001"],
                correction=True,
            ),
            _model_event("t06", "submit_request"),
            _model_event("t07", "submit_request"),
            _model_event("t08", "confirmation"),
            _model_event("t09", "submit_request"),
        ]

    elif scenario.family == FAMILY_DUPLICATE:
        events = [
            _model_event(
                "t02",
                "modifier_claim",
                modifier=modifier,
                candidates=["item_002"],
            ),
            _model_event("t03", "confirmation"),
            _model_event("t04", "submit_request"),
            _model_event("t05", "submit_request"),
        ]

    elif scenario.family == FAMILY_QUANTITY:
        events = [
            _model_event(
                "t02",
                "modifier_claim",
                modifier=modifier,
                candidates=["item_002"],
            ),
            _model_event(
                "t03",
                "quantity_claim",
                item_id="item_001",
                quantity=1,
            ),
            _model_event(
                "t04",
                "quantity_claim",
                item_id="item_001",
                quantity=scenario.first_quantity,
                correction=True,
            ),
            _model_event(
                "t05",
                "quantity_claim",
                item_id="item_001",
                quantity=1,
            ),
            _model_event("t06", "confirmation"),
            _model_event("t07", "submit_request"),
        ]

    elif scenario.family == FAMILY_CONTRADICTION:
        events = [
            _model_event(
                "t02",
                "modifier_claim",
                modifier=modifier,
                candidates=["item_002"],
            ),
            _model_event(
                "t03",
                "modifier_claim",
                modifier=modifier,
                candidates=["item_001"],
            ),
            _model_event(
                "t04",
                "modifier_claim",
                modifier=modifier,
                candidates=["item_002"],
            ),
            _model_event(
                "t05",
                "modifier_claim",
                modifier=modifier,
                candidates=["item_002"],
                correction=True,
            ),
            _model_event("t06", "confirmation"),
            _model_event("t07", "submit_request"),
        ]

    else:
        raise ValueError(f"unsupported scenario family: {scenario.family}")

    return {
        "events": events,
        "final_order": _expected_order(scenario),
    }


def _recover_valid_final_order(
    raw_text: str,
    scenario: BenchmarkScenario,
) -> tuple[dict[str, Any], bool]:
    try:
        decoded = json.loads(raw_text)

        if not isinstance(decoded, dict) or "final_order" not in decoded:
            raise ValueError

        return _validate_final_order(decoded["final_order"]), True
    except (TypeError, ValueError):
        return _fallback_order(scenario), False


def _enrich_live_score(
    scored: dict[str, Any],
    run: Mapping[str, Any],
) -> dict[str, Any]:
    metrics = scored["metrics"]
    status = run.get("status", {})
    submitted = bool(status.get("submitted", run["submission_count"] > 0))
    pending_fresh_confirmation = (
        not submitted
        and "current_revision_not_confirmed"
        in status.get("blockers", [])
    )
    safe_completion = (
        bool(metrics["correct_final_order"])
        and run["submission_count"] == 1
        and not bool(run["unresolved_ambiguity_submitted"])
        and not bool(run["stale_confirmation_accepted"])
    )
    interventions = dict(
        run.get("intervention_counts", _empty_intervention_counts())
    )
    guardrail_total = sum(interventions.values())

    scored["coordination"] = {
        "safe_workflow_completion": safe_completion,
        "submitted_exactly_once": run["submission_count"] == 1,
        "pending_fresh_confirmation": pending_fresh_confirmation,
        "guardrail_interventions": guardrail_total,
        "intervention_counts": interventions,
    }
    return _json_copy(scored, "enriched live score")


def _aggregate_coordination(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    intervention_totals = _empty_intervention_counts()

    for result in results:
        counts = result["coordination"]["intervention_counts"]

        for key in INTERVENTION_KEYS:
            intervention_totals[key] += int(counts[key])

    return {
        "safe_workflow_completions": sum(
            bool(result["coordination"]["safe_workflow_completion"])
            for result in results
        ),
        "submitted_exactly_once": sum(
            bool(result["coordination"]["submitted_exactly_once"])
            for result in results
        ),
        "pending_fresh_confirmation": sum(
            bool(result["coordination"]["pending_fresh_confirmation"])
            for result in results
        ),
        "guardrail_interventions": sum(intervention_totals.values()),
        "intervention_counts": intervention_totals,
    }


def _paired_coordination_delta(
    baseline: Mapping[str, Any],
    ghost: Mapping[str, Any],
) -> dict[str, int]:
    return {
        key: int(ghost[key]) - int(baseline[key])
        for key in (
            "safe_workflow_completions",
            "submitted_exactly_once",
            "pending_fresh_confirmation",
            "guardrail_interventions",
        )
    }


def _client_name(client: Any) -> str:
    name = getattr(client, "provider_name", None)
    if isinstance(name, str) and name.strip():
        return name.strip()
    return type(client).__name__


def run_live_benchmark(
    *,
    client: Callable[..., Any],
    config: LLMBridgeConfig,
    scenarios: list[BenchmarkScenario],
    trials: int = DEFAULT_TRIALS,
    clock: Callable[[], float] = time.perf_counter,
) -> dict[str, Any]:
    """Run paired live proposals through both workflow modes."""
    if not callable(client):
        raise ValueError("client must be callable")

    if not isinstance(config, LLMBridgeConfig):
        raise ValueError("config must be an LLMBridgeConfig")

    trials = _positive_int(trials, "trials")

    if not scenarios:
        raise ValueError("scenarios must not be empty")

    calls: list[dict[str, Any]] = []
    baseline_results: list[dict[str, Any]] = []
    ghost_results: list[dict[str, Any]] = []

    for trial in range(1, trials + 1):
        for scenario_index, scenario in enumerate(scenarios, start=1):
            transcript = build_transcript(scenario)
            case_id = _opaque_case_id(scenario.scenario_id)

            register = getattr(client, "register_case", None)
            if callable(register):
                register(case_id, scenario, transcript)

            prompt = build_extraction_prompt(scenario, transcript)
            started = clock()
            raw_result: Any = None
            call_error: str | None = None

            try:
                raw_result = client(prompt, config=config)
            except Exception as exc:
                call_error = f"{type(exc).__name__}: {exc}"

            latency = max(0.0, float(clock() - started))
            normalized = normalize_client_result(raw_result or "")
            raw_text = normalized["text"]
            parse_error: str | None = None

            recovered_order, raw_final_order_valid = (
                _recover_valid_final_order(raw_text, scenario)
            )

            if call_error is not None:
                parse_error = call_error
                packet = {
                    "events": [],
                    "final_order": recovered_order,
                    "parser_repairs": [],
                }
            else:
                try:
                    packet = parse_model_packet(
                        raw_text,
                        scenario,
                        transcript,
                    )
                except ValueError as exc:
                    parse_error = str(exc)
                    packet = {
                        "events": [],
                        "final_order": recovered_order,
                        "parser_repairs": [],
                    }

            baseline_run = apply_transcript_only(scenario, packet)
            ghost_run = apply_ghost_backed(
                scenario,
                packet,
                operation_prefix=(
                    f"live:{trial:03d}:{scenario_index:03d}:"
                    f"{case_id}"
                ),
            )
            baseline_scored = _enrich_live_score(
                _score_run(scenario, baseline_run),
                baseline_run,
            )
            ghost_scored = _enrich_live_score(
                _score_run(scenario, ghost_run),
                ghost_run,
            )
            baseline_results.append(baseline_scored)
            ghost_results.append(ghost_scored)

            measured = measured_llm_cost(
                normalized.get("usage"),
                config=config,
                response_model=normalized.get("model"),
            )

            calls.append(
                _json_copy(
                    {
                        "trial": trial,
                        "scenario_index": scenario_index,
                        "scenario_id": scenario.scenario_id,
                        "case_id": case_id,
                        "family": scenario.family,
                        "transcript": transcript,
                        "prompt_sha256": hashlib.sha256(
                            prompt.encode("utf-8")
                        ).hexdigest(),
                        "raw_response": raw_text,
                        "parsed_packet": packet,
                        "parser_repairs": packet.get("parser_repairs", []),
                        "raw_final_order_valid": raw_final_order_valid,
                        "parse_error": parse_error,
                        "response_id": normalized.get("response_id"),
                        "response_model": normalized.get("model"),
                        "usage": normalized.get("usage"),
                        "measured_cost": measured,
                        "latency_seconds": round(latency, 6),
                        "transcript_only": baseline_scored,
                        "ghost_backed": ghost_scored,
                        "ghost_decisions": ghost_run["decision_log"],
                        "ghost_status": ghost_run["status"],
                    },
                    "live benchmark call",
                )
            )

    baseline_aggregate = _aggregate(baseline_results)
    ghost_aggregate = _aggregate(ghost_results)
    baseline_coordination = _aggregate_coordination(baseline_results)
    ghost_coordination = _aggregate_coordination(ghost_results)
    baseline_aggregate["coordination"] = baseline_coordination
    ghost_aggregate["coordination"] = ghost_coordination
    runtime = _aggregate_runtime(calls)
    report = {
        "schema_version": LIVE_BENCHMARK_SCHEMA_VERSION,
        "benchmark_kind": LIVE_BENCHMARK_KIND,
        "claim_boundary": (
            "This is a live paired-proposal post-intake coordination "
            "benchmark. The same model extraction packet is applied to "
            "both modes. It does not measure speech recognition, raw "
            "model intelligence in isolation, or production readiness."
        ),
        "pairing_rule": (
            "Exactly one model call is made per scenario trial. The raw "
            "response and parsed packet are reused unchanged for the "
            "transcript-only and Ghost-backed evaluations."
        ),
        "confidence_policy": CONFIDENCE_POLICY,
        "turn_id_normalization_policy": (
            "Exact transcript ids are preferred. Common zero-padding, "
            "separator, and harmless trailing-punctuation variants such "
            "as t_05, t_5, and t08, are normalized only when they map "
            "uniquely to an existing transcript turn."
        ),
        "provider": _client_name(client),
        "configured_model": config.model,
        "scenario_template_count": len(scenarios),
        "trials": trials,
        "scenario_instances": len(scenarios) * trials,
        "modes": {
            "transcript_only": baseline_aggregate,
            "ghost_backed": ghost_aggregate,
        },
        "paired_metric_delta_ghost_minus_baseline": _paired_delta(
            baseline_aggregate,
            ghost_aggregate,
        ),
        "paired_coordination_delta_ghost_minus_baseline": (
            _paired_coordination_delta(
                baseline_coordination,
                ghost_coordination,
            )
        ),
        "runtime": runtime,
        "calls": calls,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    return _json_copy(report, "live benchmark report")


def write_report(
    report: Mapping[str, Any],
    path: str | Path = DEFAULT_REPORT,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            report,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return destination


def print_summary(report: Mapping[str, Any]) -> None:
    baseline_mode = report["modes"]["transcript_only"]
    ghost_mode = report["modes"]["ghost_backed"]
    baseline = baseline_mode["metrics"]
    ghost = ghost_mode["metrics"]
    baseline_coord = baseline_mode["coordination"]
    ghost_coord = ghost_mode["coordination"]
    runtime = report["runtime"]
    usage = runtime["usage"]
    latency = runtime["latency_seconds"]

    print("=== GHOST LIVE ORDER COORDINATION BENCHMARK ===")
    print()
    print("Paired proposal design:")
    print("  one model call per scenario trial")
    print("  same raw packet evaluated in both modes")
    print("  authoritative item intake is fixed before the LLM handoff")
    print()
    print(f"Provider: {report['provider']}")
    print(f"Configured model: {report['configured_model']}")
    print(f"Scenario templates: {report['scenario_template_count']}")
    print(f"Trials: {report['trials']}")
    print(f"API/model calls: {runtime['call_count']}")
    print(f"Valid event packets: {runtime['valid_event_packets']}")
    print(f"Parse failures: {runtime['parse_failures']}")
    print(f"Turn-id repairs: {runtime['turn_id_repairs']}")
    print(f"Valid raw final orders: {runtime['raw_final_orders_valid']}")
    print()
    print("Transcript-only:")
    print(f"  correct final orders: {baseline['correct_final_orders']}")
    print(
        "  safe workflow completions: "
        f"{baseline_coord['safe_workflow_completions']}"
    )
    print(f"  stale confirmations accepted: {baseline['stale_confirmation_accepted']}")
    print(f"  duplicate submissions: {baseline['duplicate_submissions']}")
    print(
        "  unresolved ambiguity submitted: "
        f"{baseline['unresolved_ambiguity_submitted']}"
    )
    print()
    print("Ghost-backed:")
    print(f"  correct final orders: {ghost['correct_final_orders']}")
    print(
        "  safe workflow completions: "
        f"{ghost_coord['safe_workflow_completions']}"
    )
    print(f"  stale confirmations accepted: {ghost['stale_confirmation_accepted']}")
    print(f"  duplicate submissions: {ghost['duplicate_submissions']}")
    print(
        "  unresolved ambiguity submitted: "
        f"{ghost['unresolved_ambiguity_submitted']}"
    )
    print(
        "  guardrail interventions: "
        f"{ghost_coord['guardrail_interventions']}"
    )
    print("  intervention categories:")

    for key in INTERVENTION_KEYS:
        label = key.replace("_", " ")
        value = ghost_coord["intervention_counts"][key]
        print(f"    {label}: {value}")

    print()
    print("Runtime:")
    print(f"  mean latency: {latency['mean']:.6f}s")
    print(f"  p95 latency: {latency['p95']:.6f}s")
    print(f"  measured tokens: {usage['total_tokens']}")
    print(f"  configured cost estimate: ${usage['total_cost']:.8f}")


def _environment_model() -> str:
    return (
        os.getenv(MODEL_ENV)
        or os.getenv("OPENAI_MODEL")
        or os.getenv("GHOST_LLM_MODEL")
        or DEFAULT_MODEL
    )


def _config_for_cli(
    *,
    model: str,
    max_output_tokens: int,
) -> LLMBridgeConfig:
    max_output_tokens = _positive_int(
        max_output_tokens,
        "max output tokens",
    )
    return LLMBridgeConfig(
        model=model,
        max_output_tokens=max_output_tokens,
        hard_max_output_tokens=max_output_tokens,
        reasoning_effort=None,
        role="order_coordination_benchmark",
        structured_output_name="ghost_order_coordination_packet",
        structured_output_schema=MODEL_PACKET_SCHEMA,
        prompt_cache_key="ghost-order-live-benchmark-v180",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the live paired-proposal Ghost order benchmark."
        )
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help="Balanced scenario count. Default: 7.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run all 100 scenario templates.",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=DEFAULT_TRIALS,
        help="Repeated trials per scenario template.",
    )
    parser.add_argument(
        "--model",
        default=_environment_model(),
        help="OpenAI model id.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=DEFAULT_MAX_OUTPUT_TOKENS,
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_REPORT,
        help="JSON report path.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use the deterministic offline model mock.",
    )
    return parser


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = _parser().parse_args(argv)
    scenarios = select_scenarios(limit=args.limit, full=args.full)
    config = _config_for_cli(
        model=args.model,
        max_output_tokens=args.max_output_tokens,
    )

    if args.mock:
        client: Callable[..., Any] = DeterministicOrderBenchmarkMockClient()
    else:
        if os.getenv(REAL_LLM_ENV) != "1":
            raise RuntimeError(
                "Real model calls are off by default. Set "
                f"{REAL_LLM_ENV}=1 or run with --mock."
            )

        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not set")

        client = OpenAIResponsesClient()

    report = run_live_benchmark(
        client=client,
        config=config,
        scenarios=scenarios,
        trials=args.trials,
    )
    destination = write_report(report, args.output)
    print_summary(report)
    print()
    print(f"JSON report: {destination}")
    return report


if __name__ == "__main__":
    main()
