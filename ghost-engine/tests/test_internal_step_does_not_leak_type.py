from ghost.engine import GhostEngine
from ghost.step import GhostStep


def test_internal_step_does_not_leak_type():
    engine = GhostEngine()

    step = GhostStep(
        source="npc_engine",
        intent="threat",
        actor="player",
        intensity=0.7
    )

    engine.step(step)

    ctx = engine.state()

    # Public-facing state must remain dict-based
    assert isinstance(ctx["input"], dict)
    assert isinstance(ctx["last_step"], dict)

    # Internal types must not leak
    assert not isinstance(ctx["input"], GhostStep)