import json

from ghost import GhostAPI
from ghost.engine import GhostEngine
from ghost.threat_response import evaluate_threat_response


def hostile_relationship():
    engine = GhostEngine()

    return engine.apply_event(
        "player",
        "merchant",
        "threat",
    )


def test_threat_response_is_deterministic_and_json_safe():
    relationship = hostile_relationship()

    first = evaluate_threat_response(
        npc="civilian",
        relationship=relationship,
        temperament="anxious",
        context={
            "player_armed": True,
            "player_aiming": True,
            "escape_route": True,
        },
    )

    second = evaluate_threat_response(
        npc="civilian",
        relationship=relationship,
        temperament="anxious",
        context={
            "player_armed": True,
            "player_aiming": True,
            "escape_route": True,
        },
    )

    assert first == second
    assert first["response"] == "flee"

    json.dumps(first, sort_keys=True)


def test_threat_response_changes_when_escape_is_removed():
    relationship = hostile_relationship()

    escape = evaluate_threat_response(
        npc="civilian",
        relationship=relationship,
        temperament="anxious",
        context={
            "player_armed": True,
            "player_aiming": True,
            "escape_route": True,
        },
    )

    trapped = evaluate_threat_response(
        npc="civilian",
        relationship=relationship,
        temperament="anxious",
        context={
            "player_armed": True,
            "player_aiming": True,
            "escape_route": False,
        },
    )

    assert escape["response"] == "flee"
    assert trapped["response"] in ("freeze", "surrender")
    assert trapped["scores"]["surrender"] > escape["scores"]["surrender"]


def test_guard_context_prefers_calling_guards():
    relationship = hostile_relationship()

    packet = evaluate_threat_response(
        npc="guard",
        relationship=relationship,
        temperament="suspicious",
        context={
            "player_armed": True,
            "player_aiming": True,
            "guard_nearby": True,
            "authority_present": True,
            "crowd_size": 10,
        },
    )

    assert packet["response"] == "call_guards"


def test_armed_resentful_npc_can_fight():
    relationship = hostile_relationship()

    packet = evaluate_threat_response(
        npc="rival",
        relationship=relationship,
        temperament="resentful",
        context={
            "player_armed": True,
            "player_attacking": True,
            "npc_armed": True,
            "allies_nearby": 2,
            "escape_route": False,
        },
    )

    assert packet["response"] == "fight"


def test_threat_response_does_not_mutate_relationship_packet():
    relationship = hostile_relationship()
    before = json.dumps(relationship, sort_keys=True)

    evaluate_threat_response(
        npc="civilian",
        relationship=relationship,
        temperament="anxious",
        context={"player_aiming": True},
    )

    after = json.dumps(relationship, sort_keys=True)

    assert after == before


def test_public_api_can_read_live_npc_relationship():
    api = GhostAPI()

    api.apply_event(
        "player",
        "merchant",
        {"type": "threat", "intensity": 0.90},
    )

    packet = api.evaluate_npc_threat_response(
        npc="merchant",
        source="player",
        target="merchant",
        temperament="anxious",
        context={
            "player_armed": True,
            "player_aiming": True,
            "escape_route": True,
        },
    )

    assert packet["npc"] == "merchant"
    assert packet["response"] == "flee"


import math

import pytest


VALID_RESPONSES = {
    "fight",
    "call_guards",
    "confront",
    "surrender",
    "flee",
    "freeze",
    "warn",
    "ignore",
}


def test_threat_response_context_normalization_is_order_independent():
    relationship = hostile_relationship()

    left_context = {
        "player_armed": "true",
        "player_aiming": "1",
        "npc_armed": "false",
        "escape_route": "yes",
        "allies_nearby": "2",
        "crowd_size": "4",
    }

    right_context = {
        "crowd_size": "4",
        "allies_nearby": "2",
        "escape_route": "yes",
        "npc_armed": "false",
        "player_aiming": "1",
        "player_armed": "true",
    }

    left = evaluate_threat_response(
        npc="civilian",
        relationship=relationship,
        temperament="anxious",
        context=left_context,
    )

    right = evaluate_threat_response(
        npc="civilian",
        relationship=relationship,
        temperament="anxious",
        context=right_context,
    )

    assert left == right
    assert left["context"]["player_armed"] is True
    assert left["context"]["npc_armed"] is False


