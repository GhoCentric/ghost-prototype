"""
Public API layer for ghocentric-ghost-engine.

This wraps internal systems into a clean, stable interface
for external developers.

v1.1.0 adds Governance Core:
- ClaimAssessment
- IntentAssessment
- EffectAssessment
- StancePacket
- Policy runtime access
- World / society runtime access
- Optional LLM adapter helpers
"""

from .engine import GhostEngine
from .governance import (
    assess_effects,
    assess_intent,
    assess_player_claim,
    build_stance_packet,
    evaluate_governance,
)
from .llm_adapter import build_voice_contract_prompt, fallback_from_stance
from .policies import (
    CommercePolicy,
    LawPolicy,
    PricingPolicy,
    ReintegrationPolicy,
)
from .world import WorldRuntime


# -----------------------------
# DEFAULT EVENT MAP
# -----------------------------
DEFAULT_EVENT_MAP = {
    "neutral": {"trust": 0.0},
    "greet": {"trust": +0.02, "attachment": +0.01},
    "help": {"trust": +0.2, "attachment": +0.05},
    "cooperate": {"trust": +0.08, "attachment": +0.02},
    "apology": {"trust": +0.05},
    "disengage": {"trust": +0.01},
    "pressure": {"trust": -0.08},
    "manipulate": {"trust": -0.10},
    "deceive": {"trust": -0.15},
    "insult": {"trust": -0.3},
    "threat": {"trust": -0.5},
    "theft": {"trust": -0.6, "attachment": -0.2},
    "betrayal": {"trust": -0.8, "attachment": -0.5},
}


