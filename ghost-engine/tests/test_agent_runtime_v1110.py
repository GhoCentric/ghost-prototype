import copy
import json
import math

import pytest

from ghost.agent import (
    AGENT_SNAPSHOT_SCHEMA_VERSION,
    AgentRuntime,
)


def assert_json_safe(value):
    json.dumps(value, allow_nan=False)


def test_register_agent_builds_normalized_isolated_identity_record():
    traits = {" cautious ": 0.7}
    values = {"loyalty": 1}
    goals = [" guard_gate "]
    capabilities = ["question", "warn"]
    metadata = {"faction": "watch", "nested": {"rank": 2}}
    runtime = AgentRuntime()
    state = runtime.register_agent(
        "  sera  ", role=" guard ", traits=traits, values=values,
        goals=goals, capabilities=capabilities, metadata=metadata,
    )
    traits[" cautious "] = 0.1
    values["loyalty"] = 0.2
    goals.append("leave")
    capabilities.append("attack")
    metadata["nested"]["rank"] = 99
    assert state == {
        "agent_id": "sera",
        "role": "guard",
        "traits": {"cautious": 0.7},
        "values": {"loyalty": 1.0},
        "goals": ["guard_gate"],
        "goal_states": {
            "guard_gate": {
                "goal_id": "guard_gate",
                "status": "active",
                "priority": 0.5,
                "progress": 0.0,
                "value_weights": {},
                "metadata": {},
                "transition_count": 0,
                "last_transition": None,
            },
        },
        "capabilities": ["question", "warn"],
        "metadata": {"faction": "watch", "nested": {"rank": 2}},
    }
    assert runtime.get_state("sera") == state


def test_get_state_returns_copy_and_missing_returns_none():
    runtime = AgentRuntime()
    runtime.register_agent("sera", metadata={"x": [1]})
    state = runtime.get_state("sera")
    state["metadata"]["x"].append(2)
    assert runtime.get_state("sera")["metadata"]["x"] == [1]
    assert runtime.get_state("rowan") is None


def test_has_agent_and_has_state_are_explicit():
    runtime = AgentRuntime()
    assert runtime.has_state() is False
    assert runtime.has_agent("sera") is False
    runtime.register_agent("sera")
    assert runtime.has_state() is True
    assert runtime.has_agent(" sera ") is True


def test_duplicate_registration_is_rejected_after_normalization():
    runtime = AgentRuntime()
    runtime.register_agent("sera")
    with pytest.raises(ValueError, match="already registered"):
        runtime.register_agent(" sera ")
    assert list(runtime.snapshot()["agents"]) == ["sera"]


@pytest.mark.parametrize("agent_id", [None, "", "   ", "bad|id"])
def test_agent_id_uses_public_id_contract(agent_id):
    runtime = AgentRuntime()
    with pytest.raises(ValueError):
        runtime.register_agent(agent_id)
    assert runtime.has_state() is False


@pytest.mark.parametrize("role", ["", "   ", "bad|role"])
def test_invalid_non_none_role_is_rejected(role):
    runtime = AgentRuntime()
    with pytest.raises(ValueError):
        runtime.register_agent("sera", role=role)
    assert runtime.has_state() is False


def test_none_role_is_preserved_as_none():
    runtime = AgentRuntime()
    state = runtime.register_agent("sera", role=None)
    assert state["role"] is None


@pytest.mark.parametrize("field", ["traits", "values"])
def test_channel_map_must_be_dict_or_none(field):
    runtime = AgentRuntime()
    with pytest.raises(ValueError, match="dict or None"):
        runtime.register_agent("sera", **{field: []})
    assert runtime.has_state() is False


@pytest.mark.parametrize("bad", [True, "0.5", None, float("nan"), float("inf"), -0.01, 1.01])
def test_trait_channel_values_must_be_finite_unit_interval_numbers(bad):
    runtime = AgentRuntime()
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        runtime.register_agent("sera", traits={"cautious": bad})
    assert runtime.has_state() is False


