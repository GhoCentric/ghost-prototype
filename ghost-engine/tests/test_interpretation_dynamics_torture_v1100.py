from __future__ import annotations

from copy import deepcopy
import json
import math
import sys

import pytest

from ghost.interpretation import (
    DEFAULT_INTERPRETATION_HISTORY_LIMIT,
    InterpretationRuntime,
)


def configured_runtime(*, history_limit=64):
    runtime = InterpretationRuntime(history_limit=history_limit)
    runtime.register_agent(
        "npc",
        initial={"betrayal": 0.35, "cooperation": 0.20},
        baseline={"betrayal": 0.10, "cooperation": 0.25},
        thresholds={
            "betrayal": {"enter": 0.70, "exit": 0.45},
            "cooperation": {"enter": 0.65, "exit": 0.40},
        },
        sensitivities={"betrayal": 1.0, "cooperation": 1.0},
        rules={
            "breach": {"betrayal": 0.23, "cooperation": -0.10},
            "repair": {"betrayal": -0.31, "cooperation": 0.19},
            "mixed": {"betrayal": 0.20, "cooperation": 0.20},
        },
    )
    return runtime


def assert_snapshot_json_safe(runtime):
    packet = runtime.snapshot()
    json.dumps(packet, allow_nan=False, sort_keys=True)
    return packet


def test_default_history_limit_contract_and_has_state_boundary():
    runtime = InterpretationRuntime()
    assert runtime.history_limit == DEFAULT_INTERPRETATION_HISTORY_LIMIT
    assert runtime.has_state() is False
    runtime.register_agent("npc")
    assert runtime.has_state() is True


@pytest.mark.parametrize("bad", [True, False, 0, -1, 1.5, "64", None])
def test_history_limit_rejects_non_positive_or_non_integer_values(bad):
    with pytest.raises(ValueError):
        InterpretationRuntime(history_limit=bad)


@pytest.mark.parametrize(
    ("kwargs", "fragment"),
    [
        ({"initial": []}, "initial"),
        ({"baseline": []}, "baseline"),
        ({"sensitivities": []}, "sensitivities"),
        ({"thresholds": []}, "thresholds"),
        ({"rules": []}, "rules"),
        ({"initial": {"x": True}}, "finite number"),
        ({"initial": {"x": math.inf}}, "finite number"),
        ({"initial": {"x": -0.1}}, "[0, 1]"),
        ({"initial": {"x": 1.1}}, "[0, 1]"),
        ({"sensitivities": {"x": -0.1}}, "non-negative"),
        ({"rules": {"f": 1}}, "must be a dict"),
        ({"rules": {"f": {"x": -1.1}}}, "[-1, 1]"),
        ({"thresholds": {"x": {"enter": 0.5, "bogus": 0.2}}}, "unsupported keys"),
        ({"thresholds": {"x": {"exit": 0.2}}}, "enter is required"),
    ],
)
def test_registration_boundary_rejects_malformed_numeric_maps(kwargs, fragment):
    runtime = InterpretationRuntime()
    before = runtime.snapshot()
    with pytest.raises(ValueError, match=fragment.replace("[", "\\[").replace("]", "\\]")):
        runtime.register_agent("npc", **kwargs)
    assert runtime.snapshot() == before


@pytest.mark.parametrize(
    "kwargs",
    [
        {"initial": {"x": 0.1, " x ": 0.2}},
        {"baseline": {"x": 0.1, " x ": 0.2}},
        {"sensitivities": {"x": 1.0, " x ": 2.0}},
        {"thresholds": {"x": 0.4, " x ": 0.5}},
        {"rules": {"f": {"x": 0.2}, " f ": {"x": 0.3}}},
        {"rules": {"f": {"x": 0.2, " x ": 0.3}}},
    ],
)
def test_normalization_collisions_are_rejected_instead_of_silently_overwriting(kwargs):
    runtime = InterpretationRuntime()
    before = runtime.snapshot()
    with pytest.raises(ValueError, match="duplicate normalized"):
        runtime.register_agent("npc", **kwargs)
    assert runtime.snapshot() == before


