from dataclasses import dataclass


@dataclass
class GhostStep:
    source: str
    intent: str | None = None
    actor: str = "unknown"     # ← DEFAULT
    target: str | None = None
    intensity: float = 0.0
