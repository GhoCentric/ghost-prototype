from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import json
import sqlite3

import pytest

from continuity_benchmark_v1110 import run_stage7_optimization as runner
from continuity_benchmark_v1110 import stage7_optimization_variants as variants


def _event_kwargs(source='e', dimension='respect', emotion=None):
    return dict(
        source=source,
        dimension=dimension,
        meaning_delta=.2,
        relevance=.2,
        emotion_profile={} if emotion is None else emotion,
        consequence=.01,
    )


def test_all_variant_names_and_factory(tmp_path):
    expected = {
        'ghost_current': 'ghost_current',
        'ghost_lazy': 'ghost_lazy',
        'ghost_sparse': 'ghost_sparse',
        'ghost_lazy_sparse': 'ghost_lazy_sparse',
    }
    systems = []
    try:
        for kind, name in expected.items():
            system = variants.optimized_factory(kind, tmp_path / kind, 'x')
            systems.append(system)
            assert system.variant_name == name
        with pytest.raises(ValueError):
            variants.optimized_factory('bad', tmp_path, 'bad')
    finally:
        for system in systems:
            system.close()


def test_cold_history_integrity_limit_and_tamper(tmp_path):
    archive = variants.ColdHistoryArchive(tmp_path / 'cold.sqlite')
    try:
        with pytest.raises(ValueError):
            archive.put('x', 'npc', {'sequence': 0})
        with pytest.raises(ValueError):
            archive.put('x', 'npc', {'sequence': True})
        for i in range(1, variants.COLD_HISTORY_LIMIT + 5):
            archive.put('attention', 'npc', {'sequence': i, 'underlying_salience': {}})
        assert archive.count() == variants.COLD_HISTORY_LIMIT
        assert len(archive.records('attention', 'npc')) == variants.COLD_HISTORY_LIMIT
        manifest = archive.manifest(); archive.verify_manifest(manifest)
        with pytest.raises(variants.GhostArchiveMismatchError):
            archive.verify_manifest({'schema': '1.0', 'records': 0, 'digest': 'bad'})
        archive._db.execute(
            "UPDATE history SET payload_json='{}' WHERE subsystem='attention' AND agent='npc' "
            "AND sequence=(SELECT MIN(sequence) FROM history WHERE subsystem='attention' AND agent='npc')"
        )
        with pytest.raises(RuntimeError, match='integrity'):
            archive.records('attention', 'npc')
        assert archive.bytes() > 0
    finally:
        archive.close()


def test_lazy_and_sparse_operation_paths(tmp_path):
    current = variants.optimized_factory('ghost_current', tmp_path / 'current', 'x')
    lazy = variants.optimized_factory('ghost_lazy', tmp_path / 'lazy', 'x')
    sparse = variants.optimized_factory('ghost_sparse', tmp_path / 'sparse', 'x')
    both = variants.optimized_factory('ghost_lazy_sparse', tmp_path / 'both', 'x')
    try:
        # Non-lazy early materialize and no-op sparse helper path.
        current.observe('npc')
        current._sparsify_all()
        assert current.working_projections('npc') == []
        assert current.hot_history_counts() == {'interpretation': 0, 'emotion': 0, 'attention': 0}

        # Invalid lazy scheduling branches, plus no-pending materialization.
        lazy.observe('npc')
        for bad in (0, True):
            with pytest.raises(ValueError):
                lazy.tick('npc', bad)

        # Normal current/sparse tick branches and sparse post-operation pruning.
        srow = sparse.event('npc', **_event_kwargs('s1', emotion={'hope': .2}))
        sparse.event('npc', **_event_kwargs('s2', emotion={'hope': .2}))
        sparse.tick('npc', 2)
        sparse.revise('npc', 'respect', -.05)
        sparse.recall_episode(srow['episode_id'], .5)
        sparse.recall_dimension('npc', 'respect', .5)  # ambiguous path after two episodes
        assert all(v <= 1 for v in sparse.hot_history_counts().values())
        assert sparse.cold_history is not None and sparse.cold_history.count() > 0

        # Lazy materialization and sparse+lazy branch.
        brow = both.event('npc', **_event_kwargs('b1', 'threat', {'fear': .8}))
        both.tick('npc', 5)
        assert both._pending_steps['npc'] == 5
        both.observe('npc')
        assert both._pending_steps['npc'] == 0
        both.tick('npc', 2)
        both.recall_episode(brow['episode_id'], .7)
        both.tick('npc', 2)
        both.recall_dimension('npc', 'threat', .4)
        both.tick('npc', 2)
        both.revise('npc', 'threat', -.05)
        assert all(v <= 1 for v in both.hot_history_counts().values())
    finally:
        for system in (current, lazy, sparse, both):
            system.close()


