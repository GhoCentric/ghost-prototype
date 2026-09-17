import copy
import json

import pytest

from ghost.agent import AgentRuntime, GhostAgent, GOAL_STATUSES


def assert_json_safe(value):
    json.dumps(value, allow_nan=False)


def test_goal_mapping_registration_supports_stateful_specs_and_sorted_ids():
    runtime = AgentRuntime()
    state = runtime.register_agent(
        "sera",
        values={"duty": 0.9, "loyalty": 0.7},
        goals={
            " verify_report ": {
                "status": "inactive",
                "priority": 0.8,
                "progress": 0.1,
                "value_weights": {"duty": 1.0},
                "metadata": {"source": "player"},
            },
            "hold_gate": None,
        },
    )
    assert state["goals"] == ["hold_gate", "verify_report"]
    assert state["goal_states"]["hold_gate"]["status"] == "active"
    assert state["goal_states"]["verify_report"] == {
        "goal_id": "verify_report",
        "status": "inactive",
        "priority": 0.8,
        "progress": 0.1,
        "value_weights": {"duty": 1.0},
        "metadata": {"source": "player"},
        "transition_count": 0,
        "last_transition": None,
    }
    assert_json_safe(state)


def test_goal_mapping_rejects_normalized_collision_bad_spec_unknown_keys_and_metadata():
    runtime = AgentRuntime()
    with pytest.raises(ValueError, match="duplicate normalized id"):
        runtime.register_agent("sera", goals={"x": {}, " x ": {}})
    with pytest.raises(ValueError, match="must be a dict or None"):
        runtime.register_agent("sera", goals={"x": []})
    with pytest.raises(ValueError, match="unsupported keys"):
        runtime.register_agent("sera", goals={"x": {"future": 1}})
    with pytest.raises(ValueError, match="goal metadata"):
        runtime.register_agent("sera", goals={"x": {"metadata": []}})
    assert runtime.has_state() is False


@pytest.mark.parametrize("bad", [True, "0.4", float("nan"), -0.1, 1.1])
def test_goal_priority_progress_and_value_weights_are_bounded(bad):
    runtime = AgentRuntime()
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        runtime.register_agent("sera", goals={"x": {"priority": bad}})
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        runtime.register_agent("sera", goals={"x": {"progress": bad}})
    with pytest.raises(ValueError):
        runtime.register_agent("sera", goals={"x": {"value_weights": {"duty": bad}}})
    assert runtime.has_state() is False


def test_goal_status_validation_is_explicit():
    runtime = AgentRuntime()
    with pytest.raises(ValueError, match="must be a string"):
        runtime.register_agent("sera", goals={"x": {"status": 1}})
    with pytest.raises(ValueError, match="unsupported goal status"):
        runtime.register_agent("sera", goals={"x": {"status": "future"}})
    assert GOAL_STATUSES == {"inactive", "active", "blocked", "satisfied", "abandoned"}


def test_values_are_copy_isolated_and_explicitly_mutable():
    runtime = AgentRuntime()
    runtime.register_agent("sera", values={"duty": 0.8})
    copied = runtime.values("sera")
    copied["duty"] = 0.0
    assert runtime.values("sera") == {"duty": 0.8}
    packet = runtime.set_value("sera", "loyalty", 0.75)
    assert packet == {"agent_id": "sera", "value_id": "loyalty", "before": None, "after": 0.75}
    packet = runtime.set_value("sera", " loyalty ", 0.9)
    assert packet["before"] == 0.75
    assert runtime.values("sera") == {"duty": 0.8, "loyalty": 0.9}


@pytest.mark.parametrize("bad", [True, "1", float("inf"), -0.01, 1.01])
def test_set_value_rejects_invalid_weight_without_mutation(bad):
    runtime = AgentRuntime()
    runtime.register_agent("sera", values={"duty": 0.8})
    before = runtime.snapshot()
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        runtime.set_value("sera", "duty", bad)
    assert runtime.snapshot() == before


def test_agent_state_mutators_require_registered_agent():
    runtime = AgentRuntime()
    for call in (
        lambda: runtime.values("missing"),
        lambda: runtime.set_value("missing", "duty", 0.5),
        lambda: runtime.goals("missing"),
        lambda: runtime.goal("missing", "x"),
        lambda: runtime.add_goal("missing", "x"),
        lambda: runtime.transition_goal("missing", "x", "active"),
        lambda: runtime.set_goal_progress("missing", "x", 0.2),
        lambda: runtime.set_goal_priority("missing", "x", 0.2),
    ):
        with pytest.raises(ValueError, match="agent is not registered"):
            call()
    assert runtime.has_state() is False


