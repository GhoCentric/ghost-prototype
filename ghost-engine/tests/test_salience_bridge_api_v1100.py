from __future__ import annotations

import copy
import json

import pytest

from ghost import GhostAPI


def configured_api() -> GhostAPI:
    api = GhostAPI()
    api.register_emotional_agent(
        "sera",
        initial={"anger": 0.72, "fear": 0.31},
        salience_bias={"anger": 1.0, "fear": 1.2},
    )
    api.register_interpretation_agent(
        "sera",
        initial={"betrayal": 0.81, "cooperation": 0.16},
        rules={"action:report": {"betrayal": 0.5}},
    )
    return api


def focused_signals():
    return {"task_focus": 1.0, "repetition": 1.0, "stability": 1.0}


def test_api_persistent_salience_reads_both_sources():
    api = configured_api()
    packet = api.persistent_salience("sera")
    assert packet["source_count"] == 2
    assert packet["salience"]["emotion:anger"] == 0.72
    assert packet["salience"]["interpretation:betrayal"] == 0.81


def test_api_emotion_only_filter_is_explicit():
    api = configured_api()
    packet = api.persistent_salience("sera", include_interpretations=False)
    assert packet["source_count"] == 1
    assert all(name.startswith("emotion:") for name in packet["salience"])


def test_api_interpretation_only_filter_is_explicit():
    api = configured_api()
    packet = api.persistent_salience("sera", include_emotions=False)
    assert packet["source_count"] == 1
    assert all(name.startswith("interpretation:") for name in packet["salience"])


def test_api_no_registered_sources_returns_empty_salience_without_creating_them():
    api = GhostAPI()
    packet = api.persistent_salience("nobody")
    assert packet["salience"] == {}
    assert api.emotional_state("nobody") is None
    assert api.interpretation_state("nobody") is None


def test_persistent_salience_does_not_create_attention_state():
    api = configured_api()
    assert api.attention_state("sera") is None
    api.persistent_salience("sera")
    assert api.attention_state("sera") is None


def test_persistent_salience_cannot_mutate_emotion_source():
    api = configured_api()
    before = api.emotional_state("sera")
    packet = api.persistent_salience("sera")
    packet["salience"]["emotion:anger"] = 0.0
    assert api.emotional_state("sera") == before


def test_persistent_salience_cannot_mutate_interpretation_source():
    api = configured_api()
    before = api.interpretation_state("sera")
    packet = api.persistent_salience("sera")
    packet["salience"]["interpretation:betrayal"] = 0.0
    assert api.interpretation_state("sera") == before


def test_advance_from_state_hands_exact_bridge_vector_to_attention():
    api = configured_api()
    packet = api.advance_attention_from_state("sera")
    assert packet["attention"]["underlying_salience"] == packet["bridge"]["salience"]


def test_advance_from_state_uses_explicit_bridge_source_label():
    api = configured_api()
    packet = api.advance_attention_from_state("sera")
    assert packet["attention"]["source"] == "ghost:salience_bridge"


def test_advance_from_state_records_bridge_source_revisions():
    api = configured_api()
    api.apply_emotional_event("sera", "betrayal")
    api.evaluate_action_meaning("sera", "report")
    packet = api.advance_attention_from_state("sera")
    source_meta = packet["attention"]["provenance"]["salience_bridge"]["sources"]
    assert source_meta["emotion"]["revision"] > 0
    assert source_meta["interpretation"]["revision"] > 0


def test_caller_provenance_is_copied_into_attention_record():
    api = configured_api()
    provenance = {"scene": "market", "witnesses": ["guard"]}
    packet = api.advance_attention_from_state("sera", provenance=provenance)
    provenance["witnesses"].append("corrupt")
    assert packet["attention"]["provenance"]["caller"] == {
        "scene": "market",
        "witnesses": ["guard"],
    }


def test_non_dict_caller_provenance_is_rejected():
    api = configured_api()
    with pytest.raises(ValueError):
        api.advance_attention_from_state("sera", provenance=[])
    assert True


