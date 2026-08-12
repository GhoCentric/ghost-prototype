import pytest

from ghost.examples.ghost_revolution.dev_shortcuts import (
    create_fight_stage_shortcut,
)
from ghost.examples.ghost_revolution import symmetric_combat as sc


class Bare:
    pass


class NoRandomDraw:
    def randint(self, low, high):
        raise AssertionError("symmetric combat must not use random draws")


def _prepared(stage="prepared_king"):
    game, _packet = create_fight_stage_shortcut(stage)
    game.rng = NoRandomDraw()
    return game


def _lock(
    game,
    *,
    intent,
    reaction,
    combat_action,
    prediction="none",
):
    game.king_fight["intent"] = intent
    observation = game.king_fight_opponent_observation()
    audit = game.apply_king_fight_opponent_intent(
        intent,
        proposed_reaction_plan=reaction,
        proposed_combat_action=combat_action,
        proposed_feint_prediction=prediction,
        proposed_forced_response_read="dodge",
        selection_key=observation["selection_key"],
        provider_called=True,
    )
    assert audit["combat_action_accepted"] is True
    return audit


def test_symmetric_private_normalization_prediction_and_fallback_edges_v180():
    assert sc._normalize(None) is None
    assert sc._normalize("   ") is None
    assert sc._normalize("Feint-Heavy") == "feint_heavy"

    assert sc._pending_action(Bare()) is None

    dummy = Bare()
    dummy.king_fight = {
        "stage": "king_phase_one",
        "exchange_count": 0,
        "llm_opponent_combat_action_selection_key": "wrong",
        "llm_opponent_combat_action": "heavy",
    }
    assert sc._pending_action(dummy) is None

    dummy.king_fight[
        "llm_opponent_combat_action_selection_key"
    ] = "king_phase_one:0"
    dummy.king_fight["llm_opponent_combat_action"] = "unknown"
    assert sc._pending_action(dummy) is None
    assert sc._consume_action(dummy) is None

    no_audit = sc._prediction_packet(None, "heavy")
    assert no_audit == {
        "prediction": None,
        "feint_prediction": None,
        "predictive": False,
        "matched": None,
        "missed": None,
    }

    none_prediction = sc._prediction_packet(
        {
            "proposed_reaction_plan": "hold center",
            "proposed_feint_prediction": "none",
        },
        "heavy",
    )
    assert none_prediction["prediction"] is None

    invalid_prediction = sc._prediction_packet(
        {
            "selected_reaction_plan": "read_feint_light",
            "selected_feint_prediction": "invalid",
        },
        "feint_light",
    )
    assert invalid_prediction["prediction"] == "feint_light"
    assert invalid_prediction["matched"] is True

    assert sc._player_damage_for_move("deflect") == 2
    assert sc._fallback_combat_action(None) == "dodge"
    assert sc._fallback_combat_action(
        {"fallback_intent": "royal_lunge"}
    ) == "heavy"
    assert sc._fallback_combat_action(
        {"selected_intent": "unknown"}
    ) == "dodge"


@pytest.mark.parametrize(
    ("player_move", "enemy_action", "prediction", "initiative", "expected"),
    (
        ("feint_bait", "feint_bait", None, "neutral", "double_bait_standoff"),
        ("feint_bait", "parry", "feint_bait", "neutral", "enemy_reads_bait"),
        ("dodge", "feint_bait", None, "neutral", "opponent_bait_refused"),
        ("parry", "dodge", None, "neutral", "mutual_defense"),
        ("feint_light", "parry", None, "neutral", "player_attack_beats_defense"),
        ("dodge", "heavy", None, "neutral", "player_dodge"),
        ("deflect", "light", None, "neutral", "player_deflect"),
        ("heavy", "heavy", None, "enemy_advantage", "enemy_initiative_breaks_clash"),
        ("heavy", "heavy", None, "player_advantage", "player_initiative_breaks_clash"),
        ("heavy", "heavy", None, "neutral", "attack_clash"),
    ),
)
def test_symmetric_action_matrix_remaining_outcomes_v180(
    player_move,
    enemy_action,
    prediction,
    initiative,
    expected,
):
    packet = sc._resolve_pair(
        "king",
        player_move,
        enemy_action,
        prediction,
        initiative,
    )

    assert packet["result"] == expected


def test_symmetric_exchange_delegates_when_locked_action_is_stale_v180(monkeypatch):
    calls = []

    monkeypatch.setattr(
        sc,
        "_ORIGINAL_RESOLVE_KING_PHASE",
        lambda self, move: calls.append(("king", move)) or {"source": "king"},
    )
    monkeypatch.setattr(
        sc,
        "_ORIGINAL_RESOLVE_ELITE",
        lambda self, move: calls.append(("elite", move)) or {"source": "elite"},
    )

    dummy = Bare()
    dummy.king_fight = {
        "stage": "king_phase_one",
        "exchange_count": 0,
        "llm_opponent_combat_action_selection_key": "stale",
        "llm_opponent_combat_action": "heavy",
    }

    assert sc._resolve_symmetric_exchange(dummy, "heavy", "king") == {
        "source": "king"
    }

    dummy.king_fight.update(
        llm_opponent_combat_action_selection_key="stale",
        llm_opponent_combat_action="heavy",
    )

    assert sc._resolve_symmetric_exchange(
        dummy,
        "heavy",
        "elite_knight",
    ) == {"source": "elite"}
    assert calls == [("king", "heavy"), ("elite", "heavy")]


