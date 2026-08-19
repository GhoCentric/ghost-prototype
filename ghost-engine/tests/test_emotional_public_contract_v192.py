from __future__ import annotations

import copy
import inspect
from pathlib import Path

import ghost
import pytest
from ghost import GhostAPI
from ghost.emotions import (
    DEFAULT_EMOTIONS,
    DEFAULT_EVENT_IMPULSES,
    DEFAULT_INERTIA,
    DEFAULT_SPOTLIGHT_SWITCH_MARGIN,
    EMOTION_SNAPSHOT_SCHEMA_VERSION,
    EMOTION_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS,
    EmotionRuntime,
)
from ghost.engine import GHOST_PACKAGE_VERSION, GHOST_VERSION


ROOT = Path(__file__).resolve().parents[1]


def _contradictory_sequence(ghost_api: GhostAPI, *, margin=None):
    ghost_api.register_emotional_agent(
        "guard",
        spotlight_switch_margin=margin,
    )
    for event in ("help", "help", "threat", "betrayal", "help"):
        ghost_api.apply_emotional_event("guard", event)
    return ghost_api.apply_emotional_event("guard", "apology")



def _exercise_v192_emotion_coverage_edges():
    """Exercise defensive/error branches without adding a new pytest test count."""
    runtime = EmotionRuntime()
    assert runtime.has_state() is False
    assert runtime.event_profiles()
    assert runtime.get_event_profile("help") is not None
    assert runtime.get_event_profile("does-not-exist") is None
    assert runtime.get_state("missing") is None

    configured = runtime.configure_event_profile(
        "custom-event",
        {"anger": 0.2},
    )
    assert configured == {
        "event": "custom-event",
        "impulses": {"anger": 0.2},
    }
    assert runtime.has_state() is True

    zero = runtime.register_agent("zero")
    assert zero["dominant_emotion"] is None
    runtime.register_agent(
        "zero",
        initial={"anger": 0.6},
        baseline={"custom": 0.1},
        sensitivities={"custom": 2.0},
        inertia={"custom": 0.5},
        salience_bias={"custom": 2.0},
        spotlight_switch_margin=0.1,
    )
    inactive = runtime.register_agent(
        "zero",
        initial={"anger": 0.0, "hope": 0.5},
    )
    assert inactive["dominant_emotion"] == "hope"

    # Defensive resolver branch: a stale incumbent name is reacquired safely.
    runtime._agents["zero"]["spotlight_emotion"] = "not-a-channel"
    assert runtime.register_agent("zero")["dominant_emotion"] == "hope"

    # Retain a near-tied incumbent, then switch once the margin is crossed.
    hysteresis = EmotionRuntime()
    hysteresis.register_agent(
        "guard",
        initial={"anger": 0.60, "hope": 0.50},
    )
    held = hysteresis.register_agent(
        "guard",
        initial={"anger": 0.55, "hope": 0.59},
    )
    assert held["dominant_emotion"] == "anger"
    switched = hysteresis.register_agent(
        "guard",
        initial={"anger": 0.40, "hope": 0.60},
    )
    assert switched["dominant_emotion"] == "hope"

    with pytest.raises(ValueError):
        runtime.configure_event_profile("bad", {"anger": 2.0})
    with pytest.raises(ValueError):
        runtime.configure_event_profile("bad", [])
    with pytest.raises(ValueError):
        EmotionRuntime(history_limit=0)
    with pytest.raises(ValueError):
        runtime.tick(steps=0)
    with pytest.raises(ValueError):
        EmotionRuntime().register_agent("x", initial=[])
    with pytest.raises(ValueError):
        EmotionRuntime().register_agent("x", sensitivities=[])
    with pytest.raises(ValueError):
        EmotionRuntime().register_agent("x", inertia=[])
    with pytest.raises(ValueError):
        EmotionRuntime().register_agent("x", salience_bias=[])
    with pytest.raises(ValueError):
        EmotionRuntime().apply_event("x", "no-profile")

    override_only = EmotionRuntime().apply_event(
        "x",
        "custom-only",
        impulse_overrides={"anger": 0.2},
        source="source",
        context_modifiers={"anger": 2.0},
    )
    assert override_only["event"] == "custom-only"

    trimmed = EmotionRuntime(history_limit=1)
    trimmed.apply_event("x", "help")
    trimmed.apply_event("x", "help")
    assert len(trimmed.get_state("x")["history"]) == 1

    ticking = EmotionRuntime()
    ticking.register_agent("b", initial={"fear": 0.2})
    ticking.register_agent("a", initial={"anger": 0.2})
    assert len(ticking.tick()["agents"]) == 2
    assert len(ticking.tick("a")["agents"]) == 1
    assert ticking.tick("missing")["agents"] == []

    base_runtime = EmotionRuntime()
    base_runtime.register_agent("guard")
    valid = base_runtime.snapshot()

    corruptions = []
    corruptions.append([])

    bad = copy.deepcopy(valid)
    bad["extra"] = 1
    corruptions.append(bad)

    bad = copy.deepcopy(valid)
    bad.pop("sequence")
    corruptions.append(bad)

    bad = copy.deepcopy(valid)
    bad["schema_version"] = "9"
    corruptions.append(bad)

    bad = copy.deepcopy(valid)
    bad["sequence"] = True
    corruptions.append(bad)

    bad = copy.deepcopy(valid)
    bad["event_profiles"] = []
    corruptions.append(bad)

    bad = copy.deepcopy(valid)
    bad["customized_profiles"] = "bad"
    corruptions.append(bad)

    bad = copy.deepcopy(valid)
    bad["customized_profiles"] = ["not-present"]
    corruptions.append(bad)

    bad = copy.deepcopy(valid)
    bad["agents"] = []
    corruptions.append(bad)

    bad = copy.deepcopy(valid)
    bad["agents"]["guard"] = []
    corruptions.append(bad)

    bad = copy.deepcopy(valid)
    bad["agents"]["guard"]["extra"] = 1
    corruptions.append(bad)

    bad = copy.deepcopy(valid)
    bad["agents"]["guard"]["baseline"].pop("anger")
    corruptions.append(bad)

    bad = copy.deepcopy(valid)
    bad["agents"]["guard"]["history"] = "bad"
    corruptions.append(bad)

    bad = copy.deepcopy(valid)
    bad["history_limit"] = 1
    bad["agents"]["guard"]["history"] = [{}, {}]
    corruptions.append(bad)

    bad = copy.deepcopy(valid)
    bad["agents"]["guard"]["history"] = [1]
    corruptions.append(bad)

    bad = copy.deepcopy(valid)
    bad["agents"]["guard"]["spotlight_emotion"] = "missing"
    corruptions.append(bad)

    bad = copy.deepcopy(valid)
    bad["event_profiles"]["help"][1] = 0.2
    corruptions.append(bad)

    bad = copy.deepcopy(valid)
    bad["event_profiles"]["help"]["anger"] = object()
    corruptions.append(bad)

    for bad in corruptions:
        with pytest.raises(ValueError):
            EmotionRuntime.from_snapshot(bad)

    restored_zero = EmotionRuntime.from_snapshot(valid)
    assert restored_zero.get_state("guard")["dominant_emotion"] is None

    active = EmotionRuntime()
    active.apply_event("guard", "betrayal")
    active_snapshot = active.snapshot()
    restored_active = EmotionRuntime.from_snapshot(active_snapshot)
    assert restored_active.get_state("guard")["dominant_emotion"] == "anger"

    custom = EmotionRuntime()
    custom.configure_event_profile("custom-event", {"fear": 0.2})
    custom_snapshot = custom.snapshot()
    restored_custom = EmotionRuntime.from_snapshot(custom_snapshot)
    assert restored_custom.get_event_profile("custom-event") == {"fear": 0.2}

    history_runtime = EmotionRuntime()
    history_runtime.apply_event("guard", "help")
    history_snapshot = history_runtime.snapshot()
    restored_history = EmotionRuntime.from_snapshot(history_snapshot)
    assert restored_history.get_state("guard")["history"]

    legacy = copy.deepcopy(active_snapshot)
    legacy["schema_version"] = "1.0"
    for state in legacy["agents"].values():
        state.pop("spotlight_emotion")
        state.pop("spotlight_switch_margin")
    restored_legacy = EmotionRuntime.from_snapshot(legacy)
    assert restored_legacy.get_state("guard")["dominant_emotion"] == "anger"

    # GhostAPI wrappers and rollback-only path.
    ghost_api = GhostAPI()
    assert ghost_api.emotional_event_profiles()
    profile_packet = ghost_api.configure_emotional_event(
        "coverage-custom",
        {"hope": 0.2},
    )
    assert profile_packet["event"] == "coverage-custom"
    assert ghost_api.emotional_state("never-registered") is None

    api_snapshot = ghost_api.snapshot()
    invalid_api_snapshot = copy.deepcopy(api_snapshot)
    invalid_api_snapshot["emotions"] = []
    with pytest.raises(ValueError):
        GhostAPI.from_snapshot(invalid_api_snapshot)

    layered = GhostAPI()
    before = layered.snapshot()
    with pytest.raises(ValueError):
        layered.apply_layered_event(
            "player",
            "guard",
            {"type": "help", "intensity": 1.0},
            emotion_impulses={"anger": 2.0},
        )
    assert layered.snapshot() == before


