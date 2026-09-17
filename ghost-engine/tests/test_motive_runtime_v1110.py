from copy import deepcopy
import json
import math

import pytest

from ghost.motives import (
    MOTIVE_SIGNAL_PACKET_VERSION,
    MOTIVE_SNAPSHOT_SCHEMA_VERSION,
    MotiveRuntime,
    build_motive_signal_packet,
)


def base_agent():
    return {
        "agent_id": "sera",
        "role": "guard",
        "traits": {"cautious": 0.7},
        "values": {"protect_town": 0.9, "personal_safety": 0.5},
        "goals": ["maintain_post", "verify_report"],
        "goal_states": {
            "maintain_post": {
                "goal_id": "maintain_post",
                "status": "active",
                "priority": 0.8,
                "progress": 0.25,
            },
            "verify_report": {
                "goal_id": "verify_report",
                "status": "inactive",
                "priority": 0.7,
                "progress": 0.0,
            },
        },
        "capabilities": [],
        "metadata": {},
    }


def bridge(agent="sera"):
    return {
        "packet_version": "1.0",
        "agent": agent,
        "source_count": 2,
        "sources": {},
        "salience": {
            "emotion:anger": 0.8,
            "interpretation:betrayal": 0.6,
        },
    }


def attention(agent="sera", with_history=True):
    history = []
    if with_history:
        history = [{
            "sequence": 3,
            "agent": agent,
            "attended_salience": {
                "emotion:anger": 0.4,
                "interpretation:betrayal": 0.3,
            },
        }]
    return {
        "agent": agent,
        "flow_pressure": 0.5,
        "flow_active": True,
        "flow_depth": 0.25,
        "attention_gain": 0.5,
        "history": history,
    }


def packet(**kwargs):
    return build_motive_signal_packet(
        "sera",
        agent_state=kwargs.get("agent_state", base_agent()),
        persistent_salience=kwargs.get("persistent_salience", bridge()),
        attention_state=kwargs.get("attention_state", attention()),
    )


def assert_json_safe(value):
    json.dumps(value, allow_nan=False, sort_keys=True)


def test_signal_packet_combines_agent_goal_persistent_and_attended_state():
    result = packet()
    assert result["packet_version"] == MOTIVE_SIGNAL_PACKET_VERSION
    assert result["agent"] == "sera"
    signals = result["signals"]
    assert signals["trait:cautious"] == 0.7
    assert signals["value:protect_town"] == 0.9
    assert signals["goal:maintain_post:priority"] == 0.8
    assert signals["goal:maintain_post:progress"] == 0.25
    assert signals["goal:maintain_post:priority_remaining"] == pytest.approx(0.6)
    assert signals["goal:maintain_post:status:active"] == 1.0
    assert signals["goal:maintain_post:status:blocked"] == 0.0
    assert signals["goal:verify_report:priority_remaining"] == 0.0
    assert signals["persistent:emotion:anger"] == 0.8
    assert signals["persistent:interpretation:betrayal"] == 0.6
    assert signals["attention:flow_pressure"] == 0.5
    assert signals["attention:flow_active"] == 1.0
    assert signals["attended:emotion:anger"] == 0.4
    assert result["sources"]["attention"]["revision"] == 3
    assert_json_safe(result)


def test_signal_packet_without_optional_cognitive_sources_is_valid():
    result = build_motive_signal_packet(
        "sera",
        agent_state=base_agent(),
        persistent_salience=None,
        attention_state=None,
    )
    assert result["sources"]["persistent_salience"] == {
        "present": False, "count": 0, "source_count": 0,
    }
    assert result["sources"]["attention"] == {
        "present": False, "count": 0, "attended_count": 0, "revision": None,
    }
    assert not any(name.startswith("persistent:") for name in result["signals"])