def test_sparse_snapshot_restore_errors_and_success(tmp_path):
    system = variants.optimized_factory('ghost_sparse', tmp_path, 'x')
    try:
        system.event('npc', **_event_kwargs('one', emotion={'hope': .2}))
        system.event('npc', **_event_kwargs('two', emotion={'hope': .2}))
        snap = system.snapshot()
    finally:
        system.close()

    restored = variants.optimized_factory('ghost_sparse', tmp_path, 'x', snapshot=snap)
    restored.close()

    bad = dict(snap); bad['schema'] = 'bad'
    with pytest.raises(variants.GhostArchiveMismatchError):
        variants.optimized_factory('ghost_sparse', tmp_path, 'x', snapshot=bad)
    bad2 = dict(snap); bad2['variant'] = 'ghost_lazy_sparse'
    with pytest.raises(variants.GhostArchiveMismatchError):
        variants.optimized_factory('ghost_sparse', tmp_path, 'x', snapshot=bad2)

    current = variants.optimized_factory('ghost_current', tmp_path / 'current', 'c')
    try:
        csnap = current.snapshot()
    finally:
        current.close()
    csnap['cold_history'] = {'unexpected': True}
    with pytest.raises(variants.GhostArchiveMismatchError):
        variants.optimized_factory('ghost_current', tmp_path / 'current', 'c', snapshot=csnap)


def test_constructor_failure_closes_sparse_cold_archive(monkeypatch, tmp_path):
    closed = {'value': False}
    original = variants.ColdHistoryArchive.close
    def close(self):
        closed['value'] = True
        return original(self)
    monkeypatch.setattr(variants.ColdHistoryArchive, 'close', close)
    with pytest.raises(variants.GhostArchiveMismatchError):
        variants.ExperimentalGhostContinuityAdapter(
            tmp_path / 'bad.sqlite', lazy_time=False, sparse_history=True,
            snapshot={'schema': 'bad'},
        )
    assert closed['value'] is True


def test_record_score_all_subsystems_and_projection_hysteresis(tmp_path):
    system = variants.optimized_factory('ghost_lazy_sparse', tmp_path, 'x')
    try:
        row = system.event('npc', **_event_kwargs('threat', 'threat', {'fear': .9}))
        system.event('npc', **_event_kwargs('noise', 'respect', {'hope': .1}))
        assert system._record_score('interpretation', 'npc', {'transitions': {'threat': {}}}) >= 0
        assert system._record_score('emotion', 'npc', {'effective_impulses': {'fear': .2}}) >= 0
        attention_record = {
            'underlying_salience': {
                'interpretation:threat': .2,
                'emotion:fear': .2,
                'other': .2,
            }
        }
        assert system._record_score('attention', 'npc', attention_record) >= 0
        system.tick('npc', 30); system.observe('npc')
        before = system.working_projections('npc')
        system.recall_episode(row['episode_id'], .95)
        hot1 = system.working_projections('npc')
        hot2 = system.working_projections('npc')  # exercises exit threshold for already-active keys
        assert len(before) <= variants.PROJECTION_BUDGET
        assert 0 < len(hot1) <= variants.PROJECTION_BUDGET
        assert len(hot2) <= variants.PROJECTION_BUDGET
    finally:
        system.close()


