"""Stage 8 — lossless cold-history compaction experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import tempfile
import time

from .run_stage6_behavioral_value import _foreground_ablation
from .run_stage7_optimization import GHOST_ONLY_TARGETS, _checks
from .stage7_optimization_variants import ColdHistoryArchive, optimized_factory
from .stage8_cold_history_variants import (
    COMPRESSION_LEVELS,
    CompactColdHistoryArchive,
    compact_factory,
    patched_stage6_factory,
    run_stage6_quality_for_compact,
)


STAGE = "npc_continuity_stage8_cold_compaction"
VARIANTS = tuple(COMPRESSION_LEVELS)


def _wins_preserved(packet: dict) -> bool:
    checks = _checks(packet)
    return all(checks.get(name) is True for name in GHOST_ONLY_TARGETS)


def _time_us(callable_, repeats: int = 5) -> float:
    rows = []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        callable_()
        rows.append((time.perf_counter_ns() - start) / 1000.0)
    return statistics.median(rows)


def _populate(system, count: int = 120) -> list[str]:
    ids = []
    for index in range(count):
        dimension = ("respect", "threat", "betrayal")[index % 3]
        emotion = {"hope": .08} if dimension == "respect" else ({"fear": .08} if dimension == "threat" else {"anger": .08})
        consequence = .002 if dimension == "respect" else (-.002 if dimension == "betrayal" else 0.0)
        row = system.event(
            "npc",
            source=f"stage8-engineering-{index}",
            dimension=dimension,
            meaning_delta=.006,
            relevance=.006,
            emotion_profile=emotion,
            consequence=consequence,
        )
        ids.append(row["episode_id"])
    return ids


def _cold_records(system) -> dict[str, list[dict]]:
    if system.cold_history is None:
        return {}
    return {
        subsystem: system.cold_history.records(subsystem, "npc")
        for subsystem in ("interpretation", "emotion", "attention")
    }


def _engineering(kind: str, root: Path) -> dict:
    system = compact_factory(kind, root, f"{kind}-engineering")
    try:
        start = time.perf_counter_ns()
        ids = _populate(system)
        event_avg_us = (time.perf_counter_ns() - start) / len(ids) / 1000.0

        for _ in range(100):
            system.tick("npc", 1)
        dormant_materialize_us = _time_us(lambda: system.observe("npc"), repeats=1)

        start = time.perf_counter_ns()
        for _ in range(40):
            system.tick("npc", 1)
            system.observe("npc")
        active_tick_cycle_avg_us = (time.perf_counter_ns() - start) / 40 / 1000.0

        snapshot = system.snapshot()
        hot_snapshot_bytes = len(json.dumps(snapshot, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())
        assert system.cold_history is not None
        cold_history_bytes = system.cold_history.bytes()
        episode_archive_bytes = system.archive.path.stat().st_size
        projection_avg_us = _time_us(lambda: system.working_projections("npc"), repeats=9)
        full_scan_avg_us = _time_us(lambda: _cold_records(system), repeats=3)

        sample = ids[::max(1, len(ids) // 36)]
        start = time.perf_counter_ns()
        for episode_id in sample:
            system.recall_episode(episode_id, .25)
        recall_avg_us = (time.perf_counter_ns() - start) / len(sample) / 1000.0
        return {
            "episodes": len(ids),
            "event_avg_us": event_avg_us,
            "dormant_materialize_us": dormant_materialize_us,
            "active_tick_cycle_avg_us": active_tick_cycle_avg_us,
            "recall_avg_us": recall_avg_us,
            "projection_avg_us": projection_avg_us,
            "full_cold_scan_avg_us": full_scan_avg_us,
            "hot_snapshot_bytes": hot_snapshot_bytes,
            "episode_archive_bytes": episode_archive_bytes,
            "cold_history_bytes": cold_history_bytes,
            "cold_history_records": system.cold_history.count(),
            "total_persistent_bytes": hot_snapshot_bytes + episode_archive_bytes + cold_history_bytes,
            "hot_history_counts": system.hot_history_counts(),
            "manifest": system.cold_history.manifest(),
        }
    finally:
        system.close()


def _lossless_equivalence(root: Path) -> dict:
    control = optimized_factory("ghost_lazy_sparse", root / "control", "lossless-control")
    compact = compact_factory("ghost_compact_balanced", root / "compact", "lossless-compact")
    try:
        _populate(control, 96)
        _populate(compact, 96)
        control.snapshot()
        compact_snapshot = compact.snapshot()
        left = _cold_records(control)
        right = _cold_records(compact)
        projections_control = control.working_projections("npc")
        projections_compact = compact.working_projections("npc")
        before_observe = compact.observe("npc")
        compact.close()
        compact = compact_factory(
            "ghost_compact_balanced",
            root / "compact",
            "lossless-compact",
            snapshot=compact_snapshot,
        )
        after_observe = compact.observe("npc")
        return {
            "full_cold_records_exact": left == right,
            "projection_exact": projections_control == projections_compact,
            "restore_observation_exact": before_observe == after_observe,
            "records": sum(len(rows) for rows in right.values()),
        }
    finally:
        control.close()
        compact.close()


def _integrity_probe(root: Path) -> dict:
    path = root / "integrity.sqlite"
    archive = CompactColdHistoryArchive(path, compression_level=6)
    record = {"sequence": 1, "transitions": {"threat": {"after": .8}}}
    archive.put("interpretation", "npc", record)
    manifest = archive.manifest()
    archive.verify_manifest(manifest)
    archive._db.execute(
        "UPDATE history SET projection_json='[\"tampered\"]' WHERE subsystem='interpretation' AND agent='npc' AND sequence=1"
    )
    projection_tamper_detected = False
    try:
        archive.projection_rows("interpretation", "npc")
    except RuntimeError:
        projection_tamper_detected = True
    archive._db.rollback()
    archive.close()

    archive = CompactColdHistoryArchive(path, compression_level=6)
    archive._db.execute(
        "UPDATE history SET payload_z=? WHERE subsystem='interpretation' AND agent='npc' AND sequence=1",
        (b"not-zlib",),
    )
    archive._db.commit()
    payload_tamper_detected = False
    try:
        archive.records("interpretation", "npc")
    except RuntimeError:
        payload_tamper_detected = True
    manifest_tamper_detected = False
    try:
        archive.verify_manifest({**manifest, "records": 999})
    except Exception:
        manifest_tamper_detected = True
    archive.close()
    return {
        "projection_tamper_detected": projection_tamper_detected,
        "payload_tamper_detected": payload_tamper_detected,
        "manifest_mismatch_detected": manifest_tamper_detected,
    }


def _scale_probe(root: Path, agents: int = 32) -> dict:
    seed = optimized_factory("ghost_lazy_sparse", root / "seed", "scale-seed")
    try:
        _populate(seed, 120)
        seed.snapshot()
        records = _cold_records(seed)
    finally:
        seed.close()

    stores = {"stage7_json": ColdHistoryArchive(root / "scale-stage7.sqlite")}
    for kind, level in COMPRESSION_LEVELS.items():
        stores[kind] = CompactColdHistoryArchive(root / f"scale-{kind}.sqlite", compression_level=level)
    try:
        start = time.perf_counter_ns()
        for agent_index in range(agents):
            agent = f"npc-{agent_index:03d}"
            for subsystem, rows in records.items():
                for record in rows:
                    stores["stage7_json"].put(subsystem, agent, record)
        stage7_write_us = (time.perf_counter_ns() - start) / 1000.0
        rows = {}
        for kind in VARIANTS:
            start = time.perf_counter_ns()
            store = stores[kind]
            for agent_index in range(agents):
                agent = f"npc-{agent_index:03d}"
                for subsystem, values in records.items():
                    for record in values:
                        store.put(subsystem, agent, record)
            write_us = (time.perf_counter_ns() - start) / 1000.0
            rows[kind] = {"write_total_us": write_us}
        expected = agents * sum(len(values) for values in records.values())
        stage7_manifest = stores["stage7_json"].manifest()
        control_bytes = stores["stage7_json"].bytes()
        out = {
            "agents": agents,
            "records_per_agent": sum(len(values) for values in records.values()),
            "expected_records": expected,
            "stage7_json": {
                "records": stores["stage7_json"].count(),
                "bytes": control_bytes,
                "write_total_us": stage7_write_us,
                "manifest_records": stage7_manifest["records"],
            },
            "compact": {},
        }
        for kind in VARIANTS:
            store = stores[kind]
            manifest = store.manifest()
            size = store.bytes()
            out["compact"][kind] = {
                "records": store.count(),
                "bytes": size,
                "bytes_vs_stage7_json": _ratio(size, control_bytes),
                "write_total_us": rows[kind]["write_total_us"],
                "write_vs_stage7_json": _ratio(rows[kind]["write_total_us"], stage7_write_us),
                "manifest_records": manifest["records"],
            }
        return out
    finally:
        for store in stores.values():
            store.close()


def _ratio(value: float, reference: float) -> float | None:
    return None if reference == 0 else value / reference


def build_result(root: str | Path, stage6_report: dict, stage7_report: dict) -> dict:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    if stage7_report.get("strict_verdict") != "LAZY_PLUS_SPARSE_PRESERVES_STAGE6_VALUE_OPTIMIZATION_PATH_SURVIVES":
        raise RuntimeError("Stage-8 requires successful Stage-7 lazy+sparse evidence")
    s7 = stage7_report["engineering"]["ghost_lazy_sparse"]
    current = stage7_report["engineering"]["ghost_current"]

    quality = {kind: run_stage6_quality_for_compact(kind, root / f"{kind}-quality") for kind in VARIANTS}
    deterministic = {}
    subset_names = (
        "episode_specific_affect",
        "betrayal_affect_mode_resolution",
        "ambiguous_recall_inertness",
        "restart_behavior_identity",
    )
    for kind in VARIANTS:
        with patched_stage6_factory(kind) as scenarios:
            first = {name: dict(scenarios.SCENARIOS)[name](kind, root / f"{kind}-det-a" / name) for name in subset_names}
            second = {name: dict(scenarios.SCENARIOS)[name](kind, root / f"{kind}-det-b" / name) for name in subset_names}
        deterministic[kind] = first == second

    frozen_baseline = stage6_report["quality"]["baseline"]
    preservation = {}
    for kind, packet in quality.items():
        ablation = _foreground_ablation(frozen_baseline, packet)
        preservation[kind] = {
            "quality_25_of_26": packet["passed"] == 25 and packet["total"] == 26,
            "two_stage6_ghost_only_wins_preserved": _wins_preserved(packet),
            "foreground_ablation_preserved": bool(ablation["equalized_without_foreground"]),
            "deterministic": bool(deterministic[kind]),
        }

    engineering = {kind: _engineering(kind, root / f"{kind}-engineering") for kind in VARIANTS}
    ratios_to_stage7 = {}
    for kind, row in engineering.items():
        ratios_to_stage7[kind] = {
            key: _ratio(row[key], s7[key])
            for key in (
                "event_avg_us",
                "dormant_materialize_us",
                "active_tick_cycle_avg_us",
                "recall_avg_us",
                "hot_snapshot_bytes",
                "episode_archive_bytes",
                "cold_history_bytes",
                "total_persistent_bytes",
            )
        }
        ratios_to_stage7[kind]["total_vs_current_ghost"] = _ratio(row["total_persistent_bytes"], current["total_persistent_bytes"])

    lossless = _lossless_equivalence(root / "lossless")
    integrity = _integrity_probe(root / "integrity")
    scale = _scale_probe(root / "scale")
    viable = [
        kind for kind in VARIANTS
        if all(preservation[kind].values())
        and engineering[kind]["total_persistent_bytes"] <= current["total_persistent_bytes"]
    ]
    if viable and all(lossless.values()) and all(integrity.values()):
        verdict = "LOSSLESS_COLD_COMPACTION_PRESERVES_STAGE6_VALUE_AND_BEATS_CURRENT_GHOST_TOTAL_PERSISTENT_COST"
    elif any(all(preservation[k].values()) for k in VARIANTS):
        verdict = "COLD_COMPACTION_PRESERVES_VALUE_BUT_STORAGE_TARGET_NOT_CLOSED"
    else:
        verdict = "COLD_COMPACTION_FAILS_STAGE6_VALUE_PRESERVATION"

    return {
        "stage": STAGE,
        "stage7_reference": {
            "strict_verdict": stage7_report["strict_verdict"],
            "lazy_sparse": s7,
            "current": current,
        },
        "representation_contract": {
            "full_history_payload_retained_losslessly": True,
            "projection_index_contains_only_association_tokens": True,
            "projection_budget_unchanged": 3,
            "projection_thresholds_unchanged": stage7_report["projection_gate"],
            "compression_levels_tested": dict(COMPRESSION_LEVELS),
        },
        "quality": quality,
        "preservation": preservation,
        "engineering": engineering,
        "ratios_to_stage7_lazy_sparse": ratios_to_stage7,
        "lossless_equivalence": lossless,
        "integrity": integrity,
        "scale_probe": scale,
        "variants_meeting_value_and_total_storage_target": viable,
        "strict_verdict": verdict,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root")
    parser.add_argument("--stage6-report", required=True)
    parser.add_argument("--stage7-report", required=True)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    stage6_report = json.loads(Path(args.stage6_report).read_text(encoding="utf-8"))
    stage7_report = json.loads(Path(args.stage7_report).read_text(encoding="utf-8"))
    root = Path(args.root) if args.root else Path(tempfile.mkdtemp(prefix="ghost-stage8-"))
    result = build_result(root, stage6_report, stage7_report)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