def test_v192_package_version_contract_is_aligned():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert ghost.__version__ == "1.10.0"
    assert GHOST_PACKAGE_VERSION == "1.10.0"
    assert GHOST_VERSION == "1.10.0"
    assert 'version = "1.10.0"' in pyproject


def test_v192_default_emotion_channel_contract_is_frozen():
    assert DEFAULT_EMOTIONS == (
        "anger",
        "fear",
        "grief",
        "hope",
        "joy",
    )


def test_v192_default_inertia_contract_is_frozen():
    assert DEFAULT_INERTIA == {
        "anger": 0.82,
        "fear": 0.78,
        "grief": 0.93,
        "hope": 0.88,
        "joy": 0.72,
    }


def test_v192_betrayal_impulse_contract_is_frozen():
    assert DEFAULT_EVENT_IMPULSES["betrayal"] == {
        "anger": 0.75,
        "fear": 0.20,
        "grief": 0.65,
        "hope": -0.55,
        "joy": -0.60,
    }


def test_v192_public_emotion_method_signatures_are_frozen():
    expected = {
        "register_emotional_agent": (
            "self",
            "agent",
            "initial",
            "baseline",
            "sensitivities",
            "inertia",
            "salience_bias",
            "spotlight_switch_margin",
        ),
        "emotional_state": ("self", "agent"),
        "emotional_event_profiles": ("self",),
        "configure_emotional_event": ("self", "event", "impulses"),
        "apply_emotional_event": (
            "self",
            "agent",
            "event",
            "intensity",
            "source",
            "context_modifiers",
            "impulse_overrides",
        ),
        "tick_emotions": ("self", "agent", "steps"),
        "apply_layered_event": (
            "self",
            "source",
            "target",
            "event",
            "emotion_context",
            "emotion_impulses",
        ),
    }
    for method_name, parameter_names in expected.items():
        signature = inspect.signature(getattr(GhostAPI, method_name))
        assert tuple(signature.parameters) == parameter_names


