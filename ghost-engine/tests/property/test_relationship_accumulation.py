"""Exact additive-contract tests for direct relationship deltas."""

import pytest
from hypothesis import given, settings, strategies as st

from ghost.engine import GhostEngine


FINITE_DELTAS = st.floats(
    min_value=-10.0,
    max_value=10.0,
    allow_nan=False,
    allow_infinity=False,
)


@given(delta=FINITE_DELTAS)
@settings(max_examples=200)
def test_relationship_trust_delta_is_exactly_additive(delta):
    """apply_delta must preserve its explicit additive contract."""

    engine = GhostEngine()

    engine.relationships.apply_delta(
        "A",
        "B",
        {"trust": delta},
    )
    engine.relationships.apply_delta(
        "A",
        "B",
        {"trust": delta},
    )

    relationship = engine.relationships.get("A", "B")

    assert relationship["trust"] == pytest.approx(
        2.0 * delta,
        rel=1e-12,
        abs=1e-12,
    )

    if delta >= 0.0:
        assert relationship["pos"] == pytest.approx(
            2.0 * delta,
            rel=1e-12,
            abs=1e-12,
        )
        assert relationship["neg"] == 0.0
    else:
        assert relationship["pos"] == 0.0
        assert relationship["neg"] == pytest.approx(
            -2.0 * delta,
            rel=1e-12,
            abs=1e-12,
        )
