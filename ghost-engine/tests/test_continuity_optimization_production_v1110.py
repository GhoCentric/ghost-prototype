from __future__ import annotations

import copy
import json
from pathlib import Path
import sqlite3

import pytest

from ghost.api import GhostAPI
from ghost.continuity_history import (
    COLD_HISTORY_LIMIT,
    COMPRESSION_LEVEL,
    CONTINUITY_HISTORY_MANIFEST_SCHEMA,
    CONTINUITY_HISTORY_SCHEMA,
    CompactContinuityHistoryArchive,
    PendingContinuityHistory,
)
from ghost.continuity_optimization import (
    CONTINUITY_OPTIMIZATION_SCHEMA,
    HOT_HISTORY_KEEP,
    PROJECTION_BUDGET,
    PROJECTION_ENTER,
    PROJECTION_EXIT,
    ContinuityOptimizationRuntime,
)
from ghost.episode_store import EpisodeIntegrityError, SQLiteEpisodeArchive


def _record(sequence: int, *, subsystem: str = "interpretation", token: str = "respect") -> dict:
    if subsystem == "interpretation":
        return {
            "sequence": sequence,
            "transitions": {token: {"effective_impulse": 0.5, "level_after": 0.5}},
        }
    if subsystem == "emotion":
        return {
            "sequence": sequence,
            "effective_impulses": {token: 0.5},
        }
    if subsystem == "attention":
        return {
            "sequence": sequence,
            "underlying_salience": {token: 0.5},
        }
    raise AssertionError(subsystem)


def _registered_api(path: Path, agent: str = "npc") -> tuple[GhostAPI, SQLiteEpisodeArchive]:
    store = SQLiteEpisodeArchive(path)
    api = GhostAPI(episode_store=store)
    api.register_emotional_agent(
        agent,
        initial={"anger": 0.05, "fear": 0.02, "grief": 0.05, "hope": 0.15},
        baseline={"anger": 0.05, "fear": 0.02, "grief": 0.05, "hope": 0.15},
        inertia={"anger": 0.88, "fear": 0.86, "grief": 0.94, "hope": 0.92},
    )
    api.register_interpretation_agent(agent, initial={"respect": 0.0, "betrayal": 0.0})
    api.configure_interpretation_rule(agent, "action:respect_event", {"respect": 1.0})
    api.configure_interpretation_rule(agent, "action:betrayal_event", {"betrayal": 1.0})
    api.register_attention_agent(agent)
    return api, store


def _event(api: GhostAPI, agent: str = "npc", *, action: str = "respect_event", source: str = "s") -> dict:
    return api.continuity_event(
        agent,
        action,
        intensity=0.6,
        source=source,
        emotion_event="gift" if action == "respect_event" else "betrayal",
        emotion_intensity=0.5,
        signals={"interpretation_impulse": 0.6},
    )


def test_configure_interpretation_rule_preserves_public_return_contract(tmp_path):
    api, store = _registered_api(tmp_path / "episodes.sqlite")
    rule = api.configure_interpretation_rule(
        "npc",
        "action:release_coverage_probe",
        {"respect": 0.25},
    )
    assert rule == {
        "agent": "npc",
        "feature": "action:release_coverage_probe",
        "pressures": {"respect": 0.25},
    }
    assert "history" not in rule
    store.close()


