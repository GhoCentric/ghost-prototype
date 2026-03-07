from dataclasses import asdict
from ghost.step import GhostStep
from ghost.agents import AgentRegistry
from ghost.relationships import RelationshipGraph


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

        self._ctx = context

        # Subsystems
        self.agents = AgentRegistry(self._ctx)
        self.relationships = RelationshipGraph(self._ctx)

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
        ctx["cycles"] += 1

        npc = ctx["npc"]

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

            # Public-facing state (DICT ONLY)
            ctx["input"] = public_input
            ctx["last_step"] = public_input

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

        intensity = clamp(float(step.intensity), 0.0, 1.0)

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

            npc["threat_level"] = clamp(npc["threat_level"] + (0.50 * intensity), 0.0, 999999.0)

        else:
            # Unknown or neutral intent -> mild decay only
            npc["threat_level"] = clamp(npc["threat_level"] - 0.01, 0.0, 999999.0)

        return ctx

    def state(self):
        """
        Return the live engine state (mutable).

        Intended for internal or controlled external use.
        """
        return self._ctx

    def snapshot(self):
        """Return an immutable snapshot of engine state."""
        import copy
        return copy.deepcopy(self._ctx)
