"""
Minimal NPC simulation using ghost-engine (pip installed).

Run with:
    python npc_demo.py
"""

import time
import random
from ghost.engine import GhostEngine


# ----------------------------
# Simple NPC logic
# ----------------------------

class GuardNPC:
    def __init__(self, name):
        self.name = name
        self.alertness = "idle"

    def update_behavior(self, ghost_state):
        threat = ghost_state.get("npc", {}).get("threat_level", 0.0)

        if threat < 0.5:
            self.alertness = "idle"
        elif threat < 1.5:
            self.alertness = "alert"
        else:
            self.alertness = "hostile"

    def act(self):
        print(f"[NPC:{self.name}] Behavior → {self.alertness.upper()}")


# ----------------------------
# NPC Engine Event Generator
# ----------------------------

def generate_npc_event():
    """
    Fake NPC-engine output.
    """
    roll = random.random()

    if roll < 0.6:
        return None  # no event this tick
    elif roll < 0.85:
        return {
            "source": "npc_engine",
            "intent": "threat",
            "actor": "player",
            "intensity": random.uniform(0.2, 0.6),
        }
    else:
        return {
            "source": "npc_engine",
            "intent": "threat",
            "actor": "player",
            "intensity": random.uniform(0.8, 1.0),
        }


# ----------------------------
# Main Simulation Loop
# ----------------------------

def main():
    print("\n=== Ghost NPC Demo ===\n")

    # Create an explicit Ghost engine instance
    engine = GhostEngine()

    guard = GuardNPC("Gatekeeper")

    for tick in range(12):
        print(f"\n--- TICK {tick} ---")

        event = generate_npc_event()

        if event:
            print(f"[NPC Engine] Event → {event}")
            engine.step(event)
        else:
            engine.step()  # decay / passive update

        state = engine.state()
        threat = state["npc"]["threat_level"]

        print(f"[Ghost] Threat Level → {threat:.2f}")

        guard.update_behavior(state)
        guard.act()

        time.sleep(0.5)


if __name__ == "__main__":
    main()
