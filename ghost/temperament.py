from __future__ import annotations

"""
NPC temperament interpretation layer for Ghost v1.7.0.

This layer does not mutate relationships.
It does not choose actions.
It does not generate dialogue.

It consumes existing Ghost relationship packets and diagnostics,
then returns deterministic JSON-safe interpretation metadata.
"""

from dataclasses import asdict, dataclass
from typing import Any

from .events import normalize_temperament
from .validation import validate_finite_number


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


TEMPERAMENT_NUMERIC_FIELDS = {
    "anxiety",
    "confidence",
    "suspicion",
    "forgiveness",
    "aggression",
    "loyalty",
    "attachment_bias",
    "threat_sensitivity",
    "social_sensitivity",
    "pressure_sensitivity",
    "authority_sensitivity",
    "betrayal_sensitivity",
    "recovery_bias",
}


def _validate_temperament_profile(profile: TemperamentProfile) -> TemperamentProfile:
    data = profile.to_dict()

    for field_name in TEMPERAMENT_NUMERIC_FIELDS:
        data[field_name] = validate_finite_number(
            data.get(field_name),
            f"temperament {field_name}",
        )

    data["name"] = str(data.get("name", "custom"))

    return TemperamentProfile(**data)


@dataclass(frozen=True)
class TemperamentProfile:
    name: str

    anxiety: float = 0.3
    confidence: float = 0.5
    suspicion: float = 0.3
    forgiveness: float = 0.5
    aggression: float = 0.3
    loyalty: float = 0.3

    attachment_bias: float = 0.3
    threat_sensitivity: float = 1.0
    social_sensitivity: float = 1.0
    pressure_sensitivity: float = 1.0
    authority_sensitivity: float = 1.0
    betrayal_sensitivity: float = 1.0
    recovery_bias: float = 0.5

    def to_dict(self) -> dict:
        return asdict(self)


TEMPERAMENT_PRESETS = {
    "calm": TemperamentProfile(
        name="calm",
        anxiety=0.15,
        confidence=0.75,
        suspicion=0.20,
        forgiveness=0.65,
        aggression=0.20,
        loyalty=0.45,
        attachment_bias=0.45,
        threat_sensitivity=0.75,
        social_sensitivity=0.80,
        pressure_sensitivity=0.80,
        authority_sensitivity=0.75,
        betrayal_sensitivity=0.85,
        recovery_bias=0.70,
    ),
    "anxious": TemperamentProfile(
        name="anxious",
        anxiety=0.90,
        confidence=0.25,
        suspicion=0.65,
        forgiveness=0.45,
        aggression=0.20,
        loyalty=0.35,
        attachment_bias=0.35,
        threat_sensitivity=1.45,
        social_sensitivity=1.25,
        pressure_sensitivity=1.35,
        authority_sensitivity=1.10,
        betrayal_sensitivity=1.20,
        recovery_bias=0.40,
    ),
    "confident": TemperamentProfile(
        name="confident",
        anxiety=0.15,
        confidence=0.92,
        suspicion=0.35,
        forgiveness=0.45,
        aggression=0.55,
        loyalty=0.40,
        attachment_bias=0.35,
        threat_sensitivity=0.70,
        social_sensitivity=0.90,
        pressure_sensitivity=0.90,
        authority_sensitivity=0.95,
        betrayal_sensitivity=1.00,
        recovery_bias=0.50,
    ),
    "suspicious": TemperamentProfile(
        name="suspicious",
        anxiety=0.45,
        confidence=0.45,
        suspicion=0.90,
        forgiveness=0.25,
        aggression=0.35,
        loyalty=0.25,
        attachment_bias=0.25,
        threat_sensitivity=1.15,
        social_sensitivity=1.35,
        pressure_sensitivity=1.20,
        authority_sensitivity=1.25,
        betrayal_sensitivity=1.30,
        recovery_bias=0.25,
    ),
    "resentful": TemperamentProfile(
        name="resentful",
        anxiety=0.30,
        confidence=0.55,
        suspicion=0.70,
        forgiveness=0.15,
        aggression=0.75,
        loyalty=0.20,
        attachment_bias=0.20,
        threat_sensitivity=1.10,
        social_sensitivity=1.15,
        pressure_sensitivity=1.20,
        authority_sensitivity=0.90,
        betrayal_sensitivity=1.55,
        recovery_bias=0.15,
    ),
    "loyal": TemperamentProfile(
        name="loyal",
        anxiety=0.25,
        confidence=0.65,
        suspicion=0.25,
        forgiveness=0.75,
        aggression=0.35,
        loyalty=0.90,
        attachment_bias=0.85,
        threat_sensitivity=0.90,
        social_sensitivity=1.05,
        pressure_sensitivity=0.95,
        authority_sensitivity=1.00,
        betrayal_sensitivity=1.10,
        recovery_bias=0.75,
    ),
    "volatile": TemperamentProfile(
        name="volatile",
        anxiety=0.65,
        confidence=0.55,
        suspicion=0.65,
        forgiveness=0.25,
        aggression=0.80,
        loyalty=0.40,
        attachment_bias=0.50,
        threat_sensitivity=1.35,
        social_sensitivity=1.30,
        pressure_sensitivity=1.45,
        authority_sensitivity=0.90,
        betrayal_sensitivity=1.60,
        recovery_bias=0.25,
    ),
}


