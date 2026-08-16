import copy

import pytest

from ghost import GhostAPI
from ghost.emotions import EmotionRuntime


def test_default_profiles_are_explicit_and_not_random():
    runtime = EmotionRuntime()
    betrayal = runtime.get_event_profile("betrayal")
    assert betrayal == {
        "anger": 0.75,
        "fear": 0.20,
        "grief": 0.65,
        "hope": -0.55,
        "joy": -0.60,
    }


def test_emotion_levels_are_independent_and_bounded():
    runtime = EmotionRuntime()
    packet = runtime.apply_event("guard", "betrayal", source="player")
    assert packet["after"]["anger"] == pytest.approx(0.75)
    assert packet["after"]["fear"] == pytest.approx(0.20)
    assert packet["after"]["grief"] == pytest.approx(0.65)
    assert packet["after"]["hope"] == pytest.approx(0.0)
    assert packet["after"]["joy"] == pytest.approx(0.0)
    assert all(0.0 <= value <= 1.0 for value in packet["after"].values())


def test_sensitivity_changes_final_level_without_changing_profile():
    runtime = EmotionRuntime()
    runtime.register_agent(
        "guard",
        sensitivities={"anger": 1.20},
    )
    packet = runtime.apply_event("guard", "betrayal")
    assert packet["base_impulses"]["anger"] == pytest.approx(0.75)
    assert packet["after"]["anger"] == pytest.approx(0.90)


def test_context_modifier_changes_only_named_channel():
    a = EmotionRuntime()
    b = EmotionRuntime()
    base = a.apply_event("guard", "threat")
    modified = b.apply_event(
        "guard",
        "threat",
        context_modifiers={"fear": 0.50},
    )
    assert modified["after"]["fear"] < base["after"]["fear"]
    assert modified["after"]["anger"] == pytest.approx(base["after"]["anger"])


def test_negative_impulse_reduces_existing_emotion():
    runtime = EmotionRuntime()
    runtime.register_agent("guard", initial={"anger": 0.80})
    packet = runtime.apply_event("guard", "help")
    assert packet["after"]["anger"] < 0.80
    assert packet["after"]["anger"] >= 0.0


def test_tick_uses_per_channel_inertia_toward_baseline():
    runtime = EmotionRuntime()
    runtime.register_agent(
        "guard",
        initial={"anger": 0.80, "grief": 0.80},
        baseline={"anger": 0.10, "grief": 0.20},
        inertia={"anger": 0.50, "grief": 0.90},
    )
    packet = runtime.tick("guard")
    after = packet["agents"][0]["after"]
    assert after["anger"] == pytest.approx(0.45)
    assert after["grief"] == pytest.approx(0.74)


def test_salience_competes_without_selecting_action():
    runtime = EmotionRuntime()
    runtime.register_agent(
        "guard",
        initial={"anger": 0.66, "fear": 0.34, "hope": 0.20},
    )
    state = runtime.get_state("guard")
    assert state["dominant_emotion"] == "anger"
    assert state["dominant_salience"] == pytest.approx(0.66)
    assert state["spotlight"][0]["emotion"] == "anger"
    assert sum(row["share"] for row in state["spotlight"]) == pytest.approx(1.0)
    assert "action" not in state


def test_custom_emotions_and_event_profiles_are_supported():
    runtime = EmotionRuntime()
    runtime.configure_event_profile(
        "victory",
        {"pride": 0.70, "fear": -0.20, "hope": 0.30},
    )
    packet = runtime.apply_event("knight", "victory")
    assert packet["after"]["pride"] == pytest.approx(0.70)
    assert packet["state"]["dominant_emotion"] == "pride"


def test_runtime_is_deterministic_for_identical_ordered_inputs():
    a = EmotionRuntime()
    b = EmotionRuntime()
    for runtime in (a, b):
        runtime.register_agent(
            "guard",
            sensitivities={"fear": 1.30, "anger": 0.80},
        )
        runtime.apply_event("guard", "help", source="player")
        runtime.apply_event("guard", "betrayal", source="player")
        runtime.tick("guard", steps=2)
    assert a.snapshot() == b.snapshot()


