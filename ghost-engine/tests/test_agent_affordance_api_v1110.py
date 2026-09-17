import copy
import json

import pytest

from ghost import GhostAPI
from ghost.affordances import AFFORDANCE_SNAPSHOT_SCHEMA_VERSION


def assert_json_safe(value):
    json.dumps(value, allow_nan=False, sort_keys=True)


def make_agent(api: GhostAPI):
    return api.register_agent(
        "sera",
        role="guard",
        values={"protect_town": 0.9},
        goals=["maintain_post"],
        capabilities=["question", "warn", "confront", "withdraw"],
    )


def test_bound_agent_exposes_capability_and_affordance_contract():
    api = GhostAPI()
    sera = make_agent(api)
    assert sera.capabilities() == ["question", "warn", "confront", "withdraw"]
    assert sera.affordances() is None
    assert sera.affordance_history() == []

    packet = sera.set_affordances(
        [
            {
                "id": "warn_player",
                "capability": "warn",
                "features": {"target": "player", "distance": 2.0},
            },
            {
                "id": "question_player",
                "capability": "question",
                "features": {"target": "player"},
            },
        ],
        context={"scene": "gate"},
    )
    assert [item["id"] for item in packet["candidates"]] == [
        "question_player", "warn_player",
    ]
    assert sera.affordances() == packet
    assert sera.state()["layers"]["affordances"] == packet
    assert_json_safe(api.snapshot())


def test_capability_mutation_is_explicit_and_copy_safe():
    api = GhostAPI()
    sera = api.register_agent("sera", capabilities=["warn", "question"])
    first = sera.capabilities()
    first.append("corruption")
    assert sera.capabilities() == ["warn", "question"]

    added = sera.add_capability("confront")
    assert added["agent_id"] == "sera"
    assert added["capability_id"] == "confront"
    assert added["before"] == ["warn", "question"]
    assert added["after"] == ["confront", "question", "warn"]
    assert sera.capabilities() == ["confront", "question", "warn"]

    with pytest.raises(ValueError, match="already registered"):
        sera.add_capability(" confront ")

    assert sera.remove_capability("warn") is True
    assert sera.remove_capability("warn") is False
    assert sera.capabilities() == ["confront", "question"]


def test_current_affordance_must_reference_registered_agent_capability():
    api = GhostAPI()
    sera = api.register_agent("sera", capabilities=["question"])
    before = api.snapshot()
    with pytest.raises(ValueError, match="not registered for agent"):
        sera.set_affordances(
            [{"id": "attack_player", "capability": "attack"}],
        )
    assert api.snapshot() == before


def test_current_affordance_blocks_capability_removal_until_host_replaces_set():
    api = GhostAPI()
    sera = api.register_agent("sera", capabilities=["question", "warn"])
    sera.set_affordances(["question", "warn"], context={"scene": "gate"})
    before = api.snapshot()
    with pytest.raises(ValueError, match="current affordance references"):
        sera.remove_capability("warn")
    assert api.snapshot() == before

    cleared = sera.clear_affordances(context={"reason": "scene_closed"})
    assert cleared["candidates"] == []
    assert sera.remove_capability("warn") is True
    assert sera.capabilities() == ["question"]


def test_historical_removed_capability_remains_auditable_and_snapshot_safe():
    api = GhostAPI()
    sera = api.register_agent("sera", capabilities=["question", "warn"])
    first = sera.set_affordances(["warn"])
    sera.clear_affordances()
    assert sera.remove_capability("warn") is True
    assert sera.affordance_history()[0] == first

    snapshot = api.snapshot()
    restored = GhostAPI.from_snapshot(copy.deepcopy(snapshot))
    assert restored.snapshot() == snapshot
    assert restored.agent("sera").capabilities() == ["question"]
    assert restored.agent("sera").affordance_history()[0]["candidates"][0]["capability"] == "warn"
    assert restored.agent("sera").affordances()["candidates"] == []


def test_affordance_submission_does_not_mutate_motive_state_or_observations():
    api = GhostAPI()
    sera = make_agent(api)
    sera.configure_motive(
        "protect",
        baseline=0.1,
        weights={"value:protect_town": 0.8},
    )
    motive = sera.evaluate_motives()
    before_observations = sera.observation_history()
    before_motive = sera.motive_field()

    sera.set_affordances(["question", "confront"])

    assert sera.observation_history() == before_observations
    assert sera.motive_field() == before_motive == motive


