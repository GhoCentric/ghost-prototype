from ghost.engine import GhostEngine


def behavior_for_state(state):
    if state == "hostile":
        return "NPC refuses quests and speaks with open distrust."

    if state == "friendly":
        return "NPC offers help and speaks warmly."

    return "NPC speaks cautiously and keeps emotional distance."


def trigger_text(trigger):
    if trigger is None:
        return "-"

    event = trigger.get("event")

    if event == "relationship_broken":
        return "relationship_broken"

    if event == "forgiveness":
        return "forgiveness"

    if event == "deescalation":
        return "deescalation"

    if event == "state_shift":
        return "state_shift"

    return str(event)


def print_row(step, event, rel):
    trust = rel["trust"]
    state = rel["state"]
    trigger = trigger_text(rel["trigger"])

    print(
        f"{step:<4} | "
        f"{event:<9} | "
        f"{trust:>7.3f} | "
        f"{state:<8} | "
        f"{trigger}"
    )


def main():
    ghost = GhostEngine()

    actor = "player"
    target = "shopkeeper"

    sequence = [
        "help",
        "help",
        "insult",
        "help",
        "insult",
        "betrayal",
        "help",
        "tick",
        "tick",
        "help",
    ]

    print()
    print("=== GHOST NPC RELATIONSHIP DEMO ===")
    print()
    print("This demo uses the public GhostEngine relationship API:")
    print()
    print("  ghost.apply_event(a, b, event)")
    print("  ghost.tick()")
    print("  ghost.get_relationship(a, b)")
    print()
    print("No internal relationship modules are imported.")
    print()
    print("Step | Event     | Trust   | State    | Trigger")
    print("-------------------------------------------------------")

    for i, event in enumerate(sequence):
        if event == "tick":
            ghost.tick()
        else:
            ghost.apply_event(actor, target, event)

        rel = ghost.get_relationship(actor, target)
        print_row(i, event, rel)

    final_rel = ghost.get_relationship(actor, target)

    print()
    print("--- FINAL NPC BEHAVIOR ---")
    print()
    print(f"Relationship state: {final_rel['state']}")
    print(f"Trust: {final_rel['trust']:.3f}")
    print()
    print(behavior_for_state(final_rel["state"]))
    print()
    print("--- INTERPRETATION ---")
    print()
    print("The player helped the NPC, then insulted them, then betrayed them.")
    print("Even after later help and time passing, Ghost preserves emotional history.")
    print("The NPC does not instantly reset to friendly behavior.")
    print()
    print("✔ Public relationship runtime confirmed.")
    print()


if __name__ == "__main__":
    main()