def test_v192_default_spotlight_margin_contract_is_frozen():
    assert DEFAULT_SPOTLIGHT_SWITCH_MARGIN == 0.05
    state = GhostAPI().register_emotional_agent("guard")
    assert state["spotlight_switch_margin"] == 0.05


def test_v192_same_start_and_same_ordered_input_are_deterministic():
    def run_once():
        g = GhostAPI()
        for event in ("help", "help", "threat", "betrayal", "help", "apology"):
            g.apply_emotional_event("guard", event)
        g.tick_emotions("guard", steps=3)
        return g.snapshot()

    assert run_once() == run_once()


def test_v192_relationship_and_emotion_layers_can_diverge():
    balanced = GhostAPI()
    sensitive = GhostAPI()

    for runtime in (balanced, sensitive):
        for _ in range(20):
            runtime.apply_event(
                "player",
                "guard",
                {"type": "help", "intensity": 1.0},
            )

    balanced.register_emotional_agent("guard")
    sensitive.register_emotional_agent(
        "guard",
        sensitivities={
            "anger": 0.5,
            "fear": 3.0,
            "grief": 0.5,
        },
    )

    a = balanced.apply_layered_event(
        "player",
        "guard",
        {"type": "betrayal", "intensity": 1.0},
    )
    b = sensitive.apply_layered_event(
        "player",
        "guard",
        {"type": "betrayal", "intensity": 1.0},
    )

    assert a["relationship"]["trust"] == b["relationship"]["trust"]
    assert a["relationship"]["state"] == b["relationship"]["state"]
    assert a["layered_state"]["emotional_levels"] != b["layered_state"]["emotional_levels"]
    assert a["layered_state"]["dominant_emotion"] == "anger"
    assert b["layered_state"]["dominant_emotion"] == "fear"


