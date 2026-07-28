"""
World / Society runtime for Ghost.

This is explicit state.
Nothing is stored implicitly.
Callers choose when to record events or apply world effects.
"""

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any

from .validation import validate_finite_number, validate_unit_interval


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _effect_value(
    effects: dict[str, Any],
    key: str,
) -> float:
    return validate_finite_number(
        effects.get(
            key,
            0.0,
        ),
        f"world effect {key}",
    )


def _validated_effect_values(
    effects: dict[str, Any],
    keys: tuple[str, ...],
) -> dict[str, float]:
    if not isinstance(
        effects,
        dict,
    ):
        raise ValueError(
            "world effects must be a dict"
        )

    return {
        key: _effect_value(
            effects,
            key,
        )
        for key in keys
    }


_WORLD_SNAPSHOT_KEYS = {
    "events",
    "global_pressure",
    "mood",
    "status",
}


_WORLD_MOOD_KEYS = {
    "commerce",
    "fear",
    "order",
    "resentment",
}


_WORLD_EVENT_KEYS = {
    "actor",
    "details",
    "target",
    "type",
}


def _world_snapshot_json_value(
    value,
    label: str,
):
    if value is None:
        return

    if isinstance(
        value,
        (
            str,
            bool,
            int,
        ),
    ):
        return

    if isinstance(value, float):
        validate_finite_number(
            value,
            label,
        )

        return

    if isinstance(value, list):
        for index, item in enumerate(value):
            _world_snapshot_json_value(
                item,
                f"{label}[{index}]",
            )

        return

    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(
                    f"{label} keys must be strings"
                )

            _world_snapshot_json_value(
                item,
                f"{label}.{key}",
            )

        return

    raise ValueError(
        f"{label} must be JSON-safe"
    )


def _world_snapshot_optional_text(
    value,
    label: str,
):
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError(
            f"{label} must be a string or None"
        )

    return value.strip()


def _world_status_from_pressure(
    pressure: float,
) -> str:
    if pressure >= 2.0:
        return "crisis"

    if pressure >= 1.0:
        return "tense"

    return "normal"


