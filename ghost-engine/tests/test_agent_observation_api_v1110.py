import copy
import json

import pytest

from ghost import GhostAPI
from ghost.perception import PERCEPTION_SNAPSHOT_SCHEMA_VERSION


def assert_json_safe(value):
    json.dumps(value, allow_nan=False)


def test_bound_agent_observe_records_host_supplied_world_observation():
    api = GhostAPI()
    sera = api.register_agent("sera", role="guard")
    packet = sera.observe(
        "entity_approached",
        subject="player",
        features={"distance": 2.1, "visible": True, "weapon_visible": False},
    )
    assert packet == {
        "observer": "sera",
        "sequence": 1,
        "kind": "direct",
        "event": "entity_approached",
        "subject": "player",
        "source": None,
        "features": {"distance": 2.1, "visible": True, "weapon_visible": False},
    }
    assert sera.latest_observation() == packet
    assert sera.observation_history() == [packet]


def test_agent_state_exposes_perception_as_one_owned_layer():
    api = GhostAPI()
    sera = api.register_agent("sera", role="guard")
    assert sera.state()["layers"]["perception"] is None
    sera.observe("entity_approached", subject="player")
    layer = sera.state()["layers"]["perception"]
    assert layer["observer"] == "sera"
    assert layer["next_sequence"] == 2
    assert layer["history"][0]["event"] == "entity_approached"


def test_observation_surface_requires_registered_bound_handle():
    api = GhostAPI()
    before = api.snapshot()
    assert api.agent("sera") is None
    for name in (
        "submit_observation", "agent_observation_history",
        "latest_agent_observation", "agent_perception_state",
    ):
        assert not hasattr(api, name)
    assert api.snapshot() == before


def test_registered_agent_with_no_observation_does_not_create_perception_snapshot():
    api = GhostAPI()
    sera = api.register_agent("sera")
    snapshot = api.snapshot()
    assert sera.observation_history() == []
    assert sera.latest_observation() is None
    assert sera.state()["layers"]["perception"] is None
    assert "perception" not in snapshot


def test_report_perception_stays_report_and_does_not_silently_mutate_epistemics():
    api = GhostAPI()
    sera = api.register_agent("sera")
    epistemic_before = copy.deepcopy(api.epistemic.snapshot())
    packet = sera.observe(
        "captain_took_bribe",
        kind="report",
        subject="captain",
        source="player",
        features={"claimed_location": "market"},
    )
    assert packet["kind"] == "report"
    assert packet["source"] == "player"
    assert api.epistemic.snapshot() == epistemic_before
    assert api.get_belief("sera", "captain") is None


def test_phase_two_does_not_replace_existing_epistemic_observe_api():
    api = GhostAPI()
    record = api.observe(
        observer="sera",
        kind="visual",
        visible_features=["royal_guard_cloaks"],
        reliability=0.8,
        subject="market_event",
        provenance={"location": "market"},
    )
    assert record["kind"] == "observation"
    assert record["observer"] == "sera"
    assert record["visible_features"] == ["royal_guard_cloaks"]


def test_perception_and_epistemic_observation_remain_distinct_namespaces():
    api = GhostAPI()
    sera = api.register_agent("sera")
    world_packet = sera.observe(
        "entity_approached", subject="player", features={"distance": 2.1},
    )
    epistemic_packet = api.observe(
        observer="sera", kind="visual", visible_features=["player_nearby"],
        reliability=0.9, subject="player",
    )
    snapshot = api.snapshot()
    assert world_packet["event"] == "entity_approached"
    assert epistemic_packet["kind"] == "observation"
    assert snapshot["perception"]["observers"]["sera"]["history"][0] == world_packet
    assert snapshot["epistemic"] != snapshot["perception"]


