"""Behavior contracts for governance helper and decision branches."""

from __future__ import annotations

import pytest

from ghost.governance import (
    ClaimAssessment,
    IntentAssessment,
    _has_unblocked_direct_harm_clause,
    _hits,
    _tokens,
    _tuple,
    assess_intent,
    assess_player_claim,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, ()),
        (
            ("guard", "captain"),
            ("guard", "captain"),
        ),
        (
            ["guard", "captain"],
            ("guard", "captain"),
        ),
        (
            "guard",
            ("guard",),
        ),
    ],
)
def test_tuple_normalizes_none_tuple_list_and_scalar(
    value,
    expected,
):
    assert _tuple(value) == expected


def test_token_and_hits_helpers_return_empty_contracts():
    assert _tokens(" \n\t ") == ()

    assert _hits({}, "missing_group") == {
        "word_hits": (),
        "phrase_hits": (),
    }


def test_generic_threat_evidence_uses_conservative_fallback_band():
    intent = assess_intent("my friends are nearby")

    assert intent.intent_type == "threat"
    assert intent.severity == pytest.approx(0.70)
    assert intent.pressure == pytest.approx(0.55)
    assert intent.escalation == "guard_warning"

    assert intent.evidence["threat_band"] == {
        "name": "generic_threat_evidence",
        "severity": 0.70,
        "pressure": 0.55,
        "escalation": "guard_warning",
    }


def test_direct_harm_clause_skips_empty_segments_then_detects_threat():
    assert _has_unblocked_direct_harm_clause(
        "... but I will hurt you"
    ) is True


def test_blank_claim_returns_default_contract():
    assert assess_player_claim(" \n\t ") == ClaimAssessment()


def test_verified_authority_claim_requires_verified_world_state():
    claim = assess_player_claim(
        "The guard captain told you the crown paid for it.",
        verified_world_state={
            "verified_authority_order": True,
        },
    )

    assert claim.claim_type == "authority_claim"
    assert claim.verified is True
    assert claim.attempted_state_override is False
    assert claim.severity == 0.0
    assert claim.npc_stance == (
        "accept_verified_authority"
    )
    assert claim.allowed_effects == (
        "authority_context",
    )


def test_blank_intent_returns_default_contract():
    assert assess_intent(" \n\t ") == IntentAssessment()


def test_argument_pressure_reports_deterministic_packet():
    intent = assess_intent("What are you gonna do?")

    assert intent.intent_type == "argument_pressure"
    assert intent.severity == pytest.approx(0.29)
    assert intent.pressure == pytest.approx(0.225)
    assert intent.escalation == "seller_patience"

    assert intent.evidence["argument"] == {
        "score": pytest.approx(1.5),
        "word_hits": (),
        "phrase_hits": (
            "what are you gonna do",
        ),
    }


def test_acceptance_becomes_strong_at_weighted_threshold():
    intent = assess_intent(
        "Yes, I will take it at your price."
    )

    assert intent.intent_type == "clean_acceptance"
    assert intent.clean_acceptance is True
    assert intent.evidence["acceptance_strength"] == "strong"
    assert intent.evidence["acceptance_score"] == (
        pytest.approx(4.45)
    )
