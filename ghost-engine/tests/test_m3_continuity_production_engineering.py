from __future__ import annotations

import copy
import json
from pathlib import Path
import sqlite3

import pytest

from ghost.api import GhostAPI
from ghost.continuity import ContinuityRuntime, PairwiseForeground
from ghost.episode_store import (
    EPISODE_ARCHIVE_SCHEMA,
    EpisodeCapacityError,
    EpisodeIntegrityError,
    SQLiteEpisodeArchive,
)


def _interpretation_entry(sequence=1, dimension="betrayal", effective=0.9, source="test"):
    return {
        "sequence": sequence,
        "source": source,
        "transitions": {
            dimension: {
                "effective_impulse": effective,
                "level_after": max(0.0, min(1.0, effective)),
            }
        },
    }


def _emotion_entry(sequence=1, event="hurt", profile=None):
    return {
        "sequence": sequence,
        "event": event,
        "profile": {"anger": 0.7, "fear": 0.2, "zero": 0.0} if profile is None else profile,
    }


def _record(sequence=1, emotion_sequence=1, dimension="betrayal", agent="b", profile=None):
    return SQLiteEpisodeArchive.record_from_entries(
        agent=agent,
        dimension=dimension,
        interpretation_entry=_interpretation_entry(sequence, dimension),
        emotion_entry=None if emotion_sequence is None else _emotion_entry(emotion_sequence, profile=profile),
    )


def _configured_api(path: Path, *, max_records=None):
    store = SQLiteEpisodeArchive(path, max_records=max_records)
    api = GhostAPI(episode_store=store)
    api.register_emotional_agent(
        "b",
        initial={"anger": 0.05, "fear": 0.02, "grief": 0.05, "hope": 0.15},
        baseline={"anger": 0.05, "fear": 0.02, "grief": 0.05, "hope": 0.15},
        inertia={"anger": 0.88, "fear": 0.86, "grief": 0.94, "hope": 0.92},
    )
    api.register_interpretation_agent(
        "b",
        initial={"betrayal": 0.0, "threat": 0.0},
    )
    api.configure_interpretation_rule("b", "betrayal_cue", {"betrayal": 0.9})
    api.configure_interpretation_rule("b", "threat_cue", {"threat": 0.7})
    api.register_attention_agent("b")
    return api, store


def test_pairwise_foreground_all_semantic_paths_and_validation():
    with pytest.raises(ValueError):
        PairwiseForeground(1.0)
    with pytest.raises(ValueError):
        PairwiseForeground(True)
    with pytest.raises(ValueError):
        PairwiseForeground(float("nan"))
    with pytest.raises(ValueError):
        PairwiseForeground(-0.1)
    with pytest.raises(ValueError):
        PairwiseForeground(0.05, " ")

    p = PairwiseForeground(0.05)
    assert p.raw_leader({}) == (None, 0.0)
    assert p.raw_leader({"x": 0.0}) == (None, 0.0)
    assert p.pairwise_advantage(0.0, 0.0) == 0.0
    assert p.step(0, {})["reason"] == "zero_vector"
    assert p.step(1, {"a": 0.7})["reason"] == "acquired"
    assert p.step(2, {"a": 0.8, "b": 0.2})["reason"] == "leader_holds"
    assert p.step(3, {"a": 0.0, "b": 0.7})["reason"] == "incumbent_inactive"
    assert p.step(4, {"b": 0.49, "c": 0.51})["reason"] == "hysteresis_retained"
    crossed = p.step(5, {"b": 0.40, "c": 0.60})
    assert crossed["reason"] == "threshold_crossed"
    assert crossed["resolved_leader"] == "c"
    assert p.step(6, {"z": 0.5})["reason"] == "acquired"

    for bad_tick in (True, -1, 1.2):
        with pytest.raises(ValueError):
            p.step(bad_tick, {})
    with pytest.raises(ValueError):
        p.step(0, [])
    with pytest.raises(ValueError):
        p.step(0, {" ": 0.2})
    with pytest.raises(ValueError):
        p.step(0, {"x": 2.0})
    with pytest.raises(ValueError):
        p.step(0, {"x": 0.1, " x ": 0.2})


