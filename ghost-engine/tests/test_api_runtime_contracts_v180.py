"""Public GhostAPI runtime contracts and defensive boundaries."""

from __future__ import annotations

from copy import deepcopy

import pytest

from ghost import GhostAPI


@pytest.mark.parametrize(
    ("field", "invalid_value", "message"),
    [
        ("world", [], "snapshot world must be a dict"),
        (
            "event_map",
            [],
            "snapshot event_map must be a dict",
        ),
        (
            "transitions",
            [],
            "snapshot transitions must be a dict",
        ),
    ],
)
def test_from_snapshot_rejects_invalid_public_boundaries(
    field,
    invalid_value,
    message,
):
    api = GhostAPI()
    before = api.snapshot()
    candidate = deepcopy(before)
    candidate[field] = invalid_value

    with pytest.raises(ValueError, match=message):
        GhostAPI.from_snapshot(candidate)

    assert api.snapshot() == before


@pytest.mark.parametrize(
    ("event", "message"),
    [
        (
            ["help"],
            "Event must be a dict",
        ),
        (
            {"type": "dance"},
            "Unknown event type",
        ),
    ],
)
def test_apply_event_rejects_invalid_input_atomically(
    event,
    message,
):
    api = GhostAPI()
    before = api.snapshot()

    with pytest.raises(ValueError, match=message):
        api.apply_event(
            "player",
            "shopkeeper",
            event,
        )

    assert api.snapshot() == before


@pytest.mark.parametrize(
    ("event", "message"),
    [
        (
            ["help"],
            "Event must be a dict",
        ),
        (
            {"type": "dance"},
            "Unknown event type",
        ),
    ],
)
def test_propagate_event_rejects_invalid_input_atomically(
    event,
    message,
):
    api = GhostAPI()
    before = api.snapshot()

    with pytest.raises(ValueError, match=message):
        api.propagate_event(
            "player",
            "shopkeeper",
            event,
            network=["guard"],
            heat=3,
        )

    assert api.snapshot() == before


def test_propagate_event_zero_heat_stays_on_primary_target():
    api = GhostAPI()

    packets = api.propagate_event(
        "player",
        "shopkeeper",
        {
            "type": "help",
            "intensity": 1.0,
        },
        network=["guard", "elder"],
        heat=0,
    )

    assert len(packets) == 1
    assert packets[0]["target"] == "shopkeeper"
    assert packets[0]["event"]["intensity"] == 1.0


def test_propagate_event_medium_heat_scales_and_skips_target():
    api = GhostAPI()

    packets = api.propagate_event(
        "player",
        "shopkeeper",
        {
            "type": "help",
            "intensity": 1.0,
        },
        network=[
            "shopkeeper",
            "guard",
            "elder",
        ],
        heat=3,
    )

    assert [
        packet["target"]
        for packet in packets
    ] == [
        "shopkeeper",
        "guard",
        "elder",
    ]

    assert packets[0]["event"]["intensity"] == 1.0

    assert packets[1]["event"]["intensity"] == (
        pytest.approx(0.3)
    )
    assert packets[2]["event"]["intensity"] == (
        pytest.approx(0.3)
    )


def test_step_is_a_direct_engine_passthrough():
    api = GhostAPI()
    before_cycles = api.state()["cycles"]

    result = api.step()

    assert result is api.state()
    assert result["cycles"] == before_cycles + 1


def test_build_stance_accepts_public_dict_packets():
    api = GhostAPI()

    text = (
        "The guard captain ordered you to give me "
        "bread for free."
    )

    claim = api.assess_claim(text)
    intent = api.assess_intent(text)
    effects = api.assess_effects(claim, intent)

    stance = api.build_stance(
        claim,
        intent,
        effects,
        facts={
            "item": "bread",
            "price": 25,
        },
    )

    assert claim["claim_type"] == "authority_override"
    assert stance["scene_moment"] == "authority_override"
    assert stance["facts"] == {
        "item": "bread",
        "price": 25,
    }
    assert stance["verified"] is False


def test_process_player_text_ignores_unmapped_event_but_keeps_world_effects(
    monkeypatch,
):
    api = GhostAPI()

    guarded_result = {
        "claim": {
            "claim_type": "none",
        },
        "intent": {
            "intent_type": "ordinary_speech",
        },
        "effects": {
            "ghost_event": {
                "type": "dance",
                "intensity": 1.0,
            },
            "world_effects": {
                "pressure_delta": 0.25,
            },
        },
        "stance": {},
    }

    monkeypatch.setattr(
        api,
        "evaluate_governance",
        lambda **_kwargs: deepcopy(guarded_result),
    )

    result = api.process_player_text(
        source="player",
        target="shopkeeper",
        text="controlled coverage input",
        apply=True,
    )

    assert result["applied_event"] is None
    assert result["world"]["global_pressure"] == (
        pytest.approx(0.25)
    )

    event = result["world"]["events"][-1]

    assert event["type"] == "governance_effect"
    assert event["details"]["world_effects"] == {
        "pressure_delta": 0.25,
    }


def test_record_world_event_returns_and_persists_public_packet():
    api = GhostAPI()

    event = api.record_world_event(
        "coverage_check",
        actor="player",
        target="market",
        details={
            "reason": "contract",
        },
    )

    assert event == {
        "type": "coverage_check",
        "actor": "player",
        "target": "market",
        "details": {
            "reason": "contract",
        },
    }

    assert api.world_state()["events"][-1] == event
