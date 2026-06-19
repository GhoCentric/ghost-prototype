"""
Public API layer for ghocentric-ghost-engine.

GhostAPI is the high-level integration surface for external developers,
demos, adapters, and gameplay prototypes.

GhostEngine remains the lower-level deterministic state runtime.

v1.7.1 public API cleanup focus:
- GhostAPI wraps GhostEngine as the normal external entry point.
- GhostEngine remains available for lower-level engine access and tests.
- Raw strings and typed public constants both remain supported.
- apply_event() returns structured public relationship packets.
- tick() returns a public packet for relationship and world time.
- state() returns live mutable engine state for debugging only.
- snapshot() returns a JSON-safe copied public snapshot with metadata.
- Temperament interpretation is stateless and read-only.
- Optional policy, governance, world, and LLM adapter helpers remain
  subordinate to deterministic state.

Ghost does not choose actions.
Ghost does not generate dialogue.
Ghost does not invent world state.

Ghost exposes deterministic social, emotional, diagnostic, and
interpretive state.
"""


from .engine import (
    GHOST_SNAPSHOT_SCHEMA_VERSION,
    GHOST_VERSION,
    GhostEngine,
)
from .events import normalize_event
from .ids import normalize_pair_ids
from .validation import (
    validate_non_negative_finite,
    validate_unit_interval,
)
from .governance import (
    assess_effects,
    assess_intent,
    assess_player_claim,
    build_stance_packet,
    evaluate_governance,
)
from .llm_adapter import build_voice_contract_prompt, fallback_from_stance
from .temperament import (
    interpret_relationship as _interpret_relationship_packet,
    interpret_social_packet as _interpret_social_packet,
)
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
    """
    High-level public integration surface for Ghost.

    Use GhostAPI for normal external integrations, demos, gameplay
    prototypes, adapters, and JSON-friendly event packets.

    Use GhostEngine directly only when lower-level engine access is needed.
    """

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

        # Policy/runtime modules
        self.commerce = CommercePolicy()
        self.pricing = PricingPolicy()
        self.law = LawPolicy()
        self.reintegration = ReintegrationPolicy()
        self.world = WorldRuntime()

    # -----------------------------
    # CORE METHOD
    # -----------------------------
    def apply_event(self, source: str, target: str, event: dict):
        source, target = normalize_pair_ids(source, target)

        if not isinstance(event, dict):
            raise ValueError("Event must be a dict")

        event_type = normalize_event(event.get("type"))
        intensity = validate_unit_interval(
            event.get("intensity", 1.0),
            "event intensity",
        )

        if event_type not in self.event_map:
            raise ValueError(f"Unknown event type: {event_type}")

        base_deltas = self.event_map[event_type]
        scaled_deltas = {
            k: v * intensity for k, v in base_deltas.items()
        }

        if event_type in self.engine.relationships.RELATIONSHIP_EVENT_MAP:
            relationship = self.engine.apply_event(
                source,
                target,
                event_type,
                intensity=intensity,
            )
            mode = "canonical_relationship_event"
        else:
            self.engine.relationships.apply_delta(
                source,
                target,
                scaled_deltas,
            )
            relationship = self.engine.get_relationship(source, target)
            mode = "legacy_delta_event"

        return {
            "source": source,
            "target": target,
            "event": {
                "type": event_type,
                "intensity": intensity,
            },
            "deltas": scaled_deltas,
            "mode": mode,
            "relationship": relationship,
            "trust": relationship.get("trust"),
            "state": relationship.get("state"),
            "transition": relationship.get("transition"),
            "trigger": relationship.get("trigger"),
            "diagnostics": relationship.get("diagnostics"),
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
        source, target = normalize_pair_ids(source, target)

        if not isinstance(event, dict):
            raise ValueError("Event must be a dict")

        event_type = normalize_event(event.get("type"))
        intensity = validate_unit_interval(
            event.get("intensity", 1.0),
            "event intensity",
        )
        heat = validate_non_negative_finite(heat, "heat")

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

        Returns a public packet so GhostAPI matches the readable
        tick behavior exposed by GhostEngine.
        """
        relationships = self.engine.tick()

        self.world.tick()

        return {
            "event": "tick",
            "relationships": relationships.get("relationships", []),
            "world": self.world.to_dict(),
        }

    def step(self, step_data: dict | None = None):
        """
        Pass-through to the underlying GhostEngine step() method.
        Useful for demos and direct engine-style interaction.
        """
        return self.engine.step(step_data)

    def state(self):
        """
        Return the live mutable engine state.

        This is useful for debugging and controlled inspection, but it is
        not a safe persistence or adapter boundary. External integrations
        should use snapshot() when they need JSON-safe copied state.
        """
        return self.engine.state()
    # -----------------------------
    # STATELESS TEMPERAMENT INTERPRETATION
    # -----------------------------
    def interpret_relationship_packet(
        self,
        npc: str,
        relationship: dict,
        temperament="calm",
    ) -> dict:
        """
        Interpret an existing relationship packet through an NPC temperament.

        This is read-only.
        It does not mutate Ghost relationship state.
        """
        return _interpret_relationship_packet(
            npc=npc,
            relationship=relationship,
            temperament=temperament,
        )

    def interpret_npc_relationship(
        self,
        npc: str,
        source: str,
        target: str,
        temperament="calm",
    ) -> dict:
        """
        Read a relationship from the engine and interpret it
        through an NPC temperament.
        """
        relationship = self.engine.get_relationship(
            source,
            target,
        )

        return self.interpret_relationship_packet(
            npc=npc,
            relationship=relationship,
            temperament=temperament,
        )

    def interpret_social_packet(
        self,
        npc: str,
        packet: dict,
        temperament="calm",
    ) -> dict:
        """
        Interpret a v1.6.0 social propagation packet for one observer.
        """
        return _interpret_social_packet(
            npc=npc,
            packet=packet,
            temperament=temperament,
        )

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
        """
        Return the canonical engine relationship packet.

        GhostAPI uses GhostEngine as the single source of truth.
        """
        return self.engine.get_relationship(a, b)

    def snapshot(self):
        """
        Return a JSON-safe copied public snapshot.

        GhostAPI.snapshot() is the safe external boundary for persistence,
        adapter contracts, save/load flows, and engine-facing integrations.

        The wrapped GhostEngine snapshot remains available under "engine".
        Top-level metadata is also exposed so adapter layers can version the
        public GhostAPI packet without digging into engine internals.
        """
        return {
            "ghost_version": GHOST_VERSION,
            "schema_version": GHOST_SNAPSHOT_SCHEMA_VERSION,
            "engine": self.engine.snapshot(),
            "world": self.world.to_dict(),
        }
