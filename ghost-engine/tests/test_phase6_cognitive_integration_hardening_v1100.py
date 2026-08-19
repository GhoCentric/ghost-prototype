from __future__ import annotations

import copy
import json

import pytest

from ghost import GhostAPI


def configured_api(agent: str = "sera") -> GhostAPI:
    api = GhostAPI()
    api.register_emotional_agent(
        agent,
        initial={"anger": 0.62, "fear": 0.28, "hope": 0.18},
        salience_bias={"anger": 1.0, "fear": 1.1, "hope": 0.9},
    )
    api.register_interpretation_agent(
        agent,
        initial={"betrayal": 0.58, "cooperation": 0.22, "danger": 0.14},
        rules={
            "action:report": {"betrayal": 0.45},
            "action:help": {"cooperation": 0.55},
            "action:threaten": {"danger": 0.70, "betrayal": 0.20},
            "confidential_evidence_shared": {"betrayal": 0.35},
        },
    )
    api.register_attention_agent(agent)
    return api


def flow_signals() -> dict:
    return {"task_focus": 1.0, "repetition": 1.0, "stability": 1.0}


def neutral_signals() -> dict:
    return {
        "task_focus": 0.4,
        "repetition": 0.2,
        "stability": 0.5,
        "novelty": 0.2,
        "threat": 0.1,
        "contradiction": 0.0,
        "interpretation_impulse": 0.0,
    }


def source_states(api: GhostAPI, agent: str = "sera") -> tuple[dict, dict]:
    return (
        copy.deepcopy(api.emotional_state(agent)),
        copy.deepcopy(api.interpretation_state(agent)),
    )


def assert_sources_unchanged(api: GhostAPI, before: tuple[dict, dict], agent: str = "sera") -> None:
    emotion_before, interpretation_before = before
    assert api.emotional_state(agent) == emotion_before
    assert api.interpretation_state(agent) == interpretation_before


def run_cognitive_turn(api: GhostAPI, *, agent: str = "sera", emotion_event: str = "betrayal", action: str = "report", signals: dict | None = None) -> dict:
    emotion = api.apply_emotional_event(agent, emotion_event, source="player")
    meaning = api.evaluate_action_meaning(
        agent,
        action,
        features={"confidential_evidence_shared": 1.0} if action == "report" else None,
        source="player",
        provenance={"phase": 6},
    )
    attention = api.advance_attention_from_state(
        agent,
        signals=signals,
        provenance={"phase": 6, "action": action},
    )
    return {"emotion": emotion, "meaning": meaning, "attention": attention}


def test_end_to_end_bridge_consumes_current_persistent_sources():
    api = configured_api()
    turn = run_cognitive_turn(api)
    bridge = turn["attention"]["bridge"]
    assert bridge["sources"]["emotion"]["revision"] == api.emotional_state("sera")["history"][-1]["sequence"]
    assert bridge["sources"]["interpretation"]["revision"] == api.interpretation_state("sera")["history"][-1]["sequence"]


def test_attention_underlying_vector_is_exact_bridge_vector():
    api = configured_api()
    packet = run_cognitive_turn(api)["attention"]
    assert packet["attention"]["underlying_salience"] == packet["bridge"]["salience"]


def test_attention_provenance_pins_exact_bridge_revisions():
    api = configured_api()
    packet = run_cognitive_turn(api)["attention"]
    assert packet["attention"]["provenance"]["salience_bridge"]["sources"] == packet["bridge"]["sources"]


def test_attention_step_cannot_mutate_persistent_sources():
    api = configured_api()
    api.apply_emotional_event("sera", "betrayal")
    api.evaluate_action_meaning("sera", "report")
    before = source_states(api)
    api.advance_attention_from_state("sera", signals=flow_signals())
    assert_sources_unchanged(api, before)


