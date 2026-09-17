"""Stage-2 characterization tests over the frozen Stage-1 contract."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from continuity_benchmark_v1110.contract import (
    ArchiveMismatchError,
    CapacityBackpressureError,
    contract_digest,
)
from continuity_benchmark_v1110.ghost_adapter import (
    GhostArchiveMismatchError,
    GhostCapacityError,
    GhostContinuityAdapter,
    _effective_impulse_for_additive_delta,
    _foreground_token,
    ghost_factory,
)
from continuity_benchmark_v1110.run_stage2_head_to_head import (
    STAGE1_BASELINE_RESULT_SHA256,
)


STAGE1_HASHES = {
    "continuity_benchmark_v1110/__init__.py": "43240e26af68b11e931f863eeb6ed09ac81a2f8f0f78c6ab794ef0ce350e7808",
    "continuity_benchmark_v1110/contract.py": "843e19bf4baa6212aa15921ad7f5c9997c9c305d0ad3ac0b0aa1b1d50ef3a694",
    "continuity_benchmark_v1110/metrics.py": "13a1f0caefbe6e832ef8cc5d42a55470a712c9c87e7a88736642d97fbde4922b",
    "continuity_benchmark_v1110/purpose_built.py": "0b607b14d00d0c70c9b8201cfcc43c3c0a06d2270d97f4ea87a55e57206982c2",
    "continuity_benchmark_v1110/run_stage1_baseline.py": "e109fa870262b323cb7cc7eb3e2784a1f257840222c759fc03e6587974e1d495",
    "continuity_benchmark_v1110/scenario_runner.py": "1b794701ff7174b56f0f1f13016b21799bd0ffe36ac2fa86ecbefacc357a70ec",
    "continuity_benchmark_v1110/stage1_baseline_frozen.json": STAGE1_BASELINE_RESULT_SHA256,
    "tests/test_npc_continuity_stage1_v1110.py": "c1340f9f2b92b3003ad671f07ea1fe73fff58c7a9fcc4790bd8ef344756dfae3",
    "tests/test_npc_continuity_stage1_quality_v1110.py": "202127649578fb1c47a6a6fdcfbef4249a27930a7d86302fb692615638092a44",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()



def test_stage1_evidence_is_still_exactly_hash_frozen():
    root = Path(__file__).resolve().parents[1]
    assert contract_digest() == "73f5cc5573091cabfdae6372e074def395d5e573a5facb587b85c3c592342653"
    assert {rel: _sha(root / rel) for rel in STAGE1_HASHES} == STAGE1_HASHES


def test_adapter_capacity_translation_rolls_back_adapter_rule_configuration(tmp_path):
    system = ghost_factory(tmp_path, "capacity", max_records=1)
    try:
        system.event(
            "npc", source="one", dimension="betrayal", meaning_delta=0.5,
            relevance=0.5, emotion_profile={"anger": 0.5}, consequence=-0.5,
        )
        before = system._ghost.snapshot()
        with pytest.raises(CapacityBackpressureError):
            system.event(
                "npc", source="two", dimension="respect", meaning_delta=0.6,
                relevance=0.6, emotion_profile={"hope": 0.5}, consequence=0.5,
            )
        assert system._ghost.snapshot() == before
        assert system.archive.count() == 1
    finally:
        system.close()


def test_adapter_translates_wrong_archive_and_supports_close_idempotence(tmp_path):
    system = ghost_factory(tmp_path, "right")
    system.event(
        "npc", source="one", dimension="betrayal", meaning_delta=0.5,
        relevance=0.5, emotion_profile={}, consequence=0.0,
    )
    snapshot = system.snapshot()
    system.close()
    with pytest.raises(ArchiveMismatchError):
        ghost_factory(tmp_path, "wrong", snapshot=snapshot)
    system.close()


def test_adapter_helpers_cover_boundary_math_and_foreground_projection():
    assert _effective_impulse_for_additive_delta(0.0, 0.0) == 0.0
    assert _effective_impulse_for_additive_delta(1.0, 0.5) == 0.0
    assert _effective_impulse_for_additive_delta(0.0, -0.5) == 0.0
    assert _effective_impulse_for_additive_delta(0.5, 0.25) == 0.5
    assert _effective_impulse_for_additive_delta(0.5, -0.25) == -0.5
    assert _foreground_token(None) is None
    assert _foreground_token("interpretation:betrayal") == "betrayal"
    assert _foreground_token("emotion:anger") == "emotion:anger"
    assert issubclass(GhostCapacityError, CapacityBackpressureError)
    assert issubclass(GhostArchiveMismatchError, ArchiveMismatchError)


def test_adapter_closed_guard_and_invalid_snapshot_shapes(tmp_path):
    system = GhostContinuityAdapter(tmp_path / "closed.sqlite")
    system.close()
    with pytest.raises(RuntimeError, match="closed"):
        _ = system._ghost

    with pytest.raises(ArchiveMismatchError, match="invalid Ghost adapter snapshot"):
        GhostContinuityAdapter(tmp_path / "invalid.sqlite", snapshot={})
    with pytest.raises(ArchiveMismatchError, match="unsupported Ghost adapter snapshot schema"):
        GhostContinuityAdapter(
            tmp_path / "schema.sqlite",
            snapshot={"schema": "bad", "ghost": {}, "ticks": {}, "episode_archive": {}},
        )


def test_adapter_defensive_and_unique_lookup_paths(tmp_path, monkeypatch):
    system = ghost_factory(tmp_path, "defensive")
    try:
        assert system._meaning_level("missing", "x") == 0.0
        before = system._ghost.snapshot()

        def explode(*args, **kwargs):
            raise ValueError("adapter setup failure")

        monkeypatch.setattr(system, "_configure_impulse_action", explode)
        with pytest.raises(ValueError, match="adapter setup failure"):
            system.event(
                "npc", source="boom", dimension="betrayal", meaning_delta=0.5,
                relevance=0.5, emotion_profile={}, consequence=0.0,
            )
        assert system._ghost.snapshot() == before
    finally:
        system.close()

    zero = ghost_factory(tmp_path, "zero")
    try:
        before = zero._ghost.snapshot()
        with pytest.raises(RuntimeError, match="exactly one durable Ghost episode"):
            zero.event(
                "npc", source="zero", dimension="betrayal", meaning_delta=0.0,
                relevance=0.0, emotion_profile=None, consequence=0.0,
            )
        assert zero._ghost.snapshot() == before
    finally:
        zero.close()

    unique = ghost_factory(tmp_path, "unique")
    try:
        unique.event(
            "npc", source="one", dimension="betrayal", meaning_delta=0.5,
            relevance=0.5, emotion_profile={"anger": 0.4}, consequence=0.0,
        )
        lookup = unique.recall_dimension("npc", "betrayal", 0.3)
        assert lookup["status"] == "unique"
        assert lookup["candidate_count"] == 1
        assert lookup["recall"]["meaning_unchanged"] is True
    finally:
        unique.close()


def test_adapter_fast_public_contract_and_restore_paths(tmp_path):
    system = ghost_factory(tmp_path, "fast-contract")
    try:
        first = system.event(
            "npc",
            source="first",
            dimension="betrayal",
            meaning_delta=0.6,
            relevance=0.7,
            emotion_profile={"anger": 0.5},
            consequence=-0.4,
        )
        assert system.get_episode(first["episode_id"])["episode_id"] == first["episode_id"]
        assert len(system.episodes_for_dimension("npc", "betrayal")) == 1
        assert system.archive_manifest()["record_count"] == 1

        exact = system.recall_episode(first["episode_id"], 0.3)
        assert exact["status"] == "explicit_episode"
        assert exact["meaning_unchanged"] is True

        system.revise("npc", "betrayal", -0.1)
        system.tick("npc", 2)
        observed = system.observe("npc")
        assert observed["tick"] == 2
        assert observed["episode_count"] == 1
        assert observed["trust"] < 0.0
        assert len(system.near_tie_trace(4)) == 4

        second = system.event(
            "npc",
            source="second",
            dimension="betrayal",
            meaning_delta=0.1,
            relevance=0.6,
            emotion_profile={"fear": 0.3},
            consequence=0.0,
        )
        assert second["episode_id"] != first["episode_id"]
        ambiguous = system.recall_dimension("npc", "betrayal", 0.2)
        assert ambiguous["status"] == "ambiguous"
        assert ambiguous["candidate_count"] >= 2

        snapshot = system.snapshot()
    finally:
        system.close()

    restored = ghost_factory(tmp_path, "fast-contract", snapshot=snapshot)
    try:
        restored_state = restored.observe("npc")
        assert restored_state["tick"] == 2
        assert restored_state["episode_count"] == 2
    finally:
        restored.close()
