def test_public_api_surface():
    """
    Ghost exposes a stable, minimal public API.
    This is the pip-facing contract.
    """

    import ghost

    assert hasattr(ghost, "init")
    assert hasattr(ghost, "step")
    assert hasattr(ghost, "reset")
    assert hasattr(ghost, "state")
    assert hasattr(ghost, "snapshot")


def test_public_api_behavior():
    """
    Public API functions must work end-to-end without importing internals.
    """

    import ghost

    ghost.init()
    ghost.step()
    state = ghost.state()

    assert isinstance(state, dict)
    assert "cycles" in state