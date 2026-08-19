from __future__ import annotations

from copy import deepcopy
import json
import math

import pytest

from ghost.attention import AttentionRuntime


def focused(**overrides):
    values = {
        "task_focus": 1.0,
        "repetition": 1.0,
        "stability": 1.0,
        "novelty": 0.0,
        "threat": 0.0,
        "contradiction": 0.0,
        "interpretation_impulse": 0.0,
    }
    values.update(overrides)
    return values


def make_runtime(*, history_limit=64):
    runtime = AttentionRuntime(history_limit=history_limit)
    runtime.register_agent("npc")
    return runtime


def make_snapshot(*, two_agents=False, history_limit=64):
    runtime = AttentionRuntime(history_limit=history_limit)
    for i in range(10):
        runtime.step(
            "a",
            signals=focused(novelty=0.1 if i % 3 == 0 else 0.0),
            salience={"anger": 0.8, "betrayal": 0.6},
            source="player",
            provenance={"i": i},
        )
        if two_agents and i < 6:
            runtime.step(
                "b",
                signals=focused(threat=0.2 if i % 2 else 0.0),
                salience={"fear": 0.5},
                source="world",
                provenance={"i": i},
            )
    return runtime.snapshot()


def first_record(snapshot, agent="a"):
    return snapshot["agents"][agent]["history"][0]


def assert_json_safe(packet):
    encoded = json.dumps(packet, allow_nan=False, sort_keys=True)
    assert encoded.startswith("{")


def test_sustained_flow_pressure_is_monotonic_bounded_and_finite():
    runtime = make_runtime()
    pressures = []
    for _ in range(500):
        packet = runtime.step("npc", signals=focused(), salience={"anger": 1.0})
        pressures.append(packet["flow_pressure_after"])
        assert math.isfinite(packet["flow_pressure_after"])
        assert 0.0 <= packet["flow_pressure_after"] <= 1.0
        assert 0.0 <= packet["attention_gain"] <= 1.0
    assert all(b >= a for a, b in zip(pressures, pressures[1:]))
    assert pressures[-1] > 0.999999


def test_repeated_maximum_interrupts_cannot_underflow_pressure():
    runtime = make_runtime()
    for _ in range(20):
        runtime.step("npc", signals=focused())
    values = []
    for _ in range(500):
        packet = runtime.step(
            "npc",
            signals={"threat": 1.0, "novelty": 1.0, "contradiction": 1.0, "interpretation_impulse": 1.0},
            salience={"fear": 1.0},
        )
        values.append(packet["flow_pressure_after"])
        assert packet["attention_gain"] == 1.0
    assert min(values) >= 0.0
    assert values[-1] == pytest.approx(0.0, abs=1e-15)


def test_alternating_focus_and_interrupt_is_deterministic_and_bounded():
    sequence = [focused(), {"threat": 1.0}, focused(novelty=0.2), {"contradiction": 0.9}] * 300
    left = make_runtime()
    right = make_runtime()
    left_packets = [left.step("npc", signals=s) for s in sequence]
    right_packets = [right.step("npc", signals=s) for s in sequence]
    assert left_packets == right_packets
    assert left.snapshot() == right.snapshot()
    assert all(0.0 <= p["flow_pressure_after"] <= 1.0 for p in left_packets)


def test_ordered_signal_history_matters_even_when_multiset_matches():
    a = make_runtime()
    b = make_runtime()
    high = focused()
    interrupt = {"threat": 1.0}
    for signals in [high] * 8 + [interrupt] * 3:
        a.step("npc", signals=signals)
    for signals in [interrupt] * 3 + [high] * 8:
        b.step("npc", signals=signals)
    assert a.get_state("npc")["flow_pressure"] != b.get_state("npc")["flow_pressure"]


def test_hysteresis_prevents_threshold_chatter_under_small_perturbations():
    runtime = AttentionRuntime()
    runtime.register_agent("npc", initial_flow_pressure=0.73, flow_active=True)
    transitions = []
    for novelty in [0.05, 0.08, 0.04, 0.09, 0.03] * 10:
        packet = runtime.step("npc", signals=focused(novelty=novelty))
        transitions.append(packet["transition"])
    assert "released" not in transitions
    assert runtime.get_state("npc")["flow_active"] is True