def test_attention_compresses_bridged_salience_without_source_mutation():
    api = configured_api()
    api.register_attention_agent(
        "sera",
        initial_flow_pressure=0.9,
        flow_active=True,
    )
    emotional_before = api.emotional_state("sera")
    interpretation_before = api.interpretation_state("sera")
    packet = api.advance_attention_from_state("sera", signals=focused_signals())
    record = packet["attention"]
    assert record["flow_active_after"] is True
    assert record["attention_gain"] < 1.0
    assert record["attended_salience"]["emotion:anger"] < record["underlying_salience"]["emotion:anger"]
    assert api.emotional_state("sera") == emotional_before
    assert api.interpretation_state("sera") == interpretation_before


def test_breakthrough_restores_full_bridged_access_without_rebuilding_source():
    api = configured_api()
    api.register_attention_agent(
        "sera",
        initial_flow_pressure=0.9,
        flow_active=True,
    )
    before = api.emotional_state("sera")
    packet = api.advance_attention_from_state("sera", signals={"threat": 1.0})
    record = packet["attention"]
    assert record["breakthrough"] is True
    assert record["attention_gain"] == 1.0
    assert record["attended_salience"] == record["underlying_salience"]
    assert api.emotional_state("sera") == before


def test_emotion_change_is_visible_on_next_bridge_read():
    api = configured_api()
    before = api.persistent_salience("sera")["salience"]["emotion:anger"]
    api.apply_emotional_event("sera", "betrayal")
    after = api.persistent_salience("sera")["salience"]["emotion:anger"]
    assert after > before


def test_interpretation_change_is_visible_on_next_bridge_read():
    api = configured_api()
    before = api.persistent_salience("sera")["salience"]["interpretation:betrayal"]
    api.evaluate_action_meaning("sera", "report")
    after = api.persistent_salience("sera")["salience"]["interpretation:betrayal"]
    assert after > before


def test_bridge_read_itself_does_not_change_source_revision():
    api = configured_api()
    api.apply_emotional_event("sera", "betrayal")
    first = api.persistent_salience("sera")
    second = api.persistent_salience("sera")
    assert first["sources"]["emotion"]["revision"] == second["sources"]["emotion"]["revision"]


def test_attention_advance_does_not_change_source_revision():
    api = configured_api()
    api.apply_emotional_event("sera", "betrayal")
    before = api.persistent_salience("sera")
    api.advance_attention_from_state("sera")
    after = api.persistent_salience("sera")
    assert before["sources"] == after["sources"]


def test_host_supplied_attention_path_remains_independent():
    api = GhostAPI()
    packet = api.advance_attention(
        "host-agent",
        salience={"custom": 0.66},
        source="host",
    )
    assert packet["underlying_salience"] == {"custom": 0.66}
    assert packet["source"] == "host"


def test_interpretation_runtime_remains_independent_of_attention():
    api = GhostAPI()
    api.register_interpretation_agent(
        "sera",
        initial={"betrayal": 0.2},
        rules={"action:report": {"betrayal": 1.0}},
    )
    packet = api.evaluate_action_meaning("sera", "report")
    assert packet["state"]["levels"]["betrayal"] > 0.2
    assert api.attention_state("sera") is None


def test_emotion_runtime_remains_independent_of_attention():
    api = GhostAPI()
    packet = api.apply_emotional_event("sera", "betrayal")
    assert packet["state"]["levels"]["anger"] > 0.0
    assert api.attention_state("sera") is None


def test_bridge_packet_and_attention_record_are_json_safe():
    api = configured_api()
    packet = api.advance_attention_from_state("sera", provenance={"turn": 1})
    assert json.loads(json.dumps(packet, allow_nan=False)) == packet


def test_advance_from_state_output_cannot_alias_attention_history():
    api = configured_api()
    packet = api.advance_attention_from_state("sera")
    packet["attention"]["underlying_salience"]["emotion:anger"] = 0.0
    state = api.attention_state("sera")
    assert state["history"][-1]["underlying_salience"]["emotion:anger"] == 0.72


def test_snapshot_restore_replays_same_bridge_attention_step():
    api = configured_api()
    for _ in range(4):
        api.advance_attention_from_state("sera", signals=focused_signals())
    snapshot = api.snapshot()
    left = GhostAPI.from_snapshot(copy.deepcopy(snapshot))
    right = GhostAPI.from_snapshot(copy.deepcopy(snapshot))
    a = left.advance_attention_from_state("sera", signals={"novelty": 0.2})
    b = right.advance_attention_from_state("sera", signals={"novelty": 0.2})
    assert a == b
    assert left.snapshot() == right.snapshot()