def test_empty_and_non_string_tokens_are_rejected():
    runtime = InterpretationRuntime()
    with pytest.raises(ValueError):
        runtime.register_agent("npc", rules={"": {"x": 0.1}})
    with pytest.raises(ValueError):
        runtime.register_agent("npc", rules={1: {"x": 0.1}})


def test_baseline_seeds_new_dimension_but_later_baseline_reconfiguration_does_not_erase_level():
    runtime = InterpretationRuntime()
    state = runtime.register_agent("npc", baseline={"betrayal": 0.3})
    assert state["levels"]["betrayal"] == 0.3
    runtime.register_agent("npc", rules={"rise": {"betrayal": 0.5}})
    runtime.evaluate_action("npc", "act", {"rise": 1.0})
    before = runtime.get_state("npc")["levels"]["betrayal"]
    after = runtime.register_agent("npc", baseline={"betrayal": 0.9})
    assert after["baseline"]["betrayal"] == 0.9
    assert after["levels"]["betrayal"] == before


def test_positive_pressure_is_monotonic_bounded_and_asymptotically_saturates():
    runtime = InterpretationRuntime()
    runtime.register_agent("npc", rules={"rise": {"betrayal": 0.17}})
    levels = []
    for _ in range(250):
        packet = runtime.evaluate_action("npc", "act", {"rise": 1.0})
        level = packet["state"]["levels"]["betrayal"]
        assert math.isfinite(level)
        assert 0.0 <= level <= 1.0
        levels.append(level)
    assert all(b >= a for a, b in zip(levels, levels[1:]))
    assert levels[-1] > 0.999999
    assert_snapshot_json_safe(runtime)


def test_negative_pressure_is_monotonic_bounded_and_releases_active_state():
    runtime = InterpretationRuntime()
    runtime.register_agent(
        "npc",
        initial={"betrayal": 0.95},
        thresholds={"betrayal": {"enter": 0.70, "exit": 0.45}},
        rules={"repair": {"betrayal": -0.12}},
    )
    levels = []
    transitions = []
    for _ in range(150):
        packet = runtime.evaluate_action("npc", "act", {"repair": 1.0})
        levels.append(packet["state"]["levels"]["betrayal"])
        transitions.append(packet["transitions"]["betrayal"]["transition"])
    assert all(b <= a for a, b in zip(levels, levels[1:]))
    assert "released" in transitions
    assert levels[-1] < 1e-7
    assert runtime.get_state("npc")["active_interpretations"] == []


def test_hysteresis_exact_boundaries_are_stable_and_explicit():
    inactive = InterpretationRuntime()
    inactive.register_agent(
        "npc",
        initial={"x": 0.5},
        thresholds={"x": {"enter": 0.6, "exit": 0.4}},
        rules={"raise": {"x": 0.2}},
    )
    # 0.5 + (1-.5)*.2 = .6: exact enter boundary activates.
    packet = inactive.evaluate_action("npc", "act", {"raise": 1.0})
    assert packet["transitions"]["x"]["level_after"] == pytest.approx(0.6)
    assert packet["transitions"]["x"]["transition"] == "entered"

    active = InterpretationRuntime()
    active.register_agent(
        "npc",
        initial={"x": 0.5},
        thresholds={"x": {"enter": 0.6, "exit": 0.4}},
        rules={"lower": {"x": -0.2}},
    )
    # 0.5 * (1-.2) = .4: exact exit boundary releases.
    packet = active.evaluate_action("npc", "act", {"lower": 1.0})
    # Seed it active through an explicit re-register in the hysteresis band.
    active.register_agent("npc", initial={"x": 0.61})
    active.register_agent("npc", initial={"x": 0.5})
    packet = active.evaluate_action("npc", "act", {"lower": 1.0})
    assert packet["transitions"]["x"]["level_after"] == pytest.approx(0.4)
    assert packet["transitions"]["x"]["transition"] == "released"


