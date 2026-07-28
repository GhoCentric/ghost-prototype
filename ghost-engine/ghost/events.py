"""
Typed public constants for Ghost.

These enums are optional.
Raw strings remain supported for demos, JSON input, configs, and scripts.

The goal is to reduce stringly-typed mistakes without breaking the
simple public API.
"""

from enum import Enum
from typing import Any


class GhostStrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class RelationshipEvent(GhostStrEnum):
    GREET = "greet"
    HELP = "help"
    GIFT = "gift"
    APOLOGIZE = "apologize"
    APOLOGY = "apology"

    INSULT = "insult"
    THREAT = "threat"
    THEFT = "theft"
    ATTACK = "attack"
    BETRAYAL = "betrayal"


class APIEvent(GhostStrEnum):
    NEUTRAL = "neutral"
    GREET = "greet"
    HELP = "help"
    COOPERATE = "cooperate"
    APOLOGY = "apology"
    DISENGAGE = "disengage"

    PRESSURE = "pressure"
    MANIPULATE = "manipulate"
    DECEIVE = "deceive"
    INSULT = "insult"
    THREAT = "threat"
    THEFT = "theft"
    BETRAYAL = "betrayal"


class TemperamentPreset(GhostStrEnum):
    CALM = "calm"
    ANXIOUS = "anxious"
    CONFIDENT = "confident"
    SUSPICIOUS = "suspicious"
    RESENTFUL = "resentful"
    LOYAL = "loyal"
    VOLATILE = "volatile"


class PressureLabel(GhostStrEnum):
    RELATIONSHIP_BROKEN = "relationship_broken"
    NEAR_BREAK = "near_break"
    MAJOR_NEGATIVE_SHIFT = "major_negative_shift"
    NEGATIVE_SHIFT = "negative_shift"
    MINOR_NEGATIVE_SHIFT = "minor_negative_shift"
    STATE_SHIFT = "state_shift"
    FORGIVENESS = "forgiveness"
    DEESCALATING = "deescalating"
    POSITIVE_SHIFT = "positive_shift"
    MINOR_POSITIVE_SHIFT = "minor_positive_shift"
    STABLE = "stable"


class RelationshipState(GhostStrEnum):
    HOSTILE = "hostile"
    NEUTRAL = "neutral"
    FRIENDLY = "friendly"


def normalize_public_value(value: Any) -> str:
    """
    Normalize strings and Ghost enum values into public string values.

    This keeps raw strings working while allowing enum-based calls.
    """
    if isinstance(value, Enum):
        value = value.value

    return str(value).lower().strip()


GAME_ACTION_ALIASES = {
    "apologize": "apology",
    "apology": "apology",
    "sorry": "apology",

    "steal": "theft",
    "theft": "theft",

    "betray": "betrayal",
    "betrayal": "betrayal",

    "attack": "attack",
    "greet": "greet",
    "help": "help",
    "gift": "gift",
    "insult": "insult",
    "threat": "threat",
}


def normalize_game_action(value: Any) -> str:
    """
    Normalize player-facing actions into Ghost's canonical
    public game-action vocabulary.
    """
    action = normalize_public_value(value)

    if not action:
        raise ValueError("game action must not be empty")

    return GAME_ACTION_ALIASES.get(action, action)


def normalize_event(value: Any) -> str:
    return normalize_public_value(value)


def normalize_temperament(value: Any) -> str:
    return normalize_public_value(value)


def normalize_pressure(value: Any) -> str:
    return normalize_public_value(value)


def normalize_relationship_state(value: Any) -> str:
    return normalize_public_value(value)
