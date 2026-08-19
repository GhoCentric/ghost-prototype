from copy import deepcopy
import json
import math

import pytest

from ghost.attention import (
    ATTENTION_SNAPSHOT_SCHEMA_VERSION,
    AttentionRuntime,
    _attention_gain,
    _flow_depth,
    _interrupt_strength,
    _json_safe,
    _resolve_flow,
    _support,
    _transition,
    _validate_config,
    _validate_history_limit,
    _validate_salience,
    _validate_signals,
)


def focused_signals(**overrides):
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


def test_fresh_runtime_has_no_state():
    runtime = AttentionRuntime()
    assert runtime.has_state() is False
    assert runtime.snapshot() == {
        "schema_version": "1.0",
        "history_limit": 64,
        "sequence": 0,
        "agents": {},
    }


def test_register_agent_defaults_and_copy_boundary():
    runtime = AttentionRuntime()
    packet = runtime.register_agent(" Sera ")
    assert runtime.has_state() is True
    assert packet["agent"] == "Sera"
    assert packet["flow_pressure"] == 0.0
    assert packet["flow_active"] is False
    assert packet["attention_gain"] == 1.0
    packet["config"]["build_rate"] = 0.99
    assert runtime.get_state("Sera")["config"]["build_rate"] != 0.99


def test_register_agent_preserves_pressure_when_reconfiguring_without_initial():
    runtime = AttentionRuntime()
    runtime.register_agent("Sera", initial_flow_pressure=0.5)
    runtime.register_agent("Sera", config={"build_rate": 0.5})
    assert runtime.get_state("Sera")["flow_pressure"] == 0.5
    runtime.register_agent("Sera", initial_flow_pressure=0.4, config={"build_rate": 0.5})
    assert runtime.get_state("Sera")["flow_pressure"] == 0.4
    assert runtime.get_state("Sera")["config"]["build_rate"] == 0.5
    runtime.register_agent("Sera", initial_flow_pressure=0.3)
    assert runtime.get_state("Sera")["flow_pressure"] == 0.3
    assert runtime.get_state("Sera")["config"]["build_rate"] == 0.5


def test_register_agent_explicit_hysteresis_states_are_supported():
    runtime = AttentionRuntime()
    inactive = runtime.register_agent(
        "A", initial_flow_pressure=0.5, flow_active=False
    )
    active = runtime.register_agent(
        "B", initial_flow_pressure=0.5, flow_active=True
    )
    assert inactive["flow_active"] is False
    assert active["flow_active"] is True


@pytest.mark.parametrize("value", [True, False, 0, -1, 1.5, "64", None])
def test_invalid_history_limits_rejected(value):
    with pytest.raises(ValueError, match="history_limit"):
        _validate_history_limit(value)


@pytest.mark.parametrize("value", [1, [], "bad"])
def test_config_must_be_dict_or_none(value):
    with pytest.raises(ValueError, match="attention config"):
        _validate_config(value)


def test_config_unknown_keys_rejected():
    with pytest.raises(ValueError, match="unsupported keys: nope, wat"):
        _validate_config({"wat": 1, "nope": 1})


@pytest.mark.parametrize(
    "key,value",
    [
        ("entry_threshold", -0.1),
        ("exit_threshold", 1.1),
        ("build_rate", math.inf),
        ("release_rate", True),
        ("interrupt_threshold", "x"),
        ("interrupt_release", None),
        ("max_suppression", -1),
    ],
)
def test_config_unit_fields_are_validated(key, value):
    with pytest.raises(ValueError):
        _validate_config({key: value})


def test_config_exit_cannot_exceed_entry():
    with pytest.raises(ValueError, match="cannot exceed"):
        _validate_config({"entry_threshold": 0.4, "exit_threshold": 0.5})


def test_signals_none_returns_complete_zero_map():
    result = _validate_signals(None)
    assert set(result) == {
        "task_focus", "repetition", "stability", "novelty", "threat",
        "contradiction", "interpretation_impulse",
    }
    assert all(value == 0.0 for value in result.values())


@pytest.mark.parametrize("value", [1, [], "bad"])
def test_signals_must_be_dict_or_none(value):
    with pytest.raises(ValueError, match="signals"):
        _validate_signals(value)


def test_signals_unknown_keys_rejected():
    with pytest.raises(ValueError, match="unsupported keys"):
        _validate_signals({"boredom": 1.0})


@pytest.mark.parametrize("value", [-0.01, 1.01, math.nan, math.inf, True, "1"])
def test_signal_values_are_unit_finite_numbers(value):
    with pytest.raises(ValueError):
        _validate_signals({"task_focus": value})


