"""
Immutable configuration and fresh scenario factories for Ghost Revolution.

This module owns static world data only. Callers receive new copies from
factory functions, so one game run cannot mutate shared configuration.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final, Mapping


def _freeze_mapping(
    data: Mapping[str, object],
) -> Mapping[str, object]:
    frozen: dict[str, object] = {}

    for key, value in data.items():
        if isinstance(value, dict):
            frozen[key] = _freeze_mapping(value)
        else:
            frozen[key] = value

    return MappingProxyType(frozen)


REBELLION_DAYS: Final = 7
CAMP_DAYS: Final = 2
REBELLION_ACTIONS: Final = 6
CAMP_ACTIONS: Final = 3

START_GOLD: Final = 20
START_FOOD: Final = 3
START_WEAPONS: Final = 1

KING_FIGHT_PLAYER_DAMAGE: Final = _freeze_mapping(
    {
        "normal": {
            "heavy": 4,
            "light": 2,
            "feint_heavy": 4,
            "feint_light": 2,
            "deflect": 2,
        },
        "parry_opening": {
            "heavy": 5,
            "light": 3,
        },
        "forced_recovery": {
            "light": 1,
            "dodge": 0,
        },
    }
)

LOCATIONS: Final = (
    "base",
    "ashfield",
    "millcross",
    "crownmarket",
    "castle",
)

LOCATION_DISTANCE: Final = _freeze_mapping(
    {
        "base": 0,
        "ashfield": 1,
        "millcross": 2,
        "crownmarket": 3,
        "castle": 4,
    }
)

TOWN_IDS: Final = (
    "ashfield",
    "millcross",
    "crownmarket",
)

WEAPON_TYPES: Final = (
    "sword",
    "axe",
    "spear",
    "bow",
)

SHIELD_TYPES: Final = (
    "light",
    "medium",
    "heavy",
)

WEAPON_TIERS: Final = _freeze_mapping(
    {
        "common": 1,
        "rare": 2,
        "legendary": 3,
    }
)

RAID_REQUIREMENTS: Final = _freeze_mapping(
    {
        "ashfield": {
            "recommended_warriors": 25,
            "food_required": 6,
            "recommended_weapons": 18,
        },
        "millcross": {
            "recommended_warriors": 50,
            "food_required": 12,
            "recommended_weapons": 38,
        },
        "crownmarket": {
            "recommended_warriors": 75,
            "food_required": 18,
            "recommended_weapons": 58,
        },
        "castle": {
            "recommended_warriors": 100,
            "food_required": 28,
            "recommended_weapons": 80,
        },
    }
)

MILITARY_CAMPS: Final = _freeze_mapping(
    {
        "ashfield": {
            "name": "Eastwatch Camp",
            "knight": "Sir Rowan",
            "warlord": "Garran the Iron Hand",
            "garrison": 25,
        },
        "millcross": {
            "name": "Ironford Camp",
            "knight": "Lady Merrow",
            "warlord": "Varek the Hound",
            "garrison": 50,
        },
        "crownmarket": {
            "name": "Crown Guard Camp",
            "knight": "Sir Mael",
            "warlord": "Dorian Blackshield",
            "garrison": 75,
        },
        "castle": {
            "name": "Royal War Camp",
            "knight": "The King's Champion",
            "warlord": "Marshal Voss",
            "garrison": 100,
        },
    }
)


def military_camp_for(target: str) -> dict[str, object]:
    try:
        camp = MILITARY_CAMPS[target]
    except KeyError as error:
        raise ValueError(
            f"Unknown military camp target: {target}"
        ) from error

    return dict(camp)


def raid_requirement_for(target: str) -> dict[str, int]:
    try:
        requirement = RAID_REQUIREMENTS[target]
    except KeyError as error:
        raise ValueError(
            f"Unknown raid target: {target}"
        ) from error

    return {
        key: int(value)
        for key, value in requirement.items()
    }


def build_revolution_scenario() -> dict[str, object]:
    """
    Return a brand-new scenario configuration for one game run.
    """

    return {
        "scenario_id": "ghost_revolution_demo",
        "npc_roles": {
            "ashfield": "ashfield",
            "millcross": "millcross",
            "crownmarket": "crownmarket",
            "king": "king",
            "captain": "captain",
        },
        "npcs": {
            "ashfield": {
                "personality": "forgiving",
                "temperament": "calm",
            },
            "millcross": {
                "personality": "balanced",
                "temperament": "calm",
            },
            "crownmarket": {
                "personality": "resentful",
                "temperament": "suspicious",
            },
            "king": {
                "personality": "volatile",
                "temperament": "volatile",
            },
            "captain": {
                "personality": "balanced",
                "temperament": "suspicious",
            },
        },
        "relationships": [
            {
                "source": "crownmarket",
                "target": "captain",
                "trust": 0.35,
            },
            {
                "source": "captain",
                "target": "king",
                "trust": 0.45,
            },
            {
                "source": "ashfield",
                "target": "millcross",
                "trust": 0.20,
            },
        ],
        "propagation_weights": {
            "ashfield": 0.55,
            "millcross": 0.75,
            "crownmarket": 0.90,
            "king": 1.0,
            "captain": 0.85,
        },
        "economy": {
            "base_prices": {
                "bread": 10,
                "weapons": 15,
            },
        },
        "quest": {
            "trust_required": 0.25,
            "pressure_max": 1.25,
        },
        "thresholds": {
            "pressure_crisis": 2.0,
            "pressure_expulsion": 3.5,
            "arrest_severity": 0.85,
        },
        "win_conditions": [
            "complete_market_quest",
        ],
        "fail_conditions": [
            "town_expels_player",
        ],
    }
