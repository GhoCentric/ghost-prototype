from __future__ import annotations

from copy import deepcopy
import json

import pytest

from ghost.interpretation import (
    DEFAULT_INTERPRETATION_THRESHOLD,
    INTERPRETATION_SNAPSHOT_SCHEMA_VERSION,
    InterpretationRuntime,
)


def sera_runtime():
    runtime = InterpretationRuntime()
    runtime.register_agent(
        "sera",
        thresholds={
            "betrayal": {"enter": 0.60, "exit": 0.40},
            "cooperation": 0.70,
        },
        rules={
            "action:report_evidence_to_guards": {
                "betrayal": 0.15,
                "cooperation": 0.05,
            },
            "confidential_evidence_shared": {"betrayal": 0.70},
            "authority_involved": {"betrayal": 0.10},
        },
    )
    return runtime


def test_default_threshold_contract():
    assert DEFAULT_INTERPRETATION_THRESHOLD == 0.65
    runtime = InterpretationRuntime()
    state = runtime.register_agent(
        "npc",
        rules={"feature": {"betrayal": 0.2}},
    )
    assert state["thresholds"]["betrayal"] == {
        "enter": 0.65,
        "exit": 0.5,
    }


def test_same_objective_action_can_mean_different_things_to_different_npcs():
    runtime = InterpretationRuntime()
    runtime.register_agent(
        "sera",
        thresholds={"betrayal": 0.60, "cooperation": 0.70},
        rules={
            "action:report_evidence_to_guards": {"betrayal": 0.15},
            "confidential_evidence_shared": {"betrayal": 0.70},
        },
    )
    runtime.register_agent(
        "rowan",
        thresholds={"betrayal": 0.75, "cooperation": 0.55},
        rules={
            "action:report_evidence_to_guards": {"cooperation": 0.65},
            "confidential_evidence_shared": {"betrayal": 0.05},
        },
    )
    features = {"confidential_evidence_shared": 1.0, "authority_involved": 1.0}
    sera = runtime.evaluate_action("sera", "report_evidence_to_guards", features)
    rowan = runtime.evaluate_action("rowan", "report_evidence_to_guards", features)
    assert sera["active_interpretations"] == ["betrayal"]
    assert rowan["active_interpretations"] == ["cooperation"]
    assert sera["objective_action"] == rowan["objective_action"]


def test_threshold_is_individual_even_when_rules_are_identical():
    runtime = InterpretationRuntime()
    rule = {"broken_promise": {"betrayal": 0.55}}
    runtime.register_agent("low", thresholds={"betrayal": 0.50}, rules=rule)
    runtime.register_agent("high", thresholds={"betrayal": 0.80}, rules=rule)
    low = runtime.evaluate_action("low", "leave", {"broken_promise": 1.0})
    high = runtime.evaluate_action("high", "leave", {"broken_promise": 1.0})
    assert low["transitions"]["betrayal"]["transition"] == "entered"
    assert high["transitions"]["betrayal"]["transition"] == "inactive"


def test_small_actions_accumulate_until_threshold_is_crossed():
    runtime = InterpretationRuntime()
    runtime.register_agent(
        "npc",
        thresholds={"betrayal": 0.60},
        rules={"small_breach": {"betrayal": 0.25}},
    )
    first = runtime.evaluate_action("npc", "act", {"small_breach": 1.0})
    second = runtime.evaluate_action("npc", "act", {"small_breach": 1.0})
    third = runtime.evaluate_action("npc", "act", {"small_breach": 1.0})
    fourth = runtime.evaluate_action("npc", "act", {"small_breach": 1.0})
    assert first["state"]["active_interpretations"] == []
    assert second["state"]["active_interpretations"] == []
    assert third["state"]["active_interpretations"] == []
    assert fourth["state"]["active_interpretations"] == ["betrayal"]


def test_negative_pressure_can_release_active_state_with_hysteresis():
    runtime = InterpretationRuntime()
    runtime.register_agent(
        "npc",
        initial={"betrayal": 0.75},
        thresholds={"betrayal": {"enter": 0.60, "exit": 0.40}},
        rules={"repair": {"betrayal": -0.60}},
    )
    before = runtime.get_state("npc")
    assert before["active_interpretations"] == ["betrayal"]
    packet = runtime.evaluate_action("npc", "repair", {"repair": 1.0})
    assert packet["transitions"]["betrayal"]["transition"] == "released"
    assert packet["state"]["levels"]["betrayal"] == pytest.approx(0.30)


