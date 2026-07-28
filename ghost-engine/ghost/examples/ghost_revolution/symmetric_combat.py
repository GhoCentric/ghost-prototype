"""Deterministic symmetric combat actions for the LLM opponent.

The strategist locks an actual combat action before the player moves.
Ghost resolves the two physical actions with a fixed matrix. Prediction is
separate evidence: a wrong prediction never deletes the already-locked action.
"""

from __future__ import annotations

from copy import deepcopy

from .config import KING_FIGHT_PLAYER_DAMAGE


SYMMETRIC_COMBAT_ACTIONS = (
    "heavy",
    "light",
    "feint_heavy",
    "feint_light",
    "feint_bait",
    "parry",
    "deflect",
    "dodge",
)

_ATTACK_ACTIONS = {
    "heavy",
    "light",
    "feint_heavy",
    "feint_light",
}
_DEFENSE_ACTIONS = {"parry", "deflect", "dodge"}
_HEAVY_LINES = {"heavy", "feint_heavy"}
_LIGHT_LINES = {"light", "feint_light"}

_ORIGINAL_APPLY = None
_ORIGINAL_OBSERVATION = None
_ORIGINAL_RESOLVE_KING_PHASE = None
_ORIGINAL_RESOLVE_ELITE = None
_ORIGINAL_RESOLVE_FIGHT = None


def _normalize(value):
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    return normalized or None


def _selection_key(fight):
    return f"{fight.get('stage', '')}:{int(fight.get('exchange_count', 0))}"


def _pending_action(self):
    fight = getattr(self, "king_fight", None)
    if not isinstance(fight, dict):
        return None
    if fight.get("llm_opponent_combat_action_selection_key") != _selection_key(fight):
        return None
    action = fight.get("llm_opponent_combat_action")
    return action if action in SYMMETRIC_COMBAT_ACTIONS else None


def _consume_action(self):
    fight = self.king_fight
    current_key = _selection_key(fight)
    stored_key = fight.pop("llm_opponent_combat_action_selection_key", None)
    action = fight.pop("llm_opponent_combat_action", None)
    if stored_key != current_key or action not in SYMMETRIC_COMBAT_ACTIONS:
        return None
    return action


def _prediction_packet(audit, player_move):
    reaction_plan = None
    feint_prediction = None
    if isinstance(audit, dict):
        reaction_plan = _normalize(
            audit.get("selected_reaction_plan")
            or audit.get("proposed_reaction_plan")
        )
        feint_prediction = _normalize(
            audit.get("selected_feint_prediction")
            or audit.get("proposed_feint_prediction")
        )

    if feint_prediction == "none":
        feint_prediction = None
    if feint_prediction not in {
        "feint_heavy", "feint_light", "feint_bait"
    }:
        feint_prediction = None

    legacy_prediction = {
        "read_feint_heavy": "feint_heavy",
        "read_feint_light": "feint_light",
        "read_feint_bait": "feint_bait",
        "parry_heavy": "heavy",
        "deflect_light": "light",
        "dodge_heavy": "heavy",
        "break_parry": "parry",
        "beat_deflect": "deflect",
        "track_dodge": "dodge",
    }.get(reaction_plan)

    prediction = feint_prediction or legacy_prediction
    predictive = prediction is not None
    matched = player_move == prediction if predictive else None
    return {
        "prediction": prediction,
        "feint_prediction": (
            prediction
            if prediction in {"feint_heavy", "feint_light", "feint_bait"}
            else None
        ),
        "predictive": predictive,
        "matched": matched,
        "missed": (not matched) if predictive else None,
    }


def _enemy_damage_for_action(enemy_actor, action):
    if enemy_actor == "elite_knight":
        return 4 if action in {"heavy", "feint_heavy"} else 3
    return 3 if action in {"heavy", "feint_heavy"} else 2


def _player_damage_for_move(move):
    if move == "deflect":
        return int(KING_FIGHT_PLAYER_DAMAGE["normal"]["deflect"])
    return int(KING_FIGHT_PLAYER_DAMAGE["normal"].get(move, 0))


def _actor_name(enemy_actor):
    return "The King's Champion" if enemy_actor == "elite_knight" else "The king"


