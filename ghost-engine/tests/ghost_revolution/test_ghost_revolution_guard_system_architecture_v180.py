"""Architecture guardrails for GuardSystem extraction."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "ghost" / "examples"

RUNTIME_PATH = EXAMPLES / "ghost_revolution" / "demo.py"
GUARD_PATH = EXAMPLES / "ghost_revolution" / "guard.py"


def test_guard_system_is_a_separate_domain_module():
    assert GUARD_PATH.is_file()

    source = GUARD_PATH.read_text()
    tree = ast.parse(source)

    classes = {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    }

    assert "GuardSystem" in classes
    assert "def defection_chance(" in source
    assert "input(" not in source
    assert "print(" not in source


def test_revolution_facade_delegates_defection_math():
    source = RUNTIME_PATH.read_text()
    tree = ast.parse(source)

    assert (
        "from .guard import GuardSystem"
        in source
    )

    assert (
        "self._guards = GuardSystem()"
        in source
    )

    class_node = next(
        node
        for node in tree.body
        if (
            isinstance(node, ast.ClassDef)
            and node.name == "GhostRevolutionRun"
        )
    )

    methods = {
        node.name: ast.get_source_segment(source, node)
        for node in class_node.body
        if isinstance(node, ast.FunctionDef)
    }

    defection_source = methods["guard_defection_chance"]

    assert (
        "self._guards.defection_chance("
        in defection_source
    )

    assert "chance = 20" not in defection_source
    assert "round(trust * 60)" not in defection_source
