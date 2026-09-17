"""Permanent value/cost regressions for the Stage-9-selected continuity architecture."""

from __future__ import annotations

import json
from pathlib import Path

from continuity_benchmark_v1110.run_stage6_behavioral_value import build_result
from ghost import GhostAPI
from ghost.episode_store import SQLiteEpisodeArchive


_STAGE6_GHOST_ONLY = [
    "episode_specific_affect :: fearful_episode_recall_is_behaviorally_more_defensive",
    "betrayal_affect_mode_resolution :: grief_tagged_betrayal_recall_prefers_withdrawal",
]


def test_optimized_production_preserves_stage6_behavioral_value(tmp_path):
    result = build_result(tmp_path / "stage6-value")
    assert result["quality"]["ghost"]["passed"] == 25
    assert result["quality"]["ghost"]["total"] == 26
    assert result["quality"]["ghost_only_passes"] == _STAGE6_GHOST_ONLY
    assert result["quality"]["baseline_only_passes"] == []
    assert result["foreground_ablation"]["equalized_without_foreground"] is True
    assert result["deterministic_rerun"] is True
    assert result["strict_verdict"] == (
        "LIMITED_GHOST_BEHAVIORAL_ADVANTAGE_DEMONSTRATED_"
        "CROSS_LAYER_FOREGROUND_CAUSALLY_CONTRIBUTES"
    )


def test_optimized_production_keeps_hot_history_sparse(tmp_path):
    episode_path = tmp_path / "episodes.sqlite"
    store = SQLiteEpisodeArchive(episode_path)
    api = GhostAPI(episode_store=store)
    try:
        agent = "npc"
        api.register_interpretation_agent(agent)
        api.register_attention_agent(agent, config={"release_rate": 0.08})
        api.register_emotional_agent(
            agent,
            inertia={"anger": 0.88, "fear": 0.86, "grief": 0.94, "hope": 0.92},
            spotlight_switch_margin=0.05,
        )
        dimensions = ("respect", "threat", "betrayal")
        for dimension in dimensions:
            api.configure_interpretation_rule(
                agent,
                f"action:sparse_{dimension}",
                {dimension: 1.0},
            )
        for index in range(120):
            dimension = dimensions[index % 3]
            emotion = (
                {"hope": 0.08}
                if dimension == "respect"
                else ({"fear": 0.08} if dimension == "threat" else {"anger": 0.08})
            )
            api.continuity_event(
                agent,
                f"sparse_{dimension}",
                intensity=0.006,
                source=f"sparse-{index}",
                emotion_event="sparse_history_probe",
                emotion_impulses=emotion,
            )
        for _ in range(100):
            api.continuity_tick(agent, 1)
        snapshot = api.snapshot()
        encoded = json.dumps(
            snapshot,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        assert len(encoded) < 30_000
        assert api._continuity_optimization.hot_history_counts() == {
            "interpretation": 1,
            "emotion": 1,
            "attention": 1,
        }
        history = snapshot["continuity"]["history_archive"]
        assert history["compression"] == "zlib"
        assert history["level"] == 6
        assert history["record_count"] <= 192
        assert len(api._continuity_optimization.working_projections(agent)) <= 3
    finally:
        store.close()