def test_attention_without_history_exposes_flow_but_no_attended_salience():
    result = build_motive_signal_packet(
        "sera", agent_state=base_agent(), persistent_salience=bridge(),
        attention_state=attention(with_history=False),
    )
    assert result["sources"]["attention"]["revision"] is None
    assert result["sources"]["attention"]["attended_count"] == 0
    assert "attended:emotion:anger" not in result["signals"]


@pytest.mark.parametrize("status", ["active", "blocked", "inactive", "satisfied", "abandoned"])
def test_goal_status_signal_and_remaining_priority(status):
    state = base_agent()
    state["goal_states"] = {
        "g": {"goal_id": "g", "status": status, "priority": 0.8, "progress": 0.25},
    }
    result = build_motive_signal_packet("sera", agent_state=state)
    expected = 0.6 if status in {"active", "blocked"} else 0.0
    assert result["signals"]["goal:g:priority_remaining"] == pytest.approx(expected)
    for possible in ("inactive", "active", "blocked", "satisfied", "abandoned"):
        assert result["signals"][f"goal:g:status:{possible}"] == (1.0 if status == possible else 0.0)


def test_runtime_configuration_evaluation_ranking_and_missing_signal_diagnostics():
    runtime = MotiveRuntime(history_limit=2)
    runtime.configure(
        "sera", "protect", baseline=0.1,
        weights={
            "value:protect_town": 0.5,
            "goal:maintain_post:priority_remaining": 0.5,
            "persistent:emotion:anger": 0.2,
            "missing:signal": 0.4,
        },
    )
    runtime.configure(
        "sera", "withdraw", baseline=0.4,
        weights={"value:personal_safety": 0.2, "persistent:emotion:anger": -0.5},
    )
    result = runtime.evaluate("sera", packet())
    assert result["ranking"] == ["protect", "withdraw"]
    assert result["dominant_motive"] == "protect"
    assert result["dominant_score"] == 1.0
    protect = result["motives"]["protect"]
    assert protect["missing_signals"] == ["missing:signal"]
    assert protect["score"] == 1.0
    assert protect["raw_score"] > 1.0
    withdraw = result["motives"]["withdraw"]
    assert withdraw["opposition"] > 0.0
    assert withdraw["support"] > 0.0
    assert_json_safe(result)


def test_negative_pressure_clamps_at_zero_and_tie_break_is_stable():
    runtime = MotiveRuntime()
    runtime.configure("sera", "zeta", baseline=0.2, weights={"persistent:emotion:anger": -1.0})
    runtime.configure("sera", "alpha", baseline=0.0, weights={})
    result = runtime.evaluate("sera", packet())
    assert result["motives"]["zeta"]["score"] == 0.0
    assert result["motives"]["alpha"]["score"] == 0.0
    assert result["ranking"] == ["alpha", "zeta"]
    assert result["dominant_motive"] == "alpha"


def test_evaluate_with_no_profiles_returns_auditable_empty_field():
    runtime = MotiveRuntime()
    result = runtime.evaluate("sera", packet())
    assert result["motives"] == {}
    assert result["ranking"] == []
    assert result["dominant_motive"] is None
    assert result["dominant_score"] is None
    assert runtime.current("sera") == result


def test_history_limit_current_and_zero_limit():
    runtime = MotiveRuntime(history_limit=2)
    runtime.configure("sera", "protect", baseline=0.1)
    first = runtime.evaluate("sera", packet())
    second = runtime.evaluate("sera", packet())
    third = runtime.evaluate("sera", packet())
    assert [r["sequence"] for r in runtime.history("sera")] == [2, 3]
    assert runtime.current("sera") == third
    assert runtime.history("sera", limit=1) == [third]
    assert runtime.history("sera", limit=0) == []
    assert first["sequence"] == 1 and second["sequence"] == 2