def test_affordance_order_is_host_input_order_independent_through_public_api():
    left = GhostAPI()
    right = GhostAPI()
    a = left.register_agent("sera", capabilities=["question", "warn"])
    b = right.register_agent("sera", capabilities=["question", "warn"])
    first = a.set_affordances(
        [
            {"id": "warn_player", "capability": "warn"},
            {"id": "question_player", "capability": "question"},
        ],
        context={"scene": "gate"},
    )
    second = b.set_affordances(
        [
            {"id": "question_player", "capability": "question"},
            {"id": "warn_player", "capability": "warn"},
        ],
        context={"scene": "gate"},
    )
    assert first == second
    assert left.snapshot() == right.snapshot()


def test_snapshot_roundtrip_restores_affordance_state_and_continuation():
    api = GhostAPI()
    sera = make_agent(api)
    sera.set_affordances(
        [{"id": "question_player", "capability": "question"}],
        context={"scene": "gate", "phase": 1},
    )
    snapshot = api.snapshot()
    assert snapshot["affordances"]["schema_version"] == AFFORDANCE_SNAPSHOT_SCHEMA_VERSION
    restored = GhostAPI.from_snapshot(copy.deepcopy(snapshot))
    assert restored.snapshot() == snapshot

    original_next = sera.set_affordances(
        [{"id": "confront_player", "capability": "confront"}],
        context={"scene": "gate", "phase": 2},
    )
    restored_next = restored.agent("sera").set_affordances(
        [{"id": "confront_player", "capability": "confront"}],
        context={"scene": "gate", "phase": 2},
    )
    assert original_next == restored_next
    assert api.snapshot() == restored.snapshot()


def test_legacy_snapshot_without_affordances_restores_empty_runtime():
    api = GhostAPI()
    sera = make_agent(api)
    sera.set_affordances(["question"])
    legacy = api.snapshot()
    legacy.pop("affordances")
    restored = GhostAPI.from_snapshot(copy.deepcopy(legacy))
    assert restored.agent("sera").affordances() is None
    assert restored.agent("sera").affordance_history() == []
    assert "affordances" not in restored.snapshot()


def test_snapshot_rejects_non_dict_affordance_payload():
    api = GhostAPI()
    snap = api.snapshot()
    snap["affordances"] = []
    with pytest.raises(ValueError, match="snapshot affordances must be a dict"):
        GhostAPI.from_snapshot(snap)


def test_snapshot_rejects_affordance_agent_without_registered_identity():
    api = GhostAPI()
    sera = make_agent(api)
    sera.set_affordances(["question"])
    snap = api.snapshot()
    snap["affordances"]["history"]["unknown"] = snap["affordances"]["history"].pop("sera")
    snap["affordances"]["history"]["unknown"][0]["agent"] = "unknown"
    with pytest.raises(ValueError, match="affordance agent must reference a registered agent"):
        GhostAPI.from_snapshot(snap)


def test_snapshot_rejects_current_affordance_using_removed_capability():
    api = GhostAPI()
    sera = make_agent(api)
    sera.set_affordances(["warn"])
    snap = api.snapshot()
    snap["agents"]["agents"]["sera"]["capabilities"].remove("warn")
    with pytest.raises(ValueError, match="current affordance capability must be registered"):
        GhostAPI.from_snapshot(snap)


def test_in_place_restore_rebinds_affordance_runtime():
    first = GhostAPI()
    make_agent(first).set_affordances(["question"])
    snapshot = first.snapshot()

    second = GhostAPI()
    second.register_agent("rowan", capabilities=["wait"]).set_affordances(["wait"])
    result = second.restore_snapshot(copy.deepcopy(snapshot))
    assert result == snapshot
    assert second.agent("sera").affordances()["candidates"][0]["capability"] == "question"
    assert second.agent("rowan") is None


def test_phase_five_exposes_possibilities_but_does_not_choose_or_execute_one():
    api = GhostAPI()
    sera = make_agent(api)
    packet = sera.set_affordances(["question", "confront"])
    assert len(packet["candidates"]) == 2
    assert not hasattr(sera, "consider")
    assert not hasattr(sera, "choose_intent")
    assert not hasattr(sera, "step")
    assert not hasattr(sera, "resolve_intent")