def test_continuity_runtime_minimal_state_snapshot_and_validation():
    c = ContinuityRuntime()
    assert not c.has_state()
    assert c.agents() == []
    assert c.get_state("b") is None
    with pytest.raises(ValueError):
        c.recall("b", "x", 0.5)

    state = c.register_agent("b", release_rate=0.48, switch_threshold=0.05)
    assert c.has_state()
    assert c.agents() == ["b"]
    assert set(state) == {"agent", "release_rate", "activation", "current_leader", "switch_threshold"}
    c.register_agent("b", release_rate=0.48, switch_threshold=0.05)
    with pytest.raises(ValueError):
        c.register_agent("b", release_rate=0.47, switch_threshold=0.05)
    with pytest.raises(ValueError):
        c.register_agent("b", release_rate=0.48, switch_threshold=0.04)

    with pytest.raises(ValueError):
        c.ingest_interpretation_result("b", [])
    with pytest.raises(ValueError):
        c.ingest_interpretation_result("b", {"agent": "a", "transitions": {}})
    with pytest.raises(ValueError):
        c.ingest_interpretation_result("b", {"agent": "b", "transitions": []})
    with pytest.raises(ValueError):
        c.ingest_interpretation_result("b", {"agent": "b", "transitions": {"x": []}})
    with pytest.raises(ValueError):
        c.ingest_interpretation_result("b", {"agent": "b", "transitions": {"x": {"level_after": 0.5, "effective_impulse": True}}})
    with pytest.raises(ValueError):
        c.ingest_interpretation_result("b", {"agent": "b", "transitions": {"x": {"level_after": 0.5, "effective_impulse": 2.0}}})

    rows = c.ingest_interpretation_result(
        "b",
        {"agent": "b", "transitions": {"x": {"level_after": 0.8, "effective_impulse": -0.25}}},
    )
    assert rows[0]["relevance_impulse"] == 0.25
    assert c.recall("b", "x", 0.5)["activation_after"] > 0.5
    with pytest.raises(ValueError):
        c.recall("b", "x", 1.2)
    with pytest.raises(ValueError):
        c.tick_activation("b", steps=0)
    assert c.tick_activation("b", steps=2)["steps"] == 2

    with pytest.raises(ValueError):
        c.activation_aware_salience("b", {})
    bridge = {
        "salience": {"emotion:anger": 0.2, "interpretation:x": 0.99},
        "other": {"keep": True},
    }
    out = c.activation_aware_salience("b", bridge)
    assert out["other"] == {"keep": True}
    assert out["salience"]["emotion:anger"] == 0.2
    assert out["salience"]["interpretation:x"] == c.get_state("b")["activation"]["x"]
    assert bridge["salience"]["interpretation:x"] == 0.99
    c.resolve_foreground("b", out["salience"], sequence=7)

    snapshot = c.snapshot()
    assert "tick" not in snapshot
    restored = ContinuityRuntime.from_snapshot(copy.deepcopy(snapshot))
    assert restored.snapshot() == snapshot

    invalids = [
        None,
        {"schema_version": "1.0"},
        {"schema_version": "9", "agents": {}},
        {"schema_version": "1.0", "agents": []},
        {"schema_version": "1.0", "agents": {"b": []}},
        {"schema_version": "1.0", "agents": {"b": {"release_rate": 0.48, "switch_threshold": 0.05, "current_leader": None, "activation": []}}},
        {"schema_version": "1.0", "agents": {"b": {"release_rate": 0.48, "switch_threshold": 0.05, "current_leader": "interpretation:missing", "activation": {}}}},
        {"schema_version": "1.0", "agents": {"b": {"release_rate": 0.48, "switch_threshold": 0.05, "current_leader": None, "activation": {"x": 2.0}}}},
        {"schema_version": "1.0", "agents": {"b": {"release_rate": 0.48, "switch_threshold": 0.05, "current_leader": None, "activation": {"x": 0.2, " x ": 0.3}}}},
        {"schema_version": "1.0", "agents": {"b": {"release_rate": 0.48, "switch_threshold": 0.05, "current_leader": None, "activation": {}}, " b ": {"release_rate": 0.48, "switch_threshold": 0.05, "current_leader": None, "activation": {}}}},
    ]
    for invalid in invalids:
        with pytest.raises(ValueError):
            ContinuityRuntime.from_snapshot(invalid)


