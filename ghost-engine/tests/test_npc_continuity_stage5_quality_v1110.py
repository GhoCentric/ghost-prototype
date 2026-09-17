from __future__ import annotations

import ast
from pathlib import Path


def test_stage5_is_diagnostic_only_and_bounded_in_scope():
    root = Path(__file__).resolve().parents[1]
    module = root / "continuity_benchmark_v1110/run_stage5_projection_adjudication.py"
    text = module.read_text(encoding="utf-8")
    tree = ast.parse(text)
    assert len(text.splitlines()) < 430
    assert sum(1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)) <= 16
    assert "ghost.api" not in text
    assert "configure_interpretation_rule" not in text
    assert "apply_emotional_event" not in text
    assert "production_correctness_patch_justified" in text
    assert "rescored" in text