def test_active_state_is_retained_inside_hysteresis_band():
    runtime = InterpretationRuntime()
    runtime.register_agent(
        "npc",
        initial={"x": 0.8},
        thresholds={"x": {"enter": 0.7, "exit": 0.4}},
        rules={"soften": {"x": -0.25}},
    )
    packet = runtime.evaluate_action("npc", "act", {"soften": 1.0})
    assert packet["state"]["levels"]["x"] == pytest.approx(0.6)
    assert packet["transitions"]["x"]["transition"] == "retained_active"


def test_zero_intensity_records_objective_action_without_moving_levels():
    runtime = configured_runtime()
    before = runtime.get_state("npc")
    packet = runtime.evaluate_action(
        "npc", "act", {"breach": 1.0}, intensity=0.0
    )
    assert packet["state"]["levels"] == before["levels"]
    assert packet["sequence"] == 1
    assert packet["transitions"]["betrayal"]["effective_impulse"] == 0.0


def test_zero_sensitivity_and_zero_context_modifier_suppress_only_target_dimension():
    runtime = InterpretationRuntime()
    runtime.register_agent(
        "npc",
        sensitivities={"betrayal": 0.0, "threat": 1.0},
        rules={"event": {"betrayal": 1.0, "threat": 0.5}},
    )
    packet = runtime.evaluate_action(
        "npc", "act", {"event": 1.0}, context_modifiers={"threat": 0.0}
    )
    assert packet["state"]["levels"] == {"betrayal": 0.0, "threat": 0.0}


def test_multiple_contributions_cancel_exactly_before_state_update():
    runtime = InterpretationRuntime()
    runtime.register_agent(
        "npc",
        initial={"x": 0.4},
        rules={"a": {"x": 0.5}, "b": {"x": -0.5}},
    )
    packet = runtime.evaluate_action("npc", "act", {"a": 1.0, "b": 1.0})
    transition = packet["transitions"]["x"]
    assert transition["raw_impulse"] == 0.0
    assert transition["level_after"] == 0.4


def test_positive_aggregate_above_one_clamps_effective_impulse_to_one():
    runtime = InterpretationRuntime()
    runtime.register_agent(
        "npc",
        initial={"x": 0.2},
        rules={"a": {"x": 1.0}, "b": {"x": 1.0}},
    )
    packet = runtime.evaluate_action("npc", "act", {"a": 1.0, "b": 1.0})
    transition = packet["transitions"]["x"]
    assert transition["raw_impulse"] == 2.0
    assert transition["effective_impulse"] == 1.0
    assert transition["level_after"] == 1.0


def test_negative_aggregate_below_minus_one_clamps_effective_impulse_to_minus_one():
    runtime = InterpretationRuntime()
    runtime.register_agent(
        "npc",
        initial={"x": 0.8},
        rules={"a": {"x": -1.0}, "b": {"x": -1.0}},
    )
    packet = runtime.evaluate_action("npc", "act", {"a": 1.0, "b": 1.0})
    transition = packet["transitions"]["x"]
    assert transition["raw_impulse"] == -2.0
    assert transition["effective_impulse"] == -1.0
    assert transition["level_after"] == 0.0


def test_extreme_finite_sensitivity_and_context_saturate_without_inf_or_nan():
    runtime = InterpretationRuntime()
    runtime.register_agent(
        "npc",
        sensitivities={"x": sys.float_info.max},
        rules={"event": {"x": 1.0}},
    )
    packet = runtime.evaluate_action(
        "npc",
        "act",
        {"event": 1.0},
        context_modifiers={"x": sys.float_info.max},
    )
    contribution = packet["contributions"][0]["contribution"]
    raw = packet["transitions"]["x"]["raw_impulse"]
    assert contribution == sys.float_info.max
    assert raw == sys.float_info.max
    assert math.isfinite(contribution)
    assert math.isfinite(raw)
    assert packet["state"]["levels"]["x"] == 1.0
    assert_snapshot_json_safe(runtime)


