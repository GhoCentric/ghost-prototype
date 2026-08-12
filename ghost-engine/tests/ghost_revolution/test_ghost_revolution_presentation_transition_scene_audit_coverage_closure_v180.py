from __future__ import annotations

from types import SimpleNamespace

from ghost.examples.ghost_revolution import llm_bridge
from ghost.examples.ghost_revolution import presentation as p


def _clear_scene_env(monkeypatch):
    for name in (
        "GHOST_REAL_LLM",
        "GHOST_DEV_LLM_NARRATION",
        "GHOST_LLM_DEBUG",
        "GHOST_LLM_OPPONENT_DEBUG",
        "GHOST_LLM_OPPONENT",
    ):
        monkeypatch.delenv(name, raising=False)


def test_transition_receipt_and_opponent_env_helpers(monkeypatch, capsys):
    _clear_scene_env(monkeypatch)

    p._print_king_fight_transition_receipt({})
    assert capsys.readouterr().out == ""

    monkeypatch.setenv("GHOST_LLM_OPPONENT_DEBUG", "1")
    p._print_king_fight_transition_receipt({})
    assert capsys.readouterr().out == ""

    p._print_king_fight_transition_receipt(
        {
            "transition_trigger": {
                "player_move": "heavy",
                "king_damage": 5,
                "king_health_after_final_attack": 10,
                "king_half_health": 10,
            }
        }
    )
    output = capsys.readouterr().out
    assert "GHOST PHASE RECEIPT" in output
    assert "Resolved move: heavy" in output

    monkeypatch.delenv("GHOST_LLM_OPPONENT_DEBUG", raising=False)
    assert p._king_fight_llm_opponent_debug_enabled() is False
    monkeypatch.setenv("GHOST_LLM_DEBUG", "1")
    assert p._king_fight_llm_opponent_debug_enabled() is True
    monkeypatch.delenv("GHOST_LLM_DEBUG", raising=False)
    monkeypatch.setenv("GHOST_LLM_OPPONENT_DEBUG", "1")
    assert p._king_fight_llm_opponent_debug_enabled() is True

    monkeypatch.delenv("GHOST_LLM_OPPONENT", raising=False)
    assert p._king_fight_llm_opponent_enabled() is False
    monkeypatch.setenv("GHOST_LLM_OPPONENT", "1")
    assert p._king_fight_llm_opponent_enabled() is True

    assert p._king_fight_control_source_label(
        "llm_commitment_ghost_resolution"
    ) == "LLM commitment / Ghost resolution"
    assert p._king_fight_control_source_label(
        "llm_combat_action_ghost_matrix"
    ) == "LLM combat action / Ghost matrix"
    assert p._king_fight_control_source_label(
        "ghost_forced_continuation"
    ) == "Ghost forced continuation"
    assert p._king_fight_control_source_label(
        "ghost_parry_continuation"
    ) == "Ghost parry continuation"
    assert p._king_fight_control_source_label(
        "ghost_resolution"
    ) == "Ghost resolution"
    assert p._king_fight_control_source_label("custom") == "custom"


def test_scene_beat_all_provider_and_debug_paths(monkeypatch, capsys):
    _clear_scene_env(monkeypatch)

    calls = []

    class FakeBridge:
        def __init__(self, *, client, config):
            calls.append(("init", client, config))

        def generate_king_fight_scene_beat(self, packet, reason):
            calls.append(("generate", packet, reason))
            return {
                "text": "real beat",
                "provider_called": True,
                "response_model": None,
                "cost_estimate": {"model": "fallback-model"},
                "measured_cost": {
                    "reasoning_effort": "low",
                    "input_tokens": 2,
                    "cached_input_tokens": 0,
                    "output_tokens": 3,
                    "reasoning_tokens": 1,
                    "total_cost": 0.000001,
                },
            }

    monkeypatch.setattr(llm_bridge, "GhostRevolutionLLMBridge", FakeBridge)
    monkeypatch.setattr(llm_bridge, "OpenAIResponsesClient", lambda: "client")
    monkeypatch.setattr(llm_bridge, "config_for_role", lambda role: ("config", role))
    monkeypatch.setattr(
        llm_bridge,
        "generate_king_fight_adapter_fallback_scene_beat",
        lambda packet, reason: {
            "text": "fallback beat",
            "provider_called": False,
            "provider": "adapter",
        },
    )

    p._print_king_fight_scene_beat({"stage": "king_phase_one"}, "phase_one_start")
    assert capsys.readouterr().out == ""

    monkeypatch.setenv("GHOST_REAL_LLM", "1")
    p._print_king_fight_scene_beat({"stage": "king_phase_one"}, "phase_one_start")
    output = capsys.readouterr().out
    assert "REAL LLM SCENE BEAT" in output
    assert "real beat" in output

    monkeypatch.setenv("GHOST_LLM_DEBUG", "1")
    p._print_king_fight_scene_beat({"stage": "king_phase_one"}, "phase_one_start")
    output = capsys.readouterr().out
    assert "Reason: phase_one_start" in output
    assert "fallback-model" in output
    assert "Measured token cost" in output

    class RaisingBridge(FakeBridge):
        def generate_king_fight_scene_beat(self, packet, reason):
            raise RuntimeError("scene boom")

    monkeypatch.setattr(llm_bridge, "GhostRevolutionLLMBridge", RaisingBridge)
    p._print_king_fight_scene_beat({"stage": "elite_knight"}, "elite_knight_start")
    output = capsys.readouterr().out
    assert "LLM FAILED - SAFE SCENE BEAT" in output
    assert "Error: RuntimeError" in output

    monkeypatch.delenv("GHOST_LLM_DEBUG", raising=False)
    p._print_king_fight_scene_beat({"stage": "elite_knight"}, "elite_knight_start")
    output = capsys.readouterr().out
    assert "fallback beat" in output
    assert "Error:" not in output

    monkeypatch.delenv("GHOST_REAL_LLM", raising=False)
    monkeypatch.setenv("GHOST_DEV_LLM_NARRATION", "1")
    p._print_king_fight_scene_beat({"stage": "king_phase_two"}, "phase_two_start")
    output = capsys.readouterr().out
    assert "ADAPTER SCENE BEAT" in output
    assert "Provider:" not in output

    monkeypatch.setenv("GHOST_LLM_DEBUG", "1")
    p._print_king_fight_scene_beat({"stage": "king_phase_two"}, "phase_two_start")
    output = capsys.readouterr().out
    assert "Provider: adapter" in output
    assert any(item[0] == "generate" for item in calls)


