from ghost.engine import GhostEngine
from hypothesis import given, strategies as st


@given(st.floats(min_value=0, max_value=10))
def test_relationship_trust_accumulates(delta):
    g = GhostEngine()

    g.relationships.apply_delta("A", "B", {"trust": delta})
    g.relationships.apply_delta("A", "B", {"trust": delta})

    rel = g.relationships.get("A", "B")

    assert rel["trust"] >= delta