def test_extreme_negative_contributions_saturate_to_finite_negative_bound():
    runtime = InterpretationRuntime()
    runtime.register_agent(
        "npc",
        initial={"x": 1.0},
        sensitivities={"x": sys.float_info.max},
        rules={"event": {"x": -1.0}},
    )
    packet = runtime.evaluate_action(
        "npc", "act", {"event": 1.0}, context_modifiers={"x": sys.float_info.max}
    )
    assert packet["transitions"]["x"]["raw_impulse"] == -sys.float_info.max
    assert packet["transitions"]["x"]["level_after"] == 0.0
    assert_snapshot_json_safe(runtime)


def test_saturating_add_handles_multiple_huge_same_sign_contributions():
    runtime = InterpretationRuntime()
    runtime.register_agent(
        "npc",
        sensitivities={"x": sys.float_info.max},
        rules={"a": {"x": 1.0}, "b": {"x": 1.0}},
    )
    packet = runtime.evaluate_action("npc", "act", {"a": 1.0, "b": 1.0})
    assert packet["transitions"]["x"]["raw_impulse"] == sys.float_info.max


def test_event_order_is_history_sensitive_but_each_order_is_replay_deterministic():
    def run(order):
        runtime = InterpretationRuntime()
        runtime.register_agent(
            "npc",
            initial={"x": 0.5},
            rules={"up": {"x": 0.5}, "down": {"x": -0.5}},
        )
        for feature in order:
            runtime.evaluate_action("npc", "act", {feature: 1.0})
        return runtime.snapshot()

    up_down_a = run(["up", "down"])
    up_down_b = run(["up", "down"])
    down_up = run(["down", "up"])
    assert up_down_a == up_down_b
    assert up_down_a != down_up
    assert up_down_a["agents"]["npc"]["levels"]["x"] == pytest.approx(0.375)
    assert down_up["agents"]["npc"]["levels"]["x"] == pytest.approx(0.625)


def test_many_agents_remain_isolated_under_interleaved_updates():
    runtime = InterpretationRuntime(history_limit=8)
    count = 128
    for index in range(count):
        runtime.register_agent(
            f"npc-{index}",
            rules={"event": {"pressure": (index % 5 + 1) / 10}},
        )
    untouched = runtime.get_state("npc-127")
    for index in range(64):
        runtime.evaluate_action(f"npc-{index}", "act", {"event": 1.0})
    assert runtime.get_state("npc-127") == untouched
    for index in range(64):
        assert runtime.get_state(f"npc-{index}")["levels"]["pressure"] > 0.0
    assert runtime.snapshot()["sequence"] == 64


def test_long_deterministic_alternating_run_stays_finite_bounded_and_json_safe():
    runtime = configured_runtime(history_limit=16)
    for index in range(2000):
        feature = "breach" if index % 3 else "repair"
        strength = ((index * 37) % 101) / 100.0
        intensity = ((index * 19) % 101) / 100.0
        runtime.evaluate_action(
            "npc",
            "cycle",
            {feature: strength},
            intensity=intensity,
            context_modifiers={
                "betrayal": 0.5 + ((index * 7) % 11) / 10.0,
                "cooperation": 0.5 + ((index * 13) % 11) / 10.0,
            },
        )
        state = runtime.get_state("npc")
        for level in state["levels"].values():
            assert math.isfinite(level)
            assert 0.0 <= level <= 1.0
    snapshot = assert_snapshot_json_safe(runtime)
    assert snapshot["sequence"] == 2000
    assert len(snapshot["agents"]["npc"]["history"]) == 16


def test_snapshot_forks_replay_identically_after_long_prefix():
    runtime = configured_runtime(history_limit=32)
    for index in range(120):
        runtime.evaluate_action(
            "npc", "prefix", {"breach" if index % 2 else "repair": 0.4}
        )
    snapshot = runtime.snapshot()
    left = InterpretationRuntime.from_snapshot(deepcopy(snapshot))
    right = InterpretationRuntime.from_snapshot(deepcopy(snapshot))
    for index in range(250):
        feature = "breach" if index % 4 else "repair"
        kwargs = {
            "features": {feature: ((index * 17) % 100) / 100.0},
            "intensity": ((index * 29) % 100) / 100.0,
        }
        assert left.evaluate_action("npc", "suffix", **kwargs) == right.evaluate_action(
            "npc", "suffix", **kwargs
        )
    assert left.snapshot() == right.snapshot()


