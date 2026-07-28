"""Defensive numeric-normalization contracts for threat response."""

from __future__ import annotations

import pytest

from ghost.threat_response import _unit


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (-5.0, 0.0),
        (0.0, 0.0),
        (0.37, 0.37),
        (1.0, 1.0),
        (9.0, 1.0),
        ("0.25", 0.25),
    ],
)
def test_unit_normalizes_finite_values_into_unit_interval(
    raw_value,
    expected,
):
    assert _unit(raw_value) == pytest.approx(expected)


@pytest.mark.parametrize(
    "raw_value",
    [
        None,
        [],
        {},
        object(),
        "not-a-number",
    ],
)
def test_unit_rejects_unparseable_values_as_zero(
    raw_value,
):
    assert _unit(raw_value) == 0.0


@pytest.mark.parametrize(
    "raw_value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_unit_rejects_non_finite_values_as_zero(
    raw_value,
):
    assert _unit(raw_value) == 0.0
