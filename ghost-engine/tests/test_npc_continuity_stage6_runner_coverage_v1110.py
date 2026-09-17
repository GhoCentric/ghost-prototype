from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from continuity_benchmark_v1110 import run_stage6_behavioral_value as runner
from continuity_benchmark_v1110 import stage6_behavior_policy as policy
from continuity_benchmark_v1110 import stage6_behavior_scenarios as scenarios


class FakeArchive:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fake-archive")


class FakeSystem:
    def __init__(self, path: Path, snapshot=None):
        self.archive = FakeArchive(path)
        self.closed = False
        self.episodes = []
        self.state = {
            "meaning": {}, "activation": {},
            "emotion": {"anger": 0.0, "fear": 0.0, "grief": 0.0, "hope": 0.0},
            "trust": 0.0, "foreground": None, "tick": 0, "episode_count": 0,
        }
        if snapshot is not None:
            self.state = deepcopy(snapshot["state"])
            self.episodes = deepcopy(snapshot["episodes"])

    def event(self, agent, *, source, dimension, meaning_delta, relevance, emotion_profile, consequence):
        del agent
        row = {
            "episode_id": f"e{len(self.episodes)+1}", "source": source,
            "dimension": dimension, "emotion_profile": deepcopy(emotion_profile),
        }
        self.episodes.append(row)
        self.state["episode_count"] = len(self.episodes)
        self.state["meaning"][dimension] = min(1.0, max(0.0, self.state["meaning"].get(dimension, 0.0) + meaning_delta))
        self.state["activation"][dimension] = min(1.0, self.state["activation"].get(dimension, 0.0) + abs(relevance))
        for name, value in emotion_profile.items():
            self.state["emotion"][name] = min(1.0, self.state["emotion"].get(name, 0.0) + value)
        self.state["trust"] += consequence
        self.state["foreground"] = dimension
        return deepcopy(row)

    def tick(self, agent, steps=1):
        del agent
        for key in self.state["activation"]:
            self.state["activation"][key] *= 0.1 ** steps
        for key in self.state["emotion"]:
            self.state["emotion"][key] *= 0.5 ** steps
        self.state["tick"] += steps

    def revise(self, agent, dimension, meaning_delta):
        del agent
        self.state["meaning"][dimension] = min(1.0, max(0.0, self.state["meaning"].get(dimension, 0.0) + meaning_delta))

    def recall_episode(self, episode_id, strength):
        row = next(row for row in self.episodes if row["episode_id"] == episode_id)
        self.state["activation"][row["dimension"]] = min(1.0, self.state["activation"].get(row["dimension"], 0.0) + strength)
        for name, value in row["emotion_profile"].items():
            self.state["emotion"][name] = min(1.0, self.state["emotion"].get(name, 0.0) + value * strength)
        emotion = max(row["emotion_profile"], key=row["emotion_profile"].get) if row["emotion_profile"] else None
        self.state["foreground"] = f"emotion:{emotion}" if emotion else row["dimension"]
        return {"episode_id": episode_id}

    def recall_dimension(self, agent, dimension, strength):
        del agent, strength
        rows = [row for row in self.episodes if row["dimension"] == dimension]
        if len(rows) > 1:
            return {"status": "ambiguous", "candidate_count": len(rows)}
        if not rows:
            return {"status": "missing", "candidate_count": 0}
        return {"status": "unique", "candidate_count": 1}

    def observe(self, agent):
        del agent
        return deepcopy(self.state)

    def snapshot(self):
        return {"state": deepcopy(self.state), "episodes": deepcopy(self.episodes)}

    def get_episode(self, episode_id):
        for row in self.episodes:
            if row["episode_id"] == episode_id:
                return deepcopy(row)
        return None

    def close(self):
        self.closed = True


def fake_factory(kind, root, label, *, snapshot=None):
    del kind
    return FakeSystem(Path(root) / f"{label}.sqlite", snapshot=snapshot)


