from __future__ import annotations

import json

import pytest

from continuity_benchmark_v1110 import run_stage7_optimization as runner
from continuity_benchmark_v1110.stage7_optimization_variants import ColdHistoryArchive, optimized_factory


def test_ratio_zero_and_nonzero():
    assert runner._ratio(2, 0) is None
    assert runner._ratio(4, 2) == 2


def test_check_flattening_and_win_target_helpers():
    packet = {'scenarios': {'x': {'checks': {'a': True, 'b': False}}}}
    assert runner._checks(packet) == {'x :: a': True, 'x :: b': False}
    assert runner._ghost_wins_preserved(packet) is False


def test_unknown_variant_rejected(tmp_path):
    with pytest.raises(ValueError):
        optimized_factory('nope', tmp_path, 'x')


def test_cold_archive_rejects_bad_sequence(tmp_path):
    archive = ColdHistoryArchive(tmp_path / 'cold.sqlite')
    try:
        with pytest.raises(ValueError): archive.put('x', 'npc', {'sequence': 0})
        with pytest.raises(ValueError): archive.put('x', 'npc', {'sequence': True})
    finally:
        archive.close()


def test_main_writes_json(monkeypatch, tmp_path):
    stage6 = tmp_path / 'stage6.json'; stage6.write_text('{}')
    out = tmp_path / 'out.json'
    monkeypatch.setattr(runner, 'build_result', lambda root, report: {'ok': True})
    assert runner.main(['--root', str(tmp_path / 'run'), '--stage6-report', str(stage6), '--out', str(out)]) == 0
    assert json.loads(out.read_text()) == {'ok': True}