def test_patched_stage6_factory_both_dispatch_paths_and_finally(monkeypatch, tmp_path):
    from continuity_benchmark_v1110 import stage6_behavior_scenarios as scenarios
    original = scenarios.factory
    sentinel = object()
    def original_fake(requested, root, label, snapshot=None):
        return sentinel
    monkeypatch.setattr(scenarios, 'factory', original_fake)
    with variants.patched_stage6_factory('ghost_lazy') as module:
        obj = module.factory('other', tmp_path, 'x')
        assert obj is sentinel
        system = module.factory('ghost_lazy', tmp_path, 'y')
        system.close()
    assert scenarios.factory is original_fake
    monkeypatch.setattr(scenarios, 'factory', original)


def test_run_stage6_quality_for_variant_dispatch(monkeypatch, tmp_path):
    from continuity_benchmark_v1110 import stage6_behavior_scenarios as scenarios
    monkeypatch.setattr(scenarios, 'run_quality', lambda kind, root: {'kind': kind, 'root': str(root)})
    result = variants.run_stage6_quality_for_variant('ghost_current', tmp_path)
    assert result['kind'] == 'ghost_current'


class _FakeCold:
    def bytes(self): return 30
    def count(self): return 4


class _FakeArchive:
    class _P:
        def stat(self):
            class S: st_size = 50
            return S()
    path = _P()


class _FakeSystem:
    def __init__(self, sparse=False):
        self.sparse_history = sparse
        self.cold_history = _FakeCold() if sparse else None
        self.archive = _FakeArchive()
        self._id = 0
    def event(self, *args, **kwargs): self._id += 1; return {'episode_id': f'e{self._id}'}
    def tick(self, *args, **kwargs): return None
    def observe(self, *args, **kwargs): return {'ok': True}
    def snapshot(self): return {'x': 1}
    def working_projections(self, agent): return [{'key': 'k'}] if self.sparse_history else []
    def hot_history_counts(self): return {'interpretation': 1, 'emotion': 1, 'attention': 1}
    def recall_episode(self, *args, **kwargs): return None
    def close(self): return None


def test_runner_helpers_engineering_and_projection_probe(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, 'optimized_factory', lambda kind, root, label: _FakeSystem('sparse' in kind))
    assert runner._time_us(lambda: None, repeats=2) >= 0
    dense = runner._engineering('ghost_current', tmp_path / 'dense')
    sparse = runner._engineering('ghost_sparse', tmp_path / 'sparse')
    assert dense['cold_history_bytes'] == 0 and sparse['cold_history_bytes'] == 30
    assert runner._ratio(1, 0) is None and runner._ratio(4, 2) == 2

    class Probe(_FakeSystem):
        def __init__(self): super().__init__(True); self.calls = 0
        def working_projections(self, agent):
            self.calls += 1
            return [] if self.calls in (1, 3) else [{'key': 'a'}]
    monkeypatch.setattr(runner, 'optimized_factory', lambda *args, **kwargs: Probe())
    probe = runner._projection_probe(tmp_path / 'probe')
    assert probe['admitted_after_recall'] and probe['bounded'] and probe['cools_or_holds_below_hot']


def _quality(kind, passed=25):
    checks = {
        'fearful_episode_recall_is_behaviorally_more_defensive': True,
    }
    grief = {'grief_tagged_betrayal_recall_prefers_withdrawal': True}
    return {
        'kind': kind, 'passed': passed, 'total': 26,
        'scenarios': {
            'episode_specific_affect': {'checks': checks, 'ablation': {'fear_without_foreground': {'policy_passes': 1}}},
            'betrayal_affect_mode_resolution': {'checks': grief, 'ablation': {
                'fear_without_foreground': {'policy_passes': 1},
                'grief_without_foreground': {'policy_passes': 1},
            }},
        },
    }


@contextmanager
def _fake_stage6_context(kind):
    class M:
        SCENARIOS = (
            ('episode_specific_affect', lambda k, r: {'v': 1}),
            ('betrayal_affect_mode_resolution', lambda k, r: {'v': 2}),
            ('ambiguous_recall_inertness', lambda k, r: {'v': 3}),
            ('restart_behavior_identity', lambda k, r: {'v': 4}),
        )
    yield M


