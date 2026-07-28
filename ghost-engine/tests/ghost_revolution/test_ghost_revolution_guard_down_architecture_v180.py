"""Architecture guardrails for GuardSystem guard-down policy."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "ghost" / "examples"

RUNTIME_PATH = EXAMPLES / "ghost_revolution" / "demo.py"
GUARD_PATH = EXAMPLES / "ghost_revolution" / "guard.py"


def _methods(
    source: str,
    class_name: str,
) -> dict[str, str]:
    tree = ast.parse(source)

    class_node = next(
        node
        for node in tree.body
        if (
            isinstance(node, ast.ClassDef)
            and node.name == class_name
        )
    )

    return {
        node.name: ast.get_source_segment(source, node)
        for node in class_node.body
        if isinstance(node, ast.FunctionDef)
    }


def test_guard_system_owns_pure_guard_down_policy():
    source = GUARD_PATH.read_text()
    methods = _methods(source, "GuardSystem")

    assert "resolve_guard_down_outcome" in methods

    policy_source = methods[
        "resolve_guard_down_outcome"
    ]

    assert "execution_is_accepted" in policy_source
    assert "execution_is_rejected" in policy_source
    assert "from .demo import" not in source
    assert "input(" not in source
    assert "print(" not in source


def test_revolution_facade_delegates_guard_down_policy():
    source = RUNTIME_PATH.read_text()
    methods = _methods(source, "GhostRevolutionRun")

    resolution_source = methods["resolve_guard_down"]

    assert (
        "self._guards.resolve_guard_down_outcome("
        in resolution_source
    )

    assert "execution_is_accepted" not in resolution_source
    assert "execution_is_rejected" not in resolution_source
    assert "earns_support" not in resolution_source

    assert (
        "self._record_town_execution_memory("
        in resolution_source
    )

    assert 'outcome["ghost_event"]' in resolution_source