def test_channel_normalization_collision_is_rejected():
    runtime = AgentRuntime()
    with pytest.raises(ValueError, match="duplicate normalized key"):
        runtime.register_agent("sera", values={"loyalty": 0.4, " loyalty ": 0.5})
    assert runtime.has_state() is False


def test_capability_list_rejects_non_sequence_and_normalized_duplicates():
    runtime = AgentRuntime()
    with pytest.raises(ValueError, match="list, tuple, or None"):
        runtime.register_agent("sera", capabilities={"x"})
    with pytest.raises(ValueError, match="duplicate normalized id"):
        runtime.register_agent("sera", capabilities=["x", " x "])
    assert runtime.has_state() is False


def test_goal_collection_rejects_wrong_type_and_normalized_duplicates():
    runtime = AgentRuntime()
    with pytest.raises(ValueError, match="list, tuple, dict, or None"):
        runtime.register_agent("sera", goals={"x"})
    with pytest.raises(ValueError, match="duplicate normalized id"):
        runtime.register_agent("sera", goals=["x", " x "])
    assert runtime.has_state() is False


def test_id_lists_accept_tuples_and_normalize_items():
    runtime = AgentRuntime()
    state = runtime.register_agent(
        "sera", goals=(" guard ",), capabilities=(" question ",),
    )
    assert state["goals"] == ["guard"]
    assert state["goal_states"]["guard"]["status"] == "active"
    assert state["capabilities"] == ["question"]


@pytest.mark.parametrize("bad", [[], "metadata", 3])
def test_metadata_must_be_dict_or_none(bad):
    runtime = AgentRuntime()
    with pytest.raises(ValueError, match="metadata must be a dict"):
        runtime.register_agent("sera", metadata=bad)
    assert runtime.has_state() is False


def test_metadata_rejects_non_string_keys_non_json_types_and_nonfinite_numbers():
    runtime = AgentRuntime()
    with pytest.raises(ValueError, match="keys must be strings"):
        runtime.register_agent("sera", metadata={1: "bad"})
    with pytest.raises(ValueError, match="JSON-safe"):
        runtime.register_agent("sera", metadata={"bad": {1, 2}})
    with pytest.raises(ValueError, match="finite numbers"):
        runtime.register_agent("sera", metadata={"bad": float("nan")})
    assert runtime.has_state() is False


def test_metadata_accepts_complete_json_value_surface():
    runtime = AgentRuntime()
    state = runtime.register_agent(
        "sera",
        metadata={
            "none": None,
            "text": "guard",
            "bool": True,
            "int": 2,
            "float": 0.25,
            "list": [1, False, {"nested": "yes"}],
        },
    )
    assert_json_safe(state)
    assert state["metadata"]["list"][2]["nested"] == "yes"


def test_snapshot_is_sorted_json_safe_and_copy_isolated():
    runtime = AgentRuntime()
    runtime.register_agent("zeta", traits={"calm": 0.2})
    runtime.register_agent("alpha", traits={"calm": 0.8})
    snapshot = runtime.snapshot()
    assert snapshot["schema_version"] == AGENT_SNAPSHOT_SCHEMA_VERSION
    assert list(snapshot["agents"]) == ["alpha", "zeta"]
    assert_json_safe(snapshot)
    snapshot["agents"]["alpha"]["traits"]["calm"] = 0.0
    assert runtime.get_state("alpha")["traits"]["calm"] == 0.8


def test_snapshot_is_registration_order_invariant():
    first = AgentRuntime()
    second = AgentRuntime()
    for runtime, order in ((first, ["b", "a"]), (second, ["a", "b"])):
        for agent_id in order:
            runtime.register_agent(agent_id, values={"duty": 0.5})
    assert first.snapshot() == second.snapshot()


def test_snapshot_roundtrip_is_exact_and_continuation_isolated():
    runtime = AgentRuntime()
    runtime.register_agent(
        "sera", role="guard", traits={"cautious": 0.7},
        values={"duty": 0.9}, goals=["hold_gate"],
        capabilities=["question"], metadata={"rank": 2},
    )
    snapshot = runtime.snapshot()
    restored = AgentRuntime.from_snapshot(snapshot)
    snapshot["agents"]["sera"]["metadata"]["rank"] = 99
    assert restored.snapshot() == runtime.snapshot()
    restored.register_agent("rowan")
    assert runtime.get_state("rowan") is None
    assert restored.get_state("rowan")["agent_id"] == "rowan"


