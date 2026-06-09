"""
World / Society runtime for Ghost.

This is explicit state.
Nothing is stored implicitly.
Callers choose when to record events or apply world effects.
"""

from dataclasses import asdict, dataclass, field
from typing import Any


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class TownMood:
    fear: float = 0.0
    order: float = 0.5
    commerce: float = 1.0
    resentment: float = 0.0

    def apply(self, effects: dict[str, Any]):
        self.fear = clamp(
            self.fear + float(effects.get("fear_delta", 0.0)),
            0.0,
            1.0,
        )

        self.order = clamp(
            self.order + float(effects.get("order_delta", 0.0)),
            0.0,
            1.0,
        )

        self.commerce = clamp(
            self.commerce + float(effects.get("commerce_delta", 0.0)),
            0.0,
            1.0,
        )

        self.resentment = clamp(
            self.resentment + float(effects.get("resentment_delta", 0.0)),
            0.0,
            1.0,
        )

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
            "type": event_type,
            "actor": actor,
            "target": target,
            "details": details or {},
        }

        self.events.append(event)

        if len(self.events) > 25:
            self.events.pop(0)

        return event

    def apply_effects(self, effects: dict[str, Any]):
        self.global_pressure = clamp(
            self.global_pressure + float(effects.get("pressure_delta", 0.0)),
            0.0,
            5.0,
        )

        self.mood.apply(effects)

        if self.global_pressure >= 2.0:
            self.status = "crisis"
        elif self.global_pressure >= 1.0:
            self.status = "tense"
        else:
            self.status = "normal"

    def tick(self):
        self.global_pressure = clamp(
            self.global_pressure * 0.98,
            0.0,
            5.0,
        )

        self.mood.tick()

        if self.global_pressure >= 2.0:
            self.status = "crisis"
        elif self.global_pressure >= 1.0:
            self.status = "tense"
        else:
            self.status = "normal"

    def propagate_social_effect(
        self,
        source_event: str,
        faction_heat: float = 0.0,
    ) -> dict:
        heat = clamp(float(faction_heat), 0.0, 1.0)

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
                "source_event": source_event,
                "heat": heat,
                "effects": effects,
            },
        )

        return effects

    def to_dict(self) -> dict:
        return {
            "mood": self.mood.to_dict(),
            "events": list(self.events),
            "global_pressure": self.global_pressure,
            "status": self.status,
        }