@pytest.mark.parametrize(
    "context",
    [
        None,
        [],
        "not a mapping",
        7,
        {
            "player_armed": "false",
            "player_aiming": "off",
            "player_attacking": "no",
            "npc_armed": "0",
            "escape_route": "true",
            "allies_nearby": -999,
            "crowd_size": "not-a-number",
        },
        {
            "allies_nearby": float("inf"),
            "crowd_size": float("-inf"),
        },
        {
            "allies_nearby": float("nan"),
            "crowd_size": float("nan"),
        },
    ],
)
def test_threat_response_survives_hostile_context_inputs(context):
    packet = evaluate_threat_response(
        npc="civilian",
        relationship=hostile_relationship(),
        temperament="anxious",
        context=context,
    )

    assert packet["response"] in VALID_RESPONSES
    assert set(packet["scores"]) == VALID_RESPONSES
    assert all(
        math.isfinite(score) and score >= 0.0
        for score in packet["scores"].values()
    )

    json.dumps(packet, sort_keys=True)


@pytest.mark.parametrize(
    "temperament",
    [
        "calm",
        "anxious",
        "resentful",
        "suspicious",
        {
            "name": "custom_test",
            "confidence": 0.90,
            "anxiety": 0.10,
            "suspicion": 0.20,
            "forgiveness": 0.50,
            "aggression": 0.80,
            "loyalty": 0.40,
            "attachment_bias": 0.50,
            "threat_sensitivity": 1.00,
            "social_sensitivity": 1.00,
            "pressure_sensitivity": 1.00,
            "authority_sensitivity": 1.00,
            "betrayal_sensitivity": 1.00,
            "recovery_bias": 0.50,
        },
    ],
)
def test_threat_response_output_schema_is_complete_for_profiles(
    temperament,
):
    packet = evaluate_threat_response(
        npc="npc",
        relationship=hostile_relationship(),
        temperament=temperament,
        context={
            "player_armed": True,
            "player_aiming": True,
            "escape_route": False,
            "npc_armed": True,
            "allies_nearby": 3,
            "guard_nearby": True,
        },
    )

    assert packet["response"] in VALID_RESPONSES
    assert set(packet["scores"]) == VALID_RESPONSES
    assert set(packet["signals"]) == {
        "threat",
        "fear",
        "suspicion",
        "anger",
        "confidence",
        "loyalty",
        "intensity",
    }
    assert all(
        0.0 <= value <= 1.0
        for value in packet["signals"].values()
    )


def test_unknown_temperament_fails_explicitly():
    with pytest.raises(ValueError, match="Unknown temperament"):
        evaluate_threat_response(
            npc="npc",
            relationship=hostile_relationship(),
            temperament="does_not_exist",
            context={},
        )


def test_invalid_relationship_numbers_fail_explicitly():
    relationship = hostile_relationship()
    relationship["trust"] = float("nan")

    with pytest.raises(ValueError):
        evaluate_threat_response(
            npc="npc",
            relationship=relationship,
            temperament="calm",
            context={},
        )


def test_response_matrix_is_deterministic_json_safe_and_bounded():
    relationship = hostile_relationship()

    for player_aiming in (False, True):
        for player_attacking in (False, True):
            for npc_armed in (False, True):
                for escape_route in (False, True):
                    for guard_nearby in (False, True):
                        context = {
                            "player_armed": (
                                player_aiming or player_attacking
                            ),
                            "player_aiming": player_aiming,
                            "player_attacking": player_attacking,
                            "npc_armed": npc_armed,
                            "escape_route": escape_route,
                            "guard_nearby": guard_nearby,
                            "authority_present": guard_nearby,
                            "allies_nearby": 2 if npc_armed else 0,
                            "crowd_size": 5,
                        }

                        first = evaluate_threat_response(
                            npc="matrix_npc",
                            relationship=relationship,
                            temperament="resentful",
                            context=context,
                        )
                        second = evaluate_threat_response(
                            npc="matrix_npc",
                            relationship=relationship,
                            temperament="resentful",
                            context=context,
                        )

                        assert first == second
                        assert first["response"] in VALID_RESPONSES
                        assert all(
                            math.isfinite(score) and score >= 0.0
                            for score in first["scores"].values()
                        )

                        json.dumps(first, sort_keys=True)


def test_public_api_matches_direct_policy_for_same_live_relationship():
    api = GhostAPI()

    relationship = api.apply_event(
        "player",
        "merchant",
        {"type": "threat", "intensity": 0.90},
    )

    context = {
        "player_armed": True,
        "player_aiming": True,
        "escape_route": True,
    }

    direct = evaluate_threat_response(
        npc="merchant",
        relationship=relationship,
        temperament="anxious",
        context=context,
    )

    live = api.evaluate_npc_threat_response(
        npc="merchant",
        source="player",
        target="merchant",
        temperament="anxious",
        context=context,
    )

    assert live == direct


