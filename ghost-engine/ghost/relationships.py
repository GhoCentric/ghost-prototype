from .ids import normalize_id, normalize_pair_ids
from .events import normalize_event
from .validation import (
    validate_finite_number,
    validate_non_negative_finite,
    validate_positive_finite,
    validate_unit_interval,
)


class RelationshipGraph:
    """
    Stores pairwise relationships between agents.
    """

    RELATIONSHIP_EVENT_MAP = {
        "greet": ("pos", 0.04),
        "help": ("pos", 0.12),
        "gift": ("pos", 0.16),
        "apologize": ("pos", 0.10),
        "insult": ("neg", 0.15),
        "threat": ("neg", 0.22),
        "attack": ("neg", 0.35),
        "betrayal": ("neg", 0.70),
    }

    def __init__(self, ctx: dict):
        self._ctx = ctx
        self._rels = ctx.setdefault("relationships", {})
        self._neighbors = ctx.setdefault("neighbors", {})
        self._propagation_log = ctx.setdefault("social_propagation", [])

        # -----------------------------
        # GLOBAL PARAMETERS
        # -----------------------------
        self.pos_gain = validate_non_negative_finite(
            ctx.get("pos_gain", 0.85),
            "pos_gain",
        )
        self.neg_gain = validate_non_negative_finite(
            ctx.get("neg_gain", 1.1),
            "neg_gain",
        )

        self.pos_decay = validate_unit_interval(
            ctx.get("pos_decay", 0.97),
            "pos_decay",
        )
        self.neg_decay = validate_unit_interval(
            ctx.get("neg_decay", 0.975),
            "neg_decay",
        )

        self.max_reservoir = validate_positive_finite(
            ctx.get("max_reservoir", 5.0),
            "max_reservoir",
        )

        self.volatility = validate_non_negative_finite(
            ctx.get("volatility", 1.0),
            "volatility",
        )
        self.positive_volatility = validate_non_negative_finite(
            ctx.get("positive_volatility", 1.0),
            "positive_volatility",
        )
        self.negative_volatility = validate_non_negative_finite(
            ctx.get("negative_volatility", 1.0),
            "negative_volatility",
        )

        self.maturity_gain = validate_unit_interval(
            ctx.get("maturity_gain", 0.01),
            "maturity_gain",
        )
        self.maturity_cap = validate_unit_interval(
            ctx.get("maturity_cap", 0.75),
            "maturity_cap",
        )
        
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

    def _validate_param(self, key: str, value):
        if key in ("pos_decay", "neg_decay", "maturity_gain", "maturity_cap"):
            return validate_unit_interval(
                value,
                f"relationship parameter {key}",
            )

        if key == "max_reservoir":
            return validate_positive_finite(
                value,
                f"relationship parameter {key}",
            )

        return validate_non_negative_finite(
            value,
            f"relationship parameter {key}",
        )


    def _key(self, a: str, b: str):
        a, b = normalize_pair_ids(a, b)
        a, b = sorted((a, b))
        return f"{a}|{b}"

    def ensure_pair(self, a: str, b: str):
        a, b = normalize_pair_ids(a, b)
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
            if k not in rel:
                raise ValueError(f"Unknown relationship parameter: {k}")

            rel[k] = self._validate_param(k, v)
    
    def apply_delta(self, a: str, b: str, deltas: dict):
        if not isinstance(deltas, dict):
            raise ValueError("Relationship deltas must be a dict")

        rel = self.ensure_pair(a, b)

        for k, v in deltas.items():
            v = validate_finite_number(v, f"relationship delta {k}")

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

    def _near_break(
        self,
        *,
        after_state: str,
        after_trust: float,
        delta: float,
    ) -> bool:
        return bool(
            after_state == "neutral"
            and -0.55 < after_trust <= -0.45
            and delta < 0.0
        )

    def _pressure_label(
        self,
        *,
        trigger,
        delta: float,
        after_state: str,
        after_trust: float,
    ):
        if self._near_break(
            after_state=after_state,
            after_trust=after_trust,
            delta=delta,
        ):
            return "near_break"

        if trigger:
            event = trigger.get("event")

            if event == "relationship_broken":
                return "relationship_broken"

            if event == "deescalation":
                return "deescalating"

            if event == "forgiveness":
                return "forgiveness"

            if event == "state_shift":
                return "state_shift"

        if delta <= -0.50:
            return "major_negative_shift"

        if delta <= -0.20:
            return "negative_shift"

        if delta >= 0.20:
            return "positive_shift"

        if delta > 0.0:
            return "minor_positive_shift"

        if delta < 0.0:
            return "minor_negative_shift"

        return "stable"

    def _direction_label(self, delta: float):
        if delta > 0.0:
            return "positive"

        if delta < 0.0:
            return "negative"

        return "stable"

    def _build_diagnostics(
        self,
        *,
        event: str,
        channel: str,
        base_amount: float,
        effective_gain: float,
        before_state: str,
        after_state: str,
        before_trust: float,
        after_trust: float,
        maturity: float,
        maturity_modifier: float,
        volatility: float,
        positive_volatility: float,
        negative_volatility: float,
        transition,
        trigger,
    ):
        delta = after_trust - before_trust

        pressure = self._pressure_label(
            trigger=trigger,
            delta=delta,
            after_state=after_state,
            after_trust=after_trust,
        )

        return {
            "event": event,
            "channel": channel,
            "base_amount": base_amount,
            "effective_gain": effective_gain,
            "from_state": before_state,
            "to_state": after_state,
            "trust_before": before_trust,
            "trust_after": after_trust,
            "delta": delta,
            "abs_delta": abs(delta),
            "direction": self._direction_label(delta),
            "severity": min(1.0, abs(delta)),
            "maturity": maturity,
            "maturity_modifier": maturity_modifier,
            "volatility": volatility,
            "positive_volatility": positive_volatility,
            "negative_volatility": negative_volatility,
            "transition": transition,
            "trigger": trigger,
            "pressure": pressure,
            "near_break": pressure == "near_break",
        }

    def apply_event(
        self,
        a: str,
        b: str,
        event: str,
        intensity: float = 1.0,
    ):
        rel = self.ensure_pair(a, b)

        event = normalize_event(event)
        intensity = validate_unit_interval(
            intensity,
            "relationship event intensity",
        )

        event_map = self.RELATIONSHIP_EVENT_MAP

        if event not in event_map:
            raise ValueError(f"Unknown relationship event: {event}")

        before_trust = rel.get("pos", 0.0) - rel.get("neg", 0.0)
        before_state = rel.get("state", self._classify_state(before_trust))

        channel, base_amount = event_map[event]
        amount = base_amount * intensity
        effective_gain = 0.0

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

            effective_gain = gain

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

            effective_gain = gain

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

        diagnostics = self._build_diagnostics(
            event=event,
            channel=channel,
            base_amount=base_amount,
            effective_gain=effective_gain,
            before_state=before_state,
            after_state=after_state,
            before_trust=before_trust,
            after_trust=trust,
            maturity=maturity,
            maturity_modifier=maturity_modifier,
            volatility=volatility,
            positive_volatility=positive_volatility,
            negative_volatility=negative_volatility,
            transition=transition,
            trigger=trigger,
        )

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
        rel["diagnostics"] = diagnostics

        return self.get_relationship(a, b)

    def _social_heat_from_diagnostics(self, diagnostics: dict):
        severity = validate_unit_interval(
            diagnostics.get("severity", 0.0),
            "diagnostic severity",
        )
        pressure = diagnostics.get("pressure")
        direction = diagnostics.get("direction")

        heat = severity

        if pressure == "relationship_broken":
            heat += 0.30

        elif pressure == "near_break":
            heat += 0.20

        elif pressure == "major_negative_shift":
            heat += 0.15

        elif pressure == "state_shift":
            heat += 0.10

        if direction == "positive":
            heat *= 0.40

        return max(0.0, min(1.0, heat))

    def _apply_social_delta(
        self,
        *,
        source: str,
        affected: str,
        trust_delta: float,
        source_event: str,
        source_pressure: str,
        heat: float,
    ):
        trust_delta = validate_finite_number(
            trust_delta,
            "social trust delta",
        )
        heat = validate_unit_interval(
            heat,
            "social heat",
        )

        rel = self.ensure_pair(source, affected)

        before_trust = rel.get("pos", 0.0) - rel.get("neg", 0.0)
        before_state = rel.get("state", self._classify_state(before_trust))

        if trust_delta > 0:
            rel["pos"] = min(
                self.max_reservoir,
                rel.get("pos", 0.0) + trust_delta,
            )

        elif trust_delta < 0:
            rel["neg"] = min(
                self.max_reservoir,
                rel.get("neg", 0.0) + abs(trust_delta),
            )

        trust = rel.get("pos", 0.0) - rel.get("neg", 0.0)
        after_state = self._classify_state(trust)

        transition = None
        if before_state != after_state:
            transition = (before_state, after_state)

        trigger = self._trigger_for_transition(before_state, after_state)

        diagnostics = self._build_diagnostics(
            event="social_propagation",
            channel="social",
            base_amount=abs(trust_delta),
            effective_gain=abs(trust_delta),
            before_state=before_state,
            after_state=after_state,
            before_trust=before_trust,
            after_trust=trust,
            maturity=rel.get("maturity", 0.0),
            maturity_modifier=max(0.0, 1.0 - rel.get("maturity", 0.0)),
            volatility=rel.get("volatility", self.volatility),
            positive_volatility=rel.get(
                "positive_volatility",
                self.positive_volatility,
            ),
            negative_volatility=rel.get(
                "negative_volatility",
                self.negative_volatility,
            ),
            transition=transition,
            trigger=trigger,
        )

        rel["trust"] = trust
        rel["state"] = after_state
        rel["transition"] = transition
        rel["trigger"] = trigger
        rel["last_event"] = "social_propagation"
        rel["diagnostics"] = diagnostics

        return {
            "affected": affected,
            "source_event": source_event,
            "source_pressure": source_pressure,
            "heat": heat,
            "trust_delta": trust_delta,
            "relationship": self.get_relationship(source, affected),
        }

    def propagate_social_event(
        self,
        source: str,
        target: str,
        event: str,
        observers: list[str] | tuple[str, ...] | None = None,
        weights: dict[str, float] | None = None,
    ):
        """
        Apply a direct relationship event, then propagate bounded
        secondary relationship effects to observers.

        This is deterministic.
        No random spread.
        No hidden world mutation.
        """
        observers = list(observers or [])
        weights = weights or {}

        direct = self.apply_event(source, target, event)
        diagnostics = direct.get("diagnostics", {}) or {}

        heat = self._social_heat_from_diagnostics(diagnostics)
        direction = diagnostics.get("direction")
        pressure = diagnostics.get("pressure")
        severity = diagnostics.get("severity", 0.0)

        propagated = []

        for observer in observers:
            if observer in (source, target):
                continue

            weight = validate_unit_interval(
                weights.get(observer, 1.0),
                f"social propagation weight for {observer}",
            )

            if direction == "negative":
                trust_delta = -0.20 * heat * weight

            elif direction == "positive":
                trust_delta = 0.05 * heat * weight

            else:
                trust_delta = 0.0

            if trust_delta == 0.0:
                continue

            propagated.append(
                self._apply_social_delta(
                    source=source,
                    affected=observer,
                    trust_delta=trust_delta,
                    source_event=event,
                    source_pressure=pressure,
                    heat=heat,
                )
            )

        world_effects = {
            "pressure_delta": 0.20 * heat,
            "fear_delta": 0.08 * heat,
            "resentment_delta": 0.08 * heat,
            "order_delta": -0.04 * heat,
            "guard_suspicion_delta": 0.35 * heat,
        }

        packet = {
            "source": source,
            "target": target,
            "event": event,
            "heat": heat,
            "severity": severity,
            "pressure": pressure,
            "direct": direct,
            "propagated": propagated,
            "world_effects": world_effects,
        }

        self._propagation_log.append(packet)

        if len(self._propagation_log) > 25:
            self._propagation_log.pop(0)

        return packet

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
            "diagnostics": rel.get("diagnostics"),
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
        updated = []

        for key, rel in self._rels.items():
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

            diagnostics = self._build_diagnostics(
                event="tick",
                channel="decay",
                base_amount=0.0,
                effective_gain=trust - before_trust,
                before_state=before_state,
                after_state=after_state,
                before_trust=before_trust,
                after_trust=trust,
                maturity=maturity,
                maturity_modifier=maturity_modifier,
                volatility=volatility,
                positive_volatility=positive_volatility,
                negative_volatility=negative_volatility,
                transition=transition,
                trigger=trigger,
            )

            rel["trust"] = trust
            rel["state"] = after_state
            rel["transition"] = transition
            rel["trigger"] = trigger
            rel["last_event"] = "tick"
            rel["diagnostics"] = diagnostics

            a, b = key.split("|", 1)

            updated.append(
                {
                    "a": a,
                    "b": b,
                    "trust": trust,
                    "state": after_state,
                    "transition": transition,
                    "trigger": trigger,
                    "diagnostics": diagnostics,
                    "maturity": maturity,
                    "volatility": volatility,
                    "positive_volatility": positive_volatility,
                    "negative_volatility": negative_volatility,
                }
            )

        return {
            "event": "tick",
            "relationships": updated,
        }

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
        import copy

        return copy.deepcopy(self._rels)

    def neighbors(self, agent_id: str):
        agent_id = normalize_id(agent_id, "agent id")

        return list(self._neighbors.get(agent_id, []))

    def propagation_log(self):
        return list(self._propagation_log)