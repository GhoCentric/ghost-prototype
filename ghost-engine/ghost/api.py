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
    GHOST_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS,
    GHOST_VERSION,
    GhostEngine,
)
from .relationships import RelationshipGraph
from copy import deepcopy

from .events import (
    normalize_event,
    normalize_game_action,
)
from .ids import normalize_pair_ids
from .validation import (
    validate_finite_number,
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
from .threat_response import (
    evaluate_threat_response as _evaluate_threat_response,
)
from .policies import (
    CommercePolicy,
    LawPolicy,
    PricingPolicy,
    ReintegrationPolicy,
)
from .world import WorldRuntime
from .epistemic import EpistemicRuntime
from .emotions import EmotionRuntime
from .objectives import (
    build_combat_objective_packet,
)
from .combat import (
    advance_combat_initiative_packet,
    lock_combat_recovery_read_packet,
    resolve_combat_recovery_packet,
)


# -----------------------------
# DEFAULT EVENT MAP
# -----------------------------
# Keep one private authoritative template. DEFAULT_EVENT_MAP remains a
# copied compatibility export, so external mutation cannot alter future
# GhostAPI instances.
_DEFAULT_EVENT_MAP_TEMPLATE = (
    RelationshipGraph.public_event_map()
)

DEFAULT_EVENT_MAP = deepcopy(
    _DEFAULT_EVENT_MAP_TEMPLATE
)


def _fresh_default_event_map() -> dict:
    return deepcopy(
        _DEFAULT_EVENT_MAP_TEMPLATE
    )


_GHOST_API_SNAPSHOT_REQUIRED_KEYS = {
    "engine",
    "schema_version",
    "world",
}


_GHOST_API_SNAPSHOT_OPTIONAL_KEYS = {
    "emotions",
    "epistemic",
    "event_map",
    "ghost_version",
    "transitions",
}


def _api_snapshot_json_value(
    value,
    label: str,
):
    if value is None:
        return

    if isinstance(
        value,
        (
            str,
            bool,
            int,
        ),
    ):
        return

    if isinstance(value, float):
        validate_finite_number(
            value,
            label,
        )

        return

    if isinstance(value, list):
        for index, item in enumerate(value):
            _api_snapshot_json_value(
                item,
                f"{label}[{index}]",
            )

        return

    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(
                    f"{label} keys must be strings"
                )

            _api_snapshot_json_value(
                item,
                f"{label}.{key}",
            )

        return

    raise ValueError(
        f"{label} must be JSON-safe"
    )


def _validate_snapshot_event_map(
    event_map,
) -> dict | None:
    if event_map is None:
        return None

    if not isinstance(event_map, dict):
        raise ValueError(
            "snapshot event_map must be a dict"
        )

    validated = {}

    for event_name, deltas in (
        event_map.items()
    ):
        if (
            not isinstance(event_name, str)
            or not event_name.strip()
        ):
            raise ValueError(
                "snapshot event_map names "
                "must be non-empty strings"
            )

        if not isinstance(deltas, dict):
            raise ValueError(
                "snapshot event_map entries "
                "must be dicts"
            )

        validated_deltas = {}

        for key, value in deltas.items():
            if (
                not isinstance(key, str)
                or not key.strip()
            ):
                raise ValueError(
                    "snapshot event_map delta names "
                    "must be non-empty strings"
                )

            validated_deltas[key] = (
                validate_finite_number(
                    value,
                    (
                        "snapshot event_map delta "
                        f"{event_name}.{key}"
                    ),
                )
            )

        validated[event_name] = (
            validated_deltas
        )

    return validated


class GhostAPI:
    """
    High-level public integration surface for Ghost.

    Use GhostAPI for normal external integrations, demos, gameplay
    prototypes, adapters, and JSON-friendly event packets.

    Use GhostEngine directly only when lower-level engine access is needed.
    """

    def __init__(
        self,
        config: dict | None = None,
        event_map: dict | None = None,
    ):
        """
        Construct a fresh high-level runtime.

        Caller-owned configuration is copied at the boundary. Snapshot
        restoration is intentionally separate and must use
        GhostAPI.from_snapshot().
        """
        if config is not None and not isinstance(
            config,
            dict,
        ):
            raise ValueError(
                "config must be a dict or None"
            )

        validated_event_map = (
            _fresh_default_event_map()
            if event_map is None
            else _validate_snapshot_event_map(
                event_map
            )
        )

        self._bind_runtime(
            engine=GhostEngine(
                deepcopy(config)
                if config is not None
                else {}
            ),
            event_map=validated_event_map,
            world=WorldRuntime(),
            epistemic=EpistemicRuntime(),
            emotions=EmotionRuntime(),
        )

    def _bind_runtime(
        self,
        *,
        engine: GhostEngine,
        event_map: dict,
        world: WorldRuntime,
        epistemic: EpistemicRuntime,
        emotions: EmotionRuntime,
    ) -> None:
        """
        Attach already-constructed or already-restored runtime parts.

        Mutable configuration is copied so no caller, snapshot packet,
        or compatibility export shares live runtime configuration.
        """
        self.engine = engine
        self.event_map = deepcopy(event_map)
        self.world = world
        self.epistemic = epistemic
        self.emotions = emotions

        # Patch 7 retires the inert pre-v1.8 transition cache. Remove it
        # when rebinding an object created by older code in the same
        # process. Legacy snapshot packets are still accepted below.
        self.__dict__.pop(
            "_transitions",
            None,
        )

        self.commerce = CommercePolicy()
        self.pricing = PricingPolicy()
        self.law = LawPolicy()
        self.reintegration = (
            ReintegrationPolicy()
        )

    @classmethod
    def from_snapshot(
        cls,
        snapshot: dict,
    ) -> "GhostAPI":
        """
        Restore a complete GhostAPI runtime from a validated snapshot.

        Older supported packets may omit ghost_version, event_map,
        transitions, epistemic, or emotions. Unknown packet fields are rejected.
        Restoration bypasses __init__ and preserves the construction /
        restoration split established by the prior patch.
        """
        if not isinstance(snapshot, dict):
            raise ValueError(
                "snapshot must be a dict"
            )

        keys = set(snapshot)

        allowed = (
            _GHOST_API_SNAPSHOT_REQUIRED_KEYS
            | _GHOST_API_SNAPSHOT_OPTIONAL_KEYS
        )

        unknown = keys - allowed

        if unknown:
            raise ValueError(
                "snapshot has unsupported keys: "
                + ", ".join(sorted(unknown))
            )

        missing = (
            _GHOST_API_SNAPSHOT_REQUIRED_KEYS
            - keys
        )

        if missing:
            raise ValueError(
                "snapshot is missing required keys: "
                + ", ".join(sorted(missing))
            )

        _api_snapshot_json_value(
            snapshot,
            "snapshot",
        )

        schema_version = snapshot[
            "schema_version"
        ]

        if (
            schema_version
            not in GHOST_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS
        ):
            raise ValueError(
                "unsupported GhostAPI snapshot "
                "schema version: "
                f"{schema_version!r}"
            )

        ghost_version = snapshot.get(
            "ghost_version"
        )

        if ghost_version is not None:
            if (
                not isinstance(ghost_version, str)
                or not ghost_version.strip()
            ):
                raise ValueError(
                    "snapshot ghost_version must be "
                    "a non-empty string"
                )

        engine_snapshot = snapshot[
            "engine"
        ]

        world_snapshot = snapshot[
            "world"
        ]

        if not isinstance(
            engine_snapshot,
            dict,
        ):
            raise ValueError(
                "snapshot engine must be a dict"
            )

        if not isinstance(
            world_snapshot,
            dict,
        ):
            raise ValueError(
                "snapshot world must be a dict"
            )

        event_map = (
            _validate_snapshot_event_map(
                snapshot.get(
                    "event_map"
                )
            )
        )

        legacy_transitions = snapshot.get(
            "transitions"
        )

        if legacy_transitions is not None:
            if not isinstance(
                legacy_transitions,
                dict,
            ):
                raise ValueError(
                    "snapshot transitions must be a dict"
                )

            _api_snapshot_json_value(
                legacy_transitions,
                "snapshot transitions",
            )

        if "epistemic" in snapshot:
            epistemic_snapshot = (
                snapshot["epistemic"]
            )

            if not isinstance(
                epistemic_snapshot,
                dict,
            ):
                raise ValueError(
                    "snapshot epistemic "
                    "must be a dict"
                )
        else:
            epistemic_snapshot = None

        if "emotions" in snapshot:
            emotions_snapshot = snapshot["emotions"]
            if not isinstance(
                emotions_snapshot,
                dict,
            ):
                raise ValueError(
                    "snapshot emotions must be a dict"
                )
        else:
            emotions_snapshot = None

        api = cls.__new__(
            cls
        )

        api._bind_runtime(
            engine=GhostEngine.from_snapshot(
                deepcopy(
                    engine_snapshot
                )
            ),
            event_map=(
                event_map
                if event_map is not None
                else _fresh_default_event_map()
            ),
            world=WorldRuntime.from_dict(
                deepcopy(
                    world_snapshot
                )
            ),
            epistemic=(
                EpistemicRuntime.from_snapshot(
                    deepcopy(
                        epistemic_snapshot
                    )
                )
                if epistemic_snapshot is not None
                else EpistemicRuntime()
            ),
            emotions=(
                EmotionRuntime.from_snapshot(
                    deepcopy(
                        emotions_snapshot
                    )
                )
                if emotions_snapshot is not None
                else EmotionRuntime()
            ),
        )

        return api

    def restore_snapshot(self, snapshot: dict) -> dict:
        """
        Restore this API instance in-place from snapshot() output.

        Returns the restored JSON-safe public snapshot.
        """
        restored = self.from_snapshot(snapshot)

        self._bind_runtime(
            engine=restored.engine,
            event_map=restored.event_map,
            world=restored.world,
            epistemic=restored.epistemic,
            emotions=restored.emotions,
        )

        return self.snapshot()

    # -----------------------------
    # CORE METHOD
    # -----------------------------
    def apply_event(
        self,
        source: str,
        target: str,
        event: dict,
    ):
        source, target = normalize_pair_ids(
            source,
            target,
        )

        if not isinstance(event, dict):
            raise ValueError(
                "Event must be a dict"
            )

        event_type = normalize_game_action(
            event.get("type")
        )

        intensity = validate_unit_interval(
            event.get(
                "intensity",
                1.0,
            ),
            "event intensity",
        )

        if event_type not in self.event_map:
            raise ValueError(
                f"Unknown event type: {event_type}"
            )

        base_deltas = deepcopy(
            self.event_map[event_type]
        )

        if not isinstance(base_deltas, dict):
            raise ValueError(
                "event map entries must be dicts"
            )

        for key, value in base_deltas.items():
            validate_finite_number(
                value,
                f"event map delta {key}",
            )

        default_deltas = (
            _DEFAULT_EVENT_MAP_TEMPLATE.get(
                event_type
            )
        )

        is_default_event = (
            default_deltas is not None
            and base_deltas == default_deltas
        )

        relationship = self.engine.apply_event(
            source,
            target,
            event_type,
            intensity=intensity,
            event_spec=(
                None
                if is_default_event
                else base_deltas
            ),
        )

        diagnostics = (
            relationship.get(
                "diagnostics"
            )
            or {}
        )

        scaled_deltas = {
            key: value * intensity
            for key, value in (
                base_deltas.items()
            )
        }

        if "trust" in scaled_deltas:
            scaled_deltas["trust"] = (
                diagnostics.get(
                    "delta",
                    scaled_deltas["trust"],
                )
            )

        return {
            "source": source,
            "target": target,
            "event": {
                "type": event_type,
                "intensity": intensity,
            },
            "deltas": scaled_deltas,
            "mode": (
                "canonical_relationship_event"
                if is_default_event
                else "configured_relationship_event"
            ),
            "relationship": relationship,
            "trust": relationship.get(
                "trust"
            ),
            "state": relationship.get(
                "state"
            ),
            "transition": deepcopy(
                relationship.get(
                    "transition"
                )
            ),
            "trigger": deepcopy(
                relationship.get(
                    "trigger"
                )
            ),
            "diagnostics": deepcopy(
                relationship.get(
                    "diagnostics"
                )
            ),
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

        event_type = normalize_game_action(event.get("type"))
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

        epistemic = self.epistemic.tick()

        return {
            "event": "tick",
            "relationships": relationships.get("relationships", []),
            "world": self.world.to_dict(),
            "epistemic": epistemic,
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
    # EPISTEMIC STATE v1.8.0
    # -----------------------------
    def record_fact(
        self,
        fact_id: str,
        source: str,
        subject: str,
        predicate: str,
        object: str,
        attributes: dict | None = None,
    ) -> dict:
        """Record objective truth without exposing it automatically."""
        return self.epistemic.record_fact(
            fact_id=fact_id,
            source=source,
            subject=subject,
            predicate=predicate,
            object=object,
            attributes=attributes,
        )

    def get_fact(
        self,
        fact_id: str,
    ) -> dict | None:
        """
        Return objective runtime truth for an integration layer.

        Calling this does not imply an in-world actor knows the fact.
        """
        return self.epistemic.get_fact(fact_id)

    def observe(
        self,
        observer: str,
        kind: str,
        visible_features: list[str] | tuple[str, ...],
        reliability: float,
        provenance: dict | None = None,
        subject: str | None = None,
    ) -> dict:
        """Record what one actor observed or received."""
        return self.epistemic.observe(
            observer=observer,
            kind=kind,
            visible_features=visible_features,
            reliability=reliability,
            provenance=provenance,
            subject=subject,
        )

    def report(
        self,
        speaker: str,
        audience: str | list[str] | tuple[str, ...] | set[str],
        claim: dict,
        confidence: float,
        source_belief_id: str | None = None,
        provenance: dict | None = None,
    ) -> dict:
        """
        Record a communicated claim.

        A report is not objective truth and does not force belief.
        """
        return self.epistemic.report(
            speaker=speaker,
            audience=audience,
            claim=claim,
            confidence=confidence,
            source_belief_id=source_belief_id,
            provenance=provenance,
        )

    def add_evidence(
        self,
        evidence_type: str,
        source: str,
        supports: dict | None = None,
        contradicts: dict | None = None,
        subject: str | None = None,
        available_to: (
            str
            | list[str]
            | tuple[str, ...]
            | set[str]
            | None
        ) = None,
        provenance: dict | None = None,
    ) -> dict:
        """Append evidence without silently revising beliefs."""
        return self.epistemic.add_evidence(
            evidence_type=evidence_type,
            source=source,
            supports=supports,
            contradicts=contradicts,
            subject=subject,
            available_to=available_to,
            provenance=provenance,
        )

    def evaluate_beliefs(
        self,
        holder: str,
        subject: str,
        candidates: dict | None = None,
        evidence_ids: list[str] | tuple[str, ...] | None = None,
        report_quality: dict | None = None,
        previous_belief_id: str | None = None,
        provenance: dict | None = None,
    ) -> dict:
        """Create or explicitly revise one actor-owned belief packet."""
        return self.epistemic.evaluate_beliefs(
            holder=holder,
            subject=subject,
            candidates=candidates,
            evidence_ids=evidence_ids,
            report_quality=report_quality,
            previous_belief_id=previous_belief_id,
            provenance=provenance,
        )

    def get_belief(
        self,
        holder: str,
        subject: str,
    ) -> dict | None:
        """Return one holder's latest belief for one subject."""
        return self.epistemic.get_belief(
            holder,
            subject,
        )

    def propagate_belief(
        self,
        speaker: str,
        audience: str | list[str] | tuple[str, ...] | set[str],
        belief_id: str,
        confidence: float | None = None,
        provenance: dict | None = None,
    ) -> dict:
        """
        Turn a speaker-owned belief into a report.

        Recipients receive the claim, not automatic belief.
        """
        return self.epistemic.propagate_belief(
            speaker=speaker,
            audience=audience,
            belief_id=belief_id,
            confidence=confidence,
            provenance=provenance,
        )

    # -----------------------------
    # MULTI-EMOTION STATE v1.9.2
    # -----------------------------
    def register_emotional_agent(
        self,
        agent: str,
        initial: dict | None = None,
        baseline: dict | None = None,
        sensitivities: dict | None = None,
        inertia: dict | None = None,
        salience_bias: dict | None = None,
        spotlight_switch_margin: float | None = None,
    ) -> dict:
        """Register or configure independent bounded emotional channels."""
        return self.emotions.register_agent(
            agent=agent,
            initial=initial,
            baseline=baseline,
            sensitivities=sensitivities,
            inertia=inertia,
            salience_bias=salience_bias,
            spotlight_switch_margin=spotlight_switch_margin,
        )

    def emotional_state(
        self,
        agent: str,
    ) -> dict | None:
        """Return copied emotional levels, salience, and history for one agent."""
        return self.emotions.get_state(agent)

    def emotional_event_profiles(self) -> dict:
        """Return copied deterministic base impulse profiles."""
        return self.emotions.event_profiles()

    def configure_emotional_event(
        self,
        event: str,
        impulses: dict,
    ) -> dict:
        """Replace one event's explicit signed emotional impulse profile."""
        return self.emotions.configure_event_profile(
            event,
            impulses,
        )

    def apply_emotional_event(
        self,
        agent: str,
        event: str,
        intensity: float = 1.0,
        source: str | None = None,
        context_modifiers: dict | None = None,
        impulse_overrides: dict | None = None,
    ) -> dict:
        """
        Apply one deterministic emotional impulse without choosing an action.

        Levels remain independently bounded in [0, 1]. Event impulses are
        explicit signed inputs; sensitivity and context scale the impulse,
        saturation limits the resulting level, and salience only exposes
        current attention pressure.
        """
        return self.emotions.apply_event(
            agent=agent,
            event=event,
            intensity=intensity,
            source=source,
            context_modifiers=context_modifiers,
            impulse_overrides=impulse_overrides,
        )

    def tick_emotions(
        self,
        agent: str | None = None,
        steps: int = 1,
    ) -> dict:
        """Decay emotional levels toward per-channel baselines via inertia."""
        return self.emotions.tick(
            agent=agent,
            steps=steps,
        )

    def apply_layered_event(
        self,
        source: str,
        target: str,
        event: dict,
        emotion_context: dict | None = None,
        emotion_impulses: dict | None = None,
    ) -> dict:
        """
        Atomically apply one event to relationship state and target emotions.

        This is the explicit bridge between the existing relationship layer
        and the new independent emotional layer. Ghost still does not choose
        the target's action.
        """
        checkpoint = self.snapshot()
        try:
            relationship_packet = self.apply_event(
                source,
                target,
                event,
            )
            resolved_event = relationship_packet["event"]
            emotion_packet = self.apply_emotional_event(
                agent=target,
                event=resolved_event["type"],
                intensity=resolved_event["intensity"],
                source=source,
                context_modifiers=emotion_context,
                impulse_overrides=emotion_impulses,
            )
        except Exception:
            self.restore_snapshot(checkpoint)
            raise

        emotional_state = emotion_packet["state"]
        return {
            "source": relationship_packet["source"],
            "target": relationship_packet["target"],
            "event": deepcopy(relationship_packet["event"]),
            "relationship": relationship_packet,
            "emotions": emotion_packet,
            "layered_state": {
                "trust": relationship_packet.get("trust"),
                "relationship_state": relationship_packet.get("state"),
                "emotional_levels": deepcopy(
                    emotional_state["levels"]
                ),
                "dominant_emotion": emotional_state.get(
                    "dominant_emotion"
                ),
                "dominant_salience": emotional_state.get(
                    "dominant_salience"
                ),
                "raw_leader_emotion": emotional_state.get(
                    "raw_leader_emotion"
                ),
                "raw_leader_salience": emotional_state.get(
                    "raw_leader_salience"
                ),
                "spotlight_switch_margin": emotional_state.get(
                    "spotlight_switch_margin"
                ),
            },
        }

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

    def evaluate_threat_response(
        self,
        npc: str,
        relationship: dict,
        temperament="calm",
        context: dict | None = None,
    ) -> dict:
        """
        Read-only deterministic threat-response recommendation.

        Ghost does not execute the response. A game or simulation layer
        decides how to animate, schedule, or apply it.
        """
        return _evaluate_threat_response(
            npc=npc,
            relationship=relationship,
            temperament=temperament,
            context=context,
        )

    def evaluate_npc_threat_response(
        self,
        npc: str,
        source: str,
        target: str,
        temperament="calm",
        context: dict | None = None,
    ) -> dict:
        """
        Read a live Ghost relationship, then evaluate a deterministic
        threat-response recommendation for one NPC.
        """
        relationship = self.engine.get_relationship(
            source,
            target,
        )

        return self.evaluate_threat_response(
            npc=npc,
            relationship=relationship,
            temperament=temperament,
            context=context,
        )

    # -----------------------------
    # STRATEGIC OBJECTIVE CONTRACTS
    # -----------------------------
    def build_combat_objective(
        self,
        *,
        actor: str,
        target: str,
        actor_health: int,
        actor_max_health: int,
        target_health: int,
        target_max_health: int,
        turns_remaining: int,
        expected_damage_per_success: int,
        deadline_label: str = "the deadline",
    ) -> dict:
        """
        Build a deterministic fight-level objective packet.

        Ghost defines the objective and tactical horizon. An external
        policy may propose a legal tactic, but Ghost remains authoritative
        for validation, state mutation, consequences, and terminal state.
        """
        return build_combat_objective_packet(
            actor=actor,
            target=target,
            actor_health=actor_health,
            actor_max_health=(
                actor_max_health
            ),
            target_health=target_health,
            target_max_health=(
                target_max_health
            ),
            turns_remaining=turns_remaining,
            expected_damage_per_success=(
                expected_damage_per_success
            ),
            deadline_label=deadline_label,
        )

    def advance_combat_initiative(
        self,
        *,
        previous_state: str,
        event: str,
    ) -> dict:
        """Advance one deterministic Ghost-owned initiative state."""
        return advance_combat_initiative_packet(
            previous_state=previous_state,
            event=event,
        )

    def lock_combat_recovery_read(
        self,
        *,
        selection_key: str,
        proposed_move: str | None,
        fallback_move: str = "dodge",
    ) -> dict:
        """Validate and lock a hidden forced-recovery prediction."""
        return lock_combat_recovery_read_packet(
            selection_key=selection_key,
            proposed_move=proposed_move,
            fallback_move=fallback_move,
        )

    def resolve_combat_recovery(
        self,
        *,
        read_packet: dict,
        player_move: str,
        light_damage: int = 1,
    ) -> dict:
        """Resolve a locked recovery read without randomness."""
        return resolve_combat_recovery_packet(
            read_packet=read_packet,
            player_move=player_move,
            light_damage=light_damage,
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

    def propagate_social_event(
        self,
        source: str,
        target: str,
        event: str,
        observers: list[str] | tuple[str, ...] | None = None,
        weights: dict[str, float] | None = None,
        intensity: float = 1.0,
    ) -> dict:
        """
        Apply a direct relationship event and propagate bounded
        secondary effects to observers.

        Returns the v1.6 social propagation packet consumed by
        interpret_social_packet().
        """
        event = normalize_game_action(event)
        intensity = validate_unit_interval(
            intensity,
            "social event intensity",
        )

        return self.engine.propagate_social_event(
            source=source,
            target=target,
            event=event,
            observers=observers,
            weights=weights,
            intensity=intensity,
        )

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

        The packet contains all state required by from_snapshot() to
        restore a deterministic GhostAPI runtime.
        """
        packet = {
            "ghost_version": GHOST_VERSION,
            "schema_version": GHOST_SNAPSHOT_SCHEMA_VERSION,
            "engine": self.engine.snapshot(),
            "world": self.world.to_dict(),
            "epistemic": self.epistemic.snapshot(),
            "event_map": deepcopy(self.event_map),
        }
        if self.emotions.has_state():
            packet["emotions"] = self.emotions.snapshot()
        return packet