def test_add_goal_is_canonical_copy_safe_and_rejects_duplicate():
    runtime = AgentRuntime()
    runtime.register_agent("sera", goals=["zeta"])
    metadata = {"nested": [1]}
    state = runtime.add_goal(
        "sera", " alpha ", status="inactive", priority=0.7, progress=0.2,
        value_weights={"duty": 0.9}, metadata=metadata,
    )
    metadata["nested"].append(2)
    assert state["goal_id"] == "alpha"
    assert runtime.get_state("sera")["goals"] == ["alpha", "zeta"]
    assert runtime.goal("sera", "alpha")["metadata"] == {"nested": [1]}
    with pytest.raises(ValueError, match="already registered"):
        runtime.add_goal("sera", " alpha ")


def test_goal_reads_are_copy_isolated_and_missing_goal_returns_none():
    runtime = AgentRuntime()
    runtime.register_agent("sera", goals=["hold"])
    all_goals = runtime.goals("sera")
    one = runtime.goal("sera", "hold")
    all_goals["hold"]["priority"] = 0.0
    one["metadata"]["x"] = 1
    assert runtime.goal("sera", "hold")["priority"] == 0.5
    assert runtime.goal("sera", "hold")["metadata"] == {}
    assert runtime.goal("sera", "missing") is None


def test_goal_lifecycle_valid_transitions_and_same_state_is_idempotent():
    runtime = AgentRuntime()
    runtime.register_agent("sera", goals={"verify": {"status": "inactive"}})
    no_change = runtime.transition_goal("sera", "verify", "inactive", reason="still_waiting")
    assert no_change["changed"] is False
    assert no_change["transition_count"] == 0
    active = runtime.transition_goal("sera", "verify", "active", reason="report_received")
    blocked = runtime.transition_goal("sera", "verify", "blocked", reason="evidence_missing")
    resumed = runtime.transition_goal("sera", "verify", "active", reason="ledger_found")
    satisfied = runtime.transition_goal("sera", "verify", "satisfied", reason="verified")
    assert [p["to_status"] for p in (active, blocked, resumed, satisfied)] == [
        "active", "blocked", "active", "satisfied",
    ]
    state = runtime.goal("sera", "verify")
    assert state["transition_count"] == 4
    assert state["last_transition"] == {
        "from_status": "active", "to_status": "satisfied", "reason": "verified",
    }


@pytest.mark.parametrize(
    ("start", "target"),
    [
        ("inactive", "blocked"),
        ("inactive", "satisfied"),
        ("satisfied", "active"),
        ("abandoned", "active"),
    ],
)
def test_invalid_goal_lifecycle_transitions_fail_closed(start, target):
    runtime = AgentRuntime()
    runtime.register_agent("sera", goals={"x": {"status": start}})
    before = runtime.snapshot()
    with pytest.raises(ValueError, match="invalid goal lifecycle transition"):
        runtime.transition_goal("sera", "x", target)
    assert runtime.snapshot() == before


def test_goal_transition_requires_existing_goal_and_valid_reason():
    runtime = AgentRuntime()
    runtime.register_agent("sera", goals=["hold"])
    with pytest.raises(ValueError, match="goal is not registered"):
        runtime.transition_goal("sera", "missing", "active")
    with pytest.raises(ValueError):
        runtime.transition_goal("sera", "hold", "blocked", reason="bad|reason")
    with pytest.raises(ValueError, match="unsupported goal status"):
        runtime.transition_goal("sera", "hold", "future")
    assert runtime.goal("sera", "hold")["status"] == "active"


def test_progress_and_priority_mutate_explicitly_without_auto_satisfaction():
    runtime = AgentRuntime()
    runtime.register_agent("sera", goals=["verify"])
    progress = runtime.set_goal_progress("sera", "verify", 1.0)
    priority = runtime.set_goal_priority("sera", "verify", 0.95)
    state = runtime.goal("sera", "verify")
    assert progress == {"agent_id": "sera", "goal_id": "verify", "before": 0.0, "after": 1.0}
    assert priority == {"agent_id": "sera", "goal_id": "verify", "before": 0.5, "after": 0.95}
    assert state["progress"] == 1.0
    assert state["priority"] == 0.95
    assert state["status"] == "active"
    assert state["transition_count"] == 0


@pytest.mark.parametrize("method", ["progress", "priority"])
@pytest.mark.parametrize("bad", [True, "0.2", float("nan"), -0.1, 1.1])
def test_progress_priority_validation_and_missing_goal(method, bad):
    runtime = AgentRuntime()
    runtime.register_agent("sera", goals=["verify"])
    before = runtime.snapshot()
    call = runtime.set_goal_progress if method == "progress" else runtime.set_goal_priority
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        call("sera", "verify", bad)
    assert runtime.snapshot() == before
    with pytest.raises(ValueError, match="goal is not registered"):
        call("sera", "missing", 0.2)