def test_compact_history_archive_roundtrip_trim_integrity_and_validation(tmp_path):
    path = tmp_path / "cold.sqlite"
    archive = CompactContinuityHistoryArchive(path)
    assert archive.count() == 0
    archive.store_batch([])
    assert archive.count() == 0
    assert COMPRESSION_LEVEL == 6

    with pytest.raises(ValueError):
        archive.store_batch([("unknown", "npc", _record(1))])
    with pytest.raises(ValueError):
        archive.store_batch([("interpretation", "npc", {"sequence": 0, "transitions": {}})])
    with pytest.raises(ValueError):
        archive.store_batch([("interpretation", "npc", {"sequence": True, "transitions": {}})])
    with pytest.raises(ValueError):
        archive.store_batch([("interpretation", "npc", {"sequence": 1, "transitions": []})])

    rows = [
        ("interpretation", "npc", _record(index, token=f"d{index}"))
        for index in range(1, COLD_HISTORY_LIMIT + 3)
    ]
    archive.store_batch(rows)
    assert archive.count() == COLD_HISTORY_LIMIT
    records = archive.records("interpretation", "npc")
    assert records[0]["sequence"] == 3
    assert records[-1]["sequence"] == COLD_HISTORY_LIMIT + 2
    records[0]["transitions"].clear()
    assert archive.records("interpretation", "npc")[0]["transitions"]

    # Identical duplicates are idempotent; different content at one sequence is not.
    latest = rows[-1]
    archive.store_batch([latest])
    collision = copy.deepcopy(latest[2])
    collision["transitions"] = {"other": {"effective_impulse": 0.5, "level_after": 0.5}}
    with pytest.raises(EpisodeIntegrityError):
        archive.store_batch([("interpretation", "npc", collision)])

    projection = archive.projection_rows("interpretation", "npc")[-1]
    assert projection[0] == COLD_HISTORY_LIMIT + 2
    assert projection[1] == [f"d{COLD_HISTORY_LIMIT + 2}"]

    manifest = archive.manifest()
    assert manifest["schema"] == CONTINUITY_HISTORY_MANIFEST_SCHEMA
    assert manifest["archive_schema"] == CONTINUITY_HISTORY_SCHEMA
    assert manifest["level"] == 6
    archive.verify_manifest(copy.deepcopy(manifest))
    bad = copy.deepcopy(manifest)
    bad["record_count"] += 1
    with pytest.raises(EpisodeIntegrityError):
        archive.verify_manifest(bad)

    seq = COLD_HISTORY_LIMIT + 2
    archive._con.execute(
        "UPDATE history SET projection_json='[]' WHERE subsystem='interpretation' AND agent='npc' AND sequence=?",
        (seq,),
    )
    archive._con.commit()
    with pytest.raises(EpisodeIntegrityError):
        archive.projection_rows("interpretation", "npc")
    archive.close()

    # Constructor validation closes its connection and rejects missing/wrong schemas.
    with pytest.raises(EpisodeIntegrityError):
        CompactContinuityHistoryArchive(tmp_path / "missing.sqlite", create=False)
    wrong = tmp_path / "wrong.sqlite"
    con = sqlite3.connect(wrong)
    con.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
    con.execute("INSERT INTO metadata VALUES('schema','wrong')")
    con.commit(); con.close()
    with pytest.raises(EpisodeIntegrityError):
        CompactContinuityHistoryArchive(wrong, create=False)


def test_compact_history_payload_tamper_and_invalid_projection_json(tmp_path):
    archive = CompactContinuityHistoryArchive(tmp_path / "cold.sqlite")
    archive.store_batch([("emotion", "npc", _record(1, subsystem="emotion", token="hope"))])
    archive._con.execute(
        "UPDATE history SET payload_z=? WHERE subsystem='emotion' AND agent='npc' AND sequence=1",
        (sqlite3.Binary(b"not-zlib"),),
    )
    archive._con.commit()
    with pytest.raises(EpisodeIntegrityError):
        archive.records("emotion", "npc")
    archive.close()

    archive = CompactContinuityHistoryArchive(tmp_path / "cold2.sqlite")
    archive.store_batch([("attention", "npc", _record(1, subsystem="attention", token="emotion:hope"))])
    archive._con.execute(
        "UPDATE history SET projection_json='{' , projection_sha256=? WHERE subsystem='attention' AND agent='npc' AND sequence=1",
        (__import__("hashlib").sha256(b"{").hexdigest(),),
    )
    archive._con.commit()
    with pytest.raises(EpisodeIntegrityError):
        archive.projection_rows("attention", "npc")
    archive.close()


