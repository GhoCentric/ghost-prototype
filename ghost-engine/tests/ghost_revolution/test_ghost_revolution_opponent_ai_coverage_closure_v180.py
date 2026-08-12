from copy import deepcopy
import json

import pytest

from ghost.examples.ghost_revolution.dev_shortcuts import (
    create_fight_stage_shortcut,
)
from ghost.examples.ghost_revolution.llm_bridge import (
    LLMBridgeConfig,
)
from ghost.examples.ghost_revolution import opponent_ai as oa


def _game(stage="prepared_king"):
    game, _packet = create_fight_stage_shortcut(stage)
    return game


def _lock(
    game,
    *,
    intent,
    reaction,
    combat_action="dodge",
    feint_prediction="none",
    forced_read="dodge",
):
    game.king_fight["intent"] = intent
    observation = game.king_fight_opponent_observation()
    return game.apply_king_fight_opponent_intent(
        intent,
        proposed_reaction_plan=reaction,
        proposed_combat_action=combat_action,
        proposed_feint_prediction=feint_prediction,
        proposed_forced_response_read=forced_read,
        selection_key=observation["selection_key"],
        provider_called=True,
        intent_explanation="intent evidence",
        reaction_explanation="reaction evidence",
    )


def _bait_packet(target="king", recovery="guard_recovery"):
    return {
        "allowed_moves": ("light", "parry", "pass"),
        "bait_recovery": {
            "selected_recovery": recovery,
            "utility_scores": {
                "quick_retaliation": 48,
                "guard_recovery": 48,
            },
        },
        "target": target,
        "intent": (
            "shield_wall"
            if target == "elite_knight"
            else "crown_guard"
        ),
        "source_commitment": {
            "reaction_plan": "read_feint_heavy",
            "reaction_plan_label": "Read Feint Heavy",
            "predicted_feint_subtype": "feint_heavy",
            "intent_reason": "intent evidence",
            "reaction_reason": "reaction evidence",
        },
    }


def test_prompt_normalizes_non_mapping_sections_v180():
    prompt = oa.build_king_fight_opponent_intent_prompt(
        {
            "legal_intents": ["crown_guard"],
            "intent_labels": [],
            "intent_options": [],
            "legal_reaction_plans_by_intent": [],
            "reaction_plan_labels": [],
            "combat_objective": [],
            "combat_initiative": [],
        }
    )

    assert "OPPONENT_OBSERVATION" in prompt
    payload = json.loads(prompt.split("OPPONENT_OBSERVATION:\n", 1)[1])
    assert payload["intent_labels"] == {"crown_guard": "crown_guard"}
    assert payload["intent_options"] == {"crown_guard": None}
    assert payload["legal_reaction_plans_by_intent"] == {
        "crown_guard": []
    }
    assert payload["reaction_plan_labels"] == {}
    assert payload["combat_objective"] == {}
    assert payload["combat_initiative"] == {}


def test_parser_covers_fences_embedded_tokens_and_invalid_fields_v180():
    legal = ("crown_guard", "royal_lunge")
    reactions = {
        None: ("ignored",),
        "crown_guard": ("hold_center",),
        "royal_lunge": ("commit_attack",),
    }

    fenced = oa.parse_king_fight_opponent_intent(
        "```json\n"
        '{"intent":"crown_guard","reaction_plan":"hold_center",'
        '"combat_action":"heavy","feint_prediction":"none",'
        '"forced_response_read":"light"}\n```',
        legal,
        reactions,
    )
    assert fenced["accepted"] is True
    assert fenced["parse_mode"] == "json"

    embedded = oa.parse_king_fight_opponent_intent(
        "strategy follows: "
        '{"intent":"royal_lunge","reaction_plan":"commit_attack",'
        '"combat_action":"light","feint_prediction":"none",'
        '"forced_response_read":"dodge"} trailing',
        legal,
        reactions,
    )
    assert embedded["parse_mode"] == "embedded_json"
    assert embedded["accepted"] is True

    plain = oa.parse_king_fight_opponent_intent(
        " Crown Guard ",
        legal,
    )
    assert plain["accepted"] is True
    assert plain["parse_mode"] == "plain_legal_token"

    invalid_plain = oa.parse_king_fight_opponent_intent(
        "not a legal token",
        legal,
    )
    assert invalid_plain["accepted"] is False
    assert invalid_plain["reason"] == "invalid_format"

    invalid_json_shape = oa.parse_king_fight_opponent_intent(
        "[1, 2, 3]",
        legal,
    )
    assert invalid_json_shape["accepted"] is False

    malformed_embedded = oa.parse_king_fight_opponent_intent(
        "prefix {not-json} suffix",
        legal,
    )
    assert malformed_embedded["accepted"] is False

    illegal_fields = oa.parse_king_fight_opponent_intent(
        '{"intent":"crown_guard","reaction_plan":"hold_center",'
        '"combat_action":"teleport","feint_prediction":"unknown",'
        '"forced_response_read":"roll"}',
        legal,
        reactions,
    )
    assert illegal_fields["combat_action_reason"] == "illegal_combat_action"
    assert illegal_fields["forced_response_read_reason"] == (
        "illegal_forced_response_read"
    )
    assert illegal_fields["feint_prediction"] is None

    missing_intent = oa.parse_king_fight_opponent_intent(
        '{"reaction_plan":"hold_center"}',
        legal,
        reactions,
    )
    assert missing_intent["reason"] == "invalid_format"