def _defense_covers(defense, attack):
    return (
        defense == "dodge"
        or (defense == "parry" and attack in _HEAVY_LINES)
        or (defense == "deflect" and attack in _LIGHT_LINES)
    )


def _attack_priority(action):
    # Faster lines reach slower commitments first. Within one speed band,
    # the feinted version beats the direct version because it changes timing.
    return {
        "heavy": 1,
        "feint_heavy": 2,
        "light": 3,
        "feint_light": 4,
    }[action]


def _resolve_pair(
    enemy_actor,
    player_move,
    enemy_action,
    prediction,
    initiative_state,
):
    actor = _actor_name(enemy_actor)
    result = {
        "result": "symmetric_standoff",
        "enemy_damage": 0,
        "player_damage": 0,
        "initiative_event": "preserve",
        "message": "Both fighters hold the line and the exchange resets.",
        "player_parry_opening": False,
        "enemy_forced_response": False,
        "bait_setup": False,
        "action_effective": False,
    }

    # Pure bait is resolved first. Prediction controls whether the opponent
    # knowingly attacks the recovery. A wrong read never deletes the physical
    # action that was locked before the player chose.
    if player_move == "feint_bait":
        if prediction == "feint_bait":
            if enemy_action in {"light", "heavy"}:
                result.update(
                    result="enemy_punishes_bait",
                    player_damage=_enemy_damage_for_action(
                        enemy_actor, enemy_action
                    ),
                    initiative_event="enemy_hit",
                    message=(
                        f"{actor} expected the pure bait and sends a committed "
                        f"{enemy_action} attack through the recovery window before "
                        "you can rebuild your line."
                    ),
                    action_effective=True,
                )
            else:
                result.update(
                    result="enemy_reads_bait",
                    initiative_event="bait_read_denied",
                    message=(
                        f"{actor} expected the pure bait and refuses to spend the "
                        f"locked {enemy_action} action on the false opening. "
                        "No blade lands."
                    ),
                    action_effective=True,
                )
            return result

        if enemy_action == "feint_bait":
            result.update(
                result="double_bait_standoff",
                initiative_event="preserve",
                message=(
                    "Both fighters offer false openings and neither commits. "
                    "The distance resets without damage."
                ),
            )
            return result

        result.update(
            result="bait_setup",
            initiative_event="player_bait",
            message=(
                f"Your pure bait draws {actor.lower()}'s locked {enemy_action} "
                "action toward a threat that never arrives. His recovery is "
                "exposed for one hidden beat."
            ),
            bait_setup=True,
            action_effective=False,
        )
        return result

    # The opponent's pure bait is a real action too. It deals no automatic
    # damage. A committed response gives the opponent tempo; refusing it does
    # not. The LLM can use the resulting initiative on the next exchange.
    if enemy_action == "feint_bait":
        if player_move in {"feint_bait", "dodge"}:
            result.update(
                result="opponent_bait_refused",
                initiative_event="preserve",
                message=(
                    f"{actor} offers a pure bait, but you refuse the false line. "
                    "Neither fighter gains a wound."
                ),
            )
        else:
            result.update(
                result="opponent_bait_succeeds",
                initiative_event="enemy_counter",
                message=(
                    f"{actor} gives you a false opening and your {player_move} "
                    "commits into empty space. No automatic damage follows, but "
                    "he takes the initiative."
                ),
                action_effective=True,
            )
        return result

    # Both sides use the same defense coverage. Parry answers committed heavy
    # lines, deflect answers committed light lines, and dodge leaves any attack
    # cutting empty air. A mismatched defense is beaten by the attack.
    if enemy_action in _DEFENSE_ACTIONS:
        if player_move not in _ATTACK_ACTIONS:
            result.update(
                result="mutual_defense",
                initiative_event="preserve",
                message=(
                    f"You choose {player_move} while {actor.lower()} locks "
                    f"{enemy_action}. Neither fighter commits an attack."
                ),
            )
            return result

        if _defense_covers(enemy_action, player_move):
            result.update(
                result=f"enemy_{enemy_action}",
                initiative_event="enemy_counter",
                message=(
                    f"{actor} keeps the locked {enemy_action} action through the "
                    f"deception and answers the committed {player_move} line. "
                    "Your attack is denied without automatic damage."
                ),
                enemy_forced_response=(enemy_action in {"parry", "deflect"}),
                action_effective=True,
            )
            return result

        result.update(
            result="player_attack_beats_defense",
            enemy_damage=_player_damage_for_move(player_move),
            initiative_event="player_attack_hit",
            message=(
                f"{actor} committed to {enemy_action}, but your {player_move} "
                "attacks a different timing and lands through the mismatch."
            ),
        )
        return result

    if player_move in _DEFENSE_ACTIONS:
        if _defense_covers(player_move, enemy_action):
            if player_move == "dodge":
                result.update(
                    result="player_dodge",
                    initiative_event="player_dodge",
                    message=(
                        f"You leave the line before {actor.lower()}'s locked "
                        f"{enemy_action} action arrives. No blade lands."
                    ),
                )
            elif player_move == "parry":
                result.update(
                    result="player_parry",
                    initiative_event="player_parry",
                    message=(
                        f"You wait for {actor.lower()}'s committed {enemy_action} "
                        "line and turn the real attack aside, opening his guard "
                        "for your next strike."
                    ),
                    player_parry_opening=True,
                )
            else:
                result.update(
                    result="player_deflect",
                    enemy_damage=int(
                        KING_FIGHT_PLAYER_DAMAGE["normal"]["deflect"]
                    ),
                    initiative_event="player_deflect",
                    message=(
                        f"You meet {actor.lower()}'s committed {enemy_action} "
                        "line early and deflect it into a narrow countercut."
                    ),
                )
            return result

        result.update(
            result="enemy_attack_beats_defense",
            player_damage=_enemy_damage_for_action(enemy_actor, enemy_action),
            initiative_event="enemy_hit",
            message=(
                f"Your {player_move} commits to the wrong timing. "
                f"{actor}'s locked {enemy_action} action lands through the gap."
            ),
            action_effective=True,
        )
        return result

    # Attack versus attack uses one shared priority rule. Fast attacks reach
    # slow commitments first; a feinted action beats the direct action in the
    # same speed band. Identical commitments use existing Ghost initiative as
    # the deterministic tie-breaker, never a random draw.
    enemy_priority = _attack_priority(enemy_action)
    player_priority = _attack_priority(player_move)

    if enemy_priority > player_priority:
        result.update(
            result="enemy_action_interrupts",
            player_damage=_enemy_damage_for_action(enemy_actor, enemy_action),
            initiative_event="enemy_hit",
            message=(
                f"{actor}'s locked {enemy_action} action reaches the recovery "
                f"inside your {player_move} before your line can settle."
            ),
            action_effective=True,
        )
        return result

    if player_priority > enemy_priority:
        result.update(
            result="player_action_interrupts",
            enemy_damage=_player_damage_for_move(player_move),
            initiative_event="player_attack_hit",
            message=(
                f"Your {player_move} reaches the recovery inside "
                f"{actor.lower()}'s locked {enemy_action} action and lands first."
            ),
        )
        return result

    if initiative_state == "enemy_advantage":
        result.update(
            result="enemy_initiative_breaks_clash",
            player_damage=_enemy_damage_for_action(enemy_actor, enemy_action),
            initiative_event="enemy_hit",
            message=(
                f"Both fighters commit {player_move}, but {actor.lower()} owns "
                "the tempo and reaches the line first."
            ),
            action_effective=True,
        )
        return result

    if initiative_state == "player_advantage":
        result.update(
            result="player_initiative_breaks_clash",
            enemy_damage=_player_damage_for_move(player_move),
            initiative_event="player_attack_hit",
            message=(
                f"Both fighters commit {player_move}, but your existing tempo "
                "carries your blade through first."
            ),
        )
        return result

    result.update(
        result="attack_clash",
        initiative_event="preserve",
        message=(
            f"Your {player_move} and {actor.lower()}'s locked {enemy_action} "
            "arrive on the same neutral beat. Steel meets steel and neither "
            "wound lands."
        ),
    )
    return result