def test_lazy_tick_materializes_exactly_on_read_and_does_not_wake_other_agents(tmp_path):
    api, store = _registered_api(tmp_path / "episodes.sqlite", "a")
    api.register_emotional_agent("b")
    api.register_interpretation_agent("b", initial={"respect": 0.0})
    api.configure_interpretation_rule("b", "action:respect_event", {"respect": 1.0})
    api.register_attention_agent("b")
    _event(api, "a", source="a0")
    _event(api, "b", source="b0")

    receipt_a = api.continuity_tick("a", 7)
    receipt_b = api.continuity_tick("b", 11)
    assert receipt_a["deferred"] and receipt_a["pending_steps"] == 7
    assert receipt_b["deferred"] and receipt_b["pending_steps"] == 11
    assert api._continuity_optimization.has_pending("a")
    assert api._continuity_optimization.has_pending("b")

    # An event for a materializes only a; b remains dormant and cheap.
    _event(api, "a", source="a1")
    assert not api._continuity_optimization.has_pending("a")
    assert api._continuity_optimization.has_pending("b")

    before_b = copy.deepcopy(api.continuity._agents["b"])
    state_b = api.continuity_state("b")
    assert not api._continuity_optimization.has_pending("b")
    assert state_b != before_b
    store.close()


def test_lazy_tick_batches_repeated_calls_and_first_tick_registers_agent(tmp_path):
    api, store = _registered_api(tmp_path / "episodes.sqlite")
    _event(api)
    first = api.continuity_tick("npc", 2)
    second = api.continuity_tick("npc", 3)
    assert first["pending_steps"] == 2 and first["pending_calls"] == 1
    assert second["pending_steps"] == 5 and second["pending_calls"] == 2
    api.continuity_state("npc")
    assert not api._continuity_optimization.has_pending("npc")

    fresh = GhostAPI(episode_store=None)
    receipt = fresh.continuity_tick("new", 1)
    assert receipt["pending_steps"] == 1
    assert fresh.continuity.get_state("new") is not None
    with pytest.raises(ValueError):
        fresh.continuity_tick("new", 0)
    store.close()


def test_sparse_hot_history_preserves_full_public_history_and_snapshot_pairing(tmp_path):
    api, store = _registered_api(tmp_path / "episodes.sqlite")
    for index in range(70):
        _event(api, source=f"source-{index}")

    counts = api._continuity_optimization.hot_history_counts()
    assert counts == {"interpretation": 1, "emotion": 1, "attention": 1}
    assert len(api.interpretation_state("npc")["history"]) == 64
    assert len(api.emotional_state("npc")["history"]) == 64
    assert len(api.attention_state("npc")["history"]) == 64

    snapshot = api.snapshot()
    continuity_packet = snapshot["continuity"]
    assert set(continuity_packet) == {
        "runtime", "episode_archive", "history_archive", "optimization"
    }
    assert continuity_packet["optimization"] == {
        "schema": CONTINUITY_OPTIMIZATION_SCHEMA,
        "compression_level": 6,
        "hot_history_keep": 1,
        "projection_budget": 3,
        "projection_enter": PROJECTION_ENTER,
        "projection_exit": PROJECTION_EXIT,
    }
    assert max(
        len(snapshot[name]["agents"]["npc"]["history"])
        for name in ("emotions", "interpretations", "attention")
    ) <= HOT_HISTORY_KEEP

    restored = GhostAPI.from_snapshot(copy.deepcopy(snapshot), episode_store=store)
    assert restored.interpretation_state("npc") == api.interpretation_state("npc")
    assert restored.emotional_state("npc") == api.emotional_state("npc")
    assert restored.attention_state("npc") == api.attention_state("npc")
    assert restored.snapshot() == snapshot
    store.close()


