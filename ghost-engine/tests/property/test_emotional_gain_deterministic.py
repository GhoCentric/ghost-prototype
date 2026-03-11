def test_emotional_gain_deterministic():
    from ghost.engine import GhostEngine

    e1 = GhostEngine({"state": {"mood": 0.9}})
    e2 = GhostEngine({"state": {"mood": 0.9}})

    step = {
        "source": "runtime",
        "intent": "threat",
        "actor": "a",
        "intensity": 1.0,
    }

    e1.step(step)
    e2.step(step)

    assert e1.state() == e2.state()
