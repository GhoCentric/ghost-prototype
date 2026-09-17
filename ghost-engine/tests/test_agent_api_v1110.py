import copy
import json

import pytest

import ghost
from ghost import GhostAPI
from ghost.agent import GhostAgent
from ghost.engine import GHOST_PACKAGE_VERSION, GHOST_SNAPSHOT_SCHEMA_VERSION


def assert_json_safe(value):
    json.dumps(value, allow_nan=False)


def test_public_api_registers_and_recovers_bound_agent_handle():
    api = GhostAPI()
    sera = api.register_agent(
        " sera ", role="guard", traits={"cautious": 0.7},
        values={"duty": 0.9}, goals=["hold_gate"],
        capabilities=["question", "warn"], metadata={"faction": "watch"},
    )
    again = api.agent("sera")
    assert isinstance(sera, GhostAgent)
    assert isinstance(again, GhostAgent)
    assert sera.agent_id == "sera"
    assert again.agent_id == "sera"
    assert api.agent("missing") is None


def test_agent_state_can_be_profile_only_or_coherent_layer_view():
    api = GhostAPI()
    sera = api.register_agent("sera", role="guard")
    profile = sera.state(include_layers=False)
    full = sera.state()
    assert profile["agent_id"] == "sera"
    assert "layers" not in profile
    assert full["layers"] == {
        "emotions": None,
        "interpretation": None,
        "attention": None,
        "perception": None,
        "motives": None,
        "affordances": None,
    }


def test_agent_state_reads_existing_layers_without_mutating_them():
    api = GhostAPI()
    sera = api.register_agent("sera", role="guard")
    api.register_emotional_agent("sera", initial={"anger": 0.4, "fear": 0.2})
    api.register_interpretation_agent("sera")
    api.register_attention_agent("sera")
    before = api.snapshot()
    state = sera.state()
    after = api.snapshot()
    assert state["layers"]["emotions"] == api.emotional_state("sera")
    assert state["layers"]["interpretation"] == api.interpretation_state("sera")
    assert state["layers"]["attention"] == api.attention_state("sera")
    assert after == before


def test_agent_state_missing_and_include_layers_validation():
    api = GhostAPI()
    assert api.agent_state("missing") is None
    api.register_agent("sera")
    with pytest.raises(ValueError, match="include_layers must be a bool"):
        api.agent_state("sera", include_layers=1)
    assert api.agent_state("sera", include_layers=False)["agent_id"] == "sera"


def test_bound_handle_state_is_copy_isolated_and_repr_is_stable():
    api = GhostAPI()
    sera = api.register_agent("sera", metadata={"nested": [1]})
    state = sera.snapshot()
    state["metadata"]["nested"].append(2)
    assert sera.state(include_layers=False)["metadata"]["nested"] == [1]
    assert repr(sera) == "GhostAgent(agent_id='sera')"


def test_empty_api_snapshot_omits_agent_layer_and_registered_snapshot_includes_it():
    api = GhostAPI()
    empty = api.snapshot()
    assert "agents" not in empty
    api.register_agent("sera", role="guard")
    snapshot = api.snapshot()
    assert snapshot["agents"]["schema_version"] == "1.1"
    assert snapshot["agents"]["agents"]["sera"]["role"] == "guard"
    assert_json_safe(snapshot)


def test_api_snapshot_roundtrip_restores_bound_identity_exactly():
    api = GhostAPI()
    api.register_agent(
        "sera", role="guard", traits={"cautious": 0.7},
        values={"duty": 0.9}, goals=["hold_gate"], capabilities=["question"],
    )
    snapshot = api.snapshot()
    restored = GhostAPI.from_snapshot(snapshot)
    assert restored.snapshot() == snapshot
    assert restored.agent("sera").state() == api.agent("sera").state()


def test_legacy_v110_snapshot_without_agents_restores_unchanged():
    api = GhostAPI()
    api.register_agent("sera")
    with_agents = api.snapshot()
    legacy = copy.deepcopy(with_agents)
    legacy.pop("agents")
    restored = GhostAPI.from_snapshot(legacy)
    assert restored.agent("sera") is None
    assert restored.snapshot() == legacy


def test_api_rejects_non_dict_and_invalid_agent_snapshot():
    api = GhostAPI()
    snapshot = api.snapshot()
    bad_type = copy.deepcopy(snapshot)
    bad_type["agents"] = []
    with pytest.raises(ValueError, match="snapshot agents must be a dict"):
        GhostAPI.from_snapshot(bad_type)

    bad_schema = copy.deepcopy(snapshot)
    bad_schema["agents"] = {"schema_version": "9.9", "agents": {}}
    with pytest.raises(ValueError, match="unsupported agent snapshot schema"):
        GhostAPI.from_snapshot(bad_schema)
    assert "agents" not in snapshot


def test_in_place_restore_rebinds_agent_runtime():
    first = GhostAPI()
    first.register_agent("sera", role="guard")
    snapshot = first.snapshot()
    second = GhostAPI()
    second.register_agent("rowan", role="merchant")
    result = second.restore_snapshot(snapshot)
    assert result == snapshot
    assert second.agent("sera").state()["role"] == "guard"
    assert second.agent("rowan") is None


def test_agent_registration_does_not_create_cognitive_or_perception_history():
    api = GhostAPI()
    sera = api.register_agent("sera", role="guard")
    assert api.emotional_state("sera") is None
    assert api.interpretation_state("sera") is None
    assert api.attention_state("sera") is None
    assert sera.state()["layers"]["perception"] is None
    assert sera.motive_field() is None
    assert sera.affordances() is None


def test_v111_phase_one_does_not_change_release_version_or_top_schema():
    api = GhostAPI()
    api.register_agent("sera")
    snapshot = api.snapshot()
    assert ghost.__version__ == "1.10.0"
    assert GHOST_PACKAGE_VERSION == "1.10.0"
    assert GHOST_SNAPSHOT_SCHEMA_VERSION == "1.0"
    assert snapshot["schema_version"] == "1.0"


def test_phase_two_handle_adds_observe_but_still_has_no_step_or_resolve_intent():
    api = GhostAPI()
    sera = api.register_agent("sera")
    assert hasattr(sera, "observe")
    assert not hasattr(sera, "step")
    assert not hasattr(sera, "resolve_intent")

def test_direct_bound_handle_rejects_unregistered_agent_mutation():
    api = GhostAPI()
    missing = GhostAgent(api, "missing")
    with pytest.raises(
        ValueError, match="agent must be registered before agent-state mutation"
    ):
        missing.values()


def test_direct_bound_handle_translates_unregistered_observer_error():
    api = GhostAPI()
    missing = GhostAgent(api, "missing")
    with pytest.raises(
        ValueError, match="observer must be a registered GhostAgent before observation"
    ):
        missing.observe("signal")