def test_partial_signals_fill_defaults():
    values = _validate_signals({"task_focus": 0.75})
    assert values["task_focus"] == 0.75
    assert values["threat"] == 0.0


@pytest.mark.parametrize("value", [1, [], "bad"])
def test_salience_must_be_dict_or_none(value):
    with pytest.raises(ValueError, match="salience"):
        _validate_salience(value)


def test_salience_none_is_empty():
    assert _validate_salience(None) == {}


@pytest.mark.parametrize("key", ["", "   ", 5])
def test_salience_names_must_be_nonempty_strings(key):
    with pytest.raises(ValueError, match="salience name"):
        _validate_salience({key: 0.2})


@pytest.mark.parametrize("value", [-0.1, 1.1, math.nan, True, "0.2"])
def test_salience_values_are_unit_finite(value):
    with pytest.raises(ValueError):
        _validate_salience({"anger": value})


def test_salience_normalized_collision_rejected():
    with pytest.raises(ValueError, match="duplicate normalized"):
        _validate_salience({"anger": 0.2, " anger ": 0.3})


def test_json_safe_accepts_nested_json_values():
    assert _json_safe({"a": [None, True, 1, 0.5, "x", {"b": False}]}) is None


@pytest.mark.parametrize("value", [math.nan, math.inf])
def test_json_safe_rejects_nonfinite_float(value):
    with pytest.raises(ValueError, match="finite"):
        _json_safe({"a": value})


def test_json_safe_rejects_nonstring_dict_keys():
    with pytest.raises(ValueError, match="keys must be strings"):
        _json_safe({1: "x"})


def test_json_safe_rejects_non_json_types():
    with pytest.raises(ValueError, match="JSON-safe"):
        _json_safe({"a": object()})


def test_support_is_weighted_and_bounded_at_extremes():
    assert _support(focused_signals()) == pytest.approx(1.0)
    low = focused_signals(
        task_focus=0.0, repetition=0.0, stability=0.0, novelty=1.0, threat=1.0
    )
    assert _support(low) == 0.0


def test_interrupt_strength_uses_strongest_interrupt_channel():
    signals = focused_signals(
        novelty=0.1, threat=0.2, contradiction=0.7, interpretation_impulse=0.4
    )
    assert _interrupt_strength(signals) == 0.7


def test_resolve_flow_and_transition_hysteresis_helpers():
    config = _validate_config(None)
    assert _resolve_flow(False, 0.72, config) is True
    assert _resolve_flow(False, 0.71, config) is False
    assert _resolve_flow(True, 0.45, config) is True
    assert _resolve_flow(True, 0.44, config) is False
    assert _transition(False, True) == "entered"
    assert _transition(True, False) == "released"
    assert _transition(True, True) == "retained_active"
    assert _transition(False, False) == "inactive"


def test_flow_depth_branches_and_attention_gain_branches():
    config = _validate_config(None)
    assert _flow_depth(False, 1.0, config) == 0.0
    assert _flow_depth(True, 0.72, config) == 0.0
    assert _flow_depth(True, 1.0, config) == 1.0
    edge = _validate_config({"entry_threshold": 1.0, "exit_threshold": 1.0})
    assert _flow_depth(True, 1.0, edge) == 1.0
    assert _attention_gain(False, 0.0, config, False) == 1.0
    assert _attention_gain(True, 1.0, config, True) == 1.0
    assert _attention_gain(True, 1.0, config, False) == pytest.approx(0.04)
    full = _validate_config({"max_suppression": 1.0})
    assert _attention_gain(True, 1.0, full, False) == 0.0


def test_step_auto_registers_and_does_not_mutate_inputs():
    runtime = AttentionRuntime()
    signals = focused_signals()
    salience = {"anger": 0.8, "betrayal": 0.7}
    provenance = {"event": {"id": 9}, "tags": ["observed"]}
    original = deepcopy((signals, salience, provenance))
    packet = runtime.step(
        "Sera", signals=signals, salience=salience, source="player", provenance=provenance
    )
    assert (signals, salience, provenance) == original
    assert packet["source"] == "player"
    assert packet["underlying_salience"] == salience
    assert runtime.get_state("Sera") is not None


def test_step_rejects_invalid_source_and_provenance():
    runtime = AttentionRuntime()
    with pytest.raises(ValueError, match="source"):
        runtime.step("Sera", source="  ")
    with pytest.raises(ValueError, match="provenance"):
        runtime.step("Sera", provenance=[])
    with pytest.raises(ValueError):
        runtime.step("Sera", provenance={"x": math.inf})


