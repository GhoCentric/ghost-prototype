"""
Deterministic threat-response policy for Ghost v1.8.0.

This module does not mutate Ghost state.
It does not animate NPCs.
It does not create dialogue.

It reads existing Ghost relationship diagnostics, temperament, and
explicit game context, then returns a JSON-safe response recommendation.

A game layer decides how to execute the recommendation.
"""

from __future__ import annotations

import math
from typing import Any

from .temperament import (
    clamp,
    interpret_relationship,
)


RESPONSE_ORDER = (
    "fight",
    "call_guards",
    "confront",
    "surrender",
    "flee",
    "freeze",
    "warn",
    "ignore",
)


def _bool(value: Any) -> bool:
    """
    Normalize common caller values without treating "false" as truthy.
    """
    if isinstance(value, str):
        return value.strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

    return bool(value)


def _count(value: Any) -> int:
    """
    Normalize count-like values to a safe non-negative integer.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0

    if not math.isfinite(number):
        return 0

    return max(0, int(number))


def _unit(value: Any) -> float:
    """
    Normalize a value into a finite 0.0-1.0 range.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0

    if not math.isfinite(number):
        return 0.0

    return clamp(number, 0.0, 1.0)


def _normalize_context(context: dict | None) -> dict:
    """
    Normalize explicit non-Ghost game facts.

    These values are owned by the caller's game/simulation layer.
    Ghost only interprets them alongside persistent social state.
    """
    if not isinstance(context, dict):
        context = {}

    return {
        "player_armed": _bool(context.get("player_armed", False)),
        "player_aiming": _bool(context.get("player_aiming", False)),
        "player_attacking": _bool(context.get("player_attacking", False)),
        "npc_armed": _bool(context.get("npc_armed", False)),
        "escape_route": _bool(context.get("escape_route", True)),
        "guard_nearby": _bool(context.get("guard_nearby", False)),
        "authority_present": _bool(
            context.get("authority_present", False)
        ),
        "allies_nearby": _count(context.get("allies_nearby", 0)),
        "crowd_size": _count(context.get("crowd_size", 0)),
    }


def _threat_signal(context: dict) -> float:
    signal = 0.0

    if context["player_armed"]:
        signal += 0.30

    if context["player_aiming"]:
        signal += 0.55

    if context["player_attacking"]:
        signal += 0.85

    return _unit(signal)


def _choose(scores: dict[str, float]) -> str:
    """
    Deterministic max selection.

    RESPONSE_ORDER provides a stable tie-break rule.
    """
    return max(
        RESPONSE_ORDER,
        key=lambda response: (
            scores[response],
            -RESPONSE_ORDER.index(response),
        ),
    )


def evaluate_threat_response(
    *,
    npc: str,
    relationship: dict,
    temperament="calm",
    context: dict | None = None,
) -> dict:
    """
    Return a deterministic, read-only NPC threat-response recommendation.

    The packet is deliberately advisory:
    - response is what a caller may execute
    - scores explain why it won
    - interpretation exposes the Ghost-derived social state
    - context contains only explicit caller-owned game facts
    """
    interpretation_packet = interpret_relationship(
        npc=npc,
        relationship=relationship,
        temperament=temperament,
    )

    interpretation = interpretation_packet["interpretation"]
    normalized = _normalize_context(context)

    fear = _unit(interpretation["fear"])
    suspicion = _unit(interpretation["suspicion"])
    anger = _unit(interpretation["anger"])
    confidence = _unit(interpretation["confidence"])
    loyalty = _unit(interpretation["loyalty"])
    intensity = _unit(interpretation["intensity"])

    threat = _threat_signal(normalized)
    allies = min(normalized["allies_nearby"], 5) / 5.0
    crowd = min(normalized["crowd_size"], 20) / 20.0

    escape = 1.0 if normalized["escape_route"] else 0.0
    trapped = 1.0 - escape
    npc_armed = 1.0 if normalized["npc_armed"] else 0.0
    guard_nearby = 1.0 if normalized["guard_nearby"] else 0.0
    authority = 1.0 if normalized["authority_present"] else 0.0

    scores = {
        "flee": (
            fear * 1.20
            + threat * 0.85
            + escape * 0.35
            - confidence * 0.30
            - npc_armed * 0.20
            - allies * 0.15
        ),
        "freeze": (
            fear * 1.00
            + threat * 0.50
            + trapped * 0.20
            - confidence * 0.35
            - anger * 0.20
        ),
        "surrender": (
            fear * 0.95
            + threat * 0.75
            + trapped * 0.45
            - anger * 0.45
            - npc_armed * 0.20
        ),
        "warn": (
            confidence * 0.55
            + suspicion * 0.45
            + threat * 0.40
            + guard_nearby * 0.20
            - fear * 0.35
        ),
        "call_guards": (
            guard_nearby * 1.00
            + authority * 0.45
            + suspicion * 0.45
            + threat * 0.55
            + crowd * 0.10
        ),
        "confront": (
            confidence * 0.80
            + anger * 0.85
            + npc_armed * 0.45
            + allies * 0.20
            + threat * 0.25
            - fear * 0.85
        ),
        "fight": (
            confidence * 0.65
            + anger * 1.05
            + npc_armed * 0.85
            + allies * 0.25
            + threat * 0.50
            - fear * 0.70
        ),
        "ignore": (
            confidence * 0.35
            + loyalty * 0.20
            - threat * 1.10
            - fear * 0.55
            - suspicion * 0.25
            - intensity * 0.15
        ),
    }

    scores = {
        name: round(
            max(
                0.0,
                score if math.isfinite(score) else 0.0,
            ),
            6,
        )
        for name, score in scores.items()
    }

    response = _choose(scores)

    reasons = {
        "flee": "fear and escape opportunity outweigh resistance",
        "freeze": "fear overwhelms confidence without a clear response",
        "surrender": "trapped threat pressure favors submission",
        "warn": "confidence permits a boundary response",
        "call_guards": "authority access turns threat into escalation",
        "confront": "anger and confidence support direct resistance",
        "fight": "armed resistance and anger outweigh fear",
        "ignore": "the threat signal is too weak to change behavior",
    }

    return {
        "npc": str(npc),
        "temperament": interpretation_packet["temperament"],
        "response": response,
        "reason": reasons[response],
        "scores": scores,
        "signals": {
            "threat": round(threat, 6),
            "fear": round(fear, 6),
            "suspicion": round(suspicion, 6),
            "anger": round(anger, 6),
            "confidence": round(confidence, 6),
            "loyalty": round(loyalty, 6),
            "intensity": round(intensity, 6),
        },
        "context": normalized,
        "interpretation": interpretation_packet,
    }
