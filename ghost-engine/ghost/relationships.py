class RelationshipGraph:
    """
    Stores pairwise relationships between agents.
    """

    def __init__(self, ctx: dict):
        self._ctx = ctx
        self._rels = ctx.setdefault("relationships", {})
        self._neighbors = ctx.setdefault("neighbors", {})

        # -----------------------------
        # GLOBAL PARAMETERS
        # -----------------------------
        self.pos_gain = ctx.get("pos_gain", 0.85)
        self.neg_gain = ctx.get("neg_gain", 1.1)

        self.pos_decay = ctx.get("pos_decay", 0.97)
        self.neg_decay = ctx.get("neg_decay", 0.975)

        self.max_reservoir = ctx.get("max_reservoir", 5.0)
        
    # -----------------------------
    # PERSONALITY PRESETS
    # -----------------------------
    PERSONALITY_PRESETS = {
            "balanced": {
                "pos_gain": 0.85,
                "neg_gain": 1.1,
                "pos_decay": 0.97,
                "neg_decay": 0.975,
            },
            "forgiving": {
                "pos_gain": 1.2,
                "neg_gain": 0.8,
                "pos_decay": 0.96,
                "neg_decay": 0.94,
            },
            "resentful": {
                "pos_gain": 0.6,
                "neg_gain": 1.4,
                "pos_decay": 0.98,
                "neg_decay": 0.995,
            },
            "volatile": {
                "pos_gain": 1.5,
                "neg_gain": 1.5,
                "pos_decay": 0.9,
                "neg_decay": 0.9,
            },
        }

    def set_personality(self, a: str, b: str, personality: str):
        if personality not in self.PERSONALITY_PRESETS:
            raise ValueError(f"Unknown personality: {personality}")

        params = self.PERSONALITY_PRESETS[personality]

        self.set_params(a, b, **params)

    def _key(self, a: str, b: str):
        a, b = sorted((a, b))
        return f"{a}|{b}"

    def ensure_pair(self, a: str, b: str):
        key = self._key(a, b)

        rel = self._rels.setdefault(
            key,
            {
                "pos": 0.0,
                "neg": 0.0,
                "attachment": 0.0,

                # -----------------------------
                # PER-RELATIONSHIP PARAMETERS
                # -----------------------------
                "pos_gain": self.pos_gain,
                "neg_gain": self.neg_gain,
                "pos_decay": self.pos_decay,
                "neg_decay": self.neg_decay,
            },
        )

        self._neighbors.setdefault(a, [])
        self._neighbors.setdefault(b, [])

        if b not in self._neighbors[a]:
            self._neighbors[a].append(b)

        if a not in self._neighbors[b]:
            self._neighbors[b].append(a)

        return rel
    
    def set_params(self, a: str, b: str, **params):
        rel = self.ensure_pair(a, b)

        for k, v in params.items():
            if k in rel:
                rel[k] = v
    
    def apply_delta(self, a: str, b: str, deltas: dict):
        rel = self.ensure_pair(a, b)

        for k, v in deltas.items():

            if k == "trust":

# -----------------------------
                # RESISTANCE + SATURATION
                # -----------------------------

                pos = rel.get("pos", 0.0)
                neg = rel.get("neg", 0.0)

                pos_gain = rel.get("pos_gain", 1.0)
                neg_gain = rel.get("neg_gain", 1.0)

                max_r = self.max_reservoir

                if v > 0:
                    # resistance: high negative reduces positive effect
                    resistance = 1.0 - min(neg / max_r, 1.0)

                    # saturation: high positive reduces further growth
                    saturation = 1.0 - min(pos / max_r, 1.0)

                    effective_gain = pos_gain * resistance * saturation

                    pos += v * effective_gain

                elif v < 0:
                    # keep negative side simple (for now)
                    neg += abs(v) * neg_gain                

                # -----------------------------
                # CLAMP
                # -----------------------------
                max_r = self.max_reservoir
                pos = min(pos, max_r)
                neg = min(neg, max_r)

                rel["pos"] = pos
                rel["neg"] = neg
                rel["trust"] = pos - neg
                continue

            rel[k] = rel.get(k, 0.0) + v

        return rel

    # -----------------------------
    # NEW: TIME DECAY (optional)
    # -----------------------------
    def tick(self):
        for rel in self._rels.values():
            rel["pos"] *= rel["pos_decay"]
            rel["neg"] *= rel["neg_decay"]

    def get(self, a: str, b: str):
        rel = self._rels.get(self._key(a, b))

        if rel is None:
            return None

        pos = rel.get("pos", 0.0)
        neg = rel.get("neg", 0.0)

        out = dict(rel)
        out["trust"] = pos - neg

        return out

    def all(self):
        return self._rels

    def neighbors(self, agent_id: str):
        return self._neighbors.get(agent_id, [])
