"""
Deterministic scenario runtime for Ghost v1.8+.

This module sits above Ghost's generic state engine.
It turns one validated scenario action into one complete,
JSON-safe consequence packet.
"""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

from .api import GhostAPI
from .events import normalize_game_action
from .scenario import validate_scenario_config
from .validation import (
    validate_finite_number,
    validate_unit_interval,
)


NEGATIVE_ACTIONS = {
    "insult",
    "threat",
    "attack",
    "theft",
    "betrayal",
}

ACTION_SEVERITY = {
    "neutral": 0.00,
    "greet": 0.00,
    "help": 0.00,
    "cooperate": 0.00,
    "apology": 0.00,
    "disengage": 0.00,
    "pressure": 0.15,
    "manipulate": 0.20,
    "deceive": 0.30,
    "insult": 0.35,
    "threat": 0.55,
    "attack": 0.75,
    "theft": 0.70,
    "betrayal": 0.90,
}

ACTION_WORLD_EFFECTS = {
    "neutral": {},
    "greet": {},
    "help": {
        "pressure_delta": -0.05,
        "fear_delta": -0.02,
        "order_delta": 0.01,
        "commerce_delta": 0.01,
        "resentment_delta": -0.02,
    },
    "cooperate": {
        "pressure_delta": -0.03,
        "order_delta": 0.01,
        "commerce_delta": 0.02,
        "resentment_delta": -0.01,
    },
    "apology": {
        "pressure_delta": -0.04,
        "fear_delta": -0.01,
        "resentment_delta": -0.03,
    },
    "disengage": {
        "pressure_delta": -0.01,
    },
    "pressure": {
        "pressure_delta": 0.10,
        "fear_delta": 0.02,
        "resentment_delta": 0.03,
        "order_delta": -0.01,
    },
    "manipulate": {
        "pressure_delta": 0.14,
        "fear_delta": 0.03,
        "resentment_delta": 0.05,
        "order_delta": -0.02,
    },
    "deceive": {
        "pressure_delta": 0.18,
        "fear_delta": 0.04,
        "resentment_delta": 0.06,
        "order_delta": -0.03,
    },
    "insult": {
        "pressure_delta": 0.22,
        "fear_delta": 0.05,
        "resentment_delta": 0.08,
        "order_delta": -0.03,
    },
    "threat": {
        "pressure_delta": 0.35,
        "fear_delta": 0.10,
        "resentment_delta": 0.10,
        "order_delta": -0.06,
    },
    "attack": {
        "pressure_delta": 0.60,
        "fear_delta": 0.18,
        "resentment_delta": 0.15,
        "order_delta": -0.10,
        "commerce_delta": -0.05,
    },
    "theft": {
        "pressure_delta": 0.42,
        "fear_delta": 0.08,
        "resentment_delta": 0.12,
        "order_delta": -0.06,
        "commerce_delta": -0.04,
    },
    "betrayal": {
        "pressure_delta": 0.70,
        "fear_delta": 0.14,
        "resentment_delta": 0.18,
        "order_delta": -0.10,
        "commerce_delta": -0.06,
    },
}


def _require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")

    normalized = value.strip()

    if not normalized:
        raise ValueError(f"{field_name} must not be empty")

    return normalized


def _copy_effects(action_type: str, intensity: float) -> dict:
    effects = ACTION_WORLD_EFFECTS.get(action_type)

    if effects is None:
        raise ValueError(
            f"unsupported scenario action: {action_type}"
        )

    return {
        key: float(value) * intensity
        for key, value in effects.items()
    }


