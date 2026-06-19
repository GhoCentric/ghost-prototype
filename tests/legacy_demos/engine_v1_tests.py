from ghost.engine import GhostEngine
import json
import copy


# --------------------------------------------------
# TEST 1 — DETERMINISM
# --------------------------------------------------

def test_determinism():
    print("\n=== TEST 1: DETERMINISM ===")

    steps = [
        {"source": "npc_engine", "intent": "greet", "actor": "npc_1", "target": "npc_2", "intensity": 0.5},
        {"source": "npc_engine", "intent": "help",  "actor": "npc_2", "target": "npc_3", "intensity": 0.7},
        {"source": "npc_engine", "intent": "threat","actor": "npc_1", "target": "npc_2", "intensity": 0.6},
    ]

    # Run sequence once
    engine1 = GhostEngine()
    for s in steps:
        engine1.step(s)

    state1 = engine1.snapshot()

    # Run again
    engine2 = GhostEngine()
    for s in steps:
        engine2.step(s)

    state2 = engine2.snapshot()

    if state1 == state2:
        print("PASS — deterministic behavior confirmed")
    else:
        print("FAIL — states differ")
        print("STATE 1:", state1)
        print("STATE 2:", state2)


# --------------------------------------------------
# TEST 2 — CLAMPING
# --------------------------------------------------

def test_clamping():
    print("\n=== TEST 2: CLAMPING ===")

    engine = GhostEngine()

    engine.step({
        "source": "npc_engine",
        "intent": "threat",
        "actor": "npc_A",
        "target": "npc_B",
        "intensity": 5.0   # intentionally extreme
    })

    state = engine.snapshot()

    npc_A = state["agents"]["npc_A"]
    npc_B = state["agents"]["npc_B"]

    if (
        0.0 <= npc_A["mood"] <= 1.0 and
        0.0 <= npc_B["mood"] <= 1.0 and
        0.0 <= npc_A["tension"] <= 1.0 and
        0.0 <= npc_B["tension"] <= 1.0
    ):
        print("PASS — values properly clamped")
    else:
        print("FAIL — values out of bounds")
        print(state)


# --------------------------------------------------
# TEST 3 — SERIALIZATION SAFETY
# --------------------------------------------------

def test_serialization():
    print("\n=== TEST 3: SERIALIZATION SAFETY ===")

    engine = GhostEngine()

    engine.step({
        "source": "npc_engine",
        "intent": "greet",
        "actor": "npc_1",
        "target": "npc_2",
        "intensity": 0.5,
    })

    state = engine.snapshot()

    try:
        json.dumps(state)
        print("PASS — state is JSON serializable")
    except Exception as e:
        print("FAIL — not JSON serializable")
        print("ERROR:", e)


# --------------------------------------------------
# RUN ALL TESTS
# --------------------------------------------------

if __name__ == "__main__":
    test_determinism()
    test_clamping()
    test_serialization()