def test_symmetric_king_player_death_transition_and_endings_v180():
    death = _prepared()
    death.king_fight["player_health"] = 1
    _lock(
        death,
        intent="royal_lunge",
        reaction="commit_attack",
        combat_action="heavy",
    )
    packet = death.resolve_king_fight_move("deflect")
    assert packet["outcome"] == "player_killed_by_king"

    transition = _prepared()
    transition.king_fight["king_health"] = (
        transition.king_fight["king_half_health"] + 2
    )
    _lock(
        transition,
        intent="royal_lunge",
        reaction="commit_attack",
        combat_action="heavy",
    )
    packet = transition.resolve_king_fight_move("light")
    assert packet["outcome"] == "elite_knight_called"
    assert packet["stage"] == "elite_knight"
    assert "narrative" in packet

    non_dict_transition = _prepared()
    non_dict_transition.king_fight["king_health"] = (
        non_dict_transition.king_fight["king_half_health"] + 2
    )
    non_dict_transition._transition_to_elite_knight = lambda: "transitioned"
    _lock(
        non_dict_transition,
        intent="royal_lunge",
        reaction="commit_attack",
        combat_action="heavy",
    )
    packet = non_dict_transition.resolve_king_fight_move("light")
    assert packet == "transitioned"

    clean = _prepared("king_phase_two")
    clean.king_fight["king_health"] = 2
    clean.king_fight["clean_king_victory_possible"] = True
    _lock(
        clean,
        intent="royal_lunge",
        reaction="commit_attack",
        combat_action="heavy",
    )
    packet = clean.resolve_king_fight_move("light")
    assert packet["outcome"] == "clean_king_victory"

    uncertain = _prepared("king_phase_two")
    uncertain.king_fight["king_health"] = 2
    uncertain.king_fight["clean_king_victory_possible"] = False
    _lock(
        uncertain,
        intent="royal_lunge",
        reaction="commit_attack",
        combat_action="heavy",
    )
    packet = uncertain.resolve_king_fight_move("light")
    assert packet["outcome"] == "uncertain_king_fall"


def test_symmetric_king_and_elite_castle_collapse_paths_v180():
    king = _prepared()
    king.king_fight["castle_timer"] = 1
    _lock(
        king,
        intent="royal_lunge",
        reaction="commit_attack",
        combat_action="heavy",
    )
    packet = king.resolve_king_fight_move("parry")
    assert packet["outcome"] == "castle_collapse_legend"

    transition = _prepared()
    transition.king_fight["castle_timer"] = 1
    transition.king_fight["king_health"] = (
        transition.king_fight["king_half_health"] + 2
    )
    _lock(
        transition,
        intent="royal_lunge",
        reaction="commit_attack",
        combat_action="heavy",
    )
    packet = transition.resolve_king_fight_move("light")
    assert packet["outcome"] == "castle_collapse_legend"

    elite_defeat = _prepared("champion")
    elite_defeat.king_fight["elite_knight_health"] = 2
    elite_defeat.king_fight["castle_timer"] = 2
    _lock(
        elite_defeat,
        intent="shield_wall",
        reaction="commit_attack",
        combat_action="heavy",
    )
    packet = elite_defeat.resolve_king_fight_move("light")
    assert packet["outcome"] == "elite_knight_defeated"

    elite_collapse = _prepared("champion")
    elite_collapse.king_fight["elite_knight_health"] = 2
    elite_collapse.king_fight["castle_timer"] = 1
    _lock(
        elite_collapse,
        intent="shield_wall",
        reaction="commit_attack",
        combat_action="heavy",
    )
    packet = elite_collapse.resolve_king_fight_move("light")
    assert packet["outcome"] == "castle_collapse_legend"

    elite_normal = _prepared("champion")
    elite_normal.king_fight["castle_timer"] = 1
    _lock(
        elite_normal,
        intent="shield_wall",
        reaction="commit_attack",
        combat_action="heavy",
    )
    packet = elite_normal.resolve_king_fight_move("parry")
    assert packet["outcome"] == "castle_collapse_legend"


