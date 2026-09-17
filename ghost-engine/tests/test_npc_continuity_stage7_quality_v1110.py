from __future__ import annotations

import json
from pathlib import Path

import pytest

from continuity_benchmark_v1110.run_stage7_optimization import build_result
from continuity_benchmark_v1110.stage7_optimization_variants import (
    ColdHistoryArchive,
    PROJECTION_ENTER,
    PROJECTION_EXIT,
    optimized_factory,
)


STAGE6_REPORT = Path('/mnt/data/ghost_npc_continuity_experiment_stage6_local_result.json')


def test_projection_hysteresis_is_ordered_and_bounded():
    assert 0.0 <= PROJECTION_EXIT < PROJECTION_ENTER <= 1.0


def test_cold_history_archive_integrity_and_manifest(tmp_path):
    archive = ColdHistoryArchive(tmp_path / 'cold.sqlite')
    try:
        archive.put('emotion', 'npc', {'sequence': 1, 'effective_impulses': {'fear': .5}})
        archive.put('emotion', 'npc', {'sequence': 1, 'effective_impulses': {'fear': .5}})
        manifest = archive.manifest()
        assert archive.count() == 1
        assert archive.records('emotion', 'npc')[0]['sequence'] == 1
        archive.verify_manifest(manifest)
        with pytest.raises(Exception):
            archive.verify_manifest({'schema': '1.0', 'records': 0, 'digest': 'x'})
    finally:
        archive.close()


def test_sparse_variant_moves_raw_histories_cold_and_restores(tmp_path):
    system = optimized_factory('ghost_sparse', tmp_path, 'sparse')
    restored = None
    try:
        for i in range(6):
            system.event('npc', source=f'e{i}', dimension='respect', meaning_delta=.04,
                         relevance=.04, emotion_profile={'hope': .1}, consequence=.01)
        counts = system.hot_history_counts()
        assert all(value <= 1 for value in counts.values())
        assert system.cold_history is not None and system.cold_history.count() > 0
        before = system.observe('npc')
        snapshot = system.snapshot()
        system.close(); system = None
        restored = optimized_factory('ghost_sparse', tmp_path, 'sparse', snapshot=snapshot)
        assert restored.observe('npc') == before
    finally:
        if system is not None:
            system.close()
        if restored is not None:
            restored.close()


def test_lazy_tick_defers_work_but_materializes_before_observation(tmp_path):
    lazy = optimized_factory('ghost_lazy', tmp_path, 'lazy')
    current = optimized_factory('ghost_current', tmp_path, 'current')
    try:
        kwargs = dict(source='threat', dimension='threat', meaning_delta=.7,
                      relevance=.7, emotion_profile={'fear': .8}, consequence=0.0)
        lazy.event('npc', **kwargs); current.event('npc', **kwargs)
        lazy.tick('npc', 30); current.tick('npc', 30)
        assert lazy._pending_steps['npc'] == 30
        lazy_state = lazy.observe('npc'); current_state = current.observe('npc')
        assert lazy._pending_steps['npc'] == 0
        assert lazy_state['meaning'] == current_state['meaning']
        assert lazy_state['activation'] == current_state['activation']
        assert lazy_state['emotion'] == current_state['emotion']
        assert lazy_state['foreground'] == current_state['foreground']
    finally:
        lazy.close(); current.close()


def test_full_stage7_result_preserves_frozen_value_locally(tmp_path):
    report = json.loads(STAGE6_REPORT.read_text(encoding='utf-8'))
    result = build_result(tmp_path / 'run', report)
    assert result['quality']['ghost_current']['passed'] == 25
    assert result['quality']['ghost_current']['total'] == 26
    assert all(row['deterministic'] for row in result['preservation'].values())
    assert result['strict_verdict'] in {
        'LAZY_PLUS_SPARSE_PRESERVES_STAGE6_VALUE_OPTIMIZATION_PATH_SURVIVES',
        'PARTIAL_OPTIMIZATION_PATH_SURVIVES_STAGE6_VALUE_PRESERVED',
        'OPTIMIZATION_HYPOTHESES_FAIL_STAGE6_VALUE_PRESERVATION',
    }