def test_snapshot_restore_preserves_source_revisions_used_by_bridge():
    api = configured_api()
    api.apply_emotional_event("sera", "betrayal")
    api.evaluate_action_meaning("sera", "report")
    before = api.persistent_salience("sera")
    restored = GhostAPI.from_snapshot(api.snapshot())
    after = restored.persistent_salience("sera")
    assert after["sources"] == before["sources"]
    assert after["salience"] == before["salience"]


def test_attention_only_snapshot_does_not_require_bridge_state():
    api = GhostAPI()
    api.advance_attention("sera", salience={"host": 0.4})
    snapshot = api.snapshot()
    assert "attention" in snapshot
    assert "salience_bridge" not in snapshot


def test_bridge_is_stateless_and_adds_no_top_level_snapshot_key():
    api = configured_api()
    api.persistent_salience("sera")
    snapshot = api.snapshot()
    assert "salience_bridge" not in snapshot


def test_filtered_advance_uses_only_emotion_dimensions():
    api = configured_api()
    packet = api.advance_attention_from_state(
        "sera",
        include_interpretations=False,
    )
    assert all(
        name.startswith("emotion:")
        for name in packet["attention"]["underlying_salience"]
    )


def test_filtered_advance_uses_only_interpretation_dimensions():
    api = configured_api()
    packet = api.advance_attention_from_state(
        "sera",
        include_emotions=False,
    )
    assert all(
        name.startswith("interpretation:")
        for name in packet["attention"]["underlying_salience"]
    )


def test_filtered_advance_with_no_sources_still_advances_flow_signals():
    api = configured_api()
    packet = api.advance_attention_from_state(
        "sera",
        signals=focused_signals(),
        include_emotions=False,
        include_interpretations=False,
    )
    assert packet["bridge"]["salience"] == {}
    assert packet["attention"]["flow_pressure_after"] > 0.0


@pytest.mark.parametrize("flag_name", ["include_emotions", "include_interpretations"])
@pytest.mark.parametrize("bad", [0, 1, None, "yes"])
def test_api_bridge_filters_reject_non_bool_values(flag_name, bad):
    api = configured_api()
    kwargs = {flag_name: bad}
    with pytest.raises(ValueError):
        api.persistent_salience("sera", **kwargs)
    assert True


def test_bridge_source_revisions_are_a_coherent_pre_attention_view():
    api = configured_api()
    api.apply_emotional_event("sera", "betrayal")
    api.evaluate_action_meaning("sera", "report")
    before = api.persistent_salience("sera")
    packet = api.advance_attention_from_state("sera")
    assert packet["bridge"]["sources"] == before["sources"]
    assert packet["attention"]["provenance"]["salience_bridge"]["sources"] == before["sources"]


def test_two_snapshot_forks_keep_bridge_output_deterministic_after_source_updates():
    api = configured_api()
    snapshot = api.snapshot()
    left = GhostAPI.from_snapshot(copy.deepcopy(snapshot))
    right = GhostAPI.from_snapshot(copy.deepcopy(snapshot))
    for runtime in (left, right):
        runtime.apply_emotional_event("sera", "betrayal")
        runtime.evaluate_action_meaning("sera", "report")
    assert left.persistent_salience("sera") == right.persistent_salience("sera")


def test_attention_gain_scales_all_namespaced_dimensions_uniformly():
    api = configured_api()
    api.register_attention_agent("sera", initial_flow_pressure=0.9, flow_active=True)
    record = api.advance_attention_from_state("sera", signals=focused_signals())["attention"]
    gain = record["attention_gain"]
    for name, underlying in record["underlying_salience"].items():
        assert record["attended_salience"][name] == pytest.approx(underlying * gain)


def test_bridge_does_not_choose_action_or_dialogue_fields():
    api = configured_api()
    packet = api.advance_attention_from_state("sera")
    serialized = json.dumps(packet, sort_keys=True)
    assert '"action"' not in serialized
    assert '"dialogue"' not in serialized
