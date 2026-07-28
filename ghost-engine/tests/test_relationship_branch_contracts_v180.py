"""Behavior contracts for RelationshipGraph edge cases."""

from __future__ import annotations

import pytest

from ghost.engine import GhostEngine
from ghost.relationships import RelationshipGraph


def test_unknown_personality_is_rejected_without_creating_state():
    engine = GhostEngine()
    before = engine.snapshot()

    with pytest.raises(
        ValueError,
        match="Unknown personality: invented",
    ):
        engine.relationships.set_personality(
            "player",
            "npc",
            "invented",
        )

    assert engine.snapshot() == before


def test_apply_delta_rejects_non_mapping_without_creating_pair():
    engine = GhostEngine()
    before = engine.snapshot()

    with pytest.raises(
        ValueError,
        match="Relationship deltas must be a dict",
    ):
        engine.relationships.apply_delta(
            "player",
            "npc",
            ["not", "a", "mapping"],
        )

    assert engine.snapshot() == before


def test_unknown_event_is_rejected_before_pair_creation():
    engine = GhostEngine()
    before = engine.snapshot()

    with pytest.raises(
        ValueError,
        match="Unknown relationship event: invented",
    ):
        engine.apply_event(
            "player",
            "npc",
            "invented",
        )

    assert engine.snapshot() == before


def test_invalid_event_map_channel_is_rejected_before_pair_creation(
    monkeypatch,
):
    engine = GhostEngine()
    before = engine.snapshot()

    monkeypatch.setitem(
        RelationshipGraph.RELATIONSHIP_EVENT_MAP,
        "invalid_channel_event",
        ("unexpected", 0.10),
    )

    with pytest.raises(
        RuntimeError,
        match="unsupported channel: unexpected",
    ):
        engine.apply_event(
            "player",
            "npc",
            "invalid_channel_event",
        )

    assert engine.snapshot() == before


def test_parameter_validation_supports_positive_fields_and_rejects_unknowns():
    engine = GhostEngine()

    engine.relationships.set_params(
        "player",
        "npc",
        relative_shock_ratio=3.0,
    )

    stored = engine.relationships.get(
        "player",
        "npc",
    )

    assert stored["relative_shock_ratio"] == 3.0

    with pytest.raises(
        ValueError,
        match="Unknown relationship parameter: invented",
    ):
        engine.relationships.set_params(
            "player",
            "npc",
            invented=1.0,
        )


def test_negative_trust_delta_updates_negative_reservoir_exactly():
    engine = GhostEngine()

    engine.relationships.apply_delta(
        "player",
        "npc",
        {"trust": -0.25},
    )

    raw = engine.relationships.get(
        "player",
        "npc",
    )

    assert raw["neg"] == pytest.approx(0.25)
    assert raw["trust"] == pytest.approx(-0.25)


def test_tick_reports_deescalation_when_hostility_decays_to_neutral():
    engine = GhostEngine()

    engine.apply_event(
        "player",
        "npc",
        "betrayal",
    )

    engine.relationships.set_params(
        "player",
        "npc",
        neg_decay=0.0,
    )

    packet = engine.tick()
    relationship = packet["relationships"][0]

    assert relationship["transition"] == (
        "hostile",
        "neutral",
    )

    assert relationship["trigger"] == {
        "event": "deescalation",
    }

    assert relationship["diagnostics"]["pressure"] == (
        "deescalating"
    )


def test_pressure_falls_back_to_delta_for_unknown_trigger():
    graph = RelationshipGraph({})

    pressure = graph._pressure_label(
        trigger={"event": "future_event"},
        delta=-0.60,
        after_state="neutral",
        after_trust=0.0,
    )

    assert pressure == "major_negative_shift"


def test_positive_social_propagation_increases_observer_trust():
    engine = GhostEngine()

    packet = engine.propagate_social_event(
        source="player",
        target="shopkeeper",
        event="help",
        observers=["guard"],
        weights={"guard": 1.0},
    )

    assert (
        packet["direct"]["diagnostics"]["direction"]
        == "positive"
    )

    assert len(packet["propagated"]) == 1
    assert packet["propagated"][0]["affected"] == "guard"
    assert packet["propagated"][0]["trust_delta"] > 0.0

    assert (
        engine.get_relationship(
            "player",
            "guard",
        )["trust"]
        > 0.0
    )