def test_sustained_focus_enters_flow_without_timer_or_rng():
    runtime = AttentionRuntime()
    packets = []
    for _ in range(8):
        packets.append(runtime.step("Sera", signals=focused_signals(), salience={"anger": 0.9}))
    assert any(packet["transition"] == "entered" for packet in packets)
    final = packets[-1]
    assert final["flow_active_after"] is True
    assert 0.0 < final["attention_gain"] < 1.0
    assert final["attended_salience"]["anger"] < 0.9
    assert final["underlying_salience"]["anger"] == 0.9


def test_breakthrough_restores_current_access_and_releases_flow():
    runtime = AttentionRuntime()
    for _ in range(10):
        runtime.step("Sera", signals=focused_signals(), salience={"anger": 0.9})
    assert runtime.get_state("Sera")["flow_active"] is True
    packet = runtime.step(
        "Sera",
        signals=focused_signals(threat=1.0),
        salience={"anger": 0.9},
    )
    assert packet["breakthrough"] is True
    assert packet["resurfaced"] is True
    assert packet["flow_active_after"] is False
    assert packet["attention_gain"] == 1.0
    assert packet["attended_salience"] == {"anger": 0.9}


def test_non_breakthrough_can_release_through_pressure_decay():
    runtime = AttentionRuntime()
    for _ in range(10):
        runtime.step("Sera", signals=focused_signals())
    assert runtime.get_state("Sera")["flow_active"] is True
    packet = None
    low = focused_signals(
        task_focus=0.0,
        repetition=0.0,
        stability=0.0,
        novelty=0.6,
        threat=0.6,
    )
    for _ in range(8):
        packet = runtime.step("Sera", signals=low)
        if packet["transition"] == "released":
            break
    assert packet["transition"] == "released"
    assert packet["breakthrough"] is False
    assert packet["resurfaced"] is True


def test_inactive_non_breakthrough_is_not_resurfacing():
    runtime = AttentionRuntime()
    packet = runtime.step("Sera", signals={"novelty": 0.2})
    assert packet["flow_active_before"] is False
    assert packet["flow_active_after"] is False
    assert packet["resurfaced"] is False


def test_target_pressure_uses_build_and_release_rates():
    runtime = AttentionRuntime()
    first = runtime.step("Sera", signals=focused_signals())
    assert first["flow_pressure_after"] == pytest.approx(0.26)
    second = runtime.step(
        "Sera",
        signals=focused_signals(
            task_focus=0.0,
            repetition=0.0,
            stability=0.0,
            novelty=0.6,
            threat=0.6,
        ),
    )
    expected_target = (0.14 * 0.4 + 0.10 * 0.4) * (1.0 - 0.85 * 0.6)
    assert second["target_flow_pressure"] == pytest.approx(expected_target)
    assert second["flow_pressure_after"] == pytest.approx(
        0.26 + (expected_target - 0.26) * 0.48
    )


def test_history_limit_trims_oldest_records():
    runtime = AttentionRuntime(history_limit=2)
    for _ in range(4):
        runtime.step("Sera", signals=focused_signals())
    history = runtime.get_state("Sera")["history"]
    assert [record["sequence"] for record in history] == [3, 4]


def test_returned_record_and_state_history_do_not_alias_runtime():
    runtime = AttentionRuntime()
    packet = runtime.step(
        "Sera", signals=focused_signals(), provenance={"nested": {"x": 1}}
    )
    packet["provenance"]["nested"]["x"] = 99
    state = runtime.get_state("Sera")
    state["history"][0]["signals"]["task_focus"] = 0
    fresh = runtime.get_state("Sera")
    assert fresh["history"][0]["provenance"]["nested"]["x"] == 1
    assert fresh["history"][0]["signals"]["task_focus"] == 1.0


def test_agents_are_isolated():
    runtime = AttentionRuntime()
    for _ in range(10):
        runtime.step("Sera", signals=focused_signals())
    runtime.step("Rowan", signals={"threat": 1.0})
    assert runtime.get_state("Sera")["flow_active"] is True
    assert runtime.get_state("Rowan")["flow_active"] is False
    assert len(runtime.get_state("Sera")["history"]) == 10
    assert len(runtime.get_state("Rowan")["history"]) == 1


def test_signal_trajectory_not_tick_number_determines_flow():
    a = AttentionRuntime()
    b = AttentionRuntime()
    for _ in range(8):
        a.step("npc", signals=focused_signals())
        b.step("npc", signals=focused_signals(novelty=0.55, threat=0.55))
    assert a.get_state("npc")["flow_active"] is True
    assert b.get_state("npc")["flow_active"] is False