def test_return_packet_mutation_cannot_alias_persistent_sources():
    api = configured_api()
    packet = api.advance_attention_from_state("sera")
    packet["bridge"]["salience"]["emotion:anger"] = 0.0
    packet["attention"]["underlying_salience"]["interpretation:betrayal"] = 0.0
    assert api.emotional_state("sera")["levels"]["anger"] == 0.62
    assert api.interpretation_state("sera")["levels"]["betrayal"] == 0.58


def test_attention_history_mutation_cannot_alias_persistent_sources():
    api = configured_api()
    api.advance_attention_from_state("sera")
    state = api.attention_state("sera")
    state["history"][-1]["underlying_salience"]["emotion:anger"] = 0.0
    assert api.emotional_state("sera")["levels"]["anger"] == 0.62


def test_flow_compression_applies_uniform_gain_to_both_namespaces():
    api = configured_api()
    api.register_attention_agent("sera", initial_flow_pressure=0.95, flow_active=True)
    record = api.advance_attention_from_state("sera", signals=flow_signals())["attention"]
    gain = record["attention_gain"]
    assert gain < 1.0
    for name, value in record["underlying_salience"].items():
        assert record["attended_salience"][name] == pytest.approx(value * gain)


@pytest.mark.parametrize("channel", ["novelty", "threat", "contradiction", "interpretation_impulse"])
def test_each_breakthrough_channel_restores_full_cross_layer_access(channel):
    api = configured_api()
    api.register_attention_agent("sera", initial_flow_pressure=0.95, flow_active=True)
    record = api.advance_attention_from_state("sera", signals={channel: 1.0})["attention"]
    assert record["breakthrough"] is True
    assert record["attention_gain"] == 1.0
    assert record["attended_salience"] == record["underlying_salience"]


def test_source_update_is_visible_next_step_without_rewriting_old_attention_history():
    api = configured_api()
    first = api.advance_attention_from_state("sera")["attention"]
    api.apply_emotional_event("sera", "betrayal")
    api.evaluate_action_meaning("sera", "report")
    second = api.advance_attention_from_state("sera")["attention"]
    history = api.attention_state("sera")["history"]
    assert first["underlying_salience"] == history[-2]["underlying_salience"]
    assert second["underlying_salience"] == history[-1]["underlying_salience"]
    assert first["underlying_salience"] != second["underlying_salience"]


def test_source_revisions_advance_independently():
    api = configured_api()
    baseline = api.persistent_salience("sera")["sources"]
    api.apply_emotional_event("sera", "betrayal")
    emotion_only = api.persistent_salience("sera")["sources"]
    api.evaluate_action_meaning("sera", "report")
    both = api.persistent_salience("sera")["sources"]
    assert emotion_only["emotion"]["revision"] > baseline["emotion"]["revision"]
    assert emotion_only["interpretation"]["revision"] == baseline["interpretation"]["revision"]
    assert both["interpretation"]["revision"] > emotion_only["interpretation"]["revision"]


def test_attention_sequence_advances_without_advancing_source_revisions():
    api = configured_api()
    before = api.persistent_salience("sera")["sources"]
    a = api.advance_attention_from_state("sera")
    b = api.advance_attention_from_state("sera")
    after = api.persistent_salience("sera")["sources"]
    assert b["attention"]["sequence"] == a["attention"]["sequence"] + 1
    assert after == before


@pytest.mark.parametrize(
    "include_emotions,include_interpretations,expected_prefixes",
    [
        (True, True, {"emotion:", "interpretation:"}),
        (True, False, {"emotion:"}),
        (False, True, {"interpretation:"}),
        (False, False, set()),
    ],
)
def test_source_filters_are_preserved_through_attention(include_emotions, include_interpretations, expected_prefixes):
    api = configured_api()
    packet = api.advance_attention_from_state(
        "sera",
        include_emotions=include_emotions,
        include_interpretations=include_interpretations,
    )
    names = set(packet["attention"]["underlying_salience"])
    found = {prefix for prefix in ("emotion:", "interpretation:") if any(name.startswith(prefix) for name in names)}
    assert found == expected_prefixes