class ScenarioRuntime:
    """
    Deterministic scenario layer around GhostAPI.

    ScenarioRuntime owns game-facing counters and evaluates a full
    consequence packet after every player action.
    """

    def __init__(
        self,
        config: dict,
        api: GhostAPI | None = None,
    ):
        self.config = validate_scenario_config(config)
        self.api = api or GhostAPI()

        self.warning_count = 0
        self.arrest_count = 0
        self.served_punishment = False
        self.resistance_remaining = 0
        self.quest_completed = False
        self.price_records = {}

        self._seed_relationships()

    def _seed_relationships(self) -> None:
        for relationship in self.config["relationships"]:
            source = relationship["source"]
            target = relationship["target"]
            trust = relationship["trust"]

            self.api.engine.relationships.apply_delta(
                source,
                target,
                {"trust": trust},
            )

    def _target_id(self, value: Any) -> str:
        target = _require_string(value, "action.target")

        roles = self.config["npc_roles"]

        if target in roles:
            return roles[target]

        if target in self.config["npcs"]:
            return target

        raise ValueError(
            f"action.target is not a scenario role or NPC: {target}"
        )

    def _observer_ids(self, target_id: str) -> list[str]:
        observers = []

        for npc_id in sorted(self.config["npcs"]):
            if npc_id != target_id:
                observers.append(npc_id)

        return observers

    def _severity(
        self,
        action_type: str,
        relationship: dict,
        intensity: float,
    ) -> float:
        trust = float(relationship.get("trust", 0.0))
        action_base = (
            ACTION_SEVERITY[action_type]
            * intensity
        )

        return min(
            5.0,
            action_base + max(0.0, -trust),
        )

    def _town_status(self) -> str:
        pressure = self.api.world_state()["global_pressure"]

        if pressure >= self.config["thresholds"]["pressure_expulsion"]:
            return "expelled"

        if pressure >= self.config["thresholds"]["pressure_crisis"]:
            return "crisis"

        return "normal"

    def _quest_packet(
        self,
        relationship: dict,
    ) -> dict:
        trust = float(relationship.get("trust", 0.0))
        pressure = float(
            self.api.world_state()["global_pressure"]
        )

        trust_required = self.config["quest"]["trust_required"]
        pressure_max = self.config["quest"]["pressure_max"]

        available = bool(
            trust >= trust_required
            and pressure <= pressure_max
        )

        return {
            "available": available,
            "completed": self.quest_completed,
            "trust_required": trust_required,
            "pressure_max": pressure_max,
            "trust": trust,
            "pressure": pressure,
        }

    def _win_fail_packet(
        self,
        relationship: dict,
        law: dict,
    ) -> dict:
        shopkeeper_id = self.config["npc_roles"].get(
            "shopkeeper"
        )

        shopkeeper_trust = None

        if shopkeeper_id:
            shopkeeper_trust = self.api.get_relationship(
                "player",
                shopkeeper_id,
            )["trust"]

        pressure = self.api.world_state()["global_pressure"]

        condition_values = {
            "restore_shopkeeper_trust": bool(
                shopkeeper_trust is not None
                and shopkeeper_trust
                >= self.config["quest"]["trust_required"]
            ),
            "complete_market_quest": self.quest_completed,
            "guard_arrests_player": law["action"] == "detain",
            "town_expels_player": (
                pressure
                >= self.config["thresholds"]["pressure_expulsion"]
            ),
        }

        won = [
            name
            for name in self.config["win_conditions"]
            if condition_values.get(name, False)
        ]

        failed = [
            name
            for name in self.config["fail_conditions"]
            if condition_values.get(name, False)
        ]

        return {
            "won": won,
            "failed": failed,
            "is_win": bool(won),
            "is_fail": bool(failed),
            "shopkeeper_trust": shopkeeper_trust,
            "pressure": pressure,
            "current_relationship": relationship,
        }

    def _checkpoint(self) -> dict:
        """Capture all mutable ScenarioRuntime state."""
        return {
            "api": self.api.snapshot(),
            "warning_count": self.warning_count,
            "arrest_count": self.arrest_count,
            "served_punishment": self.served_punishment,
            "resistance_remaining": self.resistance_remaining,
            "quest_completed": self.quest_completed,
            "price_records": deepcopy(self.price_records),
        }


    def _restore_checkpoint(self, checkpoint: dict) -> None:
        """Restore state after a rejected action."""
        self.api.restore_snapshot(checkpoint["api"])
        self.warning_count = checkpoint["warning_count"]
        self.arrest_count = checkpoint["arrest_count"]
        self.served_punishment = checkpoint["served_punishment"]
        self.resistance_remaining = checkpoint[
            "resistance_remaining"
        ]
        self.quest_completed = checkpoint["quest_completed"]
        self.price_records = deepcopy(
            checkpoint["price_records"]
        )


    def resolve_action(self, action: dict) -> dict:
        """
        Resolve one action atomically or leave the runtime unchanged.
        """
        checkpoint = self._checkpoint()

        try:
            return self._resolve_action(action)
        except Exception:
            self._restore_checkpoint(checkpoint)
            raise

    def _resolve_action(self, action: dict) -> dict:
        """
        Resolve one player action into one full consequence packet.

        Supported action fields:
        - type: known Ghost event or "complete_quest"
        - target: scenario role name or NPC ID
        - intensity: optional unit interval, default 1.0
        - item: optional economy item for commerce pricing
        """
        if not isinstance(action, dict):
            raise ValueError("action must be a dict")

        raw_type = _require_string(
            action.get("type"),
            "action.type",
        )
        target_id = self._target_id(action.get("target"))

        intensity = validate_unit_interval(
            action.get("intensity", 1.0),
            "action.intensity",
        )

        item = action.get("item")

        if item is not None:
            item = _require_string(item, "action.item")

            if item not in self.config["economy"]["base_prices"]:
                raise ValueError(
                    f"unknown economy item: {item}"
                )

        if raw_type == "complete_quest":
            relationship = self.api.get_relationship(
                "player",
                target_id,
            )

            quest_before = self._quest_packet(relationship)

            if not quest_before["available"]:
                raise ValueError(
                    "quest cannot be completed while unavailable"
                )

            self.quest_completed = True

            social_packet = {
                "event": "complete_quest",
                "intensity": intensity,
                "direct": relationship,
                "propagated": [],
            }
            action_type = "complete_quest"
            world_effects = {}
            severity = 0.0

        else:
            action_type = normalize_game_action(raw_type)

            if action_type not in self.api.event_map:
                raise ValueError(
                    f"unsupported scenario action: {action_type}"
                )

            if action_type == "neutral":
                relationship = self.api.get_relationship(
                    "player",
                    target_id,
                )

                social_packet = {
                    "event": "neutral",
                    "intensity": intensity,
                    "direct": relationship,
                    "propagated": [],
                }

                world_effects = {}
                severity = 0.0

            else:
                observers = self._observer_ids(target_id)

                social_packet = self.api.propagate_social_event(
                    "player",
                    target_id,
                    action_type,
                    observers=observers,
                    weights=self.config["propagation_weights"],
                    intensity=intensity,
                )

                relationship = self.api.get_relationship(
                    "player",
                    target_id,
                )

                world_effects = _copy_effects(
                    action_type,
                    intensity,
                )

                if world_effects:
                    self.api.apply_world_effects(world_effects)

                severity = self._severity(
                    action_type,
                    relationship,
                    intensity,
                )

        town_status = self._town_status()

        if action_type in NEGATIVE_ACTIONS:
            self.warning_count += 1

        law_decision = self.api.law.evaluate(
            severity=severity,
            argument_pressure=self.warning_count,
            warning_count=self.warning_count,
        ).to_dict()

        if law_decision["action"] == "detain":
            self.served_punishment = True
            self.arrest_count += 1

        relationship_state = relationship.get(
            "state",
            "neutral",
        )

        blacklisted = bool(
            relationship_state == "hostile"
            or severity
            >= self.config["thresholds"]["arrest_severity"]
        )

        commerce_decision = self.api.commerce.evaluate_service(
            severity=severity,
            blacklisted=blacklisted,
            town_status=town_status,
        ).to_dict()

        pricing = None

        if item is not None:
            base_price = self.config["economy"]["base_prices"][item]

            pricing_decision = self.api.pricing.compute_price(
                item=item,
                base_price=int(base_price),
                relationship_state=relationship_state,
                sale_access=commerce_decision["sale_access"],
                economic_modifier=self.api.world_state()[
                    "mood"
                ]["commerce"],
                severity=severity,
                prior_record=self.price_records.get(item),
            )

            pricing = pricing_decision.to_dict()

            self.price_records[item] = {
                "current_price": pricing["final_price"],
                "sale_access": pricing["sale_access"],
                "anchor_price": pricing["anchor_price"],
            }

        commerce_packet = {
            "service": commerce_decision,
            "price": pricing,
        }

        reintegration = self.api.reintegration.evaluate(
            served_punishment=self.served_punishment,
            current_trust=float(
                relationship.get("trust", 0.0)
            ),
            arrest_count=self.arrest_count,
            resistance_remaining=self.resistance_remaining,
        ).to_dict()

        quest_packet = self._quest_packet(relationship)
        win_fail = self._win_fail_packet(
            relationship,
            law_decision,
        )

        packet = {
            "scenario_id": self.config["scenario_id"],
            "action": {
                "type": action_type,
                "target": target_id,
                "intensity": intensity,
                "item": item,
            },
            "relationship": relationship,
            "propagation": social_packet,
            "world_effects": {
                "applied": world_effects,
                "state": self.api.world_state(),
            },
            "commerce": commerce_packet,
            "law": law_decision,
            "quest": quest_packet,
            "reintegration": reintegration,
            "win_fail": win_fail,
            "snapshot": self.api.snapshot(),
        }

        json.dumps(packet, sort_keys=True)

        return deepcopy(packet)