def test_policy_all_branches():
    assert policy.seeded_float("a", 1, 2) == policy.seeded_float("a", 1, 2)
    assert policy.seeded_int("a", 2, 2) == 2
    with pytest.raises(ValueError): policy.seeded_int("a", 2, 1)
    assert policy.clamp(-1) == 0 and policy.clamp(2) == 1 and policy.clamp(.5) == .5
    for token, action in [
        ("respect", "cooperate"), ("emotion:hope", "cooperate"),
        ("threat", "guard"), ("emotion:fear", "guard"),
        ("betrayal", "confront"), ("emotion:anger", "confront"),
        ("emotion:grief", "withdraw"), ("x", None), (None, None),
    ]:
        assert policy.foreground_action(token) == action
    with pytest.raises(ValueError): policy.policy_weights(policy.POLICY_VARIANTS)
    state = {
        "meaning": {"respect": .4, "threat": .3, "betrayal": .2},
        "activation": {"respect": .3, "threat": .2, "betrayal": .1},
        "emotion": {"hope": .4, "fear": .3, "anger": .2, "grief": .1},
        "trust": 3.0, "foreground": "emotion:hope",
    }
    assert policy.behavior_scores(state, 0)["cooperate"] > policy.behavior_scores(state, 0, use_foreground=False)["cooperate"]
    state["trust"] = -3.0; state["foreground"] = "x"
    assert set(policy.behavior_scores(state, 1)) == set(policy.ACTIONS)
    empty = {"meaning": {}, "activation": {}, "emotion": {}, "trust": 0, "foreground": None}
    sig = policy.behavior_signature(empty); assert sum(sig["winner_counts"].values()) == 16
    assert policy.behavior_distance(sig, sig) == 0
    assert policy.robust(lambda _: True)["passed"]
    assert not policy.robust(lambda _: False)["passed"]


def test_all_scenarios_with_fast_fake(monkeypatch, tmp_path):
    original_factory = scenarios.factory
    monkeypatch.setattr(scenarios, "factory", fake_factory)
    result = scenarios.run_quality("baseline", tmp_path)
    assert result["total"] == 26
    assert len(result["scenarios"]) == len(scenarios.SCENARIOS)
    monkeypatch.setattr(scenarios, "factory", original_factory)
    real_b = scenarios.factory("baseline", tmp_path / "real", "b"); real_b.close()
    real_g = scenarios.factory("ghost", tmp_path / "real", "g"); real_g.close()
    with pytest.raises(ValueError): scenarios.factory("bad", tmp_path, "bad")


def test_restart_exception_cleanup_branch(monkeypatch, tmp_path):
    made = []
    def tracked_factory(kind, root, label, *, snapshot=None):
        system = FakeSystem(Path(root) / f"{label}.sqlite", snapshot=snapshot); made.append(system); return system
    monkeypatch.setattr(scenarios, "factory", tracked_factory)
    original_event = scenarios.event
    monkeypatch.setattr(scenarios, "event", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError): scenarios.restart_behavior_identity("baseline", tmp_path)
    assert made[0].closed
    monkeypatch.setattr(scenarios, "event", original_event)


def _quality(passed, total=26, *, ghost_wins=False, ghost_loss=False):
    checks_b = {"a": not ghost_wins, "b": True}
    checks_g = {"a": True, "b": not ghost_loss}
    base = {"kind": "baseline", "passed": passed, "total": total,
            "scenarios": {
                "episode_specific_affect": {"checks": checks_b, "ablation": {"fear_without_foreground": {"policy_passes": 15, "policy_total": 16, "passed": True}}},
                "betrayal_affect_mode_resolution": {"checks": {"x": True}, "ablation": {"fear_without_foreground": {"policy_passes": 15, "policy_total": 16, "passed": True}, "grief_without_foreground": {"policy_passes": 10, "policy_total": 16, "passed": False}}},
            }}
    ghost = deepcopy(base); ghost["kind"] = "ghost"; ghost["passed"] = passed; ghost["scenarios"]["episode_specific_affect"]["checks"] = checks_g
    return base, ghost


