# tests/test_environment_isolation.py

import os
import sys
import copy


def test_no_environment_side_effects():
    """
    Importing and initializing Ghost must not mutate
    global environment variables or sys.path.
    """

    env_before = dict(os.environ)
    path_before = list(sys.path)

    import ghost

    # Explicit init is allowed, but must be clean
    ghost.init()

    assert dict(os.environ) == env_before
    assert list(sys.path) == path_before