"""
Ghost relationship proof demo.

This demo compares Ghost's emotional inertia model against a simple
linear baseline.

Run with:
    ghost-demo

Or:
    python -m ghost.examples.relationship_proof_demo
"""

from ghost.engine import GhostEngine


ACTOR = "player"
TARGET = "villager"


SEQUENCE = [
    "help",
    "help",
    "insult",
    "help",
    "insult",
    "betrayal",
    "help",
]


BASELINE_DELTAS = {
    "help": 0.30,
    "insult": -0.35,
    "betrayal": -1.00,
}


def clamp(value, low, high):
    return max(low, min(high, value))


def baseline_step(value, event):
    """
    Simple linear smoothing baseline.

    This intentionally does not store separate positive and negative
    reservoirs. It mostly reacts to the latest value and drifts quickly.
    """
    delta = BASELINE_DELTAS[event]

    value = (value * 0.80) + (delta * 0.20)

    return clamp(value, -1.0, 1.0)


def trigger_label(trigger):
    if not trigger:
        return None

    return trigger.get("event")


def main():
    ghost = GhostEngine()
    baseline = 0.0

    print()
    print("=== GHOST vs LINEAR BASELINE ===")
    print()
    print("Both systems receive the same events.")
    print()
    print("The baseline is a simple smoothed trust score.")
    print("Ghost uses persistent positive/negative emotional reservoirs.")
    print()
    print("Step | Event     | Baseline  | Ghost     | State")
    print("-" * 70)

    for step, event in enumerate(SEQUENCE):
        baseline = baseline_step(baseline, event)

        ghost.apply_event(ACTOR, TARGET, event)
        rel = ghost.get_relationship(ACTOR, TARGET)

        ghost_trust = rel["trust"]
        state = rel["state"]
        transition = rel["transition"]
        trigger = trigger_label(rel["trigger"])

        print(
            f"{step:<4} | "
            f"{event:<9} | "
            f"{baseline:<9.3f} | "
            f"{ghost_trust:<9.3f} | "
            f"{state}"
        )

        if transition:
            before, after = transition
            print(f"      ↔ State change: {before} → {after}")

        if trigger == "forgiveness":
            print("      ✓ Forgiveness triggered")

        if trigger == "relationship_broken":
            print("      ⚠ Relationship broken")

        final_rel = ghost.get_relationship(ACTOR, TARGET)

    print()
    print("--- GAMEPLAY SIMULATION ---")

    if final_rel["state"] == "hostile":
        print("Villager: 'I will never trust you again.'")
        print("→ NPC refuses quests.")
    elif final_rel["state"] == "friendly":
        print("Villager: 'You have earned my trust.'")
        print("→ NPC offers help.")
    else:
        print("Villager: 'I am not sure what to think of you.'")
        print("→ NPC remains cautious.")

    print()
    print("--- INTERPRETATION ---")
    print("Baseline: Gradually smooths back toward neutral.")
    print("Ghost: Retains emotional memory after betrayal.")
    print("Result: Persistent emotional inertia.")

    print()
    print("=== FINAL RESULT ===")

    if final_rel["state"] == "hostile" and baseline > final_rel["trust"]:
        print("Ghost retained stronger negative state.")
        print("Baseline normalized more quickly.")
        print("✔ Emotional inertia confirmed.")
    else:
        print("Ghost and baseline diverged, but review thresholds if needed.")

    print()


if __name__ == "__main__":
    main()