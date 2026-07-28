"""Behavior contracts for Ghost policy decision branches."""

from __future__ import annotations

import pytest

from ghost import GhostAPI


def test_normal_price_change_reports_reason_and_clears_anchor():
    ghost = GhostAPI()

    decision = ghost.compute_price(
        item="bread",
        base_price=20,
        relationship_state="hostile",
        sale_access="normal",
        prior_record={
            "current_price": 25,
            "sale_access": "restricted",
            "anchor_price": 50,
        },
    )

    assert decision["final_price"] == 40
    assert decision["raw_changed"] is True
    assert decision["changed"] is True
    assert decision["passive_decay"] is False
    assert decision["reason"] == (
        "relationship or market price changed"
    )
    assert decision["anchor_price"] == 0


def test_restricted_price_change_sets_markup_reason_and_anchor():
    ghost = GhostAPI()

    decision = ghost.compute_price(
        item="bread",
        base_price=20,
        relationship_state="neutral",
        sale_access="restricted",
        severity=0.50,
        prior_record={
            "current_price": 25,
            "sale_access": "normal",
            "anchor_price": 0,
        },
    )

    assert decision["final_price"] == 50
    assert decision["raw_changed"] is True
    assert decision["changed"] is True
    assert decision["passive_decay"] is False
    assert decision["reason"] == "restricted service markup"
    assert decision["anchor_price"] == 50


def test_refused_service_price_reports_refusal_reason():
    ghost = GhostAPI()

    decision = ghost.compute_price(
        item="bread",
        base_price=20,
        relationship_state="hostile",
        sale_access="refused",
        prior_record={
            "current_price": 40,
            "sale_access": "normal",
            "anchor_price": 40,
        },
    )

    assert decision["final_price"] == 0
    assert decision["raw_changed"] is True
    assert decision["changed"] is True
    assert decision["passive_decay"] is False
    assert decision["reason"] == "service refused"
    assert decision["anchor_price"] == 0


def test_restricted_price_decay_is_not_a_new_price_event():
    ghost = GhostAPI()

    decision = ghost.compute_price(
        item="bread",
        base_price=20,
        relationship_state="neutral",
        sale_access="restricted",
        severity=0.40,
        prior_record={
            "current_price": 50,
            "sale_access": "restricted",
            "anchor_price": 50,
        },
    )

    assert decision["final_price"] == 48
    assert decision["raw_changed"] is True
    assert decision["changed"] is False
    assert decision["passive_decay"] is True
    assert decision["reason"] == (
        "passive restricted-service price decay"
    )
    assert decision["anchor_price"] == 50


def test_release_grace_overrides_other_law_escalations():
    ghost = GhostAPI()

    decision = ghost.evaluate_law(
        severity=5.0,
        argument_pressure=4,
        warning_count=3,
        release_grace=1,
    )

    assert decision["status"] == "grace"
    assert decision["action"] == "watch"
    assert decision["reason"] == "release grace active"


def test_argument_pressure_ejects_before_warning_count_removal():
    ghost = GhostAPI()

    decision = ghost.evaluate_law(
        severity=1.5,
        argument_pressure=4,
        warning_count=3,
    )

    assert decision["status"] == "ejection"
    assert decision["action"] == "call_guards"
    assert decision["allowed_effects"] == (
        "guard_warning",
    )


def test_warning_count_removes_player_when_pressure_is_lower():
    ghost = GhostAPI()

    decision = ghost.evaluate_law(
        severity=1.5,
        argument_pressure=0,
        warning_count=3,
    )

    assert decision["status"] == "removed"
    assert decision["action"] == "remove_from_stall"
    assert decision["allowed_effects"] == (
        "trespass_detention",
    )


@pytest.mark.parametrize(
    ("arrest_count", "expected_multiplier"),
    [
        (2, 0.35),
        (3, 0.20),
    ],
)
def test_repeat_arrests_reduce_reintegration_recovery(
    arrest_count,
    expected_multiplier,
):
    ghost = GhostAPI()

    decision = ghost.evaluate_reintegration(
        served_punishment=True,
        current_trust=-0.80,
        arrest_count=arrest_count,
        resistance_remaining=0,
    )

    assert decision["allowed"] is True
    assert decision["trust_floor"] == -0.45
    assert decision["recovery_multiplier"] == (
        expected_multiplier
    )
    assert decision["reason"] == (
        "reintegration allowed with reduced recovery"
    )
