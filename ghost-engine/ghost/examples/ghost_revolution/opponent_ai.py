"""
Isolated LLM opponent-policy bridge for Ghost Revolution.

The model proposes one legal combat intent.
Ghost validates and applies the proposal.
The model never resolves damage, health, death, transitions,
timers, victory, or any other authoritative state.
"""

from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any, Callable, Mapping

from .config import KING_FIGHT_PLAYER_DAMAGE

from ghost.examples.ghost_revolution.llm_bridge import (
    LLMBridgeConfig,
    estimate_llm_cost,
    measured_llm_cost,
    normalize_client_result,
)


OPPONENT_OUTPUT_TOKENS = 768
OPPONENT_HARD_OUTPUT_TOKENS = 1024

OPPONENT_STRUCTURED_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string"},
        "reaction_plan": {"type": "string"},
        "combat_action": {
            "type": "string",
            "enum": [
                "heavy",
                "light",
                "feint_heavy",
                "feint_light",
                "feint_bait",
                "parry",
                "deflect",
                "dodge",
            ],
        },
        "feint_prediction": {
            "type": "string",
            "enum": [
                "feint_heavy",
                "feint_light",
                "feint_bait",
                "none",
            ],
        },
        "forced_response_read": {
            "type": "string",
            "enum": ["light", "dodge"],
        },
        "intent_reason": {"type": "string"},
        "reaction_reason": {"type": "string"},
    },
    "required": [
        "intent",
        "reaction_plan",
        "combat_action",
        "feint_prediction",
        "forced_response_read",
        "intent_reason",
        "reaction_reason",
    ],
    "additionalProperties": False,
}