def test_snapshot_round_trip_is_exact():
    runtime = EmotionRuntime()
    runtime.register_agent(
        "guard",
        initial={"anger": 0.30},
        sensitivities={"fear": 1.50},
        inertia={"grief": 0.95},
        salience_bias={"fear": 1.20},
    )
    runtime.apply_event("guard", "betrayal", source="player")
    snapshot = runtime.snapshot()
    restored = EmotionRuntime.from_snapshot(copy.deepcopy(snapshot))
    assert restored.snapshot() == snapshot


def test_snapshot_rejects_invalid_emotional_level():
    runtime = EmotionRuntime()
    runtime.apply_event("guard", "betrayal")
    snapshot = runtime.snapshot()
    snapshot["agents"]["guard"]["levels"]["anger"] = 1.5
    with pytest.raises(ValueError):
        EmotionRuntime.from_snapshot(snapshot)


def test_ghost_api_snapshot_stays_legacy_shaped_until_emotions_are_used():
    ghost = GhostAPI()
    assert "emotions" not in ghost.snapshot()


def test_ghost_api_snapshot_includes_emotions_after_use_and_restores_exactly():
    ghost = GhostAPI()
    ghost.apply_emotional_event(
        "guard",
        "betrayal",
        source="player",
    )
    snapshot = ghost.snapshot()
    assert "emotions" in snapshot
    restored = GhostAPI.from_snapshot(snapshot)
    assert restored.snapshot() == snapshot


def test_layered_event_keeps_relationship_and_emotion_as_separate_layers():
    ghost = GhostAPI()
    for _ in range(20):
        ghost.apply_event(
            "player",
            "guard",
            {"type": "help", "intensity": 1.0},
        )

    packet = ghost.apply_layered_event(
        "player",
        "guard",
        {"type": "betrayal", "intensity": 1.0},
    )

    assert packet["layered_state"]["relationship_state"] == "friendly"
    assert packet["layered_state"]["emotional_levels"]["anger"] == pytest.approx(0.75)
    assert packet["layered_state"]["emotional_levels"]["grief"] == pytest.approx(0.65)
    assert packet["layered_state"]["dominant_emotion"] == "anger"


def test_same_relationship_outcome_can_carry_different_emotional_vectors():
    a = GhostAPI()
    b = GhostAPI()
    b.register_emotional_agent(
        "guard",
        sensitivities={
            "anger": 0.50,
            "fear": 3.00,
            "grief": 0.50,
        },
    )

    for ghost in (a, b):
        for _ in range(20):
            ghost.apply_event(
                "player",
                "guard",
                {"type": "help", "intensity": 1.0},
            )

    pa = a.apply_layered_event(
        "player",
        "guard",
        {"type": "betrayal", "intensity": 1.0},
    )
    pb = b.apply_layered_event(
        "player",
        "guard",
        {"type": "betrayal", "intensity": 1.0},
    )

    assert pa["layered_state"]["trust"] == pytest.approx(pb["layered_state"]["trust"])
    assert pa["layered_state"]["relationship_state"] == pb["layered_state"]["relationship_state"]
    assert pa["layered_state"]["dominant_emotion"] == "anger"
    assert pb["layered_state"]["dominant_emotion"] == "fear"


def test_apply_layered_event_is_deterministic_from_same_snapshot():
    ghost = GhostAPI()
    for _ in range(5):
        ghost.apply_event("player", "guard", {"type": "help", "intensity": 1.0})
    start = ghost.snapshot()

    a = GhostAPI.from_snapshot(copy.deepcopy(start))
    b = GhostAPI.from_snapshot(copy.deepcopy(start))
    pa = a.apply_layered_event(
        "player",
        "guard",
        {"type": "betrayal", "intensity": 0.70},
    )
    pb = b.apply_layered_event(
        "player",
        "guard",
        {"type": "betrayal", "intensity": 0.70},
    )
    assert pa == pb
    assert a.snapshot() == b.snapshot()