def test_exact_replay_is_deterministic():
    sequence = [
        focused_signals(),
        focused_signals(repetition=0.7),
        focused_signals(novelty=0.2),
        focused_signals(threat=0.8),
        focused_signals(),
    ] * 5
    a = AttentionRuntime()
    b = AttentionRuntime()
    assert [a.step("npc", signals=s) for s in sequence] == [
        b.step("npc", signals=s) for s in sequence
    ]
    assert a.snapshot() == b.snapshot()


def test_snapshot_round_trip_and_fork_replay_identically():
    runtime = AttentionRuntime(history_limit=10)
    for _ in range(9):
        runtime.step("Sera", signals=focused_signals(), salience={"anger": 0.8})
    snapshot = runtime.snapshot()
    restored = AttentionRuntime.from_snapshot(snapshot)
    assert restored.snapshot() == snapshot
    snapshot["agents"]["Sera"]["config"]["build_rate"] = 0.99
    assert restored.get_state("Sera")["config"]["build_rate"] != 0.99
    future = [
        focused_signals(novelty=0.1),
        focused_signals(contradiction=0.9),
        focused_signals(),
    ]
    original_packets = [runtime.step("Sera", signals=s) for s in future]
    restored_packets = [restored.step("Sera", signals=s) for s in future]
    assert original_packets == restored_packets
    assert runtime.snapshot() == restored.snapshot()


def test_snapshot_is_json_serializable():
    runtime = AttentionRuntime()
    runtime.step("Sera", signals=focused_signals(), provenance={"evidence": [1, 2]})
    json.dumps(runtime.snapshot(), allow_nan=False)


@pytest.mark.parametrize("value", [None, [], "bad", 3])
def test_snapshot_must_be_dict(value):
    with pytest.raises(ValueError, match="snapshot must be a dict"):
        AttentionRuntime.from_snapshot(value)


def test_snapshot_unknown_and_missing_keys_rejected():
    snap = AttentionRuntime().snapshot()
    bad = deepcopy(snap)
    bad["extra"] = 1
    with pytest.raises(ValueError, match="unsupported keys"):
        AttentionRuntime.from_snapshot(bad)
    for key in ("schema_version", "history_limit", "sequence", "agents"):
        bad = deepcopy(snap)
        del bad[key]
        with pytest.raises(ValueError, match="missing required keys"):
            AttentionRuntime.from_snapshot(bad)


def test_snapshot_json_safety_and_schema_are_validated():
    snap = AttentionRuntime().snapshot()
    bad = deepcopy(snap)
    bad["x"] = object()
    with pytest.raises(ValueError):
        AttentionRuntime.from_snapshot(bad)
    bad = deepcopy(snap)
    bad["schema_version"] = "9.9"
    with pytest.raises(ValueError, match="unsupported attention snapshot schema"):
        AttentionRuntime.from_snapshot(bad)


@pytest.mark.parametrize("sequence", [True, -1, 1.5, "1"])
def test_snapshot_sequence_must_be_nonnegative_integer(sequence):
    snap = AttentionRuntime().snapshot()
    snap["sequence"] = sequence
    with pytest.raises(ValueError, match="sequence"):
        AttentionRuntime.from_snapshot(snap)


def test_snapshot_agents_must_be_dict():
    snap = AttentionRuntime().snapshot()
    snap["agents"] = []
    with pytest.raises(ValueError, match="agents must be a dict"):
        AttentionRuntime.from_snapshot(snap)


def valid_active_snapshot():
    runtime = AttentionRuntime()
    for _ in range(10):
        runtime.step("Sera", signals=focused_signals())
    return runtime.snapshot()


def test_snapshot_agent_name_collision_and_state_type_rejected():
    snap = valid_active_snapshot()
    snap["agents"][" Sera "] = deepcopy(snap["agents"]["Sera"])
    with pytest.raises(ValueError, match="duplicate normalized agent"):
        AttentionRuntime.from_snapshot(snap)
    snap = valid_active_snapshot()
    snap["agents"]["Sera"] = []
    with pytest.raises(ValueError, match="must be a dict"):
        AttentionRuntime.from_snapshot(snap)


def test_snapshot_agent_keys_must_be_exact():
    snap = valid_active_snapshot()
    del snap["agents"]["Sera"]["config"]
    with pytest.raises(ValueError, match="keys must be exactly"):
        AttentionRuntime.from_snapshot(snap)


