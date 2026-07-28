"""
Ghost Revolution deterministic game-state facade.

Ghost owns social interpretation through GhostRevolutionSocialBridge.
This facade coordinates game rules without terminal input, rendering,
animation, or direct ScenarioRuntime access.
"""

from __future__ import annotations

from copy import deepcopy
import json
import random

from .config import (
    CAMP_ACTIONS,
    CAMP_DAYS,
    LOCATIONS,
    LOCATION_DISTANCE,
    MILITARY_CAMPS,
    KING_FIGHT_PLAYER_DAMAGE,
    RAID_REQUIREMENTS,
    REBELLION_ACTIONS,
    REBELLION_DAYS,
    SHIELD_TYPES,
    START_FOOD,
    START_GOLD,
    START_WEAPONS,
    TOWN_IDS,
    WEAPON_TIERS,
    WEAPON_TYPES,
    build_revolution_scenario,
    military_camp_for,
    raid_requirement_for,
)
from .social import (
    GhostRevolutionSocialBridge,
)
from .raid import (
    RaidContext,
    RaidOutcome,
    RaidSystem,
)
from .town_memory import TownMemory
from .guard import GuardSystem


PLAYER = "player"

GAME_SNAPSHOT_SCHEMA_VERSION = "1.0"

_GAME_SNAPSHOT_KEYS = {
    "schema_version",
    "social",
    "rng_state",
    "state",
}

_GAME_STATE_KEYS = {
    "phase",
    "phase_number",
    "phase_day",
    "actions",
    "location",
    "followers",
    "gold",
    "food",
    "primary_weapon",
    "leader_weapon_name",
    "leader_weapon_tier",
    "armor",
    "armor_item",
    "weapon_stock",
    "shield_stock",
    "weapons",
    "seeds",
    "cooking_kits",
    "heat",
    "royal_alert",
    "guards_defeated",
    "king_control",
    "alive",
    "captured",
    "quit_game",
    "ending",
    "last_packet",
    "last_king_response",
    "last_action_note",
    "guard_combat",
    "king_fight",
    "siege_armed",
    "raid_state",
    "town_memory",
    "next_guard_serial",
    "scout_intel",
    "role_assignments",
    "recruited_today",
    "daily_activity",
    "scout_reports_today",
    "last_scout_reports",
    "scouts_captured",
    "public_event_state",
    "knight_town",
    "assignments",
    "towns",
}


