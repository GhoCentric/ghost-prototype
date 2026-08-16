import copy
import math

import pytest

from ghost import GhostAPI
from ghost.emotions import (
    DEFAULT_SPOTLIGHT_SWITCH_MARGIN,
    EmotionRuntime,
)


def state(runtime, agent="guard"):
    return runtime.get_state(agent)


def test_default_spotlight_switch_margin_is_explicit():
    runtime = EmotionRuntime()
    runtime.register_agent("guard", initial={"anger": 0.60})
    assert state(runtime)["spotlight_switch_margin"] == pytest.approx(0.05)
    assert DEFAULT_SPOTLIGHT_SWITCH_MARGIN == pytest.approx(0.05)


def test_initial_spotlight_acquires_raw_leader_without_hysteresis_delay():
    runtime = EmotionRuntime()
    runtime.register_agent("guard", initial={"anger": 0.60, "hope": 0.58})
    current = state(runtime)
    assert current["raw_leader_emotion"] == "anger"
    assert current["dominant_emotion"] == "anger"


def test_near_tied_challenger_does_not_steal_spotlight():
    runtime = EmotionRuntime()
    runtime.register_agent("guard", initial={"anger": 0.60, "hope": 0.58})
    runtime.register_agent("guard", initial={"anger": 0.55, "hope": 0.599})
    current = state(runtime)
    assert current["raw_leader_emotion"] == "hope"
    assert current["raw_leader_salience"] == pytest.approx(0.599)
    assert current["dominant_emotion"] == "anger"
    assert current["dominant_salience"] == pytest.approx(0.55)


def test_challenger_switches_when_advantage_reaches_margin():
    runtime = EmotionRuntime()
    runtime.register_agent("guard", initial={"anger": 0.60, "hope": 0.55})
    runtime.register_agent("guard", initial={"anger": 0.55, "hope": 0.60})
    current = state(runtime)
    assert current["raw_leader_emotion"] == "hope"
    assert current["dominant_emotion"] == "hope"


def test_custom_larger_margin_requires_larger_advantage():
    runtime = EmotionRuntime()
    runtime.register_agent(
        "guard",
        initial={"anger": 0.60, "hope": 0.50},
        spotlight_switch_margin=0.10,
    )
    runtime.register_agent("guard", initial={"anger": 0.52, "hope": 0.60})
    current = state(runtime)
    assert current["raw_leader_emotion"] == "hope"
    assert current["dominant_emotion"] == "anger"


def test_zero_margin_behaves_like_raw_max_selection():
    runtime = EmotionRuntime()
    runtime.register_agent(
        "guard",
        initial={"anger": 0.60, "hope": 0.50},
        spotlight_switch_margin=0.0,
    )
    runtime.register_agent("guard", initial={"anger": 0.550, "hope": 0.551})
    current = state(runtime)
    assert current["raw_leader_emotion"] == "hope"
    assert current["dominant_emotion"] == "hope"


def test_inactive_incumbent_releases_spotlight_even_with_max_margin():
    runtime = EmotionRuntime()
    runtime.register_agent(
        "guard",
        initial={"anger": 0.40},
        spotlight_switch_margin=1.0,
    )
    runtime.register_agent("guard", initial={"anger": 0.0, "hope": 0.01})
    current = state(runtime)
    assert current["dominant_emotion"] == "hope"


def test_zero_vector_clears_spotlight():
    runtime = EmotionRuntime()
    runtime.register_agent("guard", initial={"anger": 0.40})
    runtime.register_agent("guard", initial={"anger": 0.0})
    current = state(runtime)
    assert current["raw_leader_emotion"] is None
    assert current["dominant_emotion"] is None
    assert current["dominant_salience"] == pytest.approx(0.0)


def test_salience_bias_participates_in_hysteresis_not_raw_level_only():
    runtime = EmotionRuntime()
    runtime.register_agent("guard", initial={"anger": 0.60, "fear": 0.40})
    runtime.register_agent(
        "guard",
        salience_bias={"anger": 0.90, "fear": 1.45},
    )
    current = state(runtime)
    assert current["levels"]["anger"] > current["levels"]["fear"]
    assert current["raw_leader_emotion"] == "fear"
    assert current["raw_leader_salience"] == pytest.approx(0.58)
    assert current["dominant_emotion"] == "anger"
    assert current["dominant_salience"] == pytest.approx(0.54)


