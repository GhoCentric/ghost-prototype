from __future__ import annotations

from copy import deepcopy
import json

import pytest

import continuity_benchmark_v1110.run_stage5_projection_adjudication as m


def _stage4():
    return {
        "stage": "npc_continuity_stage4_ambiguity_correction_rerun",
        "pre_patch": {"ghost": {"passes": 58, "total": 62}},
        "post_patch": {
            "baseline": {"passes": 62, "total": 62},
            "ghost": {"passes": 60, "total": 62},
            "competence": {"passes": 31, "total": 32},
            "discriminators": {"passes": 29, "total": 30},
        },
        "ghost_pass_delta": 2,
        "remaining_raw_failures": deepcopy(m.STAGE4_EXPECTED_FAILED),
        "ghost_deterministic_rerun": True,
        "stage1_baseline_replay_exact": True,
        "frozen_benchmark_modified": False,
        "strict_conclusion": (
            "CONFIRMED_AMBIGUOUS_RECALL_DEFECT_CORRECTED_GHOST_MOVES_58_TO_60_"
            "TWO_FROZEN_PROJECTION_MISMATCHES_REMAIN"
        ),
    }


class MiniArchiveSystem:
    def __init__(self, root=None, label=None):
        self.closed = False
        self.rows = []
    def event(self, agent, **kwargs):
        row = {"episode_id": f"e{len(self.rows)}", "emotion_profile": kwargs["emotion_profile"]}
        self.rows.append(row)
        return row
    def snapshot(self):
        return {"episode_archive": {"record_count": len(self.rows)}}
    def archive_manifest(self):
        return {"record_count": len(self.rows)}
    def close(self):
        self.closed = True


class BrokenSystem(MiniArchiveSystem):
    def event(self, *args, **kwargs):
        raise RuntimeError("forced")


class RecentSystem:
    def __init__(self):
        self.closed = False
        self.events = []
        self._state = {
            "foreground": "emotion:hope",
            "activation": {"betrayal": 0.0, "respect": 0.2},
            "emotion": {"anger": 0.0, "fear": 0.0, "grief": 0.0, "hope": 0.3},
            "meaning": {"betrayal": 0.9, "respect": 0.06},
        }
        self._ghost = self
    def event(self, agent, **kwargs):
        self.events.append(kwargs)
        return {"episode_id": f"x{len(self.events)}"}
    def tick(self, agent, steps):
        return None
    def observe(self, agent):
        return deepcopy(self._state)
    def continuity_state(self, agent):
        return {"current_leader": self._state["foreground"]}
    def close(self):
        self.closed = True


def test_fast_helpers_and_validation(monkeypatch, tmp_path):
    good = _stage4()
    m.validate_stage4_report(good)
    mutations = []
    for path, value in [
        (("stage",), "x"),
        (("pre_patch", "ghost"), {"passes": 1, "total": 62}),
        (("post_patch", "baseline"), {}),
        (("post_patch", "ghost"), {}),
        (("post_patch", "competence"), {}),
        (("post_patch", "discriminators"), {}),
        (("ghost_pass_delta",), 1),
        (("remaining_raw_failures",), {}),
        (("ghost_deterministic_rerun",), False),
        (("stage1_baseline_replay_exact",), False),
        (("frozen_benchmark_modified",), True),
        (("strict_conclusion",), "x"),
    ]:
        bad = deepcopy(good)
        cur = bad
        for key in path[:-1]:
            cur = cur[key]
        cur[path[-1]] = value
        mutations.append(bad)
    for bad in mutations:
        with pytest.raises(ValueError):
            m.validate_stage4_report(bad)

    assert m._canonical_bytes({"b": 1, "a": 2}) == b'{"a":2,"b":1}'
    assert m._contains_equal_subtree({"a": [1, {"b": 2}]}, 2)
    assert not m._contains_equal_subtree({"a": [1]}, 3)

    made = []
    monkeypatch.setattr(m, "PurposeBuiltContinuity", lambda path: made.append(path) or MiniArchiveSystem())
    baseline = m._baseline_factory(tmp_path / "base", "x")
    assert baseline is not None and made

    system, snap, rows = m._populate_snapshot_system(lambda root, label: MiniArchiveSystem(), tmp_path, "ok", 2)
    assert len(rows) == 2 and snap["episode_archive"]["record_count"] == 2
    system.close()

    opened = []
    def broken_factory(root, label):
        obj = BrokenSystem(); opened.append(obj); return obj
    with pytest.raises(RuntimeError):
        m._populate_snapshot_system(broken_factory, tmp_path, "bad", 1)
    assert opened[0].closed

    sized = m._snapshot_size(lambda root, label: MiniArchiveSystem(), tmp_path, "size", 1)
    assert sized["count"] == 1 and sized["archive_count"] == 1


