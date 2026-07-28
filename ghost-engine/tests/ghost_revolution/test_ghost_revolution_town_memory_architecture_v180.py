"""Architecture guardrails for extracted TownMemory ownership."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "ghost" / "examples"

RUNTIME_PATH = EXAMPLES / "ghost_revolution" / "demo.py"
MEMORY_PATH = EXAMPLES / "ghost_revolution" / "town_memory.py"


def test_town_memory_is_a_separate_domain_module():
    assert MEMORY_PATH.is_file()

    source = MEMORY_PATH.read_text()
    tree = ast.parse(source)

    classes = {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    }

    assert "TownMemory" in classes

    assert "from .demo import" not in source
    assert "def record_execution(" in source
    assert "def advance_day(" in source
    assert "def label(" in source
    assert "def snapshot(" in source


def test_revolution_facade_delegates_memory_ownership():
    source = RUNTIME_PATH.read_text()
    tree = ast.parse(source)

    assert (
        "from .town_memory "
        "import TownMemory"
    ) in source

    assert (
        "self._town_memory = TownMemory(TOWN_IDS)"
    ) in source

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

    assert (
        "self._town_memory.remaining(town_id)"
        in methods["town_execution_memory"]
    )

    assert (
        "self._town_memory.label(town_id)"
        in methods["town_memory_label"]
    )

    assert (
        "self._town_memory.record_execution("
        in methods["_record_town_execution_memory"]
    )

    assert (
        "self._town_memory.advance_day()"
        in methods["_advance_town_memories"]
    )