def test_legacy_snapshot_migrates_only_with_empty_sidecar_and_unpaired_history_is_rejected(tmp_path):
    # Build a legacy snapshot without the optimization keys using a no-store API.
    legacy = GhostAPI()
    legacy.register_emotional_agent("npc")
    legacy.register_interpretation_agent("npc", initial={"respect": 0.0})
    legacy.register_attention_agent("npc")
    legacy._ensure_continuity_agent("npc")
    legacy_snapshot = legacy.snapshot()
    legacy_packet = legacy_snapshot["continuity"]
    legacy_snapshot["continuity"] = {
        "runtime": legacy_packet["runtime"],
        "episode_archive": None,
    }

    restored = GhostAPI.from_snapshot(copy.deepcopy(legacy_snapshot), episode_store=None)
    assert restored.continuity_state("npc") is not None

    store = SQLiteEpisodeArchive(tmp_path / "episodes.sqlite")
    api = GhostAPI(episode_store=store)
    api.register_emotional_agent("npc")
    api.register_interpretation_agent("npc", initial={"respect": 0.0})
    api.register_attention_agent("npc")
    api._ensure_continuity_agent("npc")
    # Put one valid diagnostic record in the sidecar. A fresh runtime may share
    # the causal episode archive, but it must not consume or mutate unpaired cold
    # diagnostic history. It falls back to ordinary hot history until restored
    # from a matching optimized snapshot.
    api._continuity_optimization.history.store_batch([
        ("interpretation", "npc", _record(1))
    ])
    fresh = GhostAPI(episode_store=store)
    assert fresh._continuity_optimization.history is None
    assert api._continuity_optimization.history.count() == 1
    store.close()


def test_snapshot_rejects_history_and_optimization_mismatch(tmp_path):
    api, store = _registered_api(tmp_path / "episodes.sqlite")
    for index in range(4):
        _event(api, source=f"s{index}")
    snapshot = api.snapshot()

    bad = copy.deepcopy(snapshot)
    bad["continuity"]["optimization"]["compression_level"] = 9
    with pytest.raises(EpisodeIntegrityError):
        GhostAPI.from_snapshot(bad, episode_store=store)

    bad = copy.deepcopy(snapshot)
    bad["continuity"]["history_archive"]["record_count"] += 1
    with pytest.raises(EpisodeIntegrityError):
        GhostAPI.from_snapshot(bad, episode_store=store)

    bad = copy.deepcopy(snapshot)
    bad["continuity"]["history_archive"] = []
    with pytest.raises(ValueError):
        GhostAPI.from_snapshot(bad, episode_store=store)
    store.close()


def test_deferred_compaction_keeps_hot_path_live_and_snapshot_is_strict(tmp_path, monkeypatch):
    api, store = _registered_api(tmp_path / "episodes.sqlite")
    _event(api, source="first")
    history = api._continuity_optimization.history
    assert history is not None
    original = history.store_batch

    def fail(_rows):
        raise sqlite3.OperationalError("synthetic cold-store outage")

    monkeypatch.setattr(history, "store_batch", fail)
    packet = _event(api, source="second")
    assert packet["episodes"]
    runtime = api._continuity_optimization
    assert runtime._pending_history._rows
    assert len(api.interpretations._agents["npc"]["history"]) == HOT_HISTORY_KEEP
    assert len(api.interpretation_state("npc")["history"]) >= 2
    with pytest.raises(RuntimeError):
        runtime.history_manifest()
    with pytest.raises(RuntimeError):
        runtime.optimization_packet()
    pending = copy.deepcopy(runtime._pending_history._rows)
    with pytest.raises(sqlite3.OperationalError):
        api.snapshot()
    assert runtime._pending_history._rows == pending

    monkeypatch.setattr(history, "store_batch", original)
    snapshot = api.snapshot()
    assert runtime._pending_history._rows == {}
    assert snapshot["continuity"]["history_archive"]["record_count"] > 0
    store.close()


def test_event_failure_restores_target_without_materializing_unrelated_pending_state(tmp_path, monkeypatch):
    api, store = _registered_api(tmp_path / "episodes.sqlite", "a")
    api.register_emotional_agent("b")
    api.register_interpretation_agent("b", initial={"respect": 0.0})
    api.configure_interpretation_rule("b", "action:respect_event", {"respect": 1.0})
    api.register_attention_agent("b")
    _event(api, "a", source="a0")
    _event(api, "b", source="b0")
    api.continuity_tick("a", 5)
    api.continuity_tick("b", 9)

    before_a = api._continuity_agent_checkpoint("a")
    before_b = api._continuity_agent_checkpoint("b")

    def fail_put(_record):
        raise RuntimeError("synthetic episode failure")

    monkeypatch.setattr(store, "put_record", fail_put)
    with pytest.raises(RuntimeError):
        _event(api, "a", source="fail")

    after_a = api._continuity_agent_checkpoint("a")
    after_b = api._continuity_agent_checkpoint("b")
    for key in before_a:
        if key == "continuity_state":
            continue
        assert after_a[key] == before_a[key]
    assert api.continuity.get_state("a") == {
        "agent": "a",
        "release_rate": before_a["continuity_state"]["release_rate"],
        "activation": before_a["continuity_state"]["activation"],
        "current_leader": before_a["continuity_state"]["foreground"].current_leader,
        "switch_threshold": before_a["continuity_state"]["foreground"].threshold,
    }
    for key in before_b:
        if key == "continuity_state":
            continue
        assert after_b[key] == before_b[key]
    assert api.continuity.get_state("b")["activation"] == before_b["continuity_state"]["activation"]
    store.close()


