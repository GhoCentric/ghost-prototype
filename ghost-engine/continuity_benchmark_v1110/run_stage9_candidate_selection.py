"""Stage 9 — production-candidate selection for compact cold history.

Stage 8 established that all three zlib levels preserve the frozen Stage-6
behavioral advantage, remain lossless, and beat current Ghost's total persistent
storage at the representative workload.  Stage 9 does not change behavior or
representation semantics.  It chooses a production candidate by measuring the
three exact Stage-8 representations across orthogonal agent-count and history-depth
scales under a pre-registered storage-constrained runtime rule.
"""

from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path
import statistics
import tempfile
import time
import tracemalloc

from .run_stage8_cold_compaction import _cold_records, _populate
from .stage7_optimization_variants import optimized_factory
from .stage8_cold_history_variants import (
    COMPRESSION_LEVELS,
    CompactColdHistoryArchive,
    compact_factory,
)


STAGE = "npc_continuity_stage9_candidate_selection"
VARIANTS = tuple(COMPRESSION_LEVELS)
STORAGE_NEAR_BEST_RATIO = 1.05
RUNTIME_TIE_RATIO = 1.03
WORKLOADS = (
    ("agent_scale_1_short", 1, 24),
    ("agent_scale_32_short", 32, 24),
    ("agent_scale_100_short", 100, 24),
    ("agent_scale_500_short", 500, 24),
    ("history_depth_32_medium", 32, 96),
    ("history_depth_32_large", 32, 192),
)


def _ratio(value: float, reference: float) -> float | None:
    return None if reference == 0 else value / reference


def _median_us(callable_, repeats: int = 5) -> float:
    rows = []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        callable_()
        rows.append((time.perf_counter_ns() - start) / 1000.0)
    return statistics.median(rows)


def _seed_records(root: Path) -> dict[str, list[dict]]:
    system = optimized_factory("ghost_lazy_sparse", root / "seed", "stage9-seed")
    try:
        _populate(system, 120)
        system.snapshot()
        records = _cold_records(system)
        if {name: len(rows) for name, rows in records.items()} != {
            "interpretation": 64,
            "emotion": 64,
            "attention": 64,
        }:
            raise RuntimeError("Stage-9 seed did not produce exact 64/64/64 cold history")
        return records
    finally:
        system.close()


def _subset(records: dict[str, list[dict]], records_per_agent: int) -> dict[str, list[dict]]:
    if records_per_agent not in {24, 96, 192}:
        raise ValueError("records_per_agent must be one of 24, 96, or 192")
    per_subsystem = records_per_agent // 3
    return {name: rows[-per_subsystem:] for name, rows in records.items()}


