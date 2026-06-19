from hypothesis import given, strategies as st

VALID_AGENT_IDS = st.text(
    alphabet=st.characters(
        blacklist_characters="|",
        blacklist_categories=("Cs",),
    ),
    min_size=1,
    max_size=5,
).filter(lambda value: value.strip() != "")

from ghost.engine import GhostEngine
from ghost.step import GhostStep

def contains_ghoststep(obj):
    if isinstance(obj, GhostStep):
        return True
    if isinstance(obj, dict):
        return any(contains_ghoststep(v) for v in obj.values())
    if isinstance(obj, list):
        return any(contains_ghoststep(v) for v in obj)
    return False

@given(
    intensity=st.floats(min_value=0, max_value=10),
    actor=VALID_AGENT_IDS
)
def test_no_internal_types_leak(intensity, actor):
    engine = GhostEngine()

    step = GhostStep(
        source="npc_engine",
        intent="threat",
        actor=actor,
        intensity=intensity
    )

    engine.step(step)
    state = engine.state()

    assert not contains_ghoststep(state)