import copy

import pytest

from ghost import GhostAPI
from ghost.emotions import EmotionRuntime


def levels(runtime, agent="guard"):
    return runtime.get_state(agent)["levels"]


def test_repeated_positive_impulses_saturate_monotonically_without_overshoot():
    runtime = EmotionRuntime()
    seen = []
    for _ in range(20):
        runtime.apply_event("guard", "threat")
        seen.append(levels(runtime)["fear"])
    assert all(a < b for a, b in zip(seen, seen[1:]))
    assert all(0.0 <= value <= 1.0 for value in seen)
    assert seen[-1] < 1.0
    assert seen[-1] > 0.999


def test_positive_saturation_produces_diminishing_returns():
    runtime = EmotionRuntime()
    deltas = []
    for _ in range(5):
        packet = runtime.apply_event("guard", "help")
        deltas.append(packet["deltas"]["hope"])
    assert all(a > b > 0.0 for a, b in zip(deltas, deltas[1:]))


def test_apology_reduces_but_does_not_erase_betrayal_anger():
    runtime = EmotionRuntime()
    runtime.apply_event("guard", "betrayal")
    before = levels(runtime)["anger"]
    packet = runtime.apply_event("guard", "apology")
    after = packet["after"]["anger"]
    assert before == pytest.approx(0.75)
    assert after == pytest.approx(0.5625)
    assert 0.0 < after < before


def test_help_after_betrayal_can_add_hope_while_anger_and_grief_persist():
    runtime = EmotionRuntime()
    runtime.apply_event("guard", "betrayal")
    runtime.apply_event("guard", "help")
    state = runtime.get_state("guard")
    assert state["levels"]["hope"] == pytest.approx(0.35)
    assert state["levels"]["joy"] == pytest.approx(0.25)
    assert state["levels"]["anger"] > 0.60
    assert state["levels"]["grief"] > 0.60


def test_default_inertia_can_move_spotlight_from_anger_to_grief_over_time():
    runtime = EmotionRuntime()
    runtime.apply_event("guard", "betrayal")
    assert runtime.get_state("guard")["dominant_emotion"] == "anger"
    runtime.tick("guard", steps=2)
    state = runtime.get_state("guard")
    assert state["dominant_emotion"] == "grief"
    assert state["levels"]["grief"] > state["levels"]["anger"]


def test_multi_step_tick_matches_repeated_single_ticks():
    a = EmotionRuntime()
    b = EmotionRuntime()
    for runtime in (a, b):
        runtime.apply_event("guard", "betrayal")
    a.tick("guard", steps=9)
    for _ in range(9):
        b.tick("guard")
    assert levels(a) == pytest.approx(levels(b))


def test_inertia_one_holds_level_and_inertia_zero_jumps_to_baseline():
    runtime = EmotionRuntime()
    runtime.register_agent(
        "guard",
        initial={"anger": 0.80, "fear": 0.90},
        baseline={"anger": 0.20, "fear": 0.30},
        inertia={"anger": 1.0, "fear": 0.0},
    )
    runtime.tick("guard", steps=12)
    state = levels(runtime)
    assert state["anger"] == pytest.approx(0.80)
    assert state["fear"] == pytest.approx(0.30)


def test_tick_recovers_upward_toward_nonzero_baseline_without_overshoot():
    runtime = EmotionRuntime()
    runtime.register_agent(
        "guard",
        initial={"hope": 0.0},
        baseline={"hope": 0.60},
        inertia={"hope": 0.50},
    )
    seen = []
    for _ in range(6):
        runtime.tick("guard")
        seen.append(levels(runtime)["hope"])
    assert all(a < b for a, b in zip(seen, seen[1:]))
    assert all(value < 0.60 for value in seen)
    assert seen[0] == pytest.approx(0.30)


def test_channels_decay_independently_according_to_their_own_inertia():
    runtime = EmotionRuntime()
    runtime.register_agent(
        "guard",
        initial={"anger": 0.8, "fear": 0.8, "grief": 0.8},
        inertia={"anger": 0.2, "fear": 0.5, "grief": 0.9},
    )
    runtime.tick("guard")
    state = levels(runtime)
    assert state["anger"] == pytest.approx(0.16)
    assert state["fear"] == pytest.approx(0.40)
    assert state["grief"] == pytest.approx(0.72)