@pytest.mark.parametrize(
    "relationship",
    [
        None,
        [],
        "not a packet",
        7,
        ("trust", -0.5),
    ],
)
def test_relationship_packet_requires_mapping(relationship):
    with pytest.raises(
        ValueError,
        match="relationship must be a dictionary packet",
    ):
        evaluate_threat_response(
            npc="npc",
            relationship=relationship,
            temperament="calm",
            context={},
        )


@pytest.mark.parametrize(
    "diagnostics",
    [
        [],
        "not diagnostics",
        7,
        ("severity", 0.5),
    ],
)
def test_relationship_diagnostics_requires_mapping(diagnostics):
    relationship = hostile_relationship()
    relationship["diagnostics"] = diagnostics

    with pytest.raises(
        ValueError,
        match="relationship diagnostics must be a dictionary packet",
    ):
        evaluate_threat_response(
            npc="npc",
            relationship=relationship,
            temperament="calm",
            context={},
        )


def test_relationship_packet_allows_missing_optional_fields():
    packet = evaluate_threat_response(
        npc="npc",
        relationship={},
        temperament="calm",
        context={},
    )

    assert packet["response"] in VALID_RESPONSES
    assert packet["signals"]["threat"] == 0.0
    assert set(packet["scores"]) == VALID_RESPONSES

    json.dumps(packet, sort_keys=True)


def test_relationship_packet_allows_none_diagnostics_as_empty_packet():
    packet = evaluate_threat_response(
        npc="npc",
        relationship={
            "trust": 0.0,
            "state": "neutral",
            "diagnostics": None,
        },
        temperament="calm",
        context={},
    )

    assert packet["response"] in VALID_RESPONSES
    assert packet["signals"]["fear"] >= 0.0

    json.dumps(packet, sort_keys=True)


@pytest.mark.parametrize(
    "field_name,bad_value",
    [
        ("trust", float("nan")),
        ("trust", float("inf")),
        ("trust", float("-inf")),
    ],
)
def test_relationship_top_level_numeric_fields_reject_non_finite_values(
    field_name,
    bad_value,
):
    relationship = hostile_relationship()
    relationship[field_name] = bad_value

    with pytest.raises(ValueError):
        evaluate_threat_response(
            npc="npc",
            relationship=relationship,
            temperament="calm",
            context={},
        )


@pytest.mark.parametrize(
    "field_name,bad_value",
    [
        ("severity", float("nan")),
        ("severity", float("inf")),
        ("severity", float("-inf")),
        ("delta", float("nan")),
        ("delta", float("inf")),
        ("delta", float("-inf")),
    ],
)
def test_relationship_diagnostic_numeric_fields_reject_non_finite_values(
    field_name,
    bad_value,
):
    relationship = hostile_relationship()
    relationship["diagnostics"][field_name] = bad_value

    with pytest.raises(ValueError):
        evaluate_threat_response(
            npc="npc",
            relationship=relationship,
            temperament="calm",
            context={},
        )


def test_unknown_relationship_fields_do_not_change_output():
    relationship = hostile_relationship()

    baseline = evaluate_threat_response(
        npc="npc",
        relationship=relationship,
        temperament="anxious",
        context={
            "player_armed": True,
            "player_aiming": True,
        },
    )

    expanded = dict(relationship)
    expanded["unrelated_debug_data"] = {
        "foo": "bar",
        "nested": [1, 2, 3],
    }

    expanded["diagnostics"] = dict(
        relationship["diagnostics"]
    )
    expanded["diagnostics"]["unknown_metric"] = 999999

    candidate = evaluate_threat_response(
        npc="npc",
        relationship=expanded,
        temperament="anxious",
        context={
            "player_armed": True,
            "player_aiming": True,
        },
    )

    assert candidate == baseline


def test_relationship_packet_is_not_mutated_by_shape_validation():
    relationship = hostile_relationship()
    relationship["diagnostics"] = dict(
        relationship["diagnostics"]
    )

    before = json.dumps(relationship, sort_keys=True)

    evaluate_threat_response(
        npc="npc",
        relationship=relationship,
        temperament="calm",
        context={},
    )

    after = json.dumps(relationship, sort_keys=True)

    assert after == before