@dataclass
class TownMood:
    fear: float = 0.0
    order: float = 0.5
    commerce: float = 1.0
    resentment: float = 0.0

    def apply(
        self,
        effects: dict[str, Any],
    ):
        values = _validated_effect_values(
            effects,
            (
                "fear_delta",
                "order_delta",
                "commerce_delta",
                "resentment_delta",
            ),
        )

        fear = clamp(
            self.fear
            + values["fear_delta"],
            0.0,
            1.0,
        )

        order = clamp(
            self.order
            + values["order_delta"],
            0.0,
            1.0,
        )

        commerce = clamp(
            self.commerce
            + values["commerce_delta"],
            0.0,
            1.0,
        )

        resentment = clamp(
            self.resentment
            + values["resentment_delta"],
            0.0,
            1.0,
        )

        self.fear = fear
        self.order = order
        self.commerce = commerce
        self.resentment = resentment

    def tick(self):
        self.fear = clamp(self.fear * 0.97, 0.0, 1.0)
        self.resentment = clamp(self.resentment * 0.98, 0.0, 1.0)

        if self.order < 0.5:
            self.order = clamp(self.order + 0.01, 0.0, 1.0)

        if self.commerce < 1.0:
            self.commerce = clamp(self.commerce + 0.01, 0.0, 1.0)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WorldRuntime:
    mood: TownMood = field(default_factory=TownMood)
    events: list[dict[str, Any]] = field(default_factory=list)
    global_pressure: float = 0.0
    status: str = "normal"

    def record_event(
        self,
        event_type: str,
        actor: str = "",
        target: str = "",
        details: dict[str, Any] | None = None,
    ) -> dict:
        event = {
            "type": str(event_type),
            "actor": str(actor),
            "target": str(target),
            "details": (
                deepcopy(details)
                if details is not None
                else {}
            ),
        }

        self.events.append(event)

        if len(self.events) > 25:
            self.events.pop(0)

        return deepcopy(event)

    def apply_effects(
        self,
        effects: dict[str, Any],
    ):
        values = _validated_effect_values(
            effects,
            (
                "pressure_delta",
                "fear_delta",
                "order_delta",
                "commerce_delta",
                "resentment_delta",
            ),
        )

        global_pressure = clamp(
            self.global_pressure
            + values["pressure_delta"],
            0.0,
            5.0,
        )

        fear = clamp(
            self.mood.fear
            + values["fear_delta"],
            0.0,
            1.0,
        )

        order = clamp(
            self.mood.order
            + values["order_delta"],
            0.0,
            1.0,
        )

        commerce = clamp(
            self.mood.commerce
            + values["commerce_delta"],
            0.0,
            1.0,
        )

        resentment = clamp(
            self.mood.resentment
            + values["resentment_delta"],
            0.0,
            1.0,
        )

        status = _world_status_from_pressure(
            global_pressure
        )

        self.global_pressure = (
            global_pressure
        )

        self.mood.fear = fear
        self.mood.order = order
        self.mood.commerce = commerce
        self.mood.resentment = resentment
        self.status = status

    def tick(self):
        self.global_pressure = clamp(
            self.global_pressure * 0.98,
            0.0,
            5.0,
        )

        self.mood.tick()

        self.status = (
            _world_status_from_pressure(
                self.global_pressure
            )
        )

    def propagate_social_effect(
        self,
        source_event: str,
        faction_heat: float = 0.0,
    ) -> dict:
        heat = validate_unit_interval(
            faction_heat,
            "faction heat",
        )

        effects = {
            "pressure_delta": 0.10 * heat,
            "fear_delta": 0.04 * heat,
            "resentment_delta": 0.04 * heat,
            "order_delta": -0.02 * heat,
        }

        self.apply_effects(effects)

        self.record_event(
            "social_propagation",
            details={
                "source_event": str(source_event),
                "heat": heat,
                "effects": effects,
            },
        )

        return effects

    @classmethod
    def from_dict(
        cls,
        payload: dict,
    ) -> "WorldRuntime":
        """
        Restore a validated WorldRuntime snapshot.

        Missing legacy mood fields retain their historical defaults.
        Unknown fields, malformed events, and contradictory status
        values are rejected.
        """
        if not isinstance(payload, dict):
            raise ValueError(
                "world snapshot must be a dict"
            )

        unknown = (
            set(payload)
            - _WORLD_SNAPSHOT_KEYS
        )

        if unknown:
            raise ValueError(
                "world snapshot has unsupported keys: "
                + ", ".join(sorted(unknown))
            )

        _world_snapshot_json_value(
            payload,
            "world snapshot",
        )

        mood_payload = payload.get(
            "mood",
            {},
        )

        if not isinstance(
            mood_payload,
            dict,
        ):
            raise ValueError(
                "world snapshot mood must be a dict"
            )

        unknown_mood = (
            set(mood_payload)
            - _WORLD_MOOD_KEYS
        )

        if unknown_mood:
            raise ValueError(
                "world snapshot mood has unsupported keys: "
                + ", ".join(
                    sorted(unknown_mood)
                )
            )

        events = payload.get(
            "events",
            [],
        )

        if not isinstance(events, list):
            raise ValueError(
                "world snapshot events must be a list"
            )

        if not all(
            isinstance(event, dict)
            for event in events
        ):
            raise ValueError(
                "world snapshot events must "
                "contain only dicts"
            )

        if len(events) > 25:
            raise ValueError(
                "world snapshot events cannot "
                "contain more than 25 entries"
            )

        validated_events = []

        for index, event in enumerate(events):
            unknown_event = (
                set(event)
                - _WORLD_EVENT_KEYS
            )

            if unknown_event:
                raise ValueError(
                    "world snapshot event "
                    f"{index} has unsupported keys: "
                    + ", ".join(
                        sorted(unknown_event)
                    )
                )

            event_type = event.get(
                "type"
            )

            if (
                not isinstance(event_type, str)
                or not event_type.strip()
            ):
                raise ValueError(
                    "world snapshot event type "
                    "must be a non-empty string"
                )

            actor = (
                _world_snapshot_optional_text(
                    event.get("actor"),
                    (
                        "world snapshot event "
                        f"{index} actor"
                    ),
                )
            )

            target = (
                _world_snapshot_optional_text(
                    event.get("target"),
                    (
                        "world snapshot event "
                        f"{index} target"
                    ),
                )
            )

            details = event.get(
                "details",
                {},
            )

            if not isinstance(details, dict):
                raise ValueError(
                    "world snapshot event details "
                    "must be a dict"
                )

            validated_events.append(
                {
                    "type": event_type.strip(),
                    "actor": actor or "",
                    "target": target or "",
                    "details": deepcopy(
                        details
                    ),
                }
            )

        mood = TownMood(
            fear=validate_unit_interval(
                mood_payload.get(
                    "fear",
                    0.0,
                ),
                "world snapshot mood fear",
            ),
            order=validate_unit_interval(
                mood_payload.get(
                    "order",
                    0.5,
                ),
                "world snapshot mood order",
            ),
            commerce=validate_unit_interval(
                mood_payload.get(
                    "commerce",
                    1.0,
                ),
                "world snapshot mood commerce",
            ),
            resentment=validate_unit_interval(
                mood_payload.get(
                    "resentment",
                    0.0,
                ),
                "world snapshot mood resentment",
            ),
        )

        global_pressure = (
            validate_finite_number(
                payload.get(
                    "global_pressure",
                    0.0,
                ),
                (
                    "world snapshot "
                    "global pressure"
                ),
            )
        )

        if not (
            0.0
            <= global_pressure
            <= 5.0
        ):
            raise ValueError(
                "world snapshot global pressure "
                "must be in [0.0, 5.0]"
            )

        expected_status = (
            _world_status_from_pressure(
                global_pressure
            )
        )

        return cls(
            mood=mood,
            events=deepcopy(
                validated_events
            ),
            global_pressure=(
                global_pressure
            ),
            status=expected_status,
        )

    def to_dict(self) -> dict:
        return {
            "mood": self.mood.to_dict(),
            "events": deepcopy(self.events),
            "global_pressure": self.global_pressure,
            "status": self.status,
        }
