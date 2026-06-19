from ghost.engine import GhostEngine


engine = GhostEngine()

print("INITIAL STATE")
print(engine.snapshot())

print("\nSTEP 1: greet")
engine.step({
    "source": "npc_engine",
    "intent": "greet",
    "actor": "npc_1",
    "target": "npc_2",
    "intensity": 0.5,
})
print(engine.snapshot())

print("\nSTEP 2: help")
engine.step({
    "source": "npc_engine",
    "intent": "help",
    "actor": "npc_2",
    "target": "npc_3",
    "intensity": 0.7,
})
print(engine.snapshot())

print("\nSTEP 3: threat")
engine.step({
    "source": "npc_engine",
    "intent": "threat",
    "actor": "npc_1",
    "target": "npc_2",
    "intensity": 0.6,
})
print(engine.snapshot())