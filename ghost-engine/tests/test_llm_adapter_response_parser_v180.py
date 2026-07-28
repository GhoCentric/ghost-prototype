from hypothesis import given, settings
from hypothesis import strategies as st

from ghost.llm_adapter import parse_voice_response


def test_parse_voice_response_accepts_plain_dialogue_v180():
    result = parse_voice_response(
        "You ended the old king's rule, but Ashfield is still watching.",
        max_words=60,
    )

    assert result["text"] == (
        "You ended the old king's rule, but Ashfield is still watching."
    )
    assert result["accepted"] is True
    assert result["used_fallback"] is False


def test_parse_voice_response_strips_speaker_label_v180():
    result = parse_voice_response(
        "Ashfield Elder: We will not cheer blindly tonight.",
        max_words=60,
    )

    assert result["text"] == "We will not cheer blindly tonight."
    assert result["accepted"] is True
    assert not result["text"].startswith("Ashfield Elder:")


def test_parse_voice_response_extracts_json_dialogue_v180():
    result = parse_voice_response(
        '{"dialogue": "Rule carefully. Ashfield is watching."}',
        max_words=60,
    )

    assert result["text"] == "Rule carefully. Ashfield is watching."
    assert "json_wrapper_removed" in result["warnings"]


def test_parse_voice_response_strips_code_fence_and_json_v180():
    result = parse_voice_response(
        '```json\n{"text": "The crown is yours, but trust is not."}\n```',
        max_words=60,
    )

    assert result["text"] == "The crown is yours, but trust is not."
    assert "code_fence_removed" in result["warnings"]
    assert "json_wrapper_removed" in result["warnings"]


def test_parse_voice_response_uses_fallback_for_empty_output_v180():
    result = parse_voice_response(
        "   ",
        fallback_text="The elder says nothing.",
    )

    assert result["text"] == "The elder says nothing."
    assert result["used_fallback"] is True
    assert "empty_response" in result["warnings"]


def test_parse_voice_response_blocks_hidden_counter_leaks_v180():
    result = parse_voice_response(
        "Your fear score is 11 and your mercy score is 56.",
        fallback_text="Ashfield is watching your crown carefully.",
    )

    assert result["text"] == "Ashfield is watching your crown carefully."
    assert result["used_fallback"] is True
    assert "forbidden_voice_term" in result["warnings"]


def test_parse_voice_response_caps_long_output_v180():
    raw = "word " * 200

    result = parse_voice_response(
        raw,
        max_words=12,
    )

    assert len(result["text"].split()) == 12
    assert "word_cap_applied" in result["warnings"]


@given(
    raw=st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
        ),
        st.text(
            min_size=0,
            max_size=5000,
        ),
    ),
    max_words=st.integers(
        min_value=-50,
        max_value=150,
    ),
)
@settings(max_examples=120)
def test_parse_voice_response_never_crashes_on_malformed_provider_output_v180(
    raw,
    max_words,
):
    result = parse_voice_response(
        raw,
        fallback_text="What do you need?",
        max_words=max_words,
    )

    assert isinstance(result, dict)
    assert isinstance(result["text"], str)
    assert result["text"]
    assert isinstance(result["warnings"], list)
    assert isinstance(result["used_fallback"], bool)
    assert isinstance(result["accepted"], bool)
    assert result["provider_called"] is True
    assert "fear score" not in result["text"].lower()
    assert "mercy score" not in result["text"].lower()
    assert "king_control" not in result["text"].lower()

    effective_max = max_words

    if not isinstance(effective_max, int) or effective_max <= 0:
        effective_max = 60

    assert len(result["text"].split()) <= effective_max