def test_projection_hysteresis_budget_and_attention_token_paths(tmp_path):
    api, store = _registered_api(tmp_path / "episodes.sqlite")
    runtime = api._continuity_optimization
    history = runtime.history
    assert history is not None

    history.store_batch([
        ("interpretation", "npc", _record(1, token="respect")),
        ("emotion", "npc", _record(2, subsystem="emotion", token="hope")),
        ("attention", "npc", _record(3, subsystem="attention", token="interpretation:respect")),
        ("attention", "npc", _record(4, subsystem="attention", token="emotion:hope")),
    ])
    api._ensure_continuity_agent("npc")
    api.continuity._agents["npc"]["activation"]["respect"] = min(1.0, PROJECTION_ENTER + 0.1)
    api.emotions._agents["npc"]["levels"]["hope"] = min(1.0, PROJECTION_ENTER + 0.15)
    hot = runtime.working_projections("npc")
    assert len(hot) == PROJECTION_BUDGET
    assert {row["subsystem"] for row in hot} <= {"interpretation", "emotion", "attention"}

    # Previously-active records use the lower exit threshold.
    api.continuity._agents["npc"]["activation"]["respect"] = (PROJECTION_ENTER + PROJECTION_EXIT) / 2
    api.emotions._agents["npc"]["levels"]["hope"] = (PROJECTION_ENTER + PROJECTION_EXIT) / 2
    held = runtime.working_projections("npc")
    assert held
    api.continuity._agents["npc"]["activation"]["respect"] = max(0.0, PROJECTION_EXIT - 0.01)
    api.emotions._agents["npc"]["levels"]["hope"] = max(0.0, PROJECTION_EXIT - 0.01)
    assert runtime.working_projections("npc") == []
    store.close()


def test_episode_store_close_owns_history_sidecar_lifecycle(tmp_path):
    store = SQLiteEpisodeArchive(tmp_path / "episodes.sqlite")
    api = GhostAPI(episode_store=store)
    history = api._continuity_optimization.history
    assert history is not None
    store.close()
    assert getattr(store, "_continuity_history_archive") is None
    with pytest.raises(sqlite3.ProgrammingError):
        history.count()


def test_optimization_runtime_without_sqlite_store_and_packet_validation():
    api = GhostAPI()
    runtime = api._continuity_optimization
    assert runtime.history is None
    assert runtime.history_manifest() is None
    assert runtime.working_projections("npc") == []
    assert runtime.compact("npc")
    assert runtime.compact_all()
    assert runtime.expanded_history("interpretation", "npc", [{"sequence": 1}], limit=64) == [{"sequence": 1}]
    packet = runtime.optimization_packet()
    ContinuityOptimizationRuntime.verify_optimization_packet(copy.deepcopy(packet))
    bad = copy.deepcopy(packet); bad["schema"] = "bad"
    with pytest.raises(EpisodeIntegrityError):
        ContinuityOptimizationRuntime.verify_optimization_packet(bad)


