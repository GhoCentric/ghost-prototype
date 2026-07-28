"""Contracts for GuardSystem combat-rank stats."""

from ghost.examples.ghost_revolution.guard import (
    GuardSystem,
)


def test_watchman_rank_stats_are_explicit():
    profile = GuardSystem.guard_profile("watchman")

    assert profile == {
        "rank": "watchman",
        "label": "Royal Watchman",
        "max_health": 10,
        "light_damage": 2,
        "heavy_damage": 3,
        "feint_read_chance": 25,
        "parry_success_chance": 75,
        "deflect_success_chance": 70,
        "escape_chance": 22,
        "death_chance": 2,
    }


def test_crown_guard_rank_stats_are_explicit():
    profile = GuardSystem.guard_profile("crown_guard")

    assert profile == {
        "rank": "crown_guard",
        "label": "Crown Guard",
        "max_health": 14,
        "light_damage": 3,
        "heavy_damage": 4,
        "feint_read_chance": 40,
        "parry_success_chance": 65,
        "deflect_success_chance": 60,
        "escape_chance": 12,
        "death_chance": 5,
    }


def test_rank_profiles_are_copy_safe():
    first = GuardSystem.guard_profile("watchman")
    first["max_health"] = 999

    second = GuardSystem.guard_profile("watchman")

    assert second["max_health"] == 10