def test_non_breakthrough_release_eventually_exits_flow():
    runtime = make_runtime()
    for _ in range(20):
        runtime.step("npc", signals=focused())
    assert runtime.get_state("npc")["flow_active"] is True
    released = False
    low = focused(task_focus=0.0, repetition=0.0, stability=0.0, novelty=0.6, threat=0.6)
    for _ in range(40):
        packet = runtime.step("npc", signals=low)
        released |= packet["transition"] == "released"
    assert released is True
    assert runtime.get_state("npc")["flow_active"] is False


@pytest.mark.parametrize("channel", ["novelty", "threat", "contradiction", "interpretation_impulse"])
def test_each_interrupt_channel_can_break_through_independently(channel):
    runtime = make_runtime()
    for _ in range(20):
        runtime.step("npc", signals=focused())
    packet = runtime.step("npc", signals={channel: 1.0}, salience={"anger": 0.9})
    assert packet["breakthrough"] is True
    assert packet["resurfaced"] is True
    assert packet["attention_gain"] == 1.0
    assert packet["attended_salience"] == packet["underlying_salience"]


@pytest.mark.parametrize("strength", [0.0, 0.1, 0.3, 0.5, 0.719999])
def test_subthreshold_interrupts_do_not_claim_breakthrough(strength):
    runtime = make_runtime()
    packet = runtime.step("npc", signals={"threat": strength})
    assert packet["breakthrough"] is False


def test_exact_interrupt_threshold_is_breakthrough():
    runtime = make_runtime()
    packet = runtime.step("npc", signals={"threat": 0.72})
    assert packet["breakthrough"] is True


def test_underlying_salience_never_changes_from_attention_compression():
    runtime = make_runtime()
    original = {"anger": 0.87, "betrayal": 0.74, "fear": 0.33}
    for _ in range(100):
        packet = runtime.step("npc", signals=focused(), salience=original)
        assert packet["underlying_salience"] == original
    assert original == {"anger": 0.87, "betrayal": 0.74, "fear": 0.33}


def test_zero_salience_remains_zero_through_all_attention_states():
    runtime = make_runtime()
    for signals in [focused()] * 12 + [{"threat": 1.0}] + [focused()] * 12:
        packet = runtime.step("npc", signals=signals, salience={"anger": 0.0})
        assert packet["underlying_salience"]["anger"] == 0.0
        assert packet["attended_salience"]["anger"] == 0.0


def test_attention_gain_multiplies_each_dimension_without_cross_coupling():
    runtime = make_runtime()
    for _ in range(20):
        packet = runtime.step("npc", signals=focused(), salience={"a": 0.2, "b": 0.8})
    gain = packet["attention_gain"]
    assert packet["attended_salience"]["a"] == pytest.approx(0.2 * gain)
    assert packet["attended_salience"]["b"] == pytest.approx(0.8 * gain)


def test_128_agent_isolation_under_interleaved_stress():
    runtime = AttentionRuntime(history_limit=8)
    for step in range(40):
        for index in range(128):
            agent = f"npc-{index}"
            signals = focused() if index % 2 == 0 else {"threat": 1.0 if step % 7 == 0 else 0.2}
            runtime.step(agent, signals=signals, salience={"x": index / 127.0})
    for index in range(128):
        state = runtime.get_state(f"npc-{index}")
        assert len(state["history"]) == 8
        assert state["history"][-1]["agent"] == f"npc-{index}"
    assert runtime.snapshot()["sequence"] == 128 * 40


def test_5000_step_finite_state_stress_and_json_safety():
    runtime = AttentionRuntime(history_limit=16)
    for step in range(5000):
        phase = step % 11
        signals = {
            "task_focus": (phase % 5) / 4.0,
            "repetition": (phase % 3) / 2.0,
            "stability": (phase % 7) / 6.0,
            "novelty": ((phase * 3) % 11) / 10.0,
            "threat": ((phase * 5) % 11) / 10.0,
            "contradiction": 1.0 if phase == 9 else 0.0,
            "interpretation_impulse": 0.8 if phase == 10 else 0.0,
        }
        packet = runtime.step("npc", signals=signals, salience={"anger": 0.9})
        assert math.isfinite(packet["flow_pressure_after"])
        assert math.isfinite(packet["attention_gain"])
    snapshot = runtime.snapshot()
    assert snapshot["sequence"] == 5000
    assert len(snapshot["agents"]["npc"]["history"]) == 16
    assert_json_safe(snapshot)