def test_symmetric_apply_observation_and_wrapper_fallback_edges_v180(monkeypatch):
    monkeypatch.setattr(sc, "_ORIGINAL_APPLY", lambda *args, **kwargs: "not-a-dict")
    assert sc._apply_with_combat_action(
        Bare(),
        None,
        selection_key="x",
    ) == "not-a-dict"

    class ApplyOwner:
        king_fight = None

    monkeypatch.setattr(
        sc,
        "_ORIGINAL_APPLY",
        lambda *args, **kwargs: {
            "selected_intent": "royal_lunge",
            "selected_reaction_plan": "commit_attack",
        },
    )
    audit = sc._apply_with_combat_action(
        ApplyOwner(),
        "royal_lunge",
        selection_key="king_phase_one:0",
        proposed_combat_action="illegal",
        provider_called=False,
    )
    assert audit["selected_combat_action"] is None
    assert audit["combat_action_reason"] == "illegal_combat_action"

    owner = ApplyOwner()
    owner.king_fight = {
        "stage": "king_phase_one",
        "exchange_count": 0,
        "llm_opponent_history": [],
    }
    audit = sc._apply_with_combat_action(
        owner,
        "royal_lunge",
        selection_key="wrong",
        proposed_combat_action=None,
        provider_called=False,
    )
    assert audit["combat_action_reason"] == "missing_combat_action"
    assert "llm_opponent_combat_action" not in owner.king_fight

    owner.king_fight["llm_opponent_history"] = "not-a-list"
    audit = sc._apply_with_combat_action(
        owner,
        "royal_lunge",
        selection_key="king_phase_one:0",
        proposed_combat_action="heavy",
        provider_called=True,
    )
    assert audit["selected_combat_action"] == "heavy"

    monkeypatch.setattr(sc, "_ORIGINAL_OBSERVATION", lambda self: "not-a-dict")
    assert sc._observation_with_combat_actions(Bare()) == "not-a-dict"

    observation_owner = Bare()
    observation_owner.king_fight = {
        "last_exchange": {
            "opponent_combat_action": "heavy",
            "opponent_action_effective": True,
            "prediction_action_separated": True,
        }
    }
    monkeypatch.setattr(
        sc,
        "_ORIGINAL_OBSERVATION",
        lambda self: {"previous_exchange_evidence": {}},
    )
    observation = sc._observation_with_combat_actions(observation_owner)
    assert observation["previous_exchange_evidence"] == {
        "opponent_combat_action": "heavy",
        "opponent_action_effective": True,
        "prediction_action_separated": True,
    }

    observation_owner.king_fight["last_exchange"] = {}
    observation = sc._observation_with_combat_actions(observation_owner)
    assert observation["previous_exchange_evidence"] == {}

    monkeypatch.setattr(
        sc,
        "_ORIGINAL_RESOLVE_KING_PHASE",
        lambda self, move: {"fallback": "king"},
    )
    monkeypatch.setattr(
        sc,
        "_ORIGINAL_RESOLVE_ELITE",
        lambda self, move: {"fallback": "elite"},
    )
    monkeypatch.setattr(
        sc,
        "_ORIGINAL_RESOLVE_FIGHT",
        lambda self, move: {"fallback": "fight"},
    )

    fallback = Bare()
    fallback.king_fight = {
        "stage": "unknown",
        "exchange_count": 0,
    }
    assert sc._resolve_king_with_action(fallback, "heavy") == {
        "fallback": "king"
    }
    assert sc._resolve_elite_with_action(fallback, "heavy") == {
        "fallback": "elite"
    }
    assert sc._resolve_fight_with_action(fallback, "heavy") == {
        "fallback": "fight"
    }

    pending_unknown = Bare()
    pending_unknown.king_fight = {
        "stage": "unknown",
        "exchange_count": 0,
        "llm_opponent_combat_action_selection_key": "unknown:0",
        "llm_opponent_combat_action": "heavy",
        "forced_response": None,
        "parry_opening": None,
        "bait_response": None,
    }
    assert sc._resolve_fight_with_action(pending_unknown, "heavy") == {
        "fallback": "fight"
    }

    no_fight = Bare()
    assert sc._resolve_fight_with_action(no_fight, "heavy") == {
        "fallback": "fight"
    }


def test_symmetric_direct_stage_wrappers_dispatch_v180(monkeypatch):
    calls = []

    monkeypatch.setattr(
        sc,
        "_resolve_symmetric_exchange",
        lambda self, move, actor: calls.append((move, actor)) or {"actor": actor},
    )

    owner = Bare()
    owner.king_fight = {
        "stage": "king_phase_one",
        "exchange_count": 0,
        "llm_opponent_combat_action_selection_key": "king_phase_one:0",
        "llm_opponent_combat_action": "heavy",
        "forced_response": None,
        "parry_opening": None,
        "bait_response": None,
    }
    assert sc._resolve_king_with_action(owner, "heavy") == {"actor": "king"}

    owner.king_fight.update(
        stage="elite_knight",
        llm_opponent_combat_action_selection_key="elite_knight:0",
        llm_opponent_combat_action="heavy",
    )
    assert sc._resolve_elite_with_action(owner, "heavy") == {
        "actor": "elite_knight"
    }
    assert sc._resolve_fight_with_action(owner, "heavy") == {
        "actor": "elite_knight"
    }
    assert calls == [
        ("heavy", "king"),
        ("heavy", "elite_knight"),
        ("heavy", "elite_knight"),
    ]