def _build_bait_response(self, *, enemy_actor, intent, reaction_plan, action,
                         prediction_packet, audit, next_intent):
    # Reuse the deterministic utility selector from the layered-feint patch.
    from . import opponent_ai as opponent_module

    selection = opponent_module._ghost_layered_select_bait_recovery(
        self, enemy_actor
    )
    patterns = opponent_module._ghost_layered_patterns(self)
    patterns["last_bait_recoveries"].append(selection["selected_recovery"])
    patterns["last_bait_recoveries"] = patterns["last_bait_recoveries"][-6:]

    return {
        "kind": "bait_response",
        "reason": "feint_bait_success",
        "source_move": "feint_bait",
        "target": enemy_actor,
        "intent": intent,
        "allowed_moves": ("light", "parry", "pass"),
        "next_intent": next_intent,
        "bait_recovery": deepcopy(selection),
        "random_used": False,
        "source_commitment": {
            "stage": self.king_fight.get("stage"),
            "intent": intent,
            "intent_label": opponent_module._ghost_layered_intent_labels(intent),
            "reaction_plan": reaction_plan,
            "reaction_plan_label": self._king_fight_reaction_plan_labels().get(
                reaction_plan, reaction_plan
            ),
            "opponent_combat_action": action,
            "predicted_feint_subtype": prediction_packet["feint_prediction"],
            "reaction_plan_predictive": prediction_packet["predictive"],
            "reaction_plan_matched": prediction_packet["matched"],
            "reaction_plan_triggered": False,
            "reaction_plan_missed": prediction_packet["missed"],
            "reaction_miss_exposed_enemy": False,
            "reaction_miss_bonus": 0,
            "resolution_source": "symmetric_bait_setup",
            "intent_reason": audit.get("intent_reason") if isinstance(audit, dict) else None,
            "reaction_reason": audit.get("reaction_reason") if isinstance(audit, dict) else None,
        },
    }


