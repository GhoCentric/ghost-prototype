def test_threat_decays_without_new_input():
    """
    Threat level should decay over time if no new threat input is received.
    """

    from ghost.engine import GhostEngine

    engine = GhostEngine()

    # --- Spike threat ---
    engine.step({
        "source": "npc_engine",
        "intent": "threat",
        "intensity": 1.0,
    })

    s1 = engine.state()
    threat_after_spike = s1["npc"]["threat_level"]

    # --- Advance cycles with no input (decay only) ---
    engine.step()
    engine.step()
    engine.step()

    s2 = engine.state()
    threat_after_decay = s2["npc"]["threat_level"]

    # --- Contracts ---
    assert "npc" in s1
    assert "npc" in s2

    assert "threat_level" in s1["npc"]
    assert "threat_level" in s2["npc"]

    # Core invariant: decay must reduce threat without new input
    assert threat_after_decay < threat_after_spike