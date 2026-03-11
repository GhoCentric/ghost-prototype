def test_actor_threat_memory_accumulates():
    from ghost.engine import GhostEngine

    e = GhostEngine()

    for _ in range(3):
        e.step({
            "source": "runtime",
            "intent": "threat",
            "actor": "a",
            "intensity": 1.0,
        })

    state = e.state()

    assert state["npc"]["actors"]["a"]["threat_count"] == 3
