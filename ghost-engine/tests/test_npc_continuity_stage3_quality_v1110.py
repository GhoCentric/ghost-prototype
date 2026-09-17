import ast
from pathlib import Path


def test_stage3_is_diagnostic_only_and_has_bounded_surface():
    root = Path(__file__).resolve().parents[1]
    module = root / "continuity_benchmark_v1110" / "run_stage3_failure_autopsy.py"
    text = module.read_text(encoding="utf-8")
    tree = ast.parse(text)
    functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    largest = max((node.end_lineno - node.lineno + 1) for node in functions)
    nonblank = sum(bool(line.strip()) for line in text.splitlines())
    assert nonblank < 330
    assert largest < 75
    assert "GhostAPI(" not in text
    assert "configure_interpretation_rule" not in text
    assert "restore_snapshot" not in text
    assert "production_fix_justified" in text