def test_cold_history_decode_and_projection_validation_branches(tmp_path):
    import hashlib
    import zlib

    def seeded(name: str) -> CompactContinuityHistoryArchive:
        archive = CompactContinuityHistoryArchive(tmp_path / name)
        archive.store_batch([("interpretation", "npc", _record(1))])
        return archive

    archive = seeded("hash.sqlite")
    archive._con.execute(
        "UPDATE history SET payload_sha256='0' WHERE subsystem='interpretation' AND agent='npc' AND sequence=1"
    )
    archive._con.commit()
    with pytest.raises(EpisodeIntegrityError):
        archive.records("interpretation", "npc")
    archive.close()

    archive = seeded("json.sqlite")
    payload = b"{"
    archive._con.execute(
        "UPDATE history SET payload_sha256=?,payload_z=? WHERE subsystem='interpretation' AND agent='npc' AND sequence=1",
        (hashlib.sha256(payload).hexdigest(), sqlite3.Binary(zlib.compress(payload, 6))),
    )
    archive._con.commit()
    with pytest.raises(EpisodeIntegrityError):
        archive.records("interpretation", "npc")
    archive.close()

    archive = seeded("shape.sqlite")
    payload = b"[]"
    archive._con.execute(
        "UPDATE history SET payload_sha256=?,payload_z=? WHERE subsystem='interpretation' AND agent='npc' AND sequence=1",
        (hashlib.sha256(payload).hexdigest(), sqlite3.Binary(zlib.compress(payload, 6))),
    )
    archive._con.commit()
    with pytest.raises(EpisodeIntegrityError):
        archive.records("interpretation", "npc")
    archive.close()

    archive = seeded("projection-shape.sqlite")
    projection = b"[1]"
    archive._con.execute(
        "UPDATE history SET projection_sha256=?,projection_json=? WHERE subsystem='interpretation' AND agent='npc' AND sequence=1",
        (hashlib.sha256(projection).hexdigest(), projection.decode()),
    )
    archive._con.commit()
    with pytest.raises(EpisodeIntegrityError):
        archive.projection_rows("interpretation", "npc")
    archive.close()


def test_optimization_constructor_cleanup_and_no_store_manifest_error(tmp_path):
    api = GhostAPI()
    with pytest.raises(EpisodeIntegrityError):
        ContinuityOptimizationRuntime(
            emotions=api.emotions,
            interpretations=api.interpretations,
            attention=api.attention,
            continuity=api.continuity,
            episode_store=None,
            history_manifest={},
        )

    store = SQLiteEpisodeArchive(tmp_path / "episodes.sqlite")
    assert getattr(store, "_continuity_history_archive", None) is None
    with pytest.raises(EpisodeIntegrityError):
        ContinuityOptimizationRuntime(
            emotions=api.emotions,
            interpretations=api.interpretations,
            attention=api.attention,
            continuity=api.continuity,
            episode_store=store,
            history_manifest={"wrong": True},
        )
    assert getattr(store, "_continuity_history_archive", None) is None
    store.close()


def test_materialize_edge_paths_and_pending_packet_guard(tmp_path):
    api = GhostAPI()
    runtime = api._continuity_optimization
    runtime.schedule("missing", 1)
    with pytest.raises(RuntimeError):
        runtime.materialize("missing")
    with pytest.raises(RuntimeError):
        runtime.optimization_packet()
    runtime._pending_steps.clear(); runtime._pending_calls.clear()

    # Continuity with attention but no emotion exercises the no-emotion branch.
    api.attention.register_agent("attention-only")
    api.continuity.register_agent("attention-only", release_rate=0.48, switch_threshold=0.05)
    runtime.schedule("attention-only", 2)
    runtime.materialize("attention-only")
    assert not runtime.has_pending("attention-only")

    # Continuity with no attention exercises the no-attention branch.
    api.continuity.register_agent("continuity-only", release_rate=0.48, switch_threshold=0.05)
    runtime.schedule("continuity-only", 2)
    runtime.materialize_all()
    assert not runtime.has_pending("continuity-only")

    store = SQLiteEpisodeArchive(tmp_path / "episodes.sqlite")
    stored = GhostAPI(episode_store=store)
    stored.continuity.register_agent("bare", release_rate=0.48, switch_threshold=0.05)
    assert stored._continuity_optimization.compact("bare")
    store.close()


def test_projection_score_direct_emotion_token_branch(tmp_path):
    api, store = _registered_api(tmp_path / "episodes.sqlite")
    api._ensure_continuity_agent("npc")
    api.emotions._agents["npc"]["levels"]["hope"] = 0.75
    assert api._continuity_optimization._projection_score(
        "attention", "npc", ["emotion:hope", "other"]
    ) == 0.75
    store.close()