class GhostRevolutionRun:
    """
    Rebellion strategy state around ScenarioRuntime.

    Town relationship consequences always move through Ghost.
    """

    @staticmethod
    def _snapshot_copy(value, label: str):
        try:
            return json.loads(
                json.dumps(
                    value,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"{label} must be JSON-safe"
            ) from error

    @classmethod
    def _rng_state_tuple(cls, value):
        if isinstance(value, list):
            return tuple(
                cls._rng_state_tuple(item)
                for item in value
            )

        return value

    def __init__(
        self,
        config: dict | None = None,
        seed: int = 7,
    ):
        scenario_config = (
            config
            if config is not None
            else build_revolution_scenario()
        )

        self._social = GhostRevolutionSocialBridge(
            scenario_config
        )
        self.rng = random.Random(seed)

        self.phase = "rebellion"
        self.phase_number = 1
        self.phase_day = 1
        self.actions = REBELLION_ACTIONS
        self.location = "base"

        self.followers = 0
        self.gold = START_GOLD
        self.food = START_FOOD
        self.primary_weapon = "sword"
        self.leader_weapon_name = "Knight's Sword"
        self.leader_weapon_tier = "common"
        self.armor = 0
        self.armor_item = "none"

        self.weapon_stock = {
            "sword": START_WEAPONS,
            "axe": 0,
            "spear": 0,
            "bow": 0,
        }

        self.shield_stock = {
            "light": 0,
            "medium": 0,
            "heavy": 0,
        }

        self.weapons = START_WEAPONS
        self.seeds = 0
        self.cooking_kits = 0
        self.heat = 0
        self.royal_alert = 0
        self.guards_defeated = 0
        self.king_control = 10

        self.alive = True
        self.captured = False
        self.quit_game = False
        self.ending = ""

        self.last_packet = None
        self.last_king_response = []
        self.last_action_note = ""
        self.guard_combat = None
        self.king_fight = None
        self.siege_armed = False
        self._raids = RaidSystem()
        self._town_memory = TownMemory(TOWN_IDS)
        self._guards = GuardSystem()
        self._next_guard_serial = 1

        self.scout_intel = {
            town_id: 0
            for town_id in TOWN_IDS
        }

        self.role_assignments = {
            "scouts": 0,
            "warriors": 0,
        }

        self.recruited_today = {
            town_id: 0
            for town_id in TOWN_IDS
        }

        self.daily_activity = {
            town_id: {
                "work": False,
                "bar": False,
                "public_event": False,
                "guard_question": False,
                "guard_recruit": False,
                "guard_bribe": False,
            }
            for town_id in TOWN_IDS
        }

        self.scout_reports_today = 0
        self.last_scout_reports = []
        self.scouts_captured = 0

        self.public_event_state = {
            town_id: {
                "open": False,
                "completed": False,
                "used_actions": set(),
            }
            for town_id in TOWN_IDS
        }

        self.knight_town = "crownmarket"

        self.assignments = {
            "farmers": 0,
            "foragers": 0,
            "trainers": 0,
            "smiths": 0,
            "scouts": 0,
        }

        self.towns = {
            "ashfield": {
                "name": "Ashfield",
                "population": 26,
                "recruited": 0,
                "fear": 1,
                "guard_roster": [],
                "locked": False,
                "raided": False,
                "rebel_controlled": False,
                "specialty": "farming",
            },
            "millcross": {
                "name": "Millcross",
                "population": 22,
                "recruited": 0,
                "fear": 2,
                "guard_roster": [],
                "locked": False,
                "raided": False,
                "rebel_controlled": False,
                "specialty": "market",
            },
            "crownmarket": {
                "name": "Crownmarket",
                "population": 18,
                "recruited": 0,
                "fear": 3,
                "guard_roster": [],
                "locked": False,
                "raided": False,
                "rebel_controlled": False,
                "specialty": "royal market",
            },
        }

        self._add_guard("millcross", "watchman")
        self._add_guard("millcross", "watchman")

        self._add_guard("crownmarket", "crown_guard")
        self._add_guard("crownmarket", "crown_guard")
        self._add_guard("crownmarket", "crown_guard")

    @property
    def complete(self) -> bool:
        return bool(
            self.quit_game
            or not self.alive
            or self.ending
        )

    @property
    def runtime(self):
        """
        Compatibility view for existing diagnostics and tests.

        New game features must use ``self._social`` semantic methods,
        not the raw ScenarioRuntime.
        """

        return self._social.runtime

    @property
    def raid_plan(self) -> dict | None:
        """Compatibility snapshot of the editable raid plan."""

        return self._raids.plan

    @raid_plan.setter
    def raid_plan(self, plan: dict | None) -> None:
        self._raids.replace_plan(plan)

    @property
    def active_raid(self) -> dict | None:
        """Compatibility snapshot of the deployed raid."""

        return self._raids.active

    @active_raid.setter
    def active_raid(self, active: dict | None) -> None:
        self._raids.replace_active(active)

    def _raid_context(
        self,
        target: str | None = None,
    ) -> RaidContext:
        requested = target

        if requested is None:
            plan = self.raid_plan
            requested = plan["target"] if plan else ""

        common = {
            "target": requested,
            "location": self.location,
            "available_warriors": self.available_warriors(),
            "food": self.food,
            "weapon_stock": deepcopy(self.weapon_stock),
            "shield_stock": deepcopy(self.shield_stock),
            "leader_weapon": self.leader_weapon_label(),
            "leader_weapon_tier": self.leader_weapon_tier,
            "leader_armor": self.armor_item,
            "training_level": self.assignments["trainers"],
            "guards_defeated": self.guards_defeated,
            "phase_number": self.phase_number,
            "phase_day": self.phase_day,
        }

        if requested not in self.towns:
            return RaidContext(
                valid_target=False,
                **common,
            )

        town = self.towns[requested]

        return RaidContext(
            valid_target=True,
            town_name=town["name"],
            town_condition=self.town_condition(requested),
            town_rebel_controlled=town["rebel_controlled"],
            town_support=(
                1
                if self.town_trust(requested) >= 0.25
                else 0
            ),
            intel_level=self.scout_intel[requested],
            camp=self.military_camp(requested),
            requirement=self.raid_requirement(requested),
            **common,
        )

    def _apply_raid_outcome(
        self,
        outcome: RaidOutcome,
    ) -> bool:
        for weapon, delta in outcome.weapon_stock_deltas.items():
            updated = self.weapon_stock[weapon] + delta

            if updated < 0:
                raise RuntimeError(
                    "Raid outcome would make weapon stock negative."
                )

            self.weapon_stock[weapon] = updated

        for shield, delta in outcome.shield_stock_deltas.items():
            updated = self.shield_stock[shield] + delta

            if updated < 0:
                raise RuntimeError(
                    "Raid outcome would make shield stock negative."
                )

            self.shield_stock[shield] = updated

        updated_food = self.food + outcome.food_delta

        if updated_food < 0:
            raise RuntimeError(
                "Raid outcome would make food negative."
            )

        self.food = updated_food
        self._sync_weapon_total()

        if outcome.note:
            self.last_action_note = outcome.note

        return outcome.ok

    def current_world(self) -> dict:
        return self._social.current_world()

    def information_summary(self) -> dict:
        """
        Return player-facing reports and beliefs.

        Objective facts remain inside Ghost's runtime state and are not
        presented as automatic player knowledge.
        """
        return self._social.information_summary()

    def snapshot(self) -> dict:
        """
        Return a versioned, JSON-safe game snapshot.

        The snapshot contains game state, deterministic RNG state, raid
        planning, town memory, and the Ghost social/epistemic ledger.
        """
        public_event_state = {
            town_id: {
                "open": event["open"],
                "completed": event["completed"],
                "used_actions": sorted(event["used_actions"]),
            }
            for town_id, event in self.public_event_state.items()
        }

        return self._snapshot_copy(
            {
                "schema_version": (
                    GAME_SNAPSHOT_SCHEMA_VERSION
                ),
                "social": self._social.snapshot(),
                "rng_state": self.rng.getstate(),
                "state": {
                    "phase": self.phase,
                    "phase_number": self.phase_number,
                    "phase_day": self.phase_day,
                    "actions": self.actions,
                    "location": self.location,
                    "followers": self.followers,
                    "gold": self.gold,
                    "food": self.food,
                    "primary_weapon": self.primary_weapon,
                    "leader_weapon_name": (
                        self.leader_weapon_name
                    ),
                    "leader_weapon_tier": (
                        self.leader_weapon_tier
                    ),
                    "armor": self.armor,
                    "armor_item": self.armor_item,
                    "weapon_stock": self.weapon_stock,
                    "shield_stock": self.shield_stock,
                    "weapons": self.weapons,
                    "seeds": self.seeds,
                    "cooking_kits": self.cooking_kits,
                    "heat": self.heat,
                    "royal_alert": self.royal_alert,
                    "guards_defeated": self.guards_defeated,
                    "king_control": self.king_control,
                    "alive": self.alive,
                    "captured": self.captured,
                    "quit_game": self.quit_game,
                    "ending": self.ending,
                    "last_packet": self.last_packet,
                    "last_king_response": (
                        self.last_king_response
                    ),
                    "last_action_note": self.last_action_note,
                    "guard_combat": self.guard_combat,
                    "king_fight": self.king_fight,
                    "siege_armed": self.siege_armed,
                    "raid_state": {
                        "plan": self._raids.plan,
                        "active": self._raids.active,
                    },
                    "town_memory": (
                        self._town_memory.snapshot()
                    ),
                    "next_guard_serial": (
                        self._next_guard_serial
                    ),
                    "scout_intel": self.scout_intel,
                    "role_assignments": (
                        self.role_assignments
                    ),
                    "recruited_today": (
                        self.recruited_today
                    ),
                    "daily_activity": self.daily_activity,
                    "scout_reports_today": (
                        self.scout_reports_today
                    ),
                    "last_scout_reports": (
                        self.last_scout_reports
                    ),
                    "scouts_captured": self.scouts_captured,
                    "public_event_state": (
                        public_event_state
                    ),
                    "knight_town": self.knight_town,
                    "assignments": self.assignments,
                    "towns": self.towns,
                },
            },
            "Ghost Revolution snapshot",
        )

    @classmethod
    def from_snapshot(
        cls,
        snapshot: dict,
    ) -> "GhostRevolutionRun":
        """
        Restore an exact deterministic game fork from snapshot() output.
        """
        if not isinstance(snapshot, dict):
            raise ValueError(
                "Ghost Revolution snapshot must be a dict"
            )

        snapshot = cls._snapshot_copy(
            snapshot,
            "Ghost Revolution snapshot",
        )

        if set(snapshot) != _GAME_SNAPSHOT_KEYS:
            raise ValueError(
                "Ghost Revolution snapshot has unsupported keys"
            )

        if (
            snapshot["schema_version"]
            != GAME_SNAPSHOT_SCHEMA_VERSION
        ):
            raise ValueError(
                "unsupported Ghost Revolution snapshot schema version"
            )

        state = snapshot["state"]

        if (
            not isinstance(state, dict)
            or set(state) != _GAME_STATE_KEYS
        ):
            raise ValueError(
                "Ghost Revolution snapshot state is invalid"
            )

        social = GhostRevolutionSocialBridge.from_snapshot(
            snapshot["social"]
        )

        game = cls(
            config=deepcopy(social.runtime.config),
            seed=0,
        )
        game._social = social
        game.rng = random.Random()

        try:
            game.rng.setstate(
                cls._rng_state_tuple(snapshot["rng_state"])
            )
        except (IndexError, TypeError, ValueError) as error:
            raise ValueError(
                "Ghost Revolution snapshot RNG state is invalid"
            ) from error

        for field in (
            "phase",
            "location",
            "primary_weapon",
            "leader_weapon_name",
            "leader_weapon_tier",
            "armor_item",
            "ending",
            "last_action_note",
            "knight_town",
        ):
            if not isinstance(state[field], str):
                raise ValueError(
                    "Ghost Revolution snapshot text state is invalid"
                )

        for field in (
            "phase_number",
            "phase_day",
            "actions",
            "followers",
            "gold",
            "food",
            "armor",
            "weapons",
            "seeds",
            "cooking_kits",
            "heat",
            "royal_alert",
            "guards_defeated",
            "king_control",
            "next_guard_serial",
            "scout_reports_today",
            "scouts_captured",
        ):
            if (
                isinstance(state[field], bool)
                or not isinstance(state[field], int)
            ):
                raise ValueError(
                    "Ghost Revolution snapshot numeric state is invalid"
                )

        for field in (
            "alive",
            "captured",
            "quit_game",
            "siege_armed",
        ):
            if not isinstance(state[field], bool):
                raise ValueError(
                    "Ghost Revolution snapshot boolean state is invalid"
                )

        for field in (
            "weapon_stock",
            "shield_stock",
            "scout_intel",
            "role_assignments",
            "recruited_today",
            "daily_activity",
            "assignments",
            "towns",
        ):
            if not isinstance(state[field], dict):
                raise ValueError(
                    "Ghost Revolution snapshot mapping state is invalid"
                )

        if (
            not isinstance(state["last_king_response"], list)
            or not isinstance(state["last_scout_reports"], list)
            or (
                state["last_packet"] is not None
                and not isinstance(state["last_packet"], dict)
            )
            or (
                state["guard_combat"] is not None
                and not isinstance(state["guard_combat"], dict)
            )
            or (
                state["king_fight"] is not None
                and not isinstance(state["king_fight"], dict)
            )
        ):
            raise ValueError(
                "Ghost Revolution snapshot record state is invalid"
            )

        raid_state = state["raid_state"]

        if (
            not isinstance(raid_state, dict)
            or set(raid_state) != {"plan", "active"}
        ):
            raise ValueError(
                "Ghost Revolution snapshot raid state is invalid"
            )

        public_event_state = state["public_event_state"]

        if (
            not isinstance(public_event_state, dict)
            or set(public_event_state) != set(TOWN_IDS)
        ):
            raise ValueError(
                "Ghost Revolution public event state is invalid"
            )

        restored_public_events = {}

        for town_id in TOWN_IDS:
            event = public_event_state[town_id]

            if (
                not isinstance(event, dict)
                or set(event) != {
                    "open",
                    "completed",
                    "used_actions",
                }
                or not isinstance(event["open"], bool)
                or not isinstance(event["completed"], bool)
                or not isinstance(event["used_actions"], list)
                or not all(
                    isinstance(action, str)
                    for action in event["used_actions"]
                )
            ):
                raise ValueError(
                    "Ghost Revolution public event state is invalid"
                )

            restored_public_events[town_id] = {
                "open": event["open"],
                "completed": event["completed"],
                "used_actions": set(event["used_actions"]),
            }

        game.phase = state["phase"]
        game.phase_number = state["phase_number"]
        game.phase_day = state["phase_day"]
        game.actions = state["actions"]
        game.location = state["location"]
        game.followers = state["followers"]
        game.gold = state["gold"]
        game.food = state["food"]
        game.primary_weapon = state["primary_weapon"]
        game.leader_weapon_name = state[
            "leader_weapon_name"
        ]
        game.leader_weapon_tier = state[
            "leader_weapon_tier"
        ]
        game.armor = state["armor"]
        game.armor_item = state["armor_item"]
        game.weapon_stock = deepcopy(state["weapon_stock"])
        game.shield_stock = deepcopy(state["shield_stock"])
        game.weapons = state["weapons"]
        game.seeds = state["seeds"]
        game.cooking_kits = state["cooking_kits"]
        game.heat = state["heat"]
        game.royal_alert = state["royal_alert"]
        game.guards_defeated = state["guards_defeated"]
        game.king_control = state["king_control"]
        game.alive = state["alive"]
        game.captured = state["captured"]
        game.quit_game = state["quit_game"]
        game.ending = state["ending"]
        game.last_packet = deepcopy(state["last_packet"])
        game.last_king_response = deepcopy(
            state["last_king_response"]
        )
        game.last_action_note = state["last_action_note"]
        game.guard_combat = deepcopy(state["guard_combat"])
        game.king_fight = deepcopy(state["king_fight"])
        game.siege_armed = state["siege_armed"]
        game._raids = RaidSystem()
        game._raids.replace_plan(
            deepcopy(raid_state["plan"])
        )
        game._raids.replace_active(
            deepcopy(raid_state["active"])
        )
        game._town_memory = TownMemory.from_snapshot(
            TOWN_IDS,
            state["town_memory"],
        )
        game._guards = GuardSystem()
        game._next_guard_serial = state[
            "next_guard_serial"
        ]
        game.scout_intel = deepcopy(state["scout_intel"])
        game.role_assignments = deepcopy(
            state["role_assignments"]
        )
        game.recruited_today = deepcopy(
            state["recruited_today"]
        )
        game.daily_activity = deepcopy(state["daily_activity"])
        game.scout_reports_today = state[
            "scout_reports_today"
        ]
        game.last_scout_reports = deepcopy(
            state["last_scout_reports"]
        )
        game.scouts_captured = state["scouts_captured"]
        game.public_event_state = restored_public_events
        game.knight_town = state["knight_town"]
        game.assignments = deepcopy(state["assignments"])
        game.towns = deepcopy(state["towns"])

        return game

    def restore_snapshot(
        self,
        snapshot: dict,
    ) -> dict:
        """Restore snapshot() output into this existing run."""
        restored = type(self).from_snapshot(snapshot)

        self.__dict__.clear()
        self.__dict__.update(restored.__dict__)

        return self.snapshot()

    def _spend_action(self, amount: int = 1) -> bool:
        if amount < 1:
            return False

        if self.actions < amount:
            return False

        self.actions -= amount
        return True

    def _save_packet(self, packet: dict) -> dict:
        self.last_packet = deepcopy(packet)

        if packet["law"]["action"] == "detain":
            self.captured = True
            self.alive = False
            self.ending = (
                "The captain detains you before the rebellion can grow."
            )

        if packet["win_fail"]["is_fail"]:
            self.alive = False
            self.ending = (
                "The kingdom drives your rebellion from the towns."
            )

        return packet

    def _resolve(
        self,
        action_type: str,
        target: str,
    ) -> dict:
        packet = self._social.resolve_action(
            action_type,
            target,
        )

        return self._save_packet(packet)

    def relationship(self, target: str) -> dict:
        return self._social.relationship(target)

    def town_people_left(self, town_id: str) -> int:
        town = self.towns[town_id]

        return town["population"] - town["recruited"]

    def town_trust(self, town_id: str) -> float:
        return float(self.relationship(town_id)["trust"])

    def guard_count(self, town_id: str) -> int:
        """
        Return how many active royal guards remain in a town.

        Guard roster entries are the source of truth. There is no
        separate boolean guard latch.
        """
        town = self.towns.get(town_id)

        if town is None:
            return 0

        return len(town["guard_roster"])

    def has_active_guard(self, town_id: str) -> bool:
        return self.guard_count(town_id) > 0

    def active_guard(self, town_id: str) -> dict | None:
        """
        Return a copy-safe view of the guard currently on patrol.
        """
        town = self.towns.get(town_id)

        if town is None or not town["guard_roster"]:
            return None

        return deepcopy(town["guard_roster"][0])

    def active_guard_label(self, town_id: str) -> str:
        guard = self.active_guard(town_id)

        if guard is None:
            return "No royal guard"

        return str(guard["label"])

    def _add_guard(
        self,
        town_id: str,
        rank: str,
    ) -> dict:
        """
        Add one named guard to a town roster.

        This facade owns mutable campaign staffing. GuardSystem only
        validates and builds a fresh guard identity packet.
        """
        if town_id not in self.towns:
            raise ValueError(
                f"unknown town id: {town_id}"
            )

        guard_id = (
            f"{town_id}-guard-{self._next_guard_serial}"
        )
        self._next_guard_serial += 1

        guard = self._guards.new_guard(
            guard_id=guard_id,
            rank=rank,
        )

        self.towns[town_id]["guard_roster"].append(guard)

        return deepcopy(guard)

    def _remove_guard(
        self,
        town_id: str,
        guard_id: str,
    ) -> dict:
        """
        Remove exactly one known guard from a town roster.

        A combat or defection outcome cannot erase every guard in town.
        """
        if town_id not in self.towns:
            raise RuntimeError(
                f"unknown town for guard removal: {town_id}"
            )

        roster = self.towns[town_id]["guard_roster"]

        for index, guard in enumerate(roster):
            if guard["id"] == guard_id:
                return roster.pop(index)

        raise RuntimeError(
            f"guard roster is missing active guard: {guard_id}"
        )

    def total_recruited(self) -> int:
        return sum(
            town["recruited"]
            for town in self.towns.values()
        )

    def assignment_total(self) -> int:
        return sum(self.assignments.values())

    def worker_followers(self) -> int:
        return max(
            0,
            self.followers
            - self.role_assignments["scouts"]
            - self.role_assignments["warriors"],
        )

    def available_workers(self) -> int:
        return max(
            0,
            self.worker_followers() - self.assignment_total(),
        )

    def deployed_warriors(self) -> int:
        return self._raids.deployed_warriors()

    def available_warriors(self) -> int:
        return max(
            0,
            self.role_assignments["warriors"]
            - self.deployed_warriors(),
        )

    def role_summary(self) -> dict:
        return {
            "workers": self.worker_followers(),
            "scouts": self.role_assignments["scouts"],
            "warriors": self.role_assignments["warriors"],
            "deployed_warriors": self.deployed_warriors(),
            "unassigned_workers": self.available_workers(),
        }

    def set_combat_role(
        self,
        role: str,
        amount: int,
    ) -> bool:
        if role not in ("scouts", "warriors"):
            self.last_action_note = "Unknown follower role."
            return False

        if not isinstance(amount, int) or amount < 0:
            self.last_action_note = "Role assignment must be a whole number."
            return False

        if (
            role == "warriors"
            and amount < self.deployed_warriors()
        ):
            self.last_action_note = (
                "You cannot remove warriors already deployed on a raid."
            )
            return False

        other_role = (
            "warriors"
            if role == "scouts"
            else "scouts"
        )

        if amount + self.role_assignments[other_role] > self.followers:
            self.last_action_note = (
                "You cannot assign more scouts and warriors "
                "than total followers."
            )
            return False

        projected_workers = (
            self.followers
            - amount
            - self.role_assignments[other_role]
        )

        if self.assignment_total() > projected_workers:
            self.last_action_note = (
                "Too many workers are assigned to camp jobs. "
                "Reduce camp assignments first."
            )
            return False

        self.role_assignments[role] = amount
        self.last_action_note = (
            f"{role.title()} assigned: {amount}."
        )

        return True

    def weapon_stock_total(self) -> int:
        """
        Return unused weapons remaining at the hidden base.

        Weapons reserved in a raid plan are not base stock.
        """

        return sum(self.weapon_stock.values())

    def shield_stock_total(self) -> int:
        """
        Return unused shields remaining at the hidden base.

        Shields reserved in a raid plan are not base stock.
        """

        return sum(self.shield_stock.values())

    def _sync_weapon_total(self) -> None:
        """
        Keep the legacy total weapon counter aligned with
        base stock plus gear reserved for the current raid plan.
        """

        self.weapons = (
            self.weapon_stock_total()
            + self.army_weapons_issued()
        )

    def _release_raid_reservations(self) -> None:
        self._apply_raid_outcome(
            self._raids.release_plan()
        )

    def cancel_raid_plan(self) -> bool:
        return self._apply_raid_outcome(
            self._raids.cancel_plan()
        )

    def leader_weapon_label(self) -> str:
        return (
            f"{self.leader_weapon_name} "
            f"[{self.leader_weapon_tier.upper()}]"
        )

    def army_weapons_issued(self) -> int:
        return self._raids.issued_weapons()

    def army_shields_issued(self) -> int:
        return self._raids.issued_shields()

    def military_camp(self, target: str) -> dict:
        if target not in MILITARY_CAMPS:
            raise ValueError(f"Unknown military camp target: {target}")

        return military_camp_for(target)

    def raid_requirement(self, target: str) -> dict:
        if target not in RAID_REQUIREMENTS:
            raise ValueError(f"Unknown raid target: {target}")

        return raid_requirement_for(target)

    def raid_readiness(self, target: str) -> dict:
        if target not in self.towns:
            raise ValueError(
                f"Unknown raid target: {target}"
            )

        return self._raids.readiness(
            self._raid_context(target)
        )

    def plan_raid(self, target: str) -> dict | None:
        outcome = self._raids.open_plan(
            self._raid_context(target)
        )

        if not self._apply_raid_outcome(outcome):
            return None

        return self.raid_readiness(target)

    def active_raid_summary(self) -> dict | None:
        return self._raids.active_summary()

    def commit_raid(self) -> bool:
        return self._apply_raid_outcome(
            self._raids.commit(
                self._raid_context()
            )
        )

    def set_raid_force(self, amount: int) -> bool:
        return self._apply_raid_outcome(
            self._raids.set_force(
                self._raid_context(),
                amount,
            )
        )

    def set_raid_weapon_issue(
        self,
        weapon: str,
        amount: int,
    ) -> bool:
        return self._apply_raid_outcome(
            self._raids.set_weapon_issue(
                self._raid_context(),
                weapon,
                amount,
            )
        )

    def set_raid_shield_issue(
        self,
        shield: str,
        amount: int,
    ) -> bool:
        return self._apply_raid_outcome(
            self._raids.set_shield_issue(
                self._raid_context(),
                shield,
                amount,
            )
        )

    def danger_level(self) -> int:
        danger = self.heat + self.royal_alert

        if self.location in self.towns:
            town = self.towns[self.location]

            guard_is_active = (
                self.has_active_guard(self.location)
                and not self.guard_passage_active(self.location)
            )

            if guard_is_active:
                danger += 2

            if self.location == self.knight_town:
                danger += 4

            if town["locked"]:
                danger += 2

        if self.location == "castle":
            danger += 8

        return danger


    def travel_cost(self, destination: str) -> int:
        return max(
            1,
            abs(
                LOCATION_DISTANCE[destination]
                - LOCATION_DISTANCE[self.location]
            ),
        )

    def travel(self, destination: str) -> bool:
        if destination not in LOCATIONS:
            return False

        if destination == self.location:
            return False

        if self.phase != "rebellion":
            return False

        if destination in self.towns:
            if self.towns[destination]["locked"]:
                return False

        cost = self.travel_cost(destination)

        if not self._spend_action(cost):
            return False

        self.location = destination

        if destination in self.towns:
            town = self.towns[destination]

            if self.has_active_guard(destination):
                self.heat = min(10, self.heat + 1)

            if destination == self.knight_town:
                self.heat = min(10, self.heat + 1)

        if destination == "castle":
            self.heat = min(10, self.heat + 2)

        self._check_capture()

        return True


    def _deny(self, note: str) -> None:
        self.last_action_note = note
        return None

    def clear_action_note(self) -> None:
        self.last_action_note = ""

    def daily_food_need(self) -> int:
        if self.followers <= 4:
            return 1

        if self.followers <= 14:
            return 2

        if self.followers <= 29:
            return 3

        return 4

    def town_condition(self, town_id: str) -> str:
        town = self.towns[town_id]
        trust = self.town_trust(town_id)

        if town["locked"]:
            return "LOCKED DOWN"

        if town_id == self.knight_town:
            return "KNIGHT OCCUPIED"

        if self.has_active_guard(town_id) and trust <= -0.25:
            return "HOSTILE"

        if trust >= 0.55:
            return "SUPPORTIVE"

        if trust >= 0.25:
            return "FRIENDLY"

        if trust <= -0.25:
            return "WARY"

        return "NEUTRAL"


    def recruitment_limit_today(self, town_id: str) -> int:
        town = self.towns[town_id]
        trust = self.town_trust(town_id)

        limit = 2

        if trust >= 0.25:
            limit += 1

        if trust >= 0.55:
            limit += 1

        if town["fear"] >= 4:
            limit -= 1

        if self.has_active_guard(town_id):
            limit -= 1

        if town_id == self.knight_town:
            limit -= 1

        return max(0, limit)


    def recruitment_available_today(self, town_id: str) -> int:
        return max(
            0,
            min(
                self.town_people_left(town_id),
                self.recruitment_limit_today(town_id)
                - self.recruited_today[town_id],
            ),
        )

    def _daily_cap_available(
        self,
        town_id: str,
        category: str,
    ) -> bool:
        if not self.daily_activity[town_id][category]:
            return True

        town_name = self.towns[town_id]["name"]

        messages = {
            "work": (
                f"You already worked in {town_name} today."
            ),
            "bar": (
                f"The bar in {town_name} has given you "
                "all it knows today."
            ),
            "public_event": (
                f"The crowd in {town_name} will not gather "
                "for another public event today."
            ),
        }

        self.last_action_note = messages[category]
        return False

    def _mark_daily_cap(
        self,
        town_id: str,
        category: str,
    ) -> None:
        self.daily_activity[town_id][category] = True

    def town_execution_memory(self, town_id: str) -> int:
        """
        Return the remaining public-memory duration for an execution.

        This is separate from Ghost relationship trust. Trust can move,
        while the town still remembers what it saw.
        """
        if town_id not in self.towns:
            return 0

        return self._town_memory.remaining(town_id)

    def town_memory_label(self, town_id: str) -> str:
        if town_id not in self.towns:
            return "none"

        return self._town_memory.label(town_id)

    def _record_town_execution_memory(
        self,
        town_id: str,
        public_response: str,
    ) -> int:
        """
        Record durable town memory after a witnessed execution.

        TownMemory owns the duration. The town dictionary keeps a
        compatibility projection for presentation consumers.
        """
        remaining = self._town_memory.record_execution(
            town_id,
            public_response,
        )

        self.towns[town_id]["execution_memory"] = remaining

        return remaining

    def _advance_town_memories(self) -> None:
        """
        Advance durable town memories at the end of each game day.

        TownMemory owns duration and fear-floor rules. This facade
        applies returned fear floors to live town state.
        """
        for town_id, fear_floor in (
            self._town_memory.advance_day().items()
        ):
            town = self.towns[town_id]

            town["fear"] = max(
                town["fear"],
                fear_floor,
            )

            town["execution_memory"] = (
                self._town_memory.remaining(town_id)
            )

    def _reset_daily_limits(self) -> None:
        self.recruited_today = {
            town_id: 0
            for town_id in TOWN_IDS
        }

        self.daily_activity = {
            town_id: {
                "work": False,
                "bar": False,
                "public_event": False,
                "guard_question": False,
                "guard_recruit": False,
                "guard_bribe": False,
            }
            for town_id in TOWN_IDS
        }

        self.public_event_state = {
            town_id: {
                "open": False,
                "completed": False,
                "used_actions": set(),
            }
            for town_id in TOWN_IDS
        }

        self.scout_reports_today = 0

    def scout_capacity(self) -> int:
        return max(
            0,
            int(self.role_assignments["scouts"]),
        )

    def scout_report_summary(self) -> dict:
        return {
            "assigned_scouts": self.scout_capacity(),
            "reports_today": self.scout_reports_today,
            "intel": deepcopy(self.scout_intel),
            "last_reports": list(self.last_scout_reports),
            "scouts_captured": self.scouts_captured,
            "crownmarket_capture_risk": (
                self._crownmarket_capture_risk()
            ),
            "information": self.information_summary(),
        }

    def _crownmarket_capture_risk(self) -> int:
        risk = 20 + self.heat * 5

        if self.has_active_guard("crownmarket"):
            risk += 10

        if self.knight_town == "crownmarket":
            risk += 15

        if self.towns["crownmarket"]["locked"]:
            risk += 10

        risk -= self.scout_intel["crownmarket"] * 3

        return max(10, min(70, risk))


    def _next_scout_target(self) -> str | None:
        candidates = [
            town_id
            for town_id in TOWN_IDS
            if self.scout_intel[town_id] < 3
        ]

        if not candidates:
            return None

        priority = {
            "ashfield": 0,
            "millcross": 1,
            "crownmarket": 2,
        }

        return min(
            candidates,
            key=lambda town_id: (
                self.scout_intel[town_id],
                priority[town_id],
            ),
        )

    def _run_scout_reports(self) -> list[str]:
        capacity = self.scout_capacity()
        reports = []

        for _ in range(capacity):
            target = self._next_scout_target()

            if target is None:
                break

            if target == "crownmarket":
                risk = self._crownmarket_capture_risk()
                roll = self.rng.randint(1, 100)

                if roll <= risk:
                    self.role_assignments["scouts"] -= 1
                    self.followers = max(0, self.followers - 1)
                    self.scouts_captured += 1

                    entry = self._social.record_scout_capture(
                        town_id=target,
                        risk=risk,
                        phase_number=self.phase_number,
                        phase_day=self.phase_day,
                    )

                    reports.append(entry["message"])
                    continue

            self.scout_intel[target] += 1
            self.scout_reports_today += 1

            camp = self.military_camp(target)
            level = self.scout_intel[target]

            entry = self._social.record_scout_report(
                town_id=target,
                camp=camp,
                intel_level=level,
                phase_number=self.phase_number,
                phase_day=self.phase_day,
            )

            reports.append(entry["message"])

        self.last_scout_reports = reports

        return list(reports)

    def begin_public_event(self) -> bool:
        if self.phase != "rebellion":
            self.last_action_note = (
                "Public events are only available during rebellion days."
            )
            return False

        if self.location not in self.towns:
            self.last_action_note = (
                "There is no town crowd to address here."
            )
            return False

        town = self.towns[self.location]

        if town["locked"]:
            self.last_action_note = (
                "The lockdown has broken up public gatherings."
            )
            return False

        event = self.public_event_state[self.location]

        if event["completed"]:
            self.last_action_note = (
                f"The gathering in {town['name']} has already "
                "dispersed for today."
            )
            return False

        event["open"] = True
        return True

    def leave_public_event(self) -> None:
        if self.location not in self.towns:
            return

        event = self.public_event_state[self.location]

        if not event["open"]:
            return

        event["open"] = False
        event["completed"] = True
        self.daily_activity[self.location]["public_event"] = True

        self.last_action_note = (
            f"The gathering in {self.towns[self.location]['name']} "
            "disperses for today."
        )

    def public_event_action_available(
        self,
        action_name: str,
    ) -> bool:
        if self.location not in self.towns:
            self.last_action_note = (
                "There is no public gathering here."
            )
            return False

        event = self.public_event_state[self.location]

        if not event["open"]:
            self.last_action_note = (
                "That public gathering is no longer active."
            )
            return False

        if action_name in event["used_actions"]:
            self.last_action_note = (
                "You already used that moment of the gathering."
            )
            return False

        return True

    def _mark_public_event_action(
        self,
        action_name: str,
    ) -> None:
        self.public_event_state[
            self.location
        ]["used_actions"].add(action_name)

    def public_event_summary(self) -> dict:
        if self.location not in self.towns:
            return {
                "open": False,
                "completed": False,
                "used_actions": set(),
            }

        event = self.public_event_state[self.location]

        return {
            "open": event["open"],
            "completed": event["completed"],
            "used_actions": set(event["used_actions"]),
        }

    def honest_work_reward(self) -> tuple[int, int]:
        if self.location == "ashfield":
            return (4, 1)

        if self.location == "millcross":
            return (7, 0)

        if self.location == "crownmarket":
            return (10, 0)

        return (0, 0)

    def earn_honest_gold(self) -> dict | None:
        if self.phase != "rebellion":
            return self._deny(
                "Honest work is only available during rebellion days."
            )

        if self.location not in self.towns:
            return self._deny(
                "There is no town work available here."
            )

        town = self.towns[self.location]

        if town["locked"]:
            return self._deny(
                "The lockdown has shut down local work."
            )

        if not self._daily_cap_available(
            self.location,
            "work",
        ):
            return None

        if self.actions <= 0:
            return self._deny(
                "No actions remain. End the day or leave town."
            )

        trust = self.town_trust(self.location)

        if trust <= -0.25:
            return self._deny(
                "No one here trusts you with honest work."
            )

        gold_gain, food_gain = self.honest_work_reward()

        if self.location == self.knight_town:
            gold_gain = max(2, gold_gain - 3)
            self.heat = min(10, self.heat + 1)

        if trust >= 0.55:
            gold_gain += 2

        if not self._spend_action():
            return self._deny(
                "No actions remain. End the day or leave town."
            )

        self._mark_daily_cap(self.location, "work")
        self.gold += gold_gain
        self.food += food_gain

        if self.location == "ashfield":
            self.last_action_note = (
                f"Farm labor earns {gold_gain} gold "
                f"and {food_gain} food."
            )
        elif self.location == "millcross":
            self.last_action_note = (
                f"Market labor earns {gold_gain} gold."
            )
        else:
            self.last_action_note = (
                f"Courier work earns {gold_gain} gold."
            )

        return self._resolve("help", self.location)

    def recruit_quietly(self) -> dict | None:
        self.clear_action_note()

        if self.phase != "rebellion":
            return self._deny(
                "Recruitment is only available during rebellion days."
            )

        if self.location not in self.towns:
            return self._deny(
                "There is no town here to recruit from."
            )

        town = self.towns[self.location]

        if town["locked"]:
            return self._deny(
                "The lockdown makes recruitment impossible."
            )

        if self.actions <= 0:
            return self._deny(
                "No actions remain. End the day or leave town."
            )

        people_left = self.town_people_left(self.location)

        if people_left <= 0:
            return self._deny(
                f"{town['name']} has no people left to recruit."
            )

        available = self.recruitment_available_today(self.location)

        if available <= 0:
            return self._deny(
                (
                    f"{town['name']} has no more willing recruits "
                    "today. Build trust, lower fear, or return later."
                )
            )

        if self.location == self.knight_town:
            if not self._spend_action():
                return self._deny(
                    "No actions remain. End the day or leave town."
                )

            self.heat = min(10, self.heat + 1)
            self.last_action_note = (
                "The knight's presence turns recruits against you."
            )

            return self._resolve("insult", self.location)

        if not self._spend_action():
            return self._deny(
                "No actions remain. End the day or leave town."
            )

        packet = self._resolve("help", self.location)
        trust = float(packet["relationship"]["trust"])

        gain = 1

        if trust >= 0.25:
            gain += 1

        if trust >= 0.55:
            gain += 1

        memory = self.town_execution_memory(self.location)

        if memory > 0:
            gain = max(0, gain - 1)

        recruited = max(
            0,
            min(gain, available, people_left),
        )

        town["recruited"] += recruited
        self.recruited_today[self.location] += recruited
        self.followers += recruited

        if memory > 0 and recruited <= 0:
            self.last_action_note = (
                f"{town['name']} still remembers the execution. "
                "No one is willing to join quietly today."
            )
        elif memory > 0:
            self.last_action_note = (
                f"{recruited} people join the rebellion in "
                f"{town['name']}, but the execution still makes "
                "others hesitate."
            )
        else:
            self.last_action_note = (
                f"{recruited} people join the rebellion in "
                f"{town['name']}."
            )

        self._check_capture()

        return packet

    def speak_publicly(self) -> dict | None:
        if not self.public_event_action_available("speech"):
            return None

        town = self.towns[self.location]

        if not self._spend_action():
            return self._deny(
                "No actions remain. End the day or leave town."
            )

        self._mark_public_event_action("speech")

        if self.location == self.knight_town:
            town["fear"] = min(5, town["fear"] + 1)
            self.heat = min(10, self.heat + 2)
            self.last_action_note = (
                "The knight turns your public speech against you."
            )
            packet = self._resolve("insult", self.location)
        else:
            town["fear"] = max(0, town["fear"] - 1)
            self.heat = min(10, self.heat + 1)
            self.last_action_note = (
                "Your public speech strengthens local trust."
            )
            packet = self._resolve("help", self.location)

        self._check_capture()
        return packet

    def rally_people(self) -> dict | None:
        if not self.public_event_action_available("rally"):
            return None

        town = self.towns[self.location]

        if not self._spend_action():
            return self._deny(
                "No actions remain. End the day or leave town."
            )

        self._mark_public_event_action("rally")

        if self.location == self.knight_town:
            town["fear"] = min(5, town["fear"] + 1)
            self.heat = min(10, self.heat + 2)
            self.last_action_note = (
                "Royal pressure turns the crowd fearful."
            )
            packet = self._resolve("insult", self.location)
        else:
            town["fear"] = max(0, town["fear"] - 2)
            self.last_action_note = (
                "The crowd steadies and local fear falls."
            )
            packet = self._resolve("help", self.location)

        self._check_capture()
        return packet

    def recruit_openly(self) -> dict | None:
        if not self.public_event_action_available("recruit"):
            return None

        followers_before = self.followers
        packet = self.recruit_quietly()

        if packet is None:
            return None

        self._mark_public_event_action("recruit")

        if self.followers > followers_before:
            self.heat = min(10, self.heat + 1)
            self.last_action_note = (
                "Open recruitment brings new rebels, "
                "but draws royal attention."
            )

        return packet

    def give_speech(self) -> dict | None:
        """
        Backward-compatible alias for the original public event action.
        """

        return self.speak_publicly()

    def bribe_network(self) -> dict | None:
        if self.phase != "rebellion":
            return self._deny(
                "Bribery is only available during rebellion days."
            )

        if self.location not in self.towns:
            return self._deny(
                "There is no town network to bribe here."
            )

        town = self.towns[self.location]

        if town["locked"]:
            return self._deny(
                "The lockdown has cut off the town network."
            )

        if self.gold < 8:
            return self._deny(
                "You need 8 gold to bribe the town network."
            )

        if not self._spend_action():
            return self._deny(
                "No actions remain. End the day or leave town."
            )

        self.gold -= 8
        self.heat = max(0, self.heat - 1)
        town["fear"] = max(0, town["fear"] - 1)

        self.last_action_note = (
            "Coins change hands behind closed doors."
        )

        return self._resolve("help", self.location)

    def _roll_royal_cache_loot(self) -> dict:
        """
        Roll one royal cache payout.

        A cache can contain one resource category, two categories,
        or a full mixed cache. The result is deterministic for a
        given RNG seed.
        """

        roll = self.rng.randint(1, 100)

        food_gain = 0
        gold_gain = 0
        weapon_count = 0
        composition = ""

        if roll <= 18:
            composition = "food"
            food_gain = self.rng.randint(3, 6)

        elif roll <= 36:
            composition = "gold"
            gold_gain = self.rng.randint(7, 14)

        elif roll <= 48:
            composition = "weapons"
            weapon_count = self.rng.randint(1, 2)

        elif roll <= 63:
            composition = "food_gold"
            food_gain = self.rng.randint(2, 4)
            gold_gain = self.rng.randint(4, 8)

        elif roll <= 75:
            composition = "food_weapons"
            food_gain = self.rng.randint(2, 4)
            weapon_count = 1

        elif roll <= 87:
            composition = "gold_weapons"
            gold_gain = self.rng.randint(5, 10)
            weapon_count = 1

        else:
            composition = "full_cache"
            food_gain = self.rng.randint(3, 6)
            gold_gain = self.rng.randint(8, 14)
            weapon_count = self.rng.randint(1, 2)

        weapons_found = []

        for _ in range(weapon_count):
            weapon = self.rng.choice(WEAPON_TYPES)
            self.weapon_stock[weapon] += 1
            weapons_found.append(weapon)

        if weapons_found:
            self._sync_weapon_total()

        self.food += food_gain
        self.gold += gold_gain

        parts = []

        if food_gain:
            parts.append(f"+{food_gain} food")

        if gold_gain:
            parts.append(f"+{gold_gain} gold")

        for weapon in weapons_found:
            parts.append(f"+1 {weapon}")

        return {
            "composition": composition,
            "food": food_gain,
            "gold": gold_gain,
            "weapons": weapons_found,
            "summary": ", ".join(parts),
        }

    def seize_royal_supplies(self) -> dict | None:
        """
        Seize a royal cache inside the current town.

        This is not treated as betrayal of civilians. Local reaction
        depends on trust, fear, guards, and royal military presence.
        """

        if self.phase != "rebellion":
            return self._deny(
                "Supply seizures are only available during rebellion days."
            )

        if self.location not in self.towns:
            return self._deny(
                "There are no royal supplies to seize here."
            )

        town = self.towns[self.location]
        trust_before = self.town_trust(self.location)
        fear_before = town["fear"]
        guard_present = (
            self.has_active_guard(self.location)
            and not self.guard_passage_active(self.location)
        )
        knight_present = self.location == self.knight_town

        if not self._spend_action():
            return self._deny(
                "No actions remain. End the day or leave town."
            )

        loot = self._roll_royal_cache_loot()
        loot_text = loot["summary"]

        if knight_present:
            self.heat = min(10, self.heat + 4)
            town["fear"] = min(5, town["fear"] + 2)

            self.last_action_note = (
                f"Royal cache seized: {loot_text}. "
                "The knight orders a response, and the town fears "
                "immediate retaliation."
            )

            self._check_capture()
            return None

        if guard_present:
            self.heat = min(10, self.heat + 3)
            town["fear"] = min(5, town["fear"] + 1)

            if trust_before >= 0.35 and fear_before <= 1:
                self.last_action_note = (
                    f"Royal cache seized: {loot_text}. "
                    "Local allies hide the supplies as the guard "
                    "sounds an alarm."
                )

                packet = self._resolve("help", self.location)
                self._check_capture()
                return packet

            self.last_action_note = (
                f"Royal cache seized: {loot_text}. "
                "The guard raises an alarm, and locals scatter "
                "before they can show support."
            )

            self._check_capture()
            return None

        if fear_before >= 3:
            self.heat = min(10, self.heat + 2)

            self.last_action_note = (
                f"Royal cache seized: {loot_text}. "
                "The town is too afraid to cheer while royal patrols "
                "search for whoever struck the crown."
            )

            self._check_capture()
            return None

        if trust_before >= 0.08:
            self.heat = min(10, self.heat + 1)
            town["fear"] = max(0, town["fear"] - 1)

            self.last_action_note = (
                f"Royal cache seized: {loot_text}. "
                "Neighbors see the supplies reclaimed from the crown "
                "and quietly support you."
            )

            packet = self._resolve("help", self.location)
            self._check_capture()
            return packet

        self.heat = min(10, self.heat + 2)

        self.last_action_note = (
            f"Royal cache seized: {loot_text}. "
            "No one cheers, but no one calls it a betrayal of the town."
        )

        self._check_capture()
        return None


    def raid_supplies(self) -> dict | None:
        """
        Backward-compatible alias for the former local action name.
        """

        return self.seize_royal_supplies()

    def guard_passage_active(self, town_id: str) -> bool:
        """
        True while a local guard is bribed for the current day.
        """

        activity = self.daily_activity.get(town_id, {})

        return bool(activity.get("guard_bribe", False))

    def guard_defection_chance(self) -> int:
        """
        Calculate a local guard's willingness to defect.

        Trust helps. Fear, Royal Alert, and recent public executions
        make defection harder.
        """
        if self.location not in self.towns:
            return 0

        town = self.towns[self.location]

        return self._guards.defection_chance(
            trust=self.town_trust(self.location),
            fear=town["fear"],
            royal_alert=self.royal_alert,
            execution_memory=(
                self.town_execution_memory(self.location)
            ),
            knight_occupied=(
                self.location == self.knight_town
            ),
        )

    def question_guard(self) -> dict | None:
        """
        Spend one action reading a local guard's mood and pressure.
        """

        if self.phase != "rebellion":
            return self._deny(
                "Guard encounters are only available during rebellion days."
            )

        if self.location not in self.towns:
            return self._deny(
                "There is no royal guard to question here."
            )

        town = self.towns[self.location]

        if not self.has_active_guard(self.location):
            return self._deny(
                "There is no active royal guard in this town."
            )

        if self.daily_activity[self.location]["guard_question"]:
            return self._deny(
                "You already questioned this guard today."
            )

        if not self._spend_action():
            return self._deny(
                "No actions remain. End the day or leave town."
            )

        self.daily_activity[self.location]["guard_question"] = True

        chance = self.guard_defection_chance()

        if self.location == self.knight_town:
            read = (
                "The guard keeps glancing toward the knight's patrols. "
                "Defection is unlikely while Crownmarket is watched."
            )
        elif chance >= 50:
            read = (
                "The guard hesitates before repeating royal orders. "
                "He looks like he could defect under the right pressure."
            )
        elif chance >= 30:
            read = (
                "The guard listens, but fear and loyalty still hold him. "
                "A bribe or stronger town support could move him."
            )
        else:
            read = (
                "The guard is rigid and alert. Low trust or rising royal "
                "pressure makes a defection attempt dangerous."
            )

        self.last_action_note = (
            f"Guard read — Defection pressure: {chance}%. {read}"
        )

        return None


    def bribe_guard(self) -> dict | None:
        """
        Pay a guard to look away for the rest of the current day.
        """

        if self.phase != "rebellion":
            return self._deny(
                "Guard bribes are only available during rebellion days."
            )

        if self.location not in self.towns:
            return self._deny(
                "There is no royal guard to bribe here."
            )

        town = self.towns[self.location]

        if not self.has_active_guard(self.location):
            return self._deny(
                "There is no active royal guard in this town."
            )

        if self.location == self.knight_town:
            return self._deny(
                "The knight watches Crownmarket too closely for a lone "
                "guard to take your coin."
            )

        if self.guard_passage_active(self.location):
            return self._deny(
                "This guard is already looking the other way today."
            )

        if self.gold < 6:
            return self._deny(
                "You need 6 gold to bribe this guard."
            )

        if not self._spend_action():
            return self._deny(
                "No actions remain. End the day or leave town."
            )

        self.gold -= 6
        self.daily_activity[self.location]["guard_bribe"] = True

        self.last_action_note = (
            f"The guard pockets 6 gold and looks away in "
            f"{town['name']} until sundown. Safe passage is active."
        )

        return None


    def recruit_guard(self) -> dict | None:
        """
        Attempt to turn the active local royal guard into a rebel.

        A success removes only that guard from the town roster.
        """
        if self.phase != "rebellion":
            return self._deny(
                "Guard recruitment is only available during rebellion days."
            )

        if self.location not in self.towns:
            return self._deny(
                "There is no royal guard to recruit here."
            )

        town = self.towns[self.location]
        guard = self.active_guard(self.location)

        if guard is None:
            return self._deny(
                "There is no active royal guard in this town."
            )

        if self.location == self.knight_town:
            return self._deny(
                "The knight's direct control prevents this guard from "
                "defecting openly."
            )

        if self.daily_activity[self.location]["guard_recruit"]:
            return self._deny(
                "You already tested a guard's loyalty today."
            )

        if not self._spend_action():
            return self._deny(
                "No actions remain. End the day or leave town."
            )

        self.daily_activity[self.location]["guard_recruit"] = True

        chance = self.guard_defection_chance()
        fear_before = town["fear"]

        if self.rng.randint(1, 100) <= chance:
            self._remove_guard(
                self.location,
                guard["id"],
            )
            town["fear"] = max(0, fear_before - 1)

            self.followers += 1
            self.heat = min(10, self.heat + 1)
            self.royal_alert = min(5, self.royal_alert + 1)

            self.last_action_note = (
                f"The {guard['label'].lower()} throws down his royal "
                "badge and joins the rebellion. A runner still reaches "
                "the royal camp. "
                f"Royal Alert: {self.royal_alert}/5."
            )

            packet = self._resolve("help", self.location)
            self._check_capture()

            return packet

        self.heat = min(10, self.heat + 1)
        self.royal_alert = min(5, self.royal_alert + 1)
        town["fear"] = min(5, fear_before + 1)

        self.last_action_note = (
            f"The {guard['label'].lower()} rejects the offer and "
            "reaches for his signal whistle. You escape before "
            "reinforcements arrive. "
            f"Royal Alert: {self.royal_alert}/5."
        )

        self._check_capture()

        return None


    def _guard_combat_witnesses(
        self,
        town_id: str,
    ) -> int:
        """
        Estimate how many townspeople clearly see the confrontation.

        This is a social-exposure signal, not a literal population count.
        """

        town = self.towns[town_id]
        trust = self.town_trust(town_id)

        witnesses = 1

        if town["fear"] <= 1:
            witnesses += 2
        elif town["fear"] <= 3:
            witnesses += 1

        if trust >= 0.12:
            witnesses += 1

        if town["population"] >= 20:
            witnesses += 1

        return max(1, min(5, witnesses))

    def _guard_witness_phrase(self, witnesses: int) -> str:
        phrases = {
            1: "One figure watches from a shuttered doorway.",
            2: "A couple of townspeople watch from the edge of the street.",
            3: "Several townspeople watch without speaking.",
            4: "A small crowd gathers at a careful distance.",
            5: "The whole street seems to hold its breath and watch.",
        }

        return phrases[max(1, min(5, witnesses))]

    def _guard_combat_tell(self, intent: str) -> str:
        """Return the physical tell for the guard's current intent."""
        return self._guards.combat_intent(intent)["tell"]

    def _next_guard_combat_intent(self) -> str:
        """Choose the next readable guard intent from the seeded RNG."""
        return self.rng.choice(
            self._guards.combat_intents()
        )

    def guard_combat_status(self) -> dict | None:
        combat = self.guard_combat

        if combat is None:
            return None

        active_guard = self.active_guard(combat["town"])

        guard_id = combat.get(
            "guard_id",
            active_guard["id"] if active_guard else "",
        )
        guard_rank = combat.get(
            "guard_rank",
            active_guard["rank"]
            if active_guard
            else "watchman",
        )
        guard_label = combat.get(
            "guard_label",
            active_guard["label"]
            if active_guard
            else "Royal Guard",
        )

        free_attack = bool(combat.get("free_attack", False))

        return {
            "stage": combat.get("stage", "combat"),
            "town": combat["town"],
            "guard_id": guard_id,
            "guard_rank": guard_rank,
            "guard_label": guard_label,
            "guards_remaining": self.guard_count(
                combat["town"]
            ),
            "exchange_count": combat.get("exchange_count", 0),
            "player_health": combat["player_health"],
            "player_max_health": combat["player_max_health"],
            "guard_health": combat["guard_health"],
            "guard_max_health": combat["guard_max_health"],
            "guard_intent": combat["intent"],
            "guard_tell": (
                "The guard is out of form. You have a free attack."
                if free_attack
                else self._guard_combat_tell(combat["intent"])
            ),
            "free_attack": free_attack,
            "conduct": combat.get("conduct", 0),
            "correct_reads": combat.get("correct_reads", 0),
            "wrong_reads": combat.get("wrong_reads", 0),
            "witnesses": combat.get("witnesses", 1),
            "combat_noise": combat.get("combat_noise", 0),
        }

    def _finish_guard_combat_victory(self) -> dict | None:
        combat = self.guard_combat

        if combat is None:
            return self._deny(
                "There is no active guard combat to finish."
            )

        combat["stage"] = "down"
        combat["free_attack"] = False

        witnesses = combat.get("witnesses", 1)

        self.last_action_note = (
            f"Your final blow sends the "
            f"{combat.get('guard_label', 'royal guard').lower()} "
            "to the stones. "
            f"{self._guard_witness_phrase(witnesses)} "
            "He is disarmed and alive. Decide what the town sees next."
        )

        return None

    def _finish_guard_combat_loss(self) -> None:
        combat = self.guard_combat

        if combat is None:
            return self._deny(
                "There is no active guard combat to finish."
            )

        town_id = combat["town"]
        town = self.towns[town_id]
        fear_before = town["fear"]

        outcome = self._guards.resolve_player_loss_outcome(
            rank=combat["guard_rank"],
            roll=self.rng.randint(1, 100),
            trust=self.town_trust(town_id),
            fear=fear_before,
            witnesses=combat.get("witnesses", 1),
            royal_alert=self.royal_alert,
            execution_memory=self.town_execution_memory(town_id),
        )

        self.guard_combat = None

        if outcome["outcome"] == "escape":
            self.heat = min(10, self.heat + 2)
            self.royal_alert = min(5, self.royal_alert + 2)
            town["fear"] = min(5, fear_before + 1)

            self.last_action_note = (
                "The guard drops you and calls for the royal camp. "
                "You escape into the streets before the patrol closes. "
                f"Royal Alert: {self.royal_alert}/5."
            )
            return None

        self.heat = min(10, self.heat + 2)
        self.royal_alert = min(5, self.royal_alert + 2)
        town["fear"] = min(5, fear_before + 1)

        if outcome["outcome"] == "detention":
            self.captured = True
            self.alive = False
            self.ending = (
                "The royal guard detains you before the rebellion "
                "can grow."
            )
            self.last_action_note = (
                "The guard disarms you and calls the royal patrol. "
                "You are detained before the rebellion can grow."
            )
            return None

        self.alive = False
        self.captured = False
        self.ending = (
            "The royal guard kills you in the street before the "
            "rebellion can grow."
        )
        self.last_action_note = (
            "The guard's final strike leaves you in the street. "
            "The rebellion ends before it can grow."
        )

        return None


    def resolve_guard_down(
        self,
        choice: str,
    ) -> dict | None:
        """
        Resolve the social meaning of a defeated guard.

        GuardSystem classifies the pure outcome. This facade applies
        mutable world state, Ghost effects, TownMemory, and presentation.
        """
        combat = self.guard_combat

        if combat is None or combat.get("stage") != "down":
            return self._deny(
                "There is no defeated guard waiting for a decision."
            )

        town_id = combat["town"]
        town = self.towns[town_id]

        trust_before = self.town_trust(town_id)
        fear_before = town["fear"]
        conduct = combat.get("conduct", 0)
        witnesses = combat.get("witnesses", 1)

        try:
            outcome = self._guards.resolve_guard_down_outcome(
                choice=choice,
                conduct=conduct,
                trust=trust_before,
                fear=fear_before,
                witnesses=witnesses,
            )
        except ValueError as error:
            return self._deny(str(error))

        outcome_name = outcome["outcome"]

        allowed_outcomes = {
            "leave_support",
            "leave_neutral",
            "execution_accepted",
            "execution_rejected",
            "execution_uncertain",
        }

        if outcome_name not in allowed_outcomes:
            raise RuntimeError(
                f"unknown guard-down outcome: {outcome_name}"
            )

        guard_id = combat.get("guard_id")

        if not isinstance(guard_id, str) or not guard_id:
            active_guard = self.active_guard(town_id)

            if active_guard is None:
                raise RuntimeError(
                    "guard-down resolution has no active guard"
                )

            guard_id = active_guard["id"]

        self._remove_guard(
            town_id,
            guard_id,
        )
        self.guards_defeated += 1

        self.guard_combat = None

        self.gold += outcome["gold_delta"]

        self.heat = min(
            10,
            self.heat + outcome["heat_delta"],
        )

        self.royal_alert = min(
            5,
            self.royal_alert
            + outcome["royal_alert_delta"],
        )

        fear_delta = outcome["fear_delta"]

        if fear_delta:
            town["fear"] = max(
                0,
                min(
                    5,
                    fear_before + fear_delta,
                ),
            )

        memory_response = outcome[
            "execution_memory_response"
        ]

        if memory_response is not None:
            self._record_town_execution_memory(
                town_id,
                memory_response,
            )

        messages = {
            "leave_support": (
                "You take the guard's 6-gold pay pouch and leave "
                "him alive. The witnesses see control instead of "
                "cruelty, and the town begins to believe in you. "
                f"Royal Alert: {self.royal_alert}/5."
            ),
            "leave_neutral": (
                "You take the guard's 6-gold pay pouch and leave him "
                "alive. The witnesses remember the victory, but they "
                "do not yet know what kind of ruler you will become. "
                f"Royal Alert: {self.royal_alert}/5."
            ),
            "execution_accepted": (
                "You execute the guard before the witnesses. In this "
                "town, the act is seen as justice against the crown. "
                f"Royal Alert: {self.royal_alert}/5."
            ),
            "execution_rejected": (
                "You execute the guard before the witnesses. The street "
                "goes silent, and people pull away from you in fear. "
                "The town will carry the memory of this execution. "
                f"Royal Alert: {self.royal_alert}/5."
            ),
            "execution_uncertain": (
                "You execute the guard before the witnesses. No one "
                "speaks as the crowd decides what that victory means. "
                "The memory will remain in the town for a while. "
                f"Royal Alert: {self.royal_alert}/5."
            ),
        }

        self.last_action_note = messages[outcome_name]

        ghost_event = outcome["ghost_event"]

        if ghost_event is None:
            self._check_capture()
            return None

        packet = self._resolve(
            ghost_event,
            town_id,
        )

        self._check_capture()

        return packet



    def retreat_guard_combat(self) -> dict | None:
        combat = self.guard_combat

        if combat is None:
            return self._deny(
                "There is no active guard combat to leave."
            )

        self.heat = min(10, self.heat + 1)
        self.royal_alert = min(5, self.royal_alert + 1)

        self.guard_combat = None

        self.last_action_note = (
            "You break contact before the guard can force the issue. "
            f"Royal Alert: {self.royal_alert}/5."
        )

        return None


    def resolve_guard_combat_move(
        self,
        move: str,
    ) -> dict | None:
        combat = self.guard_combat

        if combat is None:
            return self._deny(
                "There is no active guard combat."
            )

        if combat.get("stage") != "combat":
            return self._deny(
                "The guard is down. Decide what happens next."
            )

        normalized = (
            move.strip().lower()
            if isinstance(move, str)
            else move
        )

        kwargs = {
            "rank": combat["guard_rank"],
            "intent": combat["intent"],
            "player_move": normalized,
            "free_attack": bool(
                combat.get("free_attack", False)
            ),
        }

        if (
            not kwargs["free_attack"]
            and combat["intent"] == "tight_defense"
            and normalized in ("feint_heavy", "feint_light")
        ):
            kwargs["feint_read_roll"] = self.rng.randint(
                1,
                100,
            )
            kwargs["counter_roll"] = self.rng.randint(
                1,
                100,
            )

        if (
            not kwargs["free_attack"]
            and normalized in ("parry", "deflect")
        ):
            kwargs["technique_roll"] = self.rng.randint(
                1,
                100,
            )

        try:
            exchange = self._guards.resolve_tactical_exchange(
                **kwargs,
            )
        except ValueError as error:
            return self._deny(str(error))

        combat["exchange_count"] = (
            combat.get("exchange_count", 0) + 1
        )
        combat["guard_health"] = max(
            0,
            combat["guard_health"]
            - exchange["guard_damage"],
        )
        combat["player_health"] = max(
            0,
            combat["player_health"]
            - exchange["player_damage"],
        )
        combat["conduct"] = (
            combat.get("conduct", 0)
            + exchange["conduct_delta"]
        )
        combat["correct_reads"] = (
            combat.get("correct_reads", 0)
            + exchange["correct_reads_delta"]
        )
        combat["wrong_reads"] = (
            combat.get("wrong_reads", 0)
            + exchange["wrong_reads_delta"]
        )

        if combat["guard_health"] <= 0:
            return self._finish_guard_combat_victory()

        if combat["player_health"] <= 0:
            return self._finish_guard_combat_loss()

        message = exchange["message"]

        if exchange["free_attack"]:
            combat["free_attack"] = True
            self.last_action_note = message
            return None

        combat["free_attack"] = False
        combat["intent"] = self._next_guard_combat_intent()

        if combat["exchange_count"] % 3 == 0:
            combat["combat_noise"] = (
                combat.get("combat_noise", 0) + 1
            )
            self.heat = min(10, self.heat + 1)
            self.royal_alert = min(5, self.royal_alert + 1)
            message += (
                " The prolonged clash draws royal attention. "
                f"Royal Alert: {self.royal_alert}/5."
            )

        self.last_action_note = (
            f"{message} "
            f"{self._guard_combat_tell(combat['intent'])}"
        )

        return None


    def fight_guard(self) -> dict | None:
        """
        Begin one health-based tactical duel against a named guard.

        Player health is fresh for every duel. The leader's personal
        Knight's Sword is permanent; army weapon stock is not duel fuel.
        """
        if self.guard_combat is not None:
            return self._deny(
                "You are already in a guard combat exchange."
            )

        if self.phase != "rebellion":
            return self._deny(
                "Guard confrontations are only available during "
                "rebellion days."
            )

        if self.location not in self.towns:
            return self._deny(
                "There is no royal guard to confront here."
            )

        guard = self.active_guard(self.location)

        if guard is None:
            return self._deny(
                "There is no active royal guard in this town."
            )

        if self.location == self.knight_town:
            return self._deny(
                "The knight controls this street. A lone challenge "
                "would bring a military response. You need a larger "
                "operation before confronting Crownmarket's guard."
            )

        if self.guard_passage_active(self.location):
            return self._deny(
                "The guard is looking the other way until sundown. "
                "Use the safe passage or return tomorrow."
            )

        if not self.primary_weapon:
            return self._deny(
                "You need your personal weapon before confronting "
                "a royal guard."
            )

        if not self._spend_action():
            return self._deny(
                "No actions remain. End the day or leave town."
            )

        profile = self._guards.guard_profile(guard["rank"])
        intent = self._next_guard_combat_intent()

        self.guard_combat = {
            "stage": "combat",
            "town": self.location,
            "guard_id": guard["id"],
            "guard_rank": guard["rank"],
            "guard_label": guard["label"],
            "player_health": 10,
            "player_max_health": 10,
            "guard_health": profile["max_health"],
            "guard_max_health": profile["max_health"],
            "intent": intent,
            "exchange_count": 0,
            "free_attack": False,
            "conduct": 0,
            "correct_reads": 0,
            "wrong_reads": 0,
            "combat_noise": 0,
            "witnesses": self._guard_combat_witnesses(
                self.location
            ),
        }

        self.last_action_note = (
            f"You face a {guard['label'].lower()}. "
            f"{self._guard_combat_tell(intent)}"
        )

        return None



    def scout_target(self, target: str) -> bool:
        self.last_action_note = (
            "Kingdom intel now comes from assigned scouts "
            "when the rebellion day ends."
        )
        return False

    def scout(self) -> bool:
        self.last_action_note = (
            "Assign followers as scouts at the hidden base, "
            "then review reports after day end."
        )
        return False

    def buy_food(self, item: str) -> bool:
        prices = {
            "bread": 6,
            "meat": 14,
            "vegetables": 10,
        }
        food_gain = {
            "bread": 1,
            "meat": 3,
            "vegetables": 2,
        }

        if self.phase != "rebellion":
            return False

        if self.location not in self.towns:
            return False

        if item not in prices:
            return False

        town = self.towns[self.location]

        if town["locked"]:
            self.last_action_note = (
                "The lockdown has closed this food stall."
            )
            return False

        if self.gold < prices[item]:
            self.last_action_note = (
                "You do not have enough gold for that food."
            )
            return False

        if not self._spend_action():
            self.last_action_note = (
                "No actions remain. End the day or leave town."
            )
            return False

        self.gold -= prices[item]
        self.food += food_gain[item]

        return True

    def blacksmith_buy(self, item: str) -> bool:
        prices = {
            "sword": 12,
            "spear": 14,
            "shield": 10,
            "axe": 15,
            "bow": 16,
            "repair": 6,
        }

        if self.phase != "rebellion":
            return False

        if self.location not in self.towns:
            return False

        if item not in prices:
            return False

        if self.gold < prices[item]:
            self.last_action_note = (
                "You do not have enough gold for that item."
            )
            return False

        if not self._spend_action():
            self.last_action_note = (
                "No actions remain. End the day or leave town."
            )
            return False

        self.gold -= prices[item]

        if item == "repair":
            self.armor += 1
            self.armor_item = "repaired armor"
        elif item == "shield":
            self.shield_stock["light"] += 1
            self.armor += 1
            self.armor_item = "light shield"
        else:
            self.weapon_stock[item] += 1
            self._sync_weapon_total()
            self.primary_weapon = item

        self.last_action_note = (
            f"You acquire a {item.replace('_', ' ')}."
        )

        return True

    def buy_common_goods(self, item: str) -> bool:
        prices = {
            "seeds": 8,
            "cooking_kit": 10,
        }

        if self.phase != "rebellion":
            return False

        if self.location not in self.towns:
            return False

        if item not in prices:
            return False

        if self.gold < prices[item]:
            self.last_action_note = (
                "You do not have enough gold for that item."
            )
            return False

        if not self._spend_action():
            self.last_action_note = (
                "No actions remain. End the day or leave town."
            )
            return False

        self.gold -= prices[item]

        if item == "seeds":
            self.seeds += 1
        else:
            self.cooking_kits += 1

        return True

    def bar_rumor(self) -> dict | None:
        if self.phase != "rebellion":
            return self._deny(
                "The bar is closed outside rebellion days."
            )

        if self.location not in self.towns:
            return self._deny(
                "There is no bar here."
            )

        if not self._daily_cap_available(
            self.location,
            "bar",
        ):
            return None

        if not self._spend_action():
            return self._deny(
                "No actions remain. End the day or leave town."
            )

        self._mark_daily_cap(self.location, "bar")
        self.heat = max(0, self.heat - 1)
        self.last_action_note = (
            "Whispers travel faster than royal patrols."
        )

        return self._resolve("help", self.location)

    def bar_recruit_quietly(self) -> dict | None:
        if self.location not in self.towns:
            return self._deny("There is no bar here.")

        if not self._daily_cap_available(
            self.location,
            "bar",
        ):
            return None

        packet = self.recruit_quietly()

        if packet is not None:
            self._mark_daily_cap(self.location, "bar")

        return packet

    def bar_local_work(self) -> dict | None:
        if self.location not in self.towns:
            return self._deny("There is no bar here.")

        if not self._daily_cap_available(
            self.location,
            "bar",
        ):
            return None

        packet = self.earn_honest_gold()

        if packet is not None:
            self._mark_daily_cap(self.location, "bar")

        return packet

    def public_event(self) -> dict | None:
        """
        Backward-compatible public-event API.
        """

        return self.speak_publicly()

    def set_assignment(
        self,
        assignment: str,
        amount: int,
    ) -> bool:
        if self.phase != "camp":
            return False

        if assignment not in self.assignments:
            return False

        if not isinstance(amount, int) or amount < 0:
            return False

        current = self.assignments[assignment]
        proposed_total = self.assignment_total() - current + amount

        if proposed_total > self.worker_followers():
            return False

        self.assignments[assignment] = amount

        return True

    def train_rebels(self) -> bool:
        if self.phase != "camp":
            return False

        if self.followers < 3:
            return False

        if self.food <= 0:
            return False

        if not self._spend_action():
            return False

        self.food -= 1
        self.weapon_stock["sword"] += 1
        self._sync_weapon_total()

        return True

    def castle_pressure(self) -> dict | None:
        if self.phase != "rebellion":
            return None

        if self.location != "castle":
            return None

        if not self._spend_action():
            return None

        self.heat = min(10, self.heat + 3)

        packet = self._resolve("threat", "king")

        if self.followers >= 35:
            self.followers += 3
            self.king_control = max(0, self.king_control - 1)

        self._check_capture()

        return packet

    def calculate_rebellion_strength(self) -> dict:
        """
        Return the deterministic castle-siege readiness packet.

        Army strength decides whether the rebellion reaches the king.
        It does not decide the king fight itself.
        """
        town_support = sum(
            1
            for town_id in TOWN_IDS
            if self.town_trust(town_id) >= 0.25
        )

        strength = (
            self.followers
            + self.weapons * 2
            + self.armor
            + town_support * 4
            + self.guards_defeated * 2
            - self.king_control
        )

        minimum = 35
        strong = 48

        return {
            "followers": self.followers,
            "weapons": self.weapons,
            "armor": self.armor,
            "town_support": town_support,
            "guards_defeated": self.guards_defeated,
            "king_control": self.king_control,
            "strength": strength,
            "minimum_required": minimum,
            "strong_threshold": strong,
            "reaches_king": strength >= minimum,
            "prepared_assault": strength >= strong,
            "wounded_start": minimum <= strength < strong,
        }

    def siege_warning(self) -> dict:
        warning = self.calculate_rebellion_strength()
        warning["likely_success"] = warning["reaches_king"]
        return warning

    def endgame_action_label(self) -> str:
        """Return the current red endgame-button label."""
        if (
            self.phase == "crown"
            and isinstance(self.king_fight, dict)
            and self.king_fight.get("stage") == "crown_loop"
        ):
            return "Retire the Crown"

        return "Siege the Castle"

    def _final_kingdom_stats(self) -> dict:
        return self._snapshot_copy(
            {
                "phase": self.phase,
                "phase_number": self.phase_number,
                "phase_day": self.phase_day,
                "location": self.location,
                "followers": self.followers,
                "gold": self.gold,
                "food": self.food,
                "weapons": self.weapons,
                "weapon_stock": self.weapon_stock,
                "armor": self.armor,
                "armor_item": self.armor_item,
                "heat": self.heat,
                "royal_alert": self.royal_alert,
                "guards_defeated": self.guards_defeated,
                "king_control": self.king_control,
                "towns": {
                    town_id: {
                        "name": town["name"],
                        "recruited": town["recruited"],
                        "fear": town["fear"],
                        "rebel_controlled": (
                            town["rebel_controlled"]
                        ),
                        "trust": self.town_trust(town_id),
                        "memory": self.town_memory_label(town_id),
                    }
                    for town_id, town in self.towns.items()
                },
            },
            "final kingdom stats",
        )

    def final_ending_packet(self) -> dict:
        """
        Return the current terminal ending packet.

        If the run has not reached a terminal ending, the packet reports
        the current endgame state without marking the game complete.
        """
        if isinstance(self.last_packet, dict) and self.ending:
            return self._snapshot_copy(
                self.last_packet,
                "final ending packet",
            )

        return self._snapshot_copy(
            {
                "outcome": (
                    self.king_fight.get("stage")
                    if isinstance(self.king_fight, dict)
                    else "in_progress"
                ),
                "ending": self.ending,
                "complete": bool(self.ending),
                "player_alive": self.alive,
                "player_captured": self.captured,
                "king_fight": self.king_fight,
                "final_stats": self._final_kingdom_stats(),
            },
            "final ending packet",
        )

    def _set_final_ending(
        self,
        *,
        outcome: str,
        ending: str,
        ending_type: str,
        king_status: str,
        rebellion_status: str,
        extra: dict | None = None,
    ) -> dict:
        self.ending = ending

        packet = {
            "outcome": outcome,
            "ending_type": ending_type,
            "ending": self.ending,
            "player_alive": self.alive,
            "player_captured": self.captured,
            "king_status": king_status,
            "rebellion_status": rebellion_status,
            "king_fight": self.king_fight,
            "final_stats": self._final_kingdom_stats(),
        }

        if extra:
            packet.update(deepcopy(extra))

        packet = self._snapshot_copy(
            packet,
            "final ending packet",
        )
        self.last_packet = packet
        self.last_action_note = ending

        return deepcopy(packet)

    def _king_damage(self, base: int) -> int:
        """Return exact duel damage without siege-strength multipliers."""
        return max(0, int(base))

    def _deny_parry_opening_move(
        self,
        move: str,
    ) -> dict:
        """
        Reject a move that is illegal during a parry continuation.

        The continuation remains available and no combat state, health,
        exchange counter, or castle time is consumed.
        """
        fight = self.king_fight
        opening = fight.get("parry_opening")
        stage = fight["stage"]

        message = (
            "Your parry opening only allows a heavy or light attack. "
            "The opening remains available."
        )

        self.last_action_note = message

        packet = {
            "outcome": "parry_opening_move_denied",
            "stage": stage,
            "message": message,
            "attempted_move": move,
            "allowed_moves": ["heavy", "light"],
            "player_health": fight["player_health"],
            "king_health": fight["king_health"],
            "castle_timer": fight["castle_timer"],
            "parry_opening": deepcopy(opening),
            "forced_response": self._public_forced_response(
                fight.get("forced_response")
            ),
            "initiative": deepcopy(
                fight.get("initiative")
            ),
            "state_mutated": False,
        }

        if stage == "elite_knight":
            packet["elite_knight_health"] = (
                fight["elite_knight_health"]
            )

        return packet

    def _ensure_king_fight_initiative(self) -> dict:
        fight = self.king_fight

        if fight is None:
            return self._social.advance_combat_initiative(
                previous_state="neutral",
                event="fight_started",
            )

        packet = fight.get("initiative")

        if (
            not isinstance(packet, dict)
            or packet.get("kind") != "combat_initiative"
            or packet.get("state") not in {
                "enemy_advantage",
                "neutral",
                "player_advantage",
            }
        ):
            packet = self._social.advance_combat_initiative(
                previous_state="neutral",
                event="fight_started",
            )
            fight["initiative"] = deepcopy(packet)

        return deepcopy(packet)

    def _advance_king_fight_initiative(
        self,
        event: str,
    ) -> dict:
        fight = self.king_fight
        current = self._ensure_king_fight_initiative()
        packet = self._social.advance_combat_initiative(
            previous_state=current["state"],
            event=event,
        )

        if fight is not None:
            fight["initiative"] = deepcopy(packet)

        return deepcopy(packet)

    def _king_fight_initiative_event(
        self,
        *,
        move: str,
        damage_to_enemy: int,
        damage_to_player: int,
        opponent_reaction,
        reaction_missed: bool | None,
    ) -> str:
        if damage_to_player > 0:
            return "enemy_hit"

        if opponent_reaction is not None:
            return "enemy_counter"

        if damage_to_enemy > 0:
            if reaction_missed is True:
                return "prediction_missed_player_hit"
            return "player_attack_hit"

        if move == "parry":
            return "player_parry"

        if move == "deflect":
            return "player_deflect"

        if move == "dodge":
            if reaction_missed is True:
                return "prediction_missed_player_escape"
            return "player_dodge"

        return "preserve"

    @staticmethod
    def _public_forced_response(
        forced_response,
    ) -> dict | None:
        if not isinstance(forced_response, dict):
            return None

        public = deepcopy(forced_response)
        read_packet = public.get("recovery_read")

        if isinstance(read_packet, dict):
            public["recovery_read"] = {
                "kind": "combat_recovery_read",
                "state_owner": "Ghost",
                "selection_key": read_packet.get(
                    "selection_key"
                ),
                "hidden_until_resolution": True,
                "locked": True,
            }

        return public


    def king_fight_opponent_observation(
        self,
    ) -> dict | None:
        """
        Return the limited observation packet available to an
        optional external opponent policy.

        The packet exposes legal intentions and visible combat
        pressure only. It does not allow the policy to resolve
        damage, health changes, transitions, death, or victory.
        """
        fight = self.king_fight

        if fight is None or self.ending:
            return None

        stage = fight.get("stage")

        if stage == "elite_knight":
            enemy_actor = "elite_knight"
            enemy_display_name = (
                "the King's Champion"
            )
            enemy_personality = (
                "disciplined royal protector"
            )
            legal_intents = (
                "shield_wall",
                "champion_lunge",
                "wide_execution",
                "open_recovery",
            )
            intent_labels = {
                "shield_wall": "Shield Wall",
                "champion_lunge": (
                    "Champion Lunge"
                ),
                "wide_execution": (
                    "Wide Execution"
                ),
                "open_recovery": (
                    "Open Recovery"
                ),
            }
            intent_options = {
                "shield_wall": (
                    "Protect position under direct pressure "
                    "and punish deception only when resolved "
                    "evidence supports that read."
                ),
                "champion_lunge": (
                    "Launch direct armored pressure and "
                    "pursue a credible finishing line."
                ),
                "wide_execution": (
                    "Commit to a broad power attack that "
                    "pressures passive or mistimed defense."
                ),
                "open_recovery": (
                    "Accept a real punishable opening only "
                    "when its strategic payoff justifies "
                    "the exposure."
                ),
            }
            enemy_health = int(
                fight.get(
                    "elite_knight_health",
                    0,
                )
            )
            enemy_max_health = int(
                fight.get(
                    "elite_knight_max_health",
                    1,
                )
            )
            enemy_damage_key = (
                "elite_knight_damage"
            )
        elif stage in (
            "king_phase_one",
            "king_phase_two",
        ):
            enemy_actor = "king"
            enemy_display_name = "the king"

            if stage == "king_phase_two":
                enemy_personality = (
                    "desperate wounded tactician"
                )
            else:
                enemy_personality = (
                    "proud calculating monarch"
                )

            legal_intents = (
                "royal_lunge",
                "crown_guard",
                "overextended_recovery",
            )
            intent_labels = {
                "royal_lunge": "Royal Lunge",
                "crown_guard": "Crown Guard",
                "overextended_recovery": (
                    "Open Recovery"
                ),
            }
            intent_options = {
                "royal_lunge": (
                    "Commit to center-line pressure and "
                    "punish offensive overcommitment."
                ),
                "crown_guard": (
                    "Preserve a guarded center and punish "
                    "direct predictable attacks."
                ),
                "overextended_recovery": (
                    "Accept a real punishable opening only "
                    "when its strategic payoff justifies "
                    "the exposure."
                ),
            }
            enemy_health = int(
                fight.get(
                    "king_health",
                    0,
                )
            )
            enemy_max_health = int(
                fight.get(
                    "king_max_health",
                    1,
                )
            )
            enemy_damage_key = "king_damage"
        else:
            return None

        exchange_count = int(
            fight.get(
                "exchange_count",
                0,
            )
        )

        selection_key = (
            f"{stage}:{exchange_count}"
        )

        fallback_intent = fight.get(
            "intent"
        )

        if fallback_intent not in legal_intents:
            fallback_intent = legal_intents[
                exchange_count
                % len(legal_intents)
            ]

        reaction_plan_labels = (
            self
            ._king_fight_reaction_plan_labels()
        )

        legal_reaction_plans_by_intent = {
            candidate_intent: list(
                self
                ._king_fight_reaction_plan_catalog(
                    stage,
                    candidate_intent,
                )
            )
            for candidate_intent
            in legal_intents
        }

        fallback_reaction_plan = (
            self
            ._king_fight_default_reaction_plan(
                stage,
                fallback_intent,
            )
        )

        enemy_ratio = (
            enemy_health
            / max(
                1,
                enemy_max_health,
            )
        )

        if enemy_ratio <= 0.25:
            enemy_health_band = "critical"
        elif enemy_ratio <= 0.50:
            enemy_health_band = "wounded"
        elif enemy_ratio <= 0.75:
            enemy_health_band = "pressured"
        else:
            enemy_health_band = "steady"

        player_health = int(
            fight.get(
                "player_health",
                0,
            )
        )
        player_max_health = int(
            fight.get(
                "player_max_health",
                1,
            )
        )

        player_ratio = (
            player_health
            / max(
                1,
                player_max_health,
            )
        )

        if player_ratio <= 0.25:
            player_health_band = "critical"
        elif player_ratio <= 0.60:
            player_health_band = "wounded"
        else:
            player_health_band = "steady"

        castle_timer = int(
            fight.get(
                "castle_timer",
                0,
            )
        )

        if castle_timer <= 3:
            castle_timer_band = "critical"
        elif castle_timer <= 7:
            castle_timer_band = "urgent"
        else:
            castle_timer_band = "active"

        patterns = (
            self._ensure_king_fight_pattern_state()
        )

        recent_moves = [
            move
            for move in patterns.get(
                "last_moves",
                [],
            )
            if isinstance(move, str)
        ][-4:]

        combat_initiative = (
            self._ensure_king_fight_initiative()
        )

        light_count = int(
            patterns.get("light_count", 0)
        )
        dodge_count = int(
            patterns.get("dodge_count", 0)
        )

        fallback_forced_response_read = (
            "light"
            if light_count > dodge_count
            else "dodge"
        )

        last_exchange = fight.get(
            "last_exchange"
        )

        previous_exchange_evidence = None

        if (
            isinstance(last_exchange, dict)
            and last_exchange.get("stage")
            == stage
        ):
            previous_result = (
                last_exchange.get("result")
            )

            damage_suffered = int(
                last_exchange.get(
                    enemy_damage_key,
                    0,
                )
                or 0
            )

            damage_dealt = int(
                last_exchange.get(
                    "player_damage",
                    0,
                )
                or 0
            )

            intent_was_countered = (
                previous_result
                in (
                    "correct_read",
                    "parry_opening_hit",
                    "forced_light_landed",
                    "forced_dodge_escaped",
                )
            )

            enemy_succeeded = (
                previous_result
                in (
                    "king_hit",
                    "failed_knight_read",
                    "forced_recovery_denied",
                )
            )

            previous_exchange_evidence = {
                "enemy_intent": (
                    last_exchange.get("intent")
                ),
                "enemy_intent_label": (
                    intent_labels.get(
                        last_exchange.get(
                            "intent"
                        )
                    )
                ),
                "player_move": (
                    last_exchange.get("move")
                ),
                "result": previous_result,
                "damage_suffered_by_enemy": (
                    damage_suffered
                ),
                "damage_received_by_player": (
                    damage_dealt
                ),
                "intent_was_countered": (
                    intent_was_countered
                ),
                "enemy_succeeded": (
                    enemy_succeeded
                ),
                "opponent_reaction_plan": (
                    last_exchange.get(
                        "opponent_reaction_plan"
                    )
                ),
                "opponent_reaction_plan_label": (
                    last_exchange.get(
                        "opponent_reaction_plan_label"
                    )
                ),
                "reaction_plan_predictive": (
                    last_exchange.get(
                        "reaction_plan_predictive"
                    )
                ),
                "reaction_plan_matched": (
                    last_exchange.get(
                        "reaction_plan_matched"
                    )
                ),
                "reaction_plan_triggered": (
                    last_exchange.get(
                        "reaction_plan_triggered"
                    )
                ),
                "reaction_plan_missed": (
                    last_exchange.get(
                        "reaction_plan_missed"
                    )
                ),
                "reaction_miss_exposed_enemy": (
                    last_exchange.get(
                        "reaction_miss_exposed_enemy"
                    )
                ),
                "reaction_miss_bonus": (
                    last_exchange.get(
                        "reaction_miss_bonus"
                    )
                ),
                "resolution_source": (
                    last_exchange.get(
                        "resolution_source"
                    )
                ),
                "opponent_control_source": (
                    last_exchange.get(
                        "opponent_control_source",
                        (
                            "llm_commitment_ghost_resolution"
                            if last_exchange.get(
                                "opponent_intent_reason"
                            )
                            or last_exchange.get(
                                "opponent_reaction_reason"
                            )
                            else "ghost_resolution"
                        ),
                    )
                ),
                "opponent_intent_reason": (
                    last_exchange.get(
                        "opponent_intent_reason"
                    )
                ),
                "opponent_reaction_reason": (
                    last_exchange.get(
                        "opponent_reaction_reason"
                    )
                ),
                "opponent_proposal_reason": (
                    last_exchange.get(
                        "opponent_proposal_reason"
                    )
                ),
                "forced_response_read": (
                    last_exchange.get(
                        "forced_response_read"
                    )
                ),
                "forced_response_read_matched": (
                    last_exchange.get(
                        "forced_response_read_matched"
                    )
                ),
                "initiative_before": deepcopy(
                    last_exchange.get(
                        "initiative_before"
                    )
                ),
                "initiative_after": deepcopy(
                    last_exchange.get(
                        "initiative_after"
                    )
                ),
                "initiative_event": (
                    last_exchange.get(
                        "initiative_event"
                    )
                ),
            }

        locked_reason = None

        if isinstance(
            fight.get("forced_response"),
            dict,
        ):
            locked_reason = (
                "forced_response_pending"
            )
        elif isinstance(
            fight.get("parry_opening"),
            dict,
        ):
            locked_reason = (
                "parry_opening_pending"
            )

        existing_audit = fight.get(
            "llm_opponent_audit"
        )

        already_selected = (
            isinstance(
                existing_audit,
                dict,
            )
            and existing_audit.get(
                "selection_key"
            )
            == selection_key
        )

        history = fight.setdefault(
            "llm_opponent_history",
            [],
        )

        if not isinstance(history, list):
            history = []
            fight["llm_opponent_history"] = (
                history
            )

        stage_history = [
            item
            for item in history
            if (
                isinstance(item, dict)
                and item.get("stage") == stage
                and item.get(
                    "selected_intent"
                )
                in legal_intents
            )
        ]

        recent_opponent_intents = [
            item["selected_intent"]
            for item in stage_history[-4:]
        ]

        same_intent_streak = 0

        if recent_opponent_intents:
            latest_intent = (
                recent_opponent_intents[-1]
            )

            for item in reversed(
                recent_opponent_intents
            ):
                if item != latest_intent:
                    break

                same_intent_streak += 1

        morale_ticks = int(
            fight.get(
                "king_morale_ticks",
                0,
            )
        )

        if morale_ticks >= 3:
            morale_band = "high"
        elif morale_ticks >= 1:
            morale_band = "rising"
        else:
            morale_band = "low"

        combat_objective = (
            self._social.build_combat_objective(
                actor=enemy_actor,
                target="player",
                actor_health=enemy_health,
                actor_max_health=(
                    enemy_max_health
                ),
                target_health=player_health,
                target_max_health=(
                    player_max_health
                ),
                turns_remaining=castle_timer,
                expected_damage_per_success=3,
                deadline_label=(
                    "castle collapse"
                ),
            )
        )

        return {
            "selection_key": selection_key,
            "selection_required": (
                not already_selected
                and locked_reason is None
            ),
            "locked_reason": locked_reason,
            "stage": stage,
            "enemy_actor": enemy_actor,
            "enemy_display_name": (
                enemy_display_name
            ),
            "enemy_personality": (
                enemy_personality
            ),
            "combat_objective": (
                deepcopy(
                    combat_objective
                )
            ),
            "combat_initiative": (
                deepcopy(combat_initiative)
            ),
            "legal_forced_response_reads": [
                "light",
                "dodge",
            ],
            "fallback_forced_response_read": (
                fallback_forced_response_read
            ),
            "legal_intents": list(
                legal_intents
            ),
            "intent_labels": dict(
                intent_labels
            ),
            "intent_options": dict(
                intent_options
            ),
            "legal_reaction_plans_by_intent": (
                deepcopy(
                    legal_reaction_plans_by_intent
                )
            ),
            "reaction_plan_labels": dict(
                reaction_plan_labels
            ),
            "fallback_reaction_plan": (
                fallback_reaction_plan
            ),
            "fallback_reaction_plan_label": (
                reaction_plan_labels.get(
                    fallback_reaction_plan,
                    fallback_reaction_plan,
                )
            ),
            "fallback_intent": (
                fallback_intent
            ),
            "fallback_intent_label": (
                intent_labels.get(
                    fallback_intent,
                    fallback_intent,
                )
            ),
            "enemy_health_band": (
                enemy_health_band
            ),
            "player_health_band": (
                player_health_band
            ),
            "castle_timer_band": (
                castle_timer_band
            ),
            "king_morale_band": (
                morale_band
                if stage == "elite_knight"
                else "not_applicable"
            ),
            "recent_player_moves": (
                list(recent_moves)
            ),
            "previous_exchange_evidence": (
                deepcopy(
                    previous_exchange_evidence
                )
                if previous_exchange_evidence
                is not None
                else None
            ),
            "recent_opponent_intents": (
                list(
                    recent_opponent_intents
                )
            ),
            "same_intent_streak": (
                same_intent_streak
            ),
            "existing_audit": (
                deepcopy(existing_audit)
                if already_selected
                else None
            ),
            "state_owner": "Ghost",
            "llm_role": (
                "opponent_intent_proposal_only"
            ),
        }



    def king_fight_opponent_public_tell(
        self,
    ) -> dict | None:
        """
        Return observable combat evidence without exposing the
        opponent's authoritative internal intent name.
        """
        fight = self.king_fight

        if fight is None or self.ending:
            return None

        stage = fight.get("stage")

        forced = fight.get(
            "forced_response"
        )

        if isinstance(forced, dict):
            return {
                "tell": (
                    "Your footing is broken. The king "
                    "is already moving to capitalize, "
                    "leaving only a narrow recovery."
                ),
                "clarity": "direct_state",
                "intent_hidden": True,
                "source": (
                    "forced_response_observation"
                ),
            }

        opening = fight.get(
            "parry_opening"
        )

        if isinstance(opening, dict):
            return {
                "tell": (
                    "The king's guard is displaced. "
                    "The opening created by your parry "
                    "remains for one breath."
                ),
                "clarity": "direct_state",
                "intent_hidden": True,
                "source": (
                    "parry_opening_observation"
                ),
            }

        intent = fight.get("intent")

        if stage in (
            "king_phase_one",
            "king_phase_two",
        ):
            tells = {
                "royal_lunge": (
                    "The king lowers his center and "
                    "slides one foot through the ash, "
                    "his blade settling toward your "
                    "middle."
                ),
                "crown_guard": (
                    "The king draws his blade tight "
                    "beneath the crown and closes his "
                    "elbows, watching your shoulders "
                    "instead of your weapon."
                ),
                "overextended_recovery": (
                    "The king's last cut carries wide. "
                    "His crown-side shoulder hangs open "
                    "while his feet scramble back under "
                    "him."
                ),
            }
            enemy_actor = "king"
        elif stage == "elite_knight":
            tells = {
                "shield_wall": (
                    "The Champion squares his shield "
                    "and shortens his stance, steel "
                    "covering nearly every direct line."
                ),
                "champion_lunge": (
                    "The Champion sinks low behind the "
                    "shield, his rear leg coiling beneath "
                    "him."
                ),
                "wide_execution": (
                    "The Champion lets the blade circle "
                    "outside his frame, gathering weight "
                    "through his hips."
                ),
                "open_recovery": (
                    "The Champion drags one foot through "
                    "ash, his shield late and sword arm "
                    "slow to return."
                ),
            }
            enemy_actor = "elite_knight"
        else:
            return None

        tell = tells.get(intent)

        if tell is None:
            return None

        return {
            "tell": tell,
            "clarity": "ambiguous",
            "intent_hidden": True,
            "enemy_actor": enemy_actor,
            "source": (
                "deterministic_observable_cues"
            ),
        }


    def apply_king_fight_opponent_intent(
        self,
        proposed_intent,
        *,
        selection_key: str,
        proposed_reaction_plan: str | None = None,
        proposed_forced_response_read: str | None = None,
        provider_called: bool = False,
        parser_reason: str | None = None,
        reaction_parser_reason: str | None = None,
        proposal_reason: str | None = None,
        intent_explanation: str | None = None,
        reaction_explanation: str | None = None,
    ) -> dict:
        """
        Validate and lock an external opponent commitment.

        The policy proposes an intent and hidden reaction before the
        player chooses. Ghost validates both and owns all consequences.
        """
        observation = (
            self.king_fight_opponent_observation()
        )

        if observation is None:
            return {
                "accepted": False,
                "fallback_used": True,
                "reason": "no_active_fight",
                "selected_intent": None,
                "selected_reaction_plan": None,
                "state_owner": "Ghost",
            }

        fight = self.king_fight

        current_key = observation[
            "selection_key"
        ]

        existing_audit = observation.get(
            "existing_audit"
        )

        if isinstance(
            existing_audit,
            dict,
        ):
            return deepcopy(
                existing_audit
            )

        legal_intents = tuple(
            observation["legal_intents"]
        )

        intent_labels = observation.get(
            "intent_labels",
            {},
        )

        reaction_labels = observation.get(
            "reaction_plan_labels",
            {},
        )

        if not isinstance(
            intent_labels,
            dict,
        ):
            intent_labels = {}

        if not isinstance(
            reaction_labels,
            dict,
        ):
            reaction_labels = {}

        fallback_intent = observation[
            "fallback_intent"
        ]

        normalized_intent = None

        if isinstance(
            proposed_intent,
            str,
        ):
            normalized_intent = (
                proposed_intent
                .strip()
                .lower()
                .replace("-", "_")
                .replace(" ", "_")
            )

        normalized_reaction = None

        if isinstance(
            proposed_reaction_plan,
            str,
        ):
            normalized_reaction = (
                proposed_reaction_plan
                .strip()
                .lower()
                .replace("-", "_")
                .replace(" ", "_")
            )

        normalized_recovery_read = None

        if isinstance(
            proposed_forced_response_read,
            str,
        ):
            normalized_recovery_read = (
                proposed_forced_response_read
                .strip()
                .lower()
                .replace("-", "_")
                .replace(" ", "_")
            )

        normalized_intent_reason = None

        raw_intent_reason = (
            intent_explanation
            if isinstance(
                intent_explanation,
                str,
            )
            else proposal_reason
        )

        if isinstance(
            raw_intent_reason,
            str,
        ):
            normalized_intent_reason = (
                raw_intent_reason.strip()
            )

            if normalized_intent_reason:
                normalized_intent_reason = (
                    normalized_intent_reason[:200]
                )
            else:
                normalized_intent_reason = None

        normalized_reaction_reason = None

        if isinstance(
            reaction_explanation,
            str,
        ):
            normalized_reaction_reason = (
                reaction_explanation.strip()
            )

            if normalized_reaction_reason:
                normalized_reaction_reason = (
                    normalized_reaction_reason[:200]
                )
            else:
                normalized_reaction_reason = None

        selected_intent = (
            fallback_intent
        )

        intent_accepted = False
        intent_fallback_used = True

        if selection_key != current_key:
            intent_reason = (
                "stale_selection_key"
            )
        elif not observation[
            "selection_required"
        ]:
            intent_reason = (
                observation.get(
                    "locked_reason"
                )
                or "selection_already_locked"
            )
        elif normalized_intent in legal_intents:
            selected_intent = (
                normalized_intent
            )
            intent_accepted = True
            intent_fallback_used = False
            intent_reason = "accepted"
        elif normalized_intent is None:
            intent_reason = (
                parser_reason
                or "missing_proposal"
            )
        else:
            intent_reason = (
                "illegal_intent"
            )

        legal_reactions = tuple(
            self
            ._king_fight_reaction_plan_catalog(
                observation["stage"],
                selected_intent,
            )
        )

        fallback_reaction = (
            self
            ._king_fight_default_reaction_plan(
                observation["stage"],
                selected_intent,
            )
        )

        selected_reaction = (
            fallback_reaction
        )

        reaction_accepted = False
        reaction_fallback_used = True

        if not intent_accepted:
            reaction_reason = (
                "intent_fallback_requires_"
                "reaction_fallback"
            )
        elif normalized_reaction in legal_reactions:
            selected_reaction = (
                normalized_reaction
            )
            reaction_accepted = True
            reaction_fallback_used = False
            reaction_reason = "accepted"
        elif normalized_reaction is None:
            reaction_reason = (
                reaction_parser_reason
                or "missing_reaction_plan"
            )
        else:
            reaction_reason = (
                "illegal_reaction_plan"
            )

        recovery_read_packet = (
            self._social.lock_combat_recovery_read(
                selection_key=current_key,
                proposed_move=(
                    normalized_recovery_read
                ),
                fallback_move=observation.get(
                    "fallback_forced_response_read",
                    "dodge",
                ),
            )
        )

        fight["intent"] = (
            selected_intent
        )

        fight[
            "llm_opponent_reaction_plan"
        ] = selected_reaction

        fight[
            "llm_opponent_reaction_selection_key"
        ] = current_key

        audit = {
            "selection_key": current_key,
            "stage": observation["stage"],
            "enemy_actor": observation[
                "enemy_actor"
            ],
            "proposed_intent": (
                normalized_intent
            ),
            "proposed_intent_label": (
                intent_labels.get(
                    normalized_intent,
                    normalized_intent,
                )
            ),
            "selected_intent": (
                selected_intent
            ),
            "selected_intent_label": (
                intent_labels.get(
                    selected_intent,
                    selected_intent,
                )
            ),
            "fallback_intent": (
                fallback_intent
            ),
            "fallback_intent_label": (
                intent_labels.get(
                    fallback_intent,
                    fallback_intent,
                )
            ),
            "proposed_reaction_plan": (
                normalized_reaction
            ),
            "proposed_reaction_plan_label": (
                reaction_labels.get(
                    normalized_reaction,
                    normalized_reaction,
                )
            ),
            "selected_reaction_plan": (
                selected_reaction
            ),
            "selected_reaction_plan_label": (
                reaction_labels.get(
                    selected_reaction,
                    selected_reaction,
                )
            ),
            "fallback_reaction_plan": (
                fallback_reaction
            ),
            "fallback_reaction_plan_label": (
                reaction_labels.get(
                    fallback_reaction,
                    fallback_reaction,
                )
            ),
            "proposed_forced_response_read": (
                normalized_recovery_read
            ),
            "forced_response_read": (
                deepcopy(recovery_read_packet)
            ),
            "forced_response_read_accepted": (
                recovery_read_packet["accepted"]
            ),
            "forced_response_read_fallback_used": (
                recovery_read_packet["fallback_used"]
            ),
            "forced_response_read_reason": (
                recovery_read_packet["reason"]
            ),
            "legal_forced_response_reads": (
                list(
                    observation.get(
                        "legal_forced_response_reads",
                        ("light", "dodge"),
                    )
                )
            ),
            "legal_intents": list(
                legal_intents
            ),
            "legal_reaction_plans": list(
                legal_reactions
            ),
            "accepted": (
                intent_accepted
            ),
            "fallback_used": (
                intent_fallback_used
            ),
            "reason": intent_reason,
            "reaction_plan_accepted": (
                reaction_accepted
            ),
            "reaction_plan_fallback_used": (
                reaction_fallback_used
            ),
            "reaction_plan_reason": (
                reaction_reason
            ),
            "parser_reason": (
                parser_reason
            ),
            "reaction_parser_reason": (
                reaction_parser_reason
            ),
            "intent_reason": (
                normalized_intent_reason
            ),
            "reaction_reason": (
                normalized_reaction_reason
            ),
            "proposal_reason": (
                normalized_intent_reason
            ),
            "proposal_reason_authoritative": (
                False
            ),
            "provider_called": bool(
                provider_called
            ),
            "previous_exchange_evidence": (
                deepcopy(
                    observation.get(
                        "previous_exchange_evidence"
                    )
                )
            ),
            "state_owner": "Ghost",
            "llm_role": (
                "opponent_commitment_proposal_only"
            ),
            "selection_locked": True,
            "reaction_hidden_until_resolution": (
                True
            ),
        }

        fight["llm_opponent_audit"] = (
            deepcopy(audit)
        )

        history = fight.setdefault(
            "llm_opponent_history",
            [],
        )

        if not isinstance(history, list):
            history = []
            fight["llm_opponent_history"] = (
                history
            )

        history.append(
            deepcopy(audit)
        )

        del history[:-12]

        return deepcopy(audit)

    def _king_intent(self, exchange_count: int) -> str:
        return (
            "royal_lunge",
            "crown_guard",
            "overextended_recovery",
        )[exchange_count % 3]

    def _elite_knight_intent(self, exchange_count: int) -> str:
        return (
            "shield_wall",
            "champion_lunge",
            "wide_execution",
            "open_recovery",
        )[exchange_count % 4]

    def _king_intent_tell(self, intent: str) -> str:
        return {
            "royal_lunge": (
                "The king lowers his crown-guard and drives his "
                "blade toward your center line."
            ),
            "crown_guard": (
                "The king hides behind a perfect royal guard, waiting "
                "for you to strike directly into it."
            ),
            "overextended_recovery": (
                "The king's last cut carries too far. His crown-side "
                "shoulder is open for one breath."
            ),
        }[intent]

    def _elite_knight_tell(self, intent: str) -> str:
        return {
            "shield_wall": (
                "The King's Champion sets his shield like a wall. "
                "A direct cut will die on the steel."
            ),
            "champion_lunge": (
                "The Champion crouches low, ready to launch through "
                "the burning hall."
            ),
            "wide_execution": (
                "The Champion's blade circles wide, gathering speed "
                "for an execution cut."
            ),
            "open_recovery": (
                "The Champion drags one foot through ash and is late "
                "recovering his guard."
            ),
        }[intent]

    def king_fight_status(self) -> dict | None:
        if self.king_fight is None:
            return None

        status = self._snapshot_copy(
            self.king_fight,
            "king fight status",
        )

        stage = status["stage"]
        status["forced_response"] = (
            self._public_forced_response(
                status.get("forced_response")
            )
        )

        if stage in ("king_phase_one", "king_phase_two"):
            status["tell"] = self._king_intent_tell(
                status["intent"]
            )
        elif stage == "elite_knight":
            status["tell"] = self._elite_knight_tell(
                status["intent"]
            )
        elif stage == "fate_choice":
            status["tell"] = (
                "The king is beaten. Choose execute_king or jail_king."
            )
        elif stage == "crown_loop":
            status["tell"] = (
                "The crown is yours. Visit the towns, then retire it."
            )

        return status

    def siege_castle(self) -> dict:
        """
        Begin the final rebellion outcome.

        A weak army fails before reaching the king. A sufficient army
        starts a timed burning-castle confrontation where player skill
        decides the ending.
        """
        if self.king_fight is not None and not self.ending:
            return self._deny(
                "The castle endgame is already underway."
            )

        warning = self.calculate_rebellion_strength()
        score = warning["strength"]

        self.siege_armed = False

        if not warning["reaches_king"]:
            executed = self.followers
            self.alive = False
            self.captured = True
            self.king_fight = None

            if executed <= 0:
                ending = (
                    "The siege fails before you ever reach the king. "
                    "You are publicly executed for conspiracy against "
                    "the crown."
                )
            else:
                ending = (
                    "The siege fails before you ever reach the king. "
                    "You and the rebels who followed you are publicly "
                    "executed for conspiracy against the crown."
                )

            return self._set_final_ending(
                outcome="failed_siege_before_king",
                ending=ending,
                ending_type="failure",
                king_status="enthroned",
                rebellion_status="destroyed",
                extra={
                    "score": score,
                    "followers_executed": executed,
                },
            )

        wounded = warning["wounded_start"]
        prepared = warning["prepared_assault"]
        player_max_health = 10
        player_health = 5 if wounded else 10
        # Duel damage is fixed by the combat contract. A prepared army
        # still determines the clean/full-health start, but never multiplies
        # player attack damage inside the skill fight.
        damage_bonus = 0
        intent = self._king_intent(0)

        self.location = "castle"
        self.phase = "endgame"
        self.actions = 0
        self.king_fight = {
            "stage": "king_phase_one",
            # Lower fixed player damage needs a longer strategic horizon.
            # Twenty turns preserves collapse pressure while giving the
            # opponent enough exchanges to observe, predict, and adapt.
            "castle_timer": 20,
            "score": score,
            "minimum_required": warning["minimum_required"],
            "strong_threshold": warning["strong_threshold"],
            "wounded_start": wounded,
            "prepared_assault": prepared,
            "armor_broken": wounded,
            "damage_bonus_percent": damage_bonus,
            "player_health": player_health,
            "player_max_health": player_max_health,
            "king_health": 20,
            "king_max_health": 20,
            "king_half_health": 10,
            "king_has_hit_player": False,
            "clean_king_victory_possible": True,
            "elite_knight_health": 14,
            "elite_knight_max_health": 14,
            "king_morale_ticks": 0,
            "failed_knight_reads": 0,
            "exchange_count": 0,
            "intent": intent,
            "last_exchange": None,
            "initiative": (
                self._social.advance_combat_initiative(
                    previous_state="neutral",
                    event="fight_started",
                )
            ),
        }

        if wounded:
            self.last_action_note = (
                "Your army breaches the castle, but barely. You reach "
                "the burning throne hall wounded, armor broken, and "
                "already breathing blood."
            )
        else:
            self.last_action_note = (
                "Your army breaches the castle cleanly. They need "
                "nothing from you now but words of courage, and you "
                "turn toward the king with their voices behind you."
            )

        return {
            "outcome": "king_confrontation_started",
            "score": score,
            "wounded_start": wounded,
            "prepared_assault": prepared,
            "player_health": player_health,
            "player_max_health": player_max_health,
            "damage_bonus_percent": damage_bonus,
            "castle_timer": self.king_fight["castle_timer"],
            "stage": self.king_fight["stage"],
            "tell": self._king_intent_tell(intent),
        }

    def _advance_castle_timer(self) -> dict | None:
        fight = self.king_fight

        if fight is None or self.ending:
            return None

        fight["castle_timer"] = max(
            0,
            fight["castle_timer"] - 1,
        )

        if fight["castle_timer"] > 0:
            return None

        self.alive = True
        self.captured = False
        fight["stage"] = "castle_collapse_legend"

        return self._set_final_ending(
            outcome="castle_collapse_legend",
            ending=(
                "The castle gives out before anyone can claim the "
                "final blow. The king and his champion disappear in "
                "the burning collapse. The towns rebuild from the ash, "
                "and in the square they raise a statue in your honor "
                "for breaking the crown's tyranny."
            ),
            ending_type="legend",
            king_status="dead_in_collapse",
            rebellion_status="liberated",
            extra={
                "castle_timer": fight["castle_timer"],
            },
        )


    def _finish_player_death(
        self,
        *,
        killer: str,
    ) -> dict:
        self.alive = False
        self.captured = False

        fight = self.king_fight or {}

        if killer == "elite_knight":
            if isinstance(fight, dict):
                fight["stage"] = (
                    "player_killed_by_champion"
                )

            return self._set_final_ending(
                outcome=(
                    "player_killed_by_champion"
                ),
                ending=(
                    "The King's Champion catches you "
                    "in the smoke and drives you to the "
                    "stone. The king steps through the "
                    "fire to claim the victory as the "
                    "rebellion dies around him."
                ),
                ending_type="failure",
                king_status="mocking_victor",
                rebellion_status="broken",
                extra={
                    "king_mocking_lines": [
                        (
                            "You mistook rebellion "
                            "for destiny."
                        ),
                        (
                            "Even your death needed "
                            "my knight's hand."
                        ),
                    ],
                },
            )

        if isinstance(fight, dict):
            fight["stage"] = (
                "player_killed_by_king"
            )

        return self._set_final_ending(
            outcome="player_killed_by_king",
            ending=(
                "The king's blade finds the final "
                "opening. The castle burns around your "
                "failed rebellion, and the crown uses "
                "your death as its last warning to the "
                "towns."
            ),
            ending_type="failure",
            king_status="victorious",
            rebellion_status="broken",
            extra={
                "king_mocking_lines": [
                    (
                        "All that fire, and you still "
                        "died at my feet."
                    ),
                    (
                        "Let the towns remember what "
                        "became of the knight who "
                        "challenged his king."
                    ),
                ],
            },
        )

    def _finish_uncertain_king_victory(self) -> dict:
        fight = self.king_fight

        if (
            isinstance(fight, dict)
            and fight.get("castle_timer") == 1
            and fight.get("king_health", 0) <= 0
        ):
            return self._finish_last_breath_king_victory()

        fight["stage"] = "uncertain_king_fall"

        self.alive = True
        self.captured = False
        self.king_control = 0

        return self._set_final_ending(
            outcome="uncertain_king_fall",
            ending=(
                "The king falls in the burning throne hall, but the "
                "castle tears itself apart before you can know whether "
                "he died by your hand or vanished into the ruin. You "
                "barely escape with the remaining rebels. The towns "
                "celebrate the crown's defeat, rebuild the castle, and "
                "remember you as the ruler you became afterward."
            ),
            ending_type="victory_uncertain",
            king_status="unknown",
            rebellion_status="victorious",
        )


    def _finish_last_breath_king_victory(self) -> dict:
        fight = self.king_fight or {}

        if isinstance(fight, dict):
            fight["stage"] = "last_breath_king_victory"
            fight["king_health"] = 0

        self.alive = True
        self.captured = False
        self.king_control = 0

        ending = (
            "Last-Breath Victory: your final strike kills the king "
            "as the castle breaks apart. The old crown dies by your "
            "hand, and the towns remember that the last blow was yours."
        )

        return self._set_final_ending(
            outcome="last_breath_king_victory",
            ending=ending,
            ending_type="legend",
            king_status="slain_by_player",
            rebellion_status="liberated",
            extra={
                "stage": (
                    fight.get("stage")
                    if isinstance(fight, dict)
                    else "last_breath_king_victory"
                ),
                "castle_timer": (
                    fight.get("castle_timer")
                    if isinstance(fight, dict)
                    else None
                ),
                "player_health": (
                    fight.get("player_health")
                    if isinstance(fight, dict)
                    else None
                ),
                "king_health": 0,
                "clean_king_victory_possible": (
                    fight.get("clean_king_victory_possible")
                    if isinstance(fight, dict)
                    else None
                ),
            },
        )

    def _enter_king_fate_choice(self) -> dict:
        fight = self.king_fight

        if (
            isinstance(fight, dict)
            and fight.get("castle_timer") == 1
            and fight.get("king_health", 0) <= 0
        ):
            return self._finish_last_breath_king_victory()

        fight["stage"] = "fate_choice"
        fight["king_health"] = 0
        fight["intent"] = ""
        self.king_control = 0

        self.last_action_note = (
            "The king drops to one knee with the castle burning around "
            "you. Because his blade never found you, his fate is yours: "
            "execute_king or jail_king."
        )

        return {
            "outcome": "clean_king_victory",
            "stage": "fate_choice",
            "choices": (
                "execute_king",
                "jail_king",
            ),
            "ending": "",
            "clean_king_victory_possible": True,
            "player_health": fight["player_health"],
            "castle_timer": fight["castle_timer"],
        }

    def _transition_to_elite_knight(self) -> dict:
        fight = self.king_fight

        previous_exchange = deepcopy(
            fight.get("last_exchange")
        )

        king_health_after_final_attack = (
            fight["king_health"]
        )

        transition_trigger = None

        if (
            isinstance(previous_exchange, dict)
            and previous_exchange.get("stage")
            == "king_phase_one"
            and previous_exchange.get("move")
        ):
            king_damage = int(
                previous_exchange.get(
                    "king_damage",
                    0,
                )
                or 0
            )

            player_damage = int(
                previous_exchange.get(
                    "player_damage",
                    0,
                )
                or 0
            )

            last_attack_landed = (
                king_damage > 0
            )

            if last_attack_landed:
                reaction_truth = (
                    "The player's final phase-one "
                    "attack lands on the king. The "
                    "king physically recoils from that "
                    "resolved blow, regains command, "
                    "and summons the King's Champion."
                )
            else:
                reaction_truth = (
                    "The final phase-one exchange "
                    "forces the king to yield ground. "
                    "He regains command and summons "
                    "the King's Champion without "
                    "inventing a new wound."
                )

            transition_trigger = {
                "source_stage": "king_phase_one",
                "destination_stage": (
                    "elite_knight"
                ),
                "player_move": (
                    previous_exchange.get("move")
                ),
                "king_intent": (
                    previous_exchange.get("intent")
                ),
                "result": (
                    previous_exchange.get("result")
                ),
                "last_attack_message": (
                    previous_exchange.get("message")
                ),
                "king_damage": king_damage,
                "player_damage": player_damage,
                "damage_target": (
                    "king"
                    if last_attack_landed
                    else None
                ),
                "king_health_after_final_attack": (
                    king_health_after_final_attack
                ),
                "king_half_health": (
                    fight["king_half_health"]
                ),
                "last_attack_landed": (
                    last_attack_landed
                ),
                "reaction_owner": "king",
                "reaction_truth": reaction_truth,
                "summoner": "king",
                "summoned_actor": (
                    "the King's Champion"
                ),
                "required_sequence": [
                    "final_phase_one_exchange",
                    "king_reacts_to_final_exchange",
                    "king_summons_champion",
                    "champion_enters",
                ],
            }

        fight["stage"] = "elite_knight"
        fight["parry_opening"] = None
        fight["forced_response"] = None

        fight["king_health"] = max(
            fight["king_half_health"],
            fight["king_health"],
        )

        fight["exchange_count"] = 0
        fight["intent"] = (
            self._elite_knight_intent(0)
        )
        fight["initiative"] = (
            self._social.advance_combat_initiative(
                previous_state=(
                    self._ensure_king_fight_initiative()[
                        "state"
                    ]
                ),
                event="stage_transition",
            )
        )

        fight["last_exchange"] = {
            "result": "elite_knight_called",
            "message": (
                "The king staggers back at half "
                "strength. He smiles through the "
                "smoke and calls for the one knight "
                "who never abandoned him: the "
                "King's Champion."
            ),
        }

        self.last_action_note = (
            fight["last_exchange"]["message"]
            + " "
            + self._elite_knight_tell(
                fight["intent"]
            )
        )

        packet = {
            "outcome": "elite_knight_called",
            "stage": "elite_knight",
            "king_health": fight["king_health"],
            "elite_knight_health": (
                fight["elite_knight_health"]
            ),
            "castle_timer": fight["castle_timer"],
            "tell": self._elite_knight_tell(
                fight["intent"]
            ),
        }

        if transition_trigger is not None:
            packet["transition_trigger"] = (
                transition_trigger
            )

        return packet

    def _ensure_king_fight_pattern_state(self) -> dict:
        fight = self.king_fight

        if fight is None:
            return {}

        patterns = fight.setdefault(
            "player_patterns",
            {
                "heavy_count": 0,
                "light_count": 0,
                "parry_count": 0,
                "deflect_count": 0,
                "dodge_count": 0,
                "last_moves": [],
            },
        )

        patterns.setdefault("heavy_count", 0)
        patterns.setdefault("light_count", 0)
        patterns.setdefault("parry_count", 0)
        patterns.setdefault("deflect_count", 0)
        patterns.setdefault("dodge_count", 0)
        patterns.setdefault("last_moves", [])

        if not isinstance(patterns["last_moves"], list):
            patterns["last_moves"] = []

        fight.setdefault("forced_response", None)

        return patterns

    def _record_king_fight_player_move(self, move: str) -> None:
        patterns = self._ensure_king_fight_pattern_state()
        key = move + "_count"

        if key in patterns:
            patterns[key] += 1

        patterns["last_moves"].append(move)
        patterns["last_moves"] = patterns["last_moves"][-6:]

    def _king_pattern_bonus_for_move(self, move: str) -> int:
        patterns = self._ensure_king_fight_pattern_state()
        last_moves = list(patterns.get("last_moves", []))

        bonus = 0

        if last_moves and last_moves[-1] == move:
            bonus += 10

        if last_moves[-3:].count(move) >= 2:
            bonus += 10

        heavy_count = int(patterns.get("heavy_count", 0))
        light_count = int(patterns.get("light_count", 0))

        if move == "heavy" and heavy_count > light_count:
            bonus += min(20, (heavy_count - light_count) * 5)

        if move == "light" and light_count > heavy_count:
            bonus += min(15, (light_count - heavy_count) * 5)

        if last_moves[-4:] in (
            ["heavy", "heavy", "light", "heavy"],
            ["heavy", "light", "heavy", "heavy"],
            ["light", "light", "heavy", "light"],
            ["light", "heavy", "light", "light"],
        ):
            bonus += 10

        return bonus


    def _king_fight_reaction_plan_catalog(
        self,
        stage: str,
        intent: str,
    ) -> tuple[str, ...]:
        """
        Return reactions that are mechanically legal for an intent.

        A policy may choose from this list, but Ghost alone resolves
        whether the reaction matches the player's later move.
        """
        by_intent = {
            "crown_guard": (
                "hold_center",
                "read_feint",
            ),
            "shield_wall": (
                "hold_center",
                "read_feint",
            ),
            "overextended_recovery": (
                "genuine_opening",
                "parry_heavy",
                "deflect_light",
                "dodge_heavy",
            ),
            "open_recovery": (
                "genuine_opening",
                "parry_heavy",
                "deflect_light",
                "dodge_heavy",
            ),
            "royal_lunge": (
                "commit_attack",
                "break_parry",
                "beat_deflect",
                "track_dodge",
            ),
            "champion_lunge": (
                "commit_attack",
                "break_parry",
                "beat_deflect",
                "track_dodge",
            ),
            "wide_execution": (
                "commit_attack",
                "break_parry",
                "beat_deflect",
                "track_dodge",
            ),
        }

        return tuple(
            by_intent.get(
                intent,
                ("commit_attack",),
            )
        )

    def _king_fight_reaction_plan_labels(
        self,
    ) -> dict:
        return {
            "hold_center": "Hold Center",
            "read_feint": "Read Feint",
            "genuine_opening": (
                "Genuine Opening"
            ),
            "parry_heavy": "Parry Heavy",
            "deflect_light": (
                "Deflect Light"
            ),
            "dodge_heavy": "Dodge Heavy",
            "commit_attack": (
                "Commit Attack"
            ),
            "break_parry": "Break Parry",
            "beat_deflect": (
                "Beat Deflect"
            ),
            "track_dodge": "Track Dodge",
        }

    def _king_fight_default_reaction_plan(
        self,
        stage: str,
        intent: str,
    ) -> str:
        legal = (
            self
            ._king_fight_reaction_plan_catalog(
                stage,
                intent,
            )
        )

        return legal[0]

    def _consume_king_fight_opponent_reaction_plan(
        self,
        intent: str,
    ) -> str | None:
        """
        Consume the reaction locked before the player's move.

        A stale plan cannot cross an exchange or stage boundary.
        """
        fight = self.king_fight

        if fight is None:
            return None

        stage = str(
            fight.get(
                "stage",
                "",
            )
        )

        exchange_count = int(
            fight.get(
                "exchange_count",
                0,
            )
        )

        current_key = (
            f"{stage}:{exchange_count}"
        )

        stored_key = fight.pop(
            "llm_opponent_reaction_selection_key",
            None,
        )

        reaction_plan = fight.pop(
            "llm_opponent_reaction_plan",
            None,
        )

        if stored_key != current_key:
            return None

        legal = (
            self
            ._king_fight_reaction_plan_catalog(
                stage,
                intent,
            )
        )

        if reaction_plan not in legal:
            return (
                self
                ._king_fight_default_reaction_plan(
                    stage,
                    intent,
                )
            )

        return reaction_plan


    def _king_fight_reaction_prediction_status(
        self,
        reaction_plan: str | None,
        move: str,
    ) -> dict:
        """
        Compare a locked prediction with the later player move.

        Non-predictive plans return None for matched and missed.
        """
        predicted_moves = {
            "read_feint": (
                "feint_heavy",
                "feint_light",
            ),
            "parry_heavy": (
                "heavy",
            ),
            "deflect_light": (
                "light",
            ),
            "dodge_heavy": (
                "heavy",
            ),
            "break_parry": (
                "parry",
            ),
            "beat_deflect": (
                "deflect",
            ),
            "track_dodge": (
                "dodge",
            ),
        }.get(
            reaction_plan
        )

        if predicted_moves is None:
            return {
                "predictive": False,
                "matched": None,
                "missed": None,
                "predicted_moves": [],
            }

        matched = move in predicted_moves

        return {
            "predictive": True,
            "matched": matched,
            "missed": not matched,
            "predicted_moves": list(
                predicted_moves
            ),
        }


    def _king_fight_reaction_miss_bonus(
        self,
        reaction_plan: str | None,
        move: str,
    ) -> int:
        """
        Prediction misses change initiative instead of multiplying damage.

        Damage remains governed only by the explicit game-layer damage
        table. Ghost records the miss and moves tempo; it never invents an
        extra damage tick.
        """
        return 0

    def _precommitted_opponent_reaction(
        self,
        enemy_actor: str,
        move: str,
        intent: str,
        reaction_plan: str | None,
    ) -> dict | None:
        """
        Resolve a previously locked prediction against the player move.

        This method receives the move only after commitment. It cannot
        choose or change the reaction plan.
        """
        if reaction_plan is None:
            return None

        labels = (
            self
            ._king_fight_reaction_plan_labels()
        )

        specs = {
            "read_feint": {
                "moves": (
                    "feint_heavy",
                    "feint_light",
                ),
                "result": "reads_feint",
                "player_damage_mode": (
                    "none"
                ),
                "opens_forced_response": (
                    True
                ),
            },
            "parry_heavy": {
                "moves": (
                    "heavy",
                ),
                "result": "parry",
                "player_damage_mode": (
                    "none"
                ),
                "opens_forced_response": (
                    True
                ),
            },
            "deflect_light": {
                "moves": (
                    "light",
                ),
                "result": "deflect",
                "player_damage_mode": (
                    "none"
                ),
                "opens_forced_response": (
                    True
                ),
            },
            "dodge_heavy": {
                "moves": (
                    "heavy",
                ),
                "result": "dodge",
                "player_damage_mode": (
                    "none"
                ),
                "opens_forced_response": (
                    False
                ),
            },
            "break_parry": {
                "moves": (
                    "parry",
                ),
                "result": "breaks_parry",
                "player_damage_mode": (
                    "incoming"
                ),
                "opens_forced_response": (
                    False
                ),
            },
            "beat_deflect": {
                "moves": (
                    "deflect",
                ),
                "result": "beats_deflect",
                "player_damage_mode": (
                    "incoming"
                ),
                "opens_forced_response": (
                    False
                ),
            },
            "track_dodge": {
                "moves": (
                    "dodge",
                ),
                "result": "tracks_dodge",
                "player_damage_mode": (
                    "incoming"
                ),
                "opens_forced_response": (
                    False
                ),
            },
        }

        spec = specs.get(
            reaction_plan
        )

        if spec is None:
            return None

        if move not in spec["moves"]:
            return None

        if enemy_actor == "elite_knight":
            actor_name = (
                "The King's Champion"
            )
            result_prefix = "champion"
        else:
            actor_name = "The king"
            result_prefix = "king"

        messages = {
            "read_feint": (
                actor_name
                + " watches the second movement "
                "instead of the first. He refuses "
                "the feint and keeps the real "
                "follow-up outside his guard."
            ),
            "parry_heavy": (
                actor_name
                + " committed to the weight of your "
                "heavy attack before you moved. He "
                "catches the line and turns your "
                "blade aside."
            ),
            "deflect_light": (
                actor_name
                + " anticipated the speed of your "
                "light attack. He meets it early and "
                "deflects the cut before it settles."
            ),
            "dodge_heavy": (
                actor_name
                + " abandons the line before your "
                "heavy attack arrives. Your blade "
                "cuts through the space he left."
            ),
            "break_parry": (
                actor_name
                + " shortens the attack before your "
                "parry closes, slips around the bind, "
                "and drives the threat through."
            ),
            "beat_deflect": (
                actor_name
                + " changes the angle as your "
                "deflection starts, beating your "
                "blade aside and staying on target."
            ),
            "track_dodge": (
                actor_name
                + " reads the escape step before you "
                "take it. He tracks the dodge and "
                "keeps the attack aligned."
            ),
        }

        return {
            "type": (
                result_prefix
                + "_"
                + spec["result"]
            ),
            "triggering_move": move,
            "intent": intent,
            "reaction_plan": (
                reaction_plan
            ),
            "reaction_plan_label": (
                labels.get(
                    reaction_plan,
                    reaction_plan,
                )
            ),
            "precommitted": True,
            "player_damage_mode": (
                spec[
                    "player_damage_mode"
                ]
            ),
            "opens_forced_response": bool(
                spec[
                    "opens_forced_response"
                ]
                and enemy_actor == "king"
            ),
            "message": messages[
                reaction_plan
            ],
        }


    def _king_defense_reaction(
        self,
        move: str,
        intent: str,
        reaction_plan: str | None = None,
    ) -> dict | None:
        fight = self.king_fight or {}

        precommitted = (
            self
            ._precommitted_opponent_reaction(
                "king",
                move,
                intent,
                reaction_plan,
            )
        )

        if precommitted is not None:
            return precommitted

        # A locked plan that guessed incorrectly cannot receive another
        # random defense after seeing the player's committed move.
        if reaction_plan is not None:
            return None

        adaptive_enabled = bool(
            fight.get(
                "adaptive_defense_enabled"
            )
        )

        if not adaptive_enabled:
            return None

        if move == "heavy":
            defense_type = "king_parry"
            base_chance = 40
        elif move == "light":
            defense_type = (
                "king_deflect"
            )
            base_chance = 10
        else:
            return None

        pattern_bonus = (
            self
            ._king_pattern_bonus_for_move(
                move
            )
        )

        phase_bonus = (
            10
            if fight.get("stage")
            == "king_phase_two"
            else 0
        )

        chance = min(
            85,
            (
                base_chance
                + pattern_bonus
                + phase_bonus
            ),
        )

        roll = self.rng.randint(
            1,
            100,
        )

        if roll > chance:
            return None

        if defense_type == "king_parry":
            message = (
                "The king reads the weight of your heavy attack. "
                "He catches the line, turns your blade aside, and "
                "breaks your footing before you can recover."
            )
        else:
            message = (
                "The king reads the speed of your light attack. "
                "He deflects the cut instead of chasing it, and "
                "your lead foot slips across the ash."
            )

        return {
            "type": defense_type,
            "triggering_move": move,
            "intent": intent,
            "base_chance": base_chance,
            "pattern_bonus": (
                pattern_bonus
            ),
            "phase_bonus": phase_bonus,
            "chance": chance,
            "roll": roll,
            "precommitted": False,
            "opens_forced_response": (
                True
            ),
            "player_damage_mode": (
                "none"
            ),
            "message": message,
        }

    def _king_forced_fallback_read(self) -> str:
        patterns = self._ensure_king_fight_pattern_state()

        return (
            "light"
            if int(patterns.get("light_count", 0))
            > int(patterns.get("dodge_count", 0))
            else "dodge"
        )

    def _build_king_forced_response(
        self,
        defense: dict,
        next_intent: str,
        recovery_read: dict | None = None,
    ) -> dict:
        fight = self.king_fight or {}

        if not isinstance(recovery_read, dict):
            recovery_read = (
                self._social.lock_combat_recovery_read(
                    selection_key=(
                        f"{fight.get('stage', '')}:"
                        f"{max(0, int(fight.get('exchange_count', 0)) - 1)}"
                    ),
                    proposed_move=None,
                    fallback_move=(
                        self._king_forced_fallback_read()
                    ),
                )
            )

        return {
            "reason": defense["type"],
            "source_move": defense["triggering_move"],
            "allowed_moves": ("dodge", "light"),
            "next_intent": next_intent,
            "message": defense["message"],
            "recovery_read": deepcopy(recovery_read),
            "random_used": False,
        }


    def _resolve_king_forced_response(self, move: str) -> dict:
        fight = self.king_fight
        forced = fight.get("forced_response")

        if not isinstance(forced, dict):
            fight["forced_response"] = None
            return self._resolve_king_phase_move(move)

        allowed_moves = tuple(forced.get("allowed_moves", ()))

        if move not in allowed_moves:
            allowed_text = " or ".join(allowed_moves)
            message = (
                "You are off balance. Choose "
                + allowed_text
                + "."
            )
            self.last_action_note = message

            return {
                "outcome": "forced_response_denied",
                "stage": fight["stage"],
                "message": message,
                "player_health": fight["player_health"],
                "king_health": fight["king_health"],
                "castle_timer": fight["castle_timer"],
                "forced_response": self._public_forced_response(forced),
                "tell": self._king_intent_tell(
                    forced.get("next_intent", fight["intent"])
                ),
            }

        read_packet = forced.get("recovery_read")

        if not isinstance(read_packet, dict):
            read_packet = self._social.lock_combat_recovery_read(
                selection_key=(
                    f"{fight.get('stage', '')}:"
                    f"{max(0, int(fight.get('exchange_count', 0)) - 1)}"
                ),
                proposed_move=None,
                fallback_move=self._king_forced_fallback_read(),
            )

        resolution = self._social.resolve_combat_recovery(
            read_packet=read_packet,
            player_move=move,
            light_damage=int(
                KING_FIGHT_PLAYER_DAMAGE[
                    "forced_recovery"
                ]["light"]
            ),
        )

        intent = forced.get("next_intent", fight["intent"])
        king_damage = int(resolution["damage_to_opponent"])
        player_damage = int(resolution["damage_to_player"])
        result = str(resolution["result"])

        if result == "forced_recovery_denied":
            message = (
                "The king reads the only recovery you choose and closes "
                "the lane before it can become an attack or escape. "
                "Neither blade lands, but he keeps the initiative."
            )
        elif result == "forced_light_landed":
            message = (
                "The king commits to stopping your dodge. Your desperate "
                "light cut takes the unguarded line for one damage and "
                "steals back the initiative."
            )
        else:
            message = (
                "The king commits to smothering your light recovery. Your "
                "dodge clears the follow-up and resets the duel without "
                "either fighter taking damage."
            )

        fight["forced_response"] = None
        fight["king_health"] = max(
            0,
            fight["king_health"] - king_damage,
        )
        fight["player_health"] = max(
            0,
            fight["player_health"] - player_damage,
        )
        fight["exchange_count"] += 1
        self._record_king_fight_player_move(move)

        initiative_before = self._ensure_king_fight_initiative()
        initiative_after = self._advance_king_fight_initiative(
            resolution["initiative_event"]
        )

        fight["last_exchange"] = {
            "stage": fight["stage"],
            "intent": intent,
            "move": move,
            "expected": resolution["predicted_move"],
            "valid_responses": list(allowed_moves),
            "forced_response": deepcopy(forced),
            "source_opponent_commitment": deepcopy(
                forced.get("source_commitment")
            ),
            "opponent_reaction_plan": "forced_recovery_read",
            "opponent_reaction_plan_label": "Forced Recovery Read",
            "forced_response_read": resolution["predicted_move"],
            "forced_response_read_matched": resolution["matched"],
            "reaction_plan_predictive": True,
            "reaction_plan_matched": resolution["matched"],
            "reaction_plan_triggered": resolution["matched"],
            "reaction_plan_missed": not resolution["matched"],
            "reaction_miss_exposed_enemy": (
                result == "forced_light_landed"
            ),
            "reaction_miss_bonus": 0,
            "resolution_source": "forced_response_read",
            "opponent_control_source": "ghost_forced_continuation",
            "opponent_intent_reason": (
                "Ghost continued the already-resolved exchange while the "
                "player recovered from broken footing."
            ),
            "opponent_reaction_reason": (
                "The LLM's hidden light-or-dodge contingency was locked "
                "before the off-balance menu and Ghost resolved it without "
                "randomness."
            ),
            "opponent_proposal_reason": None,
            "initiative_before": initiative_before,
            "initiative_after": initiative_after,
            "initiative_event": resolution["initiative_event"],
            "result": result,
            "king_damage": king_damage,
            "player_damage": player_damage,
            "message": message,
        }

        next_intent = self._king_intent(fight["exchange_count"])
        fight["intent"] = next_intent
        self.last_action_note = (
            message + " " + self._king_intent_tell(next_intent)
        )

        collapse = self._advance_castle_timer()
        if collapse is not None:
            return collapse

        return {
            "outcome": "king_forced_response",
            "stage": fight["stage"],
            "exchange": deepcopy(fight["last_exchange"]),
            "player_health": fight["player_health"],
            "king_health": fight["king_health"],
            "castle_timer": fight["castle_timer"],
            "clean_king_victory_possible": (
                fight["clean_king_victory_possible"]
            ),
            "tell": self._king_intent_tell(next_intent),
            "forced_response": None,
            "initiative": deepcopy(fight["initiative"]),
        }



    def _resolve_king_phase_move(self, move: str) -> dict:
        fight = self.king_fight
        self._ensure_king_fight_pattern_state()

        forced_response = fight.get("forced_response")

        if isinstance(forced_response, dict):
            return self._resolve_king_forced_response(move)

        intent = fight["intent"]

        reaction_plan = (
            self
            ._consume_king_fight_opponent_reaction_plan(
                intent
            )
        )

        active_audit = fight.get(
            "llm_opponent_audit"
        )

        opponent_intent_reason = None
        opponent_reaction_reason = None

        if (
            isinstance(
                active_audit,
                dict,
            )
            and active_audit.get(
                "selection_key"
            )
            == (
                f"{fight['stage']}:"
                f"{fight['exchange_count']}"
            )
        ):
            opponent_intent_reason = (
                active_audit.get(
                    "intent_reason"
                )
                or active_audit.get(
                    "proposal_reason"
                )
            )

            opponent_reaction_reason = (
                active_audit.get(
                    "reaction_reason"
                )
            )

        reaction_prediction = (
            self
            ._king_fight_reaction_prediction_status(
                reaction_plan,
                move,
            )
        )

        parry_opening = fight.get("parry_opening")

        if (
            isinstance(parry_opening, dict)
            and move in ("heavy", "light")
        ):
            source_commitment = parry_opening.get(
                "source_commitment"
            )

            if not isinstance(source_commitment, dict):
                source_commitment = {}

            intent = str(
                parry_opening.get("intent")
                or source_commitment.get("intent")
                or intent
            )
            king_damage = self._king_damage(
                int(
                    KING_FIGHT_PLAYER_DAMAGE[
                        "parry_opening"
                    ][move]
                )
            )
            player_damage = 0
            result = "parry_opening_hit"
            expected = move
            valid_responses = ("heavy", "light")

            message = (
                "You spend the opening your parry created. "
                f"Your {move} attack lands cleanly before the king "
                "can rebuild his guard."
            )

            fight["parry_opening"] = None
            fight["king_health"] = max(
                0,
                fight["king_health"] - king_damage,
            )
            fight["player_health"] = max(
                0,
                fight["player_health"] - player_damage,
            )
            fight["exchange_count"] += 1
            self._record_king_fight_player_move(move)

            initiative_before = (
                self._ensure_king_fight_initiative()
            )
            initiative_after = (
                self._advance_king_fight_initiative(
                    "player_attack_hit"
                )
            )

            fight["last_exchange"] = {
                "stage": fight["stage"],
                "intent": intent,
                "move": move,
                "expected": expected,
                "valid_responses": list(valid_responses),
                "parry_opening_used": deepcopy(
                    parry_opening
                ),
                "source_opponent_commitment": deepcopy(
                    source_commitment
                ),
                "opponent_reaction_plan": (
                    source_commitment.get(
                        "reaction_plan"
                    )
                ),
                "opponent_reaction_plan_label": (
                    source_commitment.get(
                        "reaction_plan_label"
                    )
                ),
                "reaction_plan_predictive": (
                    source_commitment.get(
                        "reaction_plan_predictive"
                    )
                ),
                "reaction_plan_matched": (
                    source_commitment.get(
                        "reaction_plan_matched"
                    )
                ),
                "reaction_plan_triggered": (
                    source_commitment.get(
                        "reaction_plan_triggered"
                    )
                ),
                "reaction_plan_missed": (
                    source_commitment.get(
                        "reaction_plan_missed"
                    )
                ),
                "reaction_miss_exposed_enemy": (
                    source_commitment.get(
                        "reaction_miss_exposed_enemy"
                    )
                ),
                "reaction_miss_bonus": (
                    source_commitment.get(
                        "reaction_miss_bonus",
                        0,
                    )
                ),
                "resolution_source": "parry_opening",
                "opponent_control_source": (
                    "ghost_parry_continuation"
                ),
                "opponent_intent_reason": (
                    source_commitment.get(
                        "intent_reason"
                    )
                ),
                "opponent_reaction_reason": (
                    source_commitment.get(
                        "reaction_reason"
                    )
                ),
                "opponent_proposal_reason": (
                    source_commitment.get(
                        "intent_reason"
                    )
                ),
                "initiative_before": initiative_before,
                "initiative_after": initiative_after,
                "initiative_event": "player_attack_hit",
                "result": result,
                "king_damage": king_damage,
                "player_damage": player_damage,
                "message": message,
            }

            if (
                fight["stage"] == "king_phase_one"
                and fight["king_health"] <= fight["king_half_health"]
            ):
                collapse = self._advance_castle_timer()
                if collapse is not None:
                    return collapse

                packet = self._transition_to_elite_knight()
                narrative = (
                    "For one breath the king looks almost mortal. He "
                    "staggers back into the smoke, one hand pressed to "
                    "the blood under his royal armor. Then his fear hardens "
                    "into command. He raises two fingers, and the burning "
                    "hall answers with iron: the King's Champion steps "
                    "between you and the throne."
                )

                if isinstance(packet, dict):
                    next_tell = packet.get("tell", "")

                    packet["narrative"] = narrative
                    packet["note"] = narrative

                    if next_tell:
                        packet["tell"] = narrative + "\n\n" + next_tell
                    else:
                        packet["tell"] = narrative

                    self.last_action_note = packet["tell"]

                return packet

            if (
                fight["stage"] == "king_phase_two"
                and fight["king_health"] <= 0
            ):
                if fight["clean_king_victory_possible"]:
                    return self._enter_king_fate_choice()

                return self._finish_uncertain_king_victory()

            next_intent = self._king_intent(fight["exchange_count"])
            fight["intent"] = next_intent

            self.last_action_note = (
                message
                + " "
                + self._king_intent_tell(fight["intent"])
            )

            collapse = self._advance_castle_timer()
            if collapse is not None:
                return collapse

            return {
                "outcome": "king_exchange",
                "stage": fight["stage"],
                "exchange": deepcopy(fight["last_exchange"]),
                "player_health": fight["player_health"],
                "king_health": fight["king_health"],
                "castle_timer": fight["castle_timer"],
                "clean_king_victory_possible": (
                    fight["clean_king_victory_possible"]
                ),
                "tell": self._king_intent_tell(fight["intent"]),
                "parry_opening": deepcopy(
                    fight.get("parry_opening")
                ),
                "forced_response": self._public_forced_response(
                    fight.get("forced_response")
                ),
                "initiative": deepcopy(
                    fight.get("initiative")
                ),
            }

        correct_moves = {
            "royal_lunge": (
                "parry",
                "deflect",
                "dodge",
            ),
            "crown_guard": (
                "feint_heavy",
                "feint_light",
            ),
            "overextended_recovery": (
                "heavy",
                "light",
            ),
        }
        base_damage = {
            "royal_lunge": {
                # Parry creates tempo/control.
                # It does not directly wound the king.
                "parry": 0,
                "deflect": int(
                    KING_FIGHT_PLAYER_DAMAGE[
                        "normal"
                    ]["deflect"]
                ),
                "dodge": 0,
            },
            "crown_guard": {
                "feint_heavy": int(
                    KING_FIGHT_PLAYER_DAMAGE[
                        "normal"
                    ]["feint_heavy"]
                ),
                "feint_light": int(
                    KING_FIGHT_PLAYER_DAMAGE[
                        "normal"
                    ]["feint_light"]
                ),
            },
            "overextended_recovery": {
                "heavy": int(
                    KING_FIGHT_PLAYER_DAMAGE[
                        "normal"
                    ]["heavy"]
                ),
                "light": int(
                    KING_FIGHT_PLAYER_DAMAGE[
                        "normal"
                    ]["light"]
                ),
            },
        }
        incoming_damage = {
            "royal_lunge": 3,
            "crown_guard": 2,
            "overextended_recovery": 2,
        }

        valid_responses = correct_moves[intent]
        expected = valid_responses[0]
        correct = move in valid_responses
        king_defense = None
        reaction_miss_bonus = 0

        if correct:
            raw_damage = base_damage[intent][move]

            if raw_damage > 0:
                reaction_miss_bonus = (
                    self
                    ._king_fight_reaction_miss_bonus(
                        reaction_plan,
                        move,
                    )
                )

                raw_damage += (
                    reaction_miss_bonus
                )

            king_damage = (
                self._king_damage(raw_damage)
                if raw_damage > 0
                else 0
            )

            player_damage = 0
            result = "correct_read"

            if move == "dodge":
                message = (
                    "You read the king correctly. The dodge clears "
                    "the blade and keeps you alive, but it does not "
                    "wound him."
                )
            elif move == "parry":
                message = (
                    "You read the king correctly. Your parry catches "
                    "the committed line and turns his force back into "
                    "the smoke, opening the king for your next attack."
                )
                fight["parry_opening"] = {
                    "source": "player_parry",
                    "intent": intent,
                    "damage_bonus": 1,
                    "guaranteed_next_attack": True,
                    "allowed_moves": ("heavy", "light"),
                    "message": (
                        "Your parry has opened the king. "
                        "Your next heavy attack will deal 5 damage, "
                        "or your next light attack will deal 3."
                    ),
                }
            elif move == "deflect":
                message = (
                    "You read the king correctly. Your deflection "
                    "slides the blade off-line and opens a narrow cut."
                )
            elif move.startswith("feint_"):
                message = (
                    "You read the king correctly. Your feint draws "
                    "the royal guard out of place before your attack "
                    "lands."
                )
            else:
                message = (
                    "You read the king correctly. "
                    f"Your {move} answer lands through the smoke."
                )

            king_defense = self._king_defense_reaction(
                move,
                intent,
                reaction_plan=reaction_plan,
            )

            if king_defense is not None:
                king_damage = 0

                if (
                    king_defense.get(
                        "player_damage_mode"
                    )
                    == "incoming"
                ):
                    player_damage = (
                        incoming_damage[intent]
                    )
                else:
                    player_damage = 0

                result = king_defense[
                    "type"
                ]

                message = king_defense[
                    "message"
                ]

                if move == "parry":
                    fight["parry_opening"] = None

                if player_damage > 0:
                    fight[
                        "king_has_hit_player"
                    ] = True

                    fight[
                        "clean_king_victory_possible"
                    ] = False
        else:
            king_damage = 0
            player_damage = incoming_damage[intent]
            result = "king_hit"
            fight["king_has_hit_player"] = True
            fight["clean_king_victory_possible"] = False
            message = (
                "You misread the king. His blade lands, and something "
                "about the fight changes without him saying why."
            )

        reaction_plan_matched = (
            reaction_prediction["matched"]
        )

        reaction_plan_missed = (
            reaction_prediction["missed"]
        )

        reaction_miss_exposed_enemy = (
            reaction_plan_missed is True
            and king_damage > 0
        )

        if king_defense is not None:
            resolution_source = (
                "reaction_plan"
            )
        elif correct:
            resolution_source = (
                "player_counter"
            )
        else:
            resolution_source = (
                "base_intent"
            )

        active_opening = fight.get(
            "parry_opening"
        )

        if isinstance(active_opening, dict):
            active_opening[
                "source_commitment"
            ] = {
                "stage": fight["stage"],
                "intent": intent,
                "intent_label": {
                    "royal_lunge": "Royal Lunge",
                    "crown_guard": "Crown Guard",
                    "overextended_recovery": (
                        "Open Recovery"
                    ),
                }.get(
                    intent,
                    intent,
                ),
                "reaction_plan": reaction_plan,
                "reaction_plan_label": (
                    self
                    ._king_fight_reaction_plan_labels()
                    .get(
                        reaction_plan,
                        reaction_plan,
                    )
                ),
                "reaction_plan_predictive": (
                    reaction_prediction[
                        "predictive"
                    ]
                ),
                "reaction_plan_matched": (
                    reaction_plan_matched
                ),
                "reaction_plan_triggered": (
                    reaction_plan_matched is True
                ),
                "reaction_plan_missed": (
                    reaction_plan_missed
                ),
                "reaction_miss_exposed_enemy": (
                    reaction_miss_exposed_enemy
                ),
                "reaction_miss_bonus": (
                    reaction_miss_bonus
                ),
                "resolution_source": (
                    resolution_source
                ),
                "intent_reason": (
                    opponent_intent_reason
                ),
                "reaction_reason": (
                    opponent_reaction_reason
                ),
            }

        fight["king_health"] = max(
            0,
            fight["king_health"] - king_damage,
        )
        fight["player_health"] = max(
            0,
            fight["player_health"] - player_damage,
        )
        fight["exchange_count"] += 1
        self._record_king_fight_player_move(move)

        next_intent = self._king_intent(fight["exchange_count"])

        if (
            king_defense is not None
            and king_defense.get(
                "opens_forced_response",
                True,
            )
        ):
            forced_response = (
                self
                ._build_king_forced_response(
                    king_defense,
                    next_intent,
                    recovery_read=(
                        deepcopy(
                            active_audit.get(
                                "forced_response_read"
                            )
                        )
                        if isinstance(
                            active_audit,
                            dict,
                        )
                        else None
                    ),
                )
            )

            forced_response[
                "source_commitment"
            ] = {
                "stage": fight["stage"],
                "intent": intent,
                "intent_label": {
                    "royal_lunge": "Royal Lunge",
                    "crown_guard": "Crown Guard",
                    "overextended_recovery": (
                        "Open Recovery"
                    ),
                    "shield_wall": "Shield Wall",
                    "champion_lunge": (
                        "Champion Lunge"
                    ),
                    "wide_execution": (
                        "Wide Execution"
                    ),
                    "open_recovery": (
                        "Open Recovery"
                    ),
                }.get(
                    intent,
                    intent,
                ),
                "reaction_plan": reaction_plan,
                "reaction_plan_label": (
                    self
                    ._king_fight_reaction_plan_labels()
                    .get(
                        reaction_plan,
                        reaction_plan,
                    )
                ),
                "reaction_plan_predictive": (
                    reaction_prediction[
                        "predictive"
                    ]
                ),
                "reaction_plan_matched": (
                    reaction_plan_matched
                ),
                "reaction_plan_triggered": (
                    reaction_plan_matched is True
                ),
                "reaction_plan_missed": (
                    reaction_plan_missed
                ),
                "reaction_miss_exposed_enemy": (
                    reaction_miss_exposed_enemy
                ),
                "reaction_miss_bonus": (
                    reaction_miss_bonus
                ),
                "resolution_source": (
                    resolution_source
                ),
                "intent_reason": (
                    opponent_intent_reason
                ),
                "reaction_reason": (
                    opponent_reaction_reason
                ),
            }

            fight["forced_response"] = (
                forced_response
            )

            king_defense[
                "forced_response"
            ] = self._public_forced_response(
                forced_response
            )

        initiative_before = (
            self._ensure_king_fight_initiative()
        )
        initiative_event = (
            self._king_fight_initiative_event(
                move=move,
                damage_to_enemy=king_damage,
                damage_to_player=player_damage,
                opponent_reaction=king_defense,
                reaction_missed=(
                    reaction_plan_missed
                ),
            )
        )
        initiative_after = (
            self._advance_king_fight_initiative(
                initiative_event
            )
        )

        fight["last_exchange"] = {
            "stage": fight["stage"],
            "intent": intent,
            "move": move,
            "expected": expected,
            "valid_responses": list(valid_responses),
            "king_defense": deepcopy(king_defense),
            "opponent_reaction": deepcopy(
                king_defense
            ),
            "opponent_reaction_plan": (
                reaction_plan
            ),
            "opponent_reaction_plan_label": (
                self
                ._king_fight_reaction_plan_labels()
                .get(
                    reaction_plan,
                    reaction_plan,
                )
            ),
            "reaction_plan_predictive": (
                reaction_prediction[
                    "predictive"
                ]
            ),
            "reaction_plan_matched": (
                reaction_plan_matched
            ),
            "reaction_plan_triggered": (
                reaction_plan_matched is True
            ),
            "reaction_plan_missed": (
                reaction_plan_missed
            ),
            "reaction_miss_exposed_enemy": (
                reaction_miss_exposed_enemy
            ),
            "reaction_miss_bonus": (
                reaction_miss_bonus
            ),
            "resolution_source": (
                resolution_source
            ),
            "opponent_intent_reason": (
                opponent_intent_reason
            ),
            "opponent_reaction_reason": (
                opponent_reaction_reason
            ),
            "opponent_proposal_reason": (
                opponent_intent_reason
            ),
            "initiative_before": initiative_before,
            "initiative_after": initiative_after,
            "initiative_event": initiative_event,
            "parry_opening": deepcopy(fight.get("parry_opening")),
            "result": result,
            "king_damage": king_damage,
            "player_damage": player_damage,
            "message": message,
        }

        if fight["player_health"] <= 0:
            return self._finish_player_death(killer="king")

        if (
            fight["stage"] == "king_phase_one"
            and fight["king_health"] <= fight["king_half_health"]
        ):
            collapse = self._advance_castle_timer()
            if collapse is not None:
                return collapse

            packet = self._transition_to_elite_knight()
            narrative = (
                "For one breath the king looks almost mortal. He "
                "staggers back into the smoke, one hand pressed to "
                "the blood under his royal armor. Then his fear hardens "
                "into command. He raises two fingers, and the burning "
                "hall answers with iron: the King's Champion steps "
                "between you and the throne."
            )

            if isinstance(packet, dict):
                next_tell = packet.get("tell", "")

                packet["narrative"] = narrative
                packet["note"] = narrative

                if next_tell:
                    packet["tell"] = narrative + "\n\n" + next_tell
                else:
                    packet["tell"] = narrative

                self.last_action_note = packet["tell"]

            return packet

        if (
            fight["stage"] == "king_phase_two"
            and fight["king_health"] <= 0
        ):
            if fight["clean_king_victory_possible"]:
                return self._enter_king_fate_choice()

            return self._finish_uncertain_king_victory()

        fight["intent"] = next_intent
        self.last_action_note = (
            message
            + " "
            + self._king_intent_tell(fight["intent"])
        )

        collapse = self._advance_castle_timer()
        if collapse is not None:
            return collapse

        return {
            "outcome": "king_exchange",
            "stage": fight["stage"],
            "exchange": deepcopy(fight["last_exchange"]),
            "player_health": fight["player_health"],
            "king_health": fight["king_health"],
            "castle_timer": fight["castle_timer"],
            "clean_king_victory_possible": (
                fight["clean_king_victory_possible"]
            ),
            "tell": self._king_intent_tell(fight["intent"]),
            "parry_opening": deepcopy(
                fight.get("parry_opening")
            ),
            "forced_response": self._public_forced_response(
                fight.get("forced_response")
            ),
            "initiative": deepcopy(
                fight.get("initiative")
            ),
        }

    def _resolve_elite_parry_opening_move(
        self,
        move: str,
        parry_opening: dict,
    ) -> dict:
        fight = self.king_fight
        source_commitment = parry_opening.get(
            "source_commitment"
        )

        if not isinstance(source_commitment, dict):
            source_commitment = {}

        intent = str(
            parry_opening.get("intent")
            or source_commitment.get("intent")
            or fight["intent"]
        )
        knight_damage = int(
            KING_FIGHT_PLAYER_DAMAGE[
                "parry_opening"
            ][move]
        )
        player_damage = 0
        result = "parry_opening_hit"
        message = (
            "You spend the opening your parry created. "
            f"Your {move} attack lands before the Champion can "
            "rebuild his shield line."
        )

        fight["parry_opening"] = None
        fight["elite_knight_health"] = max(
            0,
            fight["elite_knight_health"] - knight_damage,
        )
        fight["exchange_count"] += 1
        self._record_king_fight_player_move(move)

        initiative_before = self._ensure_king_fight_initiative()
        initiative_after = self._advance_king_fight_initiative(
            "player_attack_hit"
        )

        fight["last_exchange"] = {
            "stage": "elite_knight",
            "intent": intent,
            "move": move,
            "expected": move,
            "valid_responses": ["heavy", "light"],
            "parry_opening_used": deepcopy(parry_opening),
            "source_opponent_commitment": deepcopy(
                source_commitment
            ),
            "opponent_reaction_plan": (
                source_commitment.get(
                    "reaction_plan"
                )
            ),
            "opponent_reaction_plan_label": (
                source_commitment.get(
                    "reaction_plan_label"
                )
            ),
            "reaction_plan_predictive": (
                source_commitment.get(
                    "reaction_plan_predictive"
                )
            ),
            "reaction_plan_matched": (
                source_commitment.get(
                    "reaction_plan_matched"
                )
            ),
            "reaction_plan_triggered": (
                source_commitment.get(
                    "reaction_plan_triggered"
                )
            ),
            "reaction_plan_missed": (
                source_commitment.get(
                    "reaction_plan_missed"
                )
            ),
            "reaction_miss_exposed_enemy": (
                source_commitment.get(
                    "reaction_miss_exposed_enemy"
                )
            ),
            "reaction_miss_bonus": (
                source_commitment.get(
                    "reaction_miss_bonus",
                    0,
                )
            ),
            "resolution_source": "parry_opening",
            "opponent_control_source": (
                "ghost_parry_continuation"
            ),
            "opponent_intent_reason": (
                source_commitment.get(
                    "intent_reason"
                )
            ),
            "opponent_reaction_reason": (
                source_commitment.get(
                    "reaction_reason"
                )
            ),
            "opponent_proposal_reason": (
                source_commitment.get(
                    "intent_reason"
                )
            ),
            "result": result,
            "elite_knight_damage": knight_damage,
            "player_damage": player_damage,
            "king_heal": 0,
            "initiative_before": initiative_before,
            "initiative_after": initiative_after,
            "initiative_event": "player_attack_hit",
            "message": message,
        }

        if fight["elite_knight_health"] <= 0:
            fight["stage"] = "king_phase_two"
            fight["exchange_count"] = 0
            fight["intent"] = self._king_intent(0)
            fight["initiative"] = (
                self._social.advance_combat_initiative(
                    previous_state=initiative_after["state"],
                    event="stage_transition",
                )
            )
            self.last_action_note = (
                "The King's Champion falls into the burning stone. "
                "The king steps over him for the final phase."
            )
            collapse = self._advance_castle_timer()
            if collapse is not None:
                return collapse
            return {
                "outcome": "elite_knight_defeated",
                "stage": "king_phase_two",
                "king_health": fight["king_health"],
                "king_morale_ticks": fight["king_morale_ticks"],
                "failed_knight_reads": fight["failed_knight_reads"],
                "player_health": fight["player_health"],
                "castle_timer": fight["castle_timer"],
                "tell": self._king_intent_tell(fight["intent"]),
                "initiative": deepcopy(fight["initiative"]),
            }

        fight["intent"] = self._elite_knight_intent(
            fight["exchange_count"]
        )
        self.last_action_note = (
            message + " " + self._elite_knight_tell(fight["intent"])
        )
        collapse = self._advance_castle_timer()
        if collapse is not None:
            return collapse

        return {
            "outcome": "elite_knight_exchange",
            "stage": "elite_knight",
            "exchange": deepcopy(fight["last_exchange"]),
            "player_health": fight["player_health"],
            "elite_knight_health": fight["elite_knight_health"],
            "king_health": fight["king_health"],
            "king_morale_ticks": fight["king_morale_ticks"],
            "castle_timer": fight["castle_timer"],
            "tell": self._elite_knight_tell(fight["intent"]),
            "parry_opening": None,
            "initiative": deepcopy(fight["initiative"]),
        }

    def _resolve_elite_knight_move(self, move: str) -> dict:
        fight = self.king_fight
        intent = fight["intent"]

        parry_opening = fight.get("parry_opening")

        if (
            isinstance(parry_opening, dict)
            and move in ("heavy", "light")
        ):
            return self._resolve_elite_parry_opening_move(
                move,
                parry_opening,
            )

        reaction_plan = (
            self
            ._consume_king_fight_opponent_reaction_plan(
                intent
            )
        )

        active_audit = fight.get(
            "llm_opponent_audit"
        )

        opponent_intent_reason = None
        opponent_reaction_reason = None

        if (
            isinstance(
                active_audit,
                dict,
            )
            and active_audit.get(
                "selection_key"
            )
            == (
                f"{fight['stage']}:"
                f"{fight['exchange_count']}"
            )
        ):
            opponent_intent_reason = (
                active_audit.get(
                    "intent_reason"
                )
                or active_audit.get(
                    "proposal_reason"
                )
            )

            opponent_reaction_reason = (
                active_audit.get(
                    "reaction_reason"
                )
            )

        reaction_prediction = (
            self
            ._king_fight_reaction_prediction_status(
                reaction_plan,
                move,
            )
        )

        correct_moves = {
            "shield_wall": (
                "feint_heavy",
                "feint_light",
            ),
            "champion_lunge": (
                "parry",
                "deflect",
                "dodge",
            ),
            "wide_execution": (
                "deflect",
                "parry",
                "dodge",
            ),
            "open_recovery": (
                "heavy",
                "light",
            ),
        }
        knight_damage_by_intent = {
            "shield_wall": {
                "feint_heavy": int(
                    KING_FIGHT_PLAYER_DAMAGE[
                        "normal"
                    ]["feint_heavy"]
                ),
                "feint_light": int(
                    KING_FIGHT_PLAYER_DAMAGE[
                        "normal"
                    ]["feint_light"]
                ),
            },
            "champion_lunge": {
                "parry": 0,
                "deflect": int(
                    KING_FIGHT_PLAYER_DAMAGE[
                        "normal"
                    ]["deflect"]
                ),
                "dodge": 0,
            },
            "wide_execution": {
                "deflect": int(
                    KING_FIGHT_PLAYER_DAMAGE[
                        "normal"
                    ]["deflect"]
                ),
                "parry": 0,
                "dodge": 0,
            },
            "open_recovery": {
                "heavy": int(
                    KING_FIGHT_PLAYER_DAMAGE[
                        "normal"
                    ]["heavy"]
                ),
                "light": int(
                    KING_FIGHT_PLAYER_DAMAGE[
                        "normal"
                    ]["light"]
                ),
            },
        }

        valid_responses = correct_moves[intent]
        expected = valid_responses[0]
        correct = move in valid_responses

        opponent_reaction = None
        reaction_miss_bonus = 0

        if correct:
            raw_knight_damage = (
                knight_damage_by_intent[
                    intent
                ][move]
            )

            if raw_knight_damage > 0:
                reaction_miss_bonus = (
                    self
                    ._king_fight_reaction_miss_bonus(
                        reaction_plan,
                        move,
                    )
                )

                raw_knight_damage += (
                    reaction_miss_bonus
                )

            knight_damage = (
                raw_knight_damage
            )
            player_damage = 0
            king_heal = 0
            result = "correct_read"

            if move == "dodge":
                message = (
                    "You clear the Champion's lunge. The dodge keeps "
                    "you alive, but it does not cut through his armor."
                )
            elif move == "parry":
                message = (
                    "You catch the Champion's committed line and turn "
                    "his shield-side pressure into a one-breath opening."
                )
            else:
                message = (
                    "You survive the Champion's read and cut through "
                    "his legend one exchange at a time."
                )

            opponent_reaction = (
                self
                ._precommitted_opponent_reaction(
                    "elite_knight",
                    move,
                    intent,
                    reaction_plan,
                )
            )

            if opponent_reaction is not None:
                knight_damage = 0

                if (
                    opponent_reaction.get(
                        "player_damage_mode"
                    )
                    == "incoming"
                ):
                    player_damage = 3
                    king_heal = 1

                    fight[
                        "failed_knight_reads"
                    ] += 1

                    fight[
                        "king_morale_ticks"
                    ] += 1

                    fight["king_health"] = min(
                        fight["king_max_health"],
                        (
                            fight["king_health"]
                            + king_heal
                        ),
                    )
                else:
                    player_damage = 0
                    king_heal = 0

                result = opponent_reaction[
                    "type"
                ]

                message = opponent_reaction[
                    "message"
                ]
            elif move == "parry":
                fight["parry_opening"] = {
                    "source": "player_parry",
                    "intent": intent,
                    "target": "elite_knight",
                    "damage_bonus": 1,
                    "guaranteed_next_attack": True,
                    "allowed_moves": ("heavy", "light"),
                    "message": (
                        "Your parry has opened the Champion. "
                        "Your next heavy attack will deal 5 damage, "
                        "or your next light attack will deal 3."
                    ),
                }
        else:
            knight_damage = 0
            player_damage = 3
            king_heal = 1
            result = "failed_knight_read"
            fight["failed_knight_reads"] += 1
            fight["king_morale_ticks"] += 1
            fight["king_health"] = min(
                fight["king_max_health"],
                fight["king_health"] + king_heal,
            )
            message = (
                "Your response fails against the Champion's committed "
                "tactic. The king straightens behind him, feeding on "
                "every failed attack."
            )

        reaction_plan_matched = (
            reaction_prediction["matched"]
        )

        reaction_plan_missed = (
            reaction_prediction["missed"]
        )

        reaction_miss_exposed_enemy = (
            reaction_plan_missed is True
            and knight_damage > 0
        )

        if opponent_reaction is not None:
            resolution_source = (
                "reaction_plan"
            )
        elif correct:
            resolution_source = (
                "player_counter"
            )
        else:
            resolution_source = (
                "base_intent"
            )

        active_opening = fight.get(
            "parry_opening"
        )

        if isinstance(active_opening, dict):
            active_opening[
                "source_commitment"
            ] = {
                "stage": fight["stage"],
                "intent": intent,
                "intent_label": {
                    "shield_wall": "Shield Wall",
                    "champion_lunge": (
                        "Champion Lunge"
                    ),
                    "wide_execution": (
                        "Wide Execution"
                    ),
                    "open_recovery": (
                        "Open Recovery"
                    ),
                }.get(
                    intent,
                    intent,
                ),
                "reaction_plan": reaction_plan,
                "reaction_plan_label": (
                    self
                    ._king_fight_reaction_plan_labels()
                    .get(
                        reaction_plan,
                        reaction_plan,
                    )
                ),
                "reaction_plan_predictive": (
                    reaction_prediction[
                        "predictive"
                    ]
                ),
                "reaction_plan_matched": (
                    reaction_plan_matched
                ),
                "reaction_plan_triggered": (
                    reaction_plan_matched is True
                ),
                "reaction_plan_missed": (
                    reaction_plan_missed
                ),
                "reaction_miss_exposed_enemy": (
                    reaction_miss_exposed_enemy
                ),
                "reaction_miss_bonus": (
                    reaction_miss_bonus
                ),
                "resolution_source": (
                    resolution_source
                ),
                "intent_reason": (
                    opponent_intent_reason
                ),
                "reaction_reason": (
                    opponent_reaction_reason
                ),
            }

        fight["elite_knight_health"] = max(
            0,
            fight["elite_knight_health"] - knight_damage,
        )
        fight["player_health"] = max(
            0,
            fight["player_health"] - player_damage,
        )
        fight["exchange_count"] += 1
        self._record_king_fight_player_move(move)

        initiative_before = (
            self._ensure_king_fight_initiative()
        )
        initiative_event = (
            self._king_fight_initiative_event(
                move=move,
                damage_to_enemy=knight_damage,
                damage_to_player=player_damage,
                opponent_reaction=opponent_reaction,
                reaction_missed=(
                    reaction_plan_missed
                ),
            )
        )
        initiative_after = (
            self._advance_king_fight_initiative(
                initiative_event
            )
        )

        fight["last_exchange"] = {
            "stage": "elite_knight",
            "intent": intent,
            "move": move,
            "expected": expected,
            "valid_responses": list(valid_responses),
            "result": result,
            "elite_knight_damage": knight_damage,
            "player_damage": player_damage,
            "king_heal": king_heal,
            "opponent_reaction": deepcopy(
                opponent_reaction
            ),
            "opponent_reaction_plan": (
                reaction_plan
            ),
            "opponent_reaction_plan_label": (
                self
                ._king_fight_reaction_plan_labels()
                .get(
                    reaction_plan,
                    reaction_plan,
                )
            ),
            "reaction_plan_predictive": (
                reaction_prediction[
                    "predictive"
                ]
            ),
            "reaction_plan_matched": (
                reaction_plan_matched
            ),
            "reaction_plan_triggered": (
                reaction_plan_matched is True
            ),
            "reaction_plan_missed": (
                reaction_plan_missed
            ),
            "reaction_miss_exposed_enemy": (
                reaction_miss_exposed_enemy
            ),
            "reaction_miss_bonus": (
                reaction_miss_bonus
            ),
            "resolution_source": (
                resolution_source
            ),
            "opponent_intent_reason": (
                opponent_intent_reason
            ),
            "opponent_reaction_reason": (
                opponent_reaction_reason
            ),
            "opponent_proposal_reason": (
                opponent_intent_reason
            ),
            "initiative_before": initiative_before,
            "initiative_after": initiative_after,
            "initiative_event": initiative_event,
            "parry_opening": deepcopy(
                fight.get("parry_opening")
            ),
            "message": message,
        }

        if fight["player_health"] <= 0:
            return self._finish_player_death(
                killer="elite_knight"
            )

        if fight["elite_knight_health"] <= 0:
            fight["stage"] = "king_phase_two"
            fight["parry_opening"] = None
            fight["forced_response"] = None
            fight["exchange_count"] = 0
            fight["intent"] = self._king_intent(0)
            fight["initiative"] = (
                self._social.advance_combat_initiative(
                    previous_state=(
                        self._ensure_king_fight_initiative()[
                            "state"
                        ]
                    ),
                    event="stage_transition",
                )
            )

            self.last_action_note = (
                "The King's Champion falls into the burning stone. "
                "The king steps over him, restored by every mistake "
                "you made against the knight."
            )

            collapse = self._advance_castle_timer()
            if collapse is not None:
                return collapse

            return {
                "outcome": "elite_knight_defeated",
                "stage": "king_phase_two",
                "king_health": fight["king_health"],
                "king_morale_ticks": fight["king_morale_ticks"],
                "failed_knight_reads": fight["failed_knight_reads"],
                "player_health": fight["player_health"],
                "castle_timer": fight["castle_timer"],
                "tell": self._king_intent_tell(fight["intent"]),
            }

        fight["intent"] = self._elite_knight_intent(
            fight["exchange_count"]
        )
        self.last_action_note = (
            message
            + " "
            + self._elite_knight_tell(fight["intent"])
        )

        collapse = self._advance_castle_timer()
        if collapse is not None:
            return collapse

        return {
            "outcome": "elite_knight_exchange",
            "stage": "elite_knight",
            "exchange": deepcopy(fight["last_exchange"]),
            "player_health": fight["player_health"],
            "elite_knight_health": fight["elite_knight_health"],
            "king_health": fight["king_health"],
            "king_morale_ticks": fight["king_morale_ticks"],
            "castle_timer": fight["castle_timer"],
            "tell": self._elite_knight_tell(fight["intent"]),
            "parry_opening": deepcopy(
                fight.get("parry_opening")
            ),
            "initiative": deepcopy(
                fight.get("initiative")
            ),
        }

    def resolve_king_fight_move(
        self,
        move: str,
    ) -> dict | None:
        """
        Resolve one deterministic exchange in the burning castle.

        The hidden clean-victory flag is lost only when the king hits the
        player during a king phase. Knight damage can kill the player,
        but it does not break the execute/jail condition by itself.
        """
        if self.king_fight is None:
            return self._deny(
                "There is no active king confrontation."
            )

        if self.ending:
            return self._deny(
                "The endgame has already resolved."
            )

        if not isinstance(move, str) or not move.strip():
            return self._deny(
                "Choose a king-fight move."
            )

        normalized = move.strip().lower()
        allowed = {
            "heavy",
            "light",
            "feint_heavy",
            "feint_light",
            "parry",
            "deflect",
            "dodge",
        }

        if normalized not in allowed:
            return self._deny(
                "Choose heavy, light, feint_heavy, feint_light, "
                "parry, deflect, or dodge."
            )

        stage = self.king_fight["stage"]
        parry_opening = self.king_fight.get(
            "parry_opening"
        )

        if (
            isinstance(parry_opening, dict)
            and normalized not in ("heavy", "light")
        ):
            return self._deny_parry_opening_move(
                normalized
            )

        if stage in ("king_phase_one", "king_phase_two"):
            return self._resolve_king_phase_move(normalized)

        if stage == "elite_knight":
            return self._resolve_elite_knight_move(normalized)

        if stage == "fate_choice":
            return self._deny(
                "The king is beaten. Choose execute_king or jail_king."
            )

        if stage == "crown_loop":
            return self._deny(
                "The king fight is over. You hold the crown now."
            )

        return self._deny(
            "The burning castle has already resolved."
        )

    def choose_king_fate(
        self,
        choice: str,
    ) -> dict | None:
        if (
            not isinstance(self.king_fight, dict)
            or self.king_fight.get("stage") != "fate_choice"
            or self.ending
        ):
            return self._deny(
                "You do not have the king at your mercy."
            )

        normalized = (
            choice.strip().lower()
            if isinstance(choice, str)
            else choice
        )

        if normalized not in ("execute_king", "jail_king"):
            return self._deny(
                "Choose execute_king or jail_king."
            )

        self.phase = "crown"
        self.actions = REBELLION_ACTIONS
        self.location = "castle"
        self.alive = True
        self.captured = False
        self.king_control = 0
        self.king_fight["stage"] = "crown_loop"
        self.king_fight["king_fate"] = normalized
        self.king_fight["clean_ending_choice"] = True

        if normalized == "execute_king":
            king_status = "executed"
            note = (
                "The tyrant dies by your order. The loop flips: the "
                "rebellion is over, the crown is yours, and the towns "
                "will now judge what kind of king you become."
            )
        else:
            king_status = "jailed"
            note = (
                "The tyrant lives behind your bars. The loop flips: "
                "the rebellion is over, the crown is yours, and the "
                "towns will now judge what kind of king you become."
            )

        self.last_action_note = note

        return {
            "outcome": normalized,
            "stage": "crown_loop",
            "king_status": king_status,
            "phase": self.phase,
            "endgame_action": self.endgame_action_label(),
            "ending": "",
            "note": note,
        }

    def royal_visit(
        self,
        town_id: str,
    ) -> dict | None:
        if (
            self.phase != "crown"
            or not isinstance(self.king_fight, dict)
            or self.king_fight.get("stage") != "crown_loop"
        ):
            return self._deny(
                "You do not hold the crown yet."
            )

        if town_id not in self.towns:
            return self._deny(
                "Unknown town."
            )

        self.location = town_id
        trust = self.town_trust(town_id)
        fear = self.towns[town_id]["fear"]

        if trust >= 0.55 and fear <= 2:
            view = "beloved"
            note = (
                f"{self.towns[town_id]['name']} greets you as the "
                "king who remembered them before taking the crown."
            )
        elif trust >= 0.25:
            view = "hopeful"
            note = (
                f"{self.towns[town_id]['name']} watches carefully, "
                "hopeful that the rebellion did not become another "
                "mask for power."
            )
        elif fear >= 4:
            view = "afraid"
            note = (
                f"{self.towns[town_id]['name']} kneels quickly. "
                "They are free from the old tyrant, but not yet free "
                "from fear."
            )
        else:
            view = "uncertain"
            note = (
                f"{self.towns[town_id]['name']} studies you in silence, "
                "waiting to see whether the crown changed hands or "
                "changed shape."
            )

        self.last_action_note = note

        return {
            "town": town_id,
            "town_name": self.towns[town_id]["name"],
            "view": view,
            "trust": trust,
            "fear": fear,
            "note": note,
        }

    def retire_crown(self) -> dict | None:
        if (
            self.phase != "crown"
            or not isinstance(self.king_fight, dict)
            or self.king_fight.get("stage") != "crown_loop"
        ):
            return self._deny(
                "You cannot retire a crown you do not hold."
            )

        stats = self._final_kingdom_stats()
        average_trust = sum(
            town["trust"]
            for town in stats["towns"].values()
        ) / len(stats["towns"])
        total_fear = sum(
            town["fear"]
            for town in stats["towns"].values()
        )

        if average_trust >= 0.55 and total_fear <= 7:
            legacy = "beloved"
        elif average_trust >= 0.25:
            legacy = "respected"
        elif total_fear >= 11:
            legacy = "feared"
        else:
            legacy = "remembered"

        self.alive = True
        self.captured = False
        self.king_fight["retired_legacy"] = legacy

        return self._set_final_ending(
            outcome="retired_crown",
            ending=(
                "Years pass after the burning castle. You walk the "
                "roads your rebellion once crossed in secret, now as "
                f"a {legacy} king. When you finally retire the crown, "
                "the towns remember the whole story: the fear, the "
                "fire, the choices, and the day the state of the "
                "kingdom truly changed."
            ),
            ending_type="retirement",
            king_status=self.king_fight.get(
                "king_fate",
                "defeated",
            ),
            rebellion_status="became_kingdom",
            extra={
                "legacy": legacy,
                "endgame_action": self.endgame_action_label(),
            },
        )

    def _check_capture(self) -> None:
        if self.heat < 8 or not self.alive:
            return

        risk = (
            (self.heat - 7) * 12
            + self.danger_level() * 3
        )

        risk = max(5, min(85, risk))

        if self.rng.randint(1, 100) <= risk:
            self.captured = True
            self.alive = False
            self.ending = (
                "The king's patrol net closes around you."
            )

    def _camp_output(self) -> dict:
        farmers = self.assignments["farmers"]
        foragers = self.assignments["foragers"]
        trainers = self.assignments["trainers"]
        smiths = self.assignments["smiths"]
        scouts = self.assignments["scouts"]

        food_gain = (
            farmers * (2 if self.seeds else 1)
            + foragers
        )

        gold_gain = foragers

        weapon_gain = smiths // 2

        if trainers >= 2 and self.food > 0:
            self.weapon_stock["sword"] += 1
            self._sync_weapon_total()
            self.food -= 1

        self.food += food_gain
        self.gold += gold_gain
        if weapon_gain:
            self.weapon_stock["sword"] += weapon_gain
            self._sync_weapon_total()

        self.heat = max(0, self.heat - scouts)

        return {
            "food_gain": food_gain,
            "gold_gain": gold_gain,
            "weapon_gain": weapon_gain,
            "scouts": scouts,
        }

    def _king_response(self) -> list[str]:
        events = []

        self.knight_town = self.rng.choice(list(TOWN_IDS))
        knight_town = self.towns[self.knight_town]

        knight_town["fear"] = min(
            5,
            knight_town["fear"] + 1,
        )

        events.append(
            "A royal knight arrives in "
            + knight_town["name"]
            + "."
        )

        for town_id, town in self.towns.items():
            if not self.has_active_guard(town_id):
                chance = (
                    15
                    + self.heat * 4
                    + town["recruited"] * 2
                )

                if town_id == "crownmarket":
                    chance += 10

                if self.rng.randint(1, 100) <= min(75, chance):
                    rank = (
                        "crown_guard"
                        if town_id == "crownmarket"
                        else "watchman"
                    )

                    self._add_guard(town_id, rank)

                    events.append(
                        "The king reinforces "
                        + town["name"]
                        + "."
                    )

        most_recruited = max(
            TOWN_IDS,
            key=lambda town_id: self.towns[town_id]["recruited"],
        )

        if (
            self.towns[most_recruited]["recruited"] >= 5
            and self.rng.randint(1, 100) <= 45
        ):
            self.towns[most_recruited]["locked"] = True
            self.towns[most_recruited]["fear"] = min(
                5,
                self.towns[most_recruited]["fear"] + 1,
            )

            events.append(
                "The king locks down "
                + self.towns[most_recruited]["name"]
                + "."
            )

        if self.followers >= 15:
            self.king_control = max(0, self.king_control - 1)

            events.append(
                "Rumors of rebellion weaken royal control."
            )
        else:
            self.king_control = min(10, self.king_control + 1)

            events.append(
                "Royal propaganda strengthens the king's control."
            )

        return events


    def end_day(self) -> dict:
        self._advance_town_memories()

        if self.phase == "rebellion":
            food_needed = self.daily_food_need()
            food_before = self.food

            if self.food < food_needed:
                self.food = 0
                self.alive = False
                self.ending = (
                    "Your rebellion starves and scatters."
                )

                return {
                    "food": self.food,
                    "alive": self.alive,
                    "ending": self.ending,
                    "day_report": {
                        "food_before": food_before,
                        "food_used": food_needed,
                        "leader_fed": 1,
                        "followers_fed": self.followers,
                        "starved": True,
                        "scout_reports": [],
                    },
                }

            self.food -= food_needed

            scout_reports = self._run_scout_reports()
            scout_capacity = self.scout_capacity()

            self._reset_daily_limits()

            tick_packet = self._social.tick()

            day_report = {
                "food_before": food_before,
                "food_used": food_needed,
                "leader_fed": 1,
                "followers_fed": self.followers,
                "starved": False,
                "scout_capacity": scout_capacity,
                "scout_reports": scout_reports,
            }

            if self.phase_day >= REBELLION_DAYS:
                self.phase = "camp"
                self.phase_day = 1
                self.actions = CAMP_ACTIONS

                return {
                    "phase_change": "camp",
                    "tick": tick_packet,
                    "day_report": day_report,
                }

            self.phase_day += 1
            self.actions = REBELLION_ACTIONS

            return {
                "phase": "rebellion",
                "tick": tick_packet,
                "day_report": day_report,
            }

        camp_output = self._camp_output()

        if self.phase_day >= CAMP_DAYS:
            self.last_king_response = self._king_response()

            self.phase = "rebellion"
            self.phase_number += 1
            self.phase_day = 1
            self.actions = REBELLION_ACTIONS
            self._reset_daily_limits()

            return {
                "phase_change": "rebellion",
                "camp_output": camp_output,
                "king_response": self.last_king_response,
            }

        self.phase_day += 1
        self.actions = CAMP_ACTIONS

        return {
            "phase": "camp",
            "camp_output": camp_output,
        }

    def crown_towns(self) -> tuple[str, ...]:
        return (
            "Ashfield",
            "Millcross",
            "Crownmarket",
        )

    def crown_town_locations(
        self,
        town_id: str,
    ) -> tuple[dict, ...]:
        town = self._normalize_crown_town(town_id)

        return (
            {
                "id": "blacksmith",
                "label": "Visit blacksmith",
                "town": town,
            },
            {
                "id": "goods_stall",
                "label": "Visit goods stall",
                "town": town,
            },
            {
                "id": "public_event",
                "label": "Visit public event",
                "town": town,
            },
            {
                "id": "town_square",
                "label": "Visit middle of town",
                "town": town,
            },
        )

    def _normalize_crown_town(
        self,
        town_id: str,
    ) -> str:
        if not isinstance(town_id, str) or not town_id.strip():
            raise ValueError("Choose a crown-loop town.")

        requested = town_id.strip().lower().replace("_", " ")

        for town in self.crown_towns():
            if requested == town.lower():
                return town

        aliases = {
            "ash": "Ashfield",
            "field": "Ashfield",
            "mill": "Millcross",
            "market": "Crownmarket",
            "crown": "Crownmarket",
        }

        if requested in aliases:
            return aliases[requested]

        raise ValueError(
            "Unknown crown-loop town: "
            f"{town_id!r}"
        )

    def _normalize_crown_location(
        self,
        location_id: str,
    ) -> str:
        if not isinstance(location_id, str) or not location_id.strip():
            raise ValueError("Choose a crown-loop location.")

        key = (
            location_id
            .strip()
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )

        aliases = {
            "smith": "blacksmith",
            "black_smith": "blacksmith",
            "stall": "goods_stall",
            "goods": "goods_stall",
            "market": "goods_stall",
            "event": "public_event",
            "public": "public_event",
            "square": "town_square",
            "middle": "town_square",
            "center": "town_square",
            "centre": "town_square",
        }

        key = aliases.get(key, key)

        allowed = {
            "blacksmith",
            "goods_stall",
            "public_event",
            "town_square",
        }

        if key not in allowed:
            raise ValueError(
                "Unknown crown-loop location: "
                f"{location_id!r}"
            )

        return key

    def _crown_fate(self) -> str:
        fight = getattr(self, "king_fight", None)

        if not isinstance(fight, dict):
            return "-"

        return (
            fight.get("king_fate")
            or fight.get("chosen_fate")
            or fight.get("king_fate_choice")
            or fight.get("fate")
            or "-"
        )

    def crown_rule_profile(self) -> dict:
        fate = self._crown_fate()

        fear_score = (
            self.heat
            + self.guards_defeated
            + (2 if fate == "execute_king" else 0)
        )

        mercy_score = (
            self.followers
            + self.food
            - self.heat
            - self.guards_defeated
            + (5 if fate == "jail_king" else 0)
        )

        if fear_score >= 14:
            rule = "feared"
        elif mercy_score >= 65:
            rule = "trusted"
        else:
            rule = "uncertain"

        return {
            "rule": rule,
            "fate": fate,
            "fear_score": fear_score,
            "mercy_score": mercy_score,
            "heat": self.heat,
            "followers": self.followers,
            "food": self.food,
            "gold": self.gold,
            "weapon_caches": self.weapons,
            "armor": self.armor,
            "guards_defeated": self.guards_defeated,
            "king_control": self.king_control,
        }

    def _crown_location_label(
        self,
        location_id: str,
    ) -> str:
        labels = {
            "blacksmith": "Blacksmith",
            "goods_stall": "Goods Stall",
            "public_event": "Public Event",
            "town_square": "Middle of Town",
        }

        return labels[location_id]

    def _crown_location_narration(
        self,
        town: str,
        location_id: str,
        profile: dict,
    ) -> str:
        rule = profile["rule"]
        fate = profile["fate"]

        if location_id == "blacksmith":
            if rule == "feared":
                return (
                    f"{town}'s blacksmith stops hammering when you enter. "
                    "The forge stays hot, but every apprentice goes silent. "
                    "They know the crown changed hands through force."
                )

            if rule == "trusted":
                return (
                    f"{town}'s blacksmith meets you at the anvil with a guarded bow. "
                    "He remembers the rebellion, but he also remembers who spared "
                    "people when the old crown would not."
                )

            return (
                f"{town}'s blacksmith watches you from behind the forge. "
                "He has not decided whether your crown is a promise or just "
                "a sharper blade."
            )

        if location_id == "goods_stall":
            if rule == "feared":
                return (
                    f"The goods stall in {town} lowers its prices before you ask. "
                    "No one calls it loyalty. It is the math of fear."
                )

            if rule == "trusted":
                return (
                    f"The goods stall in {town} stays open as you approach. "
                    "The merchant speaks carefully, but the crowd does not scatter."
                )

            return (
                f"The goods stall in {town} keeps trading, but every coin changes "
                "hands slower while people measure what kind of ruler you are."
            )

        if location_id == "public_event":
            if rule == "feared":
                return (
                    f"A public gathering in {town} bends around your arrival. "
                    "Three voices react at once: fear, anger, and practical survival."
                )

            if rule == "trusted":
                return (
                    f"A public gathering in {town} does not stop when you arrive. "
                    "Three citizens watch you closely, but none of them flee."
                )

            return (
                f"A public gathering in {town} falls into a tense pause. "
                "The crowd is not sure whether to cheer, kneel, or wait."
            )

        if rule == "feared":
            return (
                f"The middle of {town} clears a path for you. "
                "People remember the bodies it took to place you under the crown."
            )

        if rule == "trusted":
            return (
                f"The middle of {town} stays alive around you. "
                "Children keep running, traders keep calling, and the crown feels "
                "less like a threat than it used to."
            )

        return (
            f"The middle of {town} holds its breath. "
            "The kingdom is free from the old king, but not yet certain about you."
        )

    def _crown_npcs_for_location(
        self,
        town: str,
        location_id: str,
        profile: dict,
    ) -> tuple[dict, ...]:
        rule = profile["rule"]

        reaction_by_rule = {
            "feared": "fear",
            "trusted": "cautious_trust",
            "uncertain": "uncertainty",
        }

        base_reaction = reaction_by_rule[rule]

        if location_id == "blacksmith":
            return (
                {
                    "id": "blacksmith",
                    "name": f"{town} Blacksmith",
                    "role": "blacksmith",
                    "reaction": base_reaction,
                    "dialogue_hook": "forge_crown_reaction",
                },
            )

        if location_id == "goods_stall":
            return (
                {
                    "id": "stall_keeper",
                    "name": f"{town} Stall Keeper",
                    "role": "merchant",
                    "reaction": base_reaction,
                    "dialogue_hook": "market_crown_reaction",
                },
            )

        if location_id == "public_event":
            return (
                {
                    "id": "town_elder",
                    "name": f"{town} Elder",
                    "role": "elder",
                    "reaction": (
                        "remembers_cost"
                        if rule == "feared"
                        else base_reaction
                    ),
                    "dialogue_hook": "elder_public_reaction",
                },
                {
                    "id": "former_guard",
                    "name": f"{town} Former Guard",
                    "role": "former_guard",
                    "reaction": (
                        "defensive"
                        if self.guards_defeated >= 4
                        else "watchful"
                    ),
                    "dialogue_hook": "former_guard_reaction",
                },
                {
                    "id": "market_worker",
                    "name": f"{town} Market Worker",
                    "role": "worker",
                    "reaction": base_reaction,
                    "dialogue_hook": "worker_public_reaction",
                },
            )

        return (
            {
                "id": "child_runner",
                "name": f"{town} Runner",
                "role": "runner",
                "reaction": base_reaction,
                "dialogue_hook": "street_reaction",
            },
            {
                "id": "old_witness",
                "name": f"{town} Witness",
                "role": "witness",
                "reaction": (
                    "afraid"
                    if rule == "feared"
                    else "measuring"
                ),
                "dialogue_hook": "witness_reaction",
            },
            {
                "id": "street_vendor",
                "name": f"{town} Street Vendor",
                "role": "vendor",
                "reaction": base_reaction,
                "dialogue_hook": "street_vendor_reaction",
            },
        )

    def crown_visit_location(
        self,
        town_id: str,
        location_id: str,
    ) -> dict:
        town = self._normalize_crown_town(town_id)
        location = self._normalize_crown_location(location_id)
        profile = self.crown_rule_profile()

        narrative = self._crown_location_narration(
            town,
            location,
            profile,
        )

        npcs = self._crown_npcs_for_location(
            town,
            location,
            profile,
        )

        packet = {
            "outcome": "crown_location",
            "stage": "crown_loop",
            "town": town,
            "location": location,
            "location_label": self._crown_location_label(location),
            "narrative": narrative,
            "ending": narrative,
            "npcs": npcs,
            "crown_profile": profile,
            "llm_ready": True,
            "llm_context": {
                "mode": "crown_loop_location",
                "town": town,
                "location": location,
                "ruler_profile": profile,
                "available_npcs": npcs,
            },
        }

        self.last_action_note = narrative
        return packet

    def crown_npc_interaction(
        self,
        town_id: str,
        location_id: str,
        npc_id: str,
        action: str,
    ) -> dict:
        town = self._normalize_crown_town(town_id)
        location = self._normalize_crown_location(location_id)
        action_key = (
            action
            .strip()
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )

        if action_key not in {"greet", "open_dialogue"}:
            raise ValueError(
                "Unknown crown-loop NPC action: "
                f"{action!r}"
            )

        location_packet = self.crown_visit_location(
            town,
            location,
        )

        npcs = location_packet["npcs"]
        npc = None

        for candidate in npcs:
            if candidate["id"] == npc_id:
                npc = candidate
                break

        if npc is None:
            raise ValueError(
                "Unknown crown-loop NPC: "
                f"{npc_id!r}"
            )

        profile = location_packet["crown_profile"]
        rule = profile["rule"]

        if action_key == "greet":
            if rule == "feared":
                narrative = (
                    f"You greet {npc['name']}. They answer with the exact "
                    "respect a dangerous crown demands, not the warmth a good "
                    "king earns."
                )
            elif rule == "trusted":
                narrative = (
                    f"You greet {npc['name']}. They answer carefully, but there "
                    "is room in their voice for the idea that this crown may "
                    "be different."
                )
            else:
                narrative = (
                    f"You greet {npc['name']}. They answer without disrespect, "
                    "but the silence around the words carries the real question."
                )
        else:
            narrative = (
                f"Dialogue hook opened for {npc['name']}. "
                "The future LLM bridge should generate this conversation from "
                "the crown profile, town memory, NPC role, and how the player "
                "took the throne."
            )

        packet = {
            "outcome": "crown_npc_interaction",
            "stage": "crown_loop",
            "town": town,
            "location": location,
            "location_label": location_packet["location_label"],
            "npc": npc,
            "action": action_key,
            "narrative": narrative,
            "ending": narrative,
            "crown_profile": profile,
            "llm_ready": action_key == "open_dialogue",
            "llm_context": {
                "mode": "crown_loop_npc_dialogue",
                "town": town,
                "location": location,
                "npc": npc,
                "action": action_key,
                "ruler_profile": profile,
                "world_numbers": {
                    "followers": self.followers,
                    "food": self.food,
                    "gold": self.gold,
                    "weapon_caches": self.weapons,
                    "armor": self.armor,
                    "heat": self.heat,
                    "guards_defeated": self.guards_defeated,
                    "king_control": self.king_control,
                },
                "instruction": (
                    "Generate NPC dialogue that reacts to how the player became king. "
                    "Do not treat spoken claims as automatic truth."
                ),
            },
        }

        self.last_action_note = narrative
        return packet

from .opponent_ai import (
    install_layered_feint as _install_layered_feint,
)

_install_layered_feint(GhostRevolutionRun)

def main() -> None:
    """
    Run the terminal adapter without placing UI logic in the runtime.
    """

    from .presentation import run_presentation

    run_presentation()


if __name__ == "__main__":
    main()
