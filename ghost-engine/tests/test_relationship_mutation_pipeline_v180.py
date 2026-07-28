from copy import deepcopy
import inspect

import pytest

from ghost.api import (
    DEFAULT_EVENT_MAP,
    GhostAPI,
)
from ghost.engine import GhostEngine
from ghost.relationships import RelationshipGraph


def test_default_event_vocabulary_is_derived_from_relationship_specs_v180():
    assert DEFAULT_EVENT_MAP == (
        RelationshipGraph.public_event_map()
    )

    assert {
        "neutral",
        "greet",
        "help",
        "cooperate",
        "gift",
        "apology",
        "disengage",
        "pressure",
        "manipulate",
        "deceive",
        "insult",
        "threat",
        "theft",
        "attack",
        "betrayal",
    } == set(DEFAULT_EVENT_MAP)


def test_public_api_and_engine_share_public_event_resolution_v180():
    for event_type in sorted(
        DEFAULT_EVENT_MAP
    ):
        api = GhostAPI()
        engine = GhostEngine()

        if event_type == "apology":
            api.apply_event(
                "player",
                "merchant",
                {
                    "type": "threat",
                },
            )

            engine.apply_event(
                "player",
                "merchant",
                "threat",
            )

        api_packet = api.apply_event(
            "player",
            "merchant",
            {
                "type": event_type,
                "intensity": 0.50,
            },
        )

        engine_packet = engine.apply_event(
            "player",
            "merchant",
            event_type,
            intensity=0.50,
        )

        assert api_packet["mode"] == (
            "canonical_relationship_event"
        )

        assert (
            api_packet["relationship"]
            == engine_packet
        )

        assert isinstance(
            engine_packet["diagnostics"],
            dict,
        )


def test_previous_api_only_events_receive_fresh_diagnostics_v180():
    for event_type in (
        "cooperate",
        "disengage",
        "pressure",
        "manipulate",
        "deceive",
        "neutral",
    ):
        api = GhostAPI()

        packet = api.apply_event(
            "player",
            "merchant",
            {
                "type": event_type,
            },
        )

        relationship = packet[
            "relationship"
        ]

        assert packet["mode"] == (
            "canonical_relationship_event"
        )

        assert isinstance(
            relationship["diagnostics"],
            dict,
        )

        assert relationship["maturity"] > 0.0

        assert relationship[
            "diagnostics"
        ]["event"] == event_type


def test_previous_delta_event_replaces_stale_diagnostics_v180():
    api = GhostAPI()

    api.apply_event(
        "player",
        "merchant",
        {
            "type": "betrayal",
        },
    )

    packet = api.apply_event(
        "player",
        "merchant",
        {
            "type": "cooperate",
        },
    )

    diagnostics = packet[
        "relationship"
    ]["diagnostics"]

    assert diagnostics["event"] == "cooperate"
    assert diagnostics["delta"] > 0.0

    assert diagnostics["pressure"] != (
        "relationship_broken"
    )

    assert packet["trigger"] is None


def test_repeated_pressure_reports_real_hostile_transition_v180():
    api = GhostAPI()
    packet = None

    for _ in range(20):
        packet = api.apply_event(
            "player",
            "merchant",
            {
                "type": "pressure",
            },
        )

        if packet["state"] == "hostile":
            break

    assert packet is not None
    assert packet["state"] == "hostile"

    diagnostics = packet[
        "relationship"
    ]["diagnostics"]

    assert diagnostics["event"] == "pressure"

    assert diagnostics["transition"] == (
        "neutral",
        "hostile",
    )

    assert diagnostics["trigger"][
        "event"
    ] == "relationship_broken"


def test_attack_and_gift_are_available_through_both_layers_v180():
    for event_type in (
        "attack",
        "gift",
    ):
        api_packet = GhostAPI().apply_event(
            "player",
            "merchant",
            {
                "type": event_type,
            },
        )

        engine_packet = (
            GhostEngine().apply_event(
                "player",
                "merchant",
                event_type,
            )
        )

        assert (
            api_packet["relationship"]
            == engine_packet
        )