def test_modified_public_layer_methods_materialize_compact_and_rollback(tmp_path):
    api, store = _registered_api(tmp_path / "episodes.sqlite")
    _event(api, source="seed")
    api.continuity_tick("npc", 3)
    one = api.tick_emotions("npc", steps=2)
    assert one["agents"][0]["state"]["history"]

    api.continuity_tick("npc", 2)
    all_agents = api.tick_emotions(None, steps=1)
    assert any(row["agent"] == "npc" for row in all_agents["agents"])

    meaning = api.evaluate_action_meaning(
        "npc", "respect_event", intensity=0.2, source="direct"
    )
    assert meaning["state"]["history"]
    attention = api.advance_attention(
        "npc", signals={"novelty": 0.2}, salience={"x": 0.4}, source="direct"
    )
    assert attention["agent"] == "npc"

    before_relationship = copy.deepcopy(api.get_relationship("source", "npc"))
    layered = api.apply_layered_event(
        "source", "npc", {"type": "gift", "intensity": 0.4}
    )
    assert layered["emotions"]["state"]["history"]
    after_success = copy.deepcopy(api.get_relationship("source", "npc"))
    assert after_success != before_relationship

    # A downstream emotion validation failure must rollback the relationship write.
    checkpoint = copy.deepcopy(api.get_relationship("source", "npc"))
    with pytest.raises(ValueError):
        api.apply_layered_event(
            "source",
            "npc",
            {"type": "gift", "intensity": 0.4},
            emotion_impulses={"anger": 2.0},
        )
    assert api.get_relationship("source", "npc") == checkpoint
    store.close()


def test_optimized_snapshot_invalid_packet_shape_and_attention_idle_validation(tmp_path):
    api, store = _registered_api(tmp_path / "episodes.sqlite")
    _event(api)
    snapshot = api.snapshot()
    bad = copy.deepcopy(snapshot)
    bad["continuity"]["optimization"] = []
    with pytest.raises(ValueError):
        GhostAPI.from_snapshot(bad, episode_store=store)

    with pytest.raises(ValueError):
        api.attention._advance_idle_time("npc", 0)
    with pytest.raises(ValueError):
        api.attention._advance_idle_time("npc", True)
    assert api.attention._advance_idle_time("missing", 1) is None
    store.close()


def test_one_agent_event_does_not_materialize_nineteen_dormant_agents():
    api = GhostAPI()
    agents = [f"npc-{index:02d}" for index in range(20)]
    for agent in agents:
        api.continuity_tick(agent, 5)

    target = agents[0]
    api.register_interpretation_agent(target, initial={"respect": 0.0})
    api.configure_interpretation_rule(target, "action:respect_event", {"respect": 1.0})
    api.register_attention_agent(target)
    api.register_emotional_agent(target)
    api.continuity_tick(target, 7)

    assert all(api._continuity_optimization.has_pending(agent) for agent in agents)
    api.continuity_event(
        target,
        "respect_event",
        intensity=0.5,
        source="single-active-agent",
        emotion_event="gift",
        emotion_intensity=0.4,
        signals={"interpretation_impulse": 0.5},
    )

    assert not api._continuity_optimization.has_pending(target)
    assert all(
        api._continuity_optimization.has_pending(agent)
        for agent in agents[1:]
    )


def test_pending_history_buffer_is_bounded_idempotent_and_validated():
    pending = PendingContinuityHistory()
    first = _record(1)
    pending.stage([("interpretation", "npc", first)])
    pending.stage([("interpretation", "npc", copy.deepcopy(first))])
    assert pending.records("interpretation", "npc") == [first]
    assert pending.projection_rows("interpretation", "npc") == [(1, ["respect"])]

    collision = copy.deepcopy(first)
    collision["transitions"] = {"other": {"effective_impulse": 0.5, "level_after": 0.5}}
    with pytest.raises(EpisodeIntegrityError):
        pending.stage([("interpretation", "npc", collision)])
    with pytest.raises(ValueError):
        pending.stage([("unknown", "npc", first)])

    pending.stage([
        ("interpretation", "npc", _record(index, token=f"d{index}"))
        for index in range(2, COLD_HISTORY_LIMIT + 3)
    ])
    rows = pending.rows()
    assert len(rows) == COLD_HISTORY_LIMIT
    assert rows[0][2]["sequence"] == 3
    assert rows[-1][2]["sequence"] == COLD_HISTORY_LIMIT + 2


