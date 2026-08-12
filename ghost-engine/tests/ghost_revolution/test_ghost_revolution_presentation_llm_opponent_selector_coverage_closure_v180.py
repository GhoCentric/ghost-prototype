from __future__ import annotations

from ghost.examples.ghost_revolution import llm_bridge
from ghost.examples.ghost_revolution import opponent_ai
from ghost.examples.ghost_revolution import presentation as p


class Game:
    def __init__(self, observation, audit=None):
        self.observation = observation
        self.audit = audit or {
            "accepted": True,
            "reaction_plan_accepted": True,
            "fallback_used": False,
            "reaction_plan_fallback_used": False,
            "forced_response_read_accepted": True,
            "forced_response_read_fallback_used": False,
            "forced_response_read_reason": "ok",
            "reason": "ok",
            "reaction_plan_reason": "ok",
        }
        self.calls = []

    def king_fight_opponent_observation(self):
        return self.observation

    def apply_king_fight_opponent_intent(self, candidate, **kwargs):
        self.calls.append((candidate, kwargs))
        return dict(self.audit)


def _clear(monkeypatch):
    for name in (
        "GHOST_REAL_LLM",
        "GHOST_LLM_OPPONENT_DEBUG",
        "GHOST_LLM_DEBUG",
    ):
        monkeypatch.delenv(name, raising=False)


def _real_observation(previous=None):
    return {
        "selection_required": True,
        "selection_key": "sel-1",
        "enemy_display_name": "King",
        "previous_exchange_evidence": previous,
    }


def _result():
    return {
        "proposed_candidate": "pressure",
        "proposed_reaction_candidate": "read_light",
        "proposed_forced_response_read_candidate": "light",
        "proposed_combat_action_candidate": "heavy",
        "proposed_feint_prediction": "feint_light",
        "provider_called": True,
        "proposal_reason": "test proposal",
        "intent_reason": "test intent",
        "reaction_reason": "test reaction",
        "response_model": None,
        "cost_estimate": {"model": "test-model"},
        "parser": {
            "reason": "parsed",
            "reaction_plan_reason": "parsed reaction",
        },
    }


def test_selector_early_returns_and_disabled_provider(monkeypatch):
    _clear(monkeypatch)

    assert p._select_king_fight_llm_opponent_intent(
        Game(None)
    ) is None

    existing = {"accepted": True}
    assert p._select_king_fight_llm_opponent_intent(
        Game({"existing_audit": existing})
    ) is existing

    locked_calls = []
    monkeypatch.setattr(
        p,
        "_king_fight_locked_audit_once",
        lambda game, observation: locked_calls.append(observation),
    )
    locked_observation = {"selection_required": False}
    assert p._select_king_fight_llm_opponent_intent(
        Game(locked_observation)
    ) is None
    assert locked_calls == [locked_observation]

    game = Game(_real_observation())
    audit = p._select_king_fight_llm_opponent_intent(game)

    assert audit["accepted"] is True
    assert game.calls[0][0] is None
    assert game.calls[0][1]["parser_reason"] == "provider_disabled"


