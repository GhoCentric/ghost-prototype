def test_emotional_modulation_affects_threat_gain():
    """
    Same threat input, different mood → different threat accumulation.
    Higher mood (anxious) should amplify threat gain.
    """

    from ghost.engine import GhostEngine

    # ---- Calm mood engine ----
    calm_engine = GhostEngine()

    # Inject calm mood into engine state
    calm_state = calm_engine.state()
    calm_state.setdefault("state", {})
    calm_state["state"]["mood"] = 0.1  # calm / low arousal

    calm_engine.step({
        "source": "npc_engine",
        "intent": "threat",
        "intensity": 1.0,
    })

    calm_threat = calm_engine.state()["npc"]["threat_level"]

    # ---- Anxious mood engine ----
    anxious_engine = GhostEngine()

    anxious_state = anxious_engine.state()
    anxious_state.setdefault("state", {})
    anxious_state["state"]["mood"] = 0.9  # anxious / high arousal

    anxious_engine.step({
        "source": "npc_engine",
        "intent": "threat",
        "intensity": 1.0,
    })

    anxious_threat = anxious_engine.state()["npc"]["threat_level"]

    assert anxious_threat > calm_threat