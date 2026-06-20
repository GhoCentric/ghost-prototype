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

        # Goodwill has its own ceiling below the absolute
        # reservoir maximum so repeated small positives cannot
        # create unlimited stored protection.
        self.positive_reservoir_cap = min(
            validate_positive_finite(
                ctx.get("positive_reservoir_cap", 3.25),
                "positive_reservoir_cap",
            ),
            self.max_reservoir,
        )

        # A mature relationship can absorb normal conflict, but
        # betrayal can breach accumulated stability once goodwill
        # and history are both substantial.
        self.betrayal_shock_maturity_threshold = validate_unit_interval(
            ctx.get("betrayal_shock_maturity_threshold", 0.50),
            "betrayal_shock_maturity_threshold",
        )

        self.betrayal_shock_positive_threshold = validate_positive_finite(
            ctx.get("betrayal_shock_positive_threshold", 1.0),
            "betrayal_shock_positive_threshold",
        )

        self.betrayal_stability_breach_fraction = validate_unit_interval(
            ctx.get("betrayal_stability_breach_fraction", 0.90),
            "betrayal_stability_breach_fraction",
        )

        # Shock mechanics activate only after a relationship has
        # substantial history and stored positive stability.
        self.stability_shock_maturity_threshold = validate_unit_interval(
            ctx.get("stability_shock_maturity_threshold", 0.50),
            "stability_shock_maturity_threshold",
        )

        self.stability_shock_positive_threshold = validate_positive_finite(
            ctx.get("stability_shock_positive_threshold", 1.0),
            "stability_shock_positive_threshold",
        )

        self.high_severity_threshold = validate_unit_interval(
            ctx.get("high_severity_threshold", 0.50),
            "high_severity_threshold",
        )

        self.high_severity_shock_bonus = validate_non_negative_finite(
            ctx.get("high_severity_shock_bonus", 0.25),
            "high_severity_shock_bonus",
        )

        # Mature history can soften ordinary conflict, but severe
        # negative events cannot be reduced below this multiplier.
        self.severe_negative_maturity_floor = validate_unit_interval(
            ctx.get("severe_negative_maturity_floor", 0.45),
            "severe_negative_maturity_floor",
        )

        self.relative_shock_ratio = validate_positive_finite(
            ctx.get("relative_shock_ratio", 2.50),
            "relative_shock_ratio",
        )

        self.relative_shock_bonus = validate_non_negative_finite(
            ctx.get("relative_shock_bonus", 0.20),
            "relative_shock_bonus",
        )

        self.recent_event_decay = validate_unit_interval(
            ctx.get("recent_event_decay", 0.80),
            "recent_event_decay",
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
        if key in (
            "pos_decay",
            "neg_decay",
            "maturity_gain",
            "maturity_cap",
            "betrayal_shock_maturity_threshold",
            "betrayal_stability_breach_fraction",
            "stability_shock_maturity_threshold",
            "high_severity_threshold",
            "severe_negative_maturity_floor",
            "recent_event_decay",
        ):
            return validate_unit_interval(
                value,
                f"relationship parameter {key}",
            )

        if key in (
            "max_reservoir",
            "positive_reservoir_cap",
            "betrayal_shock_positive_threshold",
            "stability_shock_positive_threshold",
            "relative_shock_ratio",
        ):
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
                "positive_reservoir_cap": self.positive_reservoir_cap,

                "betrayal_shock_maturity_threshold": (
                    self.betrayal_shock_maturity_threshold
                ),
                "betrayal_shock_positive_threshold": (
                    self.betrayal_shock_positive_threshold
                ),
                "betrayal_stability_breach_fraction": (
                    self.betrayal_stability_breach_fraction
                ),

                "stability_shock_maturity_threshold": (
                    self.stability_shock_maturity_threshold
                ),
                "stability_shock_positive_threshold": (
                    self.stability_shock_positive_threshold
                ),
                "high_severity_threshold": self.high_severity_threshold,
                "high_severity_shock_bonus": (
                    self.high_severity_shock_bonus
                ),
                "severe_negative_maturity_floor": (
                    self.severe_negative_maturity_floor
                ),
                "relative_shock_ratio": self.relative_shock_ratio,
                "relative_shock_bonus": self.relative_shock_bonus,
                "recent_event_decay": self.recent_event_decay,
                "recent_event_magnitude": 0.0,
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

        # Tiny decay drift should not be presented as a meaningful shift.
        # Positive and negative reservoirs can decay at slightly different rates.
        # Preserve the math, but expose a stable diagnostic below this threshold.
        if delta >= 0.005:
            return "minor_positive_shift"

        if delta <= -0.005:
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
        shock_applied: bool = False,
        stability_breach: float = 0.0,
        high_severity_shock: bool = False,
        relative_shock: bool = False,
        shock_multiplier: float = 1.0,
        event_maturity_modifier: float = 1.0,
        recent_event_magnitude: float = 0.0,
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
            "shock_applied": shock_applied,
            "stability_breach": stability_breach,
            "high_severity_shock": high_severity_shock,
            "relative_shock": relative_shock,
            "shock_multiplier": shock_multiplier,
            "event_maturity_modifier": event_maturity_modifier,
            "recent_event_magnitude": recent_event_magnitude,
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
        shock_applied = False
        stability_breach = 0.0
        high_severity_shock = False
        relative_shock = False
        shock_multiplier = 1.0

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
        event_maturity_modifier = maturity_modifier
        recent_event_magnitude = rel.get(
            "recent_event_magnitude",
            0.0,
        )

        if channel == "pos":
            positive_cap = min(
                rel.get(
                    "positive_reservoir_cap",
                    self.positive_reservoir_cap,
                ),
                self.max_reservoir,
            )

            resistance = 1.0 / (1.0 + (rel.get("neg", 0.0) * 0.35))
            saturation = max(
                0.0,
                1.0 - (rel.get("pos", 0.0) / positive_cap),
            )

            gain = amount * rel.get("pos_gain", self.pos_gain)
            gain *= volatility
            gain *= positive_volatility
            gain *= maturity_modifier
            gain *= resistance
            gain *= saturation

            effective_gain = gain

            rel["pos"] = min(
                positive_cap,
                rel.get("pos", 0.0) + gain,
            )

        elif channel == "neg":
            saturation = max(
                0.0,
                1.0 - (rel.get("neg", 0.0) / self.max_reservoir),
            )

            shock_eligible = (
                maturity >= rel.get(
                    "stability_shock_maturity_threshold",
                    self.stability_shock_maturity_threshold,
                )
                and rel.get("pos", 0.0) >= rel.get(
                    "stability_shock_positive_threshold",
                    self.stability_shock_positive_threshold,
                )
            )

            if shock_eligible:
                if amount >= rel.get(
                    "high_severity_threshold",
                    self.high_severity_threshold,
                ):
                    high_severity_shock = True
                    shock_multiplier += rel.get(
                        "high_severity_shock_bonus",
                        self.high_severity_shock_bonus,
                    )

                    event_maturity_modifier = max(
                        maturity_modifier,
                        rel.get(
                            "severe_negative_maturity_floor",
                            self.severe_negative_maturity_floor,
                        ),
                    )

                if (
                    recent_event_magnitude > 0.0
                    and amount >= recent_event_magnitude * rel.get(
                        "relative_shock_ratio",
                        self.relative_shock_ratio,
                    )
                ):
                    relative_shock = True
                    shock_multiplier += rel.get(
                        "relative_shock_bonus",
                        self.relative_shock_bonus,
                    )

            gain = amount * rel.get("neg_gain", self.neg_gain)
            gain *= volatility
            gain *= negative_volatility
            gain *= event_maturity_modifier
            gain *= saturation
            gain *= shock_multiplier

            if (
                event == "betrayal"
                and maturity >= rel.get(
                    "betrayal_shock_maturity_threshold",
                    self.betrayal_shock_maturity_threshold,
                )
                and rel.get("pos", 0.0) >= rel.get(
                    "betrayal_shock_positive_threshold",
                    self.betrayal_shock_positive_threshold,
                )
            ):
                stability_breach = (
                    rel.get("pos", 0.0)
                    * rel.get(
                        "betrayal_stability_breach_fraction",
                        self.betrayal_stability_breach_fraction,
                    )
                )
                shock_applied = True

            effective_gain = gain + stability_breach

            rel["neg"] = min(
                self.max_reservoir,
                rel.get("neg", 0.0) + gain + stability_breach,
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
            shock_applied=shock_applied,
            stability_breach=stability_breach,
            high_severity_shock=high_severity_shock,
            relative_shock=relative_shock,
            shock_multiplier=shock_multiplier,
            event_maturity_modifier=event_maturity_modifier,
            recent_event_magnitude=recent_event_magnitude,
        )

        recent_decay = rel.get(
            "recent_event_decay",
            self.recent_event_decay,
        )

        rel["recent_event_magnitude"] = (
            recent_event_magnitude * recent_decay
            + amount * (1.0 - recent_decay)
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