from ghost import GhostAPI
from ghost.engine import GhostEngine


def test_mature_goodwill_does_not_immunize_against_betrayal():
    api = GhostAPI()

    for _ in range(100):
        api.apply_event(
            "player",
            "shopkeeper",
            {"type": "help", "intensity": 1.0},
        )

    api.apply_event(
        "player",
        "shopkeeper",
        {"type": "betrayal", "intensity": 1.0},
    )

    relationship = api.get_relationship(
        "player",
        "shopkeeper",
    )

    diagnostics = relationship["diagnostics"]

    assert diagnostics["shock_applied"] is True
    assert diagnostics["stability_breach"] > 2.0
    assert relationship["state"] == "neutral"
    assert relationship["trust"] < 0.08


def test_low_maturity_betrayal_keeps_existing_behavior():
    g = GhostEngine()

    g.apply_event("player", "shopkeeper", "help")
    g.apply_event("player", "shopkeeper", "help")

    relationship = g.apply_event(
        "player",
        "shopkeeper",
        "betrayal",
    )

    diagnostics = relationship["diagnostics"]

    assert diagnostics["shock_applied"] is False
    assert diagnostics["stability_breach"] == 0.0
    assert relationship["state"] == "hostile"


def test_existing_near_break_path_does_not_trigger_mature_shock():
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
    assert diagnostics["shock_applied"] is False
