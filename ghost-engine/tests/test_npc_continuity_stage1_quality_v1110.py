from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "continuity_benchmark_v1110"


def _tree(path: Path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_stage1_is_baseline_only_and_cannot_reach_into_ghost():
    for name in ("contract.py", "purpose_built.py", "scenario_runner.py", "metrics.py", "run_stage1_baseline.py"):
        text = (PKG / name).read_text(encoding="utf-8").lower()
        assert "from ghost" not in text
        assert "import ghost" not in text
        assert "openai" not in text
        assert "requests." not in text
        assert "httpx." not in text
        assert "import random" not in text


def test_stage1_contract_runner_and_baseline_are_bounded_and_not_monolithic():
    budgets = {
        "contract.py": (280, 700, 30),
        "purpose_built.py": (430, 3000, 60),
        "scenario_runner.py": (600, 5000, 60),
        "metrics.py": (120, 900, 60),
        "run_stage1_baseline.py": (120, 900, 60),
    }
    for name, (line_budget, node_budget, function_budget) in budgets.items():
        path = PKG / name
        text = path.read_text(encoding="utf-8")
        tree = _tree(path)
        nonblank = sum(bool(line.strip()) for line in text.splitlines())
        nodes = sum(1 for _ in ast.walk(tree))
        functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        largest = max((node.end_lineno - node.lineno + 1 for node in functions), default=0)
        assert nonblank <= line_budget, (name, nonblank, line_budget)
        assert nodes <= node_budget, (name, nodes, node_budget)
        assert largest <= function_budget, (name, largest, function_budget)


def test_no_dead_pass_statements_or_broad_exception_swallowing():
    offenders = []
    for path in PKG.glob("*.py"):
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Pass):
                offenders.append(f"{path.name}:{node.lineno}:pass")
            if isinstance(node, ast.ExceptHandler):
                body = node.body
                if not any(isinstance(child, ast.Raise) for child in body):
                    if node.type is None or (isinstance(node.type, ast.Name) and node.type.id in {"Exception", "BaseException"}):
                        offenders.append(f"{path.name}:{node.lineno}:broad-except")
    assert offenders == []
