from __future__ import annotations

from pathlib import Path

import pytest

from ghost.examples.ghost_revolution import live_llm_dev as live


MANAGED = (
    "OPENAI_API_KEY",
    "GHOST_REAL_LLM",
    "GHOST_LLM_OPPONENT",
    "GHOST_DEV_LLM_NARRATION",
)


def test_httpx_probe_boundary_v191(monkeypatch):
    monkeypatch.setattr(
        live.importlib.util,
        "find_spec",
        lambda name: None,
    )
    assert live._httpx_available() is False

    monkeypatch.setattr(
        live.importlib.util,
        "find_spec",
        lambda name: object(),
    )
    assert live._httpx_available() is True


def test_missing_httpx_refuses_before_key_prompt_v191(
    monkeypatch,
    capsys,
):
    prompted = []

    monkeypatch.setattr(
        live,
        "_httpx_available",
        lambda: False,
    )
    monkeypatch.setattr(
        live.getpass,
        "getpass",
        lambda prompt: prompted.append(prompt) or "secret",
    )

    assert live.main() == 2
    assert prompted == []

    output = capsys.readouterr().out
    assert "python -m pip install httpx" in output


def test_empty_key_refuses_without_env_mutation_v191(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        live,
        "_httpx_available",
        lambda: True,
    )
    monkeypatch.setattr(
        live.getpass,
        "getpass",
        lambda _prompt: "   ",
    )

    before = {
        name: live.os.environ.get(name)
        for name in MANAGED
    }

    assert live.main() == 2

    after = {
        name: live.os.environ.get(name)
        for name in MANAGED
    }

    assert after == before
    assert "cancelled" in capsys.readouterr().out.lower()


def test_live_mode_enables_both_llm_roles_and_restores_v191(
    monkeypatch,
    capsys,
):
    secret = "test-secret-never-print-this"

    original = {
        "OPENAI_API_KEY": "previous-key",
        "GHOST_REAL_LLM": "old-real",
        "GHOST_LLM_OPPONENT": "old-opponent",
        "GHOST_DEV_LLM_NARRATION": "old-narration",
    }

    for name, value in original.items():
        monkeypatch.setenv(name, value)

    monkeypatch.setattr(
        live,
        "_httpx_available",
        lambda: True,
    )
    monkeypatch.setattr(
        live.getpass,
        "getpass",
        lambda _prompt: secret,
    )

    seen = {}

    def fake_panel():
        seen.update(
            {
                name: live.os.environ.get(name)
                for name in MANAGED
            }
        )

    monkeypatch.setattr(
        live.dev_shortcuts,
        "run_developer_shortcut_panel",
        fake_panel,
    )

    assert live.main() == 0

    assert seen == {
        "OPENAI_API_KEY": secret,
        "GHOST_REAL_LLM": "1",
        "GHOST_LLM_OPPONENT": "1",
        "GHOST_DEV_LLM_NARRATION": "1",
    }

    assert {
        name: live.os.environ.get(name)
        for name in MANAGED
    } == original

    output = capsys.readouterr().out
    assert secret not in output
    assert "real LLM opponent decisions" in output
    assert "real LLM fight narration" in output
    assert "NOT a finished game mode" in output


def test_live_mode_restores_environment_after_panel_failure_v191(
    monkeypatch,
    capsys,
):
    secret = "another-test-secret"

    for name in MANAGED:
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setattr(
        live,
        "_httpx_available",
        lambda: True,
    )
    monkeypatch.setattr(
        live.getpass,
        "getpass",
        lambda _prompt: secret,
    )

    def boom():
        raise RuntimeError("panel failed")

    monkeypatch.setattr(
        live.dev_shortcuts,
        "run_developer_shortcut_panel",
        boom,
    )

    with pytest.raises(RuntimeError, match="panel failed"):
        live.main()

    for name in MANAGED:
        assert name not in live.os.environ

    assert secret not in capsys.readouterr().out


def test_launcher_source_does_not_persist_or_echo_key_v191():
    source = Path(live.__file__).read_text(encoding="utf-8")

    assert "getpass.getpass" in source
    assert "write_text(" not in source
    assert "write_bytes(" not in source
    assert "print(api_key" not in source
    assert "print(key" not in source