def test_bridge_without_client_uses_empty_normalized_response_v180():
    bridge = oa.GhostFightOpponentBridge(
        client=None,
        config=LLMBridgeConfig(
            max_output_tokens=9999,
            hard_max_output_tokens=9999,
        ),
    )
    observation = {
        "legal_intents": ["crown_guard"],
        "legal_reaction_plans_by_intent": {
            "crown_guard": ["hold_center"]
        },
        "legal_forced_response_reads": ["light", "dodge"],
    }

    prepared = bridge.prepare_king_fight_opponent_intent(observation)
    assert prepared["output_token_limit"] == oa.OPPONENT_OUTPUT_TOKENS

    result = bridge.generate_king_fight_opponent_intent(observation)
    assert result["provider_called"] is False
    assert result["raw_text"] == ""
    assert result["parser"]["accepted"] is False


def test_layered_patterns_repairs_corrupt_histories_v180():
    game = _game()
    patterns = game._ensure_king_fight_pattern_state()
    patterns["last_feint_defenses"] = "bad"
    patterns["last_bait_recoveries"] = {"bad": True}

    repaired = oa._ghost_layered_patterns(game)

    assert repaired["last_feint_defenses"] == []
    assert repaired["last_bait_recoveries"] == []


@pytest.mark.parametrize(
    "predicted,initiative,enemy_health,player_health,timer,last_moves",
    [
        ("light", "neutral", 20, 10, 8, ["feint_light", "feint_light"]),
        ("heavy", "enemy_advantage", 20, 10, 8, ["feint_heavy", "feint_heavy"]),
        ("heavy", "player_advantage", 6, 3, 3, ["feint_heavy", "feint_heavy"]),
        ("unknown", "neutral", 20, 10, 12, []),
    ],
)
def test_feint_defense_scoring_covers_all_utility_inputs_v180(
    predicted,
    initiative,
    enemy_health,
    player_health,
    timer,
    last_moves,
):
    game = _game()
    game.king_fight["king_health"] = enemy_health
    game.king_fight["player_health"] = player_health
    game.king_fight["castle_timer"] = timer
    game.king_fight["initiative"]["state"] = initiative
    patterns = oa._ghost_layered_patterns(game)
    patterns["last_moves"] = last_moves + [None]
    patterns["last_feint_defenses"] = ["parry", "deflect", "dodge"]

    result = oa._ghost_layered_score_feint_defenses(
        game,
        enemy_actor="king",
        predicted_follow_up=predicted,
    )

    assert result["selected_defense"] in {"parry", "deflect", "dodge"}
    assert result["random_used"] is False


@pytest.mark.parametrize(
    "initiative,enemy_health,timer,last_moves",
    [
        ("enemy_advantage", 20, 8, ["light"]),
        ("player_advantage", 20, 8, ["parry"]),
        ("neutral", 6, 3, ["parry", "light"]),
        ("neutral", 20, 12, []),
    ],
)
def test_bait_recovery_scoring_covers_all_utility_inputs_v180(
    initiative,
    enemy_health,
    timer,
    last_moves,
):
    game = _game()
    game.king_fight["king_health"] = enemy_health
    game.king_fight["castle_timer"] = timer
    game.king_fight["initiative"]["state"] = initiative
    patterns = oa._ghost_layered_patterns(game)
    patterns["last_moves"] = last_moves + [None]
    patterns["last_bait_recoveries"] = [
        "quick_retaliation",
        "guard_recovery",
    ]

    result = oa._ghost_layered_select_bait_recovery(game, "king")

    assert result["selected_recovery"] in {
        "quick_retaliation",
        "guard_recovery",
    }
    assert result["locked"] is True


