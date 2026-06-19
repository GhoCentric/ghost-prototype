import copy

from .ids import normalize_id


class AgentRegistry:
    """
    Tracks agents inside the Ghost engine.

    Provides a consistent place to store:
    - emotional state
    - memory
    - agent metadata

    ensure() returns the live internal agent dict because callers use it
    for controlled mutation through the engine runtime.

    get() and all() return safe copies for public reads.
    """

    def __init__(self, ctx: dict):
        self._ctx = ctx
        self._agents = ctx.setdefault("agents", {})

    def ensure(self, agent_id: str):
        """
        Ensure an agent exists.
        Returns the live agent state dict for internal mutation.
        """
        agent_id = normalize_id(agent_id, "agent id")

        return self._agents.setdefault(
            agent_id,
            {
                "mood": 0.5,
                "memory": {},
                "last_intent": None,
                "tension": 0.0,
            },
        )

    def get(self, agent_id: str):
        agent_id = normalize_id(agent_id, "agent id")

        agent = self._agents.get(agent_id)

        if agent is None:
            return None

        return copy.deepcopy(agent)

    def all(self):
        return copy.deepcopy(self._agents)