def test_configure_replaces_profile_and_remove_is_explicit():
    runtime = MotiveRuntime()
    assert runtime.has_state() is False
    p1 = runtime.configure("sera", "protect", baseline=0.1)
    p2 = runtime.configure("sera", "protect", baseline=0.2, weights={"value:protect_town": 0.5})
    assert p1 != p2
    assert runtime.profiles("sera")["protect"] == p2
    leaked = runtime.profiles("sera")
    leaked["protect"]["baseline"] = 1.0
    assert runtime.profiles("sera")["protect"]["baseline"] == 0.2
    assert runtime.remove("sera", "missing") is False
    assert runtime.remove("nobody", "protect") is False
    assert runtime.remove("sera", "protect") is True
    assert runtime.profiles("sera") == {}
    assert runtime.agent_ids() == []


def test_snapshot_roundtrip_and_deterministic_continuation():
    runtime = MotiveRuntime(history_limit=3)
    runtime.configure("sera", "protect", baseline=0.1, weights={"value:protect_town": 0.5})
    runtime.evaluate("sera", packet())
    snap = runtime.snapshot()
    assert snap["schema_version"] == MOTIVE_SNAPSHOT_SCHEMA_VERSION
    restored = MotiveRuntime.from_snapshot(deepcopy(snap))
    assert restored.snapshot() == snap
    assert restored.evaluate("sera", packet()) == runtime.evaluate("sera", packet())



def test_snapshot_roundtrip_is_exact_for_multi_term_float_accumulation():
    runtime = MotiveRuntime()
    runtime.configure(
        "sera",
        "protect",
        baseline=0.05,
        weights={
            "value:protect_town": 0.45,
            "goal:maintain_post:priority_remaining": 0.50,
        },
    )
    result = runtime.evaluate("sera", packet())
    assert result["motives"]["protect"]["raw_score"] > 0.0
    snap = runtime.snapshot()
    restored = MotiveRuntime.from_snapshot(deepcopy(snap))
    assert restored.snapshot() == snap


def test_history_can_exist_after_profiles_are_removed_and_agent_ids_are_union():
    runtime = MotiveRuntime()
    runtime.configure("sera", "protect")
    runtime.evaluate("sera", packet())
    runtime.remove("sera", "protect")
    runtime.configure("rowan", "investigate")
    assert runtime.agent_ids() == ["rowan", "sera"]


@pytest.mark.parametrize("bad", [0, -1, True, 1.2, "2"])
def test_constructor_rejects_bad_history_limit(bad):
    with pytest.raises(ValueError):
        MotiveRuntime(history_limit=bad)


@pytest.mark.parametrize("bad", [True, "x", None, float("nan"), float("inf")])
def test_profile_baseline_rejects_non_unit_numbers(bad):
    runtime = MotiveRuntime()
    with pytest.raises(ValueError):
        runtime.configure("sera", "protect", baseline=bad)


@pytest.mark.parametrize("bad", [-1.1, 1.1, float("nan"), True, "x"])
def test_weight_rejects_out_of_range_or_non_numeric_values(bad):
    runtime = MotiveRuntime()
    with pytest.raises(ValueError):
        runtime.configure("sera", "protect", weights={"x": bad})


def test_weight_validation_rejects_wrong_container_blank_signal_and_duplicate_normalized_signal():
    runtime = MotiveRuntime()
    with pytest.raises(ValueError):
        runtime.configure("sera", "protect", weights=[])
    with pytest.raises(ValueError):
        runtime.configure("sera", "protect", weights={"   ": 0.2})
    with pytest.raises(ValueError):
        runtime.configure("sera", "protect", weights={"x": 0.2, " x ": 0.3})


@pytest.mark.parametrize("bad_limit", [True, -1, 1.2, "x"])
def test_history_rejects_bad_limit(bad_limit):
    runtime = MotiveRuntime()
    with pytest.raises(ValueError):
        runtime.history("sera", limit=bad_limit)