def test_custom_event_map_uses_relationship_pipeline_v180():
    api = GhostAPI(
        event_map={
            "custom_positive": {
                "trust": 0.123,
                "attachment": 0.045,
            },
        }
    )

    packet = api.apply_event(
        "player",
        "merchant",
        {
            "type": "custom_positive",
            "intensity": 0.50,
        },
    )

    relationship = packet[
        "relationship"
    ]

    raw = api.engine.relationships.get(
        "player",
        "merchant",
    )

    assert packet["mode"] == (
        "configured_relationship_event"
    )

    assert relationship["trust"] == (
        pytest.approx(0.0615)
    )

    assert relationship[
        "diagnostics"
    ]["delta"] == pytest.approx(
        0.0615
    )

    assert relationship["maturity"] > 0.0

    assert raw["attachment"] == (
        pytest.approx(0.0225)
    )


def test_custom_override_controls_actual_trust_v180():
    api = GhostAPI(
        event_map={
            "help": {
                "trust": 0.90,
            },
        }
    )

    packet = api.apply_event(
        "player",
        "merchant",
        {
            "type": "help",
        },
    )

    assert packet["mode"] == (
        "configured_relationship_event"
    )

    assert packet["trust"] == (
        pytest.approx(0.90)
    )

    assert packet["deltas"]["trust"] == (
        pytest.approx(0.90)
    )


def test_custom_negative_event_gets_transition_diagnostics_v180():
    api = GhostAPI(
        event_map={
            "custom_break": {
                "trust": -0.80,
                "attachment": -0.20,
            },
        }
    )

    packet = api.apply_event(
        "player",
        "merchant",
        {
            "type": "custom_break",
        },
    )

    diagnostics = packet[
        "relationship"
    ]["diagnostics"]

    assert diagnostics["event"] == (
        "custom_break"
    )

    assert diagnostics["direction"] == (
        "negative"
    )

    assert diagnostics["delta"] < 0.0
    assert diagnostics["severity"] > 0.0
    assert diagnostics["pressure"]


def test_public_apology_preserves_exact_recovery_contract_v180():
    api = GhostAPI()
    engine = GhostEngine()

    api.apply_event(
        "player",
        "merchant",
        {
            "type": "threat",
        },
    )

    engine.apply_event(
        "player",
        "merchant",
        "threat",
    )

    api_before = api.get_relationship(
        "player",
        "merchant",
    )["trust"]

    engine_before = engine.get_relationship(
        "player",
        "merchant",
    )["trust"]

    api_after = api.apply_event(
        "player",
        "merchant",
        {
            "type": "apology",
        },
    )["relationship"]

    engine_after = engine.apply_event(
        "player",
        "merchant",
        "apology",
    )

    assert api_after == engine_after

    assert (
        api_after["trust"]
        - api_before
    ) == pytest.approx(0.05)

    assert (
        engine_after["trust"]
        - engine_before
    ) == pytest.approx(0.05)

    assert api_after[
        "diagnostics"
    ]["event"] == "apology"


def test_direct_apologize_dynamic_event_remains_unchanged_v180():
    engine = GhostEngine()

    engine.apply_event(
        "player",
        "merchant",
        "greet",
    )

    before = engine.get_relationship(
        "player",
        "merchant",
    )["trust"]

    after = engine.apply_event(
        "player",
        "merchant",
        "apologize",
    )

    assert after["trust"] > before

    assert after[
        "diagnostics"
    ]["event"] == "apologize"


def test_public_apply_event_has_no_raw_delta_branch_v180():
    source = inspect.getsource(
        GhostAPI.apply_event
    )

    assert "apply_delta" not in source

    assert (
        "legacy_delta_event"
        not in source
    )

    assert (
        "self.engine.apply_event"
        in source
    )