def test_history_limit_is_per_agent_while_sequence_is_global():
    runtime = InterpretationRuntime(history_limit=2)
    runtime.register_agent("a", rules={"f": {"x": 0.1}})
    runtime.register_agent("b", rules={"f": {"x": 0.1}})
    runtime.evaluate_action("a", "act", {"f": 1.0})  # 1
    runtime.evaluate_action("b", "act", {"f": 1.0})  # 2
    runtime.evaluate_action("a", "act", {"f": 1.0})  # 3
    runtime.evaluate_action("b", "act", {"f": 1.0})  # 4
    runtime.evaluate_action("a", "act", {"f": 1.0})  # 5
    snapshot = runtime.snapshot()
    assert [e["sequence"] for e in snapshot["agents"]["a"]["history"]] == [3, 5]
    assert [e["sequence"] for e in snapshot["agents"]["b"]["history"]] == [2, 4]
    assert snapshot["sequence"] == 5
    assert InterpretationRuntime.from_snapshot(snapshot).snapshot() == snapshot


def test_evaluate_packet_is_detached_from_internal_provenance_and_state():
    runtime = InterpretationRuntime()
    runtime.register_agent("npc", rules={"f": {"x": 0.3}})
    packet = runtime.evaluate_action(
        "npc", "act", {"f": 1.0}, provenance={"nested": {"items": [1, 2]}}
    )
    original = runtime.snapshot()
    packet["objective_action"]["provenance"]["nested"]["items"].append(999)
    packet["state"]["levels"]["x"] = 999
    packet["state_before"]["rules"].clear()
    packet["transitions"]["x"]["level_after"] = 999
    packet["contributions"].clear()
    assert runtime.snapshot() == original


def test_input_provenance_is_copied_before_storage():
    runtime = InterpretationRuntime()
    runtime.register_agent("npc", rules={"f": {"x": 0.3}})
    provenance = {"nested": {"items": [1]}}
    runtime.evaluate_action("npc", "act", {"f": 1.0}, provenance=provenance)
    provenance["nested"]["items"].append(2)
    stored = runtime.get_state("npc")["history"][0]["provenance"]
    assert stored == {"nested": {"items": [1]}}


@pytest.mark.parametrize(
    "bad_provenance",
    [
        [],
        {1: "bad-key"},
        {"bad": object()},
        {"bad": math.nan},
        {"bad": math.inf},
    ],
)
def test_provenance_must_be_strict_json_safe_and_failure_is_atomic(bad_provenance):
    runtime = configured_runtime()
    before = runtime.snapshot()
    with pytest.raises(ValueError):
        runtime.evaluate_action("npc", "act", {"breach": 1.0}, provenance=bad_provenance)
    assert runtime.snapshot() == before


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("action", ""),
        ("intensity", True),
        ("intensity", -0.01),
        ("intensity", 1.01),
        ("features", []),
        ("context_modifiers", []),
        ("context_modifiers", {"x": -1.0}),
        ("source", "bad|id"),
    ],
)
def test_evaluate_action_boundary_failures_are_atomic(field, value):
    runtime = configured_runtime()
    before = runtime.snapshot()
    kwargs = {}
    action = "act"
    if field == "action":
        action = value
    else:
        kwargs[field] = value
    with pytest.raises(ValueError):
        runtime.evaluate_action("npc", action, **kwargs)
    assert runtime.snapshot() == before


def test_unknown_context_dimensions_are_ignored_without_creating_state():
    runtime = InterpretationRuntime()
    runtime.register_agent("npc", rules={"f": {"x": 0.2}})
    packet = runtime.evaluate_action(
        "npc", "act", {"f": 1.0}, context_modifiers={"unknown": 999.0}
    )
    assert set(packet["state"]["levels"]) == {"x"}


