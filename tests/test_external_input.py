def test_external_input_passthrough():
    """
    External input passed to step() must be recorded in state as a
    public-safe canonical dict.
    """

    from ghost.engine import GhostEngine

    engine = GhostEngine()

    event = {
        "source": "npc_engine",
        "intent": "threat",
        "actor": "player",
        "intensity": 0.5,
    }

    engine.step(event)
    state = engine.state()

    assert "input" in state
    assert state["input"] is not None
    assert isinstance(state["input"], dict)

    assert state["input"]["source"] == "npc_engine"
    assert state["input"]["intent"] == "threat"
    assert state["input"]["actor"] == "player"
    assert state["input"]["target"] is None
    assert state["input"]["intensity"] == 0.5

    assert state["last_step"] == state["input"]
