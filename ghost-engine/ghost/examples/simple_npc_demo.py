"""
Deterministic NPC mapping demo using ghost-engine.

This demo shows how a small NPC behavior layer can consume Ghost's
public API over 10 ticks.

It demonstrates:

- GhostEngine.step()
- GhostEngine.apply_event()
- GhostEngine.tick()
- GhostEngine.get_relationship()
- deterministic NPC behavior mapping
- threat state + relationship state working together

Run with:
    ghost-npc-demo

Or:
    python -m ghost.examples.simple_npc_demo
"""

from ghost.engine import GhostEngine


ACTOR = "player"
TARGET = "gatekeeper"


SCRIPTED_TICKS = [
    {
        "label": "Player approaches calmly.",
        "intent": "greet",
        "relationship_event": "greet",
        "intensity": 0.2,
    },
    {
        "label": "Player helps carry supplies.",
        "intent": "help",
        "relationship_event": "help",
        "intensity": 0.4,
    },
    {
        "label": "Time passes with no new pressure.",
        "intent": None,
        "relationship_event": "tick",
        "intensity": 0.0,
    },
    {
        "label": "Player insults the guard.",
        "intent": "threat",
        "relationship_event": "insult",
        "intensity": 0.4,
    },
    {
        "label": "Player threatens the guard.",
        "intent": "threat",
        "relationship_event": "threat",
        "intensity": 0.7,
    },
    {
        "label": "Player attacks the guard.",
        "intent": "threat",
        "relationship_event": "attack",
        "intensity": 0.9,
    },
    {
        "label": "Player tries to help afterward.",
        "intent": "help",
        "relationship_event": "help",
        "intensity": 0.3,
    },
    {
        "label": "Time passes after conflict.",
        "intent": None,
        "relationship_event": "tick",
        "intensity": 0.0,
    },
    {
        "label": "Player apologizes.",
        "intent": "help",
        "relationship_event": "apologize",
        "intensity": 0.2,
    },
    {
        "label": "Final quiet tick.",
        "intent": None,
        "relationship_event": "tick",
        "intensity": 0.0,
    },
]


class GatekeeperNPC:
    def __init__(self, name):
        self.name = name
        self.behavior = "idle"

    def update_behavior(self, threat, relationship_state, trust):
        if relationship_state == "hostile":
            self.behavior = "refuse"
            return

        if threat >= 1.0:
            self.behavior = "block"
            return

        if threat >= 0.5:
            self.behavior = "warn"
            return

        if relationship_state == "friendly":
            self.behavior = "help"
            return

        if trust < -0.25:
            self.behavior = "watch"
            return

        self.behavior = "idle"

    def dialogue(self):
        lines = {
            "idle": "Gatekeeper: \"Move along.\"",
            "help": "Gatekeeper: \"You have been helpful.\"",
            "watch": "Gatekeeper: \"I am watching you.\"",
            "warn": "Gatekeeper: \"Careful. No more trouble.\"",
            "block": "Gatekeeper: \"That is far enough.\"",
            "refuse": "Gatekeeper: \"No. I remember.\"",
        }

        return lines.get(self.behavior, "Gatekeeper says nothing.")


def trigger_label(trigger):
    if not trigger:
        return "-"

    event = trigger.get("event", "-")

    labels = {
        "relationship_broken": "broken",
        "forgiveness": "forgive",
        "deescalation": "deesc",
        "state_shift": "shift",
    }

    return labels.get(event, event)


def make_step_event(tick):
    intent = tick["intent"]

    if intent is None:
        return None

    return {
        "source": "npc_demo",
        "intent": intent,
        "actor": ACTOR,
        "target": TARGET,
        "intensity": tick["intensity"],
    }


def apply_relationship_event(engine, event):
    if event == "tick":
        engine.tick()
    else:
        engine.apply_event(ACTOR, TARGET, event)


def main():
    engine = GhostEngine()
    npc = GatekeeperNPC("Gatekeeper")

    print()
    print("=== GHOST NPC API MAPPING DEMO ===")
    print()
    print("This demo runs a deterministic 10-tick NPC sequence.")
    print()
    print("It uses Ghost's public API:")
    print()
    print("  engine.step(...)")
    print("  engine.apply_event(a, b, event)")
    print("  engine.tick()")
    print("  engine.get_relationship(a, b)")
    print()
    print("The NPC behavior is a small external mapping layer.")
    print("Ghost exposes state. The NPC code decides how to respond.")
    print()

    print("Tick | Threat | Trust  | Rel      | Trig    | NPC")
    print("---------------------------------------------------")

    for index, tick in enumerate(SCRIPTED_TICKS):
        step_event = make_step_event(tick)

        if step_event is None:
            engine.step()
        else:
            engine.step(step_event)

        apply_relationship_event(engine, tick["relationship_event"])

        state = engine.state()
        threat = state["npc"]["threat_level"]
        rel = engine.get_relationship(ACTOR, TARGET)

        trust = rel["trust"]
        relationship_state = rel["state"]
        trigger = trigger_label(rel["trigger"])

        npc.update_behavior(threat, relationship_state, trust)

        print(
            f"{index:<4} | "
            f"{threat:>6.2f} | "
            f"{trust:>6.3f} | "
            f"{relationship_state:<8} | "
            f"{trigger:<7} | "
            f"{npc.behavior}"
        )

        print(f"     {tick['label']}")
        print(f"     {npc.dialogue()}")
        print()

    final_rel = engine.get_relationship(ACTOR, TARGET)
    final_threat = engine.state()["npc"]["threat_level"]

    print("--- FINAL STATE ---")
    print()
    print(f"Threat level:        {final_threat:.2f}")
    print(f"Relationship trust:  {final_rel['trust']:.3f}")
    print(f"Relationship state:  {final_rel['state']}")
    print(f"Final NPC behavior:  {npc.behavior}")
    print(f"Final NPC dialogue:  {npc.dialogue()}")
    print()
    print("✔ Ghost API mapping confirmed.")
    print()


if __name__ == "__main__":
    main()