def test_current_snapshot_roundtrip_preserves_goal_history_exactly():
    runtime = AgentRuntime()
    runtime.register_agent(
        "sera", values={"duty": 0.9}, goals={"verify": {"status": "inactive", "priority": 0.8}},
    )
    runtime.transition_goal("sera", "verify", "active", reason="report_received")
    runtime.set_goal_progress("sera", "verify", 0.4)
    runtime.set_value("sera", "duty", 0.95)
    snapshot = runtime.snapshot()
    restored = AgentRuntime.from_snapshot(copy.deepcopy(snapshot))
    assert restored.snapshot() == snapshot
    assert_json_safe(restored.snapshot())


def test_legacy_agent_schema_10_restores_into_11_goal_state():
    legacy = {
        "schema_version": "1.0",
        "agents": {
            "sera": {
                "agent_id": "sera",
                "role": "guard",
                "traits": {"cautious": 0.7},
                "values": {"duty": 0.9},
                "goals": ["hold_gate"],
                "capabilities": ["question"],
                "metadata": {},
            }
        },
    }
    restored = AgentRuntime.from_snapshot(legacy)
    upgraded = restored.snapshot()
    assert upgraded["schema_version"] == "1.1"
    assert upgraded["agents"]["sera"]["goal_states"]["hold_gate"]["status"] == "active"


def _current_snapshot():
    runtime = AgentRuntime()
    runtime.register_agent("sera", goals=["hold"])
    runtime.transition_goal("sera", "hold", "blocked", reason="door_closed")
    return runtime.snapshot()


def test_snapshot_goal_states_requires_dict_and_matching_goal_ids():
    valid = _current_snapshot()
    bad = copy.deepcopy(valid)
    bad["agents"]["sera"]["goal_states"] = []
    with pytest.raises(ValueError, match="goal_states must be a dict"):
        AgentRuntime.from_snapshot(bad)
    bad = copy.deepcopy(valid)
    bad["agents"]["sera"]["goals"] = ["different"]
    with pytest.raises(ValueError, match="same ids"):
        AgentRuntime.from_snapshot(bad)
    assert AgentRuntime.from_snapshot(valid).snapshot() == valid


def test_snapshot_goal_record_shape_and_identity_validation():
    valid = _current_snapshot()
    for mutator, message in (
        (lambda x: x["agents"]["sera"]["goal_states"].__setitem__("hold", []), "must be a dict"),
        (lambda x: x["agents"]["sera"]["goal_states"]["hold"].__setitem__("future", 1), "unsupported keys"),
        (lambda x: x["agents"]["sera"]["goal_states"]["hold"].pop("priority"), "missing required keys"),
        (lambda x: x["agents"]["sera"]["goal_states"]["hold"].__setitem__("goal_id", "other"), "key/id mismatch"),
    ):
        bad = copy.deepcopy(valid)
        mutator(bad)
        with pytest.raises(ValueError, match=message):
            AgentRuntime.from_snapshot(bad)
    assert valid["agents"]["sera"]["goal_states"]["hold"]["goal_id"] == "hold"


@pytest.mark.parametrize("bad_count", [True, -1, 1.5, "1"])
def test_snapshot_goal_transition_count_validation(bad_count):
    bad = _current_snapshot()
    bad["agents"]["sera"]["goal_states"]["hold"]["transition_count"] = bad_count
    with pytest.raises(ValueError, match="non-negative integer"):
        AgentRuntime.from_snapshot(bad)
    assert bad_count is not None


def test_snapshot_last_transition_zero_count_contract():
    runtime = AgentRuntime()
    runtime.register_agent("sera", goals=["hold"])
    bad = runtime.snapshot()
    bad["agents"]["sera"]["goal_states"]["hold"]["last_transition"] = {
        "from_status": "active", "to_status": "blocked", "reason": None,
    }
    with pytest.raises(ValueError, match="must be None"):
        AgentRuntime.from_snapshot(bad)
    assert runtime.goal("sera", "hold")["transition_count"] == 0


def test_snapshot_last_transition_positive_count_shape_validation():
    valid = _current_snapshot()
    for value, message in (
        (None, "must be a dict"),
        ({"from_status": "active", "to_status": "blocked", "reason": None, "future": 1}, "unsupported keys"),
        ({"from_status": "active", "to_status": "blocked"}, "missing required keys"),
    ):
        bad = copy.deepcopy(valid)
        bad["agents"]["sera"]["goal_states"]["hold"]["last_transition"] = value
        with pytest.raises(ValueError, match=message):
            AgentRuntime.from_snapshot(bad)
    assert valid["agents"]["sera"]["goal_states"]["hold"]["transition_count"] == 1


