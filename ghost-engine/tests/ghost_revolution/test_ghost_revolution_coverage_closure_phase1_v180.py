"""Coverage closure for small Ghost Revolution domain modules."""

from __future__ import annotations

from copy import deepcopy

import pytest

from ghost.examples.ghost_revolution.config import (
    SHIELD_TYPES,
    TOWN_IDS,
    WEAPON_TYPES,
    build_revolution_scenario,
    military_camp_for,
    raid_requirement_for,
)
from ghost.examples.ghost_revolution.raid import (
    RaidContext,
    RaidSystem,
)
from ghost.examples.ghost_revolution.social import (
    GhostRevolutionSocialBridge,
)
from ghost.examples.ghost_revolution.town_memory import (
    TownMemory,
)


def _context(
    *,
    target: str = "ashfield",
    location: str = "base",
    valid_target: bool = True,
    town_rebel_controlled: bool = False,
    available_warriors: int = 30,
    food: int = 30,
    weapon_stock: dict[str, int] | None = None,
    shield_stock: dict[str, int] | None = None,
) -> RaidContext:
    camp_target = target if target in {
        "ashfield",
        "millcross",
        "crownmarket",
        "castle",
    } else "ashfield"

    return RaidContext(
        target=target,
        location=location,
        valid_target=valid_target,
        town_name=target.title(),
        town_condition="stable",
        town_rebel_controlled=town_rebel_controlled,
        available_warriors=available_warriors,
        food=food,
        weapon_stock=(
            weapon_stock
            if weapon_stock is not None
            else {weapon: 10 for weapon in WEAPON_TYPES}
        ),
        shield_stock=(
            shield_stock
            if shield_stock is not None
            else {shield: 10 for shield in SHIELD_TYPES}
        ),
        leader_weapon="Knight's Sword",
        leader_weapon_tier="common",
        leader_armor="none",
        camp=military_camp_for(camp_target),
        requirement=raid_requirement_for(camp_target),
    )


def _active_snapshot() -> dict:
    return {
        "target": "ashfield",
        "town": "Ashfield",
        "force": 25,
        "weapon_issue": {
            weapon: (18 if weapon == "sword" else 0)
            for weapon in WEAPON_TYPES
        },
        "shield_issue": {
            shield: (2 if shield == "light" else 0)
            for shield in SHIELD_TYPES
        },
        "food_committed": 6,
        "intel_level": 1,
        "intel_bonus": 2,
        "readiness": 38,
        "odds": "FAVORABLE",
        "camp": "Eastwatch Camp",
        "knight": "Sir Rowan",
        "warlord": "Garran the Iron Hand",
        "phase_number": 1,
        "phase_day": 2,
    }


def test_config_lookup_rejects_unknown_targets_v180():
    with pytest.raises(
        ValueError,
        match="Unknown military camp target: missing",
    ):
        military_camp_for("missing")

    with pytest.raises(
        ValueError,
        match="Unknown raid target: missing",
    ):
        raid_requirement_for("missing")


def test_town_memory_rejects_non_mapping_execution_memory_v180():
    with pytest.raises(
        ValueError,
        match="execution memory must be a dict",
    ):
        TownMemory.from_snapshot(
            TOWN_IDS,
            {"execution_memory": []},
        )


def test_social_snapshot_rejects_json_unsafe_and_invalid_fields_v180():
    bridge = GhostRevolutionSocialBridge(
        build_revolution_scenario()
    )
    snapshot = bridge.snapshot()

    with pytest.raises(
        ValueError,
        match="social snapshot must be JSON-safe",
    ):
        GhostRevolutionSocialBridge.from_snapshot(
            {"unsafe": object()}
        )

    cases = (
        (
            "config",
            [],
            "social snapshot config must be a dict",
        ),
        (
            "actor_id",
            "   ",
            "social snapshot actor id must be a non-empty string",
        ),
        (
            "information_sequence",
            True,
            "information sequence must be a non-negative integer",
        ),
        (
            "information_entries",
            {},
            "information entries must be a list",
        ),
    )

    for key, value, message in cases:
        damaged = deepcopy(snapshot)
        damaged[key] = value

        with pytest.raises(ValueError, match=message):
            GhostRevolutionSocialBridge.from_snapshot(damaged)

    damaged = deepcopy(snapshot)
    damaged["scenario_state"] = []

    with pytest.raises(
        ValueError,
        match="scenario state is invalid",
    ):
        GhostRevolutionSocialBridge.from_snapshot(damaged)

    damaged = deepcopy(snapshot)
    damaged["scenario_state"]["served_punishment"] = 0

    with pytest.raises(
        ValueError,
        match="scenario state is invalid",
    ):
        GhostRevolutionSocialBridge.from_snapshot(damaged)