def test_runner_helpers_workload_verdicts_and_cli(monkeypatch, tmp_path, capsys):
    # Helper list branches and ablation.
    b, g = _quality(20, ghost_wins=True, ghost_loss=True)
    assert runner._ghost_only_passes(b, g)
    assert runner._baseline_only_failures(b, g)
    assert runner._foreground_ablation(b, g)["equalized_without_foreground"]
    assert runner._ratio(2, 1) == 2 and runner._ratio(2, 0) is None

    # Fast workload covers dimension/consequence branches.
    monkeypatch.setattr(runner, "factory", fake_factory)
    monkeypatch.setattr(runner, "seeded_int", lambda *args: 3)
    monkeypatch.setattr(runner, "event", scenarios.event)
    workload = runner._workload("baseline", tmp_path / "work")
    assert workload["episodes"] == 3 and workload["snapshot_bytes"] > 0

    # build_result branches using synthetic quality packets.
    def run_case(base_pass, ghost_pass, *, losses=False, ablation=True, eng_ratio=1.0):
        base, ghost = _quality(base_pass)
        ghost["passed"] = ghost_pass
        if losses:
            ghost["scenarios"]["episode_specific_affect"]["checks"]["b"] = False
        sequence = iter([base, ghost, deepcopy(base), deepcopy(ghost)])
        monkeypatch.setattr(runner, "run_quality", lambda kind, root: next(sequence))
        monkeypatch.setattr(runner, "_foreground_ablation", lambda b, g: {"equalized_without_foreground": ablation})
        monkeypatch.setattr(runner, "_workload", lambda kind, root: {"snapshot_bytes": 10 if kind == "baseline" else 10*eng_ratio, "archive_bytes": 10, "event_avg_us": 1, "tick_avg_us": 1, "recall_avg_us": 1})
        return runner.build_result(tmp_path / f"case-{base_pass}-{ghost_pass}-{losses}-{ablation}-{eng_ratio}")

    assert run_case(20, 19)["strict_verdict"] == "GHOST_BEHAVIORAL_VALUE_DISADVANTAGE"
    assert run_case(20, 22)["strict_verdict"].startswith("LIMITED_GHOST_BEHAVIORAL_ADVANTAGE")
    assert run_case(20, 21, ablation=False)["strict_verdict"] == "GHOST_BEHAVIORAL_EDGE_OBSERVED_BUT_CAUSAL_ADVANTAGE_NOT_ESTABLISHED"
    assert run_case(20, 20, eng_ratio=3)["strict_verdict"] == "NO_GHOST_BEHAVIORAL_ADVANTAGE_SIMPLER_BASELINE_HAS_ENGINEERING_ADVANTAGE"
    assert run_case(20, 20, eng_ratio=1)["strict_verdict"] == "NO_CLEAR_BEHAVIORAL_WINNER"
    assert run_case(20, 22, losses=True)["strict_verdict"] == "GHOST_BEHAVIORAL_VALUE_DISADVANTAGE"

    # Explicitly cover build_result's no-engineering branch.
    base, ghost = _quality(20)
    seq = iter([base, ghost, deepcopy(base), deepcopy(ghost)])
    monkeypatch.setattr(runner, "run_quality", lambda kind, root: next(seq))
    monkeypatch.setattr(runner, "_foreground_ablation", lambda b, g: {"equalized_without_foreground": True})
    no_eng = runner.build_result(tmp_path / "no-eng", include_engineering=False)
    assert no_eng["engineering"] is None

    fake_result = {"strict_verdict": "CLI", "x": 1}
    monkeypatch.setattr(runner, "build_result", lambda root, include_engineering=True: fake_result)
    out = tmp_path / "out.json"
    assert runner.main(["--root", str(tmp_path / "cli"), "--out", str(out), "--no-engineering"]) == 0
    assert json.loads(out.read_text()) == fake_result
    assert runner.main([]) == 0
    assert '"strict_verdict": "CLI"' in capsys.readouterr().out


def test_module_entrypoint_line(monkeypatch, tmp_path):
    import runpy, sys
    base, ghost = _quality(20)
    monkeypatch.setattr(scenarios, "run_quality", lambda kind, root: deepcopy(base if kind == "baseline" else ghost))
    monkeypatch.setattr(sys, "argv", ["stage6", "--root", str(tmp_path / "entry"), "--no-engineering"])
    monkeypatch.delitem(sys.modules, "continuity_benchmark_v1110.run_stage6_behavioral_value", raising=False)
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("continuity_benchmark_v1110.run_stage6_behavioral_value", run_name="__main__")
    assert exc.value.code == 0
