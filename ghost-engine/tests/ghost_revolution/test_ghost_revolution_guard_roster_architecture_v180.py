"""Architecture guardrails for Ghost Revolution guard rosters."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "ghost" / "examples"

DEMO_PATH = EXAMPLES / "ghost_revolution" / "demo.py"
GUARD_PATH = EXAMPLES / "ghost_revolution" / "guard.py"
PRESENTATION_PATH = (
    EXAMPLES / "ghost_revolution" / "presentation.py"
)


def _methods(
    source: str,
    class_name: str,
) -> set[str]:
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
        node.name
        for node in class_node.body
        if isinstance(node, ast.FunctionDef)
    }


def test_guard_roster_replaces_legacy_boolean_state():
    demo_source = DEMO_PATH.read_text()
    presentation_source = PRESENTATION_PATH.read_text()

    assert '["guard"]' not in demo_source
    assert '["guard"]' not in presentation_source

    assert "guard_roster" in demo_source


def test_facade_owns_mutable_roster_operations():
    source = DEMO_PATH.read_text()

    methods = _methods(source, "GhostRevolutionRun")

    assert {
        "guard_count",
        "has_active_guard",
        "active_guard",
        "active_guard_label",
        "_add_guard",
        "_remove_guard",
    } <= methods


def test_guard_system_owns_rank_identity_validation():
    source = GUARD_PATH.read_text()

    methods = _methods(source, "GuardSystem")

    assert {
        "guard_profile",
        "new_guard",
    } <= methods

    assert "from .demo import" not in source
    assert "from .presentation import" not in source
