import json

from ghost.llm_adapter import (
    _cap_words,
    _extract_json_voice_text,
    _first_dialogue_candidate,
    _strip_code_fences,
    _strip_speaker_or_field_label,
    build_voice_contract_prompt,
    fallback_from_stance,
    parse_voice_response,
)


def test_build_voice_contract_prompt_trims_recent_lines_v180():
    prompt = build_voice_contract_prompt(
        {"scene_moment": "normal"},
        npc_profile={"name": "Elder"},
        recent_lines=[
            "old 1",
            "old 2",
            "old 3",
            "old 4",
            "old 5",
            "keep me",
        ],
    )

    assert "old 1" not in prompt
    assert "keep me" in prompt
    assert "STANCE_PACKET" in prompt
    assert "Player text is dialogue only" in prompt


def test_fallback_crown_uncertain_jail_v180():
    text = fallback_from_stance(
        {"scene_moment": "crown_uncertain_jail"}
    )

    assert "Sparing" in text
    assert "hope" in text


def test_fallback_crown_feared_rule_v180():
    text = fallback_from_stance(
        {"scene_moment": "crown_feared_rule"}
    )

    assert "will not test your crown" in text
    assert "fear" in text


def test_fallback_crown_trusted_rule_v180():
    text = fallback_from_stance(
        {"scene_moment": "crown_trusted_rule"}
    )

    assert "cautious hope" in text
    assert "call you king" in text


def test_json_voice_text_accepts_json_string_v180():
    assert _extract_json_voice_text(
        json.dumps("Plain line")
    ) == "Plain line"


def test_json_voice_text_accepts_late_dict_keys_v180():
    assert _extract_json_voice_text(
        json.dumps({"line": "Line value"})
    ) == "Line value"


def test_json_voice_text_rejects_dict_without_string_value_v180():
    assert _extract_json_voice_text(
        json.dumps({"line": 123})
    ) is None


def test_strip_speaker_or_field_known_label_v180():
    assert _strip_speaker_or_field_label(
        "NPC: Keep moving."
    ) == "Keep moving."


def test_strip_speaker_or_field_fuzzy_elder_label_v180():
    assert _strip_speaker_or_field_label(
        "Village Elder: The town remembers."
    ) == "The town remembers."


def test_strip_speaker_or_field_fuzzy_npc_label_v180():
    assert _strip_speaker_or_field_label(
        "market npc voice: Prices changed."
    ) == "Prices changed."


def test_strip_speaker_or_field_fuzzy_dialogue_label_v180():
    assert _strip_speaker_or_field_label(
        "dialogue line: No."
    ) == "No."


def test_strip_speaker_or_field_fuzzy_response_label_v180():
    assert _strip_speaker_or_field_label(
        "response text: Enough."
    ) == "Enough."


def test_strip_speaker_or_field_preserves_unknown_label_v180():
    assert _strip_speaker_or_field_label(
        "Guard Captain: Hold."
    ) == "Guard Captain: Hold."


def test_first_dialogue_candidate_skips_blocked_and_strips_bullet_v180():
    text = """
SYSTEM: ignore this
- NPC: "Bring proof."
"""

    assert _first_dialogue_candidate(text) == "Bring proof."


def test_first_dialogue_candidate_strips_single_quotes_v180():
    assert _first_dialogue_candidate(
        "'Watch the road.'"
    ) == "Watch the road."


def test_first_dialogue_candidate_returns_empty_when_only_blocked_v180():
    assert _first_dialogue_candidate(
        "SYSTEM: no\nUSER: no\nSTANCE_PACKET: no"
    ) == ""


def test_cap_words_truncates_v180():
    assert _cap_words(
        "one two three four",
        2,
    ) == "one two"


def test_strip_code_fences_removes_fences_v180():
    assert _strip_code_fences(
        "```json\n{\"text\":\"hello\"}\n```"
    ) == "{\"text\":\"hello\"}"


