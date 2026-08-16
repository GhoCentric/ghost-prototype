"""Human-readable trajectory audit for Ghost's unreleased multi-emotion layer."""

import copy
import json

from ghost import GhostAPI
from ghost.emotions import EmotionRuntime


ORDER = ("anger", "fear", "grief", "hope", "joy")


def _row(label, state):
    values = state["levels"]
    vector = "  ".join(f"{name[:2]}={values.get(name, 0.0):.3f}" for name in ORDER)
    dominant = state["dominant_emotion"] or "none"
    print(f"{label:<18} {vector}  spotlight={dominant:<6} {state['dominant_salience']:.3f}")


def _scenario_contradictions():
    print("\nSCENARIO A — CONTRADICTORY EXPERIENCE")
    runtime = EmotionRuntime()
    runtime.register_agent("guard")
    _row("start", runtime.get_state("guard"))
    for event in ("help", "help", "threat", "betrayal", "help", "apology"):
        runtime.apply_event("guard", event, source="player")
        _row(event, runtime.get_state("guard"))
    for steps in (1, 2, 4, 8):
        clone = EmotionRuntime.from_snapshot(copy.deepcopy(runtime.snapshot()))
        clone.tick("guard", steps=steps)
        _row(f"tick +{steps}", clone.get_state("guard"))


def _scenario_inertia_handoff():
    print("\nSCENARIO B — INERTIA / SPOTLIGHT HANDOFF")
    runtime = EmotionRuntime()
    runtime.apply_event("guard", "betrayal", source="player")
    _row("betrayal", runtime.get_state("guard"))
    for step in range(1, 9):
        runtime.tick("guard")
        _row(f"tick {step}", runtime.get_state("guard"))


def _scenario_personality():
    print("\nSCENARIO C — SAME EVENT, DIFFERENT SENSITIVITY")
    balanced = EmotionRuntime()
    fear_sensitive = EmotionRuntime()
    fear_sensitive.register_agent(
        "guard",
        sensitivities={"anger": 0.50, "fear": 3.00, "grief": 0.50},
    )
    for runtime in (balanced, fear_sensitive):
        runtime.apply_event("guard", "betrayal", source="player")
    _row("balanced", balanced.get_state("guard"))
    _row("fear-sensitive", fear_sensitive.get_state("guard"))


def _scenario_snapshot_continue():
    print("\nSCENARIO D — SNAPSHOT / RESTORE / CONTINUE")
    ghost = GhostAPI()
    ghost.register_emotional_agent("guard", sensitivities={"fear": 1.4, "anger": 0.8})
    ghost.apply_emotional_event("guard", "help", source="player")
    ghost.apply_emotional_event("guard", "threat", source="player")
    ghost.tick_emotions("guard", steps=2)
    snapshot = ghost.snapshot()
    a = GhostAPI.from_snapshot(copy.deepcopy(snapshot))
    b = GhostAPI.from_snapshot(copy.deepcopy(snapshot))
    for event in ("betrayal", "apology", "help"):
        a.apply_emotional_event("guard", event, source="player")
        b.apply_emotional_event("guard", event, source="player")
    a.tick_emotions("guard", steps=5)
    b.tick_emotions("guard", steps=5)
    payload_a = json.dumps(a.snapshot(), sort_keys=True, separators=(",", ":"))
    payload_b = json.dumps(b.snapshot(), sort_keys=True, separators=(",", ":"))
    print("identical continuation:", payload_a == payload_b)
    _row("continued", a.emotional_state("guard"))


def main():
    print("GHOST EMOTIONAL DYNAMICS TORTURE DEMO")
    print("====================================")
    print("No RNG. No LLM. This is a behavior audit, not a psychology claim.")
    _scenario_contradictions()
    _scenario_inertia_handoff()
    _scenario_personality()
    _scenario_snapshot_continue()


if __name__ == "__main__":
    main()
