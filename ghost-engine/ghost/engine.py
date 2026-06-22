import copy
import math
from dataclasses import asdict
from ghost.step import GhostStep
from ghost.agents import AgentRegistry
from ghost.relationships import RelationshipGraph
from ghost.events import normalize_event
from ghost.validation import (
    validate_non_negative_finite,
    validate_unit_interval,
)
from ghost.ids import normalize_id

GHOST_VERSION = "1.7.5"
GHOST_SNAPSHOT_SCHEMA_VERSION = "1.7.5"

def _json_safe(x):

    if isinstance(x, dict):
        return {str(k): _json_safe(v) for k, v in x.items()}

    if isinstance(x, list):
        return [_json_safe(v) for v in x]

    if isinstance(x, tuple):
        return [_json_safe(v) for v in x]

    if isinstance(x, set):
        return sorted(
            (_json_safe(v) for v in x),
            key=lambda value: repr(value),
        )

    if isinstance(x, float) and not math.isfinite(x):
        raise ValueError("Snapshot contains non-finite float")

    return x

def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class GhostEngine:
    """
    Core Ghost engine.

    - Public API: dict-based, serialization-safe
    - Internal logic may use typed objects (GhostStep)
    - All state mutation occurs via step()
    """

    def __init__(self, context: dict | None = None):
        if context is None:
            context = {}

        self._ctx = copy.deepcopy(context)

        # Subsystems
        self.agents: AgentRegistry = AgentRegistry(self._ctx)
        self.relationships: RelationshipGraph = RelationshipGraph(self._ctx)

        # Baseline state
        self._ctx.setdefault("cycles", 0)
        self._ctx.setdefault("input", None)
        self._ctx.setdefault("last_step", None)

        npc = self._ctx.setdefault("npc", {})
        npc.setdefault("threat_level", 0.0)
        npc.setdefault("last_intent", None)

    def step(self, step_data=None):
        """
        Advance the Ghost engine by one cycle.

        Accepts:
        - dict (public / legacy input)
        - GhostStep (internal / typed input)

        Internal types MUST NOT leak into public state.
        """

        ctx = self._ctx
        npc = ctx["npc"]
        
        # passive decay (only if no threat this step)
        if step_data is None:
            ctx["cycles"] += 1
            npc["threat_level"] = clamp(npc["threat_level"] - 0.02, 0.0, 999999.0)

        step: GhostStep | None = None
        public_input: dict | None = None
        
        

        # ---- Normalize input at boundary ----
        if step_data is not None:
            if isinstance(step_data, dict):
                step = GhostStep(**step_data)
                public_input = dict(step_data)

            elif isinstance(step_data, GhostStep):
                step = step_data
                public_input = asdict(step)

            else:
                raise TypeError("step_data must be dict or GhostStep")

            validated_intensity = validate_non_negative_finite(
                step.intensity,
                "step intensity",
            )

            safe_actor = normalize_id(step.actor, "agent id")
            safe_target = None

            if step.target:
                safe_target = normalize_id(step.target, "agent id")

            safe_step = dict(public_input)
            safe_step["actor"] = safe_actor
            safe_step["target"] = safe_target
            safe_step["intensity"] = validated_intensity

            ctx["cycles"] += 1

            # Public-facing state (DICT ONLY)
            ctx["input"] = safe_step
            ctx["last_step"] = safe_step

            step.actor = safe_actor
            step.target = safe_target

        # If no step, just return current state
        if step is None:
            return ctx

        npc["last_intent"] = step.intent

        # Ensure actor exists
        actor_state = self.agents.ensure(step.actor)
        actor_state["last_intent"] = step.intent

        # Optional target
        target_state = None
        if step.target:
            target_state = self.agents.ensure(step.target)
            target_state["last_intent"] = step.intent

        intensity = clamp(
            validated_intensity,
            0.0,
            1.0,
        )

        # ---- Intent handling ----
        if step.intent == "greet":
            actor_state["mood"] = clamp(actor_state["mood"] + (0.02 * intensity), 0.0, 1.0)
            actor_state["tension"] = clamp(actor_state["tension"] - (0.01 * intensity), 0.0, 1.0)

            if target_state is not None:
                target_state["mood"] = clamp(target_state["mood"] + (0.03 * intensity), 0.0, 1.0)
                target_state["tension"] = clamp(target_state["tension"] - (0.01 * intensity), 0.0, 1.0)

                self.relationships.apply_delta(
                    step.actor,
                    step.target,
                    {"trust": 0.02, "attachment": 0.01},
                )

            npc["threat_level"] = clamp(npc["threat_level"] - (0.02 * intensity), 0.0, 999999.0)

        elif step.intent == "help":
            actor_state["mood"] = clamp(actor_state["mood"] + (0.04 * intensity), 0.0, 1.0)
            actor_state["tension"] = clamp(actor_state["tension"] - (0.02 * intensity), 0.0, 1.0)

            if target_state is not None:
                target_state["mood"] = clamp(target_state["mood"] + (0.08 * intensity), 0.0, 1.0)
                target_state["tension"] = clamp(target_state["tension"] - (0.04 * intensity), 0.0, 1.0)

                self.relationships.apply_delta(
                    step.actor,
                    step.target,
                    {"trust": 0.05, "attachment": 0.02},
                )

            npc["threat_level"] = clamp(npc["threat_level"] - (0.05 * intensity), 0.0, 999999.0)

        elif step.intent == "threat":
            actor_state["mood"] = clamp(actor_state["mood"] - (0.05 * intensity), 0.0, 1.0)
            
            # actor memory invariant (public-facing)
            actors_mem = npc.setdefault("actors", {})
            entry = actors_mem.setdefault(step.actor, {})
            entry["threat_count"] = entry.get("threat_count", 0) + 1
            
            actor_state["tension"] = clamp(actor_state["tension"] + (0.06 * intensity), 0.0, 1.0)

            if target_state is not None:
                target_state["mood"] = clamp(target_state["mood"] - (0.12 * intensity), 0.0, 1.0)
                target_state["tension"] = clamp(target_state["tension"] + (0.18 * intensity), 0.0, 1.0)

                self.relationships.apply_delta(
                    step.actor,
                    step.target,
                    {"trust": -0.08},
                )

                # ---- bounded propagation to target neighbors ----
                neighbors = self.relationships.neighbors(step.target)
                spread = 0.25 * intensity

                for neighbor_id in neighbors:
                    if neighbor_id == step.actor or neighbor_id == step.target:
                        continue

                    neighbor_state = self.agents.ensure(neighbor_id)
                    neighbor_state["mood"] = clamp(neighbor_state["mood"] - (0.03 * spread), 0.0, 1.0)
                    neighbor_state["tension"] = clamp(neighbor_state["tension"] + (0.08 * spread), 0.0, 1.0)

            # emotional modulation (public invariant)
            mood = ctx.get("state", {}).get("mood", 0.5)

            gain = 0.50 * intensity * (0.5 + mood)

            npc["threat_level"] = clamp(npc["threat_level"] + gain, 0.0, 999999.0)

        else:
            # Unknown or neutral intent -> mild decay only
            npc["threat_level"] = clamp(npc["threat_level"] - 0.01, 0.0, 999999.0)

        return ctx

    def apply_event(self, a, b, event, intensity: float = 1.0):
        """
        Apply a relationship event between two actors.

        Public wrapper around the relationship runtime.
        """
        return self.relationships.apply_event(
            a,
            b,
            normalize_event(event),
            intensity=validate_unit_interval(
                intensity,
                "relationship event intensity",
            ),
        )

    def propagate_social_event(
        self,
        source,
        target,
        event,
        observers=None,
        weights=None,
    ):
        """
        Apply a direct relationship event and propagate bounded
        secondary effects to observers.
        """
        propagate = getattr(
            self.relationships,
            "propagate_social_event",
        )

        return propagate(
            source=source,
            target=target,
            event=event,
            observers=observers,
            weights=weights,
        )

    def tick(self):
        """
        Advance relationship time decay by one tick.

        Public wrapper around the relationship runtime.
        """
        return self.relationships.tick()

    def get_relationship(self, a, b):
        """
        Return the public relationship state between two actors.

        Public wrapper around the relationship runtime.
        """
        return self.relationships.get_relationship(a, b)

    def state(self):
        """
        Return the live engine state (mutable).

        Intended for internal or controlled external use.
        """
        return self._ctx

    def snapshot(self):
        """
        Return an immutable JSON-safe snapshot of engine state.

        Snapshot metadata is included for save/load and adapter contracts.
        Existing engine state keys remain at the top level for backward
        compatibility.
        """
        snapshot = _json_safe(copy.deepcopy(self._ctx))

        snapshot.setdefault("ghost_version", GHOST_VERSION)
        snapshot.setdefault("schema_version", GHOST_SNAPSHOT_SCHEMA_VERSION)

        return snapshot