def test_fast_snapshot_probe(monkeypatch, tmp_path):
    ghost_small = {"snapshot_bytes": 1000, "manifest_bytes": 100, "archive_count": 80,
                   "first_episode_id": "e0", "last_episode_id": "e79"}
    baseline_large = {"snapshot_bytes": 1, "manifest_bytes": 90, "archive_count": 160,
                      "first_episode_id": "b0", "last_episode_id": "b159"}
    calls = []
    def fake_size(factory, root, label, count):
        calls.append(count)
        return ghost_small if count == 80 else baseline_large
    monkeypatch.setattr(m, "_snapshot_size", fake_size)

    class GhostLarge:
        def __init__(self): self.closed = False
        def archive_manifest(self):
            return {"schema":"s","archive_schema":"a","record_count":160,"content_digest":"d"}
        def get_episode(self, episode_id):
            return {"episode_id": episode_id, "emotion_profile": {"hope": 0.01}}
        def close(self): self.closed = True
    gs = GhostLarge()
    rows = [{"episode_id":"e0"}] + [{"episode_id":f"e{i}"} for i in range(1,159)] + [{"episode_id":"e159"}]
    snap = {
        "ghost": {
            "continuity": {"runtime": {}, "episode_archive": gs.archive_manifest()},
            "interpretations": {"agents": {"npc": {"history": [{"source":"STAGE5-SOURCE-0159"}]}}},
            "emotions": {"agents": {"npc": {"history": [{"source":"STAGE5-SOURCE-0159"}]}}},
            "attention": {"agents": {"npc": {"history": [{"source":"ghost:salience_bridge"}]}}},
        }
    }
    monkeypatch.setattr(m, "_populate_snapshot_system", lambda *args, **kwargs: (gs, snap, rows))
    result = m._snapshot_probe(tmp_path)
    assert result["all_semantic_checks_pass"]
    assert result["bounded_hot_provenance_overhead_is_real"]
    assert gs.closed
    assert calls == [80, 160]


def test_fast_recent_stream_and_foreground_probe(monkeypatch, tmp_path):
    made = []
    monkeypatch.setattr(m, "ghost_factory", lambda root, label: made.append(RecentSystem()) or made[-1])
    direct = m._run_recent_stream(tmp_path, "x", include_old=True,
                                  recent_dimension="respect", recent_emotion={"hope":0.1})
    assert direct["foreground"] == "emotion:hope" and made[-1].closed
    direct2 = m._run_recent_stream(tmp_path, "y", include_old=False,
                                   recent_dimension="respect", recent_emotion={"hope":0.1})
    assert direct2["foreground"] == "emotion:hope"
    assert m._close_enough(1.0, 1.0)

    packets = {
        "old-hope": {"foreground":"emotion:hope","activation":{"betrayal":0.0,"respect":0.2},"emotion":{"hope":0.3}},
        "no-old-hope": {"foreground":"emotion:hope","activation":{"respect":0.2},"emotion":{"hope":0.3}},
        "old-no-emotion": {"foreground":"respect","activation":{"betrayal":0.0,"respect":0.2},"emotion":{"hope":0.0}},
        "old-fear": {"foreground":"emotion:fear","activation":{"betrayal":0.0,"respect":0.2},"emotion":{"hope":0.0}},
    }
    monkeypatch.setattr(m, "_run_recent_stream", lambda root, label, **kwargs: deepcopy(packets[label]))
    result = m._foreground_probe(tmp_path)
    assert result["all_semantic_checks_pass"]


def test_fast_classify_build_and_write(monkeypatch, tmp_path):
    good_snapshot = {"all_semantic_checks_pass": True, "bounded_hot_provenance_overhead_is_real": True}
    good_foreground = {"all_semantic_checks_pass": True}
    rows = m._classify(good_snapshot, good_foreground)
    assert not any(r["production_correctness_patch_justified"] for r in rows)
    rows = m._classify({"all_semantic_checks_pass":False,"bounded_hot_provenance_overhead_is_real":False},
                       {"all_semantic_checks_pass":False})
    assert all(r["production_correctness_patch_justified"] for r in rows)

    monkeypatch.setattr(m, "_snapshot_probe", lambda root: deepcopy(good_snapshot))
    monkeypatch.setattr(m, "_foreground_probe", lambda root: deepcopy(good_foreground))
    result = m.build_adjudication(_stage4(), tmp_path)
    assert result["new_production_correctness_defects_confirmed"] == 0

    monkeypatch.setattr(m, "_snapshot_probe", lambda root: {"all_semantic_checks_pass":False,"bounded_hot_provenance_overhead_is_real":True})
    monkeypatch.setattr(m, "_foreground_probe", lambda root: {"all_semantic_checks_pass":False})
    result2 = m.build_adjudication(_stage4(), tmp_path)
    assert result2["new_production_correctness_defects_confirmed"] == 2

    source = tmp_path / "s4.json"; output = tmp_path / "s5.json"
    source.write_text(json.dumps(_stage4()), encoding="utf-8")
    monkeypatch.setattr(m, "build_adjudication", lambda report, root: {"ok": True})
    assert m.write_adjudication(source, output, tmp_path) == {"ok": True}
