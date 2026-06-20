"""
ghocentric-ghost-engine
Public API surface.
"""

__version__ = "1.7.3"

from .api import GhostAPI

from .engine import GhostEngine

__all__ = [
    "GhostAPI",
    "GhostEngine",
    "init",
    "step",
    "reset",
    "state",
    "snapshot",
]

# Module-scoped active engine (explicit lifecycle)
_ACTIVE_ENGINE: GhostEngine | None = None

def snapshot():
    """
    Return an immutable snapshot of the active engine state.
    """
    if _ACTIVE_ENGINE is None:
        raise RuntimeError(
            "Ghost engine not initialized. Call ghost.init() first."
        )

    return _ACTIVE_ENGINE.snapshot()


def init(context: dict | None = None) -> GhostEngine:
    """
    Initialize and register the active Ghost engine.
    """
    global _ACTIVE_ENGINE
    _ACTIVE_ENGINE = GhostEngine(context=context)
    return _ACTIVE_ENGINE


def reset():
    """
    Reset the active Ghost engine.
    Safe to call multiple times.
    """
    global _ACTIVE_ENGINE
    _ACTIVE_ENGINE = None


def step(step_data=None):
    """
    Advance the active Ghost engine by one cycle.
    """
    if _ACTIVE_ENGINE is None:
        raise RuntimeError(
            "Ghost engine not initialized. Call ghost.init() first."
        )

    return _ACTIVE_ENGINE.step(step_data)


def state():
    """
    Return the active engine's live state.
    """
    if _ACTIVE_ENGINE is None:
        raise RuntimeError(
            "Ghost engine not initialized. Call ghost.init() first."
        )

    return _ACTIVE_ENGINE.state()