def test_rule_contributions_are_explicit_and_provenance_is_preserved():
    runtime = sera_runtime()
    packet = runtime.evaluate_action(
        "sera",
        "report_evidence_to_guards",
        {"confidential_evidence_shared": 0.8},
        source="player",
        provenance={"evidence_id": "ledger-1"},
    )
    assert packet["objective_action"]["source"] == "player"
    assert packet["objective_action"]["provenance"] == {"evidence_id": "ledger-1"}
    assert any(
        item["feature"] == "confidential_evidence_shared"
        and item["interpretation"] == "betrayal"
        for item in packet["contributions"]
    )


def test_context_modifier_changes_pressure_without_changing_objective_action():
    left = sera_runtime()
    right = sera_runtime()
    features = {"confidential_evidence_shared": 1.0}
    a = left.evaluate_action(
        "sera",
        "report_evidence_to_guards",
        features,
        context_modifiers={"betrayal": 0.5},
    )
    b = right.evaluate_action(
        "sera",
        "report_evidence_to_guards",
        features,
        context_modifiers={"betrayal": 1.5},
    )
    assert a["objective_action"] == b["objective_action"]
    assert a["state"]["levels"]["betrayal"] < b["state"]["levels"]["betrayal"]


def test_sensitivity_is_per_agent():
    runtime = InterpretationRuntime()
    rule = {"disclosure": {"betrayal": 0.4}}
    runtime.register_agent("a", sensitivities={"betrayal": 0.5}, rules=rule)
    runtime.register_agent("b", sensitivities={"betrayal": 1.5}, rules=rule)
    a = runtime.evaluate_action("a", "share", {"disclosure": 1.0})
    b = runtime.evaluate_action("b", "share", {"disclosure": 1.0})
    assert a["strongest_level"] == pytest.approx(0.2)
    assert b["strongest_level"] == pytest.approx(0.6)


def test_action_type_is_always_an_objective_feature():
    runtime = InterpretationRuntime()
    runtime.register_agent(
        "npc",
        rules={"action:call_guards": {"cooperation": 0.7}},
    )
    packet = runtime.evaluate_action("npc", "call_guards")
    assert packet["objective_action"]["features"] == {"action:call_guards": 1.0}
    assert packet["active_interpretations"] == ["cooperation"]


def test_no_matching_rule_records_action_without_fabricating_meaning():
    runtime = InterpretationRuntime()
    runtime.register_agent("npc", rules={"other": {"betrayal": 0.5}})
    packet = runtime.evaluate_action("npc", "wait", {"unknown": 1.0})
    assert packet["contributions"] == []
    assert packet["transitions"] == {}
    assert packet["active_interpretations"] == []
    assert packet["strongest_interpretation"] is None


def test_custom_interpretation_dimensions_are_supported():
    runtime = InterpretationRuntime()
    runtime.register_agent(
        "npc",
        thresholds={"dishonor": 0.4},
        rules={"public_insult": {"dishonor": 0.6}},
    )
    packet = runtime.evaluate_action("npc", "speak", {"public_insult": 1.0})
    assert packet["active_interpretations"] == ["dishonor"]


def test_rule_configuration_can_extend_existing_agent_without_erasing_history():
    runtime = InterpretationRuntime(history_limit=4)
    runtime.register_agent("npc", rules={"a": {"betrayal": 0.2}})
    runtime.evaluate_action("npc", "act", {"a": 1.0})
    before = runtime.get_state("npc")["history"]
    packet = runtime.configure_rule("npc", "b", {"cooperation": 0.4})
    after = runtime.get_state("npc")
    assert packet == {"agent": "npc", "feature": "b", "pressures": {"cooperation": 0.4}}
    assert after["history"] == before
    assert after["rules"]["b"] == {"cooperation": 0.4}


def test_history_rolls_at_configured_limit():
    runtime = InterpretationRuntime(history_limit=2)
    runtime.register_agent("npc", rules={"a": {"betrayal": 0.1}})
    for _ in range(3):
        runtime.evaluate_action("npc", "act", {"a": 1.0})
    state = runtime.get_state("npc")
    assert [entry["sequence"] for entry in state["history"]] == [2, 3]


def test_same_config_and_ordered_actions_are_deterministic():
    def run_once():
        runtime = sera_runtime()
        runtime.evaluate_action("sera", "wait", {"confidential_evidence_shared": 0.2})
        runtime.evaluate_action(
            "sera",
            "report_evidence_to_guards",
            {"confidential_evidence_shared": 1.0, "authority_involved": 1.0},
        )
        return runtime.snapshot()
    assert run_once() == run_once()


def test_feature_dict_insertion_order_does_not_change_result():
    a = sera_runtime()
    b = sera_runtime()
    pa = a.evaluate_action(
        "sera",
        "report_evidence_to_guards",
        {"authority_involved": 1.0, "confidential_evidence_shared": 1.0},
    )
    pb = b.evaluate_action(
        "sera",
        "report_evidence_to_guards",
        {"confidential_evidence_shared": 1.0, "authority_involved": 1.0},
    )
    assert pa == pb