def test_signal_builder_rejects_invalid_agent_state_shapes():
    with pytest.raises(ValueError):
        build_motive_signal_packet("sera", agent_state=[])
    bad = base_agent(); bad["agent_id"] = "rowan"
    with pytest.raises(ValueError):
        build_motive_signal_packet("sera", agent_state=bad)
    for key in ("traits", "values", "goal_states"):
        bad = base_agent(); del bad[key]
        with pytest.raises(ValueError):
            build_motive_signal_packet("sera", agent_state=bad)
    bad = base_agent(); bad["traits"] = []
    with pytest.raises(ValueError):
        build_motive_signal_packet("sera", agent_state=bad)
    bad = base_agent(); bad["values"] = []
    with pytest.raises(ValueError):
        build_motive_signal_packet("sera", agent_state=bad)
    bad = base_agent(); bad["goal_states"] = []
    with pytest.raises(ValueError):
        build_motive_signal_packet("sera", agent_state=bad)


def test_signal_builder_rejects_bad_channels_and_goals():
    bad = base_agent(); bad["traits"] = {"x": 2.0}
    with pytest.raises(ValueError):
        build_motive_signal_packet("sera", agent_state=bad)
    bad = base_agent(); bad["goal_states"] = {"g": []}
    with pytest.raises(ValueError):
        build_motive_signal_packet("sera", agent_state=bad)
    bad = base_agent(); bad["goal_states"] = {"g": {"goal_id":"other","status":"active","priority":.5,"progress":.2}}
    with pytest.raises(ValueError):
        build_motive_signal_packet("sera", agent_state=bad)
    bad = base_agent(); bad["goal_states"] = {"g": {"goal_id":"g","status":"weird","priority":.5,"progress":.2}}
    with pytest.raises(ValueError):
        build_motive_signal_packet("sera", agent_state=bad)
    for field in ("priority", "progress"):
        bad = base_agent(); bad["goal_states"] = {"g": {"goal_id":"g","status":"active","priority":.5,"progress":.2}}
        bad["goal_states"]["g"][field] = 2.0
        with pytest.raises(ValueError):
            build_motive_signal_packet("sera", agent_state=bad)


def test_signal_builder_rejects_invalid_persistent_packet():
    with pytest.raises(ValueError):
        build_motive_signal_packet("sera", agent_state=base_agent(), persistent_salience=[])
    bad = bridge("rowan")
    with pytest.raises(ValueError):
        build_motive_signal_packet("sera", agent_state=base_agent(), persistent_salience=bad)
    bad = bridge(); bad["salience"] = []
    with pytest.raises(ValueError):
        build_motive_signal_packet("sera", agent_state=base_agent(), persistent_salience=bad)
    bad = bridge(); bad["source_count"] = True
    with pytest.raises(ValueError):
        build_motive_signal_packet("sera", agent_state=base_agent(), persistent_salience=bad)
    bad = bridge(); bad["salience"] = {" ": .3}
    with pytest.raises(ValueError):
        build_motive_signal_packet("sera", agent_state=base_agent(), persistent_salience=bad)


def test_signal_builder_rejects_invalid_attention_packet():
    with pytest.raises(ValueError):
        build_motive_signal_packet("sera", agent_state=base_agent(), attention_state=[])
    bad = attention("rowan")
    with pytest.raises(ValueError):
        build_motive_signal_packet("sera", agent_state=base_agent(), attention_state=bad)
    for field in ("flow_pressure", "flow_depth", "attention_gain"):
        bad = attention(); bad[field] = 2.0
        with pytest.raises(ValueError):
            build_motive_signal_packet("sera", agent_state=base_agent(), attention_state=bad)
    bad = attention(); bad["flow_active"] = 1
    with pytest.raises(ValueError):
        build_motive_signal_packet("sera", agent_state=base_agent(), attention_state=bad)
    bad = attention(); bad["history"] = {}
    with pytest.raises(ValueError):
        build_motive_signal_packet("sera", agent_state=base_agent(), attention_state=bad)
    bad = attention(); bad["history"] = [[]]
    with pytest.raises(ValueError):
        build_motive_signal_packet("sera", agent_state=base_agent(), attention_state=bad)
    bad = attention(); bad["history"][-1]["sequence"] = 0
    with pytest.raises(ValueError):
        build_motive_signal_packet("sera", agent_state=base_agent(), attention_state=bad)
    bad = attention(); bad["history"][-1]["attended_salience"] = []
    with pytest.raises(ValueError):
        build_motive_signal_packet("sera", agent_state=base_agent(), attention_state=bad)