def test_configure_rule_auto_registers_unknown_agent_and_returns_copy_safe_packet():
    runtime = InterpretationRuntime()
    packet = runtime.configure_rule("npc", " f ", {" x ": 0.3})
    assert packet == {"agent": "npc", "feature": "f", "pressures": {"x": 0.3}}
    packet["pressures"]["x"] = 999
    assert runtime.get_state("npc")["rules"]["f"]["x"] == 0.3


def test_get_state_unknown_agent_returns_none():
    runtime = InterpretationRuntime()
    assert runtime.get_state("missing") is None


def test_strongest_interpretation_becomes_none_when_all_levels_are_zero():
    runtime = InterpretationRuntime()
    runtime.register_agent("npc", initial={"a": 0.0, "b": 0.0})
    state = runtime.get_state("npc")
    assert state["strongest_interpretation"] is None
    assert state["strongest_level"] == 0.0


def make_snapshot_with_history():
    runtime = InterpretationRuntime(history_limit=4)
    runtime.register_agent(
        "a",
        thresholds={"x": {"enter": 0.6, "exit": 0.4}},
        rules={"f": {"x": 0.5}},
    )
    runtime.register_agent(
        "b",
        thresholds={"x": {"enter": 0.6, "exit": 0.4}},
        rules={"f": {"x": -0.5}},
        initial={"x": 0.8},
    )
    runtime.evaluate_action("a", "act", {"f": 1.0}, source="player")
    runtime.evaluate_action("b", "act", {"f": 1.0}, provenance={"id": "p"})
    return runtime.snapshot()


@pytest.mark.parametrize(
    "mutator",
    [
        lambda s: s.update(history_limit=True),
        lambda s: s.update(sequence=-1),
        lambda s: s["agents"].update({"bad|id": {}}),
        lambda s: s["agents"].update({" a ": deepcopy(s["agents"]["a"])}),
        lambda s: s["agents"]["a"].update(levels=[]),
        lambda s: s["agents"]["a"].update(baseline=[]),
        lambda s: s["agents"]["a"].update(thresholds=[]),
        lambda s: s["agents"]["a"].update(sensitivities=[]),
        lambda s: s["agents"]["a"].update(rules=[]),
        lambda s: s["agents"]["a"].update(active=[]),
        lambda s: s["agents"]["a"].update(history={}),
        lambda s: s["agents"]["a"].update(extra=1),
    ],
)
def test_snapshot_shape_and_agent_state_malformed_packets_are_rejected(mutator):
    snapshot = make_snapshot_with_history()
    mutator(snapshot)
    with pytest.raises(ValueError):
        InterpretationRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_rule_dimension_not_present_in_state_dimensions():
    snapshot = make_snapshot_with_history()
    snapshot["agents"]["a"]["rules"]["f"]["unknown"] = 0.1
    with pytest.raises(ValueError, match="unknown dimensions"):
        InterpretationRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_dimension_alignment_mismatch():
    snapshot = make_snapshot_with_history()
    del snapshot["agents"]["a"]["baseline"]["x"]
    with pytest.raises(ValueError, match="dimensions do not align"):
        InterpretationRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_non_bool_and_normalized_duplicate_active_dimensions():
    snapshot = make_snapshot_with_history()
    snapshot["agents"]["a"]["active"]["x"] = 1
    with pytest.raises(ValueError, match="must be bool"):
        InterpretationRuntime.from_snapshot(snapshot)

    snapshot = make_snapshot_with_history()
    snapshot["agents"]["a"]["active"][" x "] = snapshot["agents"]["a"]["active"]["x"]
    with pytest.raises(ValueError, match="duplicate normalized"):
        InterpretationRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_history_over_limit_and_non_dict_entries():
    snapshot = make_snapshot_with_history()
    entry = deepcopy(snapshot["agents"]["a"]["history"][0])
    snapshot["agents"]["a"]["history"] = [deepcopy(entry) for _ in range(5)]
    with pytest.raises(ValueError, match="exceeds history_limit"):
        InterpretationRuntime.from_snapshot(snapshot)

    snapshot = make_snapshot_with_history()
    snapshot["agents"]["a"]["history"][0] = []
    with pytest.raises(ValueError, match="must be a dict"):
        InterpretationRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_history_key_and_sequence_corruption():
    snapshot = make_snapshot_with_history()
    snapshot["agents"]["a"]["history"][0]["extra"] = 1
    with pytest.raises(ValueError, match="invalid keys"):
        InterpretationRuntime.from_snapshot(snapshot)

    for bad in (True, 0, 999):
        snapshot = make_snapshot_with_history()
        snapshot["agents"]["a"]["history"][0]["sequence"] = bad
        with pytest.raises(ValueError, match="sequence is invalid"):
            InterpretationRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_duplicate_global_sequence_across_agents():
    snapshot = make_snapshot_with_history()
    snapshot["agents"]["b"]["history"][0]["sequence"] = 1
    with pytest.raises(ValueError, match="duplicated"):
        InterpretationRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_missing_latest_global_history_sequence():
    snapshot = make_snapshot_with_history()
    snapshot["agents"]["b"]["history"] = []
    with pytest.raises(ValueError, match="latest history sequence"):
        InterpretationRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_invalid_history_action_source_and_features():
    snapshot = make_snapshot_with_history()
    snapshot["agents"]["a"]["history"][0]["action"] = ""
    with pytest.raises(ValueError):
        InterpretationRuntime.from_snapshot(snapshot)

    snapshot = make_snapshot_with_history()
    snapshot["agents"]["a"]["history"][0]["source"] = "bad|id"
    with pytest.raises(ValueError):
        InterpretationRuntime.from_snapshot(snapshot)

    snapshot = make_snapshot_with_history()
    snapshot["agents"]["a"]["history"][0]["features"] = []
    with pytest.raises(ValueError):
        InterpretationRuntime.from_snapshot(snapshot)


