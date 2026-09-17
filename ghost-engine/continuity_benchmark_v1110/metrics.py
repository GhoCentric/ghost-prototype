"""Engineering probes for the frozen continuity comparison."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import time

from .purpose_built import PurposeBuiltContinuity


def source_metrics(path: str | Path) -> dict:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    funcs = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return {
        "bytes": len(text.encode("utf-8")),
        "nonblank_lines": sum(bool(line.strip()) for line in text.splitlines()),
        "ast_nodes": sum(1 for _ in ast.walk(tree)),
        "functions": len(funcs),
        "largest_function_lines": max((node.end_lineno - node.lineno + 1 for node in funcs), default=0),
    }


def storage_probe(root: str | Path, *, episodes: int = 10_000) -> dict:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / "baseline_storage_probe.sqlite"
    system = PurposeBuiltContinuity(path)
    target_id = None
    try:
        for index in range(episodes):
            row = system.event(
                "npc",
                source=f"episode-{index}",
                dimension=f"dimension-{index % 32}",
                meaning_delta=0.0001,
                relevance=0.01,
                emotion_profile={},
                consequence=0.0,
            )
            if index == episodes // 2:
                target_id = row["episode_id"]
        snapshot_bytes = len(
            json.dumps(system.snapshot(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        )
        assert target_id is not None
        start = time.perf_counter_ns()
        for _ in range(500):
            assert system.archive.get(target_id) is not None
        elapsed = time.perf_counter_ns() - start
        plan = system.archive._con.execute(
            "EXPLAIN QUERY PLAN SELECT episode_id FROM episodes WHERE agent=? AND dimension=? ORDER BY ordinal,episode_id",
            ("npc", "dimension-1"),
        ).fetchall()
        return {
            "episodes": episodes,
            "archive_bytes": path.stat().st_size,
            "hot_snapshot_bytes": snapshot_bytes,
            "exact_lookup_average_microseconds": elapsed / 500 / 1000.0,
            "dimension_index_used": any("INDEX" in str(row).upper() for row in plan),
        }
    finally:
        system.close()
