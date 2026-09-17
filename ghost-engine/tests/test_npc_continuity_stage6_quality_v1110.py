from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "policy": ROOT / "continuity_benchmark_v1110/stage6_behavior_policy.py",
    "scenarios": ROOT / "continuity_benchmark_v1110/stage6_behavior_scenarios.py",
    "runner": ROOT / "continuity_benchmark_v1110/run_stage6_behavioral_value.py",
}


def test_stage6_is_additive_architecture_neutral_and_bounded():
    policy = FILES["policy"].read_text(encoding="utf-8")
    scenarios = FILES["scenarios"].read_text(encoding="utf-8")
    runner = FILES["runner"].read_text(encoding="utf-8")

    assert "from ghost" not in policy and "purpose_built" not in policy and "ghost_adapter" not in policy
    assert 'if kind == "baseline"' in scenarios and 'if kind == "ghost"' in scenarios
    assert scenarios.count('if kind == "baseline"') == 1
    assert scenarios.count('if kind == "ghost"') == 1
    assert "23/26" not in runner and "25/26" not in runner
    assert "ghost_only_passes" in runner and "baseline_only_passes" in runner
    assert "use_foreground=False" in scenarios
    assert "STAGE5_CHECKPOINT_SHA256" in policy

    budgets = {
        "policy": (180, 1500, 55),
        "scenarios": (380, 4000, 45),
        "runner": (180, 1500, 55),
    }
    for name, path in FILES.items():
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        line_budget, node_budget, function_budget = budgets[name]
        assert len(text.splitlines()) <= line_budget
        assert sum(1 for _ in ast.walk(tree)) <= node_budget
        assert max(
            (node.end_lineno - node.lineno + 1)
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ) <= function_budget
