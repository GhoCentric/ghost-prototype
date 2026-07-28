"""
Deterministic strategic-objective packets for Ghost v1.8.0.

Ghost owns the objective contract and derives tactical horizon facts.
A caller supplies concrete world state and legal actions separately.
An external policy may propose a tactic, but Ghost remains authoritative
for validation, mutation, consequences, terminal state, and victory.
"""

from __future__ import annotations

import math
from typing import Any


COMBAT_OBJECTIVE_SCHEMA_VERSION = "1.0"


COMBAT_OBJECTIVE_PRIORITIES = (
    "Take credible finishing opportunities.",
    "Avoid unnecessary exposure.",
    "Preserve the ability to continue fighting.",
    "Adapt to demonstrated behavior, not imagined behavior.",
    (
        "Gather information only when it improves future "
        "success probability."
    ),
)


def _objective_text(
    value: Any,
    label: str,
) -> str:
    if not isinstance(value, str):
        raise ValueError(
            f"{label} must be a non-empty string"
        )

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{label} must be a non-empty string"
        )

    return normalized


def _objective_non_negative_int(
    value: Any,
    label: str,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
    ):
        raise ValueError(
            f"{label} must be a non-negative integer"
        )

    return value


def _objective_positive_int(
    value: Any,
    label: str,
) -> int:
    value = _objective_non_negative_int(
        value,
        label,
    )

    if value <= 0:
        raise ValueError(
            f"{label} must be a positive integer"
        )

    return value


def _objective_health(
    health: Any,
    maximum: Any,
    label: str,
) -> tuple[int, int]:
    health = _objective_non_negative_int(
        health,
        f"{label} health",
    )

    maximum = _objective_positive_int(
        maximum,
        f"{label} max health",
    )

    if health > maximum:
        raise ValueError(
            f"{label} health cannot exceed max health"
        )

    return health, maximum


def _objective_ratio(
    health: int,
    maximum: int,
) -> float:
    return round(
        health / maximum,
        6,
    )


def _objective_health_band(
    health: int,
    maximum: int,
) -> str:
    ratio = health / maximum

    if health <= 0:
        return "defeated"

    if ratio <= 0.25:
        return "critical"

    if ratio <= 0.60:
        return "wounded"

    return "steady"


def _objective_pressure_band(
    *,
    status: str,
    successes_required: int,
    turns_remaining: int,
) -> str:
    if status != "active":
        return "terminal"

    if successes_required <= 1:
        return "immediate_finish"

    if successes_required <= 2:
        return "finishing_window"

    if turns_remaining <= successes_required:
        return "deadline_critical"

    if turns_remaining <= successes_required + 2:
        return "deadline_urgent"

    return "active"


def build_combat_objective_packet(
    *,
    actor: str,
    target: str,
    actor_health: int,
    actor_max_health: int,
    target_health: int,
    target_max_health: int,
    turns_remaining: int,
    expected_damage_per_success: int,
    deadline_label: str = "the deadline",
) -> dict:
    """
    Build one strict, JSON-safe, read-only combat objective packet.

    The packet defines the fight-level purpose and continuation horizon.
    It does not select a tactic and does not resolve any consequence.
    """
    actor = _objective_text(
        actor,
        "combat objective actor",
    )

    target = _objective_text(
        target,
        "combat objective target",
    )

    if actor == target:
        raise ValueError(
            "combat objective actor and target must differ"
        )

    deadline_label = _objective_text(
        deadline_label,
        "combat objective deadline label",
    )

    actor_health, actor_max_health = (
        _objective_health(
            actor_health,
            actor_max_health,
            "combat objective actor",
        )
    )

    target_health, target_max_health = (
        _objective_health(
            target_health,
            target_max_health,
            "combat objective target",
        )
    )

    turns_remaining = (
        _objective_non_negative_int(
            turns_remaining,
            "combat objective turns remaining",
        )
    )

    expected_damage_per_success = (
        _objective_positive_int(
            expected_damage_per_success,
            (
                "combat objective expected damage "
                "per success"
            ),
        )
    )

    if target_health <= 0:
        status = "complete"
    elif actor_health <= 0 or turns_remaining <= 0:
        status = "failed"
    else:
        status = "active"

    successes_required = (
        0
        if target_health <= 0
        else math.ceil(
            target_health
            / expected_damage_per_success
        )
    )

    pressure_band = (
        _objective_pressure_band(
            status=status,
            successes_required=(
                successes_required
            ),
            turns_remaining=turns_remaining,
        )
    )

    return {
        "schema_version": (
            COMBAT_OBJECTIVE_SCHEMA_VERSION
        ),
        "kind": "combat_objective",
        "state_owner": "Ghost",
        "outcome_authority": "Ghost",
        "policy_role": "proposal_only",
        "actor": actor,
        "target": target,
        "status": status,
        "primary_goal": (
            f"Defeat {target} before {deadline_label}."
        ),
        "success_condition": (
            f"{target} reaches zero health before "
            f"{deadline_label}."
        ),
        "failure_conditions": [
            f"{actor} reaches zero health.",
            (
                f"{deadline_label} is reached before "
                f"{target} is defeated."
            ),
        ],
        "continuation_rule": (
            "Unless Ghost resolves a terminal state, "
            f"{target} receives another action after "
            "this exchange."
        ),
        "optimization_rule": (
            "Choose legal tactics that maximize the "
            "chance of completing the primary goal "
            "across the current and future exchanges."
        ),
        "exploration_rule": (
            "Do not spend an exchange on variety, "
            "testing, or information gathering unless "
            "it improves future success probability."
        ),
        "priorities": list(
            COMBAT_OBJECTIVE_PRIORITIES
        ),
        "tactical_state": {
            "actor_health": actor_health,
            "actor_max_health": (
                actor_max_health
            ),
            "actor_health_ratio": (
                _objective_ratio(
                    actor_health,
                    actor_max_health,
                )
            ),
            "actor_health_band": (
                _objective_health_band(
                    actor_health,
                    actor_max_health,
                )
            ),
            "target_health": target_health,
            "target_max_health": (
                target_max_health
            ),
            "target_health_ratio": (
                _objective_ratio(
                    target_health,
                    target_max_health,
                )
            ),
            "target_health_band": (
                _objective_health_band(
                    target_health,
                    target_max_health,
                )
            ),
            "turns_remaining": (
                turns_remaining
            ),
            "deadline_label": (
                deadline_label
            ),
            "expected_damage_per_success": (
                expected_damage_per_success
            ),
            "successful_exchanges_to_defeat_target": (
                successes_required
            ),
            "current_exchange_can_standard_finish": (
                status == "active"
                and successes_required == 1
            ),
            "future_exchange_required_for_standard_finish": (
                status == "active"
                and successes_required > 1
            ),
            "target_acts_again_if_exchange_nonterminal": (
                status == "active"
                and turns_remaining > 1
            ),
            "finishing_opportunity": (
                status == "active"
                and 0 < successes_required <= 2
            ),
            "deadline_supports_standard_finish": (
                status == "active"
                and turns_remaining
                >= successes_required
            ),
            "pressure_band": pressure_band,
        },
    }
