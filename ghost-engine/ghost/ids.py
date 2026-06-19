"""
Public ID validation helpers for Ghost.

Ghost accepts simple public IDs such as "player" and "shopkeeper".
This module keeps those IDs safe for internal relationship keys.
"""

from typing import Any


ID_DELIMITER = "|"


def normalize_id(value: Any, field_name: str = "id") -> str:
    """
    Normalize a public Ghost ID into a safe internal string.

    Rules:
    - None is rejected.
    - non-string values are accepted only if str(value) succeeds.
    - surrounding whitespace is stripped.
    - empty / whitespace-only IDs are rejected.
    - IDs containing "|" are rejected because relationship keys use it.
    """
    if value is None:
        raise ValueError(f"{field_name} cannot be None")

    try:
        text = str(value)
    except Exception as exc:
        raise ValueError(f"{field_name} must be safely stringable") from exc

    text = text.strip()

    if not text:
        raise ValueError(f"{field_name} cannot be empty")

    if ID_DELIMITER in text:
        raise ValueError(
            f"{field_name} cannot contain '{ID_DELIMITER}'"
        )

    return text


def normalize_pair_ids(a: Any, b: Any) -> tuple[str, str]:
    return (
        normalize_id(a, "actor id"),
        normalize_id(b, "target id"),
    )
