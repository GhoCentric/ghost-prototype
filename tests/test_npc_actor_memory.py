def test_actor_memory_tracks_threat_counts():
    """
    Ghost must track per-actor threat counts independently.
    """

    from ghost.engine import GhostEngine

    engine = GhostEngine()

    engine.step({
        "source": "npc_engine",
        "actor": "player",
        "intent": "threat",
        "intensity": 0.7,
    })

    engine.step({
        "source": "npc_engine",
        "actor": "player",
        "intent": "threat",
        "intensity": 0.4,
    })

    engine.step({
        "source": "npc_engine",
        "actor": "guard",
        "intent": "threat",
        "intensity": 0.9,
    })

    state = engine.state()

    assert "npc" in state
    assert "actors" in state["npc"]

    # Per-actor memory exists
    assert "player" in state["npc"]["actors"]
    assert "guard" in state["npc"]["actors"]

    assert state["npc"]["actors"]["player"]["threat_count"] == 2
    assert state["npc"]["actors"]["guard"]["threat_count"] == 1