def get_temperament_profile(profile: str | dict | TemperamentProfile) -> TemperamentProfile:
    if isinstance(profile, TemperamentProfile):
        return _validate_temperament_profile(profile)

    if isinstance(profile, dict):
        data = dict(profile)
        data.setdefault("name", "custom")
        return _validate_temperament_profile(TemperamentProfile(**data))

    key = normalize_temperament(profile or "calm")

    if key not in TEMPERAMENT_PRESETS:
        raise ValueError(f"Unknown temperament: {profile}")

    return _validate_temperament_profile(TEMPERAMENT_PRESETS[key])


def _pressure_boost(pressure: str) -> float:
    if pressure == "relationship_broken":
        return 1.00

    if pressure == "near_break":
        return 0.85

    if pressure == "major_negative_shift":
        return 0.75

    if pressure == "negative_shift":
        return 0.55

    if pressure == "state_shift":
        return 0.45

    if pressure == "minor_negative_shift":
        return 0.35

    if pressure == "forgiveness":
        return 0.20

    if pressure == "deescalating":
        return 0.15

    return 0.10


def _dominant_read(
    *,
    fear: float,
    suspicion: float,
    anger: float,
    relief: float,
    trust: float,
    state: str,
) -> str:
    if relief >= 0.55 and trust >= 0.08:
        return "reassured"

    if anger >= fear and anger >= suspicion and anger >= 0.55:
        return "angry"

    if fear >= suspicion and fear >= 0.55:
        return "anxious"

    if suspicion >= 0.50:
        return "suspicious"

    if state == "hostile":
        return "hostile"

    if state == "friendly":
        return "warm"

    return "calm"


def _stance(
    *,
    emotional_read: str,
    confidence: float,
    fear: float,
    anger: float,
    suspicion: float,
    state: str,
    near_break: bool,
) -> str:
    if near_break:
        return "guarded"

    if emotional_read == "angry" and confidence >= 0.55:
        return "confrontational"

    if emotional_read == "angry":
        return "cold"

    if emotional_read == "anxious" and confidence <= 0.40:
        return "avoidant"

    if suspicion >= 0.55:
        return "guarded"

    if state == "hostile":
        return "hostile"

    if state == "friendly" and confidence >= 0.50:
        return "open"

    if fear >= 0.50:
        return "cautious"

    return "neutral"