def _player_parry_opening(enemy_actor, intent, commitment):
    return {
        "source": "player_parry",
        "intent": intent,
        "target": enemy_actor,
        "damage_bonus": 1,
        "guaranteed_next_attack": True,
        "allowed_moves": ("heavy", "light"),
        "source_commitment": deepcopy(commitment),
        "message": (
            "Your parry has opened the opponent. Your next heavy attack will "
            "deal 5 damage, or your next light attack will deal 3."
        ),
    }


def _resolve_symmetric_exchange(self, move, enemy_actor):
    fight = self.king_fight
    player_move = _normalize(move)
    action = _consume_action(self)
    if action is None:
        original = (
            _ORIGINAL_RESOLVE_ELITE if enemy_actor == "elite_knight"
            else _ORIGINAL_RESOLVE_KING_PHASE
        )
        return original(self, move)

    intent = fight["intent"]
    reaction_plan = self._consume_king_fight_opponent_reaction_plan(intent)
    audit = fight.get("llm_opponent_audit")
    prediction = _prediction_packet(audit, player_move)
    initiative_before = self._ensure_king_fight_initiative()
    resolved = _resolve_pair(
        enemy_actor,
        player_move,
        action,
        prediction["prediction"],
        initiative_before["state"],
    )

    if enemy_actor == "elite_knight":
        health_key = "elite_knight_health"
        damage_field = "elite_knight_damage"
        outcome = "elite_knight_exchange"
    else:
        health_key = "king_health"
        damage_field = "king_damage"
        outcome = "king_exchange"

    raw_enemy_damage = int(resolved["enemy_damage"])
    enemy_damage = (
        self._king_damage(raw_enemy_damage)
        if enemy_actor == "king" and raw_enemy_damage > 0
        else raw_enemy_damage
    )
    player_damage = int(resolved["player_damage"])
    king_heal = 0

    fight[health_key] = max(0, int(fight[health_key]) - enemy_damage)
    fight["player_health"] = max(
        0, int(fight["player_health"]) - player_damage
    )

    if enemy_actor == "king" and player_damage > 0:
        fight["king_has_hit_player"] = True
        fight["clean_king_victory_possible"] = False
    elif enemy_actor == "elite_knight" and player_damage > 0:
        fight["failed_knight_reads"] += 1
        fight["king_morale_ticks"] += 1
        king_heal = 1
        fight["king_health"] = min(
            fight["king_max_health"], fight["king_health"] + king_heal
        )

    fight["exchange_count"] += 1
    self._record_king_fight_player_move(player_move)

    next_intent = (
        self._elite_knight_intent(fight["exchange_count"])
        if enemy_actor == "elite_knight"
        else self._king_intent(fight["exchange_count"])
    )

    commitment = {
        "stage": fight["stage"],
        "intent": intent,
        "intent_label": (
            audit.get("selected_intent_label")
            if isinstance(audit, dict)
            else intent
        ),
        "reaction_plan": reaction_plan,
        "reaction_plan_label": self._king_fight_reaction_plan_labels().get(
            reaction_plan, reaction_plan
        ),
        "opponent_combat_action": action,
        "predicted_feint_subtype": prediction["feint_prediction"],
        "reaction_plan_predictive": prediction["predictive"],
        "reaction_plan_matched": prediction["matched"],
        "reaction_plan_triggered": prediction["matched"] is True,
        "reaction_plan_missed": prediction["missed"],
        "reaction_miss_exposed_enemy": (
            prediction["missed"] is True and enemy_damage > 0
        ),
        "reaction_miss_bonus": 0,
        "resolution_source": "symmetric_action_matrix",
        "intent_reason": audit.get("intent_reason") if isinstance(audit, dict) else None,
        "reaction_reason": audit.get("reaction_reason") if isinstance(audit, dict) else None,
    }

    if resolved["player_parry_opening"]:
        fight["parry_opening"] = _player_parry_opening(
            enemy_actor, intent, commitment
        )

    if resolved["bait_setup"]:
        fight["bait_response"] = _build_bait_response(
            self,
            enemy_actor=enemy_actor,
            intent=intent,
            reaction_plan=reaction_plan,
            action=action,
            prediction_packet=prediction,
            audit=audit,
            next_intent=next_intent,
        )

    if resolved["enemy_forced_response"] and enemy_actor == "king":
        defense = {
            "type": "king_symmetric_" + action,
            "triggering_move": player_move,
            "message": resolved["message"],
        }
        recovery_read = (
            deepcopy(audit.get("forced_response_read"))
            if isinstance(audit, dict)
            else None
        )
        forced = self._build_king_forced_response(
            defense, next_intent, recovery_read=recovery_read
        )
        forced["source_commitment"] = deepcopy(commitment)
        fight["forced_response"] = forced

    initiative_after = self._advance_king_fight_initiative(
        resolved["initiative_event"]
    )

    exchange = {
        "stage": fight["stage"],
        "intent": intent,
        "move": player_move,
        "expected": prediction["prediction"],
        "valid_responses": list(SYMMETRIC_COMBAT_ACTIONS),
        "result": resolved["result"],
        "player_damage": player_damage,
        "king_heal": king_heal,
        damage_field: enemy_damage,
        "opponent_combat_action": action,
        "opponent_action_effective": resolved["action_effective"],
        "prediction_action_separated": True,
        "opponent_reaction_plan": reaction_plan,
        "opponent_reaction_plan_label": self._king_fight_reaction_plan_labels().get(
            reaction_plan, reaction_plan
        ),
        "predicted_feint_subtype": prediction["feint_prediction"],
        "reaction_plan_predictive": prediction["predictive"],
        "reaction_plan_matched": prediction["matched"],
        "reaction_plan_triggered": prediction["matched"] is True,
        "reaction_plan_missed": prediction["missed"],
        "reaction_miss_exposed_enemy": (
            prediction["missed"] is True and enemy_damage > 0
        ),
        "reaction_miss_bonus": 0,
        "resolution_source": "symmetric_action_matrix",
        "opponent_control_source": "llm_combat_action_ghost_matrix",
        "opponent_intent_reason": (
            audit.get("intent_reason") if isinstance(audit, dict) else None
        ),
        "opponent_reaction_reason": (
            audit.get("reaction_reason") if isinstance(audit, dict) else None
        ),
        "opponent_proposal_reason": (
            audit.get("intent_reason") if isinstance(audit, dict) else None
        ),
        "initiative_before": initiative_before,
        "initiative_after": initiative_after,
        "initiative_event": resolved["initiative_event"],
        "parry_opening": deepcopy(fight.get("parry_opening")),
        "bait_result": resolved["result"] if "bait" in resolved["result"] else None,
        "bait_hidden_recovery": (
            fight.get("bait_response", {}).get("bait_recovery", {}).get(
                "selected_recovery"
            )
            if isinstance(fight.get("bait_response"), dict)
            else None
        ),
        "message": resolved["message"],
    }
    if enemy_actor == "king":
        exchange.setdefault("elite_knight_damage", 0)
    else:
        exchange.setdefault("king_damage", 0)
    fight["last_exchange"] = exchange

    if fight["player_health"] <= 0:
        return self._finish_player_death(killer=enemy_actor)

    if enemy_actor == "king":
        if (
            fight["stage"] == "king_phase_one"
            and fight["king_health"] <= fight["king_half_health"]
        ):
            collapse = self._advance_castle_timer()
            if collapse is not None:
                return collapse
            packet = self._transition_to_elite_knight()
            narrative = (
                "For one breath the king looks almost mortal. He staggers back "
                "into the smoke, then raises two fingers. The King's Champion "
                "steps between you and the throne."
            )
            if isinstance(packet, dict):
                packet["narrative"] = narrative
                packet["note"] = narrative
                next_tell = packet.get("tell", "")
                packet["tell"] = narrative + ("\n\n" + next_tell if next_tell else "")
                self.last_action_note = packet["tell"]
            return packet

        if fight["stage"] == "king_phase_two" and fight["king_health"] <= 0:
            if fight["clean_king_victory_possible"]:
                return self._enter_king_fate_choice()
            return self._finish_uncertain_king_victory()

        fight["intent"] = next_intent
        self.last_action_note = resolved["message"] + " " + self._king_intent_tell(next_intent)
        collapse = self._advance_castle_timer()
        if collapse is not None:
            return collapse
        return {
            "outcome": outcome,
            "stage": fight["stage"],
            "exchange": deepcopy(exchange),
            "player_health": fight["player_health"],
            "king_health": fight["king_health"],
            "castle_timer": fight["castle_timer"],
            "clean_king_victory_possible": fight["clean_king_victory_possible"],
            "tell": self._king_intent_tell(next_intent),
            "parry_opening": deepcopy(fight.get("parry_opening")),
            "forced_response": self._public_forced_response(
                fight.get("forced_response")
            ),
            "bait_response": self._public_bait_response(
                fight.get("bait_response")
            ),
            "initiative": deepcopy(fight.get("initiative")),
        }

    if fight["elite_knight_health"] <= 0:
        fight["stage"] = "king_phase_two"
        fight["parry_opening"] = None
        fight["forced_response"] = None
        fight["bait_response"] = None
        fight["exchange_count"] = 0
        fight["intent"] = self._king_intent(0)
        fight["initiative"] = self._social.advance_combat_initiative(
            previous_state=initiative_after["state"], event="stage_transition"
        )
        self.last_action_note = (
            "The King's Champion falls into the burning stone. The king steps "
            "over him for the final phase."
        )
        collapse = self._advance_castle_timer()
        if collapse is not None:
            return collapse
        return {
            "outcome": "elite_knight_defeated",
            "stage": "king_phase_two",
            "king_health": fight["king_health"],
            "king_morale_ticks": fight["king_morale_ticks"],
            "failed_knight_reads": fight["failed_knight_reads"],
            "player_health": fight["player_health"],
            "castle_timer": fight["castle_timer"],
            "tell": self._king_intent_tell(fight["intent"]),
            "initiative": deepcopy(fight["initiative"]),
        }

    fight["intent"] = next_intent
    self.last_action_note = resolved["message"] + " " + self._elite_knight_tell(next_intent)
    collapse = self._advance_castle_timer()
    if collapse is not None:
        return collapse
    return {
        "outcome": outcome,
        "stage": "elite_knight",
        "exchange": deepcopy(exchange),
        "player_health": fight["player_health"],
        "elite_knight_health": fight["elite_knight_health"],
        "king_health": fight["king_health"],
        "king_morale_ticks": fight["king_morale_ticks"],
        "castle_timer": fight["castle_timer"],
        "tell": self._elite_knight_tell(next_intent),
        "parry_opening": deepcopy(fight.get("parry_opening")),
        "bait_response": self._public_bait_response(fight.get("bait_response")),
        "initiative": deepcopy(fight.get("initiative")),
    }


