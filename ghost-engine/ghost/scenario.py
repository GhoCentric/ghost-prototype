"""
Scenario configuration validation for Ghost v1.8+.

This module validates deterministic game/demo configuration without
storing scenario runtime state inside the relationship core.
"""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

from .validation import (
    validate_finite_number,
    validate_positive_finite,
    validate_unit_interval,
)


def _require_dict(
    value: Any,
    field_name: str,
) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dict")

    return value


def _require_list(
    value: Any,
    field_name: str,
) -> list:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")

    return value


def _require_nonempty_string(
    value: Any,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")

    normalized = value.strip()

    if not normalized:
        raise ValueError(f"{field_name} must not be empty")

    return normalized


def _validate_temperament(
    value: Any,
    field_name: str,
) -> str | dict:
    if isinstance(value, str):
        return _require_nonempty_string(value, field_name)

    if isinstance(value, dict):
        if not value:
            raise ValueError(
                f"{field_name} vector must not be empty"
            )

        normalized = {}

        for key, raw_value in value.items():
            name = _require_nonempty_string(
                key,
                f"{field_name} vector key",
            )

            normalized[name] = validate_unit_interval(
                raw_value,
                f"{field_name}.{name}",
            )

        return normalized

    raise ValueError(
        f"{field_name} must be a preset string or vector dict"
    )


def _validate_conditions(
    value: Any,
    field_name: str,
) -> list[str]:
    conditions = _require_list(value, field_name)

    if not conditions:
        raise ValueError(
            f"{field_name} must contain at least one condition"
        )

    normalized = []

    for index, condition in enumerate(conditions):
        normalized.append(
            _require_nonempty_string(
                condition,
                f"{field_name}[{index}]",
            )
        )

    if len(set(normalized)) != len(normalized):
        raise ValueError(
            f"{field_name} must not contain duplicates"
        )

    return normalized


def validate_scenario_config(config: dict) -> dict:
    """
    Validate and normalize a JSON-safe Ghost scenario configuration.

    The returned config is copied, normalized, and contains no
    caller-owned mutable references.
    """
    config = _require_dict(config, "scenario config")

    scenario_id = _require_nonempty_string(
        config.get("scenario_id"),
        "scenario_id",
    )

    npc_roles = _require_dict(
        config.get("npc_roles"),
        "npc_roles",
    )

    if not npc_roles:
        raise ValueError(
            "npc_roles must contain at least one role"
        )

    normalized_roles = {}
    assigned_npc_ids = set()

    for raw_role, raw_npc_id in npc_roles.items():
        role = _require_nonempty_string(
            raw_role,
            "npc_roles role",
        )
        npc_id = _require_nonempty_string(
            raw_npc_id,
            f"npc_roles.{role}",
        )

        if npc_id in assigned_npc_ids:
            raise ValueError(
                "npc_roles must not assign one NPC to multiple roles"
            )

        normalized_roles[role] = npc_id
        assigned_npc_ids.add(npc_id)

    npcs = _require_dict(
        config.get("npcs"),
        "npcs",
    )

    normalized_npcs = {}

    for npc_id in assigned_npc_ids:
        if npc_id not in npcs:
            raise ValueError(
                f"npcs is missing role NPC: {npc_id}"
            )

    for raw_npc_id, profile in npcs.items():
        npc_id = _require_nonempty_string(
            raw_npc_id,
            "npcs key",
        )
        profile = _require_dict(
            profile,
            f"npcs.{npc_id}",
        )

        temperament = _validate_temperament(
            profile.get("temperament"),
            f"npcs.{npc_id}.temperament",
        )

        personality = profile.get("personality", "balanced")

        if not isinstance(personality, str):
            raise ValueError(
                f"npcs.{npc_id}.personality must be a string"
            )

        normalized_npcs[npc_id] = {
            "temperament": temperament,
            "personality": personality.strip() or "balanced",
        }

    relationships = _require_list(
        config.get("relationships", []),
        "relationships",
    )

    normalized_relationships = []

    for index, relationship in enumerate(relationships):
        relationship = _require_dict(
            relationship,
            f"relationships[{index}]",
        )

        source = _require_nonempty_string(
            relationship.get("source"),
            f"relationships[{index}].source",
        )
        target = _require_nonempty_string(
            relationship.get("target"),
            f"relationships[{index}].target",
        )

        if source == target:
            raise ValueError(
                f"relationships[{index}] cannot target itself"
            )

        if source not in normalized_npcs:
            raise ValueError(
                f"relationships[{index}] source is unknown: {source}"
            )

        if target not in normalized_npcs:
            raise ValueError(
                f"relationships[{index}] target is unknown: {target}"
            )

        trust = validate_finite_number(
            relationship.get("trust", 0.0),
            f"relationships[{index}].trust",
        )

        if not -1.0 <= trust <= 1.0:
            raise ValueError(
                f"relationships[{index}].trust must be in [-1.0, 1.0]"
            )

        normalized_relationships.append(
            {
                "source": source,
                "target": target,
                "trust": trust,
            }
        )

    propagation_weights = _require_dict(
        config.get("propagation_weights", {}),
        "propagation_weights",
    )

    normalized_weights = {}

    for raw_npc_id, raw_weight in propagation_weights.items():
        npc_id = _require_nonempty_string(
            raw_npc_id,
            "propagation_weights key",
        )

        if npc_id not in normalized_npcs:
            raise ValueError(
                "propagation_weights references unknown NPC: "
                f"{npc_id}"
            )

        normalized_weights[npc_id] = validate_unit_interval(
            raw_weight,
            f"propagation_weights.{npc_id}",
        )

    economy = _require_dict(
        config.get("economy"),
        "economy",
    )

    base_prices = _require_dict(
        economy.get("base_prices"),
        "economy.base_prices",
    )

    if not base_prices:
        raise ValueError(
            "economy.base_prices must contain at least one item"
        )

    normalized_prices = {}

    for raw_item, raw_price in base_prices.items():
        item = _require_nonempty_string(
            raw_item,
            "economy.base_prices key",
        )

        normalized_prices[item] = validate_positive_finite(
            raw_price,
            f"economy.base_prices.{item}",
        )

    quest = _require_dict(
        config.get("quest"),
        "quest",
    )

    normalized_quest = {
        "trust_required": validate_finite_number(
            quest.get("trust_required"),
            "quest.trust_required",
        ),
        "pressure_max": validate_finite_number(
            quest.get("pressure_max"),
            "quest.pressure_max",
        ),
    }

    if not -1.0 <= normalized_quest["trust_required"] <= 1.0:
        raise ValueError(
            "quest.trust_required must be in [-1.0, 1.0]"
        )

    if not 0.0 <= normalized_quest["pressure_max"] <= 5.0:
        raise ValueError(
            "quest.pressure_max must be in [0.0, 5.0]"
        )

    thresholds = _require_dict(
        config.get("thresholds"),
        "thresholds",
    )

    normalized_thresholds = {
        "pressure_crisis": validate_finite_number(
            thresholds.get("pressure_crisis"),
            "thresholds.pressure_crisis",
        ),
        "pressure_expulsion": validate_finite_number(
            thresholds.get("pressure_expulsion"),
            "thresholds.pressure_expulsion",
        ),
        "arrest_severity": validate_unit_interval(
            thresholds.get("arrest_severity"),
            "thresholds.arrest_severity",
        ),
    }

    for key in [
        "pressure_crisis",
        "pressure_expulsion",
    ]:
        if not 0.0 <= normalized_thresholds[key] <= 5.0:
            raise ValueError(
                f"thresholds.{key} must be in [0.0, 5.0]"
            )

    if (
        normalized_thresholds["pressure_crisis"]
        >= normalized_thresholds["pressure_expulsion"]
    ):
        raise ValueError(
            "thresholds.pressure_crisis must be lower than "
            "thresholds.pressure_expulsion"
        )

    if (
        normalized_quest["pressure_max"]
        >= normalized_thresholds["pressure_expulsion"]
    ):
        raise ValueError(
            "quest.pressure_max must be lower than "
            "thresholds.pressure_expulsion"
        )

    win_conditions = _validate_conditions(
        config.get("win_conditions"),
        "win_conditions",
    )

    fail_conditions = _validate_conditions(
        config.get("fail_conditions"),
        "fail_conditions",
    )

    overlap = set(win_conditions) & set(fail_conditions)

    if overlap:
        raise ValueError(
            "win_conditions and fail_conditions must not overlap: "
            + ", ".join(sorted(overlap))
        )

    normalized = {
        "scenario_id": scenario_id,
        "npc_roles": normalized_roles,
        "npcs": normalized_npcs,
        "relationships": normalized_relationships,
        "propagation_weights": normalized_weights,
        "economy": {
            "base_prices": normalized_prices,
        },
        "quest": normalized_quest,
        "thresholds": normalized_thresholds,
        "win_conditions": win_conditions,
        "fail_conditions": fail_conditions,
    }

    json.dumps(normalized, sort_keys=True)

    return deepcopy(normalized)


def load_scenario_config(config: dict) -> dict:
    """
    Public alias for validate_scenario_config().

    This gives scenario callers a clear load-time entry point.
    """
    return validate_scenario_config(config)
