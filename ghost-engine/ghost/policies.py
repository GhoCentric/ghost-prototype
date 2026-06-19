"""
Reusable Ghost policy runtime.

These policies are deterministic helpers.
They do not generate dialogue.
They do not mutate Ghost unless the caller chooses to apply results.
"""

from dataclasses import asdict, dataclass, field
from typing import Any


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class CommerceDecision:
    sale_access: str
    purchase_allowed: bool
    price_visible: bool
    reason: str = ""
    blocked_effects: tuple[str, ...] = field(default_factory=tuple)
    allowed_effects: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PriceDecision:
    item: str
    base_price: int
    final_price: int
    relationship_state: str
    sale_access: str
    changed: bool = False
    raw_changed: bool = False
    passive_decay: bool = False
    reason: str = ""
    anchor_price: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class LawDecision:
    status: str
    action: str
    severity: float
    warning_count: int = 0
    reason: str = ""
    allowed_effects: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ReintegrationDecision:
    allowed: bool
    trust_floor: float
    recovery_multiplier: float
    resistance_remaining: int
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class CommercePolicy:
    """
    Decides whether commerce is allowed.
    """

    def evaluate_service(
        self,
        severity: float = 0.0,
        blacklisted: bool = False,
        town_status: str = "normal",
        claim_blocked_effects=(),
    ) -> CommerceDecision:
        blocked = tuple(claim_blocked_effects or ())

        if "free_item" in blocked or "price_waiver" in blocked:
            return CommerceDecision(
                sale_access="normal",
                purchase_allowed=True,
                price_visible=True,
                reason="unverified claim cannot change commerce state",
                blocked_effects=blocked,
                allowed_effects=("normal_purchase_only",),
            )

        if town_status == "expelled":
            return CommerceDecision(
                sale_access="refused",
                purchase_allowed=False,
                price_visible=False,
                reason="town expelled player",
                blocked_effects=("purchase",),
            )

        if blacklisted or severity >= 0.85:
            return CommerceDecision(
                sale_access="refused",
                purchase_allowed=False,
                price_visible=False,
                reason="service refused due to high risk",
                blocked_effects=("purchase",),
            )

        if severity >= 0.35:
            return CommerceDecision(
                sale_access="restricted",
                purchase_allowed=True,
                price_visible=True,
                reason="restricted service due to risk",
                allowed_effects=("marked_up_purchase",),
            )

        return CommerceDecision(
            sale_access="normal",
            purchase_allowed=True,
            price_visible=True,
            reason="normal service",
            allowed_effects=("purchase",),
        )


class PricingPolicy:
    """
    Computes item price from relationship, risk, and service access.
    """

    RELATIONSHIP_MULTIPLIERS = {
        "loyal": 0.50,
        "friendly": 1.00,
        "neutral": 1.25,
        "unfriendly": 1.75,
        "hostile": 2.00,
    }

    def compute_price(
        self,
        item: str,
        base_price: int,
        relationship_state: str = "neutral",
        sale_access: str = "normal",
        economic_modifier: float = 1.0,
        severity: float = 0.0,
        prior_record: dict[str, Any] | None = None,
    ) -> PriceDecision:
        prior_record = prior_record or {}

        rel_state = relationship_state or "neutral"
        mult = self.RELATIONSHIP_MULTIPLIERS.get(rel_state, 1.25)

        price = int(base_price * mult * economic_modifier)

        if sale_access == "restricted":
            risk_mult = 2.0 + clamp(severity, 0.0, 1.0)
            price = int(base_price * risk_mult * economic_modifier)

        elif sale_access == "refused":
            price = 0

        previous_price = int(prior_record.get("current_price", price))
        previous_access = str(prior_record.get("sale_access", "normal"))

        raw_changed = bool(previous_price != price)

        passive_decay = bool(
            raw_changed
            and sale_access == "restricted"
            and previous_access == "restricted"
        )

        changed = bool(raw_changed and not passive_decay)

        reason = ""

        if changed:
            if sale_access == "restricted":
                reason = "restricted service markup"
            elif sale_access == "refused":
                reason = "service refused"
            else:
                reason = "relationship or market price changed"

        elif passive_decay:
            reason = "passive restricted-service price decay"

        anchor = int(prior_record.get("anchor_price", 0) or 0)

        if sale_access == "restricted" and changed:
            anchor = price

        elif sale_access == "restricted" and anchor <= 0:
            anchor = price

        elif sale_access != "restricted":
            anchor = 0

        return PriceDecision(
            item=item,
            base_price=int(base_price),
            final_price=int(price),
            relationship_state=rel_state,
            sale_access=sale_access,
            changed=changed,
            raw_changed=raw_changed,
            passive_decay=passive_decay,
            reason=reason,
            anchor_price=int(anchor),
        )


class LawPolicy:
    """
    Escalates social conflict into warnings, detention, arrest, or expulsion.
    """

    def evaluate(
        self,
        severity: float,
        argument_pressure: int = 0,
        warning_count: int = 0,
        post_arrest_watch: int = 0,
        release_grace: int = 0,
    ) -> LawDecision:
        severity = clamp(float(severity), 0.0, 5.0)

        if release_grace > 0:
            return LawDecision(
                status="grace",
                action="watch",
                severity=severity,
                warning_count=warning_count,
                reason="release grace active",
            )

        if severity >= 1.6 and post_arrest_watch == 0:
            return LawDecision(
                status="detention",
                action="detain",
                severity=severity,
                warning_count=warning_count,
                reason="severity exceeded detention threshold",
                allowed_effects=("detention_menu",),
            )

        if argument_pressure >= 4:
            return LawDecision(
                status="ejection",
                action="call_guards",
                severity=severity,
                warning_count=warning_count,
                reason="argument pressure exceeded ejection threshold",
                allowed_effects=("guard_warning",),
            )

        if warning_count >= 3:
            return LawDecision(
                status="removed",
                action="remove_from_stall",
                severity=severity,
                warning_count=warning_count,
                reason="warning count exceeded threshold",
                allowed_effects=("trespass_detention",),
            )

        if warning_count > 0:
            return LawDecision(
                status="warning",
                action="warn",
                severity=severity,
                warning_count=warning_count,
                reason="active guard warning",
                allowed_effects=("warning",),
            )

        return LawDecision(
            status="normal",
            action="none",
            severity=severity,
            warning_count=warning_count,
            reason="no legal escalation",
        )


class ReintegrationPolicy:
    """
    Models recovery after punishment.
    """

    def evaluate(
        self,
        served_punishment: bool,
        current_trust: float,
        arrest_count: int = 0,
        resistance_remaining: int = 0,
    ) -> ReintegrationDecision:
        if not served_punishment:
            return ReintegrationDecision(
                allowed=True,
                trust_floor=-1.0,
                recovery_multiplier=1.0,
                resistance_remaining=resistance_remaining,
                reason="no punishment state active",
            )

        trust_floor = -0.45
        recovery_multiplier = 0.5

        if arrest_count >= 2:
            recovery_multiplier = 0.35

        if arrest_count >= 3:
            recovery_multiplier = 0.20

        if resistance_remaining > 0:
            return ReintegrationDecision(
                allowed=False,
                trust_floor=trust_floor,
                recovery_multiplier=recovery_multiplier,
                resistance_remaining=resistance_remaining,
                reason="reintegration resistance active",
            )

        return ReintegrationDecision(
            allowed=True,
            trust_floor=trust_floor,
            recovery_multiplier=recovery_multiplier,
            resistance_remaining=0,
            reason="reintegration allowed with reduced recovery",
        )