import copy
import json

import pytest

from ghost import GhostAPI


def assert_json_safe(value):
    json.dumps(value, allow_nan=False)


def test_public_agent_values_and_goal_lifecycle_flow():
    api = GhostAPI()
    sera = api.register_agent(
        "sera",
        role="guard",
        values={"protect_town": 0.9, "loyalty": 0.7},
        goals={
            "maintain_post": {
                "status": "active",
                "priority": 0.85,
                "value_weights": {"protect_town": 1.0},
            },
            "verify_report": {
                "status": "inactive",
                "priority": 0.7,
                "value_weights": {"loyalty": 0.6, "protect_town": 0.8},
            },
        },
    )
    assert sera.values() == {"loyalty": 0.7, "protect_town": 0.9}
    assert sera.goal("verify_report")["status"] == "inactive"
    start = sera.transition_goal("verify_report", "active", reason="player_report_received")
    sera.set_goal_progress("verify_report", 0.4)
    sera.set_goal_priority("verify_report", 0.9)
    blocked = sera.transition_goal("verify_report", "blocked", reason="evidence_unavailable")
    assert start["changed"] is True
    assert blocked["to_status"] == "blocked"
    assert sera.goal("verify_report")["progress"] == 0.4
    assert sera.goal("verify_report")["priority"] == 0.9
    assert_json_safe(api.snapshot())


def test_agent_goal_mutations_do_not_create_world_or_cognitive_facts():
    api = GhostAPI()
    sera = api.register_agent("sera", values={"duty": 0.8}, goals=["hold_gate"])
    epistemic_before = copy.deepcopy(api.epistemic.snapshot())
    perception_before = copy.deepcopy(api.perception.snapshot())
    emotion_before = api.emotional_state("sera")
    interpretation_before = api.interpretation_state("sera")
    attention_before = api.attention_state("sera")
    sera.set_value("duty", 0.9)
    sera.transition_goal("hold_gate", "blocked", reason="gate_destroyed")
    assert api.epistemic.snapshot() == epistemic_before
    assert api.perception.snapshot() == perception_before
    assert api.emotional_state("sera") == emotion_before
    assert api.interpretation_state("sera") == interpretation_before
    assert api.attention_state("sera") == attention_before


def test_observation_intake_does_not_automatically_change_values_or_goals():
    api = GhostAPI()
    sera = api.register_agent(
        "sera", values={"duty": 0.8},
        goals={"verify_report": {"status": "inactive", "priority": 0.7}},
    )
    before_values = sera.values()
    before_goals = sera.goals()
    sera.observe(
        "captain_took_bribe",
        kind="report",
        subject="captain",
        source="player",
        features={"claimed_location": "market"},
    )
    assert sera.values() == before_values
    assert sera.goals() == before_goals


def test_public_add_goal_and_value_update_are_explicit_and_copy_safe():
    api = GhostAPI()
    sera = api.register_agent("sera")
    value_packet = sera.set_value("protect_town", 0.9)
    metadata = {"source": ["captain"]}
    goal = sera.add_goal(
        "verify_report",
        status="inactive",
        priority=0.75,
        progress=0.1,
        value_weights={"protect_town": 0.8},
        metadata=metadata,
    )
    metadata["source"].append("player")
    goal["metadata"]["source"].append("mutated")
    assert value_packet["before"] is None
    assert sera.values()["protect_town"] == 0.9
    assert sera.goal("verify_report")["metadata"] == {"source": ["captain"]}
    assert "verify_report" in sera.goals()


def test_api_agent_state_includes_goal_states_as_part_of_owned_agent_profile():
    api = GhostAPI()
    sera = api.register_agent("sera", goals=["hold_gate"])
    profile = sera.state(include_layers=False)
    full = sera.state()
    assert profile["goal_states"]["hold_gate"]["status"] == "active"
    assert full["goal_states"] == profile["goal_states"]
    assert full["layers"]["perception"] is None


def test_agent_value_goal_surface_requires_a_registered_bound_handle():
    api = GhostAPI()
    before = api.snapshot()
    assert api.agent("sera") is None
    for name in (
        "agent_values", "set_agent_value", "agent_goals", "agent_goal",
        "add_agent_goal", "transition_agent_goal",
        "set_agent_goal_progress", "set_agent_goal_priority",
    ):
        assert not hasattr(api, name)
    assert api.snapshot() == before


def test_api_snapshot_roundtrip_preserves_values_goal_state_and_transition_history():
    api = GhostAPI()
    sera = api.register_agent(
        "sera", values={"duty": 0.8},
        goals={"verify": {"status": "inactive", "priority": 0.7}},
    )
    sera.transition_goal("verify", "active", reason="report_received")
    sera.set_goal_progress("verify", 0.35)
    sera.set_value("duty", 0.9)
    snapshot = api.snapshot()
    assert snapshot["agents"]["schema_version"] == "1.1"
    restored = GhostAPI.from_snapshot(copy.deepcopy(snapshot))
    assert restored.snapshot() == snapshot
    assert restored.agent("sera").goal("verify") == sera.goal("verify")


def test_api_restores_phase_two_agent_schema_10_snapshot_as_supported_legacy():
    api = GhostAPI()
    api.register_agent("sera", role="guard", values={"duty": 0.8}, goals=["hold_gate"])
    snapshot = api.snapshot()
    legacy = copy.deepcopy(snapshot)
    agent_record = legacy["agents"]["agents"]["sera"]
    legacy["agents"]["schema_version"] = "1.0"
    agent_record.pop("goal_states")
    restored = GhostAPI.from_snapshot(legacy)
    upgraded = restored.snapshot()
    assert upgraded["agents"]["schema_version"] == "1.1"
    assert upgraded["agents"]["agents"]["sera"]["goal_states"]["hold_gate"]["status"] == "active"


def test_terminal_goal_state_requires_explicit_new_goal_instead_of_implicit_revival():
    api = GhostAPI()
    sera = api.register_agent("sera", goals=["verify"])
    sera.transition_goal("verify", "satisfied", reason="verified")
    before = api.snapshot()
    with pytest.raises(ValueError, match="invalid goal lifecycle transition"):
        sera.transition_goal("verify", "active", reason="repeat")
    assert api.snapshot() == before


def test_phase_four_adds_motives_but_still_has_no_intent_or_action_execution():
    api = GhostAPI()
    sera = api.register_agent("sera", values={"duty": 1.0}, goals=["hold_gate"])
    assert hasattr(sera, "configure_motive")
    assert hasattr(sera, "evaluate_motives")
    assert not hasattr(sera, "consider")
    assert not hasattr(sera, "step")
    assert not hasattr(sera, "resolve_intent")