class GhostAPI:

    # -----------------------------
    # RELATIONSHIP STATE THRESHOLDS
    # -----------------------------
    STATE_THRESHOLDS = {
        "hostile": -0.2,
        "unfriendly": -0.05,
        "neutral": 0.05,
        "friendly": 0.2,
        "loyal": 1.0,
    }

    def __init__(
        self,
        config: dict | None = None,
        event_map: dict | None = None,
    ):
        self.engine = GhostEngine(config or {})
        self._transitions = {}
        self.event_map = event_map or DEFAULT_EVENT_MAP

        # v1.1.0 policy/runtime modules
        self.commerce = CommercePolicy()
        self.pricing = PricingPolicy()
        self.law = LawPolicy()
        self.reintegration = ReintegrationPolicy()
        self.world = WorldRuntime()

    # -----------------------------
    # CORE METHOD
    # -----------------------------
    def apply_event(self, source: str, target: str, event: dict):
        if not isinstance(event, dict):
            raise ValueError("Event must be a dict")

        event_type = event.get("type")
        intensity = event.get("intensity", 1.0)

        if not isinstance(intensity, (int, float)):
            raise ValueError("Event intensity must be numeric")

        if event_type not in self.event_map:
            raise ValueError(f"Unknown event type: {event_type}")

        base_deltas = self.event_map[event_type]

        scaled_deltas = {
            k: v * intensity for k, v in base_deltas.items()
        }

        self.engine.relationships.apply_delta(source, target, scaled_deltas)

        return {
            "source": source,
            "target": target,
            "event": {
                "type": event_type,
                "intensity": intensity,
            },
            "deltas": scaled_deltas,
        }

    def propagate_event(
        self,
        source: str,
        target: str,
        event: dict,
        network: list[str],
        heat: int = 0,
    ):
        """
        Apply an event to a target and propagate scaled effects
        across a network of agents.
        """
        if not isinstance(event, dict):
            raise ValueError("Event must be a dict")

        event_type = event.get("type")
        intensity = event.get("intensity", 1.0)

        if event_type not in self.event_map:
            raise ValueError(f"Unknown event type: {event_type}")

        applied = []

        applied.append(
            self.apply_event(source, target, event)
        )

        if heat <= 0:
            return applied

        if heat <= 2:
            spread = 0.15
        elif heat <= 4:
            spread = 0.3
        else:
            spread = 0.6

        for npc in network:
            if npc == target:
                continue

            applied.append(
                self.apply_event(
                    source,
                    npc,
                    {
                        "type": event_type,
                        "intensity": intensity * spread,
                    },
                )
            )

        return applied

    def tick(self):
        """
        Advance time for relationships and world state.
        """
        self.engine.relationships.tick()
        self.world.tick()

    def step(self, step_data: dict | None = None):
        """
        Pass-through to the underlying GhostEngine step() method.
        Useful for demos and direct engine-style interaction.
        """
        return self.engine.step(step_data)

    def state(self):
        """
        Return the live engine state.
        """
        return self.engine.state()

    # -----------------------------
    # GOVERNANCE CORE v1.1.0
    # -----------------------------
    def assess_claim(
        self,
        text: str,
        verified_world_state: dict | None = None,
    ) -> dict:
        return assess_player_claim(
            text,
            verified_world_state,
        ).to_dict()

    def assess_intent(self, text: str) -> dict:
        return assess_intent(text).to_dict()

    def assess_effects(
        self,
        claim: dict,
        intent: dict,
    ) -> dict:
        """
        Accepts dicts so public users do not need dataclass objects.
        """
        from .governance import ClaimAssessment, IntentAssessment

        claim_obj = ClaimAssessment(
            claim_type=claim.get("claim_type", "none"),
            verified=claim.get("verified", True),
            attempted_state_override=claim.get(
                "attempted_state_override",
                False,
            ),
            severity=claim.get("severity", 0.0),
            npc_stance=claim.get("npc_stance", "normal"),
            allowed_effects=tuple(claim.get("allowed_effects", ())),
            blocked_effects=tuple(claim.get("blocked_effects", ())),
            evidence=claim.get("evidence", {}),
        )

        intent_obj = IntentAssessment(
            intent_type=intent.get("intent_type", "ordinary_speech"),
            severity=intent.get("severity", 0.0),
            pressure=intent.get("pressure", 0.0),
            escalation=intent.get("escalation", "none"),
            clean_exit=intent.get("clean_exit", False),
            clean_acceptance=intent.get("clean_acceptance", False),
            evidence=intent.get("evidence", {}),
        )

        return assess_effects(claim_obj, intent_obj).to_dict()

    def build_stance(
        self,
        claim: dict,
        intent: dict,
        effects: dict,
        facts: dict | None = None,
    ) -> dict:
        from .governance import (
            ClaimAssessment,
            EffectAssessment,
            IntentAssessment,
        )

        claim_obj = ClaimAssessment(
            claim_type=claim.get("claim_type", "none"),
            verified=claim.get("verified", True),
            attempted_state_override=claim.get(
                "attempted_state_override",
                False,
            ),
            severity=claim.get("severity", 0.0),
            npc_stance=claim.get("npc_stance", "normal"),
            allowed_effects=tuple(claim.get("allowed_effects", ())),
            blocked_effects=tuple(claim.get("blocked_effects", ())),
            evidence=claim.get("evidence", {}),
        )

        intent_obj = IntentAssessment(
            intent_type=intent.get("intent_type", "ordinary_speech"),
            severity=intent.get("severity", 0.0),
            pressure=intent.get("pressure", 0.0),
            escalation=intent.get("escalation", "none"),
            clean_exit=intent.get("clean_exit", False),
            clean_acceptance=intent.get("clean_acceptance", False),
            evidence=intent.get("evidence", {}),
        )

        effects_obj = EffectAssessment(
            allowed_effects=tuple(effects.get("allowed_effects", ())),
            blocked_effects=tuple(effects.get("blocked_effects", ())),
            ghost_event=effects.get("ghost_event", {}),
            world_effects=effects.get("world_effects", {}),
            notes=tuple(effects.get("notes", ())),
        )

        return build_stance_packet(
            claim_obj,
            intent_obj,
            effects_obj,
            facts,
        ).to_dict()

    def evaluate_governance(
        self,
        text: str,
        verified_world_state: dict | None = None,
        facts: dict | None = None,
    ) -> dict:
        return evaluate_governance(
            text,
            verified_world_state,
            facts,
        )

    def process_player_text(
        self,
        source: str,
        target: str,
        text: str,
        verified_world_state: dict | None = None,
        facts: dict | None = None,
        apply: bool = True,
    ) -> dict:
        """
        Full v1.1.0 pipeline.

        text
        -> claim assessment
        -> intent assessment
        -> effect assessment
        -> stance packet
        -> optional Ghost relationship event
        -> optional world effects
        """
        result = self.evaluate_governance(
            text=text,
            verified_world_state=verified_world_state,
            facts=facts,
        )

        effects = result["effects"]
        ghost_event = effects.get("ghost_event", {})
        world_effects = effects.get("world_effects", {})

        applied_event = None

        if apply and ghost_event:
            event_type = ghost_event.get("type")

            if event_type in self.event_map:
                applied_event = self.apply_event(
                    source,
                    target,
                    ghost_event,
                )

        if apply and world_effects:
            self.world.apply_effects(world_effects)

            self.world.record_event(
                "governance_effect",
                actor=source,
                target=target,
                details={
                    "text": text,
                    "claim_type": result["claim"].get("claim_type"),
                    "intent_type": result["intent"].get("intent_type"),
                    "world_effects": world_effects,
                },
            )

        result["applied_event"] = applied_event
        result["world"] = self.world.to_dict()

        return result

    # -----------------------------
    # POLICY RUNTIME v1.1.0
    # -----------------------------
    def evaluate_commerce(
        self,
        severity: float = 0.0,
        blacklisted: bool = False,
        town_status: str = "normal",
        claim_blocked_effects=(),
    ) -> dict:
        return self.commerce.evaluate_service(
            severity=severity,
            blacklisted=blacklisted,
            town_status=town_status,
            claim_blocked_effects=claim_blocked_effects,
        ).to_dict()

    def compute_price(
        self,
        item: str,
        base_price: int,
        relationship_state: str = "neutral",
        sale_access: str = "normal",
        economic_modifier: float = 1.0,
        severity: float = 0.0,
        prior_record: dict | None = None,
    ) -> dict:
        return self.pricing.compute_price(
            item=item,
            base_price=base_price,
            relationship_state=relationship_state,
            sale_access=sale_access,
            economic_modifier=economic_modifier,
            severity=severity,
            prior_record=prior_record,
        ).to_dict()

    def evaluate_law(
        self,
        severity: float,
        argument_pressure: int = 0,
        warning_count: int = 0,
        post_arrest_watch: int = 0,
        release_grace: int = 0,
    ) -> dict:
        return self.law.evaluate(
            severity=severity,
            argument_pressure=argument_pressure,
            warning_count=warning_count,
            post_arrest_watch=post_arrest_watch,
            release_grace=release_grace,
        ).to_dict()

    def evaluate_reintegration(
        self,
        served_punishment: bool,
        current_trust: float,
        arrest_count: int = 0,
        resistance_remaining: int = 0,
    ) -> dict:
        return self.reintegration.evaluate(
            served_punishment=served_punishment,
            current_trust=current_trust,
            arrest_count=arrest_count,
            resistance_remaining=resistance_remaining,
        ).to_dict()

    # -----------------------------
    # WORLD / SOCIETY RUNTIME v1.1.0
    # -----------------------------
    def record_world_event(
        self,
        event_type: str,
        actor: str = "",
        target: str = "",
        details: dict | None = None,
    ) -> dict:
        return self.world.record_event(
            event_type=event_type,
            actor=actor,
            target=target,
            details=details,
        )

    def apply_world_effects(self, effects: dict):
        self.world.apply_effects(effects)

        return self.world.to_dict()

    def propagate_social_effect(
        self,
        source_event: str,
        faction_heat: float = 0.0,
    ) -> dict:
        return self.world.propagate_social_effect(
            source_event=source_event,
            faction_heat=faction_heat,
        )

    def world_state(self) -> dict:
        return self.world.to_dict()

    # -----------------------------
    # LLM ADAPTER v1.1.0
    # -----------------------------
    def build_voice_prompt(
        self,
        stance_packet: dict,
        npc_profile: dict | None = None,
        recent_lines: list[str] | None = None,
    ) -> str:
        return build_voice_contract_prompt(
            stance_packet=stance_packet,
            npc_profile=npc_profile,
            recent_lines=recent_lines,
        )

    def fallback_line(
        self,
        stance_packet: dict,
        item: str = "item",
        price: int | None = None,
    ) -> str:
        return fallback_from_stance(
            stance_packet=stance_packet,
            item=item,
            price=price,
        )

    # -----------------------------
    # RELATIONSHIP READ STATE
    # -----------------------------
    def _clamp(self, value, min_v=-1.0, max_v=1.0):
        return max(min(value, max_v), min_v)

    def _get_state(self, trust: float) -> str:
        t = self.STATE_THRESHOLDS

        if trust <= t["hostile"]:
            return "hostile"
        elif trust <= t["unfriendly"]:
            return "unfriendly"
        elif trust <= t["neutral"]:
            return "neutral"
        elif trust <= t["friendly"]:
            return "friendly"
        else:
            return "loyal"

    def _detect_transition(self, a: str, b: str, new_state: str):
        key = f"{a}|{b}"

        prev = self._transitions.get(key)

        transition = None

        if prev is not None and prev != new_state:
            transition = (prev, new_state)

        self._transitions[key] = new_state

        return transition

    def _handle_transition(self, _a: str, _b: str, transition):
        if not transition:
            return None

        prev, new = transition

        if new == "hostile":
            return {
                "event": "relationship_broken",
                "from": prev,
                "to": new,
            }

        if prev == "hostile" and new != "hostile":
            return {
                "event": "deescalation",
                "from": prev,
                "to": new,
            }

        if new in ("friendly", "loyal") and prev in (
            "unfriendly",
            "neutral",
        ):
            return {
                "event": "forgiveness",
                "from": prev,
                "to": new,
            }

        return {
            "event": "state_shift",
            "from": prev,
            "to": new,
        }

    def get_relationship(self, a: str, b: str) -> dict:
        rel = self.engine.relationships.get(a, b)

        if rel is None:
            state = "neutral"

            transition = self._detect_transition(a, b, state)
            trigger = self._handle_transition(a, b, transition)

            return {
                "trust": 0.0,
                "attachment": 0.0,
                "stability": 0.0,
                "state": state,
                "transition": transition,
                "trigger": trigger,
            }

        trust = rel.get("trust", 0.0)
        attachment = rel.get("attachment", 0.0)

        trust = self._clamp(trust)
        attachment = self._clamp(attachment)

        stability = abs(trust)
        state = self._get_state(trust)

        transition = self._detect_transition(a, b, state)
        trigger = self._handle_transition(a, b, transition)

        return {
            "trust": trust,
            "attachment": attachment,
            "stability": stability,
            "state": state,
            "transition": transition,
            "trigger": trigger,
        }

    # -----------------------------
    # SNAPSHOT
    # -----------------------------
    def snapshot(self):
        return {
            "engine": self.engine.snapshot(),
            "world": self.world.to_dict(),
        }
