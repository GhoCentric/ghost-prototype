from __future__ import annotations

import ast
from pathlib import Path

import continuity_benchmark_v1110.run_stage9_candidate_selection as runner


def test_stage9_scope_selection_rule_and_no_production_surface_change():
    root = Path(__file__).resolve().parents[1]
    path = Path(runner.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assert sum(1 for _ in ast.walk(tree)) < 6500
    assert len(path.read_text(encoding="utf-8").splitlines()) < 520
    assert runner.STORAGE_NEAR_BEST_RATIO == 1.05
    assert runner.RUNTIME_TIE_RATIO == 1.03
    assert runner.WORKLOADS == (
        ("agent_scale_1_short", 1, 24),
        ("agent_scale_32_short", 32, 24),
        ("agent_scale_100_short", 100, 24),
        ("agent_scale_500_short", 500, 24),
        ("history_depth_32_medium", 32, 96),
        ("history_depth_32_large", 32, 192),
    )
    assert "stage9" not in (root / "ghost" / "api.py").read_text(encoding="utf-8").lower()
