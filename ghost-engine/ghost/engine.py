from dataclasses import asdict
from ghost.step import GhostStep
from ghost.agents import AgentRegistry
from ghost.relationships import RelationshipGraph


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

        # Ensure npc bucket exists
        npc = ctx.setdefault("npc", {})
        npc.setdefault("threat_level", 0.0)
        npc.setdefault("last_intent", None)
        npc.setdefault("actors", {})

        received_threat = False
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

        # ---- Internal logic (GhostStep ONLY) ----
        if step is not None:
            if step.source == "npc_engine" and step.intent == "threat":
                received_threat = True

                actor = step.actor
                intensity = float(step.intensity)

                actor_bucket = npc["actors"].setdefault(
                    actor,
                    {"threat_count": 0}
                )
                actor_bucket["threat_count"] += 1

                mood = ctx.get("state", {}).get("mood", 0.5)
                mood_multiplier = 0.5 + mood  # 0.5 → 1.5

                npc["threat_level"] += intensity * mood_multiplier
                npc["last_intent"] = "threat"
         
        # ---- Agent interaction handling ----
        if step is not None and step.actor and step.target:

            # Ensure agents exist
            self.agents.ensure(step.actor)
            self.agents.ensure(step.target)

            intent = step.intent

            if intent == "greet":
                self.relationships.apply_delta(
                    step.actor,
                    step.target,
                    {"trust": 0.02, "attachment": 0.01},
                )

            elif intent == "help":
                self.relationships.apply_delta(
                    step.actor,
                    step.target,
                    {"trust": 0.05, "attachment": 0.02},
                )

            elif intent == "threat":
                self.relationships.apply_delta(
                    step.actor,
                    step.target,
                    {"trust": -0.08},
                )

        # ---- Decay if no threat received ----
        if not received_threat:
            npc["threat_level"] = max(
                0.0,
                npc["threat_level"] - 0.15
            )

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