@pytest.mark.parametrize("snapshot", [None, [], "bad"])
def test_from_snapshot_requires_dict(snapshot):
    with pytest.raises(ValueError, match="snapshot must be a dict"):
        AgentRuntime.from_snapshot(snapshot)
    assert not isinstance(snapshot, dict)


def test_snapshot_rejects_unknown_and_missing_top_level_keys():
    valid = AgentRuntime().snapshot()
    unknown = copy.deepcopy(valid)
    unknown["future"] = {}
    with pytest.raises(ValueError, match="unsupported keys"):
        AgentRuntime.from_snapshot(unknown)
    missing = copy.deepcopy(valid)
    missing.pop("agents")
    with pytest.raises(ValueError, match="missing required keys"):
        AgentRuntime.from_snapshot(missing)
    assert valid["agents"] == {}


def test_snapshot_rejects_unsupported_schema_and_non_dict_agents():
    with pytest.raises(ValueError, match="unsupported agent snapshot schema"):
        AgentRuntime.from_snapshot({"schema_version": "9.9", "agents": {}})
    with pytest.raises(ValueError, match="agents must be a dict"):
        AgentRuntime.from_snapshot({"schema_version": "1.0", "agents": []})
    assert AGENT_SNAPSHOT_SCHEMA_VERSION == "1.1"


def test_snapshot_rejects_bad_record_shape_and_key_identity_mismatch():
    base = AgentRuntime()
    base.register_agent("sera")
    valid = base.snapshot()

    not_dict = copy.deepcopy(valid)
    not_dict["agents"]["sera"] = []
    with pytest.raises(ValueError, match="must be a dict"):
        AgentRuntime.from_snapshot(not_dict)

    unknown = copy.deepcopy(valid)
    unknown["agents"]["sera"]["future"] = 1
    with pytest.raises(ValueError, match="unsupported keys"):
        AgentRuntime.from_snapshot(unknown)

    missing = copy.deepcopy(valid)
    missing["agents"]["sera"].pop("role")
    with pytest.raises(ValueError, match="missing required keys"):
        AgentRuntime.from_snapshot(missing)

    mismatch = copy.deepcopy(valid)
    mismatch["agents"]["sera"]["agent_id"] = "rowan"
    with pytest.raises(ValueError, match="key/id mismatch"):
        AgentRuntime.from_snapshot(mismatch)

    assert AgentRuntime.from_snapshot(valid).snapshot() == valid


def test_ghost_agent_bound_handle_delegates_state_snapshot_and_repr():
    from ghost.agent import GhostAgent

    class DummyAPI:
        def __init__(self):
            self.calls = []

        def agent_state(self, agent_id, *, include_layers=True):
            self.calls.append((agent_id, include_layers))
            return {"agent_id": agent_id, "include_layers": include_layers}

    api = DummyAPI()
    handle = GhostAgent(api, " sera ")
    assert handle.agent_id == "sera"
    assert handle.state(include_layers=False) == {
        "agent_id": "sera", "include_layers": False,
    }
    assert handle.snapshot() == {"agent_id": "sera", "include_layers": True}
    assert repr(handle) == "GhostAgent(agent_id='sera')"
    assert api.calls == [("sera", False), ("sera", True)]


def test_ghost_agent_detects_disappeared_registration():
    from ghost.agent import GhostAgent

    class MissingAPI:
        def agent_state(self, agent_id, *, include_layers=True):
            assert agent_id == "sera"
            assert include_layers is True
            return None

    handle = GhostAgent(MissingAPI(), "sera")
    with pytest.raises(RuntimeError, match="registered agent disappeared"):
        handle.state()
    assert handle.agent_id == "sera"


def test_phase_one_runtime_has_no_observation_or_decision_methods():
    runtime = AgentRuntime()
    assert not hasattr(runtime, "observe")
    assert not hasattr(runtime, "consider")
    assert not hasattr(runtime, "resolve_intent")
