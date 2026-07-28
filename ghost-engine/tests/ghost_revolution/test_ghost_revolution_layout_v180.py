"""Layout contracts for the Ghost Revolution demo package."""

from __future__ import annotations

import ast
from pathlib import Path

from ghost.examples.ghost_revolution import (
    GhostRevolutionRun,
)
from ghost.examples.ghost_revolution.demo import (
    GhostRevolutionRun as DemoRun,
)


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "ghost" / "examples"
PACKAGE = EXAMPLES / "ghost_revolution"


def test_package_exports_the_runtime_facade():
    assert GhostRevolutionRun is DemoRun


def test_package_contains_all_demo_modules():
    expected = {
        "__init__.py",
        "__main__.py",
        "config.py",
        "demo.py",
        "dev_shortcuts.py",
        "llm_bridge.py",
        "opponent_ai.py",
        "guard.py",
        "presentation.py",
        "raid.py",
        "social.py",
        "scripted_playthroughs.py",
        "symmetric_combat.py",
        "town_memory.py",
    }

    assert {
        path.name
        for path in PACKAGE.glob("*.py")
    } == expected

    for filename in expected:
        ast.parse(
            (PACKAGE / filename).read_text(),
            filename=str(PACKAGE / filename),
        )


def test_flat_legacy_demo_modules_are_gone():
    assert list(
        EXAMPLES.glob("ghost_revolution_*.py")
    ) == []


def test_module_entrypoint_delegates_to_demo_main():
    source = (PACKAGE / "__main__.py").read_text()

    assert "from .demo import main" in source
    assert 'if __name__ == "__main__":' in source
    assert "main()" in source