def test_long_prefix_snapshot_forks_replay_identically():
    runtime = AttentionRuntime(history_limit=32)
    for step in range(1200):
        runtime.step("npc", signals=focused(novelty=(step % 9) / 20.0), salience={"anger": 0.8})
    snapshot = runtime.snapshot()
    left = AttentionRuntime.from_snapshot(deepcopy(snapshot))
    right = AttentionRuntime.from_snapshot(deepcopy(snapshot))
    future = [focused(threat=0.9 if i % 17 == 0 else 0.0, novelty=(i % 5) / 10.0) for i in range(500)]
    assert [left.step("npc", signals=s) for s in future] == [right.step("npc", signals=s) for s in future]
    assert left.snapshot() == right.snapshot()


def test_snapshot_records_capture_config_used_for_math():
    runtime = AttentionRuntime()
    runtime.register_agent("npc", config={"build_rate": 0.5, "interrupt_threshold": 0.6})
    packet = runtime.step("npc", signals=focused())
    assert packet["config"] == runtime.get_state("npc")["config"]
    assert runtime.snapshot()["agents"]["npc"]["history"][0]["config"] == packet["config"]


def test_recorded_config_is_detached_from_later_reconfiguration():
    runtime = AttentionRuntime()
    runtime.register_agent("npc", config={"build_rate": 0.2})
    runtime.step("npc", signals=focused())
    before = deepcopy(runtime.get_state("npc")["history"][0]["config"])
    runtime.register_agent("npc", config={"build_rate": 0.8})
    assert runtime.get_state("npc")["history"][0]["config"] == before
    assert runtime.get_state("npc")["config"]["build_rate"] == 0.8


def test_legacy_phase_three_history_without_record_config_still_restores():
    snapshot = make_snapshot()
    for record in snapshot["agents"]["a"]["history"]:
        del record["config"]
    restored = AttentionRuntime.from_snapshot(deepcopy(snapshot))
    assert restored.snapshot() == snapshot


def test_snapshot_roundtrip_with_reconfiguration_between_steps():
    runtime = AttentionRuntime()
    runtime.step("npc", signals=focused())
    runtime.register_agent("npc", initial_flow_pressure=0.3, config={"build_rate": 0.8})
    runtime.step("npc", signals=focused(novelty=0.2))
    snapshot = runtime.snapshot()
    restored = AttentionRuntime.from_snapshot(snapshot)
    assert restored.snapshot() == snapshot


def test_snapshot_global_sequences_are_unique_across_agents():
    snapshot = make_snapshot(two_agents=True)
    a = snapshot["agents"]["a"]["history"][0]["sequence"]
    snapshot["agents"]["b"]["history"][0]["sequence"] = a
    with pytest.raises(ValueError, match="duplicated"):
        AttentionRuntime.from_snapshot(snapshot)


@pytest.mark.parametrize("key", [
    "agent", "source", "signals", "support", "interrupt_strength", "breakthrough",
    "target_flow_pressure", "flow_pressure_before", "flow_pressure_after",
    "flow_active_before", "flow_active_after", "transition", "flow_depth",
    "attention_gain", "resurfaced", "underlying_salience", "attended_salience", "provenance",
])
def test_snapshot_history_requires_exact_record_shape(key):
    snapshot = make_snapshot()
    del first_record(snapshot)[key]
    with pytest.raises(ValueError, match="invalid keys"):
        AttentionRuntime.from_snapshot(snapshot)


def test_snapshot_history_rejects_unknown_record_key():
    snapshot = make_snapshot()
    first_record(snapshot)["extra"] = 1
    with pytest.raises(ValueError, match="invalid keys"):
        AttentionRuntime.from_snapshot(snapshot)


def test_snapshot_agent_config_must_be_canonical_complete():
    snapshot = make_snapshot()
    del snapshot["agents"]["a"]["config"]["build_rate"]
    with pytest.raises(ValueError, match="canonical and complete"):
        AttentionRuntime.from_snapshot(snapshot)


def test_snapshot_record_config_must_be_canonical_complete():
    snapshot = make_snapshot()
    del first_record(snapshot)["config"]["build_rate"]
    with pytest.raises(ValueError, match="canonical and complete"):
        AttentionRuntime.from_snapshot(snapshot)


@pytest.mark.parametrize("source", ["", "   ", " player "])
def test_snapshot_source_must_be_nonempty_and_canonical(source):
    snapshot = make_snapshot()
    first_record(snapshot)["source"] = source
    with pytest.raises(ValueError, match="source"):
        AttentionRuntime.from_snapshot(snapshot)