def interpret_relationship(
    *,
    npc: str,
    relationship: dict[str, Any],
    temperament: str | dict | TemperamentProfile = "calm",
) -> dict:
    """
    Interpret an existing Ghost relationship packet through an NPC temperament.

    This function is deterministic and read-only.
    It returns plain JSON-safe dictionaries.
    """
    profile = get_temperament_profile(temperament)

    diagnostics = relationship.get("diagnostics", {}) or {}

    trust = validate_finite_number(
        relationship.get("trust", 0.0),
        "relationship trust",
    )
    state = str(relationship.get("state", "neutral"))

    pressure = str(diagnostics.get("pressure", "stable"))
    direction = str(diagnostics.get("direction", "stable"))
    event = str(diagnostics.get("event", relationship.get("last_event", "")))

    severity = clamp(
        validate_finite_number(
            diagnostics.get("severity", 0.0),
            "relationship severity",
        )
    )
    delta = validate_finite_number(
        diagnostics.get("delta", 0.0),
        "relationship delta",
    )
    near_break = bool(diagnostics.get("near_break", False))

    pressure_weight = _pressure_boost(pressure)

    negative_signal = severity

    if direction != "negative":
        negative_signal *= 0.40

    if state == "hostile":
        negative_signal += 0.25

    if near_break:
        negative_signal += 0.20

    betrayal_bonus = 0.20 if event == "betrayal" else 0.0
    threat_bonus = 0.15 if event in ("threat", "attack") else 0.0

    fear = clamp(
        (
            negative_signal * 0.55
            + pressure_weight * 0.20
            + threat_bonus
        )
        * profile.anxiety
        * profile.threat_sensitivity
        * profile.pressure_sensitivity
    )

    suspicion = clamp(
        (
            negative_signal * 0.45
            + pressure_weight * 0.25
            + betrayal_bonus
        )
        * profile.suspicion
        * profile.social_sensitivity
    )

    anger = clamp(
        (
            negative_signal * 0.55
            + betrayal_bonus
            + pressure_weight * 0.15
        )
        * profile.aggression
        * profile.betrayal_sensitivity
        * (1.15 - (profile.forgiveness * 0.35))
    )

    relief = 0.0

    if direction == "positive":
        relief = clamp(
            (
                severity * 0.60
                + max(trust, 0.0) * 0.25
            )
            * profile.forgiveness
            * profile.recovery_bias
        )

    confidence = clamp(
        profile.confidence
        - (fear * 0.35)
        + (anger * 0.10)
    )

    loyalty = clamp(
        profile.loyalty
        + (max(trust, 0.0) * profile.attachment_bias)
        - (suspicion * 0.20)
    )

    intensity = clamp(
        max(
            fear,
            suspicion,
            anger,
            relief,
            abs(delta),
            severity,
        )
        * profile.pressure_sensitivity
    )

    emotional_read = _dominant_read(
        fear=fear,
        suspicion=suspicion,
        anger=anger,
        relief=relief,
        trust=trust,
        state=state,
    )

    stance = _stance(
        emotional_read=emotional_read,
        confidence=confidence,
        fear=fear,
        anger=anger,
        suspicion=suspicion,
        state=state,
        near_break=near_break,
    )

    return {
        "npc": str(npc),
        "temperament": profile.name,
        "relationship_state": state,
        "trust": round(trust, 6),
        "pressure": pressure,
        "near_break": near_break,
        "source_event": event,
        "interpretation": {
            "emotional_read": emotional_read,
            "stance": stance,
            "fear": round(fear, 6),
            "suspicion": round(suspicion, 6),
            "anger": round(anger, 6),
            "confidence": round(confidence, 6),
            "loyalty": round(loyalty, 6),
            "relief": round(relief, 6),
            "intensity": round(intensity, 6),
        },
    }


def interpret_social_packet(
    *,
    npc: str,
    packet: dict[str, Any],
    temperament: str | dict | TemperamentProfile = "calm",
) -> dict:
    """
    Interpret a v1.6.0 social propagation packet for one observer.

    This does not mutate the packet.
    """
    for item in packet.get("propagated", []):
        if item.get("affected") == npc:
            return interpret_relationship(
                npc=npc,
                relationship=item.get("relationship", {}),
                temperament=temperament,
            )

    raise ValueError(f"NPC not found in social packet: {npc}")