def test_precommitted_reaction_covers_misses_and_defense_messages_v180(
    monkeypatch,
):
    game = _game()

    assert game._precommitted_opponent_reaction(
        "king",
        "light",
        "crown_guard",
        "read_feint_heavy",
    ) is None

    def scored(selected):
        return {
            "selected_defense": selected,
            "utility_scores": {},
            "inputs": {},
            "random_used": False,
            "state_owner": "Ghost",
        }

    for selected in ("deflect", "dodge"):
        monkeypatch.setattr(
            oa,
            "_ghost_layered_score_feint_defenses",
            lambda *args, _selected=selected, **kwargs: scored(_selected),
        )
        packet = game._precommitted_opponent_reaction(
            "elite_knight" if selected == "dodge" else "king",
            "feint_light",
            "shield_wall" if selected == "dodge" else "crown_guard",
            "read_feint_light",
        )
        assert packet["selected_feint_defense"] == selected
        assert packet["player_damage_mode"] == "none"

    assert game._precommitted_opponent_reaction(
        "king",
        "heavy",
        "crown_guard",
        "read_feint_bait",
    ) is None

    king_bait = game._precommitted_opponent_reaction(
        "king",
        "feint_bait",
        "crown_guard",
        "read_feint_bait",
    )
    champion_bait = game._precommitted_opponent_reaction(
        "elite_knight",
        "feint_bait",
        "shield_wall",
        "read_feint_bait",
    )
    assert king_bait["type"] == "king_reads_bait"
    assert champion_bait["type"] == "champion_reads_bait"


def test_public_bait_response_and_builder_cover_conversion_branches_v180():
    game = _game()
    assert game._public_bait_response(None) is None

    public = game._public_bait_response(
        {
            "allowed_moves": ("light", "parry", "pass"),
            "bait_recovery": {
                "selected_recovery": "guard_recovery",
            },
        }
    )
    assert public["allowed_moves"] == ["light", "parry", "pass"]
    assert "selected_recovery" not in public["bait_recovery"]

    unchanged = game._public_bait_response(
        {"allowed_moves": ["light"], "bait_recovery": "bad"}
    )
    assert unchanged["bait_recovery"] == "bad"

    built = oa._ghost_layered_build_bait_response(
        game,
        enemy_actor="king",
        intent="crown_guard",
        reaction_plan="read_feint_heavy",
        reaction_prediction={
            "predicted_feint_subtype": "feint_heavy",
            "predictive": True,
            "matched": False,
            "missed": True,
        },
        active_audit={
            "intent_reason": "intent evidence",
            "reaction_reason": "reaction evidence",
        },
        next_intent="royal_lunge",
    )
    assert built["kind"] == "bait_response"
    assert built["source_commitment"]["intent_reason"] == "intent evidence"

    built_no_audit = oa._ghost_layered_build_bait_response(
        game,
        enemy_actor="king",
        intent="crown_guard",
        reaction_plan="read_feint_heavy",
        reaction_prediction={
            "predicted_feint_subtype": None,
            "predictive": False,
            "matched": None,
            "missed": None,
        },
        active_audit=None,
        next_intent="royal_lunge",
    )
    assert built_no_audit["source_commitment"]["intent_reason"] is None

    elite = oa._ghost_layered_bait_target_keys("elite_knight")
    king = oa._ghost_layered_bait_target_keys("king")
    assert elite["health_key"] == "elite_knight_health"
    assert king["health_key"] == "king_health"