def _fallback_combat_action(audit):
    if not isinstance(audit, dict):
        return "dodge"

    reaction = _normalize(
        audit.get("selected_reaction_plan")
        or audit.get("fallback_reaction_plan")
    )
    reaction_actions = {
        "read_feint_heavy": "parry",
        "read_feint_light": "deflect",
        "read_feint_bait": "light",
        "parry_heavy": "parry",
        "deflect_light": "deflect",
        "dodge_heavy": "dodge",
        "break_parry": "feint_light",
        "beat_deflect": "heavy",
        "track_dodge": "light",
        "hold_center": "parry",
        "genuine_opening": "heavy",
        "commit_attack": "heavy",
    }
    if reaction in reaction_actions:
        return reaction_actions[reaction]

    intent = _normalize(
        audit.get("selected_intent")
        or audit.get("fallback_intent")
    )
    return {
        "royal_lunge": "heavy",
        "crown_guard": "parry",
        "overextended_recovery": "dodge",
        "shield_wall": "parry",
        "champion_lunge": "heavy",
        "wide_execution": "heavy",
        "open_recovery": "dodge",
    }.get(intent, "dodge")


def _apply_with_combat_action(
    self,
    proposed_intent,
    *,
    selection_key,
    proposed_reaction_plan=None,
    proposed_forced_response_read=None,
    proposed_feint_prediction=None,
    proposed_combat_action=None,
    provider_called=False,
    parser_reason=None,
    reaction_parser_reason=None,
    proposal_reason=None,
    intent_explanation=None,
    reaction_explanation=None,
):
    audit = _ORIGINAL_APPLY(
        self,
        proposed_intent,
        selection_key=selection_key,
        proposed_reaction_plan=proposed_reaction_plan,
        proposed_forced_response_read=proposed_forced_response_read,
        proposed_feint_prediction=proposed_feint_prediction,
        provider_called=provider_called,
        parser_reason=parser_reason,
        reaction_parser_reason=reaction_parser_reason,
        proposal_reason=proposal_reason,
        intent_explanation=intent_explanation,
        reaction_explanation=reaction_explanation,
    )

    if not isinstance(audit, dict):
        return audit

    proposed_action = _normalize(proposed_combat_action)
    accepted = proposed_action in SYMMETRIC_COMBAT_ACTIONS
    fallback_used = bool(
        provider_called and not accepted and parser_reason is not None
    )
    action = (
        proposed_action
        if accepted
        else _fallback_combat_action(audit)
        if fallback_used
        else None
    )
    prediction = _normalize(proposed_feint_prediction)
    if prediction == "none" or prediction not in {
        "feint_heavy", "feint_light", "feint_bait"
    }:
        prediction = None

    audit["proposed_combat_action"] = proposed_action
    audit["selected_combat_action"] = action
    audit["combat_action_accepted"] = accepted
    audit["combat_action_fallback_used"] = fallback_used
    audit["combat_action_reason"] = (
        "accepted"
        if accepted
        else "ghost_semantic_fallback_missing_combat_action"
        if fallback_used and proposed_action is None
        else "ghost_semantic_fallback_illegal_combat_action"
        if fallback_used
        else "missing_combat_action"
        if proposed_action is None
        else "illegal_combat_action"
    )
    audit["legal_combat_actions"] = list(SYMMETRIC_COMBAT_ACTIONS)
    audit["selected_feint_prediction"] = prediction
    audit["prediction_action_separated"] = True

    fight = getattr(self, "king_fight", None)
    if isinstance(fight, dict):
        current_key = _selection_key(fight)
        if action in SYMMETRIC_COMBAT_ACTIONS and selection_key == current_key:
            fight["llm_opponent_combat_action"] = action
            fight["llm_opponent_combat_action_selection_key"] = current_key
        fight["llm_opponent_audit"] = deepcopy(audit)
        history = fight.get("llm_opponent_history")
        if isinstance(history, list) and history:
            history[-1] = deepcopy(audit)

    return deepcopy(audit)


