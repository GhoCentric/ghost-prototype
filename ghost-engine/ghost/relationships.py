from copy import deepcopy

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

    DEFAULT_POS_GAIN = 0.85
    DEFAULT_NEG_GAIN = 1.10

    APOLOGY_RECOVERY_FRACTION = 0.25

    RELATIONSHIP_EVENT_ALIASES = {
        "apology": "apology",
        "apologize": "apologize",
        "steal": "theft",
        "theft": "theft",
        "betray": "betrayal",
        "betrayal": "betrayal",
    }

    RELATIONSHIP_EVENT_SPECS = {
        "neutral": {
            "mode": "exact",
            "trust": 0.0,
            "public_trust": 0.0,
        },
        "greet": {
            "mode": "dynamic",
            "channel": "pos",
            "base_amount": 0.04,
            "attachment": 0.01,
            "public_trust": 0.02,
        },
        "help": {
            "mode": "dynamic",
            "channel": "pos",
            "base_amount": 0.12,
            "attachment": 0.05,
            "public_trust": 0.20,
        },
        "cooperate": {
            "mode": "exact",
            "trust": 0.08,
            "attachment": 0.02,
            "public_trust": 0.08,
        },
        "gift": {
            "mode": "dynamic",
            "channel": "pos",
            "base_amount": 0.16,
            "public_trust": 0.16,
        },
        "apology": {
            "mode": "exact",
            "trust": 0.05,
            "recovery_fraction": 0.25,
            "public_trust": 0.05,
        },
        "apologize": {
            "mode": "dynamic",
            "channel": "pos",
            "base_amount": 0.10,
            "public": False,
        },
        "disengage": {
            "mode": "exact",
            "trust": 0.01,
            "public_trust": 0.01,
        },
        "pressure": {
            "mode": "exact",
            "trust": -0.08,
            "public_trust": -0.08,
        },
        "manipulate": {
            "mode": "exact",
            "trust": -0.10,
            "public_trust": -0.10,
        },
        "deceive": {
            "mode": "exact",
            "trust": -0.15,
            "public_trust": -0.15,
        },
        "insult": {
            "mode": "dynamic",
            "channel": "neg",
            "base_amount": 0.15,
            "public_trust": -0.30,
        },
        "threat": {
            "mode": "dynamic",
            "channel": "neg",
            "base_amount": 0.22,
            "public_trust": -0.50,
        },
        "theft": {
            "mode": "dynamic",
            "channel": "neg",
            "base_amount": 0.45,
            "attachment": -0.20,
            "public_trust": -0.60,
        },
        "attack": {
            "mode": "dynamic",
            "channel": "neg",
            "base_amount": 0.35,
            "public_trust": -0.35,
        },
        "betrayal": {
            "mode": "dynamic",
            "channel": "neg",
            "base_amount": 0.70,
            "attachment": -0.50,
            "public_trust": -0.80,
        },
    }

    RELATIONSHIP_EVENT_MAP = {
        event_name: (
            spec["channel"],
            spec["base_amount"],
        )
        for event_name, spec in (
            RELATIONSHIP_EVENT_SPECS.items()
        )
        if spec["mode"] == "dynamic"
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

    def _new_relationship_state(self) -> dict:
        """Return fresh internal state for one relationship pair."""
        return {
            "pos": 0.0,
            "neg": 0.0,
            "attachment": 0.0,
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
            "positive_reservoir_cap": (
                self.positive_reservoir_cap
            ),
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
            "high_severity_threshold": (
                self.high_severity_threshold
            ),
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
        }

    def ensure_pair(self, a: str, b: str):
        a, b = normalize_pair_ids(a, b)
        key = self._key(a, b)

        rel = self._rels.get(key)

        if rel is None:
            rel = self._new_relationship_state()
            self._rels[key] = rel

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

    @classmethod
    def public_event_map(cls) -> dict:
        event_map = {}

        for event_name, spec in (
            cls.RELATIONSHIP_EVENT_SPECS.items()
        ):
            if spec.get("public", True) is False:
                continue

            deltas = {
                "trust": spec.get(
                    "public_trust",
                    spec.get(
                        "trust",
                        0.0,
                    ),
                ),
            }

            attachment = spec.get(
                "attachment",
                0.0,
            )

            if attachment != 0.0:
                deltas["attachment"] = (
                    attachment
                )

            event_map[event_name] = deltas

        return deepcopy(event_map)

    def _resolve_event_spec(
        self,
        event: str,
        event_spec: dict | None,
    ) -> dict:
        if event_spec is not None:
            if not isinstance(event_spec, dict):
                raise ValueError(
                    "relationship event specification "
                    "must be a dict"
                )

            resolved = {
                "mode": "exact",
                "trust": validate_finite_number(
                    event_spec.get(
                        "trust",
                        0.0,
                    ),
                    (
                        "relationship event "
                        "trust delta"
                    ),
                ),
                "attachment": (
                    validate_finite_number(
                        event_spec.get(
                            "attachment",
                            0.0,
                        ),
                        (
                            "relationship event "
                            "attachment delta"
                        ),
                    )
                ),
                "extra_deltas": {},
            }

            for key, value in event_spec.items():
                if key in (
                    "trust",
                    "attachment",
                ):
                    continue

                resolved[
                    "extra_deltas"
                ][key] = validate_finite_number(
                    value,
                    (
                        "relationship event "
                        f"delta {key}"
                    ),
                )

            return resolved

        built_in = (
            self.RELATIONSHIP_EVENT_SPECS.get(
                event
            )
        )

        if built_in is not None:
            resolved = deepcopy(
                built_in
            )

            resolved.setdefault(
                "attachment",
                0.0,
            )

            resolved.setdefault(
                "extra_deltas",
                {},
            )

            return resolved

        event_map = self.RELATIONSHIP_EVENT_MAP

        if event not in event_map:
            raise ValueError(
                f"Unknown relationship event: {event}"
            )

        channel, base_amount = event_map[event]

        return {
            "mode": "dynamic",
            "channel": channel,
            "base_amount": (
                validate_non_negative_finite(
                    base_amount,
                    (
                        "relationship event "
                        "base amount"
                    ),
                )
            ),
            "attachment": 0.0,
            "extra_deltas": {},
        }

    def _apply_exact_event(
        self,
        a: str,
        b: str,
        event: str,
        intensity: float,
        spec: dict,
    ) -> dict:
        rel = self.ensure_pair(
            a,
            b,
        )

        before_trust = (
            rel.get("pos", 0.0)
            - rel.get("neg", 0.0)
        )

        before_state = rel.get(
            "state",
            self._classify_state(
                before_trust
            ),
        )

        requested_delta = (
            spec["trust"]
            * intensity
        )

        if event == "apology":
            if before_trust >= 0.0:
                trust_delta = 0.0
            else:
                trust_delta = min(
                    requested_delta,
                    (
                        -before_trust
                        * spec.get(
                            "recovery_fraction",
                            (
                                self
                                .APOLOGY_RECOVERY_FRACTION
                            ),
                        )
                    ),
                )
        else:
            trust_delta = requested_delta

        if trust_delta > 0.0:
            rel["pos"] = (
                rel.get("pos", 0.0)
                + trust_delta
            )

            channel = "pos"

        elif trust_delta < 0.0:
            rel["neg"] = (
                rel.get("neg", 0.0)
                + abs(trust_delta)
            )

            channel = "neg"

        else:
            channel = (
                "pos"
                if spec["trust"] >= 0.0
                else "neg"
            )

        attachment_delta = (
            spec.get(
                "attachment",
                0.0,
            )
            * intensity
        )

        if attachment_delta != 0.0:
            rel["attachment"] = (
                rel.get(
                    "attachment",
                    0.0,
                )
                + attachment_delta
            )

        for key, value in spec.get(
            "extra_deltas",
            {},
        ).items():
            rel[key] = (
                rel.get(
                    key,
                    0.0,
                )
                + (value * intensity)
            )

        trust = (
            rel.get("pos", 0.0)
            - rel.get("neg", 0.0)
        )

        after_state = self._classify_state(
            trust
        )

        transition = None

        if before_state != after_state:
            transition = (
                before_state,
                after_state,
            )

        trigger = self._trigger_for_transition(
            before_state,
            after_state,
        )

        maturity = rel.get(
            "maturity",
            0.0,
        )

        maturity_modifier = max(
            0.0,
            1.0 - maturity,
        )

        volatility = rel.get(
            "volatility",
            self.volatility,
        )

        positive_volatility = rel.get(
            "positive_volatility",
            self.positive_volatility,
        )

        negative_volatility = rel.get(
            "negative_volatility",
            self.negative_volatility,
        )

        recent_event_magnitude = rel.get(
            "recent_event_magnitude",
            0.0,
        )

        diagnostics = self._build_diagnostics(
            event=event,
            channel=channel,
            base_amount=abs(
                spec["trust"]
            ),
            effective_gain=abs(
                trust_delta
            ),
            before_state=before_state,
            after_state=after_state,
            before_trust=before_trust,
            after_trust=trust,
            maturity=maturity,
            maturity_modifier=(
                maturity_modifier
            ),
            volatility=volatility,
            positive_volatility=(
                positive_volatility
            ),
            negative_volatility=(
                negative_volatility
            ),
            transition=transition,
            trigger=trigger,
            shock_applied=False,
            stability_breach=0.0,
            high_severity_shock=False,
            relative_shock=False,
            shock_multiplier=1.0,
            event_maturity_modifier=(
                maturity_modifier
            ),
            recent_event_magnitude=(
                recent_event_magnitude
            ),
        )

        recent_decay = rel.get(
            "recent_event_decay",
            self.recent_event_decay,
        )

        rel["recent_event_magnitude"] = (
            recent_event_magnitude
            * recent_decay
            + abs(requested_delta)
            * (1.0 - recent_decay)
        )

        maturity_gain = rel.get(
            "maturity_gain",
            self.maturity_gain,
        )

        maturity_cap = rel.get(
            "maturity_cap",
            self.maturity_cap,
        )

        rel["maturity"] = min(
            maturity_cap,
            maturity + maturity_gain,
        )

        rel["trust"] = trust
        rel["state"] = after_state
        rel["transition"] = transition
        rel["trigger"] = trigger
        rel["last_event"] = event
        rel["diagnostics"] = diagnostics

        return self.get_relationship(
            a,
            b,
        )

    def apply_event(
        self,
        a: str,
        b: str,
        event: str,
        intensity: float = 1.0,
        event_spec: dict | None = None,
    ):
        # Validate every input before creating relationship state.
        # A rejected event must not create a pair or mutate neighbors.
        a, b = normalize_pair_ids(a, b)

        event = normalize_event(event)
        event = self.RELATIONSHIP_EVENT_ALIASES.get(
            event,
            event,
        )

        intensity = validate_unit_interval(
            intensity,
            "relationship event intensity",
        )

        resolved_spec = self._resolve_event_spec(
            event,
            event_spec,
        )

        if resolved_spec["mode"] == "exact":
            return self._apply_exact_event(
                a,
                b,
                event,
                intensity,
                resolved_spec,
            )

        channel = resolved_spec["channel"]
        base_amount = resolved_spec[
            "base_amount"
        ]

        if channel not in ("pos", "neg"):
            raise RuntimeError(
                "Relationship event map contains an unsupported "
                f"channel: {channel}"
            )

        rel = self.ensure_pair(a, b)
        before_trust = rel.get("pos", 0.0) - rel.get("neg", 0.0)
        before_state = rel.get("state", self._classify_state(before_trust))

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

        else:
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

        attachment_delta = (
            resolved_spec.get(
                "attachment",
                0.0,
            )
            * intensity
        )

        if attachment_delta != 0.0:
            rel["attachment"] = (
                rel.get(
                    "attachment",
                    0.0,
                )
                + attachment_delta
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
        intensity: float = 1.0,
    ):
        """
        Apply one direct event and all observer effects atomically.

        Every public input is validated before mutation. Any later
        exception restores relationships, neighbors, and propagation
        history to their exact pre-call state.
        """
        source, target = normalize_pair_ids(
            source,
            target,
        )

        event = normalize_event(
            event
        )

        resolved_event = (
            self
            .RELATIONSHIP_EVENT_ALIASES
            .get(
                event,
                event,
            )
        )

        intensity = validate_unit_interval(
            intensity,
            "social event intensity",
        )

        event_specs = getattr(
            self,
            "RELATIONSHIP_EVENT_SPECS",
            {},
        )

        if (
            resolved_event not in event_specs
            and resolved_event
            not in self.RELATIONSHIP_EVENT_MAP
        ):
            raise ValueError(
                "Unknown relationship event: "
                f"{resolved_event}"
            )

        if observers is None:
            raw_observers = []

        elif isinstance(
            observers,
            (
                list,
                tuple,
            ),
        ):
            raw_observers = list(
                observers
            )

        else:
            raise ValueError(
                "social observers must be "
                "a list or tuple"
            )

        if weights is None:
            weights = {}

        elif not isinstance(
            weights,
            dict,
        ):
            raise ValueError(
                "social propagation weights "
                "must be a dict"
            )

        validated_observers = []
        missing = object()

        for raw_observer in raw_observers:
            observer = normalize_id(
                raw_observer,
                "social observer id",
            )

            if observer in (
                source,
                target,
            ):
                continue

            try:
                raw_weight = weights.get(
                    raw_observer,
                    missing,
                )

            except TypeError:
                raw_weight = missing

            if raw_weight is missing:
                raw_weight = weights.get(
                    observer,
                    1.0,
                )

            weight = validate_unit_interval(
                raw_weight,
                (
                    "social propagation weight "
                    f"for {observer}"
                ),
            )

            validated_observers.append(
                (
                    observer,
                    weight,
                )
            )

        relationships_before = deepcopy(
            self._rels
        )

        neighbors_before = deepcopy(
            self._neighbors
        )

        propagation_before = deepcopy(
            self._propagation_log
        )

        try:
            direct = self.apply_event(
                source,
                target,
                event,
                intensity=intensity,
            )

            diagnostics = (
                direct.get(
                    "diagnostics",
                    {},
                )
                or {}
            )

            heat = (
                self
                ._social_heat_from_diagnostics(
                    diagnostics
                )
            )

            direction = diagnostics.get(
                "direction"
            )

            pressure = diagnostics.get(
                "pressure"
            )

            severity = diagnostics.get(
                "severity",
                0.0,
            )

            propagated = []

            for (
                observer,
                weight,
            ) in validated_observers:
                if direction == "negative":
                    trust_delta = (
                        -0.20
                        * heat
                        * weight
                    )

                elif direction == "positive":
                    trust_delta = (
                        0.05
                        * heat
                        * weight
                    )

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
                "pressure_delta": (
                    0.20 * heat
                ),
                "fear_delta": (
                    0.08 * heat
                ),
                "resentment_delta": (
                    0.08 * heat
                ),
                "order_delta": (
                    -0.04 * heat
                ),
                "guard_suspicion_delta": (
                    0.35 * heat
                ),
            }

            packet = {
                "source": source,
                "target": target,
                "event": event,
                "intensity": intensity,
                "heat": heat,
                "severity": severity,
                "pressure": pressure,
                "direct": direct,
                "propagated": propagated,
                "world_effects": world_effects,
            }

            self._propagation_log.append(
                deepcopy(packet)
            )

            if len(
                self._propagation_log
            ) > 25:
                self._propagation_log.pop(
                    0
                )

            return deepcopy(
                packet
            )

        except Exception:
            self._rels.clear()

            self._rels.update(
                relationships_before
            )

            self._neighbors.clear()

            self._neighbors.update(
                neighbors_before
            )

            self._propagation_log[:] = (
                propagation_before
            )

            raise

    def get_relationship(self, a: str, b: str):
        """
        Return a copied public relationship packet without mutating state.

        Reading an unknown pair reports the neutral default view but does
        not create relationship storage or neighbor edges.
        """
        a, b = normalize_pair_ids(a, b)
        rel = self._rels.get(
            self._key(a, b)
        )

        if rel is None:
            rel = self._new_relationship_state()

        trust = (
            rel.get("pos", 0.0)
            - rel.get("neg", 0.0)
        )

        return {
            "trust": trust,
            "state": self._classify_state(trust),
            "transition": deepcopy(
                rel.get("transition")
            ),
            "trigger": deepcopy(
                rel.get("trigger")
            ),
            "diagnostics": deepcopy(
                rel.get("diagnostics")
            ),
            "maturity": rel.get(
                "maturity",
                0.0,
            ),
            "volatility": rel.get(
                "volatility",
                self.volatility,
            ),
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
                    "transition": deepcopy(transition),
                    "trigger": deepcopy(trigger),
                    "diagnostics": deepcopy(diagnostics),
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

        out = deepcopy(rel)
        out["trust"] = pos - neg

        return out

    def all(self):
        return deepcopy(self._rels)

    def neighbors(self, agent_id: str):
        agent_id = normalize_id(agent_id, "agent id")

        return list(self._neighbors.get(agent_id, []))

    def propagation_log(self):
        return deepcopy(self._propagation_log)