def test_negative_social_propagation_can_shift_observer_state():
    engine = GhostEngine()

    engine.apply_event(
        "player",
        "guard",
        "help",
    )

    packet = engine.propagate_social_event(
        source="player",
        target="shopkeeper",
        event="betrayal",
        observers=["guard"],
        weights={"guard": 1.0},
    )

    observer = packet["propagated"][0]["relationship"]

    assert observer["transition"] == (
        "friendly",
        "neutral",
    )

    assert observer["trigger"] == {
        "event": "state_shift",
    }

    assert observer["diagnostics"]["direction"] == "negative"


def test_social_heat_adds_state_shift_bonus():
    engine = GhostEngine()

    engine.apply_event(
        "player",
        "shopkeeper",
        "help",
    )

    packet = engine.propagate_social_event(
        source="player",
        target="shopkeeper",
        event="insult",
        observers=["guard"],
        weights={"guard": 1.0},
    )

    diagnostics = packet["direct"]["diagnostics"]

    assert diagnostics["pressure"] == "state_shift"

    assert packet["heat"] == pytest.approx(
        diagnostics["severity"] + 0.10,
    )


def test_major_negative_shift_adds_social_heat_without_state_transition():
    engine = GhostEngine()

    engine.relationships.apply_delta(
        "player",
        "shopkeeper",
        {"trust": 2.0},
    )

    engine.get_relationship(
        "player",
        "shopkeeper",
    )

    packet = engine.propagate_social_event(
        source="player",
        target="shopkeeper",
        event="betrayal",
        observers=["guard"],
        weights={"guard": 1.0},
    )

    diagnostics = packet["direct"]["diagnostics"]

    assert diagnostics["pressure"] == "major_negative_shift"

    assert packet["heat"] == pytest.approx(
        diagnostics["severity"] + 0.15,
    )


def test_mature_negative_event_without_recent_baseline_skips_relative_shock():
    engine = GhostEngine()

    engine.relationships.set_params(
        "player",
        "shopkeeper",
        maturity=0.50,
        pos=1.0,
        recent_event_magnitude=0.0,
    )

    relationship = engine.apply_event(
        "player",
        "shopkeeper",
        "betrayal",
    )

    diagnostics = relationship["diagnostics"]

    assert diagnostics["high_severity_shock"] is True
    assert diagnostics["relative_shock"] is False


def test_zero_social_delta_preserves_relationship_reservoirs():
    graph = RelationshipGraph({})

    graph.ensure_pair(
        "player",
        "guard",
    )

    before = graph.get(
        "player",
        "guard",
    )

    packet = graph._apply_social_delta(
        source="player",
        affected="guard",
        trust_delta=0.0,
        source_event="neutral",
        source_pressure="stable",
        heat=0.0,
    )

    after = graph.get(
        "player",
        "guard",
    )

    assert packet["trust_delta"] == 0.0
    assert after["pos"] == before["pos"]
    assert after["neg"] == before["neg"]
    assert after["trust"] == before["trust"]

    assert (
        packet["relationship"]["diagnostics"]["pressure"]
        == "stable"
    )


def test_social_propagation_skips_source_and_target_observers():
    engine = GhostEngine()

    packet = engine.propagate_social_event(
        source="player",
        target="shopkeeper",
        event="betrayal",
        observers=[
            "player",
            "shopkeeper",
            "guard",
        ],
        weights={"guard": 1.0},
    )

    assert [
        item["affected"]
        for item in packet["propagated"]
    ] == ["guard"]


def test_zero_gain_social_event_has_no_observer_effects():
    engine = GhostEngine()

    engine.relationships.set_params(
        "player",
        "shopkeeper",
        pos_gain=0.0,
    )

    packet = engine.relationships.propagate_social_event(
        source="player",
        target="shopkeeper",
        event="greet",
        observers=["guard"],
        weights={"guard": 1.0},
    )

    assert (
        packet["direct"]["diagnostics"]["direction"]
        == "stable"
    )

    assert packet["propagated"] == []

    assert engine.relationships.get(
        "player",
        "guard",
    ) is None


def test_social_propagation_log_is_bounded_and_returns_copy_of_list():
    engine = GhostEngine()

    for index in range(26):
        engine.propagate_social_event(
            source="player",
            target=f"target_{index}",
            event="greet",
        )

    log = engine.relationships.propagation_log()

    assert len(log) == 25
    assert log[0]["target"] == "target_1"
    assert log[-1]["target"] == "target_25"

    log.clear()

    assert len(
        engine.relationships.propagation_log()
    ) == 25
