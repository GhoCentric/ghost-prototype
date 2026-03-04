class RelationshipGraph:
    """
    Stores pairwise relationships between agents.

    Relationships are stored as:

    ("A","B") → { trust, attachment }
    """

    def __init__(self, ctx: dict):
        self._ctx = ctx
        self._rels = ctx.setdefault("relationships", {})
        self._neighbors = ctx.setdefault("neighbors", {})

    def _key(self, a: str, b: str):
        return tuple(sorted((a, b)))

    def ensure_pair(self, a: str, b: str):

        key = self._key(a, b)

        rel = self._rels.setdefault(
            key,
            {
                "trust": 0.0,
                "attachment": 0.0,
            },
        )

        # Maintain neighbor index
        self._neighbors.setdefault(a, set()).add(b)
        self._neighbors.setdefault(b, set()).add(a)

        return rel

    def apply_delta(self, a: str, b: str, deltas: dict):
        """
        Apply relationship updates.
        """

        rel = self.ensure_pair(a, b)

        for k, v in deltas.items():
            rel[k] = rel.get(k, 0.0) + v

        return rel

    def get(self, a: str, b: str):
        return self._rels.get(self._key(a, b))

    def all(self):
        return self._rels
        
    def neighbors(self, agent_id: str):
        return self._neighbors.get(agent_id, set())