def test_bait_response_dispatch_and_resolution_variants_v180(monkeypatch):
    game = _game()
    game.king_fight["bait_response"] = None
    direct = oa._ghost_layered_resolve_bait_response(game, "light")
    assert isinstance(direct, dict)

    denied_game = _game()
    denied_game.king_fight["bait_response"] = _bait_packet()
    denied = denied_game.resolve_king_fight_move("heavy")
    assert denied["outcome"] == "bait_response_denied"

    missing_recovery = _game()
    packet = _bait_packet()
    packet["bait_recovery"] = "bad"
    missing_recovery.king_fight["bait_response"] = packet
    monkeypatch.setattr(
        oa,
        "_ghost_layered_select_bait_recovery",
        lambda *args, **kwargs: {
            "selected_recovery": "guard_recovery",
            "utility_scores": {},
        },
    )
    recovered = missing_recovery.resolve_king_fight_move("light")
    assert recovered["exchange"]["result"] == "bait_light_landed"

    parry_game = _game()
    parry_game.king_fight["bait_response"] = _bait_packet(
        recovery="quick_retaliation"
    )
    parried = parry_game.resolve_king_fight_move("parry")
    assert parried["exchange"]["result"] == "bait_parry_success"
    assert parried["parry_opening"] is not None

    pass_game = _game()
    pass_game.king_fight["bait_response"] = _bait_packet()
    passed = pass_game.resolve_king_fight_move("3")
    assert passed["exchange"]["result"] == "bait_opening_passed"

    wrong_game = _game()
    wrong_game.king_fight["bait_response"] = _bait_packet(
        recovery="quick_retaliation"
    )
    wrong = wrong_game.resolve_king_fight_move("light")
    assert wrong["exchange"]["result"] == "bait_recovery_denied"


def test_elite_bait_response_covers_packet_transition_and_collapse_v180():
    elite = _game("elite_knight")
    elite.king_fight["bait_response"] = _bait_packet(
        target="elite_knight",
        recovery="quick_retaliation",
    )
    packet = elite.resolve_king_fight_move("light")
    assert packet["outcome"] == "elite_knight_bait_response"
    assert "elite_knight_health" in packet
    assert packet["exchange"]["king_damage"] == 0

    defeated = _game("elite_knight")
    defeated.king_fight["elite_knight_health"] = 2
    defeated.king_fight["bait_response"] = _bait_packet(
        target="elite_knight",
        recovery="guard_recovery",
    )
    transition = defeated.resolve_king_fight_move("light")
    assert transition["outcome"] == "elite_knight_defeated"
    assert transition["stage"] == "king_phase_two"

    collapse = _game("elite_knight")
    collapse.king_fight["elite_knight_health"] = 2
    collapse.king_fight["castle_timer"] = 1
    collapse.king_fight["bait_response"] = _bait_packet(
        target="elite_knight",
        recovery="guard_recovery",
    )
    collapsed = collapse.resolve_king_fight_move("light")
    assert collapsed["outcome"] == "castle_collapse_legend"

    ordinary_collapse = _game("elite_knight")
    ordinary_collapse.king_fight["castle_timer"] = 1
    ordinary_collapse.king_fight["bait_response"] = _bait_packet(
        target="elite_knight",
        recovery="quick_retaliation",
    )
    collapsed = ordinary_collapse.resolve_king_fight_move("light")
    assert collapsed["outcome"] == "castle_collapse_legend"


def test_feint_bait_resolution_covers_guard_attack_and_death_paths_v180():
    read_game = _game()
    _lock(
        read_game,
        intent="crown_guard",
        reaction="read_feint_bait",
        combat_action="parry",
        feint_prediction="feint_bait",
    )
    read = oa._ghost_layered_resolve_feint_bait(read_game, "king")
    assert read["exchange"]["result"] == "king_reads_bait"

    setup_game = _game()
    audit = _lock(
        setup_game,
        intent="crown_guard",
        reaction="read_feint_heavy",
        combat_action="parry",
        feint_prediction="feint_heavy",
    )
    assert audit["accepted"] is True
    setup = oa._ghost_layered_resolve_feint_bait(setup_game, "king")
    assert setup["exchange"]["result"] == "bait_setup"
    assert setup["bait_response"] is not None

    no_commit = _game()
    _lock(
        no_commit,
        intent="crown_guard",
        reaction="hold_center",
        combat_action="dodge",
    )
    no_commit_packet = oa._ghost_layered_resolve_feint_bait(
        no_commit,
        "king",
    )
    assert no_commit_packet["exchange"]["result"] == "bait_no_commit"

    king_hit = _game()
    king_hit.king_fight["intent"] = "royal_lunge"
    king_hit.king_fight["player_health"] = 10
    hit = oa._ghost_layered_resolve_feint_bait(king_hit, "king")
    assert hit["exchange"]["result"] == "king_hit"
    assert king_hit.king_fight["clean_king_victory_possible"] is False

    champion_hit = _game("elite_knight")
    champion_hit.king_fight["intent"] = "champion_lunge"
    old_health = champion_hit.king_fight["king_health"]
    hit = oa._ghost_layered_resolve_feint_bait(
        champion_hit,
        "elite_knight",
    )
    assert hit["exchange"]["result"] == "failed_knight_read"
    assert champion_hit.king_fight["failed_knight_reads"] == 1
    assert champion_hit.king_fight["king_health"] >= old_health

    death = _game()
    death.king_fight["intent"] = "royal_lunge"
    death.king_fight["player_health"] = 1
    dead = oa._ghost_layered_resolve_feint_bait(death, "king")
    assert dead["outcome"] == "player_killed_by_king"