def test_raid_active_restore_and_shield_totals_v180():
    system = RaidSystem()
    snapshot = _active_snapshot()

    system.replace_active(snapshot)

    assert system.active == snapshot
    assert system.deployed_warriors() == 25
    assert system.issued_shields() == 2


def test_raid_readiness_and_plan_opening_reject_invalid_targets_v180():
    invalid = _context(
        target="missing",
        valid_target=False,
    )

    system = RaidSystem()

    with pytest.raises(
        ValueError,
        match="Unknown raid target: missing",
    ):
        system.readiness(invalid)

    outcome = system.open_plan(invalid)

    assert outcome.ok is False
    assert outcome.note == "Unknown raid target."

    controlled = _context(
        town_rebel_controlled=True,
    )
    outcome = system.open_plan(controlled)

    assert outcome.ok is False
    assert "already under rebel control" in outcome.note


def test_raid_empty_plan_commands_are_explicit_noops_v180():
    system = RaidSystem()
    context = _context()

    assert system.cancel_plan().ok is False
    assert system.release_plan().ok is True
    assert system.set_force(context, 1).ok is False
    assert system.set_weapon_issue(context, "sword", 1).ok is False
    assert system.set_shield_issue(context, "light", 1).ok is False
    assert system.commit(context).ok is False


def test_raid_force_validation_covers_invalid_and_reserved_gear_v180():
    system = RaidSystem()
    context = _context()

    assert system.open_plan(context).ok is True
    assert system.set_force(context, -1).ok is False
    assert system.set_force(context, 2).ok is True
    assert system.set_weapon_issue(context, "sword", 2).ok is True

    outcome = system.set_force(context, 1)

    assert outcome.ok is False
    assert "Reduce issued weapons or shields" in outcome.note


def test_raid_weapon_issue_validation_covers_domain_errors_v180():
    system = RaidSystem()
    context = _context(
        weapon_stock={weapon: 1 for weapon in WEAPON_TYPES},
    )

    assert system.open_plan(context).ok is True
    assert system.set_force(context, 4).ok is True

    assert system.set_weapon_issue(
        context,
        "unknown",
        1,
    ).ok is False

    assert system.set_weapon_issue(
        context,
        "sword",
        -1,
    ).ok is False

    outcome = system.set_weapon_issue(
        context,
        "sword",
        2,
    )

    assert outcome.ok is False
    assert "Only 1 swords are available" in outcome.note


def test_raid_shield_issue_validation_covers_domain_errors_v180():
    system = RaidSystem()
    context = _context(
        shield_stock={shield: 1 for shield in SHIELD_TYPES},
    )

    assert system.open_plan(context).ok is True
    assert system.set_force(context, 1).ok is True

    assert system.set_shield_issue(
        context,
        "unknown",
        1,
    ).ok is False

    assert system.set_shield_issue(
        context,
        "light",
        -1,
    ).ok is False

    outcome = system.set_shield_issue(
        context,
        "light",
        2,
    )

    assert outcome.ok is False
    assert "Only 1 light shields are available" in outcome.note

    assert system.set_shield_issue(
        context,
        "light",
        1,
    ).ok is True

    outcome = system.set_shield_issue(
        context,
        "medium",
        1,
    )

    assert outcome.ok is False
    assert "more shields than raid warriors" in outcome.note


def test_raid_commit_rejects_wrong_location_and_active_raid_v180():
    system = RaidSystem()

    outcome = system.commit(
        _context(location="ashfield")
    )

    assert outcome.ok is False
    assert "hidden base" in outcome.note

    system.replace_active(_active_snapshot())

    outcome = system.commit(_context())

    assert outcome.ok is False
    assert "already active" in outcome.note