def test_snapshot_none_source_remains_valid():
    runtime = AttentionRuntime()
    runtime.step("a", signals=focused(), source=None)
    snapshot = runtime.snapshot()
    assert AttentionRuntime.from_snapshot(snapshot).snapshot() == snapshot


def test_snapshot_signals_must_be_complete():
    snapshot = make_snapshot()
    del first_record(snapshot)["signals"]["threat"]
    with pytest.raises(ValueError, match="canonical and complete"):
        AttentionRuntime.from_snapshot(snapshot)


def test_snapshot_signals_reject_unknown_channel():
    snapshot = make_snapshot()
    first_record(snapshot)["signals"]["unknown"] = 0.2
    with pytest.raises(ValueError, match="unsupported keys"):
        AttentionRuntime.from_snapshot(snapshot)


@pytest.mark.parametrize("field", ["support", "interrupt_strength", "target_flow_pressure"])
def test_snapshot_rejects_nonfinite_or_out_of_range_derived_fields(field):
    snapshot = make_snapshot()
    first_record(snapshot)[field] = 2.0
    with pytest.raises(ValueError):
        AttentionRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_support_math_corruption():
    snapshot = make_snapshot()
    first_record(snapshot)["support"] += 0.01
    with pytest.raises(ValueError, match="support is inconsistent"):
        AttentionRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_interrupt_strength_math_corruption():
    snapshot = make_snapshot()
    first_record(snapshot)["interrupt_strength"] += 0.01
    with pytest.raises(ValueError, match="interrupt_strength is inconsistent"):
        AttentionRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_target_pressure_math_corruption():
    snapshot = make_snapshot()
    first_record(snapshot)["target_flow_pressure"] += 0.01
    with pytest.raises(ValueError, match="target_flow_pressure is inconsistent"):
        AttentionRuntime.from_snapshot(snapshot)


@pytest.mark.parametrize("field", ["flow_pressure_before", "flow_pressure_after", "flow_depth", "attention_gain"])
def test_snapshot_rejects_invalid_unit_runtime_fields(field):
    snapshot = make_snapshot()
    first_record(snapshot)[field] = -0.1
    with pytest.raises(ValueError):
        AttentionRuntime.from_snapshot(snapshot)


@pytest.mark.parametrize("field", ["breakthrough", "flow_active_before", "flow_active_after", "resurfaced"])
def test_snapshot_rejects_nonbool_flags(field):
    snapshot = make_snapshot()
    first_record(snapshot)[field] = 1
    with pytest.raises(ValueError, match="bool"):
        AttentionRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_transition_label_corruption():
    snapshot = make_snapshot()
    first_record(snapshot)["transition"] = "entered"
    with pytest.raises(ValueError, match="transition is inconsistent"):
        AttentionRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_breakthrough_math_corruption():
    snapshot = make_snapshot()
    record = first_record(snapshot)
    record["breakthrough"] = not record["breakthrough"]
    with pytest.raises(ValueError, match="breakthrough is inconsistent"):
        AttentionRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_flow_pressure_math_corruption():
    snapshot = make_snapshot()
    first_record(snapshot)["flow_pressure_after"] += 0.01
    with pytest.raises(ValueError, match="flow pressure math is inconsistent"):
        AttentionRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_flow_active_math_corruption():
    snapshot = make_snapshot()
    record = first_record(snapshot)
    record["flow_active_after"] = not record["flow_active_after"]
    record["transition"] = "entered" if record["flow_active_after"] else "released"
    with pytest.raises(ValueError, match="flow active math is inconsistent"):
        AttentionRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_flow_depth_math_corruption():
    snapshot = make_snapshot()
    first_record(snapshot)["flow_depth"] = 0.5
    with pytest.raises(ValueError, match="flow_depth is inconsistent"):
        AttentionRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_attention_gain_math_corruption():
    snapshot = make_snapshot()
    first_record(snapshot)["attention_gain"] = 0.5
    with pytest.raises(ValueError, match="attention_gain is inconsistent"):
        AttentionRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_resurfaced_math_corruption():
    snapshot = make_snapshot()
    record = first_record(snapshot)
    record["resurfaced"] = not record["resurfaced"]
    with pytest.raises(ValueError, match="resurfaced is inconsistent"):
        AttentionRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_underlying_salience_normalization_collision():
    snapshot = make_snapshot()
    first_record(snapshot)["underlying_salience"][" anger "] = 0.2
    with pytest.raises(ValueError, match="duplicate normalized"):
        AttentionRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_attended_salience_normalization_collision():
    snapshot = make_snapshot()
    first_record(snapshot)["attended_salience"][" anger "] = 0.2
    with pytest.raises(ValueError, match="duplicate normalized"):
        AttentionRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_salience_dimension_mismatch():
    snapshot = make_snapshot()
    del first_record(snapshot)["attended_salience"]["anger"]
    with pytest.raises(ValueError, match="dimensions mismatch"):
        AttentionRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_attended_salience_math_corruption():
    snapshot = make_snapshot()
    first_record(snapshot)["attended_salience"]["anger"] = 0.123
    with pytest.raises(ValueError, match="attended_salience.anger is inconsistent"):
        AttentionRuntime.from_snapshot(snapshot)