def test_enrichment_dispatch_observation_status_and_tell_branches_v180(
    monkeypatch,
):
    game = _game()

    assert oa._ghost_layered_enrich_reaction_packet(game, "bad") == "bad"
    assert oa._ghost_layered_enrich_reaction_packet(game, {}) == {}
    assert oa._ghost_layered_enrich_reaction_packet(
        game,
        {"exchange": {}},
    ) == {"exchange": {}}

    packet = {
        "exchange": {
            "opponent_reaction_plan": "read_feint_heavy",
            "opponent_reaction": {
                "selected_feint_defense": "parry",
                "feint_defense_utility": {"score": 1},
                "bait_result": "x",
            },
        }
    }
    game.king_fight["last_exchange"] = {}
    enriched = oa._ghost_layered_enrich_reaction_packet(game, packet)
    assert enriched["exchange"]["predicted_feint_subtype"] == "feint_heavy"
    assert game.king_fight["last_exchange"]["selected_feint_defense"] == "parry"

    game.king_fight["bait_response"] = _bait_packet()
    observation = game.king_fight_opponent_observation()
    assert observation["selection_required"] is False
    assert observation["locked_reason"] == "bait_response_pending"

    status = game.king_fight_status()
    assert "selected_recovery" not in status["bait_response"]["bait_recovery"]

    tell = game.king_fight_opponent_public_tell()
    assert tell["source"] == "bait_response_observation"

    monkeypatch.setattr(oa, "_GHOST_ORIGINAL_KING_FIGHT_OBSERVATION", lambda self: None)
    assert oa._ghost_layered_observation(game) is None
    monkeypatch.setattr(oa, "_GHOST_ORIGINAL_KING_FIGHT_STATUS", lambda self: None)
    assert oa._ghost_layered_status(game) is None


def test_resolve_wrapper_denials_and_stage_dispatch_v180(monkeypatch):
    no_fight = _game()
    no_fight.king_fight = None
    denied = oa._ghost_layered_resolve_king_fight_move(no_fight, "light")
    assert denied is None

    ended = _game()
    ended.ending = "done"
    denied = oa._ghost_layered_resolve_king_fight_move(ended, "light")
    assert denied is None

    blank = _game()
    denied = oa._ghost_layered_resolve_king_fight_move(blank, "")
    assert denied is None

    king_bait = _game()
    king_bait.king_fight["bait_response"] = _bait_packet()
    assert oa._ghost_layered_resolve_king_phase_move(
        king_bait,
        "pass",
    )["outcome"] == "king_bait_response"

    elite_bait = _game("elite_knight")
    elite_bait.king_fight["bait_response"] = _bait_packet(
        target="elite_knight"
    )
    assert oa._ghost_layered_resolve_elite_knight_move(
        elite_bait,
        "pass",
    )["outcome"] == "elite_knight_bait_response"

    parry_opening = _game()
    parry_opening.king_fight["parry_opening"] = {
        "allowed_moves": ("heavy", "light")
    }
    denied = oa._ghost_layered_resolve_king_fight_move(
        parry_opening,
        "feint_bait",
    )
    assert denied["outcome"] == "parry_opening_move_denied"

    forced = _game()
    forced.king_fight["forced_response"] = {
        "allowed_moves": ("light", "dodge")
    }
    response = oa._ghost_layered_resolve_king_fight_move(
        forced,
        "feint_bait",
    )
    assert isinstance(response, dict)

    monkeypatch.setattr(
        oa,
        "_GHOST_ORIGINAL_RESOLVE_KING_PHASE_MOVE",
        lambda self, move: {
            "exchange": {"opponent_reaction_plan": None}
        },
    )
    delegated = oa._ghost_layered_resolve_king_phase_move(
        _game(),
        "light",
    )
    assert "exchange" in delegated

    monkeypatch.setattr(
        oa,
        "_GHOST_ORIGINAL_RESOLVE_ELITE_KNIGHT_MOVE",
        lambda self, move: {
            "exchange": {"opponent_reaction_plan": None}
        },
    )
    delegated = oa._ghost_layered_resolve_elite_knight_move(
        _game("elite_knight"),
        "light",
    )
    assert "exchange" in delegated