def test_signal_map_duplicate_normalized_names_rejected_through_persistent_salience():
    bad = bridge(); bad["salience"] = {"x": .2, " x ": .3}
    with pytest.raises(ValueError):
        build_motive_signal_packet("sera", agent_state=base_agent(), persistent_salience=bad)


def test_signal_packet_validation_errors_reached_through_evaluate():
    runtime = MotiveRuntime(); runtime.configure("sera", "protect")
    valid = packet()
    with pytest.raises(ValueError): runtime.evaluate("sera", [])
    bad = deepcopy(valid); bad["extra"] = 1
    with pytest.raises(ValueError): runtime.evaluate("sera", bad)
    bad = deepcopy(valid); del bad["signals"]
    with pytest.raises(ValueError): runtime.evaluate("sera", bad)
    bad = deepcopy(valid); bad["packet_version"] = "9"
    with pytest.raises(ValueError): runtime.evaluate("sera", bad)
    bad = deepcopy(valid); bad["agent"] = "rowan"
    with pytest.raises(ValueError): runtime.evaluate("sera", bad)
    bad = deepcopy(valid); bad["signals"] = []
    with pytest.raises(ValueError): runtime.evaluate("sera", bad)
    bad = deepcopy(valid); bad["sources"] = {}
    with pytest.raises(ValueError): runtime.evaluate("sera", bad)
    bad = deepcopy(valid); bad["sources"]["traits"] = {1: "bad"}
    with pytest.raises(ValueError): runtime.evaluate("sera", bad)


def test_snapshot_validation_rejects_top_level_shape_errors():
    runtime = MotiveRuntime(); snap = runtime.snapshot()
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot([])
    bad = deepcopy(snap); bad["extra"] = 1
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)
    bad = deepcopy(snap); del bad["profiles"]
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)
    bad = deepcopy(snap); bad["schema_version"] = "9"
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)
    bad = deepcopy(snap); bad["history_limit"] = 0
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)
    bad = deepcopy(snap); bad["sequence"] = True
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)
    bad = deepcopy(snap); bad["profiles"] = []
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)
    bad = deepcopy(snap); bad["history"] = []
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)


def configured_snapshot():
    runtime = MotiveRuntime(history_limit=2)
    runtime.configure("sera", "protect", baseline=.1, weights={"value:protect_town":.5})
    runtime.evaluate("sera", packet())
    return runtime.snapshot()


def test_snapshot_profile_validation_paths():
    snap = configured_snapshot()
    bad = deepcopy(snap); bad["profiles"]["sera"] = []
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)
    bad = deepcopy(snap); bad["profiles"]["sera"]["protect"] = []
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)
    bad = deepcopy(snap); bad["profiles"]["sera"]["protect"]["extra"] = 1
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)
    bad = deepcopy(snap); bad["profiles"]["sera"]["protect"]["motive_id"] = "other"
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)


def test_snapshot_history_validation_paths():
    snap = configured_snapshot()
    bad = deepcopy(snap); bad["history"]["sera"] = {}
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)
    bad = deepcopy(snap); bad["history_limit"] = 1; bad["history"]["sera"] = bad["history"]["sera"] * 2
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)
    bad = deepcopy(snap); bad["history"]["sera"] = [[]]
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)
    bad = deepcopy(snap); bad["history"]["sera"][0]["sequence"] = 0
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)
    bad = deepcopy(snap); bad["history"]["sera"][0]["agent"] = "rowan"
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)
    bad = deepcopy(snap); bad["history"]["sera"][0]["motives"] = []
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)
    bad = deepcopy(snap); bad["history"]["sera"][0]["ranking"] = []
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)
    bad = deepcopy(snap); bad["history"]["sera"][0]["dominant_motive"] = "wrong"
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)
    bad = deepcopy(snap); bad["history"]["sera"][0]["dominant_score"] = 0.2
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)


