
from pathlib import Path


def test_real_crown_llm_script_exists_v180():
    path = Path("scripts/test_real_crown_llm.py")

    assert path.is_file()


def test_real_crown_llm_script_is_env_gated_v180():
    source = Path(
        "scripts/test_real_crown_llm.py"
    ).read_text(
        encoding="utf-8",
    )

    assert "GHOST_REAL_LLM" in source
    assert "OPENAI_API_KEY" in source
    assert "OpenAIResponsesClient" in source
    assert "GhostRevolutionLLMBridge" in source
    assert "create_endgame_shortcut" in source


def test_real_crown_llm_script_has_no_import_time_call_v180():
    source = Path(
        "scripts/test_real_crown_llm.py"
    ).read_text(
        encoding="utf-8",
    )

    assert 'if __name__ == "__main__":' in source
    assert "raise SystemExit(main())" in source
