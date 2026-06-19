import copy
import time


def test_no_implicit_execution():
    """
    Ghost must not mutate state unless explicitly stepped.
    """

    from ghost.engine import GhostEngine

    engine = GhostEngine()

    # Capture initial engine state
    initial_state = engine.state()

    # Wait to catch any background mutation
    time.sleep(0.2)

    # Capture state again without stepping
    later_state = engine.state()

    # State must be identical
    assert later_state == initial_state