def test_snapshot_agent_pressure_active_and_config_validated():
    snap = valid_active_snapshot()
    snap["agents"]["Sera"]["flow_pressure"] = 2.0
    with pytest.raises(ValueError, match="flow_pressure"):
        AttentionRuntime.from_snapshot(snap)
    snap = valid_active_snapshot()
    snap["agents"]["Sera"]["flow_active"] = 1
    with pytest.raises(ValueError, match="flow_active"):
        AttentionRuntime.from_snapshot(snap)
    snap = valid_active_snapshot()
    snap["agents"]["Sera"]["config"]["build_rate"] = -1
    with pytest.raises(ValueError, match="build_rate"):
        AttentionRuntime.from_snapshot(snap)


def test_snapshot_hysteresis_inconsistency_rejected():
    snap = valid_active_snapshot()
    snap["agents"]["Sera"]["flow_active"] = False
    with pytest.raises(ValueError, match="flow state is inconsistent"):
        AttentionRuntime.from_snapshot(snap)


def test_snapshot_history_type_and_limit_validated():
    snap = valid_active_snapshot()
    snap["agents"]["Sera"]["history"] = {}
    with pytest.raises(ValueError, match="history must be a list"):
        AttentionRuntime.from_snapshot(snap)
    snap = valid_active_snapshot()
    snap["history_limit"] = 1
    with pytest.raises(ValueError, match="exceeds history_limit"):
        AttentionRuntime.from_snapshot(snap)


def test_snapshot_history_record_type_json_and_sequence_validated():
    snap = valid_active_snapshot()
    snap["agents"]["Sera"]["history"][0] = []
    with pytest.raises(ValueError, match="must be a dict"):
        AttentionRuntime.from_snapshot(snap)
    snap = valid_active_snapshot()
    snap["agents"]["Sera"]["history"][0]["provenance"] = {"x": math.nan}
    with pytest.raises(ValueError, match="finite"):
        AttentionRuntime.from_snapshot(snap)
    for bad_sequence in (True, 0, 999):
        snap = valid_active_snapshot()
        snap["agents"]["Sera"]["history"][0]["sequence"] = bad_sequence
        with pytest.raises(ValueError, match="sequence is invalid"):
            AttentionRuntime.from_snapshot(snap)


def test_snapshot_history_sequences_must_increase():
    snap = valid_active_snapshot()
    history = snap["agents"]["Sera"]["history"]
    history[1]["sequence"] = history[0]["sequence"]
    with pytest.raises(ValueError, match="sequence is invalid"):
        AttentionRuntime.from_snapshot(snap)


def test_snapshot_history_agent_must_match_owner():
    snap = valid_active_snapshot()
    snap["agents"]["Sera"]["history"][0]["agent"] = "Rowan"
    with pytest.raises(ValueError, match="agent is inconsistent"):
        AttentionRuntime.from_snapshot(snap)


def test_snapshot_latest_history_sequence_must_equal_global_sequence():
    snap = valid_active_snapshot()
    snap["sequence"] += 1
    with pytest.raises(ValueError, match="latest attention history sequence"):
        AttentionRuntime.from_snapshot(snap)


def test_empty_agents_require_zero_sequence():
    snap = AttentionRuntime().snapshot()
    snap["sequence"] = 1
    with pytest.raises(ValueError, match="must be zero"):
        AttentionRuntime.from_snapshot(snap)


def test_register_rejects_invalid_flow_active_and_inconsistent_explicit_state():
    runtime = AttentionRuntime()
    with pytest.raises(ValueError, match="flow_active"):
        runtime.register_agent("Sera", flow_active=1)
    with pytest.raises(ValueError, match="inconsistent"):
        runtime.register_agent("A", initial_flow_pressure=0.8, flow_active=False)
    with pytest.raises(ValueError, match="inconsistent"):
        runtime.register_agent("B", initial_flow_pressure=0.1, flow_active=True)


def test_get_state_unknown_agent_returns_none():
    assert AttentionRuntime().get_state("unknown") is None


def test_breakthrough_pressure_is_clamped_and_gain_stays_finite():
    runtime = AttentionRuntime()
    runtime.register_agent(
        "Sera",
        initial_flow_pressure=1.0,
        flow_active=True,
        config={"interrupt_release": 1.0},
    )
    packet = runtime.step("Sera", signals={"threat": 1.0}, salience={"fear": 1.0})
    assert packet["flow_pressure_after"] == 0.0
    assert packet["attention_gain"] == 1.0
    assert math.isfinite(packet["attention_gain"])
