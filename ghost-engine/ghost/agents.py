class AgentRegistry:
    """
    Tracks agents inside the Ghost engine.

    Provides a consistent place to store:
    - emotional state
    - memory
    - agent metadata
    """

    def __init__(self, ctx: dict):
        self._ctx = ctx
        self._agents = ctx.setdefault("agents", {})

    def ensure(self, agent_id: str):
        """
        Ensure an agent exists.
        Returns the agent state dict.
        """

        return self._agents.setdefault(
            agent_id,
            {
                "mood": 0.5,
                "memory": {},
            }
        )

    def get(self, agent_id: str):
        return self._agents.get(agent_id)

    def all(self):
        return self._agents