def test_perception_snapshot_roundtrip_and_sequence_continuation_are_exact():
    api = GhostAPI()
    sera = api.register_agent("sera")
    sera.observe("entity_approached", subject="player")
    sera.observe(
        "captain_took_bribe", kind="report", subject="captain", source="player",
    )
    snapshot = api.snapshot()
    assert snapshot["perception"]["schema_version"] == PERCEPTION_SNAPSHOT_SCHEMA_VERSION
    assert_json_safe(snapshot)
    restored = GhostAPI.from_snapshot(snapshot)
    assert restored.snapshot() == snapshot
    third = restored.agent("sera").observe("rain_started", kind="environment", source="world")
    assert third["sequence"] == 3
    assert [p["sequence"] for p in restored.agent("sera").observation_history()] == [1, 2, 3]


def test_legacy_phase_one_snapshot_without_perception_restores_unchanged():
    api = GhostAPI()
    api.register_agent("sera", role="guard")
    phase_one_style = api.snapshot()
    assert "perception" not in phase_one_style
    restored = GhostAPI.from_snapshot(copy.deepcopy(phase_one_style))
    assert restored.snapshot() == phase_one_style
    assert restored.agent("sera").state()["layers"]["perception"] is None


def test_snapshot_rejects_non_dict_and_invalid_perception_schema():
    api = GhostAPI()
    snapshot = api.snapshot()
    bad_type = copy.deepcopy(snapshot)
    bad_type["perception"] = []
    with pytest.raises(ValueError, match="snapshot perception must be a dict"):
        GhostAPI.from_snapshot(bad_type)

    bad_schema = copy.deepcopy(snapshot)
    bad_schema["perception"] = {
        "schema_version": "9.9", "history_limit": 128, "observers": {},
    }
    with pytest.raises(ValueError, match="unsupported perception snapshot schema"):
        GhostAPI.from_snapshot(bad_schema)
    assert "perception" not in snapshot


def test_snapshot_rejects_perception_owner_that_is_not_registered_agent():
    api = GhostAPI()
    api.register_agent("sera")
    api.agent("sera").observe("signal")
    snapshot = api.snapshot()
    snapshot["agents"]["agents"].pop("sera")
    with pytest.raises(ValueError, match="must reference a registered agent"):
        GhostAPI.from_snapshot(snapshot)
    assert "sera" in snapshot["perception"]["observers"]


def test_in_place_restore_rebinds_perception_runtime():
    first = GhostAPI()
    first.register_agent("sera").observe("signal")
    snapshot = first.snapshot()
    second = GhostAPI()
    second.register_agent("rowan").observe("other")
    result = second.restore_snapshot(snapshot)
    assert result == snapshot
    assert second.agent("sera").latest_observation()["event"] == "signal"
    assert second.agent("rowan") is None


def test_observation_packets_are_copy_isolated_at_every_public_read():
    api = GhostAPI()
    sera = api.register_agent("sera")
    packet = sera.observe("signal", features={"nested": [1]})
    packet["features"]["nested"].append(2)
    history = sera.observation_history()
    history[0]["features"]["nested"].append(3)
    latest = sera.latest_observation()
    latest["features"]["nested"].append(4)
    state = sera.state()["layers"]["perception"]
    state["history"][0]["features"]["nested"].append(5)
    assert sera.latest_observation()["features"]["nested"] == [1]


def test_no_observation_means_no_new_perception_epistemic_emotion_or_interpretation_state():
    api = GhostAPI()
    api.register_agent("sera")
    snapshot = api.snapshot()
    assert "perception" not in snapshot
    assert api.emotional_state("sera") is None
    assert api.interpretation_state("sera") is None
    assert api.attention_state("sera") is None
    assert api.get_belief("sera", "anything") is None


def test_phase_two_is_still_not_motive_intent_or_execution_runtime():
    api = GhostAPI()
    sera = api.register_agent("sera")
    sera.observe("entity_approached", subject="player")
    assert not hasattr(sera, "step")
    assert not hasattr(sera, "consider")
    assert not hasattr(sera, "resolve_intent")
