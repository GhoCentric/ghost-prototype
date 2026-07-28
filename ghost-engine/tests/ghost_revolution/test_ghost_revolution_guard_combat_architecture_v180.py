"""Architecture guardrails for tactical GuardSystem combat."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "ghost" / "examples"

RUNTIME_PATH = EXAMPLES / "ghost_revolution" / "demo.py"
GUARD_PATH = EXAMPLES / "ghost_revolution" / "guard.py"


def _revolution_methods(source: str) -> dict[str, str]:
    tree = ast.parse(source)

    class_node = next(
        node
        for node in tree.body
        if (
            isinstance(node, ast.ClassDef)
            and node.name == "GhostRevolutionRun"
        )
    )

    return {
        node.name: ast.get_source_segment(source, node)
        for node in class_node.body
        if isinstance(node, ast.FunctionDef)
    }


def test_guard_system_owns_pure_tactical_combat_rules():
    source = GUARD_PATH.read_text()
    tree = ast.parse(source)

    classes = {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    }

    assert "GuardSystem" in classes
    assert "_COMBAT_INTENTS" in source
    assert "def resolve_tactical_exchange(" in source
    assert "def resolve_player_loss_outcome(" in source

    assert "_PLAYER_MOVE_ALIASES" not in source
    assert "_PLAYER_WINNING_PAIRS" not in source

    assert "from .demo import" not in source
    assert "input(" not in source
    assert "print(" not in source


def test_revolution_facade_delegates_tactical_math():
    source = RUNTIME_PATH.read_text()
    methods = _revolution_methods(source)

    combat_source = methods["resolve_guard_combat_move"]

    assert (
        "self._guards.resolve_tactical_exchange("
        in combat_source
    )
    assert (
        "self._guards.resolve_player_loss_outcome("
        in methods["_finish_guard_combat_loss"]
    )

    assert "winning_pairs = {" not in combat_source
    assert "player_move == guard_move" not in combat_source

    assert (
        "self._finish_guard_combat_victory()"
        in combat_source
    )
    assert (
        "self._finish_guard_combat_loss()"
        in combat_source
    )
