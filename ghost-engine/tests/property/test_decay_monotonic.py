from hypothesis import given, strategies as st
from ghost.engine import GhostEngine

@given(steps=st.integers(min_value=1, max_value=20))
def test_decay_never_increases_threat(steps):
    engine = GhostEngine()

    engine.step({
        "source": "npc_engine",
        "intent": "threat",
        "intensity": 5.0,
    })

    last = engine.state()["npc"]["threat_level"]

    for _ in range(steps):
        engine.step(None)
        current = engine.state()["npc"]["threat_level"]
        assert current <= last
        last = current