def test_snapshot_round_trip_is_exact_and_json_safe():
    runtime = sera_runtime()
    runtime.evaluate_action(
        "sera",
        "report_evidence_to_guards",
        {"confidential_evidence_shared": 1.0},
    )
    snapshot = runtime.snapshot()
    assert snapshot["schema_version"] == INTERPRETATION_SNAPSHOT_SCHEMA_VERSION
    json.dumps(snapshot, sort_keys=True, allow_nan=False)
    restored = InterpretationRuntime.from_snapshot(deepcopy(snapshot))
    assert restored.snapshot() == snapshot


def test_snapshot_restore_continuation_is_deterministic():
    runtime = sera_runtime()
    runtime.evaluate_action("sera", "wait", {"confidential_evidence_shared": 0.2})
    snapshot = runtime.snapshot()
    a = InterpretationRuntime.from_snapshot(deepcopy(snapshot))
    b = InterpretationRuntime.from_snapshot(deepcopy(snapshot))
    action = {"confidential_evidence_shared": 1.0, "authority_involved": 1.0}
    assert a.evaluate_action("sera", "report_evidence_to_guards", action) == b.evaluate_action(
        "sera", "report_evidence_to_guards", action
    )


def test_reads_are_copy_safe():
    runtime = sera_runtime()
    state = runtime.get_state("sera")
    state["levels"]["betrayal"] = 999
    state["rules"].clear()
    fresh = runtime.get_state("sera")
    assert fresh["levels"]["betrayal"] != 999
    assert fresh["rules"]


def test_invalid_action_input_is_atomic():
    runtime = sera_runtime()
    before = runtime.snapshot()
    with pytest.raises(ValueError):
        runtime.evaluate_action(
            "sera",
            "report_evidence_to_guards",
            {"confidential_evidence_shared": 2.0},
        )
    assert runtime.snapshot() == before


def test_unknown_agent_is_rejected_without_mutation():
    runtime = InterpretationRuntime()
    before = runtime.snapshot()
    with pytest.raises(ValueError):
        runtime.evaluate_action("missing", "call_guards")
    assert runtime.snapshot() == before


def test_invalid_registration_and_threshold_contracts_are_rejected():
    runtime = InterpretationRuntime()
    with pytest.raises(ValueError):
        runtime.register_agent("npc", thresholds={"betrayal": {"exit": 0.2}})
    with pytest.raises(ValueError):
        runtime.register_agent(
            "npc",
            thresholds={"betrayal": {"enter": 0.4, "exit": 0.5}},
        )
    with pytest.raises(ValueError):
        runtime.register_agent("npc", rules={"feature": {"betrayal": 2.0}})


def test_invalid_snapshot_packets_are_rejected():
    runtime = sera_runtime()
    snapshot = runtime.snapshot()
    bad_packets = [
        [],
        {**snapshot, "extra": 1},
        {**snapshot, "schema_version": "9"},
        {**snapshot, "sequence": True},
        {**snapshot, "agents": []},
    ]
    for packet in bad_packets:
        with pytest.raises(ValueError):
            InterpretationRuntime.from_snapshot(deepcopy(packet))


def test_snapshot_rejects_inconsistent_active_flag():
    runtime = InterpretationRuntime()
    runtime.register_agent(
        "npc",
        initial={"betrayal": 0.8},
        thresholds={"betrayal": {"enter": 0.6, "exit": 0.4}},
    )
    snapshot = runtime.snapshot()
    snapshot["agents"]["npc"]["active"]["betrayal"] = False
    with pytest.raises(ValueError):
        InterpretationRuntime.from_snapshot(snapshot)


def test_strongest_interpretation_tie_break_is_deterministic():
    runtime = InterpretationRuntime()
    runtime.register_agent("npc", initial={"zeta": 0.5, "alpha": 0.5})
    state = runtime.get_state("npc")
    assert state["strongest_interpretation"] == "alpha"
    assert state["strongest_level"] == 0.5


def test_reserved_action_feature_cannot_override_objective_action_and_is_atomic():
    runtime = InterpretationRuntime()
    runtime.register_agent(
        "npc",
        rules={"action:call_guards": {"cooperation": 0.7}},
    )
    before = runtime.snapshot()
    with pytest.raises(ValueError):
        runtime.evaluate_action(
            "npc",
            "call_guards",
            {"action:call_guards": 0.0},
        )
    assert runtime.snapshot() == before


def test_interpretation_agent_uses_standard_ghost_id_boundary():
    runtime = InterpretationRuntime()
    with pytest.raises(ValueError):
        runtime.register_agent("bad|id")
    assert runtime.snapshot()["agents"] == {}