def test_move_menu_and_transition_scene_tracking_cover_all_shapes():
    assert "guaranteed" in " ".join(
        p.king_fight_move_menu_lines({"parry_opening": {}})
    )
    assert "bait drew" in " ".join(
        p.king_fight_move_menu_lines({"bait_response": {}})
    )

    neither = p.king_fight_move_menu_lines(
        {"forced_response": {"allowed_moves": ()}}
    )
    assert "2. Light attack" not in neither
    assert "6. Dodge" not in neither

    both = p.king_fight_move_menu_lines(
        {"forced_response": {"allowed_moves": ("light", "dodge")}}
    )
    assert "2. Light attack" in both
    assert "6. Dodge" in both

    default = p.king_fight_move_menu_lines({})
    assert "3. Feint / bait" in default

    game = SimpleNamespace()
    p._king_fight_mark_transition_scene_seen(game, None)
    assert not hasattr(game, "_ghost_llm_scene_beats_seen")

    p._king_fight_mark_transition_scene_seen(game, {"outcome": "none", "stage": "none"})
    assert not hasattr(game, "_ghost_llm_scene_beats_seen")

    p._king_fight_mark_transition_scene_seen(
        game,
        {"outcome": "elite_knight_called", "stage": "king_phase_one"},
    )
    assert game._ghost_llm_scene_beats_seen == {"elite_knight_start"}

    p._king_fight_mark_transition_scene_seen(
        game,
        {"outcome": "elite_knight_defeated", "stage": "king_phase_two"},
    )
    assert game._ghost_llm_scene_beats_seen == {
        "elite_knight_start",
        "phase_two_start",
    }

    game._ghost_llm_scene_beats_seen = ["old"]
    p._king_fight_mark_transition_scene_seen(
        game,
        {"outcome": "elite_knight_called", "stage": "king_phase_one"},
    )
    assert game._ghost_llm_scene_beats_seen == {"old", "elite_knight_start"}


def _previous_evidence(*, predictive=True):
    return {
        "result": "resolved",
        "enemy_intent_label": "Royal lunge",
        "opponent_reaction_plan_label": "Read light",
        "opponent_combat_action": "heavy",
        "reaction_plan_predictive": predictive,
        "reaction_plan_matched": True,
        "reaction_plan_triggered": True,
        "reaction_plan_missed": False,
        "reaction_miss_exposed_enemy": False,
        "reaction_miss_bonus": 0,
        "resolution_source": "ghost",
        "opponent_control_source": "ghost_resolution",
        "opponent_intent_reason": "pressure",
        "opponent_reaction_reason": "history",
    }


def test_locked_audit_guards_predictive_and_deduplication(monkeypatch, capsys):
    _clear_scene_env(monkeypatch)
    game = SimpleNamespace()

    observation = {
        "selection_key": "k1",
        "locked_reason": "forced_response_pending",
        "enemy_display_name": "King",
        "previous_exchange_evidence": _previous_evidence(predictive=True),
    }

    p._king_fight_locked_audit_once(game, observation)
    assert capsys.readouterr().out == ""

    monkeypatch.setenv("GHOST_LLM_OPPONENT_DEBUG", "1")
    monkeypatch.setattr(
        p,
        "panel",
        lambda title, lines: title + "\n" + "\n".join(str(x) for x in lines),
    )
    p._king_fight_locked_audit_once(game, {"locked_reason": "other"})
    assert capsys.readouterr().out == ""

    p._king_fight_locked_audit_once(
        game,
        {
            "locked_reason": "forced_response_pending",
            "previous_exchange_evidence": None,
        },
    )
    assert capsys.readouterr().out == ""

    p._king_fight_locked_audit_once(game, observation)
    output = capsys.readouterr().out
    assert "AI OPPONENT AUDIT" in output
    assert "Previous reaction matched: True" in output
    assert "Ghost forced-response continuation" in output

    p._king_fight_locked_audit_once(game, observation)
    assert capsys.readouterr().out == ""

    parry_game = SimpleNamespace(_ghost_llm_locked_audits_seen=[])
    parry_observation = {
        "selection_key": "k2",
        "locked_reason": "parry_opening_pending",
        "enemy_display_name": "Champion",
        "previous_exchange_evidence": _previous_evidence(predictive=False),
    }
    p._king_fight_locked_audit_once(parry_game, parry_observation)
    output = capsys.readouterr().out
    assert "Previous reaction matched: Not applicable" in output
    assert "Ghost parry-opening continuation" in output
    assert isinstance(parry_game._ghost_llm_locked_audits_seen, set)
