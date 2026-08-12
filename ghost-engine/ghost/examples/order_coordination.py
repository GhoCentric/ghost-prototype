"""
Deterministic order coordination built on Ghost's public API.

This is an application-layer example, not restaurant logic inside the
Ghost core. Language models may propose interpretations, but this runtime
owns authoritative order state, ambiguity, corrections, confirmation,
idempotency, and submission gating.
"""

from __future__ import annotations

from copy import deepcopy
import json
import math
from typing import Any, Callable

from ghost import GhostAPI


ORDER_COORDINATION_SCHEMA_VERSION = "1.0"


class OrderSubmissionBlocked(ValueError):
    """Raised when an order cannot be submitted safely."""


def _json_copy(value: Any, label: str) -> Any:
    try:
        return json.loads(
            json.dumps(
                value,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be JSON-safe") from exc


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")

    return value.strip()


def _positive_int(value: Any, label: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
    ):
        raise ValueError(f"{label} must be a positive integer")

    return value


def _non_negative_int(value: Any, label: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
    ):
        raise ValueError(
            f"{label} must be a non-negative integer"
        )

    return value


def _candidate_ids(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(
            "candidate item ids must be a list or tuple"
        )

    out = []

    for item_id in value:
        item_id = _text(item_id, "candidate item id")

        if item_id not in out:
            out.append(item_id)

    if not out:
        raise ValueError("candidate item ids must not be empty")

    return out


def _candidate_weights(
    candidate_ids: list[str],
    value: dict | None,
) -> dict[str, float]:
    if value is None:
        return {
            item_id: 1.0
            for item_id in candidate_ids
        }

    if not isinstance(value, dict):
        raise ValueError(
            "candidate weights must be a dict or None"
        )

    if set(value) != set(candidate_ids):
        raise ValueError(
            "candidate weights must match candidate item ids"
        )

    out = {}

    for item_id in candidate_ids:
        weight = value[item_id]

        if (
            isinstance(weight, bool)
            or not isinstance(weight, (int, float))
        ):
            raise ValueError(
                "candidate weights must contain numbers"
            )

        weight = float(weight)

        if not math.isfinite(weight) or weight < 0.0:
            raise ValueError(
                "candidate weights must be finite and non-negative"
            )

        out[item_id] = weight

    total = sum(out.values())

    if total <= 0.0:
        raise ValueError(
            "candidate weights must have positive total weight"
        )

    return {
        item_id: weight / total
        for item_id, weight in out.items()
    }


class OrderCoordinator:
    """
    Shared deterministic state for one order workflow.

    The coordinator deliberately does not parse natural language. An LLM
    or another adapter proposes structured candidates. The coordinator
    records those proposals as epistemic state and refuses to guess when
    more than one target remains possible.
    """

    _SNAPSHOT_KEYS = {
        "schema_version",
        "item_sequence",
        "ambiguity_sequence",
        "fact_sequence",
        "revision",
        "confirmed_revision",
        "submitted",
        "items",
        "ambiguities",
        "corrections",
        "confirmations",
        "ledger",
        "operations",
        "ghost",
    }

    def __init__(self, ghost: GhostAPI | None = None):
        if ghost is not None and not isinstance(ghost, GhostAPI):
            raise ValueError("ghost must be a GhostAPI or None")

        self.ghost = ghost or GhostAPI()
        self._item_sequence = 0
        self._ambiguity_sequence = 0
        self._fact_sequence = 0
        self._revision = 0
        self._confirmed_revision: int | None = None
        self._submitted = False
        self._items: list[dict] = []
        self._ambiguities: list[dict] = []
        self._corrections: list[dict] = []
        self._confirmations: list[dict] = []
        self._ledger: list[dict] = []
        self._operations: dict[str, dict] = {}

    def _restore_from(self, restored: "OrderCoordinator") -> None:
        self.__dict__.clear()
        self.__dict__.update(restored.__dict__)

    def _item(self, item_id: str) -> dict:
        for item in self._items:
            if item["item_id"] == item_id:
                return item

        raise ValueError(f"unknown order item id: {item_id}")

    def _ambiguity(self, ambiguity_id: str) -> dict:
        for ambiguity in self._ambiguities:
            if ambiguity["ambiguity_id"] == ambiguity_id:
                return ambiguity

        raise ValueError(f"unknown ambiguity id: {ambiguity_id}")

    def _ensure_open(self) -> None:
        if self._submitted:
            raise RuntimeError("submitted orders are immutable")

    def _append_ledger(self, event: str, data: dict) -> dict:
        record = {
            "sequence": len(self._ledger) + 1,
            "event": _text(event, "ledger event"),
            "revision": self._revision,
            "data": _json_copy(data, "ledger data"),
        }
        self._ledger.append(record)

        return record

    def _mutated(self, event: str, data: dict) -> None:
        self._revision += 1
        self._confirmed_revision = None
        self._append_ledger(event, data)

    def _record_fact(
        self,
        *,
        subject: str,
        predicate: str,
        object: str,
        attributes: dict,
    ) -> dict:
        self._fact_sequence += 1

        return self.ghost.record_fact(
            fact_id=(
                f"order_fact_{self._fact_sequence:06d}"
            ),
            source="order_coordination_runtime",
            subject=subject,
            predicate=predicate,
            object=object,
            attributes=attributes,
        )

    def _observe_statement(
        self,
        *,
        source_text: str,
        subject: str,
        operation_id: str,
        purpose: str,
    ) -> dict:
        return self.ghost.observe(
            observer="order_intake_agent",
            kind="customer_statement",
            visible_features=[source_text],
            reliability=1.0,
            subject=subject,
            provenance={
                "operation_id": operation_id,
                "purpose": purpose,
                "language_observation_only": True,
            },
        )

    def _run_operation(
        self,
        operation_id: str,
        kind: str,
        payload: dict,
        action: Callable[[], dict],
    ) -> dict:
        operation_id = _text(operation_id, "operation id")
        kind = _text(kind, "operation kind")
        payload = _json_copy(payload, "operation payload")
        signature = {
            "kind": kind,
            "payload": payload,
        }
        existing = self._operations.get(operation_id)

        if existing is not None:
            if existing["signature"] != signature:
                raise ValueError(
                    "operation id was reused with different input"
                )

            return deepcopy(existing["result"])

        before = self.snapshot()

        try:
            result = _json_copy(action(), "operation result")
            packet = {
                "operation_id": operation_id,
                "kind": kind,
                "result": result,
                "status": self.status(),
            }
            packet = _json_copy(packet, "operation packet")
            self._operations[operation_id] = {
                "signature": signature,
                "result": packet,
            }
        except Exception:
            self._restore_from(
                type(self).from_snapshot(before)
            )
            raise

        return deepcopy(packet)

    def add_item(
        self,
        operation_id: str,
        product: str,
        quantity: int = 1,
    ) -> dict:
        product = _text(product, "product")
        quantity = _positive_int(quantity, "quantity")

        def action() -> dict:
            self._ensure_open()
            self._item_sequence += 1
            item = {
                "item_id": f"item_{self._item_sequence:03d}",
                "product": product,
                "quantity": quantity,
                "modifiers": [],
            }
            self._items.append(item)
            fact = self._record_fact(
                subject=item["item_id"],
                predicate="is_order_item",
                object=product,
                attributes={"quantity": quantity},
            )
            self._mutated(
                "item_added",
                {
                    "item_id": item["item_id"],
                    "fact_id": fact["id"],
                },
            )

            return {
                "outcome": "item_added",
                "item": deepcopy(item),
                "fact_id": fact["id"],
            }

        return self._run_operation(
            operation_id,
            "add_item",
            {
                "product": product,
                "quantity": quantity,
            },
            action,
        )

    def propose_modifier(
        self,
        operation_id: str,
        modifier: str,
        candidate_item_ids: list[str] | tuple[str, ...],
        source_text: str,
        candidate_weights: dict | None = None,
    ) -> dict:
        modifier = _text(modifier, "modifier")
        source_text = _text(source_text, "source text")
        candidates = _candidate_ids(candidate_item_ids)
        weights = _candidate_weights(
            candidates,
            candidate_weights,
        )

        def action() -> dict:
            self._ensure_open()

            for item_id in candidates:
                self._item(item_id)

            if len(candidates) == 1:
                target_id = candidates[0]
                subject = (
                    "order_modifier_target:"
                    f"direct_{self._revision + 1:06d}"
                )
                observation = self._observe_statement(
                    source_text=source_text,
                    subject=subject,
                    operation_id=operation_id,
                    purpose="direct_modifier_target",
                )
                belief = self.ghost.evaluate_beliefs(
                    holder="order_intake_agent",
                    subject=subject,
                    candidates={"target": weights},
                    evidence_ids=[observation["id"]],
                    provenance={
                        "modifier": modifier,
                        "workflow": "order_coordination",
                    },
                )
                target = self._item(target_id)

                if modifier not in target["modifiers"]:
                    target["modifiers"].append(modifier)
                    target["modifiers"].sort()
                    fact = self._record_fact(
                        subject=target_id,
                        predicate="has_modifier",
                        object=modifier,
                        attributes={
                            "belief_id": belief["id"],
                            "observation_id": observation["id"],
                        },
                    )
                    self._mutated(
                        "modifier_applied",
                        {
                            "item_id": target_id,
                            "modifier": modifier,
                            "belief_id": belief["id"],
                            "fact_id": fact["id"],
                        },
                    )
                    outcome = "modifier_applied"
                else:
                    fact = None
                    outcome = "modifier_already_present"

                return {
                    "outcome": outcome,
                    "item_id": target_id,
                    "modifier": modifier,
                    "belief_id": belief["id"],
                    "fact_id": (
                        fact["id"]
                        if fact is not None
                        else None
                    ),
                }

            self._ambiguity_sequence += 1
            ambiguity_id = (
                f"ambiguity_{self._ambiguity_sequence:03d}"
            )
            subject = f"order_modifier_target:{ambiguity_id}"
            observation = self._observe_statement(
                source_text=source_text,
                subject=subject,
                operation_id=operation_id,
                purpose="ambiguous_modifier_target",
            )
            belief = self.ghost.evaluate_beliefs(
                holder="order_intake_agent",
                subject=subject,
                candidates={"target": weights},
                evidence_ids=[observation["id"]],
                provenance={
                    "modifier": modifier,
                    "workflow": "order_coordination",
                },
            )
            ambiguity = {
                "ambiguity_id": ambiguity_id,
                "kind": "modifier_target",
                "modifier": modifier,
                "candidate_item_ids": candidates,
                "source_text": source_text,
                "status": "unresolved",
                "chosen_item_id": None,
                "belief_id": belief["id"],
                "observation_ids": [observation["id"]],
                "resolution_evidence_id": None,
            }
            self._ambiguities.append(ambiguity)
            self._mutated(
                "ambiguity_opened",
                {
                    "ambiguity_id": ambiguity_id,
                    "belief_id": belief["id"],
                },
            )

            return {
                "outcome": "clarification_required",
                "ambiguity": deepcopy(ambiguity),
                "belief": belief,
            }

        return self._run_operation(
            operation_id,
            "propose_modifier",
            {
                "modifier": modifier,
                "candidate_item_ids": candidates,
                "source_text": source_text,
                "candidate_weights": weights,
            },
            action,
        )

    def resolve_ambiguity(
        self,
        operation_id: str,
        ambiguity_id: str,
        target_item_id: str,
        source_text: str,
    ) -> dict:
        ambiguity_id = _text(ambiguity_id, "ambiguity id")
        target_item_id = _text(target_item_id, "target item id")
        source_text = _text(source_text, "source text")

        def action() -> dict:
            self._ensure_open()
            ambiguity = self._ambiguity(ambiguity_id)

            if ambiguity["status"] != "unresolved":
                raise ValueError("ambiguity is already resolved")

            if target_item_id not in ambiguity[
                "candidate_item_ids"
            ]:
                raise ValueError(
                    "target item is not an ambiguity candidate"
                )

            target = self._item(target_item_id)
            subject = f"order_modifier_target:{ambiguity_id}"
            observation = self._observe_statement(
                source_text=source_text,
                subject=subject,
                operation_id=operation_id,
                purpose="modifier_target_clarification",
            )
            other_ids = [
                item_id
                for item_id in ambiguity["candidate_item_ids"]
                if item_id != target_item_id
            ]
            evidence = self.ghost.add_evidence(
                evidence_type="customer_clarification",
                source="customer",
                subject=subject,
                available_to="order_intake_agent",
                supports={
                    "target": {
                        target_item_id: 1.0,
                    },
                },
                contradicts=(
                    {
                        "target": {
                            item_id: 1.0
                            for item_id in other_ids
                        },
                    }
                    if other_ids
                    else None
                ),
                provenance={
                    "observation_id": observation["id"],
                    "operation_id": operation_id,
                },
            )
            revised = self.ghost.evaluate_beliefs(
                holder="order_intake_agent",
                subject=subject,
                previous_belief_id=ambiguity["belief_id"],
                evidence_ids=[evidence["id"]],
                provenance={
                    "resolution": "customer_clarification",
                },
            )
            target_packet = revised["dimensions"]["target"]

            if (
                target_packet["dominant_candidate"]
                != target_item_id
            ):
                raise RuntimeError(
                    "clarification did not resolve target deterministically"
                )

            modifier = ambiguity["modifier"]

            if modifier not in target["modifiers"]:
                target["modifiers"].append(modifier)
                target["modifiers"].sort()

            ambiguity["status"] = "resolved"
            ambiguity["chosen_item_id"] = target_item_id
            ambiguity["belief_id"] = revised["id"]
            ambiguity["observation_ids"].append(
                observation["id"]
            )
            ambiguity["resolution_evidence_id"] = evidence["id"]
            fact = self._record_fact(
                subject=target_item_id,
                predicate="has_modifier",
                object=modifier,
                attributes={
                    "ambiguity_id": ambiguity_id,
                    "belief_id": revised["id"],
                    "evidence_id": evidence["id"],
                },
            )
            self._mutated(
                "ambiguity_resolved",
                {
                    "ambiguity_id": ambiguity_id,
                    "item_id": target_item_id,
                    "modifier": modifier,
                    "belief_id": revised["id"],
                    "fact_id": fact["id"],
                },
            )

            return {
                "outcome": "ambiguity_resolved",
                "ambiguity": deepcopy(ambiguity),
                "belief": revised,
                "fact_id": fact["id"],
            }

        return self._run_operation(
            operation_id,
            "resolve_ambiguity",
            {
                "ambiguity_id": ambiguity_id,
                "target_item_id": target_item_id,
                "source_text": source_text,
            },
            action,
        )

    def correct_modifier(
        self,
        operation_id: str,
        modifier: str,
        from_item_id: str,
        to_item_id: str,
        source_text: str,
    ) -> dict:
        modifier = _text(modifier, "modifier")
        from_item_id = _text(from_item_id, "from item id")
        to_item_id = _text(to_item_id, "to item id")
        source_text = _text(source_text, "source text")

        if from_item_id == to_item_id:
            raise ValueError(
                "correction source and target must differ"
            )

        def action() -> dict:
            self._ensure_open()
            source_item = self._item(from_item_id)
            target_item = self._item(to_item_id)

            if modifier not in source_item["modifiers"]:
                raise ValueError(
                    "source item does not contain modifier"
                )

            subject = f"order_modifier_correction:{modifier}"
            observation = self._observe_statement(
                source_text=source_text,
                subject=subject,
                operation_id=operation_id,
                purpose="modifier_correction",
            )
            belief = self.ghost.evaluate_beliefs(
                holder="order_intake_agent",
                subject=subject,
                candidates={
                    "target": {
                        to_item_id: 1.0,
                    },
                },
                evidence_ids=[observation["id"]],
                provenance={
                    "from_item_id": from_item_id,
                    "modifier": modifier,
                },
            )
            source_item["modifiers"].remove(modifier)

            if modifier not in target_item["modifiers"]:
                target_item["modifiers"].append(modifier)
                target_item["modifiers"].sort()

            correction = {
                "correction_id": (
                    f"correction_{len(self._corrections) + 1:03d}"
                ),
                "modifier": modifier,
                "from_item_id": from_item_id,
                "to_item_id": to_item_id,
                "source_text": source_text,
                "observation_id": observation["id"],
                "belief_id": belief["id"],
            }
            self._corrections.append(correction)
            fact = self._record_fact(
                subject=modifier,
                predicate="moved_between_order_items",
                object=to_item_id,
                attributes={
                    "from_item_id": from_item_id,
                    "belief_id": belief["id"],
                },
            )
            self._mutated(
                "modifier_corrected",
                {
                    "correction_id": correction["correction_id"],
                    "fact_id": fact["id"],
                },
            )

            return {
                "outcome": "modifier_corrected",
                "correction": deepcopy(correction),
                "fact_id": fact["id"],
            }

        return self._run_operation(
            operation_id,
            "correct_modifier",
            {
                "modifier": modifier,
                "from_item_id": from_item_id,
                "to_item_id": to_item_id,
                "source_text": source_text,
            },
            action,
        )

    def confirm_order(
        self,
        operation_id: str,
        source_text: str,
    ) -> dict:
        source_text = _text(source_text, "source text")

        def action() -> dict:
            self._ensure_open()
            blockers = self._structural_blockers()

            if blockers:
                raise OrderSubmissionBlocked(
                    "order confirmation blocked: "
                    + ", ".join(blockers)
                )

            subject = "order_final_confirmation"
            observation = self._observe_statement(
                source_text=source_text,
                subject=subject,
                operation_id=operation_id,
                purpose="final_order_confirmation",
            )
            confirmation = {
                "confirmation_id": (
                    f"confirmation_{len(self._confirmations) + 1:03d}"
                ),
                "revision": self._revision,
                "source_text": source_text,
                "observation_id": observation["id"],
            }
            self._confirmations.append(confirmation)
            self._confirmed_revision = self._revision
            self._append_ledger(
                "order_confirmed",
                deepcopy(confirmation),
            )

            return {
                "outcome": "order_confirmed",
                "confirmation": deepcopy(confirmation),
            }

        return self._run_operation(
            operation_id,
            "confirm_order",
            {"source_text": source_text},
            action,
        )

    def submit(self, operation_id: str) -> dict:
        def action() -> dict:
            self._ensure_open()
            blockers = self._submission_blockers()

            if blockers:
                raise OrderSubmissionBlocked(
                    "order submission blocked: "
                    + ", ".join(blockers)
                )

            self._submitted = True
            fact = self._record_fact(
                subject="order",
                predicate="submission_status",
                object="submitted",
                attributes={
                    "revision": self._revision,
                    "confirmed_revision": self._confirmed_revision,
                },
            )
            self._append_ledger(
                "order_submitted",
                {
                    "fact_id": fact["id"],
                    "revision": self._revision,
                },
            )

            return {
                "outcome": "order_submitted",
                "fact_id": fact["id"],
                "order": self.order(),
            }

        return self._run_operation(
            operation_id,
            "submit",
            {},
            action,
        )

    def _unresolved_ids(self) -> list[str]:
        return [
            ambiguity["ambiguity_id"]
            for ambiguity in self._ambiguities
            if ambiguity["status"] == "unresolved"
        ]

    def _structural_blockers(self) -> list[str]:
        blockers = []

        if not self._items:
            blockers.append("no_items")

        for ambiguity_id in self._unresolved_ids():
            blockers.append(
                f"unresolved_ambiguity:{ambiguity_id}"
            )

        return blockers

    def _submission_blockers(self) -> list[str]:
        blockers = self._structural_blockers()

        if self._confirmed_revision != self._revision:
            blockers.append("current_revision_not_confirmed")

        return blockers

    def status(self) -> dict:
        blockers = self._submission_blockers()

        if self._submitted:
            blockers = ["already_submitted"]

        return {
            "revision": self._revision,
            "confirmed_revision": self._confirmed_revision,
            "submitted": self._submitted,
            "submission_allowed": not blockers,
            "blockers": blockers,
            "unresolved_ambiguities": self._unresolved_ids(),
            "item_count": len(self._items),
            "correction_count": len(self._corrections),
        }

    def order(self) -> dict:
        return deepcopy(
            {
                "items": self._items,
                "revision": self._revision,
                "confirmed_revision": self._confirmed_revision,
                "submitted": self._submitted,
            }
        )

    def snapshot(self) -> dict:
        return _json_copy(
            {
                "schema_version": (
                    ORDER_COORDINATION_SCHEMA_VERSION
                ),
                "item_sequence": self._item_sequence,
                "ambiguity_sequence": self._ambiguity_sequence,
                "fact_sequence": self._fact_sequence,
                "revision": self._revision,
                "confirmed_revision": self._confirmed_revision,
                "submitted": self._submitted,
                "items": self._items,
                "ambiguities": self._ambiguities,
                "corrections": self._corrections,
                "confirmations": self._confirmations,
                "ledger": self._ledger,
                "operations": self._operations,
                "ghost": self.ghost.snapshot(),
            },
            "order coordination snapshot",
        )

    @classmethod
    def from_snapshot(cls, snapshot: dict) -> "OrderCoordinator":
        if not isinstance(snapshot, dict):
            raise ValueError(
                "order coordination snapshot must be a dict"
            )

        snapshot = _json_copy(
            snapshot,
            "order coordination snapshot",
        )

        if set(snapshot) != cls._SNAPSHOT_KEYS:
            raise ValueError(
                "order coordination snapshot has unsupported keys"
            )

        if (
            snapshot["schema_version"]
            != ORDER_COORDINATION_SCHEMA_VERSION
        ):
            raise ValueError(
                "unsupported order coordination schema version"
            )

        item_sequence = _non_negative_int(
            snapshot["item_sequence"],
            "item sequence",
        )
        ambiguity_sequence = _non_negative_int(
            snapshot["ambiguity_sequence"],
            "ambiguity sequence",
        )
        fact_sequence = _non_negative_int(
            snapshot["fact_sequence"],
            "fact sequence",
        )
        revision = _non_negative_int(
            snapshot["revision"],
            "revision",
        )
        confirmed_revision = snapshot["confirmed_revision"]

        if confirmed_revision is not None:
            confirmed_revision = _non_negative_int(
                confirmed_revision,
                "confirmed revision",
            )

            if confirmed_revision > revision:
                raise ValueError(
                    "confirmed revision cannot exceed revision"
                )

        submitted = snapshot["submitted"]

        if not isinstance(submitted, bool):
            raise ValueError("submitted must be a bool")

        list_fields = (
            "items",
            "ambiguities",
            "corrections",
            "confirmations",
            "ledger",
        )

        for field in list_fields:
            if not isinstance(snapshot[field], list):
                raise ValueError(f"{field} must be a list")

        if not isinstance(snapshot["operations"], dict):
            raise ValueError("operations must be a dict")

        restored_ghost = GhostAPI.from_snapshot(snapshot["ghost"])
        ghost_records = restored_ghost.snapshot()["epistemic"]["records"]
        ghost_record_kinds = {
            record["id"]: record["kind"]
            for record in ghost_records
        }

        item_ids = set()

        for item in snapshot["items"]:
            if not isinstance(item, dict) or set(item) != {
                "item_id",
                "product",
                "quantity",
                "modifiers",
            }:
                raise ValueError("order item schema is invalid")

            item_id = _text(item["item_id"], "item id")
            _text(item["product"], "product")
            _positive_int(item["quantity"], "quantity")

            if item_id in item_ids:
                raise ValueError("order item ids must be unique")

            item_ids.add(item_id)

            if not isinstance(item["modifiers"], list):
                raise ValueError("item modifiers must be a list")

            modifiers = [
                _text(modifier, "modifier")
                for modifier in item["modifiers"]
            ]

            if len(set(modifiers)) != len(modifiers):
                raise ValueError("item modifiers must be unique")

        if len(snapshot["items"]) > item_sequence:
            raise ValueError(
                "item sequence is behind stored items"
            )

        unresolved = 0

        for ambiguity in snapshot["ambiguities"]:
            required = {
                "ambiguity_id",
                "kind",
                "modifier",
                "candidate_item_ids",
                "source_text",
                "status",
                "chosen_item_id",
                "belief_id",
                "observation_ids",
                "resolution_evidence_id",
            }

            if not isinstance(ambiguity, dict) or set(
                ambiguity
            ) != required:
                raise ValueError("ambiguity schema is invalid")

            _text(ambiguity["ambiguity_id"], "ambiguity id")
            _text(ambiguity["kind"], "ambiguity kind")
            _text(ambiguity["modifier"], "modifier")
            _text(ambiguity["source_text"], "source text")
            _text(ambiguity["belief_id"], "belief id")
            candidates = _candidate_ids(
                ambiguity["candidate_item_ids"]
            )

            if not set(candidates).issubset(item_ids):
                raise ValueError(
                    "ambiguity references unknown order item"
                )

            if not isinstance(ambiguity["observation_ids"], list):
                raise ValueError(
                    "ambiguity observation ids must be a list"
                )

            for record_id in ambiguity["observation_ids"]:
                _text(record_id, "observation id")

            status = ambiguity["status"]

            if status == "unresolved":
                unresolved += 1

                if (
                    ambiguity["chosen_item_id"] is not None
                    or ambiguity["resolution_evidence_id"] is not None
                ):
                    raise ValueError(
                        "unresolved ambiguity has resolution data"
                    )
            elif status == "resolved":
                chosen = _text(
                    ambiguity["chosen_item_id"],
                    "chosen item id",
                )

                if chosen not in candidates:
                    raise ValueError(
                        "resolved ambiguity chose non-candidate"
                    )

                _text(
                    ambiguity["resolution_evidence_id"],
                    "resolution evidence id",
                )
            else:
                raise ValueError("ambiguity status is invalid")

        if len(snapshot["ambiguities"]) > ambiguity_sequence:
            raise ValueError(
                "ambiguity sequence is behind stored ambiguities"
            )

        if submitted and confirmed_revision != revision:
            raise ValueError(
                "submitted order must have current confirmation"
            )

        if unresolved and submitted:
            raise ValueError(
                "submitted order cannot have unresolved ambiguity"
            )

        correction_ids = []
        correction_records = snapshot["corrections"]

        for correction in correction_records:
            required = {
                "correction_id",
                "modifier",
                "from_item_id",
                "to_item_id",
                "source_text",
                "observation_id",
                "belief_id",
            }

            if not isinstance(correction, dict) or set(
                correction
            ) != required:
                raise ValueError("correction schema is invalid")

            correction_id = _text(
                correction["correction_id"],
                "correction id",
            )

            if correction_id in correction_ids:
                raise ValueError("correction ids must be unique")

            correction_ids.append(correction_id)
            _text(correction["modifier"], "modifier")
            from_item_id = _text(
                correction["from_item_id"],
                "from item id",
            )
            to_item_id = _text(
                correction["to_item_id"],
                "to item id",
            )
            _text(correction["source_text"], "source text")
            observation_id = _text(
                correction["observation_id"],
                "observation id",
            )
            belief_id = _text(
                correction["belief_id"],
                "belief id",
            )

            if from_item_id == to_item_id:
                raise ValueError(
                    "correction source and target must differ"
                )

            if from_item_id not in item_ids:
                raise ValueError(
                    "correction references unknown source item"
                )

            if to_item_id not in item_ids:
                raise ValueError(
                    "correction references unknown target item"
                )

            if observation_id not in ghost_record_kinds:
                raise ValueError(
                    "correction references unknown observation"
                )

            if ghost_record_kinds[observation_id] != "observation":
                raise ValueError(
                    "correction observation reference is not an observation"
                )

            if belief_id not in ghost_record_kinds:
                raise ValueError(
                    "correction references unknown belief"
                )

            if ghost_record_kinds[belief_id] != "belief":
                raise ValueError(
                    "correction belief reference is not a belief"
                )

        confirmation_ids = []
        confirmation_records = snapshot["confirmations"]
        previous_confirmation_revision = -1

        for confirmation in confirmation_records:
            required = {
                "confirmation_id",
                "revision",
                "source_text",
                "observation_id",
            }

            if not isinstance(confirmation, dict) or set(
                confirmation
            ) != required:
                raise ValueError("confirmation schema is invalid")

            confirmation_id = _text(
                confirmation["confirmation_id"],
                "confirmation id",
            )

            if confirmation_id in confirmation_ids:
                raise ValueError("confirmation ids must be unique")

            confirmation_ids.append(confirmation_id)
            confirmation_revision = _non_negative_int(
                confirmation["revision"],
                "confirmation revision",
            )

            if confirmation_revision > revision:
                raise ValueError(
                    "confirmation revision exceeds runtime revision"
                )

            if confirmation_revision < previous_confirmation_revision:
                raise ValueError(
                    "confirmation revisions must be non-decreasing"
                )

            previous_confirmation_revision = confirmation_revision
            _text(confirmation["source_text"], "source text")
            observation_id = _text(
                confirmation["observation_id"],
                "observation id",
            )

            if observation_id not in ghost_record_kinds:
                raise ValueError(
                    "confirmation references unknown observation"
                )

            if ghost_record_kinds[observation_id] != "observation":
                raise ValueError(
                    "confirmation observation reference is not an observation"
                )

        if confirmed_revision is not None:
            if confirmed_revision != revision:
                raise ValueError(
                    "confirmed revision must equal current revision"
                )

            if not confirmation_records:
                raise ValueError(
                    "confirmed revision requires a confirmation record"
                )

            if confirmation_records[-1]["revision"] != confirmed_revision:
                raise ValueError(
                    "confirmed revision must match latest confirmation"
                )

        elif (
            confirmation_records
            and confirmation_records[-1]["revision"] == revision
        ):
            raise ValueError(
                "current-revision confirmation cannot be unconfirmed"
            )

        ledger_confirmation_records = []
        ledger_correction_ids = []
        ledger_correction_revisions = []

        for index, record in enumerate(
            snapshot["ledger"],
            start=1,
        ):
            if not isinstance(record, dict) or set(record) != {
                "sequence",
                "event",
                "revision",
                "data",
            }:
                raise ValueError("ledger record schema is invalid")

            if record["sequence"] != index:
                raise ValueError("ledger sequence is invalid")

            _text(record["event"], "ledger event")
            record_revision = _non_negative_int(
                record["revision"],
                "ledger revision",
            )

            if record_revision > revision:
                raise ValueError(
                    "ledger revision exceeds runtime revision"
                )

            if not isinstance(record["data"], dict):
                raise ValueError("ledger data must be a dict")

            if record["event"] == "order_confirmed":
                ledger_confirmation_records.append(
                    (record_revision, record["data"])
                )
            elif record["event"] == "modifier_corrected":
                ledger_correction_ids.append(
                    record["data"].get("correction_id")
                )
                ledger_correction_revisions.append(
                    record_revision
                )

        expected_confirmation_records = [
            (confirmation["revision"], confirmation)
            for confirmation in confirmation_records
        ]

        if (
            ledger_confirmation_records
            != expected_confirmation_records
        ):
            raise ValueError(
                "confirmation records do not match confirmation ledger"
            )

        if ledger_correction_ids != correction_ids:
            raise ValueError(
                "correction records do not match correction ledger"
            )

        if ledger_correction_revisions != sorted(
            set(ledger_correction_revisions)
        ):
            raise ValueError(
                "correction ledger revisions must increase"
            )

        for operation_id, operation in snapshot[
            "operations"
        ].items():
            _text(operation_id, "operation id")

            if not isinstance(operation, dict) or set(operation) != {
                "signature",
                "result",
            }:
                raise ValueError("operation schema is invalid")

            if not isinstance(operation["signature"], dict):
                raise ValueError("operation signature must be a dict")

            if not isinstance(operation["result"], dict):
                raise ValueError("operation result must be a dict")

        runtime = cls.__new__(cls)
        runtime.ghost = restored_ghost
        runtime._item_sequence = item_sequence
        runtime._ambiguity_sequence = ambiguity_sequence
        runtime._fact_sequence = fact_sequence
        runtime._revision = revision
        runtime._confirmed_revision = confirmed_revision
        runtime._submitted = submitted
        runtime._items = deepcopy(snapshot["items"])
        runtime._ambiguities = deepcopy(snapshot["ambiguities"])
        runtime._corrections = deepcopy(snapshot["corrections"])
        runtime._confirmations = deepcopy(snapshot["confirmations"])
        runtime._ledger = deepcopy(snapshot["ledger"])
        runtime._operations = deepcopy(snapshot["operations"])

        return runtime