def test_selector_real_provider_debug_covers_previous_shapes(
    monkeypatch,
    capsys,
):
    _clear(monkeypatch)
    monkeypatch.setenv("GHOST_REAL_LLM", "1")
    monkeypatch.setenv("GHOST_LLM_OPPONENT_DEBUG", "1")

    class FakeBridge:
        def __init__(self, *, client, config):
            self.client = client
            self.config = config

        def generate_king_fight_opponent_intent(self, observation):
            return _result()

    monkeypatch.setattr(llm_bridge, "OpenAIResponsesClient", lambda: "client")
    monkeypatch.setattr(llm_bridge, "config_for_role", lambda role: ("cfg", role))
    monkeypatch.setattr(opponent_ai, "GhostFightOpponentBridge", FakeBridge)
    monkeypatch.setattr(p, "_record_llm_measured_cost", lambda *args: None)
    monkeypatch.setattr(p, "_measured_cost_lines", lambda *args: ["cost-line"])
    monkeypatch.setattr(
        p,
        "panel",
        lambda title, lines: title + "\n" + "\n".join(str(x) for x in lines),
    )

    previous = {
        "enemy_intent_label": "old intent",
        "opponent_reaction_plan_label": "old reaction",
        "opponent_combat_action": "light",
        "reaction_plan_predictive": False,
        "reaction_plan_matched": True,
        "reaction_plan_triggered": True,
        "reaction_plan_missed": False,
        "reaction_miss_exposed_enemy": False,
        "reaction_miss_bonus": 1,
        "resolution_source": "ghost",
        "opponent_control_source": "ghost_resolution",
        "opponent_intent_reason": "old intent reason",
        "opponent_reaction_reason": "old reaction reason",
        "forced_response_read": "dodge",
        "forced_response_read_matched": True,
        "initiative_after": "not-a-dict",
        "predicted_feint_subtype": "feint_light",
        "selected_feint_defense": "parry",
        "feint_defense_utility": {"parry": 1},
        "bait_result": "none",
        "bait_hidden_recovery": "guard_recovery",
        "bait_player_response": "pass",
    }

    game = Game(_real_observation(previous))
    audit = p._select_king_fight_llm_opponent_intent(game)
    output = capsys.readouterr().out

    assert audit["accepted"] is True
    assert game.calls[0][0] == "pressure"
    assert game.calls[0][1]["proposed_feint_prediction"] == "feint_light"
    assert "Previous reaction matched: Not applicable" in output
    assert "Model: test-model" in output
    assert "cost-line" in output

    game = Game(_real_observation(None))
    audit = p._select_king_fight_llm_opponent_intent(game)
    output = capsys.readouterr().out

    assert audit["accepted"] is True
    assert "Previous tactic: None" in output

    previous = {
        "reaction_plan_predictive": True,
        "initiative_after": {"state": "player_advantage"},
    }
    game = Game(_real_observation(previous))
    audit = p._select_king_fight_llm_opponent_intent(game)
    output = capsys.readouterr().out
    assert audit["accepted"] is True
    assert "Previous initiative: player_advantage" in output

    class NonDictBridge(FakeBridge):
        def generate_king_fight_opponent_intent(self, observation):
            return []

    monkeypatch.setattr(opponent_ai, "GhostFightOpponentBridge", NonDictBridge)
    game = Game(_real_observation(None))
    audit = p._select_king_fight_llm_opponent_intent(game)
    output = capsys.readouterr().out
    assert audit["accepted"] is True
    assert "Provider called:" not in output


def test_selector_provider_errors_cover_long_and_short_details(
    monkeypatch,
):
    _clear(monkeypatch)
    monkeypatch.setenv("GHOST_REAL_LLM", "1")

    class RaisingBridge:
        message = ""

        def __init__(self, *, client, config):
            pass

        def generate_king_fight_opponent_intent(self, observation):
            raise RuntimeError(self.message)

    monkeypatch.setattr(llm_bridge, "OpenAIResponsesClient", lambda: "client")
    monkeypatch.setattr(llm_bridge, "config_for_role", lambda role: role)
    monkeypatch.setattr(opponent_ai, "GhostFightOpponentBridge", RaisingBridge)

    RaisingBridge.message = "x" * 250
    long_game = Game(_real_observation())
    assert p._select_king_fight_llm_opponent_intent(long_game)["accepted"] is True
    long_reason = long_game.calls[0][1]["parser_reason"]
    assert long_reason.startswith("provider_error:RuntimeError:")
    assert long_reason.endswith("...")

    RaisingBridge.message = "short"
    short_game = Game(_real_observation())
    assert p._select_king_fight_llm_opponent_intent(short_game)["accepted"] is True
    assert short_game.calls[0][1]["parser_reason"].endswith(":short")