def test_apply_opponent_intent_feint_prediction_audit_variants_v180():
    game = _game()
    observation = game.king_fight_opponent_observation()

    generic = game.apply_king_fight_opponent_intent(
        "crown_guard",
        proposed_reaction_plan="read_feint",
        proposed_feint_prediction="feint_heavy",
        selection_key=observation["selection_key"],
    )
    assert generic["reaction_plan_accepted"] is False

    cases = (
        ("read_feint_heavy", "feint_heavy", "accepted"),
        ("read_feint_heavy", "none", "missing_exact_feint_subtype"),
        ("read_feint_heavy", "feint_light", "mismatched_exact_feint_subtype"),
        ("hold_center", "none", "not_required"),
    )

    for index, (reaction, prediction, reason) in enumerate(cases, start=1):
        current = _game()
        current.king_fight["exchange_count"] = index
        current.king_fight["intent"] = "crown_guard"
        obs = current.king_fight_opponent_observation()
        audit = current.apply_king_fight_opponent_intent(
            "crown_guard",
            proposed_reaction_plan=reaction,
            proposed_combat_action="parry",
            proposed_feint_prediction=prediction,
            selection_key=obs["selection_key"],
        )
        assert audit["feint_prediction_reason"] == reason
        assert current.king_fight["llm_opponent_history"][-1] == audit



def test_parser_remaining_fence_and_embedded_shape_branches_v180(monkeypatch):
    legal = ("crown_guard",)

    empty_fence = oa.parse_king_fight_opponent_intent("```", legal)
    assert empty_fence["accepted"] is False

    unclosed_fence = oa.parse_king_fight_opponent_intent(
        "```json\n{\"intent\":\"crown_guard\"}",
        legal,
    )
    assert unclosed_fence["accepted"] is True

    real_loads = oa.json.loads
    calls = {"count": 0}

    def fake_loads(value):
        calls["count"] += 1
        if calls["count"] == 1:
            raise ValueError("force embedded path")
        return []

    monkeypatch.setattr(oa.json, "loads", fake_loads)
    parsed = oa.parse_king_fight_opponent_intent(
        "prefix {\"intent\":\"crown_guard\"} suffix",
        legal,
    )
    assert parsed["accepted"] is False
    monkeypatch.setattr(oa.json, "loads", real_loads)


def test_direct_bait_response_numeric_alias_and_feint_bait_collapse_v180():
    game = _game()
    game.king_fight["bait_response"] = _bait_packet()
    packet = oa._ghost_layered_resolve_bait_response(game, "3")
    assert packet["exchange"]["result"] == "bait_opening_passed"

    collapse = _game()
    collapse.king_fight["intent"] = "royal_lunge"
    collapse.king_fight["castle_timer"] = 1
    packet = oa._ghost_layered_resolve_feint_bait(collapse, "king")
    assert packet["outcome"] == "castle_collapse_legend"


def test_enrichment_remaining_short_circuits_v180():
    game = _game()

    already = {
        "exchange": {
            "predicted_feint_subtype": "feint_light",
            "opponent_reaction_plan": "read_feint_heavy",
            "opponent_reaction": {},
        }
    }
    result = oa._ghost_layered_enrich_reaction_packet(game, already)
    assert result["exchange"]["predicted_feint_subtype"] == "feint_light"

    no_prediction = {
        "exchange": {
            "predicted_feint_subtype": None,
            "opponent_reaction_plan": "hold_center",
            "opponent_reaction": {},
        }
    }
    result = oa._ghost_layered_enrich_reaction_packet(game, no_prediction)
    assert result["exchange"]["predicted_feint_subtype"] is None

    game.king_fight["last_exchange"] = "bad"
    result = oa._ghost_layered_enrich_reaction_packet(
        game,
        {
            "exchange": {
                "opponent_reaction": {
                    "bait_result": "none",
                }
            }
        },
    )
    assert result["exchange"]["bait_result"] == "none"

    game.king_fight = None
    result = oa._ghost_layered_enrich_reaction_packet(
        game,
        {
            "exchange": {
                "opponent_reaction": {
                    "bait_result": "none",
                }
            }
        },
    )
    assert result["exchange"]["bait_result"] == "none"


