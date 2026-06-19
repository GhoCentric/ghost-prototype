from hypothesis import given, strategies as st
from ghost.engine import GhostEngine

@given(
    low=st.floats(min_value=0, max_value=5),
    high=st.floats(min_value=5, max_value=10),
)
def test_higher_intensity_never_reduces_threat(low, high):
    engine_low = GhostEngine()
    engine_high = GhostEngine()

    engine_low.step({
        "source": "npc_engine",
        "intent": "threat",
        "intensity": low,
    })

    engine_high.step({
        "source": "npc_engine",
        "intent": "threat",
        "intensity": high,
    })

    assert engine_high.state()["npc"]["threat_level"] >= engine_low.state()["npc"]["threat_level"]