@pytest.mark.parametrize("bad", [[], "bad", 1, True])
def test_snapshot_rejects_non_dict_provenance(bad):
    snapshot = make_snapshot()
    first_record(snapshot)["provenance"] = bad
    with pytest.raises(ValueError, match="provenance must be a dict or None"):
        AttentionRuntime.from_snapshot(snapshot)


def test_snapshot_accepts_none_provenance():
    runtime = AttentionRuntime()
    runtime.step("a", signals=focused(), provenance=None)
    snapshot = runtime.snapshot()
    assert AttentionRuntime.from_snapshot(snapshot).snapshot() == snapshot


def test_snapshot_rejects_noncanonical_underlying_salience_key_even_without_collision():
    snapshot = make_snapshot()
    record = first_record(snapshot)
    value = record["underlying_salience"].pop("anger")
    record["underlying_salience"][" anger "] = value
    with pytest.raises(ValueError, match="underlying_salience must be canonical"):
        AttentionRuntime.from_snapshot(snapshot)


def test_snapshot_rejects_noncanonical_attended_salience_key_even_without_collision():
    snapshot = make_snapshot()
    record = first_record(snapshot)
    value = record["attended_salience"].pop("anger")
    record["attended_salience"][" anger "] = value
    with pytest.raises(ValueError, match="attended_salience must be canonical"):
        AttentionRuntime.from_snapshot(snapshot)


def test_snapshot_corruption_rejection_does_not_mutate_input():
    snapshot = make_snapshot()
    first_record(snapshot)["support"] += 0.1
    original = deepcopy(snapshot)
    with pytest.raises(ValueError):
        AttentionRuntime.from_snapshot(snapshot)
    assert snapshot == original


def test_restored_snapshot_is_fully_detached_from_input_nested_history():
    snapshot = make_snapshot()
    restored = AttentionRuntime.from_snapshot(deepcopy(snapshot))
    snapshot["agents"]["a"]["history"][0]["signals"]["task_focus"] = 0.123
    snapshot["agents"]["a"]["history"][0]["config"]["build_rate"] = 0.123
    snapshot["agents"]["a"]["history"][0]["provenance"]["i"] = 999
    fresh = restored.snapshot()
    assert fresh["agents"]["a"]["history"][0]["signals"]["task_focus"] != 0.123
    assert fresh["agents"]["a"]["history"][0]["config"]["build_rate"] != 0.123
    assert fresh["agents"]["a"]["history"][0]["provenance"]["i"] != 999


def test_trimmed_multiagent_snapshot_with_sparse_global_sequences_restores():
    runtime = AttentionRuntime(history_limit=2)
    for i in range(8):
        runtime.step("a", signals=focused())
        if i % 2 == 0:
            runtime.step("b", signals={"threat": 0.2})
    snapshot = runtime.snapshot()
    assert snapshot["sequence"] == 12
    assert [r["sequence"] for r in snapshot["agents"]["a"]["history"]] == [10, 12]
    assert [r["sequence"] for r in snapshot["agents"]["b"]["history"]] == [8, 11]
    assert AttentionRuntime.from_snapshot(snapshot).snapshot() == snapshot


