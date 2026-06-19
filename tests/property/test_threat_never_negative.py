from hypothesis import given, settings
from hypothesis.strategies import floats, integers

from ghost.engine import GhostEngine


@given(
    intensities=floats(min_value=0.0, max_value=10.0),
    decay_steps=integers(min_value=0, max_value=50),
)
@settings(max_examples=200)
def test_threat_level_never_negative(intensities, decay_steps):
    """
    Threat level must never go below zero,
    regardless of threat intensity or decay cycles.
    """

    engine = GhostEngine()

    # Inject a threat
    engine.step({
        "source": "npc_engine",
        "intent": "threat",
        "actor": "player",
        "intensity": intensities,
    })

    # Apply decay steps
    for _ in range(decay_steps):
        engine.step()

    state = engine.state()
    threat = state["npc"]["threat_level"]

    assert threat >= 0.0