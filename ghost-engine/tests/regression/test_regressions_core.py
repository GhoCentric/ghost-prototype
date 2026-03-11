# The Copy-State Bug

def test_state_is_live_not_copy():
    from ghost.engine import GhostEngine

    e = GhostEngine()
    s = e.state()

    s.setdefault("state", {})
    s["state"]["mood"] = 0.9

    e.step({"source": "npc_engine", "intent": "threat", "intensity": 1.0})

    assert e.state()["npc"]["threat_level"] > 0.5
   
# Actor Memory Persistence   
 
def test_actor_memory_persists():
    from ghost.engine import GhostEngine

    e = GhostEngine()

    e.step({"source":"npc_engine","intent":"threat","actor":"a","intensity":1})
    e.step({"source":"npc_engine","intent":"threat","actor":"a","intensity":1})

    assert e.state()["npc"]["actors"]["a"]["threat_count"] == 2

# Decay Over Multiple Cycles  
     
def test_decay_multiple_steps():
    from ghost.engine import GhostEngine

    e = GhostEngine()

    e.step({"source":"npc_engine","intent":"threat","intensity":1})
    t1 = e.state()["npc"]["threat_level"]

    e.step()
    e.step()
    e.step()

    assert e.state()["npc"]["threat_level"] < t1

# Missing Mood Safe Path    
    
def test_missing_mood_safe():
    from ghost.engine import GhostEngine

    e = GhostEngine()
    e.step({"source":"npc_engine","intent":"threat","intensity":1})

    assert e.state()["npc"]["threat_level"] >= 0

# Broken Input Safe Handling

def test_broken_input_safe():
    from ghost.engine import GhostEngine

    e = GhostEngine()

    # engine should reject malformed steps cleanly
    try:
        e.step({"intent": None})
    except TypeError:
        pass

    try:
        e.step({"intent": 123})
    except TypeError:
        pass

    try:
        e.step({})
    except TypeError:
        pass

    # but engine must remain stable afterward
    assert isinstance(e.state(), dict)
