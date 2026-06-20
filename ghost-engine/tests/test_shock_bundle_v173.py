from ghost import GhostAPI
from ghost.engine import GhostEngine


def apply(api, event):
    api.apply_event(
        "player",
        "shopkeeper",
        {"type": event, "intensity": 1.0},
    )


def test_mature_betrayal_gets_severity_and_relative_shock():
    api = GhostAPI()

    for _ in range(100):
        apply(api, "help")

    apply(api, "betrayal")

    relationship = api.get_relationship(
        "player",
        "shopkeeper",
    )
    diagnostics = relationship["diagnostics"]

    assert diagnostics["high_severity_shock"] is True
    assert diagnostics["relative_shock"] is True
    assert diagnostics["shock_multiplier"] >= 1.45
    assert diagnostics["event_maturity_modifier"] >= 0.45
    assert relationship["trust"] < 0.08


def test_mature_relative_attack_gets_relative_shock_only():
    g = GhostEngine()

    for _ in range(100):
        g.apply_event("player", "shopkeeper", "help")

    relationship = g.apply_event(
        "player",
        "shopkeeper",
        "attack",
    )
    diagnostics = relationship["diagnostics"]

    assert diagnostics["high_severity_shock"] is False
    assert diagnostics["relative_shock"] is True
    assert diagnostics["shock_multiplier"] >= 1.20
    assert diagnostics["event_maturity_modifier"] == 0.25


def test_low_history_near_break_contract_is_unchanged():
    g = GhostEngine()

    for event in [
        "greet",
        "help",
        "help",
        "insult",
        "apologize",
        "gift",
        "threat",
        "help",
        "betrayal",
    ]:
        relationship = g.apply_event(
            "player",
            "shopkeeper",
            event,
        )

    diagnostics = relationship["diagnostics"]

    assert relationship["state"] == "neutral"
    assert diagnostics["pressure"] == "near_break"
    assert diagnostics["high_severity_shock"] is False
    assert diagnostics["relative_shock"] is False
    assert diagnostics["shock_multiplier"] == 1.0
