from __future__ import annotations

import copy
import json
import math

import pytest

from ghost.salience_bridge import (
    EMOTION_PREFIX,
    INTERPRETATION_PREFIX,
    SALIENCE_BRIDGE_PACKET_VERSION,
    build_salience_bridge,
)


def emotion_state(agent="sera", *, levels=None, bias=None, history=None):
    if levels is None:
        levels = {"anger": 0.6, "fear": 0.2}
    if bias is None:
        bias = {name: 1.0 for name in levels}
    return {
        "agent": agent,
        "levels": copy.deepcopy(levels),
        "salience_bias": copy.deepcopy(bias),
        "history": copy.deepcopy([] if history is None else history),
    }


def interpretation_state(agent="sera", *, levels=None, history=None):
    if levels is None:
        levels = {"betrayal": 0.8, "cooperation": 0.1}
    return {
        "agent": agent,
        "levels": copy.deepcopy(levels),
        "history": copy.deepcopy([] if history is None else history),
    }


def test_bridge_packet_version_is_frozen():
    assert SALIENCE_BRIDGE_PACKET_VERSION == "1.0"


def test_bridge_prefixes_are_explicit_and_disjoint():
    assert EMOTION_PREFIX != INTERPRETATION_PREFIX
    assert EMOTION_PREFIX.endswith(":")
    assert INTERPRETATION_PREFIX.endswith(":")


def test_empty_sources_are_explicit():
    packet = build_salience_bridge("sera")
    assert packet == {
        "packet_version": "1.0",
        "agent": "sera",
        "source_count": 0,
        "sources": {
            "emotion": {"present": False, "revision": None, "dimensions": []},
            "interpretation": {"present": False, "revision": None, "dimensions": []},
        },
        "salience": {},
    }


def test_emotion_only_maps_level_times_bias():
    packet = build_salience_bridge(
        "sera",
        emotion_state=emotion_state(
            levels={"anger": 0.5, "fear": 0.4},
            bias={"anger": 1.4, "fear": 0.5},
        ),
    )
    assert packet["salience"] == {"emotion:anger": 0.7, "emotion:fear": 0.2}
    assert packet["source_count"] == 1


def test_emotion_salience_clamps_high_bias_at_one():
    packet = build_salience_bridge(
        "sera",
        emotion_state=emotion_state(levels={"anger": 0.8}, bias={"anger": 5.0}),
    )
    assert packet["salience"]["emotion:anger"] == 1.0


def test_interpretation_only_uses_persistent_levels():
    packet = build_salience_bridge(
        "sera",
        interpretation_state=interpretation_state(
            levels={"betrayal": 0.73, "cooperation": 0.21}
        ),
    )
    assert packet["salience"] == {
        "interpretation:betrayal": 0.73,
        "interpretation:cooperation": 0.21,
    }
    assert packet["source_count"] == 1


def test_same_channel_name_cannot_collide_across_sources():
    packet = build_salience_bridge(
        "sera",
        emotion_state=emotion_state(levels={"fear": 0.7}, bias={"fear": 1.0}),
        interpretation_state=interpretation_state(levels={"fear": 0.3}),
    )
    assert packet["salience"] == {
        "emotion:fear": 0.7,
        "interpretation:fear": 0.3,
    }


def test_combined_source_dimensions_are_sorted_per_source():
    packet = build_salience_bridge(
        "sera",
        emotion_state=emotion_state(
            levels={"zeta": 0.1, "alpha": 0.2},
            bias={"zeta": 1.0, "alpha": 1.0},
        ),
        interpretation_state=interpretation_state(
            levels={"trust": 0.2, "betrayal": 0.9}
        ),
    )
    assert packet["sources"]["emotion"]["dimensions"] == [
        "emotion:alpha",
        "emotion:zeta",
    ]
    assert packet["sources"]["interpretation"]["dimensions"] == [
        "interpretation:betrayal",
        "interpretation:trust",
    ]


def test_disabled_emotion_source_is_not_validated_or_consumed():
    packet = build_salience_bridge(
        "sera",
        emotion_state="not-a-dict",
        include_emotions=False,
    )
    assert packet["sources"]["emotion"]["present"] is False


def test_disabled_interpretation_source_is_not_validated_or_consumed():
    packet = build_salience_bridge(
        "sera",
        interpretation_state="not-a-dict",
        include_interpretations=False,
    )
    assert packet["sources"]["interpretation"]["present"] is False


def test_both_disabled_sources_produce_empty_packet():
    packet = build_salience_bridge(
        "sera",
        emotion_state=emotion_state(),
        interpretation_state=interpretation_state(),
        include_emotions=False,
        include_interpretations=False,
    )
    assert packet["salience"] == {}
    assert packet["source_count"] == 0


def test_bridge_never_mutates_source_packets():
    emotions = emotion_state()
    interpretations = interpretation_state()
    before_emotions = copy.deepcopy(emotions)
    before_interpretations = copy.deepcopy(interpretations)
    build_salience_bridge(
        "sera",
        emotion_state=emotions,
        interpretation_state=interpretations,
    )
    assert emotions == before_emotions
    assert interpretations == before_interpretations


