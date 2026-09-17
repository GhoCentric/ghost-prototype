from __future__ import annotations

import ast
from pathlib import Path

from ghost.api import GhostAPI
from ghost.episode_store import SQLiteEpisodeArchive


ROOT = Path(__file__).resolve().parents[1]
AUTHORIZED_PUBLIC_API = {
    "continuity_event",
    "recall_episode",
    "recall_dimension",
    "continuity_tick",
    "continuity_state",
}


def _tree(relative: str):
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    return path, text, ast.parse(text)


def _class_metrics(relative: str, class_name: str):
    path, text, tree = _tree(relative)
    lines = text.splitlines()
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    segment = lines[node.lineno - 1 : node.end_lineno]
    functions = [n for n in ast.walk(node) if isinstance(n, ast.FunctionDef)]
    return {
        "path": path,
        "nonblank": sum(bool(line.strip()) for line in segment),
        "ast_nodes": sum(1 for _ in ast.walk(node)),
        "largest_function_lines": max(n.end_lineno - n.lineno + 1 for n in functions),
    }


def test_m3_production_scope_has_no_speculative_policy_or_identity_state():
    for relative in ("ghost/continuity.py", "ghost/episode_store.py"):
        _, _, tree = _tree(relative)
        imports = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports |= {
            (node.module or "").split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        assert not ({"random", "uuid", "time"} & imports)
        function_names = {
            node.name.lower() for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        }
        assert not any(
            token in name
            for name in function_names
            for token in ("forget", "evict", "consolidat", "importance")
        )

    _, continuity_text, continuity_tree = _tree("ghost/continuity.py")
    numeric_literals = {
        node.value
        for node in ast.walk(continuity_tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, float)
    }
    assert 0.05 not in numeric_literals
    assert 0.48 not in numeric_literals
    assert "self._tick" not in continuity_text


def test_m3_production_state_ownership_and_episode_shape_are_exact():
    assert SQLiteEpisodeArchive.REQUIRED_FIELDS == {
        "episode_id",
        "agent",
        "dimension",
        "interpretation_sequence",
        "interpretation_source",
        "emotion_sequence",
        "emotion_event",
        "emotion_profile",
    }
    # Durable episode records must not become copied subsystem snapshots.
    forbidden = {
        "relationship",
        "world",
        "epistemic",
        "meaning",
        "activation",
        "emotion_before",
        "emotion_after",
        "effective_impulses",
    }
    assert not (SQLiteEpisodeArchive.REQUIRED_FIELDS & forbidden)


def test_m3_production_bloat_budgets_are_tighter_than_research_warning_levels():
    store = _class_metrics("ghost/episode_store.py", "SQLiteEpisodeArchive")
    continuity = _class_metrics("ghost/continuity.py", "ContinuityRuntime")
    foreground = _class_metrics("ghost/continuity.py", "PairwiseForeground")

    # M3T's research SQLite class was 350 nonblank lines / 1931 AST nodes.
    # Production receives a small validation allowance, not an open-ended budget.
    assert store["nonblank"] <= 400
    assert store["ast_nodes"] <= 2100
    assert store["largest_function_lines"] <= 55

    assert continuity["nonblank"] <= 230
    assert continuity["ast_nodes"] <= 1750
    assert continuity["largest_function_lines"] <= 55
    assert foreground["nonblank"] <= 75
    assert foreground["ast_nodes"] <= 575
    assert foreground["largest_function_lines"] <= 55


def test_m3_production_api_surface_is_intentionally_small():
    for name in AUTHORIZED_PUBLIC_API:
        assert callable(getattr(GhostAPI, name))
    continuity_named = {
        name for name in GhostAPI.__dict__ if not name.startswith("_") and "continuity" in name
    }
    assert continuity_named == {"continuity_event", "continuity_tick", "continuity_state"}
    recall_named = {
        name for name in GhostAPI.__dict__ if not name.startswith("_") and name.startswith("recall")
    }
    assert recall_named == {"recall_episode", "recall_dimension"}