def test_snapshot_rejects_global_sequence_duplicates_and_terminal_sequence_mismatch():
    runtime = MotiveRuntime(history_limit=3)
    runtime.configure("sera", "a"); runtime.configure("rowan", "a")
    runtime.evaluate("sera", packet())
    rowan_state = base_agent(); rowan_state["agent_id"]="rowan"
    rowan_bridge = bridge("rowan"); rowan_attention = attention("rowan")
    rp = build_motive_signal_packet("rowan", agent_state=rowan_state, persistent_salience=rowan_bridge, attention_state=rowan_attention)
    runtime.evaluate("rowan", rp)
    snap = runtime.snapshot()
    bad = deepcopy(snap); bad["history"]["rowan"][0]["sequence"] = 1
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)
    bad = deepcopy(snap); bad["sequence"] = 3
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)


def test_snapshot_rejects_nonzero_sequence_without_history():
    snap = MotiveRuntime().snapshot(); snap["sequence"] = 1
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(snap)


def test_snapshot_rejects_non_json_safe_values_before_structural_validation():
    snap = MotiveRuntime().snapshot(); snap["profiles"] = {"sera": {"x": {"motive_id":"x","baseline":float("nan"),"weights":{}}}}
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(snap)
    snap = MotiveRuntime().snapshot(); snap["weird"] = set()
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(snap)


def test_json_safe_validator_list_and_unsupported_type_branches_via_sources():
    runtime = MotiveRuntime(); runtime.configure("sera", "x")
    good = packet()
    good["sources"]["traits"]["nested"] = [1, {"ok": 2.0}, None]
    runtime.evaluate("sera", good)
    bad = packet(); bad["sources"]["traits"]["nested"] = set()
    with pytest.raises(ValueError): runtime.evaluate("sera", bad)


def test_profile_and_signal_ids_use_public_id_validation():
    runtime = MotiveRuntime()
    with pytest.raises(ValueError): runtime.configure("sera|bad", "x")
    with pytest.raises(ValueError): runtime.configure("sera", "x|bad")
    bad = base_agent(); bad["traits"] = {"a|b": .2}
    with pytest.raises(ValueError): build_motive_signal_packet("sera", agent_state=bad)


def test_source_count_and_attention_sequence_bool_are_rejected():
    bad = bridge(); bad["source_count"] = -1
    with pytest.raises(ValueError): build_motive_signal_packet("sera", agent_state=base_agent(), persistent_salience=bad)
    bad = attention(); bad["history"][-1]["sequence"] = True
    with pytest.raises(ValueError): build_motive_signal_packet("sera", agent_state=base_agent(), attention_state=bad)


def test_duplicate_normalized_trait_signal_is_rejected():
    bad = base_agent(); bad["traits"] = {"x": .2, " x ": .3}
    with pytest.raises(ValueError):
        build_motive_signal_packet("sera", agent_state=bad)


def test_remove_one_of_multiple_profiles_retains_agent_profile_bucket():
    runtime = MotiveRuntime()
    runtime.configure("sera", "a")
    runtime.configure("sera", "b")
    assert runtime.remove("sera", "a") is True
    assert list(runtime.profiles("sera")) == ["b"]


def test_snapshot_normalized_agent_collisions_and_empty_buckets():
    snap = MotiveRuntime().snapshot()
    snap["profiles"] = {"sera": {}, " sera ": {}}
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(snap)

    snap = MotiveRuntime().snapshot()
    snap["profiles"] = {"sera": {}}
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(snap)

    snap = MotiveRuntime().snapshot()
    snap["history"] = {"sera": [], " sera ": []}
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(snap)

    snap = MotiveRuntime().snapshot()
    snap["history"] = {"sera": []}
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(snap)