def test_bridge_only_read_never_creates_attention_state():
    api = configured_api()
    api.attention = type(api.attention)()
    assert api.attention_state("sera") is None
    api.persistent_salience("sera")
    assert api.attention_state("sera") is None


def test_bridge_statelessness_survives_full_cognitive_turn():
    api = configured_api()
    run_cognitive_turn(api)
    assert "salience_bridge" not in api.snapshot()


def test_combined_packet_never_claims_to_choose_action_or_dialogue():
    api = configured_api()
    serialized = json.dumps(run_cognitive_turn(api), sort_keys=True)
    assert '"dialogue"' not in serialized
    assert '"chosen_action"' not in serialized


def test_combined_turn_is_strict_json_safe():
    api = configured_api()
    packet = run_cognitive_turn(api)
    assert json.loads(json.dumps(packet, allow_nan=False)) == packet


def test_snapshot_is_strict_json_safe_after_combined_turns():
    api = configured_api()
    for _ in range(8):
        run_cognitive_turn(api, signals=flow_signals())
    snapshot = api.snapshot()
    assert json.loads(json.dumps(snapshot, allow_nan=False)) == snapshot


def test_snapshot_roundtrip_preserves_bridge_view_exactly():
    api = configured_api()
    run_cognitive_turn(api, signals=flow_signals())
    before = api.persistent_salience("sera")
    restored = GhostAPI.from_snapshot(copy.deepcopy(api.snapshot()))
    assert restored.persistent_salience("sera") == before


def test_json_snapshot_roundtrip_preserves_bridge_view_exactly():
    api = configured_api()
    run_cognitive_turn(api, signals=flow_signals())
    encoded = json.dumps(api.snapshot(), allow_nan=False)
    restored = GhostAPI.from_snapshot(json.loads(encoded))
    assert restored.persistent_salience("sera") == api.persistent_salience("sera")


def test_snapshot_forks_replay_identical_cross_layer_continuation():
    api = configured_api()
    for _ in range(12):
        run_cognitive_turn(api, signals=flow_signals())
    snapshot = api.snapshot()
    left = GhostAPI.from_snapshot(copy.deepcopy(snapshot))
    right = GhostAPI.from_snapshot(copy.deepcopy(snapshot))
    outputs_left = []
    outputs_right = []
    for event, action, signals in [
        ("help", "help", neutral_signals()),
        ("betrayal", "report", {"novelty": 0.3}),
        ("threat", "threaten", {"threat": 1.0}),
        ("apology", "help", flow_signals()),
    ]:
        outputs_left.append(run_cognitive_turn(left, emotion_event=event, action=action, signals=signals))
        outputs_right.append(run_cognitive_turn(right, emotion_event=event, action=action, signals=signals))
    assert outputs_left == outputs_right
    assert left.snapshot() == right.snapshot()


def test_in_place_restore_replays_same_next_cognitive_turn():
    api = configured_api()
    for _ in range(5):
        run_cognitive_turn(api, signals=flow_signals())
    snapshot = copy.deepcopy(api.snapshot())
    expected = run_cognitive_turn(GhostAPI.from_snapshot(copy.deepcopy(snapshot)), emotion_event="help", action="help")
    api.restore_snapshot(snapshot)
    actual = run_cognitive_turn(api, emotion_event="help", action="help")
    assert actual == expected


@pytest.mark.parametrize("bad_signals", [[], "bad", 1, True, {"unknown": 1.0}, {"threat": 2.0}, {"novelty": -0.1}, {"task_focus": float("inf")}, {"stability": float("nan")}])
def test_invalid_signals_do_not_mutate_existing_attention_or_sources(bad_signals):
    api = configured_api()
    api.advance_attention_from_state("sera")
    before_snapshot = copy.deepcopy(api.snapshot())
    with pytest.raises(ValueError):
        api.advance_attention_from_state("sera", signals=bad_signals)
    assert api.snapshot() == before_snapshot


