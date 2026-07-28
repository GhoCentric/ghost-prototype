"""Regression tests for LLM audit continuity through forced combat windows."""

from ghost.examples.ghost_revolution.dev_shortcuts import (
    create_fight_stage_shortcut,
)
from ghost.examples.ghost_revolution.presentation import (
    _select_king_fight_llm_opponent_intent,
)


def _open_parry_heavy_forced_response():
    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    observation = (
        game.king_fight_opponent_observation()
    )

    game.apply_king_fight_opponent_intent(
        "overextended_recovery",
        proposed_reaction_plan="parry_heavy",
        proposed_forced_response_read="dodge",
        selection_key=observation["selection_key"],
        provider_called=True,
        intent_explanation=(
            "Show recovery and punish a heavy commitment."
        ),
        reaction_explanation=(
            "Precommit to parrying a repeated heavy attack."
        ),
    )

    packet = game.resolve_king_fight_move(
        "heavy"
    )

    assert packet["forced_response"] is not None

    return game, packet


def test_forced_window_reveals_resolved_llm_commitment_v180(
    monkeypatch,
    capsys,
):
    game, _packet = (
        _open_parry_heavy_forced_response()
    )

    monkeypatch.setenv(
        "GHOST_LLM_OPPONENT_DEBUG",
        "1",
    )
    monkeypatch.setenv(
        "GHOST_LLM_OPPONENT",
        "1",
    )
    monkeypatch.delenv(
        "GHOST_REAL_LLM",
        raising=False,
    )

    result = (
        _select_king_fight_llm_opponent_intent(
            game
        )
    )

    output = capsys.readouterr().out

    assert result is None
    assert "AI OPPONENT AUDIT" in output
    assert "Previous tactic: Open Recovery" in output
    assert "Previous hidden reaction: Parry Heavy" in output
    assert "Previous reaction matched: True" in output
    assert "New tactic selection: deferred" in output
    assert "forced_response_pending" in output
    assert "Provider called: False" in output


def test_forced_window_audit_prints_only_once_v180(
    monkeypatch,
    capsys,
):
    game, _packet = (
        _open_parry_heavy_forced_response()
    )

    monkeypatch.setenv(
        "GHOST_LLM_OPPONENT_DEBUG",
        "1",
    )

    _select_king_fight_llm_opponent_intent(
        game
    )
    first = capsys.readouterr().out

    _select_king_fight_llm_opponent_intent(
        game
    )
    second = capsys.readouterr().out

    assert "AI OPPONENT AUDIT" in first
    assert second == ""


def test_forced_recovery_preserves_source_commitment_v180():
    game, first = (
        _open_parry_heavy_forced_response()
    )

    forced = first["forced_response"]

    assert "selected_move" not in forced["recovery_read"]

    second = game.resolve_king_fight_move(
        "light"
    )

    exchange = second["exchange"]
    source = exchange[
        "source_opponent_commitment"
    ]

    assert exchange["resolution_source"] == (
        "forced_response_read"
    )
    assert exchange["opponent_control_source"] == (
        "ghost_forced_continuation"
    )
    assert exchange[
        "opponent_reaction_plan_label"
    ] == "Forced Recovery Read"
    assert exchange["forced_response_read"] == "dodge"
    assert exchange["forced_response_read_matched"] is False
    assert exchange["king_damage"] == 1
    assert exchange["player_damage"] == 0
    assert source["intent"] == "overextended_recovery"
    assert source["intent_label"] == "Open Recovery"
    assert source["reaction_plan"] == "parry_heavy"
    assert source["reaction_plan_label"] == (
        "Parry Heavy"
    )

    observation = (
        game.king_fight_opponent_observation()
    )
    previous = observation[
        "previous_exchange_evidence"
    ]

    assert previous["opponent_control_source"] == (
        "ghost_forced_continuation"
    )
    assert previous[
        "opponent_reaction_plan_label"
    ] == "Forced Recovery Read"
    assert previous["reaction_plan_predictive"] is True
    assert previous["forced_response_read"] == "dodge"
    assert previous["forced_response_read_matched"] is False
    assert "hidden light-or-dodge contingency" in previous[
        "opponent_reaction_reason"
    ]


def test_next_audit_labels_forced_continuation_truth_v180(
    monkeypatch,
    capsys,
):
    game, first = (
        _open_parry_heavy_forced_response()
    )

    forced = first["forced_response"]

    assert "selected_move" not in forced["recovery_read"]

    game.resolve_king_fight_move(
        "light"
    )

    monkeypatch.setenv(
        "GHOST_LLM_OPPONENT_DEBUG",
        "1",
    )
    monkeypatch.delenv(
        "GHOST_REAL_LLM",
        raising=False,
    )

    _select_king_fight_llm_opponent_intent(
        game
    )

    output = capsys.readouterr().out

    assert "Previous hidden reaction: Forced Recovery" in output
    assert "Previous reaction predictive: True" in output
    assert "Previous control source: Ghost forced" in output
    assert "continuation" in output
    assert "Previous forced read: dodge" in output
    assert "Previous forced read matched: False" in output
    assert "without randomness" in output