def test_bridge_output_cannot_alias_source_packets():
    emotions = emotion_state()
    packet = build_salience_bridge("sera", emotion_state=emotions)
    packet["salience"]["emotion:anger"] = 0.0
    packet["sources"]["emotion"]["dimensions"].append("corrupt")
    assert emotions["levels"]["anger"] == 0.6
    assert "corrupt" not in emotions


def test_source_revision_uses_latest_history_sequence():
    packet = build_salience_bridge(
        "sera",
        emotion_state=emotion_state(
            history=[{"sequence": 3}, {"sequence": 9}, {"sequence": 12}]
        ),
        interpretation_state=interpretation_state(
            history=[{"sequence": 2}, {"sequence": 7}]
        ),
    )
    assert packet["sources"]["emotion"]["revision"] == 12
    assert packet["sources"]["interpretation"]["revision"] == 7


def test_source_revision_zero_when_history_is_empty():
    packet = build_salience_bridge("sera", emotion_state=emotion_state())
    assert packet["sources"]["emotion"]["revision"] == 0


def test_bridge_is_strict_json_safe():
    packet = build_salience_bridge(
        "sera",
        emotion_state=emotion_state(),
        interpretation_state=interpretation_state(),
    )
    assert json.loads(json.dumps(packet, allow_nan=False)) == packet


def test_bridge_is_deterministic_for_same_copied_inputs():
    emotions = emotion_state()
    interpretations = interpretation_state()
    left = build_salience_bridge(
        "sera",
        emotion_state=emotions,
        interpretation_state=interpretations,
    )
    right = build_salience_bridge(
        "sera",
        emotion_state=copy.deepcopy(emotions),
        interpretation_state=copy.deepcopy(interpretations),
    )
    assert left == right


def test_many_dimensions_remain_namespaced_and_bounded():
    levels = {f"e{i:03d}": (i % 11) / 10 for i in range(128)}
    bias = {name: 1.0 for name in levels}
    packet = build_salience_bridge(
        "sera",
        emotion_state=emotion_state(levels=levels, bias=bias),
    )
    assert len(packet["salience"]) == 128
    assert all(name.startswith("emotion:") for name in packet["salience"])
    assert all(0.0 <= value <= 1.0 for value in packet["salience"].values())


def test_zero_values_are_preserved_as_explicit_dimensions():
    packet = build_salience_bridge(
        "sera",
        emotion_state=emotion_state(levels={"anger": 0.0}, bias={"anger": 1.0}),
        interpretation_state=interpretation_state(levels={"betrayal": 0.0}),
    )
    assert packet["salience"] == {
        "emotion:anger": 0.0,
        "interpretation:betrayal": 0.0,
    }


def test_agent_is_normalized_once_at_bridge_boundary():
    packet = build_salience_bridge(
        "  sera  ",
        emotion_state=emotion_state(agent="sera"),
    )
    assert packet["agent"] == "sera"


@pytest.mark.parametrize("bad", [None, "", "   ", "bad|id"])
def test_invalid_bridge_agent_is_rejected(bad):
    with pytest.raises(ValueError):
        build_salience_bridge(bad)
    assert True


@pytest.mark.parametrize("bad", [0, 1, None, "true", [], {}])
def test_include_emotions_requires_real_bool(bad):
    with pytest.raises(ValueError):
        build_salience_bridge("sera", include_emotions=bad)
    assert True


@pytest.mark.parametrize("bad", [0, 1, None, "false", [], {}])
def test_include_interpretations_requires_real_bool(bad):
    with pytest.raises(ValueError):
        build_salience_bridge("sera", include_interpretations=bad)
    assert True


@pytest.mark.parametrize("bad", ["x", [], 1, 1.2, True])
def test_enabled_emotion_state_requires_dict_or_none(bad):
    with pytest.raises(ValueError):
        build_salience_bridge("sera", emotion_state=bad)
    assert True


@pytest.mark.parametrize("bad", ["x", [], 1, 1.2, True])
def test_enabled_interpretation_state_requires_dict_or_none(bad):
    with pytest.raises(ValueError):
        build_salience_bridge("sera", interpretation_state=bad)
    assert True


def test_emotion_state_agent_must_match_bridge_agent():
    with pytest.raises(ValueError):
        build_salience_bridge("sera", emotion_state=emotion_state(agent="rowan"))
    assert True


def test_interpretation_state_agent_must_match_bridge_agent():
    with pytest.raises(ValueError):
        build_salience_bridge(
            "sera",
            interpretation_state=interpretation_state(agent="rowan"),
        )
    assert True


def test_emotion_state_requires_agent():
    packet = emotion_state()
    del packet["agent"]
    with pytest.raises(ValueError):
        build_salience_bridge("sera", emotion_state=packet)
    assert True


def test_interpretation_state_requires_agent():
    packet = interpretation_state()
    del packet["agent"]
    with pytest.raises(ValueError):
        build_salience_bridge("sera", interpretation_state=packet)
    assert True


