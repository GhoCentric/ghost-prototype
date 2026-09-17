"""Static anti-cheating and maintainability gates for Stage 2."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "continuity_benchmark_v1110" / "ghost_adapter.py"
RUNNER = ROOT / "continuity_benchmark_v1110" / "run_stage2_head_to_head.py"


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_ghost_adapter_cannot_read_frozen_oracles_or_baseline_implementation():
    text = ADAPTER.read_text(encoding="utf-8")
    forbidden = (
        "purpose_built",
        "scenario_runner",
        "stage1_baseline_frozen",
        "moving_on_without_erasure",
        "exact_recall_without_replay",
        "same_dimension_identity_and_ambiguity",
        "snapshot_archive_pairing",
        "stale_dominance_resistance",
        "large_ambiguity_safety",
        "62/62",
        "58/62",
    )
    assert not [token for token in forbidden if token in text]


def test_stage2_adds_only_adapter_runner_and_new_tests_to_frozen_stage1_surface():
    expected_new = {
        "continuity_benchmark_v1110/ghost_adapter.py",
        "continuity_benchmark_v1110/run_stage2_head_to_head.py",
        "tests/test_npc_continuity_stage2_v1110.py",
        "tests/test_npc_continuity_stage2_quality_v1110.py",
        "tests/test_npc_continuity_stage2_runner_coverage_v1110.py",
    }
    assert all((ROOT / rel).is_file() for rel in expected_new)
    frozen = {
        "continuity_benchmark_v1110/contract.py": "843e19bf4baa6212aa15921ad7f5c9997c9c305d0ad3ac0b0aa1b1d50ef3a694",
        "continuity_benchmark_v1110/metrics.py": "13a1f0caefbe6e832ef8cc5d42a55470a712c9c87e7a88736642d97fbde4922b",
        "continuity_benchmark_v1110/purpose_built.py": "0b607b14d00d0c70c9b8201cfcc43c3c0a06d2270d97f4ea87a55e57206982c2",
        "continuity_benchmark_v1110/scenario_runner.py": "1b794701ff7174b56f0f1f13016b21799bd0ffe36ac2fa86ecbefacc357a70ec",
        "continuity_benchmark_v1110/stage1_baseline_frozen.json": "d87d577214a51130c8e9bf85133e874db18a1713a728ac1b74e0150294774f61",
        "tests/test_npc_continuity_stage1_v1110.py": "c1340f9f2b92b3003ad671f07ea1fe73fff58c7a9fcc4790bd8ef344756dfae3",
        "tests/test_npc_continuity_stage1_quality_v1110.py": "202127649578fb1c47a6a6fdcfbef4249a27930a7d86302fb692615638092a44",
    }
    actual = {
        rel: hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        for rel in frozen
    }
    assert actual == frozen


def test_stage2_adapter_and_reporter_remain_bounded_and_nonduplicative():
    for path, max_nonblank, max_function_lines, max_ast_nodes in (
        (ADAPTER, 330, 55, 2600),
        (RUNNER, 330, 70, 2700),
    ):
        text = path.read_text(encoding="utf-8")
        tree = _tree(path)
        funcs = [
            node for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        assert sum(bool(line.strip()) for line in text.splitlines()) <= max_nonblank
        assert max(node.end_lineno - node.lineno + 1 for node in funcs) <= max_function_lines
        assert sum(1 for _ in ast.walk(tree)) <= max_ast_nodes
        names = [node.name for node in funcs]
        assert len(names) == len(set(names))


def test_adapter_has_no_random_llm_network_or_benchmark_result_constants():
    text = ADAPTER.read_text(encoding="utf-8").lower()
    forbidden = (
        "import random",
        "from random",
        "openai",
        "requests.",
        "httpx.",
        "socket.",
        "subprocess",
        "deterministic_digest",
        "all_checks",
        "competence",
        "discriminators",
    )
    assert not [token for token in forbidden if token in text]


def test_characterization_tests_do_not_rerun_the_expensive_frozen_head_to_head():
    text = (ROOT / "tests/test_npc_continuity_stage2_v1110.py").read_text(encoding="utf-8")
    assert "run_frozen_suite" not in text
    assert "build_report" not in text
