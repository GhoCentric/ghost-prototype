"""
Raid-planning domain for Ghost Revolution.

This module owns raid-plan and active-raid state. It never imports the
campaign facade, Ghost runtime, or terminal presentation. The campaign
facade supplies immutable RaidContext values and applies explicit
RaidOutcome inventory deltas.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from .config import (
    SHIELD_TYPES,
    WEAPON_TIERS,
    WEAPON_TYPES,
)



def _frozen_mapping(
    values: Mapping[str, Any],
) -> Mapping[str, Any]:
    """
    Copy a mapping before exposing it through a frozen value object.

    ``frozen=True`` prevents attribute replacement only. This helper
    also prevents callers from mutating nested map contents.
    """

    return MappingProxyType(dict(values))


@dataclass(frozen=True)
class RaidContext:
    target: str
    location: str
    valid_target: bool
    town_name: str = ""
    town_condition: str = ""
    town_rebel_controlled: bool = False
    available_warriors: int = 0
    food: int = 0
    weapon_stock: Mapping[str, int] = field(
        default_factory=dict
    )
    shield_stock: Mapping[str, int] = field(
        default_factory=dict
    )
    leader_weapon: str = ""
    leader_weapon_tier: str = "common"
    leader_armor: str = "none"
    training_level: int = 0
    town_support: int = 0
    intel_level: int = 0
    guards_defeated: int = 0
    camp: Mapping[str, object] = field(
        default_factory=dict
    )
    requirement: Mapping[str, int] = field(
        default_factory=dict
    )
    phase_number: int = 1
    phase_day: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "weapon_stock",
            _frozen_mapping(self.weapon_stock),
        )
        object.__setattr__(
            self,
            "shield_stock",
            _frozen_mapping(self.shield_stock),
        )
        object.__setattr__(
            self,
            "camp",
            _frozen_mapping(self.camp),
        )
        object.__setattr__(
            self,
            "requirement",
            _frozen_mapping(self.requirement),
        )


@dataclass(frozen=True)
class RaidOutcome:
    note: str
    ok: bool
    food_delta: int = 0
    weapon_stock_deltas: Mapping[str, int] = field(
        default_factory=dict
    )
    shield_stock_deltas: Mapping[str, int] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "weapon_stock_deltas",
            _frozen_mapping(self.weapon_stock_deltas),
        )
        object.__setattr__(
            self,
            "shield_stock_deltas",
            _frozen_mapping(self.shield_stock_deltas),
        )

@dataclass
class RaidPlanState:
    target: str
    force: int
    weapon_issue: dict[str, int]
    shield_issue: dict[str, int]
    camp: str
    warlord: str
    knight: str

    @classmethod
    def start(
        cls,
        context: RaidContext,
    ) -> "RaidPlanState":
        return cls(
            target=context.target,
            force=0,
            weapon_issue={
                weapon: 0
                for weapon in WEAPON_TYPES
            },
            shield_issue={
                shield: 0
                for shield in SHIELD_TYPES
            },
            camp=str(context.camp["name"]),
            warlord=str(context.camp["warlord"]),
            knight=str(context.camp["knight"]),
        )

    @classmethod
    def from_snapshot(
        cls,
        snapshot: dict,
    ) -> "RaidPlanState":
        return cls(
            target=str(snapshot["target"]),
            force=int(snapshot["force"]),
            weapon_issue={
                weapon: int(snapshot["weapon_issue"][weapon])
                for weapon in WEAPON_TYPES
            },
            shield_issue={
                shield: int(snapshot["shield_issue"][shield])
                for shield in SHIELD_TYPES
            },
            camp=str(snapshot["camp"]),
            warlord=str(snapshot["warlord"]),
            knight=str(snapshot["knight"]),
        )

    def snapshot(self) -> dict:
        return {
            "target": self.target,
            "force": self.force,
            "weapon_issue": deepcopy(self.weapon_issue),
            "shield_issue": deepcopy(self.shield_issue),
            "camp": self.camp,
            "warlord": self.warlord,
            "knight": self.knight,
        }


@dataclass
class ActiveRaidState:
    target: str
    town: str
    force: int
    weapon_issue: dict[str, int]
    shield_issue: dict[str, int]
    food_committed: int
    intel_level: int
    intel_bonus: int
    readiness: int
    odds: str
    camp: str
    knight: str
    warlord: str
    phase_number: int
    phase_day: int

    @classmethod
    def from_snapshot(
        cls,
        snapshot: dict,
    ) -> "ActiveRaidState":
        return cls(
            target=str(snapshot["target"]),
            town=str(snapshot["town"]),
            force=int(snapshot["force"]),
            weapon_issue=deepcopy(snapshot["weapon_issue"]),
            shield_issue=deepcopy(snapshot["shield_issue"]),
            food_committed=int(snapshot["food_committed"]),
            intel_level=int(snapshot["intel_level"]),
            intel_bonus=int(snapshot["intel_bonus"]),
            readiness=int(snapshot["readiness"]),
            odds=str(snapshot["odds"]),
            camp=str(snapshot["camp"]),
            knight=str(snapshot["knight"]),
            warlord=str(snapshot["warlord"]),
            phase_number=int(snapshot["phase_number"]),
            phase_day=int(snapshot["phase_day"]),
        )

    def snapshot(self) -> dict:
        return {
            "target": self.target,
            "town": self.town,
            "force": self.force,
            "weapon_issue": deepcopy(self.weapon_issue),
            "shield_issue": deepcopy(self.shield_issue),
            "food_committed": self.food_committed,
            "intel_level": self.intel_level,
            "intel_bonus": self.intel_bonus,
            "readiness": self.readiness,
            "odds": self.odds,
            "camp": self.camp,
            "knight": self.knight,
            "warlord": self.warlord,
            "phase_number": self.phase_number,
            "phase_day": self.phase_day,
        }


class RaidSystem:
    """
    Functional-core raid subsystem.

    Reservations and deployment state live here. Campaign inventory
    changes are returned as explicit deltas rather than mutated through
    a broad game context.
    """

    def __init__(self) -> None:
        self._plan: RaidPlanState | None = None
        self._active: ActiveRaidState | None = None

    @property
    def plan(self) -> dict | None:
        if self._plan is None:
            return None

        return self._plan.snapshot()

    @property
    def active(self) -> dict | None:
        if self._active is None:
            return None

        return self._active.snapshot()

    def replace_plan(self, plan: dict | None) -> None:
        self._plan = (
            RaidPlanState.from_snapshot(deepcopy(plan))
            if plan
            else None
        )

    def replace_active(self, active: dict | None) -> None:
        self._active = (
            ActiveRaidState.from_snapshot(deepcopy(active))
            if active
            else None
        )

    def active_summary(self) -> dict | None:
        return self.active

    def deployed_warriors(self) -> int:
        return self._active.force if self._active else 0

    def issued_weapons(self) -> int:
        total = 0

        if self._plan:
            total += sum(self._plan.weapon_issue.values())

        if self._active:
            total += sum(self._active.weapon_issue.values())

        return total

    def issued_shields(self) -> int:
        total = 0

        if self._plan:
            total += sum(self._plan.shield_issue.values())

        if self._active:
            total += sum(self._active.shield_issue.values())

        return total

    def readiness(self, context: RaidContext) -> dict:
        if not context.valid_target:
            raise ValueError(
                f"Unknown raid target: {context.target}"
            )

        plan = self._plan

        if plan is None or plan.target != context.target:
            force = 0
            weapon_issue = {
                weapon: 0
                for weapon in WEAPON_TYPES
            }
            shield_issue = {
                shield: 0
                for shield in SHIELD_TYPES
            }
        else:
            force = plan.force
            weapon_issue = deepcopy(plan.weapon_issue)
            shield_issue = deepcopy(plan.shield_issue)

        issued_weapons = sum(weapon_issue.values())
        issued_shields = sum(shield_issue.values())
        intel_bonus = context.intel_level * 2
        training_bonus = context.training_level * 2
        leader_bonus = (
            WEAPON_TIERS[context.leader_weapon_tier] * 3
        )

        readiness = (
            force
            + issued_weapons * 2
            + issued_shields
            + intel_bonus
            + training_bonus
            + leader_bonus
            + context.town_support * 5
            + context.guards_defeated * 2
            - int(context.camp["garrison"])
        )

        if readiness >= 25:
            odds = "FAVORABLE"
        elif readiness >= 0:
            odds = "CONTESTED"
        elif readiness >= -25:
            odds = "LOW"
        else:
            odds = "VERY LOW"

        return {
            "target": context.target,
            "town": context.town_name,
            "condition": context.town_condition,
            "camp": context.camp["name"],
            "knight": context.camp["knight"],
            "warlord": context.camp["warlord"],
            "garrison": context.camp["garrison"],
            "warriors": force,
            "available_warriors": context.available_warriors,
            "food": context.food,
            "food_required": context.requirement["food_required"],
            "weapon_stock": dict(context.weapon_stock),
            "weapon_stock_total": sum(
                context.weapon_stock.values()
            ),
            "weapon_issue": weapon_issue,
            "issued_weapons": issued_weapons,
            "shield_stock": dict(context.shield_stock),
            "shield_issue": shield_issue,
            "issued_shields": issued_shields,
            "leader_weapon": context.leader_weapon,
            "leader_armor": context.leader_armor,
            "training_level": context.training_level,
            "recommended_warriors": (
                context.requirement["recommended_warriors"]
            ),
            "recommended_weapons": (
                context.requirement["recommended_weapons"]
            ),
            "town_support": context.town_support,
            "intel_level": context.intel_level,
            "intel_bonus": intel_bonus,
            "readiness": readiness,
            "odds": odds,
            "ready": (
                force
                >= context.requirement["recommended_warriors"]
                and context.food
                >= context.requirement["food_required"]
                and issued_weapons
                >= context.requirement["recommended_weapons"]
            ),
        }

    def open_plan(self, context: RaidContext) -> RaidOutcome:
        if context.location != "base":
            return RaidOutcome(
                "Raid planning can only happen at the hidden base.",
                ok=False,
            )

        if not context.valid_target:
            return RaidOutcome(
                "Unknown raid target.",
                ok=False,
            )

        if self._active:
            return RaidOutcome(
                "A raid is already active. Resolve it before planning "
                "another.",
                ok=False,
            )

        if context.town_rebel_controlled:
            return RaidOutcome(
                f"{context.town_name} is already under rebel control.",
                ok=False,
            )

        release = self._release_plan()
        self._plan = RaidPlanState.start(context)

        return RaidOutcome(
            f"Raid plan opened for {context.town_name}.",
            ok=True,
            weapon_stock_deltas=release.weapon_stock_deltas,
            shield_stock_deltas=release.shield_stock_deltas,
        )

    def cancel_plan(self) -> RaidOutcome:
        if self._active:
            return RaidOutcome(
                "The raid force is already deployed and cannot be "
                "cancelled.",
                ok=False,
            )

        if self._plan is None:
            return RaidOutcome(
                "There is no raid plan to cancel.",
                ok=False,
            )

        target = self._plan.target
        release = self._release_plan()

        return RaidOutcome(
            (
                f"Raid plan for {target.title()} cancelled. "
                "Reserved gear returned to base stock."
            ),
            ok=True,
            weapon_stock_deltas=release.weapon_stock_deltas,
            shield_stock_deltas=release.shield_stock_deltas,
        )

    def release_plan(self) -> RaidOutcome:
        return self._release_plan()

    def set_force(
        self,
        context: RaidContext,
        amount: int,
    ) -> RaidOutcome:
        if self._plan is None:
            return RaidOutcome(
                "Open a raid plan first.",
                ok=False,
            )

        if not isinstance(amount, int) or amount < 0:
            return RaidOutcome(
                "Raid force must be a whole number.",
                ok=False,
            )

        if amount > context.available_warriors:
            return RaidOutcome(
                "You cannot send more warriors than are assigned.",
                ok=False,
            )

        if (
            self.issued_weapons() > amount
            or self.issued_shields() > amount
        ):
            return RaidOutcome(
                "Reduce issued weapons or shields before lowering the "
                "raid force.",
                ok=False,
            )

        self._plan.force = amount

        return RaidOutcome(
            f"Raid force set to {amount} warriors.",
            ok=True,
        )

    def set_weapon_issue(
        self,
        context: RaidContext,
        weapon: str,
        amount: int,
    ) -> RaidOutcome:
        if self._plan is None:
            return RaidOutcome(
                "Open a raid plan first.",
                ok=False,
            )

        if weapon not in WEAPON_TYPES:
            return RaidOutcome(
                "Unknown weapon type.",
                ok=False,
            )

        if not isinstance(amount, int) or amount < 0:
            return RaidOutcome(
                "Weapon issue must be a whole number.",
                ok=False,
            )

        current = self._plan.weapon_issue[weapon]
        available = context.weapon_stock[weapon] + current

        if amount > available:
            return RaidOutcome(
                (
                    f"Only {available} {weapon}s are available "
                    "for this raid."
                ),
                ok=False,
            )

        proposed_total = (
            self.issued_weapons()
            - current
            + amount
        )

        if proposed_total > self._plan.force:
            return RaidOutcome(
                "You cannot issue more weapons than raid warriors.",
                ok=False,
            )

        difference = amount - current
        self._plan.weapon_issue[weapon] = amount

        return RaidOutcome(
            f"{weapon.title()}s reserved for raid: {amount}.",
            ok=True,
            weapon_stock_deltas={weapon: -difference},
        )

    def set_shield_issue(
        self,
        context: RaidContext,
        shield: str,
        amount: int,
    ) -> RaidOutcome:
        if self._plan is None:
            return RaidOutcome(
                "Open a raid plan first.",
                ok=False,
            )

        if shield not in SHIELD_TYPES:
            return RaidOutcome(
                "Unknown shield tier.",
                ok=False,
            )

        if not isinstance(amount, int) or amount < 0:
            return RaidOutcome(
                "Shield issue must be a whole number.",
                ok=False,
            )

        current = self._plan.shield_issue[shield]
        available = context.shield_stock[shield] + current

        if amount > available:
            return RaidOutcome(
                (
                    f"Only {available} {shield} shields are available "
                    "for this raid."
                ),
                ok=False,
            )

        proposed_total = (
            self.issued_shields()
            - current
            + amount
        )

        if proposed_total > self._plan.force:
            return RaidOutcome(
                "You cannot issue more shields than raid warriors.",
                ok=False,
            )

        difference = amount - current
        self._plan.shield_issue[shield] = amount

        return RaidOutcome(
            f"{shield.title()} shields reserved for raid: {amount}.",
            ok=True,
            shield_stock_deltas={shield: -difference},
        )

    def commit(self, context: RaidContext) -> RaidOutcome:
        if context.location != "base":
            return RaidOutcome(
                "Raid commitment can only happen at the hidden base.",
                ok=False,
            )

        if self._active:
            return RaidOutcome(
                "A raid is already active. Resolve it before committing "
                "another.",
                ok=False,
            )

        if self._plan is None:
            return RaidOutcome(
                "Open a raid plan first.",
                ok=False,
            )

        readiness = self.readiness(context)

        if not readiness["ready"]:
            return RaidOutcome(
                "Raid plan is not ready. Meet force, food, and weapon "
                "requirements before commitment.",
                ok=False,
            )

        self._active = ActiveRaidState(
            target=context.target,
            town=str(readiness["town"]),
            force=self._plan.force,
            weapon_issue=deepcopy(self._plan.weapon_issue),
            shield_issue=deepcopy(self._plan.shield_issue),
            food_committed=int(readiness["food_required"]),
            intel_level=int(readiness["intel_level"]),
            intel_bonus=int(readiness["intel_bonus"]),
            readiness=int(readiness["readiness"]),
            odds=str(readiness["odds"]),
            camp=str(readiness["camp"]),
            knight=str(readiness["knight"]),
            warlord=str(readiness["warlord"]),
            phase_number=context.phase_number,
            phase_day=context.phase_day,
        )

        self._plan = None

        return RaidOutcome(
            (
                f"Raid committed: {readiness['town']} force deployed "
                f"with {self._active.force} warriors. "
                "Battle resolution is pending."
            ),
            ok=True,
            food_delta=-int(readiness["food_required"]),
        )

    def _release_plan(self) -> RaidOutcome:
        if self._plan is None:
            return RaidOutcome("", ok=True)

        weapon_deltas = {
            weapon: amount
            for weapon, amount in self._plan.weapon_issue.items()
            if amount
        }

        shield_deltas = {
            shield: amount
            for shield, amount in self._plan.shield_issue.items()
            if amount
        }

        self._plan = None

        return RaidOutcome(
            "",
            ok=True,
            weapon_stock_deltas=weapon_deltas,
            shield_stock_deltas=shield_deltas,
        )
