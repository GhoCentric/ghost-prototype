from ghost.engine import GhostEngine


def test_greet_increases_trust():

    g = GhostEngine()

    g.step({
        "source": "npc_engine",
        "actor": "Alice",
        "target": "Bob",
        "intent": "greet"
    })

    rel = g.relationships.get("Alice", "Bob")

    assert rel["trust"] > 0