def test_level_at_one_remains_bounded_and_can_be_reduced_by_opposite_impulse():
    runtime = EmotionRuntime()
    runtime.register_agent("guard", initial={"anger": 1.0})
    runtime.apply_event("guard", "betrayal")
    assert levels(runtime)["anger"] == pytest.approx(1.0)
    runtime.apply_event("guard", "apology")
    assert levels(runtime)["anger"] == pytest.approx(0.75)


def test_salience_bias_can_make_lower_level_emotion_win_spotlight():
    runtime = EmotionRuntime()
    runtime.register_agent(
        "guard",
        initial={"anger": 0.70, "fear": 0.40},
        salience_bias={"anger": 0.40, "fear": 2.00},
    )
    state = runtime.get_state("guard")
    assert state["levels"]["anger"] > state["levels"]["fear"]
    assert state["dominant_emotion"] == "fear"
    assert state["dominant_salience"] == pytest.approx(0.80)


def test_equal_salience_tie_break_is_stable_and_alphabetical():
    runtime = EmotionRuntime()
    runtime.register_agent("guard", initial={"anger": 0.50, "fear": 0.50})
    state = runtime.get_state("guard")
    assert state["dominant_emotion"] == "anger"
    assert [row["emotion"] for row in state["spotlight"][:2]] == ["anger", "fear"]


def test_zero_vector_has_no_dominant_emotion_and_zero_spotlight_shares():
    runtime = EmotionRuntime()
    runtime.register_agent("guard")
    state = runtime.get_state("guard")
    assert state["dominant_emotion"] is None
    assert state["dominant_salience"] == pytest.approx(0.0)
    assert all(row["share"] == pytest.approx(0.0) for row in state["spotlight"])


def test_zero_intensity_records_event_without_changing_levels():
    runtime = EmotionRuntime()
    runtime.register_agent("guard", initial={"anger": 0.35, "hope": 0.25})
    before = copy.deepcopy(levels(runtime))
    packet = runtime.apply_event("guard", "betrayal", intensity=0.0)
    assert packet["after"] == before
    assert len(runtime.get_state("guard")["history"]) == 1
    assert all(delta == pytest.approx(0.0) for delta in packet["deltas"].values())


def test_half_intensity_scales_first_impulse_exactly_from_zero():
    runtime = EmotionRuntime()
    packet = runtime.apply_event("guard", "betrayal", intensity=0.5)
    assert packet["after"]["anger"] == pytest.approx(0.375)
    assert packet["after"]["fear"] == pytest.approx(0.10)
    assert packet["after"]["grief"] == pytest.approx(0.325)


def test_sensitivity_and_context_are_multiplicative():
    base = EmotionRuntime()
    tuned = EmotionRuntime()
    tuned.register_agent("guard", sensitivities={"fear": 2.0})
    p1 = base.apply_event("guard", "threat")
    p2 = tuned.apply_event("guard", "threat", context_modifiers={"fear": 0.5})
    assert p2["after"]["fear"] == pytest.approx(p1["after"]["fear"])
    assert p2["effective_impulses"]["fear"] == pytest.approx(p1["effective_impulses"]["fear"])


def test_extreme_sensitivity_still_clamps_level_to_one():
    runtime = EmotionRuntime()
    runtime.register_agent("guard", sensitivities={"fear": 100.0})
    runtime.apply_event("guard", "threat")
    assert levels(runtime)["fear"] == pytest.approx(1.0)


def test_custom_emotion_uses_generic_inertia_when_not_overridden():
    runtime = EmotionRuntime()
    runtime.apply_event(
        "guard",
        "neutral",
        impulse_overrides={"curiosity": 0.80},
    )
    assert levels(runtime)["curiosity"] == pytest.approx(0.80)
    runtime.tick("guard")
    assert levels(runtime)["curiosity"] == pytest.approx(0.80 * 0.85)