def test_snapshot_last_transition_semantics_validation():
    valid = _current_snapshot()
    cases = [
        ({"from_status": "active", "to_status": "active", "reason": None}, "invalid lifecycle"),
        ({"from_status": "satisfied", "to_status": "active", "reason": None}, "invalid lifecycle"),
        ({"from_status": "active", "to_status": "abandoned", "reason": None}, "equal current"),
    ]
    for transition, message in cases:
        bad = copy.deepcopy(valid)
        bad["agents"]["sera"]["goal_states"]["hold"]["last_transition"] = transition
        with pytest.raises(ValueError, match=message):
            AgentRuntime.from_snapshot(bad)
    assert valid["agents"]["sera"]["goal_states"]["hold"]["status"] == "blocked"


def test_bound_ghost_agent_delegates_values_and_goal_lifecycle():
    class DummyAgents:
        def __init__(self):
            self.calls = []
        def get_state(self, agent): return {"agent_id": agent}
        def values(self, agent): self.calls.append(("values", agent)); return {"duty": 1.0}
        def set_value(self, agent, key, value): self.calls.append(("set_value", agent, key, value)); return {"after": value}
        def goals(self, agent): self.calls.append(("goals", agent)); return {"x": {}}
        def goal(self, agent, goal): self.calls.append(("goal", agent, goal)); return {"goal_id": goal}
        def add_goal(self, agent, goal, **kwargs): self.calls.append(("add", agent, goal, kwargs)); return {"goal_id": goal}
        def transition_goal(self, agent, goal, status, *, reason=None): self.calls.append(("transition", agent, goal, status, reason)); return {"to_status": status}
        def set_goal_progress(self, agent, goal, value): self.calls.append(("progress", agent, goal, value)); return {"after": value}
        def set_goal_priority(self, agent, goal, value): self.calls.append(("priority", agent, goal, value)); return {"after": value}
    class DummyAPI:
        def __init__(self): self.agents = DummyAgents()
    api = DummyAPI()
    agent = GhostAgent(api, " sera ")
    assert agent.values() == {"duty": 1.0}
    assert agent.set_value("duty", 0.8)["after"] == 0.8
    assert "x" in agent.goals()
    assert agent.goal("x")["goal_id"] == "x"
    assert agent.add_goal("y", status="inactive", priority=0.7, progress=0.1, value_weights={"duty": 1.0}, metadata={"x": 1})["goal_id"] == "y"
    assert agent.transition_goal("y", "active", reason="start")["to_status"] == "active"
    assert agent.set_goal_progress("y", 0.4)["after"] == 0.4
    assert agent.set_goal_priority("y", 0.9)["after"] == 0.9
    assert len(api.agents.calls) == 8


def test_snapshot_goal_states_normalized_key_collision_is_rejected():
    runtime = AgentRuntime()
    runtime.register_agent("sera", goals=["hold"])
    snapshot = runtime.snapshot()
    original = snapshot["agents"]["sera"]["goal_states"]["hold"]
    snapshot["agents"]["sera"]["goals"] = ["hold"]
    snapshot["agents"]["sera"]["goal_states"] = {
        "hold": copy.deepcopy(original),
        " hold ": copy.deepcopy(original),
    }
    with pytest.raises(ValueError, match="duplicate normalized id"):
        AgentRuntime.from_snapshot(snapshot)
    assert original["goal_id"] == "hold"


def test_bound_ghost_agent_preserves_phase_two_observation_delegates():
    class DummyAgents:
        def get_state(self, agent): return {"agent_id": agent}
    class DummyPerception:
        def record(self, agent, event, **kwargs):
            return {"agent": agent, "event": event, **kwargs}
        def history(self, agent, *, limit=None):
            return [{"agent": agent, "limit": limit}]
        def latest(self, agent):
            return {"agent": agent, "latest": True}
    class DummyAPI:
        def __init__(self):
            self.agents = DummyAgents()
            self.perception = DummyPerception()
    agent = GhostAgent(DummyAPI(), "sera")
    packet = agent.observe(
        "entity_approached", kind="direct", subject="player", source="world",
        features={"distance": 2.0},
    )
    assert packet["agent"] == "sera"
    assert packet["features"] == {"distance": 2.0}
    assert agent.observation_history(limit=3) == [{"agent": "sera", "limit": 3}]
    assert agent.latest_observation() == {"agent": "sera", "latest": True}
