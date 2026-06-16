from ghost.engine import GhostEngine


def test_relationship_diagnostics_exposed_after_event():
    g = GhostEngine()

    rel = g.apply_event("player", "npc", "help")

    assert "diagnostics" in rel

    d = rel["diagnostics"]

    assert d["event"] == "help"
    assert d["channel"] == "pos"
    assert d["direction"] == "positive"
    assert d["trust_after"] > d["trust_before"]
    assert d["delta"] > 0
    assert d["severity"] > 0
    assert d["pressure"] in (
        "forgiveness",
        "positive_shift",
        "minor_positive_shift",
        "state_shift",
    )


def test_relationship_break_diagnostics():
    g = GhostEngine()

    g.apply_event("player", "npc", "help")
    g.apply_event("player", "npc", "help")
    rel = g.apply_event("player", "npc", "betrayal")

    d = rel["diagnostics"]

    assert d["event"] == "betrayal"
    assert d["channel"] == "neg"
    assert d["from_state"] == "friendly"
    assert d["to_state"] == "hostile"
    assert d["trust_before"] > d["trust_after"]
    assert d["delta"] < 0
    assert d["abs_delta"] == abs(d["delta"])
    assert d["direction"] == "negative"
    assert d["severity"] > 0
    assert d["effective_gain"] > 0
    assert d["pressure"] == "relationship_broken"

    assert rel["transition"] == ("friendly", "hostile")
    assert rel["trigger"]["event"] == "relationship_broken"


def test_tick_diagnostics_are_exposed():
    g = GhostEngine()

    g.apply_event("player", "npc", "betrayal")
    g.tick()

    rel = g.get_relationship("player", "npc")
    d = rel["diagnostics"]

    assert d["event"] == "tick"
    assert d["channel"] == "decay"
    assert "trust_before" in d
    assert "trust_after" in d
    assert "delta" in d
    assert "severity" in d
    assert "pressure" in d


def test_diagnostics_include_maturity_and_volatility_values():
    g = GhostEngine()

    g.relationships.set_personality("player", "npc", "volatile")
    rel = g.apply_event("player", "npc", "help")

    d = rel["diagnostics"]

    assert d["maturity"] == 0.0
    assert d["maturity_modifier"] == 1.0
    assert d["volatility"] == 1.2
    assert d["positive_volatility"] == 1.1
    assert d["negative_volatility"] == 1.8


def test_diagnostics_available_through_get_relationship():
    g = GhostEngine()

    g.apply_event("player", "npc", "help")
    g.apply_event("player", "npc", "betrayal")

    rel = g.get_relationship("player", "npc")

    assert "diagnostics" in rel
    assert rel["diagnostics"]["event"] == "betrayal"
    assert rel["diagnostics"]["direction"] == "negative"


def test_relationship_diagnostics_are_json_safe():
    import json

    g = GhostEngine()

    g.apply_event("player", "npc", "help")
    rel = g.apply_event("player", "npc", "betrayal")

    json.dumps(rel)
