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

Ghost exposes deterministic social, emotional, diagnostic, interpretive,
and motive-pressure state.
"""


from .engine import (
    GHOST_SNAPSHOT_SCHEMA_VERSION,
    GHOST_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS,
    GHOST_VERSION,
    GhostEngine,
)
from .relationships import RelationshipGraph
from copy import deepcopy
from contextlib import contextmanager

from .events import (
    normalize_event,
    normalize_game_action,
)
from .ids import normalize_id, normalize_pair_ids
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
from .emotions import EmotionRuntime, DEFAULT_SPOTLIGHT_SWITCH_MARGIN
from .interpretation import InterpretationRuntime
from .attention import AttentionRuntime
from .continuity import ContinuityRuntime
from .continuity_optimization import (
    ContinuityOptimizationRuntime,
)
from .episode_store import EpisodeIntegrityError
from .salience_bridge import build_salience_bridge
from .agent import AgentRuntime, GhostAgent
from .perception import PerceptionRuntime
from .motives import MotiveRuntime, build_motive_signal_packet
from .affordances import AffordanceRuntime
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
    "agents",
    "perception",
    "motives",
    "affordances",
    "emotions",
    "epistemic",
    "interpretations",
    "attention",
    "continuity",
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


def _optional_snapshot_dict(snapshot: dict, key: str) -> dict | None:
    """Return one optional runtime packet after strict type validation."""
    if key not in snapshot:
        return None
    value = snapshot[key]
    if not isinstance(value, dict):
        raise ValueError(f"snapshot {key} must be a dict")
    return value


def _validate_api_snapshot_envelope(snapshot: dict) -> dict:
    """Validate the top-level GhostAPI packet without constructing runtimes."""
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be a dict")
    keys = set(snapshot)
    allowed = _GHOST_API_SNAPSHOT_REQUIRED_KEYS | _GHOST_API_SNAPSHOT_OPTIONAL_KEYS
    unknown = keys - allowed
    if unknown:
        raise ValueError(
            "snapshot has unsupported keys: " + ", ".join(sorted(unknown))
        )
    missing = _GHOST_API_SNAPSHOT_REQUIRED_KEYS - keys
    if missing:
        raise ValueError(
            "snapshot is missing required keys: " + ", ".join(sorted(missing))
        )
    _api_snapshot_json_value(snapshot, "snapshot")
    schema_version = snapshot["schema_version"]
    if schema_version not in GHOST_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS:
        raise ValueError(
            "unsupported GhostAPI snapshot schema version: "
            f"{schema_version!r}"
        )
    ghost_version = snapshot.get("ghost_version")
    if ghost_version is not None and (
        not isinstance(ghost_version, str) or not ghost_version.strip()
    ):
        raise ValueError("snapshot ghost_version must be a non-empty string")
    engine_snapshot = snapshot["engine"]
    world_snapshot = snapshot["world"]
    if not isinstance(engine_snapshot, dict):
        raise ValueError("snapshot engine must be a dict")
    if not isinstance(world_snapshot, dict):
        raise ValueError("snapshot world must be a dict")
    event_map = _validate_snapshot_event_map(snapshot.get("event_map"))
    legacy_transitions = snapshot.get("transitions")
    if legacy_transitions is not None:
        if not isinstance(legacy_transitions, dict):
            raise ValueError("snapshot transitions must be a dict")
        _api_snapshot_json_value(legacy_transitions, "snapshot transitions")
    return {
        "engine": engine_snapshot,
        "world": world_snapshot,
        "event_map": event_map,
        "epistemic": _optional_snapshot_dict(snapshot, "epistemic"),
        "emotions": _optional_snapshot_dict(snapshot, "emotions"),
        "interpretations": _optional_snapshot_dict(snapshot, "interpretations"),
        "attention": _optional_snapshot_dict(snapshot, "attention"),
        "agents": _optional_snapshot_dict(snapshot, "agents"),
        "perception": _optional_snapshot_dict(snapshot, "perception"),
        "motives": _optional_snapshot_dict(snapshot, "motives"),
        "affordances": _optional_snapshot_dict(snapshot, "affordances"),
    }


def _validate_continuity_restore_packet(snapshot: dict, episode_store):
    """Validate continuity persistence metadata and return restoration parts."""
    if "continuity" not in snapshot:
        return None, None, None
    packet = snapshot["continuity"]
    legacy_keys = frozenset({"runtime", "episode_archive"})
    optimized_keys = frozenset(
        {"runtime", "episode_archive", "history_archive", "optimization"}
    )
    packet_keys = frozenset(packet) if isinstance(packet, dict) else frozenset()
    if (
        not isinstance(packet, dict)
        or packet_keys not in {legacy_keys, optimized_keys}
        or not isinstance(packet["runtime"], dict)
    ):
        raise ValueError("snapshot continuity packet is invalid")
    archive_manifest = packet["episode_archive"]
    if archive_manifest is not None:
        if episode_store is None:
            raise EpisodeIntegrityError(
                "snapshot requires its matching durable episode archive"
            )
        episode_store.verify_manifest(deepcopy(archive_manifest))
    history_manifest = None
    optimization_packet = None
    if packet_keys == optimized_keys:
        history_manifest = packet["history_archive"]
        optimization_packet = packet["optimization"]
        if history_manifest is not None and not isinstance(history_manifest, dict):
            raise ValueError("snapshot continuity history archive is invalid")
        if not isinstance(optimization_packet, dict):
            raise ValueError("snapshot continuity optimization packet is invalid")
    return packet["runtime"], history_manifest, optimization_packet


def _restore_optional_runtime(runtime_type, packet):
    """Restore an optional runtime packet or construct its empty runtime."""
    if packet is None:
        return runtime_type()
    return runtime_type.from_snapshot(deepcopy(packet))


def _build_api_from_restore_parts(
    cls,
    parts: dict,
    continuity_snapshot: dict | None,
    *,
    episode_store,
    history_manifest,
    optimization_packet,
):
    """Construct a GhostAPI from already validated restoration parts."""
    api = cls.__new__(cls)
    api._bind_runtime(
        engine=GhostEngine.from_snapshot(deepcopy(parts["engine"])),
        event_map=(
            parts["event_map"]
            if parts["event_map"] is not None
            else _fresh_default_event_map()
        ),
        world=WorldRuntime.from_dict(deepcopy(parts["world"])),
        epistemic=_restore_optional_runtime(EpistemicRuntime, parts["epistemic"]),
        emotions=_restore_optional_runtime(EmotionRuntime, parts["emotions"]),
        interpretations=_restore_optional_runtime(
            InterpretationRuntime, parts["interpretations"]
        ),
        attention=_restore_optional_runtime(AttentionRuntime, parts["attention"]),
        agents=_restore_optional_runtime(AgentRuntime, parts["agents"]),
        perception=_restore_optional_runtime(PerceptionRuntime, parts["perception"]),
        motives=_restore_optional_runtime(MotiveRuntime, parts["motives"]),
        affordances=_restore_optional_runtime(AffordanceRuntime, parts["affordances"]),
        continuity=_restore_optional_runtime(ContinuityRuntime, continuity_snapshot),
        episode_store=episode_store,
        history_manifest=history_manifest,
        optimization_packet=optimization_packet,
    )
    return api


def _validate_restored_agent_layer_links(api) -> None:
    """Reject restored layer state that references missing agent identities."""
    for observer in api.perception.observer_ids():
        if not api.agents.has_agent(observer):
            raise ValueError(
                "snapshot perception observer must reference a registered agent: "
                f"{observer!r}"
            )
    for motive_agent in api.motives.agent_ids():
        if not api.agents.has_agent(motive_agent):
            raise ValueError(
                "snapshot motive agent must reference a registered agent: "
                f"{motive_agent!r}"
            )
    for affordance_agent in api.affordances.agent_ids():
        if not api.agents.has_agent(affordance_agent):
            raise ValueError(
                "snapshot affordance agent must reference a registered agent: "
                f"{affordance_agent!r}"
            )
        current = api.affordances.current(affordance_agent)
        allowed = set(api.agents.capabilities(affordance_agent))
        for candidate in current["candidates"]:
            if candidate["capability"] not in allowed:
                raise ValueError(
                    "snapshot current affordance capability must be registered "
                    f"for agent: {candidate['capability']!r}"
                )


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
        *,
        episode_store=None,
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
            interpretations=InterpretationRuntime(),
            attention=AttentionRuntime(),
            agents=AgentRuntime(),
            perception=PerceptionRuntime(),
            motives=MotiveRuntime(),
            affordances=AffordanceRuntime(),
            continuity=ContinuityRuntime(),
            episode_store=episode_store,
        )

    def _bind_runtime(
        self,
        *,
        engine: GhostEngine,
        event_map: dict,
        world: WorldRuntime,
        epistemic: EpistemicRuntime,
        emotions: EmotionRuntime,
        interpretations: InterpretationRuntime,
        attention: AttentionRuntime,
        agents: AgentRuntime,
        perception: PerceptionRuntime,
        motives: MotiveRuntime,
        affordances: AffordanceRuntime,
        continuity: ContinuityRuntime,
        episode_store,
        history_manifest=None,
        optimization_packet=None,
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
        self.interpretations = interpretations
        self.attention = attention
        self.agents = agents
        self.perception = perception
        self.motives = motives
        self.affordances = affordances
        self.continuity = continuity
        self.episode_store = episode_store
        self._continuity_history_defer = 0
        self._continuity_optimization = ContinuityOptimizationRuntime(
            emotions=self.emotions,
            interpretations=self.interpretations,
            attention=self.attention,
            continuity=self.continuity,
            episode_store=self.episode_store,
            history_manifest=history_manifest,
        )
        if optimization_packet is not None:
            self._continuity_optimization.verify_optimization_packet(
                deepcopy(optimization_packet)
            )
        if self.continuity.has_state():
            self._continuity_optimization.compact_all(strict=True)

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

    def _materialize_continuity_time(self, agent: str) -> None:
        self._continuity_optimization.materialize(str(agent))

    def _materialize_all_continuity_time(self) -> None:
        self._continuity_optimization.materialize_all()

    def _compact_continuity_history(self, agent: str) -> None:
        if (
            self._continuity_history_defer == 0
            and self.continuity.get_state(agent) is not None
        ):
            self._continuity_optimization.compact(str(agent))

    def _expand_history_state(
        self,
        subsystem: str,
        agent: str,
        state: dict | None,
        history_limit: int,
    ) -> dict | None:
        if state is None:
            return None
        out = deepcopy(state)
        out["history"] = self._continuity_optimization.expanded_history(
            subsystem,
            str(agent),
            out.get("history", []),
            limit=history_limit,
        )
        return out

    @contextmanager
    def _defer_continuity_history(self):
        self._continuity_history_defer += 1
        try:
            yield
        finally:
            self._continuity_history_defer -= 1

    def _continuity_agent_checkpoint(self, agent: str) -> dict:
        """Capture one agent's mutable continuity-layer state for rollback."""
        agent = str(agent)
        return {
            "emotion_sequence": self.emotions._sequence,
            "emotion_state": deepcopy(self.emotions._agents.get(agent)),
            "interpretation_sequence": self.interpretations._sequence,
            "interpretation_state": deepcopy(
                self.interpretations._agents.get(agent)
            ),
            "attention_sequence": self.attention._sequence,
            "attention_state": deepcopy(self.attention._agents.get(agent)),
            "continuity_state": deepcopy(self.continuity._agents.get(agent)),
            "pending_steps": self._continuity_optimization._pending_steps.get(agent),
            "pending_calls": self._continuity_optimization._pending_calls.get(agent),
            "projection_active": deepcopy(
                self._continuity_optimization._projection_active.get(agent)
            ),
        }

    @staticmethod
    def _restore_mapping_entry(mapping: dict, key: str, value) -> None:
        if value is None:
            mapping.pop(key, None)
        else:
            mapping[key] = deepcopy(value)

    def _restore_continuity_agent_checkpoint(
        self,
        agent: str,
        checkpoint: dict,
    ) -> None:
        """Restore a checkpoint without materializing unrelated agents."""
        agent = str(agent)
        self.emotions._sequence = checkpoint["emotion_sequence"]
        self.interpretations._sequence = checkpoint["interpretation_sequence"]
        self.attention._sequence = checkpoint["attention_sequence"]
        self._restore_mapping_entry(
            self.emotions._agents, agent, checkpoint["emotion_state"]
        )
        self._restore_mapping_entry(
            self.interpretations._agents,
            agent,
            checkpoint["interpretation_state"],
        )
        self._restore_mapping_entry(
            self.attention._agents, agent, checkpoint["attention_state"]
        )
        self._restore_mapping_entry(
            self.continuity._agents, agent, checkpoint["continuity_state"]
        )
        self._restore_mapping_entry(
            self._continuity_optimization._pending_steps,
            agent,
            checkpoint["pending_steps"],
        )
        self._restore_mapping_entry(
            self._continuity_optimization._pending_calls,
            agent,
            checkpoint["pending_calls"],
        )
        self._restore_mapping_entry(
            self._continuity_optimization._projection_active,
            agent,
            checkpoint["projection_active"],
        )

    @classmethod
    def from_snapshot(
        cls,
        snapshot: dict,
        *,
        episode_store=None,
    ) -> "GhostAPI":
        """Restore a complete GhostAPI runtime from a validated snapshot."""
        parts = _validate_api_snapshot_envelope(snapshot)
        continuity_snapshot, history_manifest, optimization_packet = (
            _validate_continuity_restore_packet(snapshot, episode_store)
        )
        api = _build_api_from_restore_parts(
            cls,
            parts,
            continuity_snapshot,
            episode_store=episode_store,
            history_manifest=history_manifest,
            optimization_packet=optimization_packet,
        )
        _validate_restored_agent_layer_links(api)
        return api

    def restore_snapshot(self, snapshot: dict) -> dict:
        """
        Restore this API instance in-place from snapshot() output.

        Returns the restored JSON-safe public snapshot.
        """
        restored = self.from_snapshot(
            snapshot,
            episode_store=self.episode_store,
        )

        self._bind_runtime(
            engine=restored.engine,
            event_map=restored.event_map,
            world=restored.world,
            epistemic=restored.epistemic,
            emotions=restored.emotions,
            interpretations=restored.interpretations,
            attention=restored.attention,
            agents=restored.agents,
            perception=restored.perception,
            motives=restored.motives,
            affordances=restored.affordances,
            continuity=restored.continuity,
            episode_store=restored.episode_store,
            history_manifest=restored._continuity_optimization.history_manifest(),
            optimization_packet=(
                restored._continuity_optimization.optimization_packet()
            ),
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
    # PERSISTENT AGENT RUNTIME (v1.11.0 DEVELOPMENT — PHASES 1-4)
    # -----------------------------
    def register_agent(
        self,
        agent_id,
        *,
        role=None,
        traits: dict | None = None,
        values: dict | None = None,
        goals=None,
        capabilities=None,
        metadata: dict | None = None,
    ) -> GhostAgent:
        """Register one durable agent identity without inventing history."""
        state = self.agents.register_agent(
            agent_id,
            role=role,
            traits=traits,
            values=values,
            goals=goals,
            capabilities=capabilities,
            metadata=metadata,
        )
        return GhostAgent(self, state["agent_id"])

    def agent(
        self,
        agent_id,
    ) -> GhostAgent | None:
        """Return a bound handle for a registered agent, or None."""
        if not self.agents.has_agent(agent_id):
            return None
        return GhostAgent(self, agent_id)

    def agent_state(
        self,
        agent_id,
        *,
        include_layers: bool = True,
    ) -> dict | None:
        """Return one copied coherent agent view over existing Ghost layers."""
        state = self.agents.get_state(agent_id)
        if state is None:
            return None
        if not isinstance(include_layers, bool):
            raise ValueError("include_layers must be a bool")
        if not include_layers:
            return state

        state["layers"] = {
            "emotions": self.emotional_state(agent_id),
            "interpretation": self.interpretation_state(agent_id),
            "attention": self.attention_state(agent_id),
            "perception": self.perception.get_state(agent_id),
            "motives": self.motives.current(agent_id),
            "affordances": self.affordances.current(agent_id),
        }
        return state

    def _remove_agent_capability(self, agent_id, capability_id) -> bool:
        """Enforce cross-layer affordance integrity for a bound GhostAgent."""
        capability_id = normalize_id(capability_id, "agent capability id")
        if capability_id in self.affordances.current_capabilities(agent_id):
            raise ValueError(
                "cannot remove capability while a current affordance references it"
            )
        return self.agents.remove_capability(agent_id, capability_id)

    def _agent_motive_signals(self, agent_id) -> dict:
        """Build motive signals across the registered agent's owned layers."""
        agent_state = self.agents.get_state(agent_id)
        if agent_state is None:
            raise RuntimeError(f"registered agent disappeared: {agent_id}")
        return build_motive_signal_packet(
            agent_id,
            agent_state=agent_state,
            persistent_salience=self.persistent_salience(agent_id),
            attention_state=self.attention_state(agent_id),
        )

    def _evaluate_agent_motives(self, agent_id) -> dict:
        """Evaluate motives after building the current cross-layer signal packet."""
        return self.motives.evaluate(
            agent_id,
            self._agent_motive_signals(agent_id),
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
        self._materialize_continuity_time(agent)
        state = self.emotions.register_agent(
            agent=agent,
            initial=initial,
            baseline=baseline,
            sensitivities=sensitivities,
            inertia=inertia,
            salience_bias=salience_bias,
            spotlight_switch_margin=spotlight_switch_margin,
        )
        self._compact_continuity_history(agent)
        return self._expand_history_state(
            "emotion", agent, state, self.emotions.history_limit
        )

    def emotional_state(
        self,
        agent: str,
    ) -> dict | None:
        """Return copied emotional levels, salience, and history for one agent."""
        self._materialize_continuity_time(agent)
        self._compact_continuity_history(agent)
        return self._expand_history_state(
            "emotion",
            agent,
            self.emotions.get_state(agent),
            self.emotions.history_limit,
        )

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
        self._materialize_continuity_time(agent)
        packet = self.emotions.apply_event(
            agent=agent,
            event=event,
            intensity=intensity,
            source=source,
            context_modifiers=context_modifiers,
            impulse_overrides=impulse_overrides,
        )
        self._compact_continuity_history(agent)
        packet = deepcopy(packet)
        packet["state"] = self._expand_history_state(
            "emotion",
            agent,
            self.emotions.get_state(agent),
            self.emotions.history_limit,
        )
        return packet

    def tick_emotions(
        self,
        agent: str | None = None,
        steps: int = 1,
    ) -> dict:
        """Decay emotional levels toward per-channel baselines via inertia."""
        if agent is None:
            self._materialize_all_continuity_time()
        else:
            self._materialize_continuity_time(agent)
        packet = self.emotions.tick(
            agent=agent,
            steps=steps,
        )
        for row in packet["agents"]:
            self._compact_continuity_history(row["agent"])
            row["state"] = self._expand_history_state(
                "emotion",
                row["agent"],
                self.emotions.get_state(row["agent"]),
                self.emotions.history_limit,
            )
        return packet

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
        engine_checkpoint = self.engine.snapshot()
        continuity_checkpoint = self._continuity_agent_checkpoint(target)
        try:
            with self._defer_continuity_history():
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
            self.engine = GhostEngine.from_snapshot(engine_checkpoint)
            self._restore_continuity_agent_checkpoint(
                target, continuity_checkpoint
            )
            raise
        self._compact_continuity_history(target)
        emotional_state = self.emotional_state(target)
        emotion_packet = deepcopy(emotion_packet)
        emotion_packet["state"] = deepcopy(emotional_state)
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
    # NPC-SPECIFIC ACTION INTERPRETATION v1.10.0
    # -----------------------------
    def register_interpretation_agent(
        self,
        agent: str,
        initial: dict | None = None,
        baseline: dict | None = None,
        thresholds: dict | None = None,
        sensitivities: dict | None = None,
        rules: dict | None = None,
    ) -> dict:
        """Register persistent NPC-specific meaning pressures and rules."""
        self._materialize_continuity_time(agent)
        state = self.interpretations.register_agent(
            agent=agent,
            initial=initial,
            baseline=baseline,
            thresholds=thresholds,
            sensitivities=sensitivities,
            rules=rules,
        )
        self._compact_continuity_history(agent)
        return self._expand_history_state(
            "interpretation", agent, state, self.interpretations.history_limit
        )

    def configure_interpretation_rule(
        self,
        agent: str,
        feature: str,
        pressures: dict,
    ) -> dict:
        """Configure one objective-feature -> interpretation-pressure rule."""
        self._materialize_continuity_time(agent)
        state = self.interpretations.configure_rule(
            agent=agent,
            feature=feature,
            pressures=pressures,
        )
        self._compact_continuity_history(agent)
        # Preserve the established public configure-rule return contract.
        # Cold-history reconstruction applies only to state/history views;
        # configure_rule() returns the rule packet itself.
        return state

    def interpretation_state(
        self,
        agent: str,
    ) -> dict | None:
        """Return copied interpretation levels, thresholds, rules, and history."""
        self._materialize_continuity_time(agent)
        self._compact_continuity_history(agent)
        return self._expand_history_state(
            "interpretation",
            agent,
            self.interpretations.get_state(agent),
            self.interpretations.history_limit,
        )

    def evaluate_action_meaning(
        self,
        agent: str,
        action: str,
        features: dict | None = None,
        intensity: float = 1.0,
        context_modifiers: dict | None = None,
        source: str | None = None,
        provenance: dict | None = None,
    ) -> dict:
        """
        Apply one objective action to one NPC's configured interpretation state.

        The action remains objective. Ghost only applies caller-configured
        meaning rules and persistent per-agent thresholds; it does not invent
        facts, infer an unobserved action, choose behavior, or generate dialogue.
        """
        self._materialize_continuity_time(agent)
        packet = self.interpretations.evaluate_action(
            agent=agent,
            action=action,
            features=features,
            intensity=intensity,
            context_modifiers=context_modifiers,
            source=source,
            provenance=provenance,
        )
        self._compact_continuity_history(agent)
        packet = deepcopy(packet)
        packet["state"] = self._expand_history_state(
            "interpretation",
            agent,
            self.interpretations.get_state(agent),
            self.interpretations.history_limit,
        )
        return packet

    # -----------------------------
    # PERSISTENT ATTENTION / FLOW v1.10.0
    # -----------------------------
    def register_attention_agent(
        self,
        agent: str,
        initial_flow_pressure: float | None = None,
        flow_active: bool | None = None,
        config: dict | None = None,
    ) -> dict:
        """Register persistent per-agent attention / flow state."""
        self._materialize_continuity_time(agent)
        state = self.attention.register_agent(
            agent=agent,
            initial_flow_pressure=initial_flow_pressure,
            flow_active=flow_active,
            config=config,
        )
        self._compact_continuity_history(agent)
        return self._expand_history_state(
            "attention", agent, state, self.attention.history_limit
        )

    def attention_state(
        self,
        agent: str,
    ) -> dict | None:
        """Return copied attention pressure, flow state, config, and history."""
        self._materialize_continuity_time(agent)
        self._compact_continuity_history(agent)
        return self._expand_history_state(
            "attention",
            agent,
            self.attention.get_state(agent),
            self.attention.history_limit,
        )

    def advance_attention(
        self,
        agent: str,
        signals: dict | None = None,
        salience: dict | None = None,
        source: str | None = None,
        provenance: dict | None = None,
    ) -> dict:
        """
        Advance one NPC's deterministic attention / flow state.

        ``salience`` is treated as an external persistent-state view. Ghost returns
        an attended copy and never rewrites the caller's underlying emotion or
        interpretation values. Strong novelty, threat, contradiction, or
        interpretation impulses can break through flow immediately.
        """
        self._materialize_continuity_time(agent)
        packet = self.attention.step(
            agent=agent,
            signals=signals,
            salience=salience,
            source=source,
            provenance=provenance,
        )
        self._compact_continuity_history(agent)
        return packet

    # -----------------------------
    # READ-ONLY PERSISTENT SALIENCE BRIDGE v1.10.0
    # -----------------------------
    def persistent_salience(
        self,
        agent: str,
        include_emotions: bool = True,
        include_interpretations: bool = True,
    ) -> dict:
        """Return a copied salience view of persistent Ghost state.

        The bridge reads emotional and interpretation state without granting
        attention write authority over either source. Source dimensions are
        namespaced so overlapping channel names cannot collide.
        """
        self._materialize_continuity_time(agent)
        emotion_state = (
            self.emotions.get_state(agent)
            if include_emotions
            else None
        )
        interpretation_state = (
            self.interpretations.get_state(agent)
            if include_interpretations
            else None
        )
        return build_salience_bridge(
            agent,
            emotion_state=emotion_state,
            interpretation_state=interpretation_state,
            include_emotions=include_emotions,
            include_interpretations=include_interpretations,
        )

    def advance_attention_from_state(
        self,
        agent: str,
        signals: dict | None = None,
        include_emotions: bool = True,
        include_interpretations: bool = True,
        provenance: dict | None = None,
    ) -> dict:
        """Advance attention from one coherent copied persistent-state view.

        Source state is read first, then the resulting salience copy is handed
        to ``AttentionRuntime``. The attention layer can transform visibility
        but cannot mutate or rebuild the emotional/interpretation sources.
        """
        if provenance is not None and not isinstance(provenance, dict):
            raise ValueError("provenance must be a dict or None")

        self._materialize_continuity_time(agent)
        bridge = self.persistent_salience(
            agent,
            include_emotions=include_emotions,
            include_interpretations=include_interpretations,
        )
        continuity_state = self.continuity.get_state(agent)
        if continuity_state is not None and include_interpretations:
            bridge = self.continuity.activation_aware_salience(agent, bridge)
        bridge_provenance = {
            "salience_bridge": {
                "packet_version": bridge["packet_version"],
                "sources": deepcopy(bridge["sources"]),
            },
        }
        if provenance is not None:
            bridge_provenance["caller"] = deepcopy(provenance)

        attention = self.attention.step(
            agent=agent,
            signals=signals,
            salience=bridge["salience"],
            source="ghost:salience_bridge",
            provenance=bridge_provenance,
        )
        packet = {
            "agent": bridge["agent"],
            "bridge": deepcopy(bridge),
            "attention": deepcopy(attention),
        }
        if continuity_state is not None:
            packet["foreground"] = self.continuity.resolve_foreground(
                agent,
                attention["attended_salience"],
                sequence=attention["sequence"],
            )
            packet["interpretation_activation"] = deepcopy(
                self.continuity.get_state(agent)["activation"]
            )
        self._compact_continuity_history(agent)
        return packet

    # -----------------------------
    # CAUSAL CONTINUITY / DURABLE EPISODES
    # -----------------------------
    def _ensure_continuity_agent(self, agent: str) -> dict:
        existing = self.continuity.get_state(agent)
        if existing is not None:
            self._materialize_continuity_time(agent)
            return self.continuity.get_state(agent)

        attention_state = self.attention_state(agent)
        if attention_state is None:
            attention_state = self.register_attention_agent(agent)

        emotion_state = self.emotional_state(agent)
        switch_threshold = (
            DEFAULT_SPOTLIGHT_SWITCH_MARGIN
            if emotion_state is None
            else emotion_state["spotlight_switch_margin"]
        )
        state = self.continuity.register_agent(
            agent,
            release_rate=attention_state["config"]["release_rate"],
            switch_threshold=switch_threshold,
        )
        self._compact_continuity_history(agent)
        return state

    @staticmethod
    def _emotion_history_entry(emotion_packet: dict) -> dict | None:
        history = emotion_packet["state"]["history"]
        return None if not history else deepcopy(history[-1])

    def _record_continuity_episodes(
        self,
        *,
        agent: str,
        interpretation: dict,
        emotion_entry: dict | None,
    ) -> list[dict]:
        if self.episode_store is None:
            return []
        positive_dimensions = [
            dimension
            for dimension, transition in sorted(interpretation["transitions"].items())
            if float(transition["effective_impulse"]) > 0.0
        ]
        if len(positive_dimensions) > 1:
            raise ValueError(
                "production M3 episode identity currently supports one positive "
                "interpretation origin per continuity event"
            )
        if not positive_dimensions:
            return []
        interpretation_entry = deepcopy(interpretation["state"]["history"][-1])
        return [
            self.episode_store.register(
                agent=agent,
                dimension=positive_dimensions[0],
                interpretation_entry=interpretation_entry,
                emotion_entry=emotion_entry,
            )
        ]

    def _apply_continuity_emotion(
        self,
        agent: str,
        *,
        event: str | None,
        intensity: float,
        context: dict | None,
        impulses: dict | None,
        source: str | None,
    ) -> tuple[dict | None, dict | None]:
        if event is None:
            if impulses is not None or context is not None:
                raise ValueError(
                    "emotion_event is required when emotion context or impulses are supplied"
                )
            return None, None
        self._materialize_continuity_time(agent)
        packet = self.emotions.apply_event(
            agent=agent,
            event=event,
            intensity=intensity,
            source=source,
            context_modifiers=context,
            impulse_overrides=impulses,
        )
        return packet, self._emotion_history_entry(packet)

    def _evaluate_continuity_meaning(
        self,
        agent: str,
        action: str,
        *,
        features: dict | None,
        intensity: float,
        context_modifiers: dict | None,
        source: str | None,
        provenance: dict | None,
        emotion_entry: dict | None,
    ) -> dict:
        meaning_provenance = deepcopy(provenance) if provenance is not None else {}
        if emotion_entry is not None:
            meaning_provenance["emotion_event_sequence"] = emotion_entry["sequence"]
        return self.interpretations.evaluate_action(
            agent=agent,
            action=action,
            features=features,
            intensity=intensity,
            context_modifiers=context_modifiers,
            source=source,
            provenance=meaning_provenance or None,
        )

    def continuity_event(
        self,
        agent: str,
        action: str,
        *,
        features: dict | None = None,
        intensity: float = 1.0,
        context_modifiers: dict | None = None,
        source: str | None = None,
        provenance: dict | None = None,
        emotion_event: str | None = None,
        emotion_intensity: float = 1.0,
        emotion_context: dict | None = None,
        emotion_impulses: dict | None = None,
        signals: dict | None = None,
    ) -> dict:
        """Apply one continuity-bearing experience without replay ambiguity."""
        checkpoint = self._continuity_agent_checkpoint(agent)
        try:
            with self._defer_continuity_history():
                self._ensure_continuity_agent(agent)
                emotion, emotion_entry = self._apply_continuity_emotion(
                    agent,
                    event=emotion_event,
                    intensity=emotion_intensity,
                    context=emotion_context,
                    impulses=emotion_impulses,
                    source=source,
                )
                interpretation = self._evaluate_continuity_meaning(
                    agent,
                    action,
                    features=features,
                    intensity=intensity,
                    context_modifiers=context_modifiers,
                    source=source,
                    provenance=provenance,
                    emotion_entry=emotion_entry,
                )
                activation = self.continuity.ingest_interpretation_result(
                    agent,
                    interpretation,
                )
                attended = self.advance_attention_from_state(
                    agent,
                    signals=signals,
                    provenance={
                        "cause": "continuity_event",
                        "action": action,
                    },
                )
                episodes = self._record_continuity_episodes(
                    agent=agent,
                    interpretation=interpretation,
                    emotion_entry=emotion_entry,
                )
        except Exception:
            self._restore_continuity_agent_checkpoint(agent, checkpoint)
            raise
        self._compact_continuity_history(agent)
        return {
            "agent": agent,
            "action": action,
            "emotion": deepcopy(emotion),
            "interpretation": deepcopy(interpretation),
            "activation": deepcopy(activation),
            "episodes": deepcopy(episodes),
            "attention": deepcopy(attended["attention"]),
            "foreground": deepcopy(attended.get("foreground")),
            "continuity": deepcopy(self.continuity.get_state(agent)),
        }

    def _reactivate_episode_lookup(
        self,
        *,
        agent: str,
        dimension: str,
        retrieval_strength: float,
        lookup: dict,
        episode_id: str | None,
    ) -> dict:
        with self._defer_continuity_history():
            self._ensure_continuity_agent(agent)
            meaning_before = deepcopy(
                (self.interpretations.get_state(agent) or {}).get("levels")
            )
            activation = self.continuity.recall(
                agent,
                dimension,
                retrieval_strength,
            )
            record = lookup.get("record")
            emotion = None
            if record is not None and record["emotion_profile"]:
                emotion = self.apply_emotional_event(
                    agent,
                    f"recall_{dimension}",
                    intensity=retrieval_strength,
                    source="ghost:continuity_recall",
                    impulse_overrides=record["emotion_profile"],
                )
            attended = self.advance_attention_from_state(
                agent,
                signals={"interpretation_impulse": retrieval_strength},
                provenance={
                    "cause": "causal_episode_recall",
                    "episode_id": episode_id,
                    "dimension": dimension,
                    "lookup_status": lookup.get("status"),
                },
            )
            meaning_after = deepcopy(
                (self.interpretations.get_state(agent) or {}).get("levels")
            )
            result = {
                "agent": agent,
                "dimension": dimension,
                "episode_id": episode_id,
                "retrieval_strength": retrieval_strength,
                "lookup": deepcopy(lookup),
                "activation": deepcopy(activation),
                "emotion": deepcopy(emotion),
                "meaning_unchanged": meaning_before == meaning_after,
                "attention": deepcopy(attended["attention"]),
                "foreground": deepcopy(attended.get("foreground")),
                "continuity": deepcopy(self.continuity.get_state(agent)),
            }
        self._compact_continuity_history(agent)
        return result

    def recall_episode(
        self,
        episode_id: str,
        retrieval_strength: float,
    ) -> dict:
        """Recall one exact causal episode without replaying its source event."""
        if self.episode_store is None:
            raise RuntimeError("no durable episode store is attached")
        record = self.episode_store.get(episode_id)
        if record is None:
            raise KeyError(f"unknown causal episode: {episode_id}")
        return self._reactivate_episode_lookup(
            agent=record["agent"],
            dimension=record["dimension"],
            retrieval_strength=retrieval_strength,
            lookup={
                "status": "explicit_episode",
                "agent": record["agent"],
                "dimension": record["dimension"],
                "candidate_count": 1,
                "record": record,
            },
            episode_id=record["episode_id"],
        )

    def recall_dimension(
        self,
        agent: str,
        dimension: str,
        retrieval_strength: float,
    ) -> dict:
        """Recall a dimension only when the durable episode is unambiguous."""
        if self.episode_store is None:
            raise RuntimeError("no durable episode store is attached")
        self._materialize_continuity_time(agent)
        self._compact_continuity_history(agent)
        lookup = self.episode_store.resolve_dimension(agent, dimension)
        if lookup.get("status") == "ambiguous":
            strength = validate_unit_interval(
                retrieval_strength,
                "retrieval_strength",
            )
            continuity = deepcopy(self.continuity.get_state(agent))
            before = (
                0.0
                if continuity is None
                else continuity["activation"].get(dimension, 0.0)
            )
            return {
                "agent": agent,
                "dimension": dimension,
                "episode_id": None,
                "retrieval_strength": strength,
                "lookup": deepcopy(lookup),
                "activation": {
                    "cause": "ambiguous_memory_recall_refused",
                    "dimension": dimension,
                    "retrieval_strength": strength,
                    "activation_before": before,
                    "activation_after": before,
                },
                "emotion": None,
                "meaning_unchanged": True,
                "attention": deepcopy(self.attention_state(agent)),
                "foreground": (
                    None if continuity is None else continuity["current_leader"]
                ),
                "continuity": continuity,
            }
        record = lookup.get("record")
        return self._reactivate_episode_lookup(
            agent=agent,
            dimension=dimension,
            retrieval_strength=retrieval_strength,
            lookup=lookup,
            episode_id=None if record is None else record["episode_id"],
        )

    def continuity_tick(self, agent: str, steps: int = 1) -> dict:
        """Advance logical continuity time without eagerly rebuilding live history."""
        state = self.continuity.get_state(agent)
        if state is None:
            state = self._ensure_continuity_agent(agent)
        receipt = self._continuity_optimization.schedule(state["agent"], steps)
        return deepcopy(receipt)

    def continuity_state(self, agent: str) -> dict | None:
        """Materialize logical time, then return copied hot continuity state."""
        self._materialize_continuity_time(agent)
        self._compact_continuity_history(agent)
        return deepcopy(self.continuity.get_state(agent))

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
        self._materialize_all_continuity_time()
        if self.continuity.has_state():
            self._continuity_optimization.compact_all(strict=True)

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
        if self.interpretations.has_state():
            packet["interpretations"] = self.interpretations.snapshot()
        if self.attention.has_state():
            packet["attention"] = self.attention.snapshot()
        if self.agents.has_state():
            packet["agents"] = self.agents.snapshot()
        if self.perception.has_state():
            packet["perception"] = self.perception.snapshot()
        if self.motives.has_state():
            packet["motives"] = self.motives.snapshot()
        if self.affordances.has_state():
            packet["affordances"] = self.affordances.snapshot()
        if self.continuity.has_state():
            packet["continuity"] = {
                "runtime": self.continuity.snapshot(),
                "episode_archive": (
                    None
                    if self.episode_store is None
                    else self.episode_store.manifest()
                ),
                "history_archive": (
                    self._continuity_optimization.history_manifest()
                ),
                "optimization": (
                    self._continuity_optimization.optimization_packet()
                ),
            }
        return packet