def test_snapshot_requires_exactly_one_matching_action_feature_at_strength_one():
    snapshot = make_snapshot_with_history()
    snapshot["agents"]["a"]["history"][0]["features"] = {"f": 1.0}
    with pytest.raises(ValueError, match="exactly one action"):
        InterpretationRuntime.from_snapshot(snapshot)

    snapshot = make_snapshot_with_history()
    entry = snapshot["agents"]["a"]["history"][0]
    entry["features"] = {"action:wrong": 1.0, "f": 1.0}
    with pytest.raises(ValueError, match="action feature mismatch"):
        InterpretationRuntime.from_snapshot(snapshot)

    snapshot = make_snapshot_with_history()
    entry = snapshot["agents"]["a"]["history"][0]
    entry["features"]["action:act"] = 0.5
    with pytest.raises(ValueError, match="must equal 1.0"):
        InterpretationRuntime.from_snapshot(snapshot)


def first_transition(snapshot):
    return snapshot["agents"]["a"]["history"][0]["transitions"]["x"]


@pytest.mark.parametrize(
    "mutator",
    [
        lambda t: t.update(extra=1),
        lambda t: t.update(level_before=True),
        lambda t: t.update(level_after=2.0),
        lambda t: t.update(raw_impulse=math.inf),
        lambda t: t.update(effective_impulse=2.0),
        lambda t: t.update(active_before=1),
        lambda t: t.update(active_after=1),
        lambda t: t.update(transition="bogus"),
        lambda t: t.update(threshold={"enter": 0.6, "exit": 0.7}),
    ],
)
def test_snapshot_rejects_malformed_transition_packets(mutator):
    snapshot = make_snapshot_with_history()
    mutator(first_transition(snapshot))
    with pytest.raises(ValueError):
        InterpretationRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_transition_unknown_dimension_and_non_dict_packet():
    snapshot = make_snapshot_with_history()
    transition = snapshot["agents"]["a"]["history"][0]["transitions"].pop("x")
    snapshot["agents"]["a"]["history"][0]["transitions"]["unknown"] = transition
    with pytest.raises(ValueError, match="unknown interpretation dimension"):
        InterpretationRuntime.from_snapshot(snapshot)

    snapshot = make_snapshot_with_history()
    snapshot["agents"]["a"]["history"][0]["transitions"]["x"] = []
    with pytest.raises(ValueError, match="must be a dict"):
        InterpretationRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_transition_effective_impulse_inconsistency():
    snapshot = make_snapshot_with_history()
    first_transition(snapshot)["effective_impulse"] = 0.25
    with pytest.raises(ValueError, match="effective impulse is inconsistent"):
        InterpretationRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_transition_level_math_inconsistency():
    snapshot = make_snapshot_with_history()
    first_transition(snapshot)["level_after"] = 0.123
    with pytest.raises(ValueError, match="level transition is inconsistent"):
        InterpretationRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_transition_active_math_inconsistency():
    snapshot = make_snapshot_with_history()
    transition = first_transition(snapshot)
    transition["active_after"] = not transition["active_after"]
    with pytest.raises(ValueError, match="active transition is inconsistent"):
        InterpretationRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_transition_label_inconsistency():
    snapshot = make_snapshot_with_history()
    transition = first_transition(snapshot)
    transition["transition"] = "retained_active"
    with pytest.raises(ValueError, match="transition label is inconsistent"):
        InterpretationRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_non_dict_transitions_and_invalid_provenance():
    snapshot = make_snapshot_with_history()
    snapshot["agents"]["a"]["history"][0]["transitions"] = []
    with pytest.raises(ValueError, match="transitions must be a dict"):
        InterpretationRuntime.from_snapshot(snapshot)

    snapshot = make_snapshot_with_history()
    snapshot["agents"]["a"]["history"][0]["provenance"] = []
    with pytest.raises(ValueError, match="provenance must be a dict"):
        InterpretationRuntime.from_snapshot(snapshot)


