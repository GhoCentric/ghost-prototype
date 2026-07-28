"""
Architecture contracts for the extracted Ghost Revolution raid domain.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ghost.examples.ghost_revolution.raid import (
    RaidContext,
    RaidOutcome,
    RaidSystem,
)


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "ghost" / "examples"
RUNTIME = EXAMPLES / "ghost_revolution" / "demo.py"
RAID = EXAMPLES / "ghost_revolution" / "raid.py"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(), filename=str(path))


def _method(tree: ast.Module, name: str) -> ast.FunctionDef:
    runtime_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "GhostRevolutionRun"
    )

    return next(
        node
        for node in runtime_class.body
        if isinstance(node, ast.FunctionDef)
        and node.name == name
    )


def test_raid_module_has_no_upward_dependencies():
    source = RAID.read_text()

    forbidden = (
        "from .demo import",
        "from .presentation import",
        "scenario_runtime",
        "ScenarioRuntime",
    )

    for name in forbidden:
        assert name not in source


def test_raid_context_and_outcome_are_immutable():
    assert RaidContext.__dataclass_params__.frozen is True
    assert RaidOutcome.__dataclass_params__.frozen is True


def test_runtime_raid_entrypoints_are_thin_delegations():
    tree = _tree(RUNTIME)

    methods = (
        "deployed_warriors",
        "_release_raid_reservations",
        "cancel_raid_plan",
        "army_weapons_issued",
        "army_shields_issued",
        "raid_readiness",
        "plan_raid",
        "active_raid_summary",
        "commit_raid",
        "set_raid_force",
        "set_raid_weapon_issue",
        "set_raid_shield_issue",
    )

    for name in methods:
        node = _method(tree, name)

        assert not any(
            isinstance(
                child,
                (
                    ast.For,
                    ast.While,
                ),
            )
            for child in ast.walk(node)
        )

        assert "self._raids" in ast.unparse(node)


def test_raid_state_does_not_leak_mutable_snapshots():
    system = RaidSystem()

    system.replace_plan(
        {
            "target": "ashfield",
            "force": 3,
            "weapon_issue": {
                "sword": 1,
                "axe": 0,
                "spear": 0,
                "bow": 0,
            },
            "shield_issue": {
                "light": 0,
                "medium": 0,
                "heavy": 0,
            },
            "camp": "Eastwatch Camp",
            "warlord": "Garran the Iron Hand",
            "knight": "Sir Rowan",
        }
    )

    leaked = system.plan
    leaked["force"] = 999
    leaked["weapon_issue"]["sword"] = 999

    fresh = system.plan

    assert fresh["force"] == 3
    assert fresh["weapon_issue"]["sword"] == 1

def test_frozen_raid_records_copy_and_freeze_nested_mappings():
    weapon_stock = {
        "sword": 2,
        "axe": 0,
    }
    shield_stock = {
        "light": 1,
    }
    camp = {
        "name": "Eastwatch Camp",
        "knight": "Sir Rowan",
        "warlord": "Garran the Iron Hand",
        "garrison": 25,
    }
    requirement = {
        "recommended_warriors": 25,
        "food_required": 6,
        "recommended_weapons": 18,
    }

    context = RaidContext(
        target="ashfield",
        location="base",
        valid_target=True,
        weapon_stock=weapon_stock,
        shield_stock=shield_stock,
        camp=camp,
        requirement=requirement,
    )

    weapon_stock["sword"] = 999
    shield_stock["light"] = 999
    camp["garrison"] = 999
    requirement["food_required"] = 999

    assert context.weapon_stock["sword"] == 2
    assert context.shield_stock["light"] == 1
    assert context.camp["garrison"] == 25
    assert context.requirement["food_required"] == 6

    with pytest.raises(TypeError):
        context.weapon_stock["sword"] = 7

    with pytest.raises(TypeError):
        context.shield_stock["light"] = 7

    with pytest.raises(TypeError):
        context.camp["garrison"] = 7

    with pytest.raises(TypeError):
        context.requirement["food_required"] = 7

    weapon_deltas = {
        "sword": -2,
    }
    shield_deltas = {
        "light": -1,
    }

    outcome = RaidOutcome(
        note="Reserved.",
        ok=True,
        weapon_stock_deltas=weapon_deltas,
        shield_stock_deltas=shield_deltas,
    )

    weapon_deltas["sword"] = 999
    shield_deltas["light"] = 999

    assert outcome.weapon_stock_deltas["sword"] == -2
    assert outcome.shield_stock_deltas["light"] == -1

    with pytest.raises(TypeError):
        outcome.weapon_stock_deltas["sword"] = 1

    with pytest.raises(TypeError):
        outcome.shield_stock_deltas["light"] = 1

    readiness = RaidSystem().readiness(context)

    readiness["weapon_stock"]["sword"] = 0
    readiness["shield_stock"]["light"] = 0

    assert context.weapon_stock["sword"] == 2
    assert context.shield_stock["light"] == 1