def test_salience_bias_switches_after_margin_is_crossed():
    runtime = EmotionRuntime()
    runtime.register_agent("guard", initial={"anger": 0.60, "fear": 0.40})
    runtime.register_agent(
        "guard",
        salience_bias={"anger": 0.80, "fear": 1.50},
    )
    current = state(runtime)
    assert current["raw_leader_salience"] == pytest.approx(0.60)
    assert current["dominant_salience"] == pytest.approx(0.60)
    assert current["dominant_emotion"] == "fear"


def test_apology_near_tie_retains_anger_even_when_hope_is_raw_leader():
    runtime = EmotionRuntime()
    for event in ("help", "help", "threat", "betrayal", "help", "apology"):
        packet = runtime.apply_event("guard", event, source="player")
    current = state(runtime)
    assert current["raw_leader_emotion"] == "hope"
    assert current["raw_leader_salience"] == pytest.approx(0.59486475)
    assert current["dominant_emotion"] == "anger"
    assert current["dominant_salience"] == pytest.approx(0.5484375)
    assert packet["spotlight_transition"]["switch_reason"] == "hysteresis_retained"
    assert packet["spotlight_transition"]["spotlight_changed"] is False


def test_next_tick_switches_from_anger_to_grief_when_margin_is_crossed():
    runtime = EmotionRuntime()
    for event in ("help", "help", "threat", "betrayal", "help", "apology"):
        runtime.apply_event("guard", event, source="player")
    tick = runtime.tick("guard")
    current = state(runtime)
    assert current["raw_leader_emotion"] == "grief"
    assert current["dominant_emotion"] == "grief"
    transition = tick["agents"][0]["spotlight_transition"]
    assert transition["previous_spotlight"] == "anger"
    assert transition["resolved_spotlight"] == "grief"
    assert transition["switch_reason"] == "margin_crossed"


def test_default_betrayal_decay_still_hands_off_to_grief_deterministically():
    runtime = EmotionRuntime()
    runtime.apply_event("guard", "betrayal")
    assert state(runtime)["dominant_emotion"] == "anger"
    runtime.tick("guard")
    assert state(runtime)["dominant_emotion"] == "anger"
    runtime.tick("guard")
    assert state(runtime)["dominant_emotion"] == "grief"


def test_spotlight_rows_mark_active_incumbent_even_if_raw_leader_differs():
    runtime = EmotionRuntime()
    for event in ("help", "help", "threat", "betrayal", "help", "apology"):
        runtime.apply_event("guard", event)
    current = state(runtime)
    assert current["raw_leader_emotion"] == "hope"
    assert current["dominant_emotion"] == "anger"
    active = [row for row in current["spotlight"] if row["active"]]
    assert len(active) == 1
    assert active[0]["emotion"] == "anger"
    assert current["spotlight"][0]["emotion"] == "hope"


def test_get_state_is_read_only_and_does_not_advance_spotlight():
    runtime = EmotionRuntime()
    for event in ("betrayal", "help", "apology"):
        runtime.apply_event("guard", event)
    before = copy.deepcopy(runtime.snapshot())
    first = runtime.get_state("guard")
    second = runtime.get_state("guard")
    assert first == second
    assert runtime.snapshot() == before


def test_event_history_records_hysteresis_decision():
    runtime = EmotionRuntime()
    for event in ("help", "help", "threat", "betrayal", "help", "apology"):
        runtime.apply_event("guard", event)
    record = state(runtime)["history"][-1]
    assert record["previous_spotlight"] == "anger"
    assert record["raw_leader_emotion"] == "hope"
    assert record["dominant_emotion"] == "anger"
    assert record["spotlight_changed"] is False
    assert record["spotlight_switch_reason"] == "hysteresis_retained"


def test_tick_packet_reports_spotlight_handoff():
    runtime = EmotionRuntime()
    runtime.apply_event("guard", "betrayal")
    runtime.tick("guard")
    packet = runtime.tick("guard")
    transition = packet["agents"][0]["spotlight_transition"]
    assert transition["previous_spotlight"] == "anger"
    assert transition["resolved_spotlight"] == "grief"
    assert transition["spotlight_changed"] is True


