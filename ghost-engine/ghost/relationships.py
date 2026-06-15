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

        self.volatility = ctx.get("volatility", 1.0)
        self.positive_volatility = ctx.get("positive_volatility", 1.0)
        self.negative_volatility = ctx.get("negative_volatility", 1.0)

        self.maturity_gain = ctx.get("maturity_gain", 0.01)
        self.maturity_cap = ctx.get("maturity_cap", 0.75)
        
    # -----------------------------
    # PERSONALITY PRESETS
    # -----------------------------
    PERSONALITY_PRESETS = {
        "balanced": {
            "pos_gain": 0.85,
            "neg_gain": 1.1,
            "pos_decay": 0.97,
            "neg_decay": 0.975,
            "volatility": 1.0,
            "positive_volatility": 1.0,
            "negative_volatility": 1.0,
            "maturity_gain": 0.01,
            "maturity_cap": 0.75,
        },
        "forgiving": {
            "pos_gain": 1.2,
            "neg_gain": 0.8,
            "pos_decay": 0.96,
            "neg_decay": 0.94,
            "volatility": 0.9,
            "positive_volatility": 1.0,
            "negative_volatility": 0.8,
            "maturity_gain": 0.04,
            "maturity_cap": 0.80,
        },
        "resentful": {
            "pos_gain": 0.6,
            "neg_gain": 1.4,
            "pos_decay": 0.98,
            "neg_decay": 0.995,
            "volatility": 1.1,
            "positive_volatility": 0.9,
            "negative_volatility": 1.3,
            "maturity_gain": 0.02,
            "maturity_cap": 0.65,
        },
        "volatile": {
            "pos_gain": 1.5,
            "neg_gain": 1.5,
            "pos_decay": 0.9,
            "neg_decay": 0.9,
            "volatility": 1.2,
            "positive_volatility": 1.1,
            "negative_volatility": 1.8,
            "maturity_gain": 0.01,
            "maturity_cap": 0.40,
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

                "maturity": 0.0,
                "volatility": self.volatility,
                "positive_volatility": self.positive_volatility,
                "negative_volatility": self.negative_volatility,
                "maturity_gain": self.maturity_gain,
                "maturity_cap": self.maturity_cap,
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
                # EXACT ACCUMULATION (TEST SAFE)
                # -----------------------------
                rel["trust"] = rel.get("trust", 0.0) + v

                # keep reservoirs in sync (optional but good)
                if v > 0:
                    rel["pos"] = rel.get("pos", 0.0) + v
                elif v < 0:
                    rel["neg"] = rel.get("neg", 0.0) + abs(v)

                continue

            rel[k] = rel.get(k, 0.0) + v

        return rel

    def _classify_state(self, trust: float):
        if trust <= -0.55:
            return "hostile"

        if trust >= 0.08:
            return "friendly"

        return "neutral"

    def _trigger_for_transition(self, before: str, after: str):
        if before == after:
            return None

        if after == "hostile":
            return {"event": "relationship_broken"}

        if before == "hostile" and after == "neutral":
            return {"event": "deescalation"}

        if before in ("hostile", "neutral") and after == "friendly":
            return {"event": "forgiveness"}

        return {"event": "state_shift"}

    def apply_event(self, a: str, b: str, event: str):
        rel = self.ensure_pair(a, b)

        event = str(event).lower().strip()

        event_map = {
            "greet": ("pos", 0.04),
            "help": ("pos", 0.12),
            "gift": ("pos", 0.16),
            "apologize": ("pos", 0.10),

            "insult": ("neg", 0.15),
            "threat": ("neg", 0.22),
            "attack": ("neg", 0.35),
            "betrayal": ("neg", 0.70),
        }

        if event not in event_map:
            raise ValueError(f"Unknown relationship event: {event}")

        before_trust = rel.get("pos", 0.0) - rel.get("neg", 0.0)
        before_state = rel.get("state", self._classify_state(before_trust))

        channel, amount = event_map[event]

        maturity = rel.get("maturity", 0.0)
        volatility = rel.get("volatility", self.volatility)
        positive_volatility = rel.get(
            "positive_volatility",
            self.positive_volatility,
        )
        negative_volatility = rel.get(
            "negative_volatility",
            self.negative_volatility,
        )
        maturity_modifier = max(0.0, 1.0 - maturity)

        if channel == "pos":
            resistance = 1.0 / (1.0 + (rel.get("neg", 0.0) * 0.35))
            saturation = max(
                0.0,
                1.0 - (rel.get("pos", 0.0) / self.max_reservoir),
            )

            gain = amount * rel.get("pos_gain", self.pos_gain)
            gain *= volatility
            gain *= positive_volatility
            gain *= maturity_modifier
            gain *= resistance
            gain *= saturation

            rel["pos"] = min(
                self.max_reservoir,
                rel.get("pos", 0.0) + gain,
            )

        elif channel == "neg":
            saturation = max(
                0.0,
                1.0 - (rel.get("neg", 0.0) / self.max_reservoir),
            )

            gain = amount * rel.get("neg_gain", self.neg_gain)
            gain *= volatility
            gain *= negative_volatility
            gain *= maturity_modifier
            gain *= saturation

            rel["neg"] = min(
                self.max_reservoir,
                rel.get("neg", 0.0) + gain,
            )

        trust = rel.get("pos", 0.0) - rel.get("neg", 0.0)
        after_state = self._classify_state(trust)

        transition = None
        if before_state != after_state:
            transition = (before_state, after_state)

        trigger = self._trigger_for_transition(before_state, after_state)

        maturity_gain = rel.get("maturity_gain", self.maturity_gain)
        maturity_cap = rel.get("maturity_cap", self.maturity_cap)

        rel["maturity"] = min(
            maturity_cap,
            rel.get("maturity", 0.0) + maturity_gain,
        )

        rel["trust"] = trust
        rel["state"] = after_state
        rel["transition"] = transition
        rel["trigger"] = trigger
        rel["last_event"] = event

        return self.get_relationship(a, b)

    def get_relationship(self, a: str, b: str):
        rel = self.ensure_pair(a, b)

        trust = rel.get("pos", 0.0) - rel.get("neg", 0.0)
        state = self._classify_state(trust)

        rel["trust"] = trust
        rel["state"] = state

        return {
            "trust": trust,
            "state": state,
            "transition": rel.get("transition"),
            "trigger": rel.get("trigger"),
            "maturity": rel.get("maturity", 0.0),
            "volatility": rel.get("volatility", self.volatility),
            "positive_volatility": rel.get(
                "positive_volatility",
                self.positive_volatility,
            ),
            "negative_volatility": rel.get(
                "negative_volatility",
                self.negative_volatility,
            ),
        }

    # -----------------------------
    # NEW: TIME DECAY (optional)
    # -----------------------------
    def tick(self):
        for rel in self._rels.values():
            before_trust = rel.get("pos", 0.0) - rel.get("neg", 0.0)
            before_state = rel.get("state", self._classify_state(before_trust))

            rel["pos"] *= rel["pos_decay"]
            rel["neg"] *= rel["neg_decay"]

            trust = rel.get("pos", 0.0) - rel.get("neg", 0.0)
            after_state = self._classify_state(trust)

            transition = None
            if before_state != after_state:
                transition = (before_state, after_state)

            trigger = self._trigger_for_transition(before_state, after_state)

            rel["trust"] = trust
            rel["state"] = after_state
            rel["transition"] = transition
            rel["trigger"] = trigger
            rel["last_event"] = "tick"

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