@pytest.mark.parametrize("bad_signals", [[], "bad", 1, True, {"unknown": 1.0}, {"threat": 2.0}, {"novelty": -0.1}, {"task_focus": float("inf")}, {"stability": float("nan")}])
def test_invalid_signals_do_not_implicitly_register_attention_agent(bad_signals):
    api = configured_api()
    api.attention = type(api.attention)()
    before_sources = source_states(api)
    with pytest.raises(ValueError):
        api.advance_attention_from_state("sera", signals=bad_signals)
    assert api.attention_state("sera") is None
    assert_sources_unchanged(api, before_sources)


@pytest.mark.parametrize("bad_provenance", [[], (), "bad", 1, True])
def test_invalid_caller_provenance_is_fully_nonmutating(bad_provenance):
    api = configured_api()
    before = copy.deepcopy(api.snapshot())
    with pytest.raises(ValueError):
        api.advance_attention_from_state("sera", provenance=bad_provenance)
    assert api.snapshot() == before


@pytest.mark.parametrize("flag_name", ["include_emotions", "include_interpretations"])
@pytest.mark.parametrize("bad_flag", [None, 0, 1, "yes", [], {}])
def test_invalid_source_filters_are_nonmutating(flag_name, bad_flag):
    api = configured_api()
    before = copy.deepcopy(api.snapshot())
    with pytest.raises(ValueError):
        api.advance_attention_from_state("sera", **{flag_name: bad_flag})
    assert api.snapshot() == before


@pytest.mark.parametrize("bad_source", ["", "   ", 1, True, [], {}])
def test_direct_attention_invalid_source_does_not_register_agent(bad_source):
    api = GhostAPI()
    with pytest.raises(ValueError):
        api.advance_attention("new-agent", salience={"x": 0.5}, source=bad_source)
    assert api.attention_state("new-agent") is None


@pytest.mark.parametrize("bad_salience", [[], "bad", 1, True, {"x": -0.1}, {"x": 1.1}, {"x": float("inf")}, {"x": float("nan")}])
def test_direct_attention_invalid_salience_does_not_register_agent(bad_salience):
    api = GhostAPI()
    with pytest.raises(ValueError):
        api.advance_attention("new-agent", salience=bad_salience)
    assert api.attention_state("new-agent") is None


@pytest.mark.parametrize("bad_provenance", [[], (), "bad", 1, True, {"bad": float("nan")}])
def test_direct_attention_invalid_provenance_does_not_register_agent(bad_provenance):
    api = GhostAPI()
    with pytest.raises(ValueError):
        api.advance_attention("new-agent", salience={"x": 0.5}, provenance=bad_provenance)
    assert api.attention_state("new-agent") is None


@pytest.mark.parametrize(
    "emotion_event,action,signals",
    [
        ("betrayal", "report", flow_signals()),
        ("betrayal", "report", {"novelty": 1.0}),
        ("help", "help", neutral_signals()),
        ("help", "report", {"contradiction": 0.8}),
        ("threat", "threaten", {"threat": 1.0}),
        ("apology", "help", {"interpretation_impulse": 0.9}),
        ("insult", "report", {"novelty": 0.4, "threat": 0.4}),
        ("help", "threaten", {"task_focus": 0.9, "repetition": 0.9}),
    ],
)
def test_same_start_same_ordered_cognitive_turn_is_deterministic(emotion_event, action, signals):
    left = configured_api()
    right = configured_api()
    assert run_cognitive_turn(left, emotion_event=emotion_event, action=action, signals=signals) == run_cognitive_turn(right, emotion_event=emotion_event, action=action, signals=signals)