def test_v11_snapshot_round_trip_preserves_spotlight_and_margin_exactly():
    runtime = EmotionRuntime()
    runtime.register_agent(
        "guard",
        initial={"anger": 0.60, "hope": 0.55},
        spotlight_switch_margin=0.12,
    )
    runtime.register_agent("guard", initial={"anger": 0.50, "hope": 0.60})
    snapshot = runtime.snapshot()
    assert snapshot["schema_version"] == "1.1"
    restored = EmotionRuntime.from_snapshot(copy.deepcopy(snapshot))
    assert restored.snapshot() == snapshot
    assert restored.get_state("guard")["dominant_emotion"] == "anger"


def test_legacy_v10_snapshot_migrates_with_default_margin_and_resolved_spotlight():
    runtime = EmotionRuntime()
    runtime.register_agent("guard", initial={"anger": 0.40, "fear": 0.70})
    legacy = runtime.snapshot()
    legacy["schema_version"] = "1.0"
    for raw_state in legacy["agents"].values():
        raw_state.pop("spotlight_emotion")
        raw_state.pop("spotlight_switch_margin")
    restored = EmotionRuntime.from_snapshot(copy.deepcopy(legacy))
    current = restored.get_state("guard")
    assert current["spotlight_switch_margin"] == pytest.approx(0.05)
    assert current["dominant_emotion"] == "fear"
    assert restored.snapshot()["schema_version"] == "1.1"


def test_snapshot_restore_continuation_is_exact_across_hysteresis_handoff():
    runtime = EmotionRuntime()
    for event in ("help", "help", "threat", "betrayal", "help", "apology"):
        runtime.apply_event("guard", event)
    snapshot = runtime.snapshot()
    a = EmotionRuntime.from_snapshot(copy.deepcopy(snapshot))
    b = EmotionRuntime.from_snapshot(copy.deepcopy(snapshot))
    for _ in range(4):
        a.tick("guard")
        b.tick("guard")
    assert a.snapshot() == b.snapshot()
    assert a.get_state("guard")["dominant_emotion"] == b.get_state("guard")["dominant_emotion"]


@pytest.mark.parametrize("value", [-0.01, 1.01, float("inf"), float("nan"), True])
def test_invalid_spotlight_switch_margin_is_rejected(value):
    runtime = EmotionRuntime()
    with pytest.raises(ValueError):
        runtime.register_agent("guard", spotlight_switch_margin=value)


def test_reregistering_margin_does_not_erase_emotional_history():
    runtime = EmotionRuntime()
    runtime.apply_event("guard", "betrayal")
    before = copy.deepcopy(state(runtime)["history"])
    runtime.register_agent("guard", spotlight_switch_margin=0.20)
    current = state(runtime)
    assert current["history"] == before
    assert current["spotlight_switch_margin"] == pytest.approx(0.20)


def test_custom_emotions_use_same_hysteresis_rule():
    runtime = EmotionRuntime()
    runtime.register_agent(
        "scholar",
        initial={"curiosity": 0.60, "wonder": 0.58},
    )
    runtime.register_agent(
        "scholar",
        initial={"curiosity": 0.55, "wonder": 0.599},
    )
    current = runtime.get_state("scholar")
    assert current["raw_leader_emotion"] == "wonder"
    assert current["dominant_emotion"] == "curiosity"


def test_ghost_api_exposes_margin_and_layered_spotlight_metadata():
    ghost = GhostAPI()
    configured = ghost.register_emotional_agent(
        "guard",
        spotlight_switch_margin=0.15,
    )
    assert configured["spotlight_switch_margin"] == pytest.approx(0.15)
    packet = ghost.apply_layered_event(
        "player",
        "guard",
        {"type": "betrayal", "intensity": 1.0},
    )
    layered = packet["layered_state"]
    assert layered["spotlight_switch_margin"] == pytest.approx(0.15)
    assert layered["dominant_emotion"] == "anger"
    assert layered["raw_leader_emotion"] == "anger"
