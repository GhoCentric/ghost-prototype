"""Live-LLM developer launcher for Ghost Revolution.

This is an experimental reference/demo entry point, not a finished game mode.

The launcher intentionally does not persist credentials. It requests the user's
OpenAI API key with hidden terminal input, exposes it only through the current
process environment while the developer panel is running, and restores the
previous environment afterward.

The existing Ghost Revolution integration remains authoritative:
- the opponent LLM proposes/selects combat intent;
- Ghost resolves the deterministic combat mechanics;
- the narration LLM describes the resolved state.
"""

from __future__ import annotations

import getpass
import importlib.util
import os

from ghost.examples.ghost_revolution import dev_shortcuts


_MANAGED_ENV = (
    "OPENAI_API_KEY",
    "GHOST_REAL_LLM",
    "GHOST_LLM_OPPONENT",
    "GHOST_DEV_LLM_NARRATION",
)


def _httpx_available() -> bool:
    """Return whether the optional HTTP client used by the live bridge exists."""
    return importlib.util.find_spec("httpx") is not None


def _restore_environment(previous: dict[str, str | None]) -> None:
    """Restore only environment variables temporarily managed by this launcher."""
    for name, value in previous.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def main() -> int:
    """Run Ghost Revolution's developer panel with both live LLM roles enabled."""
    print()
    print("=== GHOST REVOLUTION — LIVE LLM DEV MODE ===")
    print()
    print("Playable reference prototype / systems demo.")
    print("This is NOT a finished game mode.")
    print()
    print("This launcher enables:")
    print("  - real LLM opponent decisions")
    print("  - real LLM fight narration")
    print()
    print("Ghost still owns deterministic combat resolution.")
    print("Your API key is requested with hidden terminal input.")
    print("This launcher does not save the entered key to disk.")
    print("Provider API usage may incur charges on your account.")
    print()

    if not _httpx_available():
        print("Live LLM mode needs the optional 'httpx' package.")
        print("Install it, then rerun this command:")
        print("  python -m pip install httpx")
        return 2

    api_key = getpass.getpass(
        "OpenAI API key (input hidden): "
    ).strip()

    if not api_key:
        print("No API key entered. Live LLM mode cancelled.")
        return 2

    previous = {
        name: os.environ.get(name)
        for name in _MANAGED_ENV
    }

    try:
        os.environ["OPENAI_API_KEY"] = api_key
        os.environ["GHOST_REAL_LLM"] = "1"
        os.environ["GHOST_LLM_OPPONENT"] = "1"
        os.environ["GHOST_DEV_LLM_NARRATION"] = "1"

        print()
        print("Live LLM roles enabled for this process only.")
        print("Choose a boss/endgame shortcut from the developer panel.")
        print()

        dev_shortcuts.run_developer_shortcut_panel()
        return 0
    finally:
        _restore_environment(previous)
        api_key = ""


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