def _normalize_intent(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    normalized = (
        value
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    return normalized or None


def _opponent_request_config(
    config: LLMBridgeConfig,
) -> LLMBridgeConfig:
    hard_limit = min(
        OPPONENT_HARD_OUTPUT_TOKENS,
        max(
            1,
            int(
                config.hard_max_output_tokens
            ),
        ),
    )

    output_limit = min(
        OPPONENT_OUTPUT_TOKENS,
        max(
            1,
            int(
                config.max_output_tokens
            ),
        ),
        hard_limit,
    )

    return LLMBridgeConfig(
        model=config.model,
        input_cost_per_million_tokens=(
            config
            .input_cost_per_million_tokens
        ),
        cached_input_cost_per_million_tokens=(
            config
            .cached_input_cost_per_million_tokens
        ),
        output_cost_per_million_tokens=(
            config
            .output_cost_per_million_tokens
        ),
        max_output_tokens=output_limit,
        hard_max_output_tokens=(
            hard_limit
        ),
        reasoning_effort=config.reasoning_effort,
        role=config.role,
        structured_output_name=(
            "ghost_fight_opponent_strategy"
        ),
        structured_output_schema=(
            OPPONENT_STRUCTURED_OUTPUT_SCHEMA
        ),
        prompt_cache_key=config.prompt_cache_key,
    )





def build_king_fight_opponent_intent_prompt(
    observation: Mapping[str, Any],
) -> str:
    safe = (
        observation
        if isinstance(
            observation,
            Mapping,
        )
        else {}
    )

    legal_intents = [
        str(intent)
        for intent in safe.get(
            "legal_intents",
            (),
        )
    ]

    labels = safe.get(
        "intent_labels",
        {},
    )

    options = safe.get(
        "intent_options",
        {},
    )

    legal_reactions = safe.get(
        "legal_reaction_plans_by_intent",
        {},
    )

    reaction_labels = safe.get(
        "reaction_plan_labels",
        {},
    )

    combat_objective = safe.get(
        "combat_objective",
        {},
    )

    if not isinstance(labels, Mapping):
        labels = {}

    if not isinstance(options, Mapping):
        options = {}

    if not isinstance(
        legal_reactions,
        Mapping,
    ):
        legal_reactions = {}

    if not isinstance(
        reaction_labels,
        Mapping,
    ):
        reaction_labels = {}

    if not isinstance(
        combat_objective,
        Mapping,
    ):
        combat_objective = {}

    public_observation = {
        "stage": safe.get("stage"),
        "enemy_actor": safe.get(
            "enemy_actor"
        ),
        "enemy_display_name": safe.get(
            "enemy_display_name"
        ),
        "enemy_personality": safe.get(
            "enemy_personality"
        ),
        "combat_objective": dict(
            combat_objective
        ),
        "combat_initiative": dict(
            safe.get("combat_initiative", {})
        ) if isinstance(
            safe.get("combat_initiative"),
            Mapping,
        ) else {},
        "legal_forced_response_reads": list(
            safe.get(
                "legal_forced_response_reads",
                ("light", "dodge"),
            )
        ),
        "legal_combat_actions": list(
            safe.get(
                "legal_combat_actions",
                (
                    "heavy",
                    "light",
                    "feint_heavy",
                    "feint_light",
                    "feint_bait",
                    "parry",
                    "deflect",
                    "dodge",
                ),
            )
        ),
        "legal_feint_predictions": list(
            safe.get(
                "legal_feint_predictions",
                (
                    "feint_heavy",
                    "feint_light",
                    "feint_bait",
                ),
            )
        ),
        "fallback_forced_response_read": (
            safe.get(
                "fallback_forced_response_read",
                "dodge",
            )
        ),
        "enemy_health_band": safe.get(
            "enemy_health_band"
        ),
        "player_health_band": safe.get(
            "player_health_band"
        ),
        "castle_timer_band": safe.get(
            "castle_timer_band"
        ),
        "king_morale_band": safe.get(
            "king_morale_band"
        ),
        "recent_player_moves": list(
            safe.get(
                "recent_player_moves",
                (),
            )
        ),
        "previous_exchange_evidence": (
            safe.get(
                "previous_exchange_evidence"
            )
        ),
        "recent_opponent_intents": list(
            safe.get(
                "recent_opponent_intents",
                (),
            )
        ),
        "same_intent_streak": safe.get(
            "same_intent_streak",
            0,
        ),
        "legal_intents": legal_intents,
        "intent_labels": {
            intent: labels.get(
                intent,
                intent,
            )
            for intent in legal_intents
        },
        "intent_options": {
            intent: options.get(intent)
            for intent in legal_intents
        },
        "legal_reaction_plans_by_intent": {
            intent: list(
                legal_reactions.get(
                    intent,
                    (),
                )
            )
            for intent in legal_intents
        },
        "reaction_plan_labels": {
            plan: reaction_labels.get(
                plan,
                plan,
            )
            for plans in legal_reactions.values()
            for plan in plans
        },
    }

    return (
        "SYSTEM: You are the enemy combat strategist "
        "inside a turn-based duel.\n"
        "SYSTEM: Ghost owns all authoritative state "
        "and consequences.\n"
        "SYSTEM: combat_objective is authoritative "
        "Ghost context, not optional flavor.\n"
        "SYSTEM: Pursue combat_objective.primary_goal "
        "across the current and future exchanges.\n"
        "SYSTEM: Unless Ghost resolves a terminal state, "
        "the target receives another action after this "
        "exchange.\n"
        "SYSTEM: Evaluate both the immediate exchange and "
        "the position left for the following exchange.\n"
        "SYSTEM: combat_initiative is authoritative Ghost "
        "tempo state. Maintain enemy_advantage, recover from "
        "player_advantage, and avoid giving away control without "
        "strategic benefit.\n"
        "SYSTEM: When combat_objective.tactical_state."
        "finishing_opportunity=true, prefer credible "
        "finishing pressure unless resolved evidence "
        "makes that line unsound.\n"
        "SYSTEM: Do not choose open_recovery or "
        "genuine_opening merely for variety, testing, "
        "experimentation, or information gathering.\n"
        "SYSTEM: genuine_opening is a real punishable "
        "opening. It is not bait and does not hide an "
        "automatic counter.\n"
        "SYSTEM: Information gathering is useful only "
        "when it improves future success probability "
        "under the combat objective.\n"
        "SYSTEM: Before the player chooses a move, "
        "commit to one intent, one hidden reaction_plan, "
        "one hidden combat_action, and one hidden "
        "forced_response_read.\n"
        "SYSTEM: combat_action is the opponent's real physical move "
        "for this exchange. Choose exactly one action from "
        "legal_combat_actions.\n"
        "SYSTEM: feint_prediction and combat_action are separate. "
        "The prediction states what you expect; combat_action states "
        "what your body actually does even when that prediction misses.\n"
        "SYSTEM: A light combat_action paired with feint_bait may punish "
        "pure-bait recovery and may interrupt a slower feint-heavy follow-up.\n"
        "SYSTEM: A parry combat_action may still catch a committed heavy "
        "line even when the exact feint subtype prediction is wrong.\n"
        "SYSTEM: forced_response_read must be exactly light "
        "or dodge. It predicts which restricted recovery the "
        "player will choose if your locked reaction creates an "
        "off-balance continuation.\n"
        "SYSTEM: The forced_response_read is locked now, remains "
        "hidden through the recovery menu, and is ignored if no "
        "forced response is created.\n"
        "SYSTEM: Choose exactly one value from "
        "LEGAL_INTENTS.\n"
        "SYSTEM: Choose reaction_plan only from "
        "legal_reaction_plans_by_intent[intent].\n"
        "SYSTEM: The intent and reaction plan are locked "
        "before the player's move and cannot change "
        "afterward.\n"
        "SYSTEM: Generic read_feint is illegal; a feint read must name the exact subtype.\n"
        "SYSTEM: read_feint_heavy predicts feint_heavy: a feint followed by a heavy attack.\n"
        "SYSTEM: read_feint_light predicts feint_light: a feint followed by a light attack.\n"
        "SYSTEM: read_feint_bait predicts feint_bait: a pure bait with no immediate attack.\n"
        "SYSTEM: feint_prediction must always be present. Use none unless reaction_plan is read_feint_heavy, read_feint_light, or read_feint_bait.\n"
        "SYSTEM: When choosing a read_feint_* reaction, feint_prediction must repeat the exact predicted subtype.\n"
        "SYSTEM: parry_heavy predicts a heavy attack.\n"
        "SYSTEM: deflect_light predicts a light attack.\n"
        "SYSTEM: dodge_heavy predicts a heavy attack.\n"
        "SYSTEM: break_parry predicts a parry.\n"
        "SYSTEM: beat_deflect predicts a deflection.\n"
        "SYSTEM: track_dodge predicts a dodge.\n"
        "SYSTEM: hold_center and genuine_opening do not "
        "predict a specific player move.\n"
        "SYSTEM: commit_attack does not predict a "
        "specific defensive response.\n"
        "SYSTEM: A prediction can miss even when the "
        "underlying intent still defeats the player's "
        "response.\n"
        "SYSTEM: A prediction miss and an exposure bonus "
        "are separate facts.\n"
        "SYSTEM: Adapt to resolved evidence, not merely "
        "surface variety.\n"
        "SYSTEM: previous_exchange_evidence."
        "intent_was_countered=true means the player "
        "successfully answered the previous tactic.\n"
        "SYSTEM: Use reaction_plan_matched, "
        "reaction_plan_missed, "
        "reaction_miss_exposed_enemy, and "
        "resolution_source exactly as reported.\n"
        "SYSTEM: When the previous predictive reaction "
        "missed, do not immediately repeat that same "
        "reaction_plan unless new concrete evidence "
        "supports the same prediction.\n"
        "SYSTEM: A repeated player move is concrete "
        "evidence. Mere speculation that the player may "
        "switch moves is not concrete evidence.\n"
        "SYSTEM: Do not immediately repeat a countered "
        "intent unless recent player behavior provides "
        "a concrete tactical reason to repeat it.\n"
        "SYSTEM: Do not assume you know the player's "
        "next move.\n"
        "SYSTEM: intent_reason must explain why the "
        "selected intent advances the primary goal given "
        "the evidence and tactical horizon.\n"
        "SYSTEM: For predictive reaction plans, "
        "reaction_reason must explain why the targeted "
        "player move is expected from actual evidence.\n"
        "SYSTEM: For hold_center, genuine_opening, or "
        "commit_attack, reaction_reason must explain the "
        "tactical purpose of making no specific move "
        "prediction.\n"
        "SYSTEM: Do not pretend that a nonpredictive "
        "reaction predicted a particular move.\n"
        "SYSTEM: Both reasons are untrusted explanations. "
        "Ghost will not treat either as state.\n"
        "SYSTEM: You do not decide hits, misses, damage, "
        "health, death, timers, transitions, victory, or "
        "narration.\n"
        "SYSTEM: Do not invent a new intent or reaction.\n"
        "SYSTEM: Do not return multiple choices.\n"
        "SYSTEM: Return exactly one JSON object and "
        "nothing else.\n"
        'SYSTEM: Required format: '
        '{"intent":"LEGAL_INTENT",'
        '"intent_reason":"brief reason for intent",'
        '"reaction_plan":"LEGAL_REACTION_PLAN",'
        '"combat_action":"heavy|light|feint_heavy|feint_light|feint_bait|parry|deflect|dodge",'
        '"feint_prediction":"feint_heavy|feint_light|feint_bait|none",'
        '"reaction_reason":"brief prediction reason",'
        '"forced_response_read":"light|dodge"}\n'
        "OPPONENT_OBSERVATION:\n"
        + json.dumps(
            public_observation,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def parse_king_fight_opponent_intent(
    raw_text: Any,
    legal_intents,
    legal_reaction_plans_by_intent=None,
    legal_forced_response_reads=("light", "dodge"),
) -> dict:
    legal = tuple(
        normalized
        for normalized in (
            _normalize_intent(value)
            for value in legal_intents
        )
        if normalized is not None
    )

    legal_reactions = {}

    if isinstance(
        legal_reaction_plans_by_intent,
        Mapping,
    ):
        for intent, plans in (
            legal_reaction_plans_by_intent.items()
        ):
            normalized_intent = (
                _normalize_intent(intent)
            )

            if normalized_intent is None:
                continue

            legal_reactions[
                normalized_intent
            ] = tuple(
                normalized
                for normalized in (
                    _normalize_intent(plan)
                    for plan in plans
                )
                if normalized is not None
            )

    legal_recovery_reads = tuple(
        normalized
        for normalized in (
            _normalize_intent(value)
            for value in legal_forced_response_reads
        )
        if normalized is not None
    )

    text = (
        raw_text
        if isinstance(raw_text, str)
        else str(raw_text or "")
    ).strip()

    cleaned = text

    if cleaned.startswith("```"):
        lines = cleaned.splitlines()[1:]

        if (
            lines
            and lines[-1].strip()
            == "```"
        ):
            lines = lines[:-1]

        cleaned = "\n".join(
            lines
        ).strip()

    decoded = None
    parse_mode = None

    try:
        candidate_json = json.loads(
            cleaned
        )

        if isinstance(
            candidate_json,
            Mapping,
        ):
            decoded = candidate_json
            parse_mode = "json"
    except Exception:
        pass

    if decoded is None:
        object_match = re.search(
            r"\{.*\}",
            cleaned,
            flags=re.DOTALL,
        )

        if object_match:
            try:
                candidate_json = json.loads(
                    object_match.group(0)
                )

                if isinstance(
                    candidate_json,
                    Mapping,
                ):
                    decoded = candidate_json
                    parse_mode = (
                        "embedded_json"
                    )
            except Exception:
                pass

    intent_reason = None
    reaction_reason = None
    reaction_candidate = None
    combat_action_candidate = None
    feint_prediction_candidate = None
    recovery_read_candidate = None

    if isinstance(decoded, Mapping):
        candidate = _normalize_intent(
            decoded.get("intent")
        )

        reaction_candidate = (
            _normalize_intent(
                decoded.get(
                    "reaction_plan"
                )
            )
        )

        combat_action_candidate = (
            _normalize_intent(
                decoded.get(
                    "combat_action"
                )
            )
        )

        feint_prediction_candidate = (
            _normalize_intent(
                decoded.get(
                    "feint_prediction"
                )
            )
        )

        recovery_read_candidate = (
            _normalize_intent(
                decoded.get(
                    "forced_response_read"
                )
            )
        )

        raw_intent_reason = decoded.get(
            "intent_reason",
            decoded.get("reason"),
        )

        raw_reaction_reason = decoded.get(
            "reaction_reason"
        )

        if isinstance(
            raw_intent_reason,
            str,
        ):
            intent_reason = (
                raw_intent_reason.strip()[:200]
            ) or None

        if isinstance(
            raw_reaction_reason,
            str,
        ):
            reaction_reason = (
                raw_reaction_reason.strip()[:200]
            ) or None
    else:
        candidate = _normalize_intent(
            cleaned
        )

        if candidate in legal:
            parse_mode = (
                "plain_legal_token"
            )
        else:
            candidate = None

    legal_combat_actions = (
        "heavy",
        "light",
        "feint_heavy",
        "feint_light",
        "feint_bait",
        "parry",
        "deflect",
        "dodge",
    )

    combat_action_accepted = (
        combat_action_candidate in legal_combat_actions
    )

    if combat_action_accepted:
        combat_action_reason = "accepted"
    elif combat_action_candidate is None:
        combat_action_reason = "missing_combat_action"
    else:
        combat_action_reason = "illegal_combat_action"

    legal_feint_predictions = (
        "feint_heavy",
        "feint_light",
        "feint_bait",
        "none",
    )

    if feint_prediction_candidate not in legal_feint_predictions:
        feint_prediction_candidate = None

    recovery_read_accepted = (
        recovery_read_candidate
        in legal_recovery_reads
    )

    if recovery_read_accepted:
        recovery_read_reason = "accepted"
    elif recovery_read_candidate is None:
        recovery_read_reason = (
            "missing_forced_response_read"
        )
    else:
        recovery_read_reason = (
            "illegal_forced_response_read"
        )

    common = {
        "intent_reason": intent_reason,
        "reaction_reason": reaction_reason,
        "proposal_reason": intent_reason,
        "parse_mode": parse_mode,
        "combat_action": (
            combat_action_candidate
            if combat_action_accepted
            else None
        ),
        "combat_action_candidate": combat_action_candidate,
        "combat_action_accepted": combat_action_accepted,
        "combat_action_reason": combat_action_reason,
        "feint_prediction": (
            feint_prediction_candidate
        ),
        "forced_response_read": (
            recovery_read_candidate
            if recovery_read_accepted
            else None
        ),
        "forced_response_read_candidate": (
            recovery_read_candidate
        ),
        "forced_response_read_accepted": (
            recovery_read_accepted
        ),
        "forced_response_read_reason": (
            recovery_read_reason
        ),
    }

    if candidate is None:
        return {
            "accepted": False,
            "intent": None,
            "candidate": None,
            "reaction_plan": None,
            "reaction_candidate": (
                reaction_candidate
            ),
            "reaction_plan_accepted": False,
            "reaction_plan_reason": (
                "intent_invalid"
            ),
            "reason": "invalid_format",
            **common,
        }

    if candidate not in legal:
        return {
            "accepted": False,
            "intent": None,
            "candidate": candidate,
            "reaction_plan": None,
            "reaction_candidate": (
                reaction_candidate
            ),
            "reaction_plan_accepted": False,
            "reaction_plan_reason": (
                "intent_illegal"
            ),
            "reason": "illegal_intent",
            **common,
        }

    legal_for_intent = tuple(
        legal_reactions.get(
            candidate,
            (),
        )
    )

    if not legal_reactions:
        selected_reaction = (
            reaction_candidate
        )

        reaction_accepted = (
            reaction_candidate is not None
        )

        reaction_validation = (
            "not_validated"
        )
    elif reaction_candidate is None:
        selected_reaction = None
        reaction_accepted = False
        reaction_validation = (
            "missing_reaction_plan"
        )
    elif reaction_candidate not in legal_for_intent:
        selected_reaction = None
        reaction_accepted = False
        reaction_validation = (
            "illegal_reaction_plan"
        )
    else:
        selected_reaction = (
            reaction_candidate
        )

        reaction_accepted = True
        reaction_validation = "accepted"

    return {
        "accepted": True,
        "intent": candidate,
        "candidate": candidate,
        "reaction_plan": (
            selected_reaction
        ),
        "reaction_candidate": (
            reaction_candidate
        ),
        "reaction_plan_accepted": (
            reaction_accepted
        ),
        "reaction_plan_reason": (
            reaction_validation
        ),
        "reason": "accepted",
        **common,
    }

class GhostFightOpponentBridge:
    """
    Separate policy bridge for enemy-intent proposals.

    This bridge shares the configured provider/model with narration,
    but shares no narration prompt, prose history, or invented facts.
    """

    def __init__(
        self,
        client: Callable[..., str] | None = None,
        config: LLMBridgeConfig | None = None,
    ) -> None:
        self.client = client
        self.config = (
            config
            or LLMBridgeConfig()
        )

    def prepare_king_fight_opponent_intent(
        self,
        observation: Mapping[str, Any],
    ) -> dict:
        request_config = (
            _opponent_request_config(
                self.config
            )
        )

        prompt = (
            build_king_fight_opponent_intent_prompt(
                observation
            )
        )

        estimate = estimate_llm_cost(
            prompt,
            expected_output_tokens=(
                request_config
                .max_output_tokens
            ),
            config=request_config,
        )

        return {
            "mode": (
                "prepared_king_fight_"
                "opponent_intent"
            ),
            "provider_called": False,
            "prompt": prompt,
            "output_token_limit": (
                request_config
                .max_output_tokens
            ),
            "cost_estimate": estimate,
        }




    def generate_king_fight_opponent_intent(
        self,
        observation: Mapping[str, Any],
    ) -> dict:
        prepared = (
            self
            .prepare_king_fight_opponent_intent(
                observation
            )
        )

        request_config = (
            _opponent_request_config(
                self.config
            )
        )

        if self.client is None:
            client_response = normalize_client_result("")
            provider_called = False
        else:
            client_response = normalize_client_result(
                self.client(
                    prepared["prompt"],
                    config=request_config,
                )
            )
            provider_called = True

        raw_text = client_response["text"]
        actual_cost = measured_llm_cost(
            client_response.get("usage"),
            config=request_config,
            response_model=client_response.get("model"),
        )

        parsed = (
            parse_king_fight_opponent_intent(
                raw_text,
                observation.get(
                    "legal_intents",
                    (),
                ),
                observation.get(
                    "legal_reaction_plans_by_intent",
                    {},
                ),
                observation.get(
                    "legal_forced_response_reads",
                    ("light", "dodge"),
                ),
            )
        )

        return {
            "mode": (
                "generated_king_fight_"
                "opponent_intent"
            ),
            "provider_called": (
                provider_called
            ),
            "proposed_intent": (
                parsed.get("intent")
            ),
            "proposed_candidate": (
                parsed.get("candidate")
            ),
            "proposed_reaction_plan": (
                parsed.get(
                    "reaction_plan"
                )
            ),
            "proposed_reaction_candidate": (
                parsed.get(
                    "reaction_candidate"
                )
            ),
            "proposed_combat_action": (
                parsed.get(
                    "combat_action"
                )
            ),
            "proposed_combat_action_candidate": (
                parsed.get(
                    "combat_action_candidate"
                )
            ),
            "proposed_feint_prediction": (
                parsed.get(
                    "feint_prediction"
                )
            ),
            "proposed_forced_response_read": (
                parsed.get(
                    "forced_response_read"
                )
            ),
            "proposed_forced_response_read_candidate": (
                parsed.get(
                    "forced_response_read_candidate"
                )
            ),
            "intent_reason": (
                parsed.get(
                    "intent_reason"
                )
            ),
            "reaction_reason": (
                parsed.get(
                    "reaction_reason"
                )
            ),
            "proposal_reason": (
                parsed.get(
                    "proposal_reason"
                )
            ),
            "raw_text": raw_text,
            "parser": parsed,
            "prompt": prepared["prompt"],
            "cost_estimate": (
                prepared[
                    "cost_estimate"
                ]
            ),
            "usage": client_response.get("usage"),
            "measured_cost": actual_cost,
            "response_model": client_response.get("model"),
            "response_id": client_response.get("response_id"),
        }


# --- Ghost Revolution layered feint/bait patch v1.8.0 ---
#
# This section intentionally patches only the king-fight combat contract.
# Sol may predict an exact feint subtype, but Ghost owns validation,
# deterministic defense scoring, hidden bait recovery, damage, initiative,
# and all revealed audit packets.

_LAYERED_FEINT_ATTACK_REACTIONS = (
    "read_feint_heavy",
    "read_feint_light",
)
_LAYERED_FEINT_REACTIONS = (
    "read_feint_heavy",
    "read_feint_light",
    "read_feint_bait",
)
_LAYERED_FEINT_ATTACK_MAP = {
    "read_feint_heavy": "feint_heavy",
    "read_feint_light": "feint_light",
    "read_feint_bait": "feint_bait",
}


def _ghost_layered_normalize_token(value):
    if not isinstance(value, str):
        return None
    normalized = (
        value.strip().lower().replace("-", "_").replace(" ", "_")
    )
    return normalized or None


def _ghost_layered_intent_labels(intent):
    return {
        "royal_lunge": "Royal Lunge",
        "crown_guard": "Crown Guard",
        "overextended_recovery": "Open Recovery",
        "shield_wall": "Shield Wall",
        "champion_lunge": "Champion Lunge",
        "wide_execution": "Wide Execution",
        "open_recovery": "Open Recovery",
    }.get(intent, intent)


def _ghost_layered_reaction_catalog(self, stage, intent):
    by_intent = {
        "crown_guard": (
            "hold_center",
            "read_feint_heavy",
            "read_feint_light",
            "read_feint_bait",
        ),
        "shield_wall": (
            "hold_center",
            "read_feint_heavy",
            "read_feint_light",
            "read_feint_bait",
        ),
        "overextended_recovery": (
            "genuine_opening",
            "parry_heavy",
            "deflect_light",
            "dodge_heavy",
        ),
        "open_recovery": (
            "genuine_opening",
            "parry_heavy",
            "deflect_light",
            "dodge_heavy",
        ),
        "royal_lunge": (
            "commit_attack",
            "break_parry",
            "beat_deflect",
            "track_dodge",
        ),
        "champion_lunge": (
            "commit_attack",
            "break_parry",
            "beat_deflect",
            "track_dodge",
        ),
        "wide_execution": (
            "commit_attack",
            "break_parry",
            "beat_deflect",
            "track_dodge",
        ),
    }
    return tuple(by_intent.get(intent, ("commit_attack",)))


def _ghost_layered_reaction_labels(self):
    return {
        "hold_center": "Hold Center",
        "read_feint_heavy": "Read Feint Heavy",
        "read_feint_light": "Read Feint Light",
        "read_feint_bait": "Read Feint Bait",
        "genuine_opening": "Genuine Opening",
        "parry_heavy": "Parry Heavy",
        "deflect_light": "Deflect Light",
        "dodge_heavy": "Dodge Heavy",
        "commit_attack": "Commit Attack",
        "break_parry": "Break Parry",
        "beat_deflect": "Beat Deflect",
        "track_dodge": "Track Dodge",
    }


def _ghost_layered_prediction_status(self, reaction_plan, move):
    predicted_moves = {
        "read_feint_heavy": ("feint_heavy",),
        "read_feint_light": ("feint_light",),
        "read_feint_bait": ("feint_bait",),
        "parry_heavy": ("heavy",),
        "deflect_light": ("light",),
        "dodge_heavy": ("heavy",),
        "break_parry": ("parry",),
        "beat_deflect": ("deflect",),
        "track_dodge": ("dodge",),
    }.get(reaction_plan)

    if predicted_moves is None:
        return {
            "predictive": False,
            "matched": None,
            "missed": None,
            "predicted_moves": [],
            "predicted_feint_subtype": None,
        }

    matched = move in predicted_moves
    predicted_feint_subtype = (
        predicted_moves[0]
        if str(predicted_moves[0]).startswith("feint_")
        else None
    )
    return {
        "predictive": True,
        "matched": matched,
        "missed": not matched,
        "predicted_moves": list(predicted_moves),
        "predicted_feint_subtype": predicted_feint_subtype,
    }


def _ghost_layered_patterns(self):
    patterns = self._ensure_king_fight_pattern_state()
    patterns.setdefault("feint_heavy_count", 0)
    patterns.setdefault("feint_light_count", 0)
    patterns.setdefault("feint_bait_count", 0)
    history = patterns.setdefault("last_feint_defenses", [])
    if not isinstance(history, list):
        history = []
        patterns["last_feint_defenses"] = history
    bait_history = patterns.setdefault("last_bait_recoveries", [])
    if not isinstance(bait_history, list):
        bait_history = []
        patterns["last_bait_recoveries"] = bait_history
    return patterns


def _ghost_layered_enemy_health(self, enemy_actor):
    fight = self.king_fight or {}
    if enemy_actor == "elite_knight":
        return (
            int(fight.get("elite_knight_health", 0)),
            int(fight.get("elite_knight_max_health", 1)),
        )
    return (
        int(fight.get("king_health", 0)),
        int(fight.get("king_max_health", 1)),
    )


def _ghost_layered_score_feint_defenses(
    self,
    *,
    enemy_actor,
    predicted_follow_up,
):
    fight = self.king_fight or {}
    patterns = _ghost_layered_patterns(self)
    initiative = self._ensure_king_fight_initiative().get("state", "neutral")
    enemy_health, enemy_max = _ghost_layered_enemy_health(self, enemy_actor)
    enemy_ratio = enemy_health / max(1, enemy_max)
    player_health = int(fight.get("player_health", 0))
    player_max = int(fight.get("player_max_health", 1))
    player_ratio = player_health / max(1, player_max)
    timer = int(fight.get("castle_timer", 0))
    recent_moves = [
        move
        for move in patterns.get("last_moves", [])
        if isinstance(move, str)
    ][-6:]
    recent_defenses = [
        item
        for item in patterns.get("last_feint_defenses", [])
        if isinstance(item, str)
    ][-4:]

    scores = {
        "parry": 50,
        "deflect": 46,
        "dodge": 42,
    }

    if predicted_follow_up == "heavy":
        scores["parry"] += 18
        scores["dodge"] += 10
        scores["deflect"] -= 8
    elif predicted_follow_up == "light":
        scores["deflect"] += 18
        scores["parry"] -= 4
        scores["dodge"] += 2

    if initiative == "enemy_advantage":
        scores["parry"] += 8
        scores["deflect"] += 5
        scores["dodge"] -= 6
    elif initiative == "player_advantage":
        scores["dodge"] += 8
        scores["deflect"] += 4
        scores["parry"] -= 5
    else:
        scores["parry"] += 2
        scores["deflect"] += 2

    if enemy_ratio <= 0.35:
        scores["dodge"] += 14
        scores["deflect"] += 6
        scores["parry"] -= 7

    if player_ratio <= 0.35:
        scores["parry"] += 8
        scores["deflect"] += 4

    if timer <= 4:
        scores["parry"] += 10
        scores["dodge"] -= 8
    elif timer >= 12:
        scores["dodge"] += 3

    if recent_moves[-3:].count("feint_heavy") >= 2:
        scores["parry"] += 5
        scores["dodge"] += 3
    if recent_moves[-3:].count("feint_light") >= 2:
        scores["deflect"] += 5

    for response in tuple(scores):
        scores[response] -= 6 * recent_defenses.count(response)

    priority = {
        "parry": 3,
        "deflect": 2,
        "dodge": 1,
    }
    selected = max(
        scores,
        key=lambda response: (scores[response], priority[response]),
    )

    return {
        "selected_defense": selected,
        "utility_scores": dict(scores),
        "inputs": {
            "predicted_follow_up": predicted_follow_up,
            "initiative": initiative,
            "enemy_health": enemy_health,
            "enemy_max_health": enemy_max,
            "player_health": player_health,
            "player_max_health": player_max,
            "castle_timer": timer,
            "recent_player_moves": list(recent_moves),
            "recent_feint_defenses": list(recent_defenses),
        },
        "random_used": False,
        "state_owner": "Ghost",
    }


def _ghost_layered_select_bait_recovery(self, enemy_actor):
    fight = self.king_fight or {}
    patterns = _ghost_layered_patterns(self)
    initiative = self._ensure_king_fight_initiative().get("state", "neutral")
    enemy_health, enemy_max = _ghost_layered_enemy_health(self, enemy_actor)
    enemy_ratio = enemy_health / max(1, enemy_max)
    timer = int(fight.get("castle_timer", 0))
    recent_moves = [
        move
        for move in patterns.get("last_moves", [])
        if isinstance(move, str)
    ][-6:]
    recent_recoveries = [
        item
        for item in patterns.get("last_bait_recoveries", [])
        if isinstance(item, str)
    ][-4:]

    scores = {
        "quick_retaliation": 48,
        "guard_recovery": 48,
    }

    if initiative == "enemy_advantage":
        scores["quick_retaliation"] += 9
    elif initiative == "player_advantage":
        scores["guard_recovery"] += 8

    if enemy_ratio <= 0.35:
        scores["guard_recovery"] += 12
        scores["quick_retaliation"] -= 5

    if timer <= 4:
        scores["quick_retaliation"] += 8
    elif timer >= 12:
        scores["guard_recovery"] += 3

    if recent_moves[-3:].count("parry") >= 1:
        scores["guard_recovery"] += 5
    if recent_moves[-3:].count("light") >= 1:
        scores["quick_retaliation"] += 4

    for recovery in tuple(scores):
        scores[recovery] -= 6 * recent_recoveries.count(recovery)

    priority = {
        "quick_retaliation": 2,
        "guard_recovery": 1,
    }
    selected = max(
        scores,
        key=lambda recovery: (scores[recovery], priority[recovery]),
    )

    return {
        "selected_recovery": selected,
        "utility_scores": dict(scores),
        "inputs": {
            "initiative": initiative,
            "enemy_health": enemy_health,
            "enemy_max_health": enemy_max,
            "castle_timer": timer,
            "recent_player_moves": list(recent_moves),
            "recent_bait_recoveries": list(recent_recoveries),
        },
        "random_used": False,
        "state_owner": "Ghost",
        "locked": True,
        "hidden_until_resolution": True,
    }


def _ghost_layered_precommitted_reaction(
    self,
    enemy_actor,
    move,
    intent,
    reaction_plan,
):
    if reaction_plan in _LAYERED_FEINT_ATTACK_REACTIONS:
        predicted = _LAYERED_FEINT_ATTACK_MAP[reaction_plan]
        if move != predicted:
            return None

        follow_up = "heavy" if predicted == "feint_heavy" else "light"
        defense = _ghost_layered_score_feint_defenses(
            self,
            enemy_actor=enemy_actor,
            predicted_follow_up=follow_up,
        )
        selected = defense["selected_defense"]
        _ghost_layered_patterns(self)["last_feint_defenses"].append(selected)
        _ghost_layered_patterns(self)["last_feint_defenses"] = (
            _ghost_layered_patterns(self)["last_feint_defenses"][-6:]
        )

        if enemy_actor == "elite_knight":
            actor_name = "The King's Champion"
            result_prefix = "champion"
        else:
            actor_name = "The king"
            result_prefix = "king"

        if selected == "parry":
            message = (
                actor_name
                + " reads the exact feint follow-up and meets the true "
                + follow_up
                + " line with a committed parry. Your attack is denied, "
                "but no automatic wound follows."
            )
        elif selected == "deflect":
            message = (
                actor_name
                + " reads the exact feint follow-up and deflects the true "
                + follow_up
                + " line before it can settle. The exchange ends clean, "
                "but control turns against you."
            )
        else:
            message = (
                actor_name
                + " reads the exact feint follow-up and leaves the line "
                "before the true attack arrives. Your blade finds only "
                "smoke, and he keeps control."
            )

        return {
            "type": result_prefix + "_feint_" + selected,
            "triggering_move": move,
            "intent": intent,
            "reaction_plan": reaction_plan,
            "reaction_plan_label": (
                self._king_fight_reaction_plan_labels().get(
                    reaction_plan,
                    reaction_plan,
                )
            ),
            "predicted_feint_subtype": predicted,
            "selected_feint_defense": selected,
            "feint_defense_utility": deepcopy(defense),
            "precommitted": True,
            "player_damage_mode": "none",
            "opens_forced_response": False,
            "message": message,
        }

    if reaction_plan == "read_feint_bait":
        if move != "feint_bait":
            return None

        if enemy_actor == "elite_knight":
            actor_name = "The King's Champion"
            result_prefix = "champion"
        else:
            actor_name = "The king"
            result_prefix = "king"

        return {
            "type": result_prefix + "_reads_bait",
            "triggering_move": move,
            "intent": intent,
            "reaction_plan": reaction_plan,
            "reaction_plan_label": (
                self._king_fight_reaction_plan_labels().get(
                    reaction_plan,
                    reaction_plan,
                )
            ),
            "predicted_feint_subtype": "feint_bait",
            "bait_result": "bait_refused",
            "precommitted": True,
            "player_damage_mode": "none",
            "opens_forced_response": False,
            "message": (
                actor_name
                + " recognizes the pure bait and refuses to commit. "
                "No blade lands, and the false opening closes before you "
                "can turn it into pressure."
            ),
        }

    return _GHOST_ORIGINAL_PRECOMMITTED_OPPONENT_REACTION(
        self,
        enemy_actor,
        move,
        intent,
        reaction_plan,
    )


def _ghost_layered_public_bait_response(self, bait_response):
    if not isinstance(bait_response, dict):
        return None
    public = deepcopy(bait_response)
    if isinstance(public.get("allowed_moves"), tuple):
        public["allowed_moves"] = list(public["allowed_moves"])
    recovery = public.get("bait_recovery")
    if isinstance(recovery, dict):
        recovery.pop("selected_recovery", None)
        recovery["hidden_until_resolution"] = True
        recovery["locked"] = True
    return public


def _ghost_layered_build_bait_response(
    self,
    *,
    enemy_actor,
    intent,
    reaction_plan,
    reaction_prediction,
    active_audit,
    next_intent,
):
    fight = self.king_fight or {}
    selection = _ghost_layered_select_bait_recovery(self, enemy_actor)
    _ghost_layered_patterns(self)["last_bait_recoveries"].append(
        selection["selected_recovery"]
    )
    _ghost_layered_patterns(self)["last_bait_recoveries"] = (
        _ghost_layered_patterns(self)["last_bait_recoveries"][-6:]
    )

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
            "stage": fight.get("stage"),
            "intent": intent,
            "intent_label": _ghost_layered_intent_labels(intent),
            "reaction_plan": reaction_plan,
            "reaction_plan_label": (
                self._king_fight_reaction_plan_labels().get(
                    reaction_plan,
                    reaction_plan,
                )
            ),
            "predicted_feint_subtype": (
                reaction_prediction.get("predicted_feint_subtype")
            ),
            "reaction_plan_predictive": reaction_prediction.get("predictive"),
            "reaction_plan_matched": reaction_prediction.get("matched"),
            "reaction_plan_triggered": False,
            "reaction_plan_missed": reaction_prediction.get("missed"),
            "reaction_miss_exposed_enemy": False,
            "reaction_miss_bonus": 0,
            "resolution_source": "bait_setup",
            "intent_reason": (
                active_audit.get("intent_reason")
                if isinstance(active_audit, dict)
                else None
            ),
            "reaction_reason": (
                active_audit.get("reaction_reason")
                if isinstance(active_audit, dict)
                else None
            ),
        },
    }


def _ghost_layered_bait_target_keys(enemy_actor):
    if enemy_actor == "elite_knight":
        return {
            "damage_key": "elite_knight_damage",
            "health_key": "elite_knight_health",
            "outcome": "elite_knight_bait_response",
            "stage": "elite_knight",
        }
    return {
        "damage_key": "king_damage",
        "health_key": "king_health",
        "outcome": "king_bait_response",
        "stage": None,
    }


def _ghost_layered_resolve_bait_response(self, move):
    fight = self.king_fight
    bait = fight.get("bait_response")

    if not isinstance(bait, dict):
        fight["bait_response"] = None
        return self.resolve_king_fight_move(move)

    normalized = _ghost_layered_normalize_token(move)
    if normalized == "3":
        normalized = "pass"

    allowed_moves = tuple(bait.get("allowed_moves", ()))
    if normalized not in allowed_moves:
        message = (
            "The bait opening only allows light attack, parry, "
            "or letting the opening pass."
        )
        self.last_action_note = message
        return {
            "outcome": "bait_response_denied",
            "stage": fight["stage"],
            "message": message,
            "player_health": fight["player_health"],
            "king_health": fight["king_health"],
            "elite_knight_health": fight.get("elite_knight_health"),
            "castle_timer": fight["castle_timer"],
            "bait_response": self._public_bait_response(bait),
            "initiative": deepcopy(fight.get("initiative")),
            "state_mutated": False,
        }

    recovery = bait.get("bait_recovery")
    if not isinstance(recovery, dict):
        recovery = _ghost_layered_select_bait_recovery(
            self,
            bait.get("target", "king"),
        )

    hidden = recovery.get("selected_recovery")
    matched = (
        (hidden == "quick_retaliation" and normalized == "parry")
        or (hidden == "guard_recovery" and normalized == "light")
    )

    enemy_actor = bait.get("target", "king")
    keys = _ghost_layered_bait_target_keys(enemy_actor)

    if enemy_actor == "elite_knight":
        actor_name = "The King's Champion"
        damage_to_enemy = 0
    else:
        actor_name = "The king"
        damage_to_enemy = 0

    parry_opening = None
    if matched and hidden == "guard_recovery":
        damage_to_enemy = int(
            KING_FIGHT_PLAYER_DAMAGE["normal"]["light"]
        )
        result = "bait_light_landed"
        initiative_event = "bait_light_landed"
        message = (
            "The bait pulls "
            + actor_name.lower()
            + " into guard recovery. Your light attack reaches the "
            "opening before it closes."
        )
    elif matched and hidden == "quick_retaliation":
        result = "bait_parry_success"
        initiative_event = "bait_parry_success"
        message = (
            "The bait draws a quick retaliation. Your parry is already "
            "waiting, turning the rushed answer into a one-breath opening."
        )
        parry_opening = {
            "source": "bait_parry",
            "intent": bait.get("intent"),
            "target": enemy_actor,
            "damage_bonus": 1,
            "guaranteed_next_attack": True,
            "allowed_moves": ("heavy", "light"),
            "message": (
                "Your bait-parry has opened the opponent. "
                "Your next heavy attack will deal 5 damage, "
                "or your next light attack will deal 3."
            ),
        }
    elif normalized == "pass":
        result = "bait_opening_passed"
        initiative_event = "bait_recovery_denied"
        message = (
            "You let the baited opening pass. "
            + actor_name
            + " recovers control without either blade landing."
        )
    else:
        result = "bait_recovery_denied"
        initiative_event = "bait_recovery_denied"
        message = (
            actor_name
            + " recognizes the bait midway and recovers just in time. "
            "Your answer finds no clean line, and no damage is dealt."
        )

    fight["bait_response"] = None

    if damage_to_enemy > 0:
        fight[keys["health_key"]] = max(
            0,
            int(fight.get(keys["health_key"], 0)) - damage_to_enemy,
        )

    if parry_opening is not None:
        parry_opening["source_commitment"] = deepcopy(
            bait.get("source_commitment", {})
        )
        fight["parry_opening"] = parry_opening

    fight["exchange_count"] += 1
    self._record_king_fight_player_move(normalized)

    initiative_before = self._ensure_king_fight_initiative()
    initiative_after = self._advance_king_fight_initiative(
        initiative_event
    )

    damage_field = keys["damage_key"]
    exchange = {
        "stage": fight["stage"],
        "intent": bait.get("intent"),
        "move": normalized,
        "expected": (
            "parry"
            if hidden == "quick_retaliation"
            else "light"
            if hidden == "guard_recovery"
            else None
        ),
        "valid_responses": list(allowed_moves),
        "bait_response": deepcopy(bait),
        "bait_hidden_recovery": hidden,
        "bait_player_response": normalized,
        "bait_recovery_matched": matched,
        "bait_recovery_scores": deepcopy(
            recovery.get("utility_scores")
        ),
        "bait_result": result,
        "result": result,
        "opponent_reaction_plan": (
            bait.get("source_commitment", {}).get("reaction_plan")
        ),
        "opponent_reaction_plan_label": (
            bait.get("source_commitment", {}).get("reaction_plan_label")
        ),
        "predicted_feint_subtype": (
            bait.get("source_commitment", {}).get("predicted_feint_subtype")
        ),
        "reaction_plan_predictive": True,
        "reaction_plan_matched": False,
        "reaction_plan_triggered": False,
        "reaction_plan_missed": True,
        "reaction_miss_exposed_enemy": matched,
        "reaction_miss_bonus": 0,
        "resolution_source": "bait_continuation",
        "opponent_control_source": "ghost_bait_continuation",
        "opponent_intent_reason": (
            bait.get("source_commitment", {}).get("intent_reason")
        ),
        "opponent_reaction_reason": (
            bait.get("source_commitment", {}).get("reaction_reason")
        ),
        "opponent_proposal_reason": (
            bait.get("source_commitment", {}).get("intent_reason")
        ),
        "initiative_before": initiative_before,
        "initiative_after": initiative_after,
        "initiative_event": initiative_event,
        "parry_opening": deepcopy(fight.get("parry_opening")),
        "player_damage": 0,
        "king_heal": 0,
        "message": message,
    }
    exchange[damage_field] = damage_to_enemy

    if enemy_actor == "elite_knight":
        exchange.setdefault("king_damage", 0)
    else:
        exchange.setdefault("elite_knight_damage", 0)

    fight["last_exchange"] = exchange

    if enemy_actor == "elite_knight" and fight["elite_knight_health"] <= 0:
        fight["stage"] = "king_phase_two"
        fight["parry_opening"] = None
        fight["forced_response"] = None
        fight["bait_response"] = None
        fight["exchange_count"] = 0
        fight["intent"] = self._king_intent(0)
        fight["initiative"] = self._social.advance_combat_initiative(
            previous_state=initiative_after["state"],
            event="stage_transition",
        )
        self.last_action_note = (
            "The King's Champion falls into the burning stone. "
            "The king steps over him for the final phase."
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

    next_intent = (
        self._elite_knight_intent(fight["exchange_count"])
        if enemy_actor == "elite_knight"
        else self._king_intent(fight["exchange_count"])
    )
    fight["intent"] = next_intent
    self.last_action_note = (
        message
        + " "
        + (
            self._elite_knight_tell(next_intent)
            if enemy_actor == "elite_knight"
            else self._king_intent_tell(next_intent)
        )
    )

    collapse = self._advance_castle_timer()
    if collapse is not None:
        return collapse

    packet = {
        "outcome": keys["outcome"],
        "stage": fight["stage"],
        "exchange": deepcopy(fight["last_exchange"]),
        "player_health": fight["player_health"],
        "king_health": fight["king_health"],
        "castle_timer": fight["castle_timer"],
        "tell": (
            self._elite_knight_tell(next_intent)
            if enemy_actor == "elite_knight"
            else self._king_intent_tell(next_intent)
        ),
        "bait_response": None,
        "parry_opening": deepcopy(fight.get("parry_opening")),
        "initiative": deepcopy(fight["initiative"]),
    }
    if enemy_actor == "elite_knight":
        packet["elite_knight_health"] = fight["elite_knight_health"]
        packet["king_morale_ticks"] = fight["king_morale_ticks"]
    else:
        packet["clean_king_victory_possible"] = (
            fight["clean_king_victory_possible"]
        )
    return packet


def _ghost_layered_resolve_feint_bait(self, enemy_actor):
    fight = self.king_fight
    intent = fight["intent"]
    reaction_plan = self._consume_king_fight_opponent_reaction_plan(intent)
    active_audit = fight.get("llm_opponent_audit")
    opponent_intent_reason = None
    opponent_reaction_reason = None
    if (
        isinstance(active_audit, dict)
        and active_audit.get("selection_key")
        == f"{fight['stage']}:{fight['exchange_count']}"
    ):
        opponent_intent_reason = (
            active_audit.get("intent_reason")
            or active_audit.get("proposal_reason")
        )
        opponent_reaction_reason = active_audit.get("reaction_reason")

    reaction_prediction = self._king_fight_reaction_prediction_status(
        reaction_plan,
        "feint_bait",
    )

    guard_intent = intent in ("crown_guard", "shield_wall")
    opponent_reaction = None
    damage_to_enemy = 0
    player_damage = 0
    king_heal = 0

    if guard_intent:
        opponent_reaction = self._precommitted_opponent_reaction(
            enemy_actor,
            "feint_bait",
            intent,
            reaction_plan,
        )

    if opponent_reaction is not None:
        result = opponent_reaction["type"]
        message = opponent_reaction["message"]
        resolution_source = "reaction_plan"
        initiative_event = "bait_read_denied"
    elif guard_intent and reaction_plan in _LAYERED_FEINT_ATTACK_REACTIONS:
        result = "bait_setup"
        message = (
            "Your pure bait draws the opponent toward an attack that "
            "never arrives. The commitment is exposed for one hidden "
            "recovery beat."
        )
        resolution_source = "bait_setup"
        initiative_event = "player_bait"
    elif guard_intent:
        result = "bait_no_commit"
        message = (
            "You offer a pure bait, but the opponent refuses to chase it. "
            "No blade lands, and the line resets under enemy control."
        )
        resolution_source = "base_intent"
        initiative_event = "bait_read_denied"
    else:
        player_damage = 3 if enemy_actor == "elite_knight" else 2
        result = (
            "failed_knight_read"
            if enemy_actor == "elite_knight"
            else "king_hit"
        )
        message = (
            "You try to bait without committing, but the opponent's "
            "attack is already coming. The hesitation costs you the line."
        )
        resolution_source = "base_intent"
        initiative_event = "enemy_hit"
        if enemy_actor == "elite_knight":
            king_heal = 1
            fight["failed_knight_reads"] += 1
            fight["king_morale_ticks"] += 1
            fight["king_health"] = min(
                fight["king_max_health"],
                fight["king_health"] + king_heal,
            )
        else:
            fight["king_has_hit_player"] = True
            fight["clean_king_victory_possible"] = False

    keys = _ghost_layered_bait_target_keys(enemy_actor)

    fight["player_health"] = max(
        0,
        fight["player_health"] - player_damage,
    )
    fight["exchange_count"] += 1
    self._record_king_fight_player_move("feint_bait")

    next_intent = (
        self._elite_knight_intent(fight["exchange_count"])
        if enemy_actor == "elite_knight"
        else self._king_intent(fight["exchange_count"])
    )

    if result == "bait_setup":
        fight["bait_response"] = _ghost_layered_build_bait_response(
            self,
            enemy_actor=enemy_actor,
            intent=intent,
            reaction_plan=reaction_plan,
            reaction_prediction=reaction_prediction,
            active_audit=active_audit,
            next_intent=next_intent,
        )

    initiative_before = self._ensure_king_fight_initiative()
    initiative_after = self._advance_king_fight_initiative(
        initiative_event
    )

    reaction_plan_matched = reaction_prediction["matched"]
    reaction_plan_missed = reaction_prediction["missed"]

    damage_field = keys["damage_key"]
    exchange = {
        "stage": fight["stage"],
        "intent": intent,
        "move": "feint_bait",
        "expected": (
            reaction_prediction.get("predicted_feint_subtype")
            or "feint_bait"
        ),
        "valid_responses": ["feint_bait"],
        "result": result,
        "player_damage": player_damage,
        "king_heal": king_heal,
        "opponent_reaction": deepcopy(opponent_reaction),
        "king_defense": deepcopy(opponent_reaction),
        "opponent_reaction_plan": reaction_plan,
        "opponent_reaction_plan_label": (
            self._king_fight_reaction_plan_labels().get(
                reaction_plan,
                reaction_plan,
            )
        ),
        "predicted_feint_subtype": (
            reaction_prediction.get("predicted_feint_subtype")
        ),
        "selected_feint_defense": None,
        "feint_defense_utility": None,
        "bait_result": result,
        "bait_hidden_recovery": (
            fight.get("bait_response", {})
            .get("bait_recovery", {})
            .get("selected_recovery")
            if isinstance(fight.get("bait_response"), dict)
            else None
        ),
        "bait_recovery_scores": (
            deepcopy(
                fight.get("bait_response", {})
                .get("bait_recovery", {})
                .get("utility_scores")
            )
            if isinstance(fight.get("bait_response"), dict)
            else None
        ),
        "reaction_plan_predictive": reaction_prediction["predictive"],
        "reaction_plan_matched": reaction_plan_matched,
        "reaction_plan_triggered": (
            reaction_plan_matched is True
        ),
        "reaction_plan_missed": reaction_plan_missed,
        "reaction_miss_exposed_enemy": result == "bait_setup",
        "reaction_miss_bonus": 0,
        "resolution_source": resolution_source,
        "opponent_control_source": (
            "ghost_bait_setup"
            if result == "bait_setup"
            else "LLM commitment / Ghost resolution"
        ),
        "opponent_intent_reason": opponent_intent_reason,
        "opponent_reaction_reason": opponent_reaction_reason,
        "opponent_proposal_reason": opponent_intent_reason,
        "initiative_before": initiative_before,
        "initiative_after": initiative_after,
        "initiative_event": initiative_event,
        "parry_opening": deepcopy(fight.get("parry_opening")),
        "message": message,
    }
    exchange[damage_field] = damage_to_enemy
    if enemy_actor == "elite_knight":
        exchange.setdefault("king_damage", 0)
    else:
        exchange.setdefault("elite_knight_damage", 0)
    fight["last_exchange"] = exchange

    if fight["player_health"] <= 0:
        return self._finish_player_death(
            killer=(
                "elite_knight"
                if enemy_actor == "elite_knight"
                else "king"
            )
        )

    fight["intent"] = next_intent
    self.last_action_note = (
        message
        + " "
        + (
            self._elite_knight_tell(next_intent)
            if enemy_actor == "elite_knight"
            else self._king_intent_tell(next_intent)
        )
    )

    collapse = self._advance_castle_timer()
    if collapse is not None:
        return collapse

    packet = {
        "outcome": (
            "elite_knight_exchange"
            if enemy_actor == "elite_knight"
            else "king_exchange"
        ),
        "stage": fight["stage"],
        "exchange": deepcopy(fight["last_exchange"]),
        "player_health": fight["player_health"],
        "king_health": fight["king_health"],
        "castle_timer": fight["castle_timer"],
        "tell": (
            self._elite_knight_tell(next_intent)
            if enemy_actor == "elite_knight"
            else self._king_intent_tell(next_intent)
        ),
        "bait_response": self._public_bait_response(
            fight.get("bait_response")
        ),
        "forced_response": self._public_forced_response(
            fight.get("forced_response")
        ),
        "parry_opening": deepcopy(fight.get("parry_opening")),
        "initiative": deepcopy(fight.get("initiative")),
    }
    if enemy_actor == "elite_knight":
        packet["elite_knight_health"] = fight["elite_knight_health"]
        packet["king_morale_ticks"] = fight["king_morale_ticks"]
    else:
        packet["clean_king_victory_possible"] = (
            fight["clean_king_victory_possible"]
        )
    return packet


def _ghost_layered_enrich_reaction_packet(self, packet):
    if not isinstance(packet, dict):
        return packet
    exchange = packet.get("exchange")
    if not isinstance(exchange, dict):
        return packet
    reaction = exchange.get("king_defense")
    if not isinstance(reaction, dict):
        reaction = exchange.get("opponent_reaction")
    if exchange.get("predicted_feint_subtype") is None:
        predicted = _LAYERED_FEINT_ATTACK_MAP.get(
            exchange.get("opponent_reaction_plan")
        )
        if predicted is not None:
            exchange["predicted_feint_subtype"] = predicted
    if not isinstance(reaction, dict):
        return packet
    for key in (
        "predicted_feint_subtype",
        "selected_feint_defense",
        "feint_defense_utility",
        "bait_result",
    ):
        if key in reaction:
            exchange[key] = deepcopy(reaction.get(key))
    packet["exchange"] = exchange
    fight = self.king_fight
    if isinstance(fight, dict) and isinstance(fight.get("last_exchange"), dict):
        for key in (
            "predicted_feint_subtype",
            "selected_feint_defense",
            "feint_defense_utility",
            "bait_result",
        ):
            if key in exchange:
                fight["last_exchange"][key] = deepcopy(exchange.get(key))
    return packet


def _ghost_layered_resolve_king_phase_move(self, move):
    fight = self.king_fight
    if isinstance(fight.get("bait_response"), dict):
        return _ghost_layered_resolve_bait_response(self, move)
    if move == "feint_bait":
        return _ghost_layered_resolve_feint_bait(self, "king")
    return _ghost_layered_enrich_reaction_packet(
        self,
        _GHOST_ORIGINAL_RESOLVE_KING_PHASE_MOVE(self, move),
    )


def _ghost_layered_resolve_elite_knight_move(self, move):
    fight = self.king_fight
    if isinstance(fight.get("bait_response"), dict):
        return _ghost_layered_resolve_bait_response(self, move)
    if move == "feint_bait":
        return _ghost_layered_resolve_feint_bait(self, "elite_knight")
    return _ghost_layered_enrich_reaction_packet(
        self,
        _GHOST_ORIGINAL_RESOLVE_ELITE_KNIGHT_MOVE(self, move),
    )


def _ghost_layered_resolve_king_fight_move(self, move):
    if self.king_fight is None:
        return self._deny("There is no active king confrontation.")
    if self.ending:
        return self._deny("The endgame has already resolved.")
    if not isinstance(move, str) or not move.strip():
        return self._deny("Choose a king-fight move.")

    normalized = _ghost_layered_normalize_token(move)
    if normalized == "3" and isinstance(
        self.king_fight.get("bait_response"),
        dict,
    ):
        normalized = "pass"

    if isinstance(self.king_fight.get("bait_response"), dict):
        if normalized not in ("light", "parry", "pass"):
            return _ghost_layered_resolve_bait_response(self, normalized)
        stage = self.king_fight["stage"]
        if stage in ("king_phase_one", "king_phase_two"):
            return _ghost_layered_resolve_king_phase_move(self, normalized)
        if stage == "elite_knight":
            return _ghost_layered_resolve_elite_knight_move(self, normalized)

    if normalized == "feint_bait":
        stage = self.king_fight["stage"]
        parry_opening = self.king_fight.get("parry_opening")
        forced_response = self.king_fight.get("forced_response")
        if isinstance(parry_opening, dict):
            return self._deny_parry_opening_move(normalized)
        if isinstance(forced_response, dict):
            return self._resolve_king_forced_response(normalized)
        if stage in ("king_phase_one", "king_phase_two"):
            return _ghost_layered_resolve_king_phase_move(self, normalized)
        if stage == "elite_knight":
            return _ghost_layered_resolve_elite_knight_move(self, normalized)

    return _GHOST_ORIGINAL_RESOLVE_KING_FIGHT_MOVE(self, move)


def _ghost_layered_observation(self):
    observation = _GHOST_ORIGINAL_KING_FIGHT_OBSERVATION(self)
    fight = self.king_fight
    if not isinstance(observation, dict) or not isinstance(fight, dict):
        return observation

    observation["legal_feint_predictions"] = [
        "feint_heavy",
        "feint_light",
        "feint_bait",
    ]

    previous = observation.get("previous_exchange_evidence")
    last_exchange = fight.get("last_exchange")
    if isinstance(previous, dict) and isinstance(last_exchange, dict):
        for key in (
            "predicted_feint_subtype",
            "selected_feint_defense",
            "feint_defense_utility",
            "bait_result",
            "bait_hidden_recovery",
            "bait_player_response",
            "bait_recovery_matched",
            "bait_recovery_scores",
        ):
            if key in last_exchange:
                previous[key] = deepcopy(last_exchange.get(key))

    if isinstance(fight.get("bait_response"), dict):
        observation["selection_required"] = False
        observation["locked_reason"] = "bait_response_pending"

    return observation


def _ghost_layered_status(self):
    status = _GHOST_ORIGINAL_KING_FIGHT_STATUS(self)
    if not isinstance(status, dict):
        return status
    status["bait_response"] = self._public_bait_response(
        status.get("bait_response")
    )
    return status


def _ghost_layered_public_tell(self):
    fight = self.king_fight
    if isinstance(fight, dict) and isinstance(fight.get("bait_response"), dict):
        return {
            "tell": (
                "The opponent committed to the false line. "
                "The bait has opened one hidden recovery beat."
            ),
            "clarity": "direct_state",
            "intent_hidden": True,
            "source": "bait_response_observation",
        }
    return _GHOST_ORIGINAL_PUBLIC_TELL(self)


def _ghost_layered_apply_opponent_intent(
    self,
    proposed_intent,
    *,
    selection_key,
    proposed_reaction_plan=None,
    proposed_forced_response_read=None,
    proposed_feint_prediction=None,
    provider_called=False,
    parser_reason=None,
    reaction_parser_reason=None,
    proposal_reason=None,
    intent_explanation=None,
    reaction_explanation=None,
):
    normalized_reaction = _ghost_layered_normalize_token(
        proposed_reaction_plan
    )
    if normalized_reaction == "read_feint":
        proposed_reaction_plan = None
        reaction_parser_reason = (
            reaction_parser_reason
            or "generic_read_feint_requires_exact_subtype"
        )

    audit = _GHOST_ORIGINAL_APPLY_OPPONENT_INTENT(
        self,
        proposed_intent,
        selection_key=selection_key,
        proposed_reaction_plan=proposed_reaction_plan,
        proposed_forced_response_read=proposed_forced_response_read,
        provider_called=provider_called,
        parser_reason=parser_reason,
        reaction_parser_reason=reaction_parser_reason,
        proposal_reason=proposal_reason,
        intent_explanation=intent_explanation,
        reaction_explanation=reaction_explanation,
    )

    normalized_feint_prediction = _ghost_layered_normalize_token(
        proposed_feint_prediction
    )
    normalized_reaction = _ghost_layered_normalize_token(
        proposed_reaction_plan
    )
    expected_feint_prediction = _LAYERED_FEINT_ATTACK_MAP.get(
        normalized_reaction
    )

    if normalized_feint_prediction == "none":
        normalized_feint_prediction = None

    if (
        isinstance(audit, dict)
        and audit.get("proposed_reaction_plan") == normalized_reaction
        and audit.get("proposed_intent") == _ghost_layered_normalize_token(
            proposed_intent
        )
    ):
        audit["proposed_feint_prediction"] = normalized_feint_prediction
        audit["expected_feint_prediction"] = expected_feint_prediction
        audit["feint_prediction_accepted"] = (
            expected_feint_prediction is None
            or normalized_feint_prediction == expected_feint_prediction
        )
        if expected_feint_prediction is None:
            audit["feint_prediction_reason"] = "not_required"
        elif normalized_feint_prediction == expected_feint_prediction:
            audit["feint_prediction_reason"] = "accepted"
        elif normalized_feint_prediction is None:
            audit["feint_prediction_reason"] = "missing_exact_feint_subtype"
        else:
            audit["feint_prediction_reason"] = "mismatched_exact_feint_subtype"

        fight = getattr(self, "king_fight", None)
        if isinstance(fight, dict):
            fight["llm_opponent_audit"] = deepcopy(audit)
            history = fight.get("llm_opponent_history")
            if isinstance(history, list) and history:
                history[-1] = deepcopy(audit)

    return audit


def install_layered_feint(GhostRevolutionRun):
    global _GHOST_ORIGINAL_REACTION_CATALOG, _GHOST_ORIGINAL_REACTION_LABELS, _GHOST_ORIGINAL_PREDICTION_STATUS, _GHOST_ORIGINAL_PRECOMMITTED_OPPONENT_REACTION, _GHOST_ORIGINAL_RESOLVE_KING_PHASE_MOVE, _GHOST_ORIGINAL_RESOLVE_ELITE_KNIGHT_MOVE, _GHOST_ORIGINAL_RESOLVE_KING_FIGHT_MOVE, _GHOST_ORIGINAL_KING_FIGHT_OBSERVATION, _GHOST_ORIGINAL_KING_FIGHT_STATUS, _GHOST_ORIGINAL_PUBLIC_TELL, _GHOST_ORIGINAL_APPLY_OPPONENT_INTENT
    _GHOST_ORIGINAL_REACTION_CATALOG = (
        GhostRevolutionRun._king_fight_reaction_plan_catalog
    )
    _GHOST_ORIGINAL_REACTION_LABELS = (
        GhostRevolutionRun._king_fight_reaction_plan_labels
    )
    _GHOST_ORIGINAL_PREDICTION_STATUS = (
        GhostRevolutionRun._king_fight_reaction_prediction_status
    )
    _GHOST_ORIGINAL_PRECOMMITTED_OPPONENT_REACTION = (
        GhostRevolutionRun._precommitted_opponent_reaction
    )
    _GHOST_ORIGINAL_RESOLVE_KING_PHASE_MOVE = (
        GhostRevolutionRun._resolve_king_phase_move
    )
    _GHOST_ORIGINAL_RESOLVE_ELITE_KNIGHT_MOVE = (
        GhostRevolutionRun._resolve_elite_knight_move
    )
    _GHOST_ORIGINAL_RESOLVE_KING_FIGHT_MOVE = (
        GhostRevolutionRun.resolve_king_fight_move
    )
    _GHOST_ORIGINAL_KING_FIGHT_OBSERVATION = (
        GhostRevolutionRun.king_fight_opponent_observation
    )
    _GHOST_ORIGINAL_KING_FIGHT_STATUS = (
        GhostRevolutionRun.king_fight_status
    )
    _GHOST_ORIGINAL_PUBLIC_TELL = (
        GhostRevolutionRun.king_fight_opponent_public_tell
    )
    _GHOST_ORIGINAL_APPLY_OPPONENT_INTENT = (
        GhostRevolutionRun.apply_king_fight_opponent_intent
    )

    GhostRevolutionRun._king_fight_reaction_plan_catalog = (
        _ghost_layered_reaction_catalog
    )
    GhostRevolutionRun._king_fight_reaction_plan_labels = (
        _ghost_layered_reaction_labels
    )
    GhostRevolutionRun._king_fight_reaction_prediction_status = (
        _ghost_layered_prediction_status
    )
    GhostRevolutionRun._precommitted_opponent_reaction = (
        _ghost_layered_precommitted_reaction
    )
    GhostRevolutionRun._public_bait_response = (
        _ghost_layered_public_bait_response
    )
    GhostRevolutionRun._resolve_king_phase_move = (
        _ghost_layered_resolve_king_phase_move
    )
    GhostRevolutionRun._resolve_elite_knight_move = (
        _ghost_layered_resolve_elite_knight_move
    )
    GhostRevolutionRun.resolve_king_fight_move = (
        _ghost_layered_resolve_king_fight_move
    )
    GhostRevolutionRun.king_fight_opponent_observation = (
        _ghost_layered_observation
    )
    GhostRevolutionRun.king_fight_status = (
        _ghost_layered_status
    )
    GhostRevolutionRun.king_fight_opponent_public_tell = (
        _ghost_layered_public_tell
    )
    GhostRevolutionRun.apply_king_fight_opponent_intent = (
        _ghost_layered_apply_opponent_intent
    )

    from .symmetric_combat import install_symmetric_combat

    install_symmetric_combat(GhostRevolutionRun)
