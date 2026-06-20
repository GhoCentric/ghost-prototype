from ghost import GhostAPI


def _apply(api, event_name):
    api.apply_event(
        "player",
        "shopkeeper",
        {
            "type": event_name,
            "intensity": 1.0,
        },
    )


def test_negative_neutral_relationship_reads_wary_not_calm():
    api = GhostAPI()

    for event_name in ("help", "help", "help", "betrayal"):
        _apply(api, event_name)

    for _ in range(8):
        api.tick()

    relationship = api.get_relationship("player", "shopkeeper")

    reading = api.interpret_npc_relationship(
        "guard_calm",
        "player",
        "shopkeeper",
        temperament="calm",
    )

    assert relationship["state"] == "neutral"
    assert relationship["trust"] <= -0.20

    assert reading["interpretation"]["emotional_read"] == "wary"
    assert reading["interpretation"]["stance"] == "reserved"


def test_near_break_persists_during_recovery_tick():
    api = GhostAPI()

    _apply(api, "betrayal")
    _apply(api, "help")
    _apply(api, "help")
    _apply(api, "help")

    before_tick = api.get_relationship("player", "shopkeeper")

    assert before_tick["state"] == "neutral"
    assert -0.55 < before_tick["trust"] <= -0.45
    assert before_tick["diagnostics"]["near_break"] is True

    api.tick()

    after_tick = api.get_relationship("player", "shopkeeper")

    assert after_tick["state"] == "neutral"
    assert -0.55 < after_tick["trust"] <= -0.45
    assert after_tick["diagnostics"]["direction"] == "positive"
    assert after_tick["diagnostics"]["near_break"] is True


def test_tiny_asymmetric_decay_reports_stable_not_negative_shift():
    api = GhostAPI()

    _apply(api, "betrayal")

    for _ in range(10):
        _apply(api, "help")

    api.tick()

    relationship = api.get_relationship("player", "shopkeeper")
    diagnostics = relationship["diagnostics"]

    assert diagnostics["delta"] < 0.0
    assert abs(diagnostics["delta"]) < 0.005
    assert diagnostics["pressure"] == "stable"
