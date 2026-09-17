import copy
import json

import pytest

from ghost import GhostAPI
from ghost.motives import MOTIVE_SNAPSHOT_SCHEMA_VERSION


def assert_json_safe(value):
    json.dumps(value, allow_nan=False, sort_keys=True)


def make_agent(api):
    return api.register_agent(
        "sera",
        role="guard",
        traits={"cautious": 0.72},
        values={"protect_town": 0.9, "personal_safety": 0.5},
        goals={
            "maintain_post": {"status": "active", "priority": 0.8, "progress": 0.0},
            "verify_report": {"status": "inactive", "priority": 0.75, "progress": 0.0},
        },
    )


def test_bound_agent_configures_and_evaluates_deterministic_motive_field():
    api = GhostAPI()
    sera = make_agent(api)
    sera.configure_motive(
        "protect",
        baseline=0.05,
        weights={
            "value:protect_town": 0.45,
            "goal:maintain_post:priority_remaining": 0.50,
        },
    )
    sera.configure_motive(
        "investigate",
        baseline=0.05,
        weights={
            "value:protect_town": 0.20,
            "goal:verify_report:priority_remaining": 0.80,
        },
    )
    before = sera.evaluate_motives()
    assert before["dominant_motive"] == "protect"
    assert before["motives"]["investigate"]["score"] < before["motives"]["protect"]["score"]

    sera.transition_goal("maintain_post", "blocked", reason="relief_guard_arrived")
    sera.set_goal_progress("maintain_post", 1.0)
    sera.transition_goal("verify_report", "active", reason="credible_report_received")
    sera.set_goal_priority("verify_report", 0.95)
    after = sera.evaluate_motives()
    assert after["dominant_motive"] == "investigate"
    assert after["sequence"] == before["sequence"] + 1
    assert after["motives"]["investigate"]["score"] > before["motives"]["investigate"]["score"]
    assert_json_safe(after)


def test_motive_signal_packet_reads_persistent_salience_and_attended_foreground():
    api = GhostAPI()
    sera = make_agent(api)
    api.register_emotional_agent("sera", initial={"anger": 0.8, "fear": 0.2})
    bridge = api.persistent_salience("sera")
    assert bridge["salience"]["emotion:anger"] > 0.0

    api.register_attention_agent("sera")
    api.advance_attention_from_state(
        "sera",
        signals={"threat": 1.0},
        provenance={"test": "phase4"},
    )
    signals = sera.motive_signals()
    assert signals["signals"]["persistent:emotion:anger"] == bridge["salience"]["emotion:anger"]
    assert "attended:emotion:anger" in signals["signals"]
    assert signals["sources"]["attention"]["revision"] is not None


def test_raw_observation_does_not_directly_mutate_motive_field():
    api = GhostAPI()
    sera = make_agent(api)
    sera.configure_motive("protect", weights={"value:protect_town": 0.5})
    before = sera.evaluate_motives()
    sera.observe(
        "player_approached",
        subject="player",
        features={"distance": 2.0, "visible": True},
    )
    after = sera.evaluate_motives()
    assert after["motives"]["protect"]["score"] == before["motives"]["protect"]["score"]
    assert "perception" not in " ".join(after["signals"])


def test_missing_configured_signal_is_zero_and_explicitly_audited():
    api = GhostAPI()
    sera = make_agent(api)
    sera.configure_motive("investigate", baseline=0.2, weights={"persistent:interpretation:suspicion": 0.5})
    result = sera.evaluate_motives()
    motive = result["motives"]["investigate"]
    assert motive["score"] == 0.2
    assert motive["missing_signals"] == ["persistent:interpretation:suspicion"]


def test_motive_configuration_is_explicit_removable_and_copy_safe():
    api = GhostAPI()
    sera = make_agent(api)
    configured = sera.configure_motive("protect", baseline=0.1, weights={"value:protect_town": 0.4})
    profiles = sera.motive_profiles()
    profiles["protect"]["baseline"] = 1.0
    assert sera.motive_profiles()["protect"] == configured
    assert sera.remove_motive("missing") is False
    assert sera.remove_motive("protect") is True
    assert sera.motive_profiles() == {}


def test_agent_state_includes_current_motive_field_without_recomputing_it():
    api = GhostAPI()
    sera = make_agent(api)
    sera.configure_motive("protect", baseline=0.3)
    assert sera.state()["layers"]["motives"] is None
    evaluated = sera.evaluate_motives()
    before = api.snapshot()
    state = sera.state()
    after = api.snapshot()
    assert state["layers"]["motives"] == evaluated
    assert after == before


def test_motive_surface_requires_a_registered_bound_handle():
    api = GhostAPI()
    before = api.snapshot()
    assert api.agent("sera") is None
    for name in (
        "configure_agent_motive", "remove_agent_motive", "agent_motive_profiles",
        "agent_motive_signals", "evaluate_agent_motives",
        "agent_motive_state", "agent_motive_history",
    ):
        assert not hasattr(api, name)
    assert api.snapshot() == before


def test_motive_snapshot_roundtrip_and_continuation_are_exact():
    api = GhostAPI()
    sera = make_agent(api)
    sera.configure_motive("protect", baseline=.1, weights={"value:protect_town": .5})
    first = sera.evaluate_motives()
    snapshot = api.snapshot()
    assert snapshot["motives"]["schema_version"] == MOTIVE_SNAPSHOT_SCHEMA_VERSION
    restored = GhostAPI.from_snapshot(copy.deepcopy(snapshot))
    assert restored.snapshot() == snapshot
    restored_next = restored.agent("sera").evaluate_motives()
    original_next = sera.evaluate_motives()
    assert restored_next == original_next
    assert restored_next["sequence"] == first["sequence"] + 1


def test_legacy_snapshot_without_motives_restores_with_empty_motive_runtime():
    api = GhostAPI()
    sera = make_agent(api)
    sera.configure_motive("protect", baseline=.2)
    sera.evaluate_motives()
    snapshot = api.snapshot()
    legacy = copy.deepcopy(snapshot)
    legacy.pop("motives")
    restored = GhostAPI.from_snapshot(legacy)
    assert restored.agent("sera").motive_profiles() == {}
    assert restored.agent("sera").motive_field() is None
    assert "motives" not in restored.snapshot()


def test_snapshot_rejects_motive_state_owned_by_unregistered_agent():
    api = GhostAPI()
    sera = make_agent(api)
    sera.configure_motive("protect", baseline=.2)
    snapshot = api.snapshot()
    tampered = copy.deepcopy(snapshot)
    tampered["motives"]["profiles"] = {"unknown": tampered["motives"]["profiles"]["sera"]}
    with pytest.raises(ValueError, match="snapshot motive agent must reference a registered agent"):
        GhostAPI.from_snapshot(tampered)


def test_snapshot_rejects_non_dict_motive_section():
    api = GhostAPI()
    snapshot = api.snapshot()
    snapshot["motives"] = []
    with pytest.raises(ValueError, match="snapshot motives must be a dict"):
        GhostAPI.from_snapshot(snapshot)


def test_motive_history_public_limit_and_bound_handle_surface():
    api = GhostAPI()
    sera = make_agent(api)
    sera.configure_motive("protect", baseline=.2)
    sera.evaluate_motives()
    second = sera.evaluate_motives()
    assert sera.motive_history(limit=1) == [second]
    assert sera.motive_field() == second
    assert hasattr(sera, "motive_signals")
    assert not hasattr(sera, "choose_intent")
    assert not hasattr(sera, "resolve_intent")
