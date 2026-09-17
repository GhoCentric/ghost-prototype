from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import zlib

import pytest

from continuity_benchmark_v1110.ghost_adapter import GhostArchiveMismatchError
from continuity_benchmark_v1110.stage8_cold_history_variants import (
    CompactColdHistoryArchive,
    compact_factory,
    patched_stage6_factory,
    run_stage6_quality_for_compact,
)


def _record(sequence=1):
    return {"sequence": sequence, "transitions": {"threat": {"after": .8}}}


def test_compact_archive_validation_roundtrip_limit_and_manifest(tmp_path):
    with pytest.raises(ValueError, match="compression_level"):
        CompactColdHistoryArchive(tmp_path / "bad.sqlite", compression_level=2)
    archive = CompactColdHistoryArchive(tmp_path / "ok.sqlite", compression_level=6)
    for bad in (True, 0, -1, "1"):
        with pytest.raises(ValueError, match="sequence"):
            archive.put("interpretation", "npc", {"sequence": bad, "transitions": {}})
    with pytest.raises(ValueError, match="unknown"):
        archive.put("other", "npc", _record())
    with pytest.raises(ValueError, match="mapping"):
        archive.put("interpretation", "npc", {"sequence": 1, "transitions": []})

    for sequence in range(1, 67):
        archive.put("interpretation", "npc", _record(sequence))
    archive.put("emotion", "npc", {"sequence": 1, "effective_impulses": {"fear": .2}})
    archive.put("attention", "npc", {"sequence": 1, "underlying_salience": {"emotion:fear": .2, "x": .1}})
    assert archive.count() == 66
    assert archive.records("interpretation", "npc")[0]["sequence"] == 3
    rows = archive.projection_rows("emotion", "npc")
    assert rows == [(1, ["fear"])]
    assert archive.bytes() > 0
    manifest = archive.manifest()
    archive.verify_manifest(manifest)
    with pytest.raises(GhostArchiveMismatchError):
        archive.verify_manifest({**manifest, "records": 0})
    archive.close()


def test_compact_archive_integrity_failures(tmp_path):
    path = tmp_path / "integrity.sqlite"
    archive = CompactColdHistoryArchive(path, compression_level=1)
    archive.put("interpretation", "npc", _record())
    archive.manifest()

    archive._db.execute("UPDATE history SET payload_z=?", (b"bad",)); archive._db.commit()
    with pytest.raises(RuntimeError, match="decompression"):
        archive.records("interpretation", "npc")
    payload = json.dumps(_record(), sort_keys=True, separators=(",", ":")).encode()
    archive._db.execute("UPDATE history SET payload_z=?,payload_sha256=?", (zlib.compress(payload), "0" * 64)); archive._db.commit()
    with pytest.raises(RuntimeError, match="payload integrity"):
        archive.records("interpretation", "npc")
    list_payload = b"[]"
    archive._db.execute(
        "UPDATE history SET payload_z=?,payload_sha256=?",
        (zlib.compress(list_payload), hashlib.sha256(list_payload).hexdigest()),
    ); archive._db.commit()
    with pytest.raises(RuntimeError, match="not a mapping"):
        archive.records("interpretation", "npc")

    archive._db.execute("UPDATE history SET projection_json='[]',projection_sha256='bad'"); archive._db.commit()
    with pytest.raises(RuntimeError, match="projection integrity"):
        archive.projection_rows("interpretation", "npc")
    text = json.dumps([1], separators=(",", ":"))
    archive._db.execute(
        "UPDATE history SET projection_json=?,projection_sha256=?",
        (text, hashlib.sha256(text.encode()).hexdigest()),
    ); archive._db.commit()
    with pytest.raises(RuntimeError, match="projection is invalid"):
        archive.projection_rows("interpretation", "npc")
    archive.close()


def test_compact_adapter_projection_scoring_restore_and_factory(tmp_path):
    with pytest.raises(ValueError, match="unknown Stage-8"):
        compact_factory("nope", tmp_path, "x")
    from continuity_benchmark_v1110.stage8_cold_history_variants import CompactColdGhostAdapter
    with pytest.raises(ValueError, match="unknown Stage-8"):
        CompactColdGhostAdapter(tmp_path / "direct.sqlite", variant="nope")
    system = compact_factory("ghost_compact_balanced", tmp_path, "a")
    try:
        assert system.variant_name == "ghost_compact_balanced"
        row = system.event("npc", source="fear", dimension="threat", meaning_delta=.8, relevance=.8, emotion_profile={"fear": .9}, consequence=0.0)
        for index in range(4):
            system.event("npc", source=f"n{index}", dimension="respect", meaning_delta=.01, relevance=.01, emotion_profile={"hope": .01}, consequence=0.0)
        system._sparsify_all()
        assert system._projection_score("interpretation", "npc", ["threat"]) >= 0
        assert system._projection_score("emotion", "npc", ["fear"]) >= 0
        assert system._projection_score("attention", "npc", ["interpretation:threat", "emotion:fear", "other"]) >= 0
        projections = system.working_projections("npc")
        assert len(projections) <= 3
        snapshot = system.snapshot()
        observed = system.observe("npc")
    finally:
        system.close()
    restored = compact_factory("ghost_compact_balanced", tmp_path, "a", snapshot=snapshot)
    try:
        assert restored.observe("npc") == observed
        assert restored.recall_episode(row["episode_id"], .5)["status"] == "explicit_episode"
        original = restored.cold_history
        restored.cold_history = None
        assert restored.working_projections("npc") == []
        restored.cold_history = object()
        with pytest.raises(RuntimeError, match="lost compact"):
            restored.working_projections("npc")
        restored.cold_history = original
    finally:
        restored.close()

    with patched_stage6_factory("ghost_compact_fast") as scenarios:
        candidate = scenarios.factory("ghost_compact_fast", tmp_path / "p", "c")
        candidate.close()
        baseline = scenarios.factory("baseline", tmp_path / "p", "b")
        baseline.close()


def test_run_stage6_quality_wrapper_without_full_suite(tmp_path, monkeypatch):
    from continuity_benchmark_v1110 import stage6_behavior_scenarios as scenarios
    monkeypatch.setattr(scenarios, "run_quality", lambda kind, root: {"kind": kind, "root": str(root)})
    out = run_stage6_quality_for_compact("ghost_compact_fast", tmp_path)
    assert out["kind"] == "ghost_compact_fast"