def test_custom_profile_survives_snapshot_restore():
    runtime = EmotionRuntime()
    runtime.configure_event_profile("discovery", {"curiosity": 0.70, "fear": 0.10})
    runtime.apply_event("guard", "discovery")
    restored = EmotionRuntime.from_snapshot(copy.deepcopy(runtime.snapshot()))
    assert restored.get_event_profile("discovery") == {"curiosity": 0.70, "fear": 0.10}
    assert restored.snapshot() == runtime.snapshot()


def test_history_limit_rolls_forward_with_monotonic_sequence_numbers():
    runtime = EmotionRuntime(history_limit=3)
    for event in ("help", "threat", "apology", "betrayal", "gift"):
        runtime.apply_event("guard", event)
    history = runtime.get_state("guard")["history"]
    assert len(history) == 3
    assert [row["sequence"] for row in history] == [3, 4, 5]
    assert [row["event"] for row in history] == ["apology", "betrayal", "gift"]


def test_reregistering_agent_changes_parameters_without_erasing_history():
    runtime = EmotionRuntime()
    runtime.apply_event("guard", "betrayal")
    before_history = copy.deepcopy(runtime.get_state("guard")["history"])
    runtime.register_agent("guard", sensitivities={"fear": 2.0}, inertia={"grief": 0.99})
    state = runtime.get_state("guard")
    assert state["history"] == before_history
    assert state["sensitivities"]["fear"] == pytest.approx(2.0)
    assert state["inertia"]["grief"] == pytest.approx(0.99)


def test_snapshot_restore_continue_is_exact_through_contradictory_sequence_and_ticks():
    runtime = EmotionRuntime()
    runtime.register_agent(
        "guard",
        sensitivities={"anger": 0.8, "fear": 1.4, "grief": 1.1},
        baseline={"hope": 0.10},
    )
    runtime.apply_event("guard", "help")
    runtime.apply_event("guard", "threat")
    runtime.tick("guard", steps=2)
    snap = runtime.snapshot()

    a = EmotionRuntime.from_snapshot(copy.deepcopy(snap))
    b = EmotionRuntime.from_snapshot(copy.deepcopy(snap))
    for item in ("betrayal", "apology", "help", "attack"):
        a.apply_event("guard", item)
        b.apply_event("guard", item)
    a.tick("guard", steps=7)
    b.tick("guard", steps=7)
    assert a.snapshot() == b.snapshot()


def test_relationship_only_event_does_not_silently_create_emotional_state():
    ghost = GhostAPI()
    ghost.apply_event("player", "guard", {"type": "help", "intensity": 1.0})
    assert ghost.emotional_state("guard") is None


def test_emotion_tick_does_not_modify_existing_relationship_state():
    ghost = GhostAPI()
    for _ in range(20):
        ghost.apply_event("player", "guard", {"type": "help", "intensity": 1.0})
    ghost.apply_layered_event("player", "guard", {"type": "betrayal", "intensity": 1.0})
    relationship_before = copy.deepcopy(ghost.get_relationship("player", "guard"))
    ghost.tick_emotions("guard", steps=12)
    relationship_after = ghost.get_relationship("player", "guard")
    assert relationship_after == relationship_before
    assert ghost.emotional_state("guard")["levels"]["anger"] < 0.75


def test_long_positive_recovery_can_change_spotlight_without_erasing_negative_history_immediately():
    runtime = EmotionRuntime()
    runtime.apply_event("guard", "betrayal")
    first = runtime.get_state("guard")
    assert first["dominant_emotion"] == "anger"

    runtime.apply_event("guard", "help")
    after_one = runtime.get_state("guard")
    assert after_one["levels"]["anger"] > 0.0
    assert after_one["levels"]["grief"] > 0.0

    for _ in range(5):
        runtime.apply_event("guard", "help")
    recovered = runtime.get_state("guard")
    assert recovered["levels"]["hope"] > recovered["levels"]["anger"]
    assert recovered["dominant_emotion"] in {"hope", "joy"}
