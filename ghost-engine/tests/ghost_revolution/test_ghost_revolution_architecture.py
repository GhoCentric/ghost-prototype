"""
Architecture guardrails for Ghost Revolution.

These tests prevent known architecture regressions:
terminal UI leaking into runtime code, direct Ghost internals,
mutable shared configuration, and reverse UI dependencies.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ghost.examples.ghost_revolution.config import (
    LOCATION_DISTANCE,
    RAID_REQUIREMENTS,
    build_revolution_scenario,
    military_camp_for,
    raid_requirement_for,
)
from ghost.examples.ghost_revolution.demo import (
    GhostRevolutionRun,
)


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "ghost" / "examples"

RUNTIME_PATH = EXAMPLES / "ghost_revolution" / "demo.py"
SOCIAL_PATH = EXAMPLES / "ghost_revolution" / "social.py"
CONFIG_PATH = EXAMPLES / "ghost_revolution" / "config.py"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(), filename=str(path))


def _called_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id

    if isinstance(node.func, ast.Attribute):
        return node.func.attr

    return None


def test_runtime_module_has_no_terminal_side_effect_calls():
    tree = _tree(RUNTIME_PATH)

    forbidden = {"input", "print", "sleep"}

    calls = {
        name
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for name in [_called_name(node)]
        if name is not None
    }

    assert not calls.intersection(forbidden)


def test_runtime_module_has_no_legacy_terminal_helpers():
    tree = _tree(RUNTIME_PATH)

    top_level_functions = [
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    ]

    assert top_level_functions == ["main"]


def test_only_social_bridge_imports_scenario_runtime():
    runtime_tree = _tree(RUNTIME_PATH)
    social_tree = _tree(SOCIAL_PATH)
    config_tree = _tree(CONFIG_PATH)

    def scenario_runtime_imports(tree: ast.Module):
        return [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module == "ghost.scenario_runtime"
        ]

    assert scenario_runtime_imports(runtime_tree) == []
    assert scenario_runtime_imports(config_tree) == []
    assert len(scenario_runtime_imports(social_tree)) == 1

    runtime_source = RUNTIME_PATH.read_text()

    assert ".api." not in runtime_source
    assert "self.runtime." not in runtime_source


def test_presentation_import_is_limited_to_main_entrypoint():
    tree = _tree(RUNTIME_PATH)

    presentation_imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "presentation"
    ]

    assert len(presentation_imports) == 1

    main_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "main"
    )

    assert presentation_imports[0] in set(ast.walk(main_node))


def test_configuration_isolation_and_immutability():
    first = build_revolution_scenario()
    second = build_revolution_scenario()

    first["npcs"]["ashfield"]["personality"] = "volatile"

    assert second["npcs"]["ashfield"]["personality"] == "forgiving"

    camp = military_camp_for("millcross")
    camp["garrison"] = 999

    assert military_camp_for("millcross")["garrison"] == 50

    requirement = raid_requirement_for("ashfield")
    requirement["food_required"] = 999

    assert raid_requirement_for("ashfield")["food_required"] == 6

    with pytest.raises(TypeError):
        LOCATION_DISTANCE["base"] = 999

    with pytest.raises(TypeError):
        RAID_REQUIREMENTS["ashfield"]["food_required"] = 999


def test_runtime_compatibility_facade_uses_social_bridge():
    game = GhostRevolutionRun(seed=7)

    assert game.runtime is game._social.runtime
    assert game.current_world() == game._social.current_world()
    assert game.town_trust("ashfield") == 0.0
