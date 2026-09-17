from __future__ import annotations

import ast
from pathlib import Path

import continuity_benchmark_v1110.run_stage8_cold_compaction as runner
import continuity_benchmark_v1110.stage8_cold_history_variants as variants


def test_stage8_scope_and_bloat_are_bounded():
    root = Path(__file__).resolve().parents[1]
    files = [Path(variants.__file__), Path(runner.__file__)]
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert sum(1 for _ in ast.walk(tree)) < 5000
        assert len(path.read_text(encoding="utf-8").splitlines()) < 600
    assert variants.COMPRESSION_LEVELS == {
        "ghost_compact_fast": 1,
        "ghost_compact_balanced": 6,
        "ghost_compact_dense": 9,
    }
    assert not (root / "ghost" / "api.py").read_text(encoding="utf-8").count("stage8")