@pytest.mark.parametrize("prefix_length", [0, 1, 2, 3, 5, 8, 13, 21])
def test_snapshot_fork_determinism_at_multiple_prefix_lengths(prefix_length):
    api = configured_api()
    for index in range(prefix_length):
        run_cognitive_turn(
            api,
            emotion_event="betrayal" if index % 2 else "help",
            action="report" if index % 3 else "help",
            signals=flow_signals() if index % 2 else neutral_signals(),
        )
    snapshot = api.snapshot()
    left = GhostAPI.from_snapshot(copy.deepcopy(snapshot))
    right = GhostAPI.from_snapshot(copy.deepcopy(snapshot))
    a = run_cognitive_turn(left, emotion_event="threat", action="threaten", signals={"threat": 1.0})
    b = run_cognitive_turn(right, emotion_event="threat", action="threaten", signals={"threat": 1.0})
    assert a == b
    assert left.snapshot() == right.snapshot()


@pytest.mark.parametrize("agent_count", [1, 2, 8, 16, 32, 64, 128])
def test_multi_agent_cognitive_isolation(agent_count):
    api = GhostAPI()
    for index in range(agent_count):
        agent = f"npc-{index:03d}"
        api.register_emotional_agent(agent, initial={"anger": (index % 5) / 10.0})
        api.register_interpretation_agent(
            agent,
            initial={"betrayal": (index % 7) / 10.0},
            rules={"action:report": {"betrayal": 0.2}},
        )
    before_zero = api.persistent_salience("npc-000")
    target = f"npc-{agent_count - 1:03d}"
    api.apply_emotional_event(target, "betrayal")
    api.evaluate_action_meaning(target, "report")
    api.advance_attention_from_state(target, signals=flow_signals())
    if agent_count > 1:
        assert api.persistent_salience("npc-000") == before_zero
    else:
        assert api.persistent_salience(target)["source_count"] == 2


@pytest.mark.parametrize("steps", [1, 10, 50, 100, 250, 500])
def test_long_combined_sequences_remain_json_safe_and_bounded(steps):
    api = configured_api()
    for index in range(steps):
        event = ("help", "betrayal", "threat", "apology")[index % 4]
        action = ("help", "report", "threaten")[index % 3]
        signals = flow_signals() if index % 5 else {"novelty": 0.8}
        run_cognitive_turn(api, emotion_event=event, action=action, signals=signals)
    packet = api.advance_attention_from_state("sera")
    assert 0.0 <= packet["attention"]["flow_pressure_after"] <= 1.0
    assert 0.0 <= packet["attention"]["attention_gain"] <= 1.0
    assert json.loads(json.dumps(api.snapshot(), allow_nan=False)) == api.snapshot()


@pytest.mark.parametrize("interpretation_name", ["anger", "fear", "emotion:anger", "emotion:fear", "interpretation:anger", "source", "agent", "flow_pressure"])
def test_namespacing_prevents_cross_layer_dimension_collisions(interpretation_name):
    api = GhostAPI()
    api.register_emotional_agent("sera", initial={"anger": 0.5})
    api.register_interpretation_agent("sera", initial={interpretation_name: 0.7})
    packet = api.persistent_salience("sera")
    assert "emotion:anger" in packet["salience"]
    assert f"interpretation:{interpretation_name}" in packet["salience"]
    assert len(packet["salience"]) == len(set(packet["salience"]))


@pytest.mark.parametrize("caller_value", [0, 1, "market", ["guard"], {"nested": [1, 2]}, False])
def test_valid_caller_provenance_is_deep_copied(caller_value):
    api = configured_api()
    provenance = {"value": copy.deepcopy(caller_value)}
    packet = api.advance_attention_from_state("sera", provenance=provenance)
    provenance["value"] = "mutated"
    assert packet["attention"]["provenance"]["caller"]["value"] == caller_value