def test_snapshot_is_detached_from_runtime_after_restore():
    snapshot = make_snapshot_with_history()
    restored = InterpretationRuntime.from_snapshot(deepcopy(snapshot))
    snapshot["agents"]["a"]["levels"]["x"] = 999
    assert restored.get_state("a")["levels"]["x"] != 999


def test_zero_sequence_with_empty_histories_is_valid():
    runtime = InterpretationRuntime()
    runtime.register_agent("npc", rules={"f": {"x": 0.1}})
    snapshot = runtime.snapshot()
    assert snapshot["sequence"] == 0
    assert InterpretationRuntime.from_snapshot(snapshot).snapshot() == snapshot


def test_zero_weight_rule_exercises_zero_product_without_state_motion():
    runtime = InterpretationRuntime()
    runtime.register_agent("npc", initial={"x": 0.4}, rules={"f": {"x": 0.0}})
    packet = runtime.evaluate_action("npc", "act", {"f": 1.0})
    assert packet["transitions"]["x"]["raw_impulse"] == 0.0
    assert packet["state"]["levels"]["x"] == 0.4


def test_negative_saturating_add_handles_multiple_huge_contributions():
    runtime = InterpretationRuntime()
    runtime.register_agent(
        "npc",
        initial={"x": 1.0},
        sensitivities={"x": sys.float_info.max},
        rules={"a": {"x": -1.0}, "b": {"x": -1.0}},
    )
    packet = runtime.evaluate_action("npc", "act", {"a": 1.0, "b": 1.0})
    assert packet["transitions"]["x"]["raw_impulse"] == -sys.float_info.max
    assert packet["state"]["levels"]["x"] == 0.0


def test_snapshot_rejects_non_dict_agent_state_after_valid_agent_id():
    snapshot = make_snapshot_with_history()
    snapshot["agents"]["a"] = []
    with pytest.raises(ValueError, match="agent a must be a dict"):
        InterpretationRuntime.from_snapshot(snapshot)


def test_positive_sequence_requires_at_least_one_retained_history_entry():
    snapshot = make_snapshot_with_history()
    snapshot["agents"]["a"]["history"] = []
    snapshot["agents"]["b"]["history"] = []
    with pytest.raises(ValueError, match="latest history sequence"):
        InterpretationRuntime.from_snapshot(snapshot)
