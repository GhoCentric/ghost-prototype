def test_runtime_loop_stability():
    """
    Integration test:

    Simulates a real runtime loop with mixed inputs.
    Ensures Ghost remains stable across long execution.
    """

    from ghost.engine import GhostEngine
    import random

    e = GhostEngine()

    intents = ["greet", "help", "threat", None]
    actors = ["a", "b", "c", "d"]

    STEPS = 10000

    for _ in range(STEPS):

        intent = random.choice(intents)

        if intent is None:
            e.step()
            continue

        e.step({
            "source": "runtime",
            "intent": intent,
            "actor": random.choice(actors),
            "intensity": random.random(),
        })

    state = e.state()

    # ---- HARD INVARIANTS ----

    assert isinstance(state, dict)

    assert "npc" in state
    assert "threat_level" in state["npc"]

    # bounded system check
    assert state["npc"]["threat_level"] >= 0

    # ensure actors memory survived runtime
    if "actors" in state["npc"]:
        for actor, data in state["npc"]["actors"].items():
            assert data["threat_count"] >= 0