def _stage6_report():
    ghost = _quality('ghost', 25)
    baseline = _quality('baseline', 23)
    return {'quality': {'ghost': ghost, 'baseline': baseline}}


def test_build_result_invalid_reference(monkeypatch, tmp_path):
    report = _stage6_report(); report['quality']['ghost']['passed'] = 24
    with pytest.raises(RuntimeError, match='25/26'):
        runner.build_result(tmp_path, report)


def test_build_result_all_verdicts_and_mismatch(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, 'patched_stage6_factory', _fake_stage6_context)
    monkeypatch.setattr(runner, '_foreground_ablation', lambda baseline, ghost: {'equalized_without_foreground': True})
    monkeypatch.setattr(runner, '_engineering', lambda kind, root: {
        'event_avg_us': 1, 'dormant_tick_schedule_avg_us': 1, 'dormant_materialize_us': 1,
        'active_tick_cycle_avg_us': 1, 'recall_avg_us': 1, 'hot_snapshot_bytes': 10,
        'episode_archive_bytes': 5, 'cold_history_bytes': 0, 'total_persistent_bytes': 15,
    })
    monkeypatch.setattr(runner, '_projection_probe', lambda root: {'ok': True})

    report = _stage6_report()
    def q_all(kind, root):
        q = _quality('ghost' if kind == 'ghost_current' else kind, 25)
        return q
    monkeypatch.setattr(runner, 'run_stage6_quality_for_variant', q_all)
    result = runner.build_result(tmp_path / 'all', report)
    assert result['strict_verdict'].startswith('LAZY_PLUS_SPARSE')

    def q_partial(kind, root):
        passed = 25 if kind in ('ghost_current', 'ghost_lazy') else 24
        return _quality('ghost' if kind == 'ghost_current' else kind, passed)
    monkeypatch.setattr(runner, 'run_stage6_quality_for_variant', q_partial)
    result = runner.build_result(tmp_path / 'partial', report)
    assert result['strict_verdict'].startswith('PARTIAL_')

    def q_none(kind, root):
        passed = 25 if kind == 'ghost_current' else 24
        return _quality('ghost' if kind == 'ghost_current' else kind, passed)
    monkeypatch.setattr(runner, 'run_stage6_quality_for_variant', q_none)
    result = runner.build_result(tmp_path / 'none', report)
    assert result['strict_verdict'].startswith('OPTIMIZATION_')

    def q_mismatch(kind, root):
        q = _quality('ghost' if kind == 'ghost_current' else kind, 25)
        if kind == 'ghost_current': q['total'] = 25
        return q
    monkeypatch.setattr(runner, 'run_stage6_quality_for_variant', q_mismatch)
    with pytest.raises(RuntimeError, match='control'):
        runner.build_result(tmp_path / 'mismatch', report)


def test_main_both_root_and_output_branches(monkeypatch, tmp_path, capsys):
    report = tmp_path / 'report.json'; report.write_text(json.dumps(_stage6_report()))
    monkeypatch.setattr(runner, 'build_result', lambda root, stage6: {'ok': True})
    out = tmp_path / 'out.json'
    assert runner.main(['--root', str(tmp_path / 'r'), '--stage6-report', str(report), '--out', str(out)]) == 0
    assert json.loads(out.read_text()) == {'ok': True}
    assert runner.main(['--stage6-report', str(report)]) == 0
    assert '"ok": true' in capsys.readouterr().out

def test_remaining_non_sparse_restore_and_operation_branches(tmp_path):
    current = variants.optimized_factory('ghost_current', tmp_path / 'c', 'x')
    try:
        row = current.event('npc', **_event_kwargs('c1', emotion={'hope': .2}))
        snap = current.snapshot()
        current.revise('npc', 'respect', -.01)
        current.recall_episode(row['episode_id'], .3)
        current.recall_dimension('npc', 'respect', .3)
        with pytest.raises(KeyError):
            current.recall_episode('missing-episode', .3)
    finally:
        current.close()
    restored = variants.optimized_factory('ghost_current', tmp_path / 'c', 'x', snapshot=snap)
    restored.close()