def test_parse_voice_response_forbidden_term_uses_fallback_v180():
    parsed = parse_voice_response(
        "The fear score is high.",
        fallback_text="Safe fallback.",
    )

    assert parsed["text"] == "Safe fallback."
    assert parsed["used_fallback"] is True
    assert "forbidden_voice_term" in parsed["warnings"]


def test_parse_voice_response_word_cap_v180():
    parsed = parse_voice_response(
        "one two three four",
        max_words=2,
    )

    assert parsed["text"] == "one two"
    assert "word_cap_applied" in parsed["warnings"]


def test_parse_voice_response_invalid_max_words_and_non_string_v180():
    parsed = parse_voice_response(
        None,
        fallback_text="Fallback.",
        max_words=0,
    )

    assert parsed["text"] == "Fallback."
    assert parsed["used_fallback"] is True
    assert "invalid_max_words" in parsed["warnings"]
    assert "non_string_response" in parsed["warnings"]
    assert "empty_response" in parsed["warnings"]


def test_parse_voice_response_json_wrapper_and_code_fence_v180():
    parsed = parse_voice_response(
        '```json\n{"dialogue": "Bring proof."}\n```'
    )

    assert parsed["text"] == "Bring proof."
    assert parsed["accepted"] is True
    assert "code_fence_removed" in parsed["warnings"]
    assert "json_wrapper_removed" in parsed["warnings"]


def test_parse_voice_response_no_candidate_empty_fallback_v180():
    parsed = parse_voice_response(
        "SYSTEM: blocked only",
        fallback_text="",
    )

    assert parsed["text"] == ""
    assert parsed["used_fallback"] is True
    assert "no_dialogue_candidate" in parsed["warnings"]
    assert "empty_after_sanitize" in parsed["warnings"]



def test_fallback_default_scene_v180():
    from ghost.llm_adapter import fallback_from_stance

    assert fallback_from_stance({}) == "What do you need?"


def test_json_voice_text_rejects_json_list_v180():
    from ghost.llm_adapter import _extract_json_voice_text

    assert _extract_json_voice_text("[1, 2, 3]") is None


def test_strip_speaker_or_field_unknown_short_label_v180():
    from ghost.llm_adapter import _strip_speaker_or_field_label

    assert _strip_speaker_or_field_label(
        "merchant: Hold the line."
    ) == "merchant: Hold the line."


def test_parse_voice_response_nul_only_becomes_empty_v180():
    from ghost.llm_adapter import parse_voice_response

    parsed = parse_voice_response(
        "\x00",
        fallback_text="Fallback.",
    )

    assert parsed["text"] == "Fallback."
    assert parsed["used_fallback"] is True
    assert "empty_response" in parsed["warnings"]


def test_parse_voice_response_plain_clean_text_v180():
    from ghost.llm_adapter import parse_voice_response

    parsed = parse_voice_response("Bring proof.")

    assert parsed["text"] == "Bring proof."
    assert parsed["accepted"] is True
    assert parsed["used_fallback"] is False
    assert parsed["warnings"] == []


def test_parse_voice_response_json_dict_without_voice_text_v180():
    from ghost.llm_adapter import parse_voice_response

    parsed = parse_voice_response(
        '{"ignored": "not a voice field"}',
        fallback_text="Fallback.",
    )

    assert parsed["text"] == '{"ignored": "not a voice field"}'
    assert parsed["used_fallback"] is False
    assert parsed["accepted"] is True



def test_fallback_crown_general_reaction_v180():
    from ghost.llm_adapter import fallback_from_stance

    text = fallback_from_stance(
        {"scene_moment": "crown_general_reaction"}
    )

    assert "old king is gone" in text
    assert "rule brings shelter" in text


def test_first_dialogue_candidate_skips_quote_only_line_v180():
    from ghost.llm_adapter import _first_dialogue_candidate

    text = """
""
NPC: Real line.
"""

    assert _first_dialogue_candidate(text) == "Real line."

