"""Read-only bridge from persistent Ghost state into attention salience.

The bridge is deliberately stateless. It reads copied emotional and/or
interpretation packets, derives a namespaced salience vector, and returns a
JSON-safe packet that can be handed to ``AttentionRuntime``. It never owns,
mutates, decays, reconstructs, or snapshots the source state.

Namespacing keeps source semantics explicit::

    emotion:anger
    interpretation:betrayal

This prevents collisions when different persistent subsystems use the same
channel name. The bridge also records source revisions from each packet's most
recent history sequence so downstream diagnostics can identify exactly which
copied source view was consumed.
"""

from __future__ import annotations

from copy import deepcopy
import math

from .ids import normalize_id


SALIENCE_BRIDGE_PACKET_VERSION = "1.0"
EMOTION_PREFIX = "emotion:"
INTERPRETATION_PREFIX = "interpretation:"


def _token(value, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _finite(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return value


def _unit(value, label: str) -> float:
    value = _finite(value, label)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{label} must be in [0, 1]")
    return value


def _non_negative(value, label: str) -> float:
    value = _finite(value, label)
    if value < 0.0:
        raise ValueError(f"{label} must be non-negative")
    return value


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))


def _validate_flag(value, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a bool")
    return value


def _validate_state_agent(packet: dict, agent: str, label: str) -> None:
    if "agent" not in packet:
        raise ValueError(f"{label} state is missing agent")
    source_agent = normalize_id(packet["agent"], f"{label} state agent")
    if source_agent != agent:
        raise ValueError(
            f"{label} state agent mismatch: expected {agent!r}, got {source_agent!r}"
        )


def _validated_levels(value, label: str) -> dict[str, float]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a dict")
    out: dict[str, float] = {}
    for raw_name, raw_value in value.items():
        name = _token(raw_name, f"{label} name")
        if name in out:
            raise ValueError(f"{label} contains duplicate normalized name: {name}")
        out[name] = _unit(raw_value, f"{label}.{name}")
    return out


def _validated_biases(value, levels: dict[str, float]) -> dict[str, float]:
    if not isinstance(value, dict):
        raise ValueError("emotion salience_bias must be a dict")
    out: dict[str, float] = {}
    for raw_name, raw_value in value.items():
        name = _token(raw_name, "emotion salience_bias name")
        if name in out:
            raise ValueError(
                f"emotion salience_bias contains duplicate normalized name: {name}"
            )
        out[name] = _non_negative(
            raw_value,
            f"emotion salience_bias.{name}",
        )
    if set(out) != set(levels):
        raise ValueError("emotion levels and salience_bias dimensions must match")
    return out


def _history_revision(packet: dict, label: str) -> int:
    history = packet.get("history", [])
    if not isinstance(history, list):
        raise ValueError(f"{label} state history must be a list")
    if not history:
        return 0
    previous = 0
    for index, record in enumerate(history):
        if not isinstance(record, dict):
            raise ValueError(f"{label} state history[{index}] must be a dict")
        sequence = record.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= previous:
            raise ValueError(f"{label} state history[{index}].sequence is invalid")
        previous = sequence
    return previous


def _emotion_source(agent: str, packet: dict | None) -> tuple[dict, dict[str, float]]:
    if packet is None:
        return (
            {
                "present": False,
                "revision": None,
                "dimensions": [],
            },
            {},
        )
    if not isinstance(packet, dict):
        raise ValueError("emotion state must be a dict or None")
    _validate_state_agent(packet, agent, "emotion")
    if "levels" not in packet:
        raise ValueError("emotion state is missing levels")
    if "salience_bias" not in packet:
        raise ValueError("emotion state is missing salience_bias")
    levels = _validated_levels(packet["levels"], "emotion levels")
    biases = _validated_biases(packet["salience_bias"], levels)
    salience = {
        EMOTION_PREFIX + name: _clamp01(levels[name] * biases[name])
        for name in sorted(levels)
    }
    return (
        {
            "present": True,
            "revision": _history_revision(packet, "emotion"),
            "dimensions": sorted(salience),
        },
        salience,
    )


def _interpretation_source(
    agent: str,
    packet: dict | None,
) -> tuple[dict, dict[str, float]]:
    if packet is None:
        return (
            {
                "present": False,
                "revision": None,
                "dimensions": [],
            },
            {},
        )
    if not isinstance(packet, dict):
        raise ValueError("interpretation state must be a dict or None")
    _validate_state_agent(packet, agent, "interpretation")
    if "levels" not in packet:
        raise ValueError("interpretation state is missing levels")
    levels = _validated_levels(packet["levels"], "interpretation levels")
    salience = {
        INTERPRETATION_PREFIX + name: levels[name]
        for name in sorted(levels)
    }
    return (
        {
            "present": True,
            "revision": _history_revision(packet, "interpretation"),
            "dimensions": sorted(salience),
        },
        salience,
    )


def build_salience_bridge(
    agent: str,
    *,
    emotion_state: dict | None = None,
    interpretation_state: dict | None = None,
    include_emotions: bool = True,
    include_interpretations: bool = True,
) -> dict:
    """Build one copied, deterministic, read-only salience packet.

    ``include_emotions`` and ``include_interpretations`` control which copied
    state packets are consumed. A disabled source is treated as absent even if a
    packet was supplied. Missing enabled sources are represented explicitly and
    produce no salience dimensions.
    """

    agent = normalize_id(agent, "salience bridge agent")
    include_emotions = _validate_flag(include_emotions, "include_emotions")
    include_interpretations = _validate_flag(
        include_interpretations,
        "include_interpretations",
    )

    emotion_packet = deepcopy(emotion_state) if include_emotions else None
    interpretation_packet = (
        deepcopy(interpretation_state) if include_interpretations else None
    )

    emotion_meta, emotion_salience = _emotion_source(agent, emotion_packet)
    interpretation_meta, interpretation_salience = _interpretation_source(
        agent,
        interpretation_packet,
    )

    salience: dict[str, float] = {}
    salience.update(emotion_salience)
    salience.update(interpretation_salience)

    sources = {
        "emotion": emotion_meta,
        "interpretation": interpretation_meta,
    }
    source_count = sum(1 for value in sources.values() if value["present"])

    return {
        "packet_version": SALIENCE_BRIDGE_PACKET_VERSION,
        "agent": agent,
        "source_count": source_count,
        "sources": deepcopy(sources),
        "salience": deepcopy(salience),
    }
