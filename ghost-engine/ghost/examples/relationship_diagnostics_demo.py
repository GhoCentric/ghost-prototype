from ghost.engine import GhostEngine


def line():
    print("-" * 64)


def show_relationship(label, rel):
    print(label)
    print(f"trust:      {rel['trust']:.3f}")
    print(f"state:      {rel['state']}")
    print(f"transition: {rel['transition']}")
    print(f"trigger:    {rel['trigger']}")
    print()


def show_diagnostics(d):
    print("Diagnostics:")
    print(f"event:                {d['event']}")
    print(f"channel:              {d['channel']}")
    print(f"from_state:           {d['from_state']}")
    print(f"to_state:             {d['to_state']}")
    print(f"trust_before:         {d['trust_before']:.3f}")
    print(f"trust_after:          {d['trust_after']:.3f}")
    print(f"delta:                {d['delta']:.3f}")
    print(f"abs_delta:            {d['abs_delta']:.3f}")
    print(f"direction:            {d['direction']}")
    print(f"severity:             {d['severity']:.3f}")
    print(f"pressure:             {d['pressure']}")
    print(f"base_amount:          {d['base_amount']:.3f}")
    print(f"effective_gain:       {d['effective_gain']:.3f}")
    print(f"maturity:             {d['maturity']:.3f}")
    print(f"maturity_modifier:    {d['maturity_modifier']:.3f}")
    print(f"volatility:           {d['volatility']:.2f}")
    print(f"positive_volatility:  {d['positive_volatility']:.2f}")
    print(f"negative_volatility:  {d['negative_volatility']:.2f}")
    print()


def explain(d):
    print("Meaning:")

    if d["pressure"] == "relationship_broken":
        print("The event caused a major negative shift.")
        print("The relationship crossed into hostile state.")
        print("Ghost generated a relationship_broken trigger.")

    elif d["direction"] == "positive":
        print("The event improved the relationship.")
        print("Ghost measured a positive trust delta.")

    elif d["direction"] == "negative":
        print("The event damaged the relationship.")
        print("Ghost measured a negative trust delta.")

    else:
        print("The relationship remained stable.")

    print()


def main():
    print()
    print("=== GHOST RELATIONSHIP DIAGNOSTICS DEMO ===")
    print()
    print("Ghost does not only expose the final state.")
    print("Ghost can also explain what changed,")
    print("how hard it changed, and why.")
    print()

    line()
    print("SCENARIO 1: short relationship breaks")
    line()
    print("player helps npc twice, then betrays them")
    print()

    g = GhostEngine()

    g.apply_event("player", "npc", "help")
    before = g.apply_event("player", "npc", "help")
    after = g.apply_event("player", "npc", "betrayal")

    show_relationship("Before betrayal:", before)
    show_relationship("After betrayal:", after)

    diagnostics = after["diagnostics"]
    show_diagnostics(diagnostics)
    explain(diagnostics)

    line()
    print("SCENARIO 2: long relationship absorbs betrayal")
    line()
    print("player helps npc twenty times, then betrays them")
    print()

    g = GhostEngine()

    for _ in range(20):
        before = g.apply_event("player", "npc", "help")

    after = g.apply_event("player", "npc", "betrayal")

    show_relationship("Before betrayal:", before)
    show_relationship("After betrayal:", after)

    diagnostics = after["diagnostics"]
    show_diagnostics(diagnostics)

    print("Meaning:")
    print("The same betrayal happened again.")
    print("But the relationship had more maturity and history.")
    print("The trust delta was still negative,")
    print("but the relationship did not fully break.")
    print()

    line()
    print("SCENARIO 3: volatile personality")
    line()
    print("same event sequence, but with volatile tuning")
    print()

    g = GhostEngine()
    g.relationships.set_personality("player", "npc", "volatile")

    for _ in range(10):
        before = g.apply_event("player", "npc", "help")

    after = g.apply_event("player", "npc", "betrayal")

    show_relationship("Before betrayal:", before)
    show_relationship("After betrayal:", after)

    diagnostics = after["diagnostics"]
    show_diagnostics(diagnostics)

    print("Meaning:")
    print("The volatile profile has stronger positive")
    print("and negative volatility values.")
    print("Ghost exposes those values in diagnostics,")
    print("so external systems can understand why")
    print("the trust swing was so large.")
    print()

    print("✔ Ghost relationship diagnostics demo complete.")


if __name__ == "__main__":
    main()
