def test_npc_intent_is_classified():
    """
    NPC intent input should be classified and reflected in engine state.
    """

    from ghost.engine import GhostEngine

    engine = GhostEngine()

    engine.step({
        "source": "npc_engine",
        "intent": "threat",
        "intensity": 0.8
    })

    state = engine.state()

    # --- Contracts ---
    assert "npc" in state
    assert state["npc"]["last_intent"] == "threat"
    assert state["npc"]["threat_level"] > 0