def _sample_agents(agents: int) -> list[str]:
    indexes = sorted({0, max(0, agents // 2), max(0, agents - 1)})
    return [f"npc-{index:04d}" for index in indexes]


def _exact_lookup(store: CompactColdHistoryArchive, subsystem: str, agent: str, sequence: int) -> dict | None:
    row = store._db.execute(
        "SELECT payload_sha256,payload_z FROM history WHERE subsystem=? AND agent=? AND sequence=?",
        (str(subsystem), str(agent), int(sequence)),
    ).fetchone()
    if row is None:
        return None
    return store._decode(row[0], row[1])


def _write_workload(
    root: Path,
    kind: str,
    agents: int,
    records_per_agent: int,
    records: dict[str, list[dict]],
) -> dict:
    selected = _subset(records, records_per_agent)
    level = COMPRESSION_LEVELS[kind]
    archive = CompactColdHistoryArchive(root / f"{kind}.sqlite", compression_level=level)
    try:
        start = time.perf_counter_ns()
        for agent_index in range(agents):
            agent = f"npc-{agent_index:04d}"
            for subsystem in ("interpretation", "emotion", "attention"):
                for record in selected[subsystem]:
                    archive.put(subsystem, agent, record)
        write_total_us = (time.perf_counter_ns() - start) / 1000.0
        expected = agents * records_per_agent
        if archive.count() != expected:
            raise RuntimeError("Stage-9 workload record count mismatch")
        bytes_ = archive.bytes()
        manifest_us = _median_us(archive.manifest, repeats=3)
        manifest = archive.manifest()
        sample_agents = _sample_agents(agents)

        start = time.perf_counter_ns()
        exact_reads = 0
        for agent in sample_agents:
            for subsystem in ("interpretation", "emotion", "attention"):
                sequence = selected[subsystem][-1]["sequence"]
                if _exact_lookup(archive, subsystem, agent, sequence) != selected[subsystem][-1]:
                    raise RuntimeError("Stage-9 exact cold lookup mismatch")
                exact_reads += 1
        exact_lookup_total_us = (time.perf_counter_ns() - start) / 1000.0

        start = time.perf_counter_ns()
        projection_rows = 0
        for agent in sample_agents:
            for subsystem in ("interpretation", "emotion", "attention"):
                rows = archive.projection_rows(subsystem, agent)
                if len(rows) != len(selected[subsystem]):
                    raise RuntimeError("Stage-9 projection index count mismatch")
                projection_rows += len(rows)
        projection_read_total_us = (time.perf_counter_ns() - start) / 1000.0

        start = time.perf_counter_ns()
        full_records = 0
        for agent in sample_agents:
            for subsystem in ("interpretation", "emotion", "attention"):
                rows = archive.records(subsystem, agent)
                if rows != selected[subsystem]:
                    raise RuntimeError("Stage-9 full cold read mismatch")
                full_records += len(rows)
        full_read_total_us = (time.perf_counter_ns() - start) / 1000.0

        return {
            "agents": agents,
            "records_per_agent": records_per_agent,
            "records": expected,
            "bytes": bytes_,
            "write_total_us": write_total_us,
            "manifest_us": manifest_us,
            "exact_lookup_total_us": exact_lookup_total_us,
            "exact_lookup_count": exact_reads,
            "projection_read_total_us": projection_read_total_us,
            "projection_rows_read": projection_rows,
            "full_read_total_us": full_read_total_us,
            "full_records_read": full_records,
            "manifest_records": manifest["records"],
            "manifest_digest": manifest["digest"],
        }
    finally:
        archive.close()


def _adapter_lifecycle(kind: str, root: Path) -> dict:
    system = compact_factory(kind, root, f"stage9-{kind}")
    try:
        ids = _populate(system, 120)
        observe_before = system.observe("npc")
        save_us = _median_us(system.snapshot, repeats=5)
        snapshot = system.snapshot()
    finally:
        system.close()

    restore_rows = []
    observe_after = None
    for _ in range(3):
        start = time.perf_counter_ns()
        restored = compact_factory(kind, root, f"stage9-{kind}", snapshot=snapshot)
        restore_rows.append((time.perf_counter_ns() - start) / 1000.0)
        try:
            observe_after = restored.observe("npc")
        finally:
            restored.close()

    restored = compact_factory(kind, root, f"stage9-{kind}", snapshot=snapshot)
    try:
        sample = ids[::max(1, len(ids) // 24)]
        start = time.perf_counter_ns()
        for episode_id in sample:
            if restored.recall_episode(episode_id, .25)["status"] != "explicit_episode":
                raise RuntimeError("Stage-9 recall status mismatch")
        recall_avg_us = (time.perf_counter_ns() - start) / len(sample) / 1000.0
        projection_us = _median_us(lambda: restored.working_projections("npc"), repeats=7)
    finally:
        restored.close()
    return {
        "save_median_us": save_us,
        "restore_median_us": statistics.median(restore_rows),
        "recall_avg_us": recall_avg_us,
        "projection_median_us": projection_us,
        "restore_observation_exact": observe_after == observe_before,
    }


def _memory_probe(kind: str, root: Path, records: dict[str, list[dict]]) -> dict:
    selected = _subset(records, 192)
    gc.collect()
    tracemalloc.start()
    archive = CompactColdHistoryArchive(root / f"{kind}.sqlite", compression_level=COMPRESSION_LEVELS[kind])
    try:
        for subsystem in ("interpretation", "emotion", "attention"):
            for record in selected[subsystem]:
                archive.put(subsystem, "npc-0000", record)
        archive.bytes()
        current, peak = tracemalloc.get_traced_memory()
    finally:
        archive.close()
        tracemalloc.stop()
    return {"python_current_bytes": current, "python_peak_bytes": peak}


def _deterministic_archive_probe(kind: str, root: Path, records: dict[str, list[dict]]) -> bool:
    selected = _subset(records, 96)
    manifests = []
    decoded = []
    for label in ("a", "b"):
        archive = CompactColdHistoryArchive(root / f"{kind}-{label}.sqlite", compression_level=COMPRESSION_LEVELS[kind])
        try:
            for subsystem in ("interpretation", "emotion", "attention"):
                for record in selected[subsystem]:
                    archive.put(subsystem, "npc-0000", record)
            manifests.append(archive.manifest())
            decoded.append({name: archive.records(name, "npc-0000") for name in selected})
        finally:
            archive.close()
    return manifests[0] == manifests[1] and decoded[0] == decoded[1]


def _inherited_eligibility(stage8: dict, kind: str) -> dict:
    quality = stage8.get("quality", {}).get(kind, {})
    preservation = stage8.get("preservation", {}).get(kind, {})
    lossless = stage8.get("lossless_equivalence", {})
    integrity = stage8.get("integrity", {})
    viable = stage8.get("variants_meeting_value_and_total_storage_target", [])
    return {
        "behavior_25_of_26": quality.get("passed") == 25 and quality.get("total") == 26,
        "stage6_value_preserved": bool(preservation) and all(value is True for value in preservation.values()),
        "lossless_full_history": lossless.get("full_cold_records_exact") is True,
        "restore_equivalence": lossless.get("restore_observation_exact") is True,
        "tamper_integrity": all(integrity.get(name) is True for name in (
            "manifest_mismatch_detected", "payload_tamper_detected", "projection_tamper_detected"
        )),
        "beats_current_total_persistent_at_stage8_workload": kind in viable,
    }


def _aggregate_runtime_us(workloads: dict, lifecycle: dict) -> float:
    total = 0.0
    for row in workloads.values():
        total += row["write_total_us"]
        total += row["manifest_us"]
        total += row["exact_lookup_total_us"]
        total += row["projection_read_total_us"]
        total += row["full_read_total_us"]
    total += lifecycle["save_median_us"]
    total += lifecycle["restore_median_us"]
    total += lifecycle["projection_median_us"]
    total += lifecycle["recall_avg_us"] * 24.0
    return total


def _select_candidate(eligibility: dict, probes: dict, lifecycle: dict) -> dict:
    eligible = [kind for kind in VARIANTS if all(eligibility[kind].values()) and lifecycle[kind]["restore_observation_exact"]]
    if not eligible:
        return {"selected": None, "eligible": [], "storage_near_best": [], "runtime_tie_set": [], "reason": "no eligible candidate"}

    storage_near_best = []
    for kind in eligible:
        good = True
        for label in probes:
            smallest = min(probes[label][candidate]["bytes"] for candidate in eligible)
            if probes[label][kind]["bytes"] > smallest * STORAGE_NEAR_BEST_RATIO:
                good = False
                break
        if good:
            storage_near_best.append(kind)
    if not storage_near_best:
        return {"selected": None, "eligible": eligible, "storage_near_best": [], "runtime_tie_set": [], "reason": "no candidate stayed within storage envelope"}

    aggregate = {
        kind: _aggregate_runtime_us({label: probes[label][kind] for label in probes}, lifecycle[kind])
        for kind in storage_near_best
    }
    best_time = min(aggregate.values())
    runtime_tie_set = [kind for kind, value in aggregate.items() if value <= best_time * RUNTIME_TIE_RATIO]
    if len(runtime_tie_set) == 1:
        selected = runtime_tie_set[0]
        reason = "lowest aggregate measured runtime inside the storage-near-best envelope"
    else:
        selected = min(runtime_tie_set, key=lambda kind: (COMPRESSION_LEVELS[kind], kind))
        reason = "runtime tie within 3%; choose the lowest compression level among tied storage-qualified candidates"
    return {
        "selected": selected,
        "eligible": eligible,
        "storage_near_best": storage_near_best,
        "runtime_tie_set": runtime_tie_set,
        "aggregate_runtime_us": aggregate,
        "reason": reason,
    }


def build_result(root: str | Path, stage8: dict) -> dict:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    verdict = "LOSSLESS_COLD_COMPACTION_PRESERVES_STAGE6_VALUE_AND_BEATS_CURRENT_GHOST_TOTAL_PERSISTENT_COST"
    if stage8.get("strict_verdict") != verdict:
        raise RuntimeError("Stage-9 requires successful Stage-8 cold-compaction evidence")
    if set(stage8.get("variants_meeting_value_and_total_storage_target", [])) != set(VARIANTS):
        raise RuntimeError("Stage-9 requires all three Stage-8 candidates to remain viable")

    records = _seed_records(root / "seed")
    eligibility = {kind: _inherited_eligibility(stage8, kind) for kind in VARIANTS}
    probes: dict[str, dict] = {}
    for index, (label, agents, records_per_agent) in enumerate(WORKLOADS):
        probes[label] = {}
        order = list(VARIANTS[index % len(VARIANTS):] + VARIANTS[:index % len(VARIANTS)])
        for kind in order:
            probes[label][kind] = _write_workload(
                root / "workloads" / label,
                kind,
                agents,
                records_per_agent,
                records,
            )

    lifecycle = {kind: _adapter_lifecycle(kind, root / "lifecycle" / kind) for kind in VARIANTS}
    memory = {kind: _memory_probe(kind, root / "memory" / kind, records) for kind in VARIANTS}
    deterministic = {kind: _deterministic_archive_probe(kind, root / "determinism" / kind, records) for kind in VARIANTS}
    for kind in VARIANTS:
        eligibility[kind]["deterministic_cold_archive"] = deterministic[kind]

    selection = _select_candidate(eligibility, probes, lifecycle)
    selected = selection["selected"]
    if selected is None:
        strict = "NO_STAGE9_PRODUCTION_CANDIDATE_SELECTED"
    else:
        strict = f"STAGE9_PRODUCTION_CANDIDATE_SELECTED_{selected.upper()}"

    largest_label = "agent_scale_500_short"
    storage_summary = {}
    for kind in VARIANTS:
        smallest = min(probes[largest_label][candidate]["bytes"] for candidate in VARIANTS)
        storage_summary[kind] = {
            "largest_agent_scale_bytes": probes[largest_label][kind]["bytes"],
            "largest_agent_scale_vs_best": _ratio(probes[largest_label][kind]["bytes"], smallest),
            "stage8_total_vs_current_ghost": stage8["ratios_to_stage7_lazy_sparse"][kind]["total_vs_current_ghost"],
        }

    return {
        "stage": STAGE,
        "stage8_reference": {
            "strict_verdict": stage8["strict_verdict"],
            "variants": list(stage8["variants_meeting_value_and_total_storage_target"]),
        },
        "selection_rule": {
            "behavior_losslessness_integrity_are_hard_eligibility_gates": True,
            "storage_near_best_ratio": STORAGE_NEAR_BEST_RATIO,
            "runtime_tie_ratio": RUNTIME_TIE_RATIO,
            "primary_runtime_objective": "minimum aggregate measured cold lifecycle time across exact workloads",
            "tie_breaker": "lowest compression level among candidates within 3% of best aggregate runtime",
            "workloads": [
                {"name": label, "agents": agents, "records_per_agent": records_per_agent}
                for label, agents, records_per_agent in WORKLOADS
            ],
        },
        "eligibility": eligibility,
        "workloads": probes,
        "adapter_lifecycle": lifecycle,
        "memory_probe": memory,
        "storage_summary": storage_summary,
        "selection": selection,
        "selected_candidate": selected,
        "selected_compression_level": None if selected is None else COMPRESSION_LEVELS[selected],
        "strict_verdict": strict,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root")
    parser.add_argument("--stage8-report", required=True)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    stage8 = json.loads(Path(args.stage8_report).read_text(encoding="utf-8"))
    if args.root:
        root = Path(args.root)
        result = build_result(root, stage8)
    else:
        with tempfile.TemporaryDirectory(prefix="ghost-stage9-") as temp:
            result = build_result(Path(temp), stage8)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