def test_episode_archive_record_validation_queries_capacity_and_mutation(tmp_path):
    with pytest.raises(ValueError):
        SQLiteEpisodeArchive(tmp_path / "bad-cap.sqlite", max_records=0)

    store = SQLiteEpisodeArchive(tmp_path / "episodes.sqlite", max_records=2)
    assert len(store) == 0
    assert store.resolve_dimension("b", "betrayal")["status"] == "missing"
    assert store.get("none") is None

    first = _record(1, 1)
    inserted = store.put_record(first)
    assert inserted["emotion_profile"] == {"anger": 0.7, "fear": 0.2}
    inserted["emotion_profile"]["anger"] = -1.0
    assert store.get(first["episode_id"])["emotion_profile"]["anger"] == 0.7
    assert store.put_record(first) == first | {"emotion_profile": {"anger": 0.7, "fear": 0.2}}

    collision = copy.deepcopy(first)
    collision["dimension"] = "threat"
    with pytest.raises(ValueError):
        store.put_record(collision)

    second = _record(2, None)
    store.put_record(second)
    ambiguous = store.resolve_dimension("b", "betrayal")
    assert ambiguous["status"] == "ambiguous"
    assert ambiguous["candidate_count"] == 2
    assert store.for_dimension("b", "betrayal", limit=1, offset=1)[0]["episode_id"] == second["episode_id"]
    assert [r["episode_id"] for r in store.logical_records()] == sorted([first["episode_id"], second["episode_id"]])
    with pytest.raises(EpisodeCapacityError):
        store.put_record(_record(3, 3))
    assert store.get(first["episode_id"]) is not None

    plan = store._con.execute(
        "EXPLAIN QUERY PLAN SELECT episode_id FROM episodes WHERE agent=? AND dimension=? ORDER BY interpretation_sequence, emotion_sequence, episode_id",
        ("b", "betrayal"),
    ).fetchall()
    assert any("idx_episodes_agent_dimension" in str(row) for row in plan)

    manifest = store.manifest()
    store.verify_manifest(copy.deepcopy(manifest))
    bad_manifest = copy.deepcopy(manifest); bad_manifest["record_count"] += 1
    with pytest.raises(EpisodeIntegrityError):
        store.verify_manifest(bad_manifest)

    for kwargs in ({"limit": 0}, {"offset": -1}, {"offset": True}):
        with pytest.raises(ValueError):
            store.for_dimension("b", "betrayal", **kwargs)
    store.close()


def test_episode_archive_constructor_closes_connection_on_validation_failure(
    tmp_path, monkeypatch
):
    original_connect = sqlite3.connect
    opened = []

    class TrackingConnection(sqlite3.Connection):
        def close(self):
            self.closed_by_archive = True
            return super().close()

    def tracked_connect(*args, **kwargs):
        kwargs["factory"] = TrackingConnection
        connection = original_connect(*args, **kwargs)
        connection.closed_by_archive = False
        opened.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", tracked_connect)

    with pytest.raises(EpisodeIntegrityError):
        SQLiteEpisodeArchive(tmp_path / "invalid-open.sqlite", create=False)

    assert len(opened) == 1
    assert opened[0].closed_by_archive