def test_snapshot_rejects_duplicate_sequence_even_when_each_agent_history_is_locally_increasing():
    snapshot = make_snapshot(two_agents=True)
    a_seq = snapshot["agents"]["a"]["history"][2]["sequence"]
    b_history = snapshot["agents"]["b"]["history"]
    target = next(i for i, r in enumerate(b_history) if i > 0 and i < len(b_history) - 1)
    b_history[target]["sequence"] = a_seq
    # Keep local ordering valid so only the global uniqueness rule catches it.
    assert b_history[target - 1]["sequence"] < a_seq < b_history[target + 1]["sequence"]
    with pytest.raises(ValueError, match="duplicated"):
        AttentionRuntime.from_snapshot(snapshot)


def test_full_suppression_config_reaches_zero_attended_salience_without_erasing_underlying():
    runtime = AttentionRuntime()
    runtime.register_agent("npc", config={"max_suppression": 1.0})
    packet = None
    for _ in range(200):
        packet = runtime.step("npc", signals=focused(), salience={"anger": 1.0})
    assert packet["flow_active_after"] is True
    assert packet["attention_gain"] < 1e-12
    assert packet["underlying_salience"]["anger"] == 1.0
    assert packet["attended_salience"]["anger"] < 1e-12


def test_zero_suppression_config_keeps_full_access_even_in_flow():
    runtime = AttentionRuntime()
    runtime.register_agent("npc", config={"max_suppression": 0.0})
    packet = None
    for _ in range(20):
        packet = runtime.step("npc", signals=focused(), salience={"anger": 0.9})
    assert packet["flow_active_after"] is True
    assert packet["attention_gain"] == 1.0
    assert packet["attended_salience"] == {"anger": 0.9}


def test_zero_build_rate_never_enters_flow_from_zero():
    runtime = AttentionRuntime()
    runtime.register_agent("npc", config={"build_rate": 0.0})
    for _ in range(100):
        packet = runtime.step("npc", signals=focused())
    assert packet["flow_pressure_after"] == 0.0
    assert packet["flow_active_after"] is False


def test_zero_release_rate_retains_pressure_absent_breakthrough():
    runtime = AttentionRuntime()
    runtime.register_agent("npc", initial_flow_pressure=0.8, flow_active=True, config={"release_rate": 0.0})
    packet = runtime.step("npc", signals=focused(task_focus=0.0, repetition=0.0, stability=0.0, novelty=0.6, threat=0.6))
    assert packet["breakthrough"] is False
    assert packet["flow_pressure_after"] == 0.8
    assert packet["flow_active_after"] is True


def test_max_interrupt_release_collapses_pressure_on_threshold_breakthrough():
    runtime = AttentionRuntime()
    runtime.register_agent("npc", initial_flow_pressure=0.8, flow_active=True, config={"interrupt_release": 1.0})
    packet = runtime.step("npc", signals={"threat": 1.0})
    assert packet["flow_pressure_after"] == 0.0
    assert packet["flow_active_after"] is False


def test_entry_threshold_one_requires_exact_pressure_one():
    runtime = AttentionRuntime()
    runtime.register_agent("npc", config={"entry_threshold": 1.0, "exit_threshold": 0.5, "build_rate": 1.0})
    packet = runtime.step("npc", signals=focused())
    assert packet["flow_pressure_after"] == 1.0
    assert packet["flow_active_after"] is True
    assert packet["flow_depth"] == 1.0


def test_snapshot_json_roundtrip_preserves_exact_replay():
    runtime = AttentionRuntime(history_limit=12)
    for i in range(30):
        runtime.step("npc", signals=focused(novelty=(i % 4) / 10.0), salience={"anger": 0.8}, provenance={"i": i})
    wire = json.loads(json.dumps(runtime.snapshot(), allow_nan=False, sort_keys=True))
    restored = AttentionRuntime.from_snapshot(wire)
    future = [focused(threat=1.0 if i == 5 else 0.0) for i in range(20)]
    original_packets = [runtime.step("npc", signals=s) for s in future]
    restored_packets = [restored.step("npc", signals=s) for s in future]
    assert original_packets == restored_packets
    assert runtime.snapshot() == restored.snapshot()

def test_snapshot_restore_valid_breakthrough_record_exercises_interrupt_pressure_math():
    runtime = AttentionRuntime()
    runtime.step("a", signals={"threat": 1.0}, salience={"fear": 0.9})
    snapshot = runtime.snapshot()
    assert snapshot["agents"]["a"]["history"][0]["breakthrough"] is True
    assert AttentionRuntime.from_snapshot(snapshot).snapshot() == snapshot
