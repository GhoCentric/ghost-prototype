"""Focused visual audit for deterministic emotional spotlight hysteresis."""

import copy

from ghost.emotions import EmotionRuntime


ORDER = ("anger", "fear", "grief", "hope", "joy")


def row(label, state):
    values = state["levels"]
    vector = "  ".join(
        f"{name[:2]}={values.get(name, 0.0):.3f}"
        for name in ORDER
    )
    raw = state["raw_leader_emotion"] or "none"
    dominant = state["dominant_emotion"] or "none"
    gap = state["raw_leader_salience"] - state["dominant_salience"]
    print(
        f"{label:<18} {vector}  "
        f"raw={raw:<6} {state['raw_leader_salience']:.3f}  "
        f"spotlight={dominant:<6} {state['dominant_salience']:.3f}  "
        f"gap={gap:+.3f}"
    )


def scenario_near_tie():
    print("\nSCENARIO A — NEAR-TIE DOES NOT FLICKER")
    runtime = EmotionRuntime()
    for event in ("help", "help", "threat", "betrayal", "help"):
        runtime.apply_event("guard", event, source="player")
        row(event, runtime.get_state("guard"))

    packet = runtime.apply_event("guard", "apology", source="player")
    row("apology", runtime.get_state("guard"))
    transition = packet["spotlight_transition"]
    print(
        "  decision:",
        transition["switch_reason"],
        f"margin={transition['spotlight_switch_margin']:.3f}",
    )

    tick = runtime.tick("guard")
    row("tick 1", runtime.get_state("guard"))
    transition = tick["agents"][0]["spotlight_transition"]
    print(
        "  decision:",
        transition["switch_reason"],
        f"{transition['previous_spotlight']} -> {transition['resolved_spotlight']}",
    )


def scenario_margin_profiles():
    print("\nSCENARIO B — SAME SALIENCE, DIFFERENT SWITCH MARGIN")
    for label, margin in (("zero margin", 0.00), ("default", 0.05), ("sticky", 0.10)):
        runtime = EmotionRuntime()
        runtime.register_agent(
            "guard",
            initial={"anger": 0.60, "hope": 0.50},
            spotlight_switch_margin=margin,
        )
        runtime.register_agent(
            "guard",
            initial={"anger": 0.55, "hope": 0.59},
        )
        current = runtime.get_state("guard")
        print(
            f"{label:<12} margin={margin:.2f}  "
            f"raw={current['raw_leader_emotion']:<5}  "
            f"spotlight={current['dominant_emotion']:<5}"
        )


def scenario_snapshot():
    print("\nSCENARIO C — SNAPSHOT / RESTORE ACROSS HANDOFF")
    runtime = EmotionRuntime()
    for event in ("help", "help", "threat", "betrayal", "help", "apology"):
        runtime.apply_event("guard", event)
    snapshot = runtime.snapshot()
    a = EmotionRuntime.from_snapshot(copy.deepcopy(snapshot))
    b = EmotionRuntime.from_snapshot(copy.deepcopy(snapshot))
    for _ in range(4):
        a.tick("guard")
        b.tick("guard")
    print("identical continuation:", a.snapshot() == b.snapshot())
    row("continued", a.get_state("guard"))


def main():
    print("GHOST SPOTLIGHT HYSTERESIS TORTURE DEMO")
    print("=======================================")
    print("No RNG. No LLM. A 0.05 default margin prevents near-tie attention flicker.")
    scenario_near_tie()
    scenario_margin_profiles()
    scenario_snapshot()


if __name__ == "__main__":
    main()
