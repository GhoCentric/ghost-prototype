"""Durable town-level political memory for Ghost Revolution."""

from __future__ import annotations

from types import MappingProxyType


class TownMemory:
    """
    Own durable public memory that survives relationship recovery.

    Ghost still owns social state. TownMemory owns the separate
    political scar left by witnessed public executions.
    """

    _EXECUTION_MEMORY_DAYS = MappingProxyType(
        {
            "accepted": 0,
            "uncertain": 2,
            "rejected": 3,
        }
    )

    def __init__(self, town_ids):
        normalized_town_ids = tuple(
            self._normalize_town_id(town_id)
            for town_id in town_ids
        )

        if not normalized_town_ids:
            raise ValueError(
                "town memory needs at least one town"
            )

        if len(set(normalized_town_ids)) != len(
            normalized_town_ids
        ):
            raise ValueError(
                "town ids must be unique"
            )

        self._town_ids = normalized_town_ids
        self._remaining = {
            town_id: 0
            for town_id in self._town_ids
        }

    @staticmethod
    def _normalize_town_id(town_id) -> str:
        if not isinstance(town_id, str):
            raise ValueError(
                "town id must be a string"
            )

        normalized = town_id.strip()

        if not normalized:
            raise ValueError(
                "town id must not be empty"
            )

        return normalized

    def _known_town(self, town_id) -> str:
        normalized = self._normalize_town_id(town_id)

        if normalized not in self._remaining:
            raise ValueError(
                f"unknown town id: {normalized}"
            )

        return normalized

    @classmethod
    def _normalize_response(cls, public_response) -> str:
        if not isinstance(public_response, str):
            raise ValueError(
                "execution response must be a string"
            )

        normalized = public_response.strip()

        if not normalized:
            raise ValueError(
                "execution response must not be empty"
            )

        if normalized not in cls._EXECUTION_MEMORY_DAYS:
            raise ValueError(
                "unknown execution response: "
                f"{normalized}"
            )

        return normalized

    def remaining(self, town_id) -> int:
        town_id = self._known_town(town_id)

        return self._remaining[town_id]

    def record_execution(
        self,
        town_id,
        public_response,
    ) -> int:
        town_id = self._known_town(town_id)

        public_response = self._normalize_response(
            public_response
        )

        duration = self._EXECUTION_MEMORY_DAYS[
            public_response
        ]

        self._remaining[town_id] = max(
            self._remaining[town_id],
            duration,
        )

        return self._remaining[town_id]

    def label(self, town_id) -> str:
        remaining = self.remaining(town_id)

        if remaining <= 0:
            return "none"

        if remaining == 1:
            return "Execution remembered (fading)"

        return (
            f"Execution remembered ({remaining} days)"
        )

    def advance_day(self) -> dict[str, int]:
        """
        Decay durable execution memory by one day.

        Returns fear-floor effects for the facade to apply to towns.
        """
        fear_floors = {}

        for town_id in self._town_ids:
            remaining = self._remaining[town_id]

            if remaining <= 0:
                continue

            fear_floors[town_id] = (
                2 if remaining >= 2 else 1
            )

            self._remaining[town_id] = remaining - 1

        return fear_floors

    def snapshot(self) -> dict:
        """Return a copy-safe public state view."""
        return {
            "execution_memory": dict(self._remaining),
        }

    @classmethod
    def from_snapshot(
        cls,
        town_ids,
        snapshot: dict,
    ) -> "TownMemory":
        """Restore durable town memory from snapshot() output."""
        if not isinstance(snapshot, dict):
            raise ValueError(
                "town memory snapshot must be a dict"
            )

        if set(snapshot) != {"execution_memory"}:
            raise ValueError(
                "town memory snapshot has unsupported keys"
            )

        remaining = snapshot["execution_memory"]

        if not isinstance(remaining, dict):
            raise ValueError(
                "town memory execution memory must be a dict"
            )

        memory = cls(town_ids)

        if set(remaining) != set(memory._town_ids):
            raise ValueError(
                "town memory snapshot towns are invalid"
            )

        restored = {}

        for town_id in memory._town_ids:
            value = remaining[town_id]

            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise ValueError(
                    "town memory value must be a non-negative integer"
                )

            restored[town_id] = value

        memory._remaining = restored

        return memory

