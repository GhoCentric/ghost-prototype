"""Decision-table contracts for Ghost temperament interpretation."""

from __future__ import annotations

import pytest

from ghost.temperament import (
    TemperamentProfile,
    _dominant_read,
    _pressure_boost,
    _stance,
    get_temperament_profile,
)


def test_profile_instance_is_validated_at_public_entry():
    profile = TemperamentProfile(
        name="manual_profile",
        anxiety=0.70,
        confidence=0.40,
    )

    resolved = get_temperament_profile(profile)

    assert resolved.to_dict() == profile.to_dict()


@pytest.mark.parametrize(
    "invalid_anxiety",
    [
        True,
        float("nan"),
        float("inf"),
    ],
)
def test_profile_instance_rejects_invalid_numeric_fields(
    invalid_anxiety,
):
    profile = TemperamentProfile(
        name="invalid_profile",
        anxiety=invalid_anxiety,
    )

    with pytest.raises(
        ValueError,
        match="temperament anxiety",
    ):
        get_temperament_profile(profile)


@pytest.mark.parametrize(
    ("pressure", "expected"),
    [
        ("relationship_broken", 1.00),
        ("near_break", 0.85),
        ("major_negative_shift", 0.75),
        ("negative_shift", 0.55),
        ("state_shift", 0.45),
        ("minor_negative_shift", 0.35),
        ("forgiveness", 0.20),
        ("deescalating", 0.15),
        ("unknown_pressure", 0.10),
    ],
)
def test_pressure_boost_decision_table(
    pressure,
    expected,
):
    assert _pressure_boost(pressure) == expected


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (
            {
                "fear": 0.90,
                "suspicion": 0.90,
                "anger": 0.90,
                "relief": 0.55,
                "trust": 0.08,
                "state": "hostile",
            },
            "reassured",
        ),
        (
            {
                "fear": 0.40,
                "suspicion": 0.40,
                "anger": 0.55,
                "relief": 0.00,
                "trust": 0.00,
                "state": "neutral",
            },
            "angry",
        ),
        (
            {
                "fear": 0.55,
                "suspicion": 0.55,
                "anger": 0.10,
                "relief": 0.00,
                "trust": 0.00,
                "state": "neutral",
            },
            "anxious",
        ),
        (
            {
                "fear": 0.20,
                "suspicion": 0.50,
                "anger": 0.20,
                "relief": 0.00,
                "trust": 0.00,
                "state": "neutral",
            },
            "suspicious",
        ),
        (
            {
                "fear": 0.20,
                "suspicion": 0.20,
                "anger": 0.20,
                "relief": 0.00,
                "trust": 0.00,
                "state": "hostile",
            },
            "hostile",
        ),
        (
            {
                "fear": 0.20,
                "suspicion": 0.20,
                "anger": 0.20,
                "relief": 0.00,
                "trust": -0.20,
                "state": "neutral",
            },
            "wary",
        ),
        (
            {
                "fear": 0.20,
                "suspicion": 0.20,
                "anger": 0.20,
                "relief": 0.00,
                "trust": 0.20,
                "state": "friendly",
            },
            "warm",
        ),
        (
            {
                "fear": 0.20,
                "suspicion": 0.20,
                "anger": 0.20,
                "relief": 0.00,
                "trust": 0.00,
                "state": "neutral",
            },
            "calm",
        ),
    ],
)
def test_dominant_read_priority_table(
    values,
    expected,
):
    assert _dominant_read(**values) == expected


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (
            {
                "emotional_read": "angry",
                "confidence": 1.00,
                "fear": 1.00,
                "anger": 1.00,
                "suspicion": 1.00,
                "state": "hostile",
                "near_break": True,
            },
            "guarded",
        ),
        (
            {
                "emotional_read": "angry",
                "confidence": 0.55,
                "fear": 0.10,
                "anger": 0.80,
                "suspicion": 0.10,
                "state": "neutral",
                "near_break": False,
            },
            "confrontational",
        ),
        (
            {
                "emotional_read": "angry",
                "confidence": 0.54,
                "fear": 0.10,
                "anger": 0.80,
                "suspicion": 0.10,
                "state": "neutral",
                "near_break": False,
            },
            "cold",
        ),
        (
            {
                "emotional_read": "anxious",
                "confidence": 0.40,
                "fear": 0.70,
                "anger": 0.10,
                "suspicion": 0.10,
                "state": "neutral",
                "near_break": False,
            },
            "avoidant",
        ),
        (
            {
                "emotional_read": "wary",
                "confidence": 0.50,
                "fear": 0.10,
                "anger": 0.10,
                "suspicion": 0.10,
                "state": "neutral",
                "near_break": False,
            },
            "reserved",
        ),
        (
            {
                "emotional_read": "calm",
                "confidence": 0.50,
                "fear": 0.10,
                "anger": 0.10,
                "suspicion": 0.55,
                "state": "neutral",
                "near_break": False,
            },
            "guarded",
        ),
        (
            {
                "emotional_read": "calm",
                "confidence": 0.50,
                "fear": 0.10,
                "anger": 0.10,
                "suspicion": 0.10,
                "state": "hostile",
                "near_break": False,
            },
            "hostile",
        ),
        (
            {
                "emotional_read": "calm",
                "confidence": 0.50,
                "fear": 0.10,
                "anger": 0.10,
                "suspicion": 0.10,
                "state": "friendly",
                "near_break": False,
            },
            "open",
        ),
        (
            {
                "emotional_read": "calm",
                "confidence": 0.49,
                "fear": 0.50,
                "anger": 0.10,
                "suspicion": 0.10,
                "state": "neutral",
                "near_break": False,
            },
            "cautious",
        ),
        (
            {
                "emotional_read": "calm",
                "confidence": 0.49,
                "fear": 0.10,
                "anger": 0.10,
                "suspicion": 0.10,
                "state": "neutral",
                "near_break": False,
            },
            "neutral",
        ),
    ],
)
def test_stance_priority_table(
    values,
    expected,
):
    assert _stance(**values) == expected