def test_episode_archive_validation_and_integrity_failures(tmp_path):
    base = _record()
    invalid_records = [
        [],
        {"episode_id": "x"},
        base | {"agent": " "},
        base | {"dimension": " "},
        base | {"interpretation_sequence": 0},
        base | {"emotion_sequence": 0},
        base | {"episode_id": "wrong"},
        base | {"emotion_profile": []},
        base | {"emotion_profile": {"bad": 2.0}},
        base | {"emotion_profile": {"bad": True}},
        base | {"emotion_profile": {"bad": float("nan")}},
        base | {"emotion_profile": {"x": 0.2, " x ": 0.3}},
        base | {"interpretation_source": object()},
        base | {"emotion_event": object()},
    ]
    for invalid in invalid_records:
        with pytest.raises(ValueError):
            SQLiteEpisodeArchive.validate_record(invalid)

    with pytest.raises(ValueError):
        SQLiteEpisodeArchive.make_episode_id("b", True, None)
    with pytest.raises(ValueError):
        SQLiteEpisodeArchive.record_from_entries(agent="b", dimension="x", interpretation_entry=[], emotion_entry=None)
    with pytest.raises(ValueError):
        SQLiteEpisodeArchive.record_from_entries(agent="b", dimension="x", interpretation_entry={"sequence": 1, "transitions": {}}, emotion_entry=None)
    with pytest.raises(ValueError):
        SQLiteEpisodeArchive.record_from_entries(agent="b", dimension="x", interpretation_entry=_interpretation_entry(1, "x", -0.1), emotion_entry=None)
    with pytest.raises(ValueError):
        SQLiteEpisodeArchive.record_from_entries(agent="b", dimension="betrayal", interpretation_entry=_interpretation_entry(), emotion_entry=[])

    missing = tmp_path / "missing.sqlite"
    with pytest.raises(EpisodeIntegrityError):
        SQLiteEpisodeArchive(missing, create=False)

    wrong_schema = tmp_path / "wrong-schema.sqlite"
    s = SQLiteEpisodeArchive(wrong_schema); s._con.execute("UPDATE metadata SET value='bad' WHERE key='schema'"); s._con.commit(); s.close()
    with pytest.raises(EpisodeIntegrityError):
        SQLiteEpisodeArchive(wrong_schema, create=False)

    count_bad = tmp_path / "count-bad.sqlite"
    s = SQLiteEpisodeArchive(count_bad); s._con.execute("UPDATE metadata SET value='1' WHERE key='record_count'"); s._con.commit(); s.close()
    with pytest.raises(EpisodeIntegrityError):
        SQLiteEpisodeArchive(count_bad, create=False)

    digest_bad = tmp_path / "digest-bad.sqlite"
    s = SQLiteEpisodeArchive(digest_bad); s._con.execute("UPDATE metadata SET value='x' WHERE key='content_digest'"); s._con.commit(); s.close()
    with pytest.raises(EpisodeIntegrityError):
        SQLiteEpisodeArchive(digest_bad, create=False)

    invalid_count = tmp_path / "invalid-count.sqlite"
    s = SQLiteEpisodeArchive(invalid_count); s._con.execute("UPDATE metadata SET value='wat' WHERE key='record_count'"); s._con.commit(); s.close()
    with pytest.raises(EpisodeIntegrityError):
        SQLiteEpisodeArchive(invalid_count, create=False)

    missing_meta = tmp_path / "missing-meta.sqlite"
    con = sqlite3.connect(missing_meta)
    con.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    con.execute("CREATE TABLE episodes(episode_id TEXT PRIMARY KEY)")
    con.commit(); con.close()
    with pytest.raises(EpisodeIntegrityError):
        SQLiteEpisodeArchive(missing_meta, create=False)

    tampered = tmp_path / "tampered.sqlite"
    s = SQLiteEpisodeArchive(tampered); row = s.put_record(_record());
    s._con.execute("UPDATE episodes SET emotion_profile_json=? WHERE episode_id=?", (json.dumps({"anger": 0.2}), row["episode_id"])); s._con.commit()
    with pytest.raises(EpisodeIntegrityError):
        s.get(row["episode_id"])
    s.close()