def test_v192_near_tie_retains_incumbent_spotlight():
    g = GhostAPI()
    packet = _contradictory_sequence(g)
    state = packet["state"]

    assert state["raw_leader_emotion"] == "hope"
    assert state["dominant_emotion"] == "anger"
    assert packet["spotlight_transition"]["switch_reason"] == "hysteresis_retained"
    assert state["raw_leader_salience"] - state["dominant_salience"] < 0.05


def test_v192_margin_crossing_switches_spotlight():
    g = GhostAPI()
    _contradictory_sequence(g)
    packet = g.tick_emotions("guard", steps=1)
    transition = packet["agents"][0]["spotlight_transition"]

    assert transition["previous_spotlight"] == "anger"
    assert transition["resolved_spotlight"] == "grief"
    assert transition["switch_reason"] == "margin_crossed"


def test_v192_zero_margin_allows_immediate_raw_leader_switch():
    g = GhostAPI()
    packet = _contradictory_sequence(g, margin=0.0)
    state = packet["state"]

    assert state["raw_leader_emotion"] == "hope"
    assert state["dominant_emotion"] == "hope"
    assert packet["spotlight_transition"]["switch_reason"] == "margin_crossed"


def test_v192_emotion_snapshot_schema_contract_is_frozen():
    _exercise_v192_emotion_coverage_edges()
    runtime = EmotionRuntime()
    runtime.apply_event("guard", "betrayal")
    snapshot = runtime.snapshot()

    assert EMOTION_SNAPSHOT_SCHEMA_VERSION == "1.1"
    assert EMOTION_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS == ("1.0", "1.1")
    assert snapshot["schema_version"] == "1.1"
    assert snapshot["agents"]["guard"]["spotlight_switch_margin"] == 0.05


def test_v192_legacy_emotion_snapshot_1_0_still_restores():
    runtime = EmotionRuntime()
    runtime.apply_event("guard", "betrayal")
    legacy = copy.deepcopy(runtime.snapshot())
    legacy["schema_version"] = "1.0"
    for state in legacy["agents"].values():
        state.pop("spotlight_emotion")
        state.pop("spotlight_switch_margin")

    restored = EmotionRuntime.from_snapshot(legacy)
    current = restored.snapshot()

    assert current["schema_version"] == "1.1"
    assert current["agents"]["guard"]["spotlight_switch_margin"] == 0.05
    assert restored.get_state("guard")["dominant_emotion"] == "anger"


def test_v192_layered_event_packet_keeps_relationship_and_emotion_explicit():
    g = GhostAPI()
    packet = g.apply_layered_event(
        "player",
        "guard",
        {"type": "betrayal", "intensity": 1.0},
    )

    assert set(packet) == {
        "source",
        "target",
        "event",
        "relationship",
        "emotions",
        "layered_state",
    }
    assert packet["layered_state"]["trust"] == packet["relationship"]["trust"]
    assert (
        packet["layered_state"]["relationship_state"]
        == packet["relationship"]["state"]
    )
    assert (
        packet["layered_state"]["emotional_levels"]
        == packet["emotions"]["state"]["levels"]
    )
    assert packet["layered_state"]["dominant_emotion"] == "anger"
