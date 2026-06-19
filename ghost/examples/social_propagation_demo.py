from ghost.engine import GhostEngine


def line():
    print("-" * 64)


def show_direct(packet):
    direct = packet["direct"]
    d = direct["diagnostics"]

    print("Direct relationship:")
    print(f"target state:     {direct['state']}")
    print(f"target trust:     {direct['trust']:.3f}")
    print(f"transition:       {direct['transition']}")
    print(f"trigger:          {direct['trigger']}")
    print(f"pressure:         {packet['pressure']}")
    print(f"severity:         {packet['severity']:.3f}")
    print(f"heat:             {packet['heat']:.3f}")
    print(f"near_break:       {d['near_break']}")
    print()


def show_propagated(packet):
    print("Propagated observer effects:")

    for item in packet["propagated"]:
        rel = item["relationship"]
        d = rel["diagnostics"]

        print()
        print(f"observer:         {item['affected']}")
        print(f"source pressure:  {item['source_pressure']}")
        print(f"trust_delta:      {item['trust_delta']:.3f}")
        print(f"observer trust:   {rel['trust']:.3f}")
        print(f"observer state:   {rel['state']}")
        print(f"observer pressure:{d['pressure']}")

    print()


def show_world_effects(packet):
    effects = packet["world_effects"]

    print("World-effect packet:")
    print(f"pressure_delta:        {effects['pressure_delta']:.3f}")
    print(f"fear_delta:            {effects['fear_delta']:.3f}")
    print(f"resentment_delta:      {effects['resentment_delta']:.3f}")
    print(f"order_delta:           {effects['order_delta']:.3f}")
    print(f"guard_suspicion_delta: {effects['guard_suspicion_delta']:.3f}")
    print()


def scenario_full_break():
    line()
    print("SCENARIO 1: full relationship break")
    line()
    print("player betrays shopkeeper with no positive history")
    print()

    g = GhostEngine()

    packet = g.propagate_social_event(
        source="player",
        target="shopkeeper",
        event="betrayal",
        observers=["guard", "elder", "rival"],
        weights={
            "guard": 1.0,
            "elder": 0.7,
            "rival": 0.25,
        },
    )

    show_direct(packet)
    show_propagated(packet)
    show_world_effects(packet)

    print("Meaning:")
    print("The shopkeeper relationship fully broke.")
    print("The guard, elder, and rival all received secondary effects.")
    print("The guard reacted strongest because the guard had the highest weight.")
    print()


def scenario_near_break():
    line()
    print("SCENARIO 2: near-break strained neutral")
    line()
    print("player has mixed history, then betrays shopkeeper")
    print()

    g = GhostEngine()

    sequence = [
        "greet",
        "help",
        "help",
        "insult",
        "apologize",
        "gift",
        "threat",
        "help",
    ]

    for event in sequence:
        g.apply_event("player", "shopkeeper", event)

    packet = g.propagate_social_event(
        source="player",
        target="shopkeeper",
        event="betrayal",
        observers=["guard", "elder", "rival"],
        weights={
            "guard": 1.0,
            "elder": 0.7,
            "rival": 0.25,
        },
    )

    show_direct(packet)
    show_propagated(packet)
    show_world_effects(packet)

    print("Meaning:")
    print("The relationship did not fully break.")
    print("But Ghost identified the state as near_break.")
    print("This means neutral, but barely restrained.")
    print("Social systems can react before full hostility.")
    print()


def scenario_weighted_observers():
    line()
    print("SCENARIO 3: weighted observer propagation")
    line()
    print("same betrayal, but observers have different social weights")
    print()

    g = GhostEngine()

    packet = g.propagate_social_event(
        source="player",
        target="shopkeeper",
        event="betrayal",
        observers=[
            "guard",
            "shopkeeper_friend",
            "distant_bystander",
        ],
        weights={
            "guard": 1.0,
            "shopkeeper_friend": 0.8,
            "distant_bystander": 0.15,
        },
    )

    show_direct(packet)
    show_propagated(packet)
    show_world_effects(packet)

    print("Meaning:")
    print("Social propagation is not random.")
    print("Each observer receives a bounded effect based on weight.")
    print("Closer or more relevant NPCs react more strongly.")
    print()


def main():
    print()
    print("=== GHOST SOCIAL PROPAGATION DEMO ===")
    print()
    print("Ghost now supports deterministic NPC-to-NPC influence.")
    print()
    print("A direct relationship event can create:")
    print("- direct relationship change")
    print("- diagnostic pressure")
    print("- social heat")
    print("- observer relationship effects")
    print("- world-effect packets")
    print()

    scenario_full_break()
    scenario_near_break()
    scenario_weighted_observers()

    print("✔ Ghost social propagation demo complete.")


if __name__ == "__main__":
    main()