def test_production_api_snapshot_archive_pairing_exact_recall_and_ambiguity(tmp_path):
    api, store = _configured_api(tmp_path / "pair.sqlite")
    first = api.continuity_event(
        "b", "observe", features={"betrayal_cue": 1.0}, source="one",
        emotion_event="hurt_one", emotion_impulses={"anger": 0.8},
        signals={"interpretation_impulse": 0.9},
    )
    first_id = first["episodes"][0]["episode_id"]
    first_profile = store.get(first_id)["emotion_profile"]

    # Force both source-owned diagnostic histories to discard the episode origin.
    for index in range(70):
        api.continuity_event(
            "b", "observe", features={"threat_cue": 0.0}, source=f"noise-{index}",
            emotion_event=f"noise-{index}", emotion_impulses={}, signals={},
        )
    assert all(row.get("source") != "one" for row in api.interpretation_state("b")["history"])
    assert all(row.get("event") != "hurt_one" for row in api.emotional_state("b")["history"])

    before_meaning = copy.deepcopy(api.interpretation_state("b")["levels"])
    before_relationship = copy.deepcopy(api.get_relationship("a", "b"))
    recalled = api.recall_episode(first_id, 0.7)
    assert recalled["lookup"]["status"] == "explicit_episode"
    assert recalled["meaning_unchanged"]
    assert api.interpretation_state("b")["levels"] == before_meaning
    assert api.get_relationship("a", "b") == before_relationship
    assert recalled["emotion"] is not None
    assert store.get(first_id)["emotion_profile"] == first_profile

    # Same dimension, distinct existing source sequences -> explicit identity; dimension recall refuses to guess emotion.
    second = api.continuity_event(
        "b", "observe", features={"betrayal_cue": 1.0}, source="two",
        emotion_event="hurt_two", emotion_impulses={"fear": 0.6}, signals={},
    )
    second_id = second["episodes"][0]["episode_id"]
    assert second_id != first_id
    before_ambiguous = copy.deepcopy(api.snapshot())
    ambiguous = api.recall_dimension("b", "betrayal", 0.5)
    assert ambiguous["lookup"]["status"] == "ambiguous"
    assert ambiguous["emotion"] is None
    assert ambiguous["activation"]["cause"] == "ambiguous_memory_recall_refused"
    assert ambiguous["activation"]["activation_before"] == ambiguous["activation"]["activation_after"]
    assert api.snapshot() == before_ambiguous

    fresh = GhostAPI(episode_store=store)
    fresh_before = copy.deepcopy(fresh.snapshot())
    fresh_ambiguous = fresh.recall_dimension("b", "betrayal", 0.5)
    assert fresh_ambiguous["lookup"]["status"] == "ambiguous"
    assert fresh_ambiguous["continuity"] is None
    assert fresh.snapshot() == fresh_before

    exact = api.recall_episode(second_id, 0.5)
    assert exact["lookup"]["record"]["emotion_profile"] == {"fear": 0.6}

    snapshot = api.snapshot()
    encoded = json.dumps(snapshot, sort_keys=True)
    assert "emotion_profile" not in encoded
    assert snapshot["continuity"]["episode_archive"] == store.manifest()
    restored = GhostAPI.from_snapshot(copy.deepcopy(snapshot), episode_store=store)
    assert restored.snapshot() == snapshot
    with pytest.raises(EpisodeIntegrityError):
        GhostAPI.from_snapshot(copy.deepcopy(snapshot))
    mismatch = copy.deepcopy(snapshot); mismatch["continuity"]["episode_archive"]["record_count"] += 1
    with pytest.raises(EpisodeIntegrityError):
        GhostAPI.from_snapshot(mismatch, episode_store=store)

    empty_lookup = store.resolve_dimension("b", "respect")
    assert empty_lookup["status"] == "missing"
    missing_recall = api.recall_dimension("b", "respect", 0.5)
    assert missing_recall["lookup"]["status"] == "missing"
    assert missing_recall["emotion"] is None

    with pytest.raises(KeyError):
        api.recall_episode("missing", 0.5)
    bare = GhostAPI()
    with pytest.raises(RuntimeError):
        bare.recall_episode("missing", 0.5)
    with pytest.raises(RuntimeError):
        bare.recall_dimension("b", "x", 0.5)
    store.close()


def test_continuity_event_failure_is_hot_state_atomic_and_does_not_partially_archive(tmp_path):
    api, store = _configured_api(tmp_path / "capacity.sqlite", max_records=1)
    api.continuity_event(
        "b",
        "observe",
        features={"betrayal_cue": 1.0},
        source="first",
        emotion_event="hurt",
        emotion_impulses={"anger": 0.8},
        signals={},
    )
    before = copy.deepcopy(api.snapshot())
    manifest = copy.deepcopy(store.manifest())
    with pytest.raises(EpisodeCapacityError):
        api.continuity_event(
            "b",
            "observe",
            features={"betrayal_cue": 1.0},
            source="second",
            emotion_event="hurt_again",
            emotion_impulses={"fear": 0.7},
            signals={},
        )
    assert api.snapshot() == before
    assert store.manifest() == manifest
    assert store.count() == 1
    store.close()

    api, store = _configured_api(tmp_path / "multi.sqlite")
    api.configure_interpretation_rule(
        "b",
        "multi_cue",
        {"betrayal": 0.8, "threat": 0.7},
    )
    before = copy.deepcopy(api.snapshot())
    with pytest.raises(ValueError, match="one positive interpretation origin"):
        api.continuity_event(
            "b",
            "observe",
            features={"multi_cue": 1.0},
            source="multi",
            signals={},
        )
    assert api.snapshot() == before
    assert store.count() == 0
    store.close()