@pytest.mark.parametrize("event", ["help", "insult", "threat", "betrayal", "apology"])
def test_emotion_only_update_changes_or_preserves_bridge_without_touching_interpretation_revision(event):
    api = configured_api()
    before = api.persistent_salience("sera")
    api.apply_emotional_event("sera", event)
    after = api.persistent_salience("sera")
    assert after["sources"]["emotion"]["revision"] > before["sources"]["emotion"]["revision"]
    assert after["sources"]["interpretation"]["revision"] == before["sources"]["interpretation"]["revision"]


@pytest.mark.parametrize("action", ["report", "help", "threaten", "unknown-action"])
def test_interpretation_only_update_does_not_touch_emotion_revision(action):
    api = configured_api()
    before = api.persistent_salience("sera")
    api.evaluate_action_meaning("sera", action)
    after = api.persistent_salience("sera")
    assert after["sources"]["interpretation"]["revision"] > before["sources"]["interpretation"]["revision"]
    assert after["sources"]["emotion"]["revision"] == before["sources"]["emotion"]["revision"]


def test_different_order_can_produce_history_distinct_state_while_each_order_replays_exactly():
    def run(order):
        api = configured_api()
        outputs = []
        for event, action in order:
            outputs.append(run_cognitive_turn(api, emotion_event=event, action=action, signals=neutral_signals()))
        return outputs, api.snapshot()

    order_a = [("betrayal", "report"), ("help", "help"), ("threat", "threaten")]
    order_b = list(reversed(order_a))
    a1, sa1 = run(order_a)
    a2, sa2 = run(order_a)
    b1, sb1 = run(order_b)
    b2, sb2 = run(order_b)
    assert a1 == a2 and sa1 == sa2
    assert b1 == b2 and sb1 == sb2
    assert sa1 != sb1


def test_failed_attention_step_leaves_global_attention_sequence_unchanged():
    api = configured_api()
    before = copy.deepcopy(api.snapshot())
    with pytest.raises(ValueError):
        api.advance_attention_from_state("sera", signals={"threat": 9.0})
    after = api.snapshot()
    assert after == before


def test_failed_direct_attention_step_leaves_runtime_completely_empty():
    api = GhostAPI()
    with pytest.raises(ValueError):
        api.advance_attention("sera", signals={"unknown": 1.0}, salience={"x": 0.5})
    assert api.attention_state("sera") is None
    assert "attention" not in api.snapshot()


def test_valid_direct_attention_still_implicitly_registers_after_validation_hardening():
    api = GhostAPI()
    packet = api.advance_attention("sera", signals=neutral_signals(), salience={"host": 0.5})
    assert packet["agent"] == "sera"
    assert api.attention_state("sera") is not None


def test_source_packets_remain_independent_of_attention_snapshot_history():
    api = configured_api()
    for _ in range(20):
        api.advance_attention_from_state("sera", signals=flow_signals())
    before = source_states(api)
    snapshot = api.snapshot()
    snapshot["attention"]["agents"]["sera"]["history"][-1]["underlying_salience"]["emotion:anger"] = 0.0
    assert_sources_unchanged(api, before)


def test_bridge_recomputed_after_restore_not_cached_from_pre_restore_packet():
    api = configured_api()
    old_bridge = api.persistent_salience("sera")
    snapshot = api.snapshot()
    api.apply_emotional_event("sera", "betrayal")
    changed = api.persistent_salience("sera")
    api.restore_snapshot(snapshot)
    restored = api.persistent_salience("sera")
    assert changed != old_bridge
    assert restored == old_bridge


def test_combined_state_contains_no_salience_bridge_snapshot_layer_after_many_steps():
    api = configured_api()
    for _ in range(30):
        run_cognitive_turn(api, signals=flow_signals())
    snapshot = api.snapshot()
    assert "salience_bridge" not in snapshot
    assert "emotions" in snapshot and "interpretations" in snapshot and "attention" in snapshot