def test_emotion_state_requires_levels():
    packet = emotion_state()
    del packet["levels"]
    with pytest.raises(ValueError):
        build_salience_bridge("sera", emotion_state=packet)
    assert True


def test_emotion_state_requires_salience_bias():
    packet = emotion_state()
    del packet["salience_bias"]
    with pytest.raises(ValueError):
        build_salience_bridge("sera", emotion_state=packet)
    assert True


def test_interpretation_state_requires_levels():
    packet = interpretation_state()
    del packet["levels"]
    with pytest.raises(ValueError):
        build_salience_bridge("sera", interpretation_state=packet)
    assert True


@pytest.mark.parametrize(
    "bad",
    [-0.1, 1.1, math.inf, -math.inf, math.nan, True, False, "0.5", None, []],
)
def test_invalid_emotion_levels_are_rejected(bad):
    packet = emotion_state(levels={"anger": bad}, bias={"anger": 1.0})
    with pytest.raises(ValueError):
        build_salience_bridge("sera", emotion_state=packet)
    assert True


@pytest.mark.parametrize(
    "bad",
    [-0.1, math.inf, -math.inf, math.nan, True, False, "1", None, []],
)
def test_invalid_emotion_biases_are_rejected(bad):
    packet = emotion_state(levels={"anger": 0.5}, bias={"anger": bad})
    with pytest.raises(ValueError):
        build_salience_bridge("sera", emotion_state=packet)
    assert True


@pytest.mark.parametrize(
    "bad",
    [-0.1, 1.1, math.inf, -math.inf, math.nan, True, False, "0.5", None, []],
)
def test_invalid_interpretation_levels_are_rejected(bad):
    packet = interpretation_state(levels={"betrayal": bad})
    with pytest.raises(ValueError):
        build_salience_bridge("sera", interpretation_state=packet)
    assert True


def test_emotion_level_and_bias_dimensions_must_match():
    packet = emotion_state(
        levels={"anger": 0.5, "fear": 0.2},
        bias={"anger": 1.0},
    )
    with pytest.raises(ValueError):
        build_salience_bridge("sera", emotion_state=packet)
    assert True


@pytest.mark.parametrize("bad_name", ["", "   "])
def test_blank_emotion_dimension_is_rejected(bad_name):
    packet = emotion_state(levels={bad_name: 0.5}, bias={bad_name: 1.0})
    with pytest.raises(ValueError):
        build_salience_bridge("sera", emotion_state=packet)
    assert True


@pytest.mark.parametrize("bad_name", ["", "   "])
def test_blank_interpretation_dimension_is_rejected(bad_name):
    packet = interpretation_state(levels={bad_name: 0.5})
    with pytest.raises(ValueError):
        build_salience_bridge("sera", interpretation_state=packet)
    assert True


def test_non_dict_emotion_levels_are_rejected():
    packet = emotion_state()
    packet["levels"] = []
    with pytest.raises(ValueError):
        build_salience_bridge("sera", emotion_state=packet)
    assert True


def test_non_dict_interpretation_levels_are_rejected():
    packet = interpretation_state()
    packet["levels"] = []
    with pytest.raises(ValueError):
        build_salience_bridge("sera", interpretation_state=packet)
    assert True


def test_non_dict_emotion_bias_is_rejected():
    packet = emotion_state()
    packet["salience_bias"] = []
    with pytest.raises(ValueError):
        build_salience_bridge("sera", emotion_state=packet)
    assert True


@pytest.mark.parametrize(
    "history",
    [
        "bad",
        [{"sequence": 0}],
        [{"sequence": True}],
        [{"sequence": 2}, {"sequence": 2}],
        [{"sequence": 3}, {"sequence": 2}],
        ["bad-record"],
    ],
)
def test_invalid_emotion_history_revision_is_rejected(history):
    packet = emotion_state(history=history)
    with pytest.raises(ValueError):
        build_salience_bridge("sera", emotion_state=packet)
    assert True


@pytest.mark.parametrize(
    "history",
    [
        "bad",
        [{"sequence": 0}],
        [{"sequence": True}],
        [{"sequence": 2}, {"sequence": 2}],
        [{"sequence": 3}, {"sequence": 2}],
        ["bad-record"],
    ],
)
def test_invalid_interpretation_history_revision_is_rejected(history):
    packet = interpretation_state(history=history)
    with pytest.raises(ValueError):
        build_salience_bridge("sera", interpretation_state=packet)
    assert True


def test_duplicate_normalized_level_names_are_rejected():
    packet = emotion_state(
        levels={"anger": 0.5, " anger ": 0.4},
        bias={"anger": 1.0, " anger ": 1.0},
    )
    with pytest.raises(ValueError):
        build_salience_bridge("sera", emotion_state=packet)
    assert True


def test_duplicate_normalized_bias_names_are_rejected():
    packet = emotion_state(
        levels={"anger": 0.5, "fear": 0.4},
        bias={"anger": 1.0, " anger ": 1.0},
    )
    with pytest.raises(ValueError):
        build_salience_bridge("sera", emotion_state=packet)
    assert True
