from __future__ import annotations

import ast
from pathlib import Path

from ghost.api import GhostAPI

ROOT = Path(__file__).resolve().parents[1]
GHOST = ROOT / "ghost"


def _tree(name: str) -> ast.AST:
    return ast.parse((GHOST / name).read_text(encoding="utf-8"))


def test_optimization_does_not_expand_public_api_surface():
    public = {name for name in dir(GhostAPI) if not name.startswith("_")}
    assert "working_projections" not in public
    assert "schedule_continuity" not in public
    assert "compact_continuity_history" not in public


def test_new_modules_have_no_broad_exception_swallowing_or_dead_pass():
    offenders = []
    for name in ("continuity_history.py", "continuity_optimization.py"):
        for node in ast.walk(_tree(name)):
            if isinstance(node, ast.Pass):
                offenders.append((name, node.lineno, "pass"))
            if isinstance(node, ast.ExceptHandler):
                broad = node.type is None or (
                    isinstance(node.type, ast.Name)
                    and node.type.id in {"Exception", "BaseException"}
                )
                if broad and not any(isinstance(child, ast.Raise) for child in node.body):
                    offenders.append((name, node.lineno, "broad-except"))
    assert offenders == []


def test_new_module_bloat_budgets_are_bounded():
    budgets = {
        "continuity_history.py": {"nonblank": 280, "largest_fn": 55, "ast_nodes": 1900},
        "continuity_optimization.py": {"nonblank": 330, "largest_fn": 65, "ast_nodes": 2150},
    }
    for name, budget in budgets.items():
        text = (GHOST / name).read_text(encoding="utf-8")
        nonblank = sum(1 for line in text.splitlines() if line.strip())
        tree = ast.parse(text)
        fn_sizes = [
            (getattr(node, "end_lineno", node.lineno) - node.lineno + 1)
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        assert nonblank <= budget["nonblank"]
        assert max(fn_sizes, default=0) <= budget["largest_fn"]
        assert sum(1 for _ in ast.walk(tree)) <= budget["ast_nodes"]
