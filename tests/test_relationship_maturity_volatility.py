from ghost.engine import GhostEngine


def test_relationship_exposes_maturity_and_volatility():
    g = GhostEngine()

    g.apply_event("player", "npc", "help")

    rel = g.get_relationship("player", "npc")

    assert "maturity" in rel
    assert "volatility" in rel
    assert "positive_volatility" in rel
    assert "negative_volatility" in rel


def test_maturity_increases_after_events():
    g = GhostEngine()

    g.apply_event("player", "npc", "help")
    r1 = g.get_relationship("player", "npc")

    g.apply_event("player", "npc", "help")
    r2 = g.get_relationship("player", "npc")

    assert r2["maturity"] > r1["maturity"]


def test_short_relationship_betrayal_still_breaks():
    g = GhostEngine()

    g.apply_event("player", "npc", "help")
    g.apply_event("player", "npc", "help")
    g.apply_event("player", "npc", "betrayal")

    rel = g.get_relationship("player", "npc")

    assert rel["state"] == "hostile"
    assert rel["trigger"] == {"event": "relationship_broken"}


def test_long_relationship_resists_single_betrayal():
    g = GhostEngine()

    for _ in range(20):
        g.apply_event("player", "npc", "help")

    before = g.get_relationship("player", "npc")

    g.apply_event("player", "npc", "betrayal")
    after = g.get_relationship("player", "npc")

    assert before["state"] == "friendly"
    assert after["state"] == "friendly"
    assert after["trust"] < before["trust"]
    assert after["maturity"] > before["maturity"]


def test_volatile_personality_has_split_volatility():
    g = GhostEngine()

    g.relationships.set_personality("player", "npc", "volatile")
    g.apply_event("player", "npc", "help")

    rel = g.get_relationship("player", "npc")

    assert rel["positive_volatility"] == 1.1
    assert rel["negative_volatility"] == 1.8


def test_personality_profiles_diverge_after_same_sequence():
    results = {}

    for personality in ("balanced", "forgiving", "resentful", "volatile"):
        g = GhostEngine()
        g.relationships.set_personality("player", "npc", personality)

        for _ in range(10):
            g.apply_event("player", "npc", "help")

        g.apply_event("player", "npc", "betrayal")
        results[personality] = g.get_relationship("player", "npc")

    assert results["forgiving"]["trust"] > results["balanced"]["trust"]
    assert results["resentful"]["trust"] < results["balanced"]["trust"]
    assert results["volatile"]["negative_volatility"] > results["balanced"]["negative_volatility"]