def rich_snapshot_for_validation():
    runtime = MotiveRuntime(history_limit=4)
    runtime.configure(
        "sera", "protect", baseline=.2,
        weights={
            "value:protect_town": .5,
            "persistent:emotion:anger": -.25,
            "missing:signal": .3,
        },
    )
    runtime.evaluate("sera", packet())
    return runtime.snapshot()


def test_snapshot_history_record_strict_structure_and_motive_invariants():
    snap = rich_snapshot_for_validation()

    bad = deepcopy(snap); bad["history"]["sera"][0]["extra"] = 1
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)

    bad = deepcopy(snap); bad["history"]["sera"][0]["motives"]["protect"] = []
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)

    bad = deepcopy(snap); bad["history"]["sera"][0]["motives"]["protect"]["motive_id"] = "other"
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)

    bad = deepcopy(snap); bad["history"]["sera"][0]["motives"]["protect"]["support"] = -0.1
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)

    bad = deepcopy(snap); bad["history"]["sera"][0]["motives"]["protect"]["contributions"] = {}
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)

    bad = deepcopy(snap); bad["history"]["sera"][0]["motives"]["protect"]["contributions"][0]["extra"] = 1
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)

    bad = deepcopy(snap)
    cs = bad["history"]["sera"][0]["motives"]["protect"]["contributions"]
    cs[1]["signal"] = cs[0]["signal"]
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)

    bad = deepcopy(snap)
    bad["history"]["sera"][0]["motives"]["protect"]["contributions"][0]["contribution"] += .01
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)

    bad = deepcopy(snap)
    bad["history"]["sera"][0]["motives"]["protect"]["missing_signals"] = []
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)

    bad = deepcopy(snap)
    bad["history"]["sera"][0]["motives"]["protect"]["raw_score"] += .01
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)

    bad = deepcopy(snap)
    bad["history"]["sera"][0]["motives"]["protect"]["support"] += .01
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)

    restored = MotiveRuntime.from_snapshot(snap)
    item = restored.history("sera")[0]["motives"]["protect"]
    assert item["opposition"] > 0.0
    assert item["missing_signals"] == ["missing:signal"]


def test_snapshot_normalized_agent_collisions_reach_collision_checks():
    snap = rich_snapshot_for_validation()
    profile_bucket = deepcopy(snap["profiles"]["sera"])
    bad = deepcopy(snap)
    bad["profiles"] = {"sera": deepcopy(profile_bucket), " sera ": deepcopy(profile_bucket)}
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)

    record = deepcopy(snap["history"]["sera"][0])
    bad = deepcopy(snap)
    bad["history"] = {"sera": [deepcopy(record)], " sera ": [deepcopy(record)]}
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)


def test_snapshot_rejects_non_increasing_sequence_inside_one_agent_history():
    runtime = MotiveRuntime(history_limit=3)
    runtime.configure("sera", "x")
    runtime.evaluate("sera", packet())
    runtime.evaluate("sera", packet())
    snap = runtime.snapshot()
    bad = deepcopy(snap)
    bad["history"]["sera"][1]["sequence"] = bad["history"]["sera"][0]["sequence"]
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)


def test_snapshot_rejects_duplicate_normalized_motive_ids_in_profiles_and_history():
    snap = rich_snapshot_for_validation()
    profile = deepcopy(snap["profiles"]["sera"]["protect"])
    bad = deepcopy(snap)
    bad["profiles"]["sera"] = {"protect": deepcopy(profile), " protect ": deepcopy(profile)}
    bad["profiles"]["sera"][" protect "]["motive_id"] = "protect"
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)

    result = deepcopy(snap["history"]["sera"][0]["motives"]["protect"])
    bad = deepcopy(snap)
    bad["history"]["sera"][0]["motives"] = {"protect": deepcopy(result), " protect ": deepcopy(result)}
    bad["history"]["sera"][0]["ranking"] = ["protect", " protect "]
    with pytest.raises(ValueError): MotiveRuntime.from_snapshot(bad)