def _observation_with_combat_actions(self):
    observation = _ORIGINAL_OBSERVATION(self)
    if not isinstance(observation, dict):
        return observation
    observation["legal_combat_actions"] = list(SYMMETRIC_COMBAT_ACTIONS)
    observation["combat_action_labels"] = {
        "heavy": "Heavy Attack",
        "light": "Light Attack",
        "feint_heavy": "Feint Into Heavy",
        "feint_light": "Feint Into Light",
        "feint_bait": "Pure Bait",
        "parry": "Parry",
        "deflect": "Deflect",
        "dodge": "Dodge",
    }
    previous = observation.get("previous_exchange_evidence")
    fight = getattr(self, "king_fight", None)
    last_exchange = fight.get("last_exchange") if isinstance(fight, dict) else None
    if isinstance(previous, dict) and isinstance(last_exchange, dict):
        for key in (
            "opponent_combat_action",
            "opponent_action_effective",
            "prediction_action_separated",
        ):
            if key in last_exchange:
                previous[key] = deepcopy(last_exchange.get(key))
    return observation


def _resolve_king_with_action(self, move):
    fight = self.king_fight
    if (
        _pending_action(self) is not None
        and not isinstance(fight.get("forced_response"), dict)
        and not isinstance(fight.get("parry_opening"), dict)
        and not isinstance(fight.get("bait_response"), dict)
        and _normalize(move) in SYMMETRIC_COMBAT_ACTIONS
    ):
        return _resolve_symmetric_exchange(self, move, "king")
    return _ORIGINAL_RESOLVE_KING_PHASE(self, move)