def test_deferred_history_flush_preserves_public_state_and_restore(tmp_path):
    api, store = _registered_api(tmp_path / "episodes.sqlite")
    respect = _event(api, source="respect-1")
    betrayal = _event(api, action="betrayal_event", source="betrayal-1")
    api.recall_episode(respect["episodes"][0]["episode_id"], 0.7)
    api.recall_episode(betrayal["episodes"][0]["episode_id"], 0.6)
    _event(api, source="respect-2")

    runtime = api._continuity_optimization
    assert runtime._pending_history._rows
    assert runtime.hot_history_counts() == {
        "interpretation": 1, "emotion": 1, "attention": 1
    }
    before = {
        "interpretation": api.interpretation_state("npc"),
        "emotion": api.emotional_state("npc"),
        "attention": api.attention_state("npc"),
        "continuity": api.continuity_state("npc"),
    }
    assert runtime._pending_history._rows
    assert len(runtime.working_projections("npc")) <= PROJECTION_BUDGET

    snapshot = api.snapshot()
    assert runtime._pending_history._rows == {}
    after = {
        "interpretation": api.interpretation_state("npc"),
        "emotion": api.emotional_state("npc"),
        "attention": api.attention_state("npc"),
        "continuity": api.continuity_state("npc"),
    }
    assert after == before
    restored = GhostAPI.from_snapshot(copy.deepcopy(snapshot), episode_store=store)
    assert restored.interpretation_state("npc") == before["interpretation"]
    assert restored.emotional_state("npc") == before["emotion"]
    assert restored.attention_state("npc") == before["attention"]
    assert restored.continuity_state("npc") == before["continuity"]
    store.close()


def test_flush_failure_nonstrict_retains_pending_and_strict_staging_rejects_collision(tmp_path, monkeypatch):
    api, store = _registered_api(tmp_path / "episodes.sqlite")
    _event(api, source="one")
    _event(api, source="two")
    runtime = api._continuity_optimization
    history = runtime.history
    assert history is not None and runtime._pending_history._rows
    original = history.store_batch

    def fail(_rows):
        raise sqlite3.OperationalError("synthetic flush failure")

    monkeypatch.setattr(history, "store_batch", fail)
    pending = copy.deepcopy(runtime._pending_history._rows)
    assert runtime.flush_history() is False
    assert runtime._pending_history._rows == pending
    with pytest.raises(sqlite3.OperationalError):
        runtime.flush_history(strict=True)
    monkeypatch.setattr(history, "store_batch", original)
    assert runtime.flush_history(strict=True)
    assert runtime._pending_history._rows == {}

    _event(api, source="three")
    assert runtime._pending_history._rows
    # Direct strict compaction is a flush boundary too.
    assert runtime.compact("npc", strict=True)
    assert runtime._pending_history._rows == {}

    no_store = GhostAPI()._continuity_optimization
    assert no_store.flush_history()
    store.close()


def test_pending_staging_integrity_failure_paths(tmp_path, monkeypatch):
    api, store = _registered_api(tmp_path / "episodes.sqlite")
    _event(api, source="seed")
    runtime = api._continuity_optimization
    state = api.interpretations._agents["npc"]
    extra = copy.deepcopy(state["history"][-1])
    extra["sequence"] += 100
    state["history"].append(extra)

    def fail_stage(_rows):
        raise EpisodeIntegrityError("synthetic pending collision")

    monkeypatch.setattr(runtime._pending_history, "stage", fail_stage)
    assert runtime.compact("npc") is False
    with pytest.raises(EpisodeIntegrityError):
        runtime.compact("npc", strict=True)

    monkeypatch.setattr(runtime, "compact", lambda _agent: False)
    with pytest.raises(EpisodeIntegrityError):
        runtime.compact_all(strict=True)
    store.close()