def test_hot_snapshot_does_not_grow_linearly_with_archived_episode_payload(tmp_path):
    api, store = _configured_api(tmp_path / "growth.sqlite")
    api.continuity_event(
        "b", "observe", features={"betrayal_cue": 1.0}, source="seed",
        emotion_event="seed", emotion_impulses={"anger": 0.8}, signals={},
    )
    before_packet = copy.deepcopy(api.snapshot()["continuity"])
    before_size = len(json.dumps(before_packet, sort_keys=True))
    for index in range(2, 1002):
        store.put_record(_record(index, None, dimension="archive_stress"))
    after_packet = copy.deepcopy(api.snapshot()["continuity"])
    after_size = len(json.dumps(after_packet, sort_keys=True))
    assert store.count() == 1001
    assert after_packet["runtime"] == before_packet["runtime"]
    # The hot packet changes only through the constant-shape archive manifest.
    # It never contains the 1,001 retained causal episode payloads.
    assert "emotion_profile" not in json.dumps(after_packet, sort_keys=True)
    assert after_size - before_size < 8
    assert len(store.logical_records()) == 1001
    store.close()


def test_api_new_surface_compatibility_and_error_branches(tmp_path):
    # Legacy/no-continuity snapshots still restore without an archive.
    plain = GhostAPI()
    plain_snapshot = plain.snapshot()
    plain_restored = GhostAPI.from_snapshot(copy.deepcopy(plain_snapshot))
    assert "continuity" not in plain_restored.snapshot()
    plain.restore_snapshot(copy.deepcopy(plain_snapshot))

    # Existing attention behavior remains usable before continuity is registered.
    plain.register_attention_agent("plain")
    no_continuity = plain.advance_attention_from_state(
        "plain",
        include_emotions=False,
        include_interpretations=False,
    )
    assert "foreground" not in no_continuity

    # Continuity without an episode archive is allowed, contains no historical
    # payload, and restores with an explicit null archive manifest.
    no_store = GhostAPI()
    no_store.register_interpretation_agent("b", initial={"threat": 0.0})
    no_store.configure_interpretation_rule("b", "threat_cue", {"threat": 0.7})
    event = no_store.continuity_event(
        "b", "observe", features={"threat_cue": 1.0}, source="no-store", signals={}
    )
    assert event["episodes"] == []
    assert no_store.emotional_state("b") is None
    without_interpretations = no_store.advance_attention_from_state(
        "b", include_interpretations=False
    )
    assert "foreground" in without_interpretations
    null_manifest_snapshot = no_store.snapshot()
    assert null_manifest_snapshot["continuity"]["episode_archive"] is None
    assert GhostAPI.from_snapshot(copy.deepcopy(null_manifest_snapshot)).snapshot() == null_manifest_snapshot

    # A caller cannot sneak emotional replay data in without naming an event.
    with pytest.raises(ValueError):
        no_store.continuity_event(
            "b", "observe", features={"threat_cue": 1.0}, emotion_impulses={"fear": 0.5}
        )
    with pytest.raises(ValueError):
        no_store.continuity_event(
            "b", "observe", features={"threat_cue": 1.0}, emotion_context={"stress": 0.2}
        )

    # Continuity packet shape is strict.
    base = copy.deepcopy(null_manifest_snapshot)
    for invalid in (
        [],
        {"runtime": {}, "episode_archive": None, "extra": True},
        {"runtime": [], "episode_archive": None},
    ):
        packet = copy.deepcopy(base)
        packet["continuity"] = invalid
        with pytest.raises(ValueError):
            GhostAPI.from_snapshot(packet)

def test_phase5_motive_signal_detects_registration_disappearing_mid_call(monkeypatch):
    """Close the Phase-5 GhostAPI branch debt exposed by the production core gate."""
    api = GhostAPI()
    sera = api.register_agent("sera")
    states = iter(({"agent_id": "sera"}, None))
    monkeypatch.setattr(api.agents, "get_state", lambda agent_id: next(states))
    with pytest.raises(RuntimeError, match="registered agent disappeared: sera"):
        sera.motive_signals()