def _resolve_elite_with_action(self, move):
    fight = self.king_fight
    if (
        _pending_action(self) is not None
        and not isinstance(fight.get("parry_opening"), dict)
        and not isinstance(fight.get("bait_response"), dict)
        and _normalize(move) in SYMMETRIC_COMBAT_ACTIONS
    ):
        return _resolve_symmetric_exchange(self, move, "elite_knight")
    return _ORIGINAL_RESOLVE_ELITE(self, move)



def _resolve_fight_with_action(self, move):
    fight = getattr(self, "king_fight", None)
    normalized = _normalize(move)
    if (
        isinstance(fight, dict)
        and _pending_action(self) is not None
        and not isinstance(fight.get("forced_response"), dict)
        and not isinstance(fight.get("parry_opening"), dict)
        and not isinstance(fight.get("bait_response"), dict)
        and normalized in SYMMETRIC_COMBAT_ACTIONS
    ):
        stage = fight.get("stage")
        if stage in {"king_phase_one", "king_phase_two"}:
            return _resolve_symmetric_exchange(self, normalized, "king")
        if stage == "elite_knight":
            return _resolve_symmetric_exchange(self, normalized, "elite_knight")
    return _ORIGINAL_RESOLVE_FIGHT(self, move)

def install_symmetric_combat(GhostRevolutionRun):
    global _ORIGINAL_APPLY, _ORIGINAL_OBSERVATION
    global _ORIGINAL_RESOLVE_KING_PHASE, _ORIGINAL_RESOLVE_ELITE
    global _ORIGINAL_RESOLVE_FIGHT

    _ORIGINAL_APPLY = GhostRevolutionRun.apply_king_fight_opponent_intent
    _ORIGINAL_OBSERVATION = GhostRevolutionRun.king_fight_opponent_observation
    _ORIGINAL_RESOLVE_KING_PHASE = GhostRevolutionRun._resolve_king_phase_move
    _ORIGINAL_RESOLVE_ELITE = GhostRevolutionRun._resolve_elite_knight_move
    _ORIGINAL_RESOLVE_FIGHT = GhostRevolutionRun.resolve_king_fight_move

    GhostRevolutionRun.apply_king_fight_opponent_intent = _apply_with_combat_action
    GhostRevolutionRun.king_fight_opponent_observation = _observation_with_combat_actions
    GhostRevolutionRun._resolve_king_phase_move = _resolve_king_with_action
    GhostRevolutionRun._resolve_elite_knight_move = _resolve_elite_with_action
    GhostRevolutionRun.resolve_king_fight_move = _resolve_fight_with_action