def test_phase_dispatch_remaining_paths_v180(monkeypatch):
    monkeypatch.setattr(
        oa,
        "_ghost_layered_resolve_feint_bait",
        lambda self, actor: {"actor": actor},
    )

    king = _game()
    king.king_fight["bait_response"] = None
    assert oa._ghost_layered_resolve_king_phase_move(
        king,
        "feint_bait",
    ) == {"actor": "king"}

    elite = _game("elite_knight")
    elite.king_fight["bait_response"] = None
    assert oa._ghost_layered_resolve_elite_knight_move(
        elite,
        "feint_bait",
    ) == {"actor": "elite_knight"}

    elite_pending = _game("elite_knight")
    elite_pending.king_fight["bait_response"] = _bait_packet(
        target="elite_knight"
    )
    monkeypatch.setattr(
        oa,
        "_ghost_layered_resolve_elite_knight_move",
        lambda self, move: {"stage": "elite", "move": move},
    )
    assert oa._ghost_layered_resolve_king_fight_move(
        elite_pending,
        "pass",
    )["stage"] == "elite"

    monkeypatch.setattr(
        oa,
        "_ghost_layered_resolve_king_phase_move",
        lambda self, move: {"stage": "king", "move": move},
    )
    king_direct = _game()
    king_direct.king_fight["bait_response"] = None
    assert oa._ghost_layered_resolve_king_fight_move(
        king_direct,
        "feint_bait",
    )["stage"] == "king"

    monkeypatch.setattr(
        oa,
        "_ghost_layered_resolve_elite_knight_move",
        lambda self, move: {"stage": "elite", "move": move},
    )
    elite_direct = _game("elite_knight")
    elite_direct.king_fight["bait_response"] = None
    assert oa._ghost_layered_resolve_king_fight_move(
        elite_direct,
        "feint_bait",
    )["stage"] == "elite"

    monkeypatch.setattr(
        oa,
        "_GHOST_ORIGINAL_RESOLVE_KING_FIGHT_MOVE",
        lambda self, move: {"delegated": move},
    )
    unknown = _game()
    unknown.king_fight["stage"] = "unknown"
    unknown.king_fight["bait_response"] = None
    assert oa._ghost_layered_resolve_king_fight_move(
        unknown,
        "feint_bait",
    ) == {"delegated": "feint_bait"}

    pending_unknown = _game()
    pending_unknown.king_fight["stage"] = "unknown"
    pending_unknown.king_fight["bait_response"] = _bait_packet()
    assert oa._ghost_layered_resolve_king_fight_move(
        pending_unknown,
        "pass",
    ) == {"delegated": "pass"}


def test_apply_feint_audit_handles_missing_fight_and_history_v180(monkeypatch):
    audit = {
        "proposed_reaction_plan": "read_feint_heavy",
        "proposed_intent": "crown_guard",
    }
    monkeypatch.setattr(
        oa,
        "_GHOST_ORIGINAL_APPLY_OPPONENT_INTENT",
        lambda *args, **kwargs: deepcopy(audit),
    )

    class Fake:
        king_fight = None

    result = oa._ghost_layered_apply_opponent_intent(
        Fake(),
        "crown_guard",
        selection_key="x",
        proposed_reaction_plan="read_feint_heavy",
        proposed_feint_prediction="feint_heavy",
    )
    assert result["feint_prediction_reason"] == "accepted"

    fake = Fake()
    fake.king_fight = {"llm_opponent_history": None}
    result = oa._ghost_layered_apply_opponent_intent(
        fake,
        "crown_guard",
        selection_key="x",
        proposed_reaction_plan="read_feint_heavy",
        proposed_feint_prediction="feint_heavy",
    )
    assert fake.king_fight["llm_opponent_audit"] == result

    fake.king_fight = {"llm_opponent_history": []}
    result = oa._ghost_layered_apply_opponent_intent(
        fake,
        "crown_guard",
        selection_key="x",
        proposed_reaction_plan="read_feint_heavy",
        proposed_feint_prediction="feint_heavy",
    )
    assert fake.king_fight["llm_opponent_history"] == []
