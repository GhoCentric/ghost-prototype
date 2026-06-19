"""
Validation helpers for Ghost public boundaries.

These helpers keep public packets deterministic and strict-JSON-safe.
"""

import math
from typing import Any


def validate_finite_number(value: Any, field_name: str = "value") -> float:
    """Return value as float only if it is finite."""
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a finite number")

    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a finite number") from exc

    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite")

    return number


def validate_non_negative_finite(
    value: Any,
    field_name: str = "value",
) -> float:
    """Return value as float only if finite and >= 0."""
    number = validate_finite_number(value, field_name)

    if number < 0.0:
        raise ValueError(f"{field_name} must be non-negative")

    return number


def validate_positive_finite(
    value: Any,
    field_name: str = "value",
) -> float:
    """Return value as float only if finite and > 0."""
    number = validate_finite_number(value, field_name)

    if number <= 0.0:
        raise ValueError(f"{field_name} must be positive")

    return number


def validate_unit_interval(
    value: Any,
    field_name: str = "value",
) -> float:
    """Return value as float only if finite and in [0, 1]."""
    number = validate_finite_number(value, field_name)

    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0")

    return number
