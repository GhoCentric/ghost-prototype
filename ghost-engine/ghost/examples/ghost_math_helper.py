"""
Ghost Math Demo

Run with:

    ghost-math-demo

Or:

    python -m ghost.examples.ghost_math_helper

This demo explains the small mathematical contract behind Ghost.

Ghost does not choose actions.
Ghost updates state.

Games send events.
Ghost returns emotional state.
Games map that state into behavior.
"""

from ghost.engine import GhostEngine


EVENT_VALUES = {
    "greet": 0.04,
    "help": 0.12,
    "gift": 0.16,
    "apologize": 0.10,
    "insult": -0.15,
    "threat": -0.22,
    "attack": -0.35,
    "betrayal": -0.70,
}


BALANCED_PERSONALITY = {
    "pos_gain": 0.85,
    "neg_gain": 1.10,
    "pos_decay": 0.970,
    "neg_decay": 0.975,
}


RESENTFUL_PERSONALITY = {
    "pos_gain": 0.60,
    "neg_gain": 1.40,
    "pos_decay": 0.980,
    "neg_decay": 0.995,
}


def clamp(value, low, high):
    return min(max(value, low), high)


def classify_relationship(trust):
    if trust <= -0.55:
        return "hostile"

    if trust >= 0.08:
        return "friendly"

    return "neutral"


def price_from_state(state, trust):
    if state == "friendly":
        return 0.85

    if state == "hostile":
        return 2.00

    if trust < -0.35:
        return 1.50

    return 1.00


def npc_behavior_from_state(state, threat):
    if state == "hostile":
        return "refuse"

    if threat >= 0.70:
        return "block"

    if threat >= 0.50:
        return "warn"

    if state == "friendly":
        return "help"

    return "idle"


def line():
    print("-" * 64)


def section(title):
    print()
    print(title)
    line()


def show_clamp_math():
    section("1. CLAMP")

    print("clamp(x, a, b) = min(max(x, a), b)")
    print()

    examples = [
        (-0.30, 0, 1),
        (0.45, 0, 1),
        (1.70, 0, 1),
    ]

    for value, low, high in examples:
        result = clamp(value, low, high)
        print(f"clamp({value:.2f}, {low}, {high}) = {result:.2f}")


def show_relationship_math():
    section("2. RELATIONSHIP RESERVOIRS")

    pos_gain = BALANCED_PERSONALITY["pos_gain"]
    neg_gain = BALANCED_PERSONALITY["neg_gain"]

    pos = 0.0
    neg = 0.0

    print("trust = positive_reservoir - negative_reservoir")
    print()
    print(f"pos_gain = {pos_gain:.2f}")
    print(f"neg_gain = {neg_gain:.2f}")
    print()

    event = "help"
    value = EVENT_VALUES[event]

    print(f"event = {event}")
    print(f"event_value = {value:.2f}")
    print()
    print("positive_next = positive + event_value * pos_gain")

    pos = clamp(pos + value * pos_gain, 0.0, 1.0)
    trust = pos - neg
    state = classify_relationship(trust)

    print(f"positive_next = 0.000 + {value:.2f} * {pos_gain:.2f}")
    print(f"positive_next = {pos:.3f}")
    print()
    print(f"trust = {pos:.3f} - {neg:.3f}")
    print(f"trust = {trust:.3f}")
    print(f"state = {state}")
    print()

    event = "betrayal"
    value = abs(EVENT_VALUES[event])

    print(f"event = {event}")
    print(f"event_value = -{value:.2f}")
    print()
    print("negative_next = negative + abs(event_value) * neg_gain")

    neg = clamp(neg + value * neg_gain, 0.0, 1.0)
    trust = pos - neg
    state = classify_relationship(trust)

    print(f"negative_next = 0.000 + {value:.2f} * {neg_gain:.2f}")
    print(f"negative_next = {neg:.3f}")
    print()
    print(f"trust = {pos:.3f} - {neg:.3f}")
    print(f"trust = {trust:.3f}")
    print(f"state = {state}")


def show_tick_decay_math():
    section("3. TICK DECAY")

    pos = 0.102
    neg = 0.770

    pos_decay = BALANCED_PERSONALITY["pos_decay"]
    neg_decay = BALANCED_PERSONALITY["neg_decay"]

    print("positive_next = positive * pos_decay")
    print("negative_next = negative * neg_decay")
    print("trust_next = positive_next - negative_next")
    print()
    print("reservoir_t1 = reservoir_t0 * decay_constant")
    print()

    print(f"positive = {pos:.3f}")
    print(f"negative = {neg:.3f}")
    print(f"pos_decay = {pos_decay:.3f}")
    print(f"neg_decay = {neg_decay:.3f}")
    print()

    pos_next = pos * pos_decay
    neg_next = neg * neg_decay
    trust_next = pos_next - neg_next
    state_next = classify_relationship(trust_next)

    print(f"positive_next = {pos:.3f} * {pos_decay:.3f}")
    print(f"positive_next = {pos_next:.3f}")
    print()
    print(f"negative_next = {neg:.3f} * {neg_decay:.3f}")
    print(f"negative_next = {neg_next:.3f}")
    print()
    print(f"trust_next = {pos_next:.3f} - {neg_next:.3f}")
    print(f"trust_next = {trust_next:.3f}")
    print(f"state_next = {state_next}")


def show_state_threshold_math():
    section("4. STATE THRESHOLDS")

    samples = [-0.750, -0.300, 0.096]

    print("trust <= -0.55  -> hostile")
    print("-0.55 < trust < 0.08 -> neutral")
    print("trust >= 0.08 -> friendly")
    print()

    for trust in samples:
        state = classify_relationship(trust)
        print(f"trust = {trust:.3f} -> state = {state}")


def show_game_mapping_math():
    section("5. GAME BEHAVIOR MAPPING")

    examples = [
        {"trust": 0.096, "state": "friendly", "threat": 0.00},
        {"trust": -0.351, "state": "neutral", "threat": 0.55},
        {"trust": -0.768, "state": "hostile", "threat": 1.00},
    ]

    print("price:")
    print("friendly -> 0.85x")
    print("hostile -> 2.00x")
    print("neutral and trust < -0.35 -> 1.50x")
    print("neutral and trust >= -0.35 -> 1.00x")
    print()

    print("behavior:")
    print('"hostile" -> refuse')
    print("threat >= 0.70 -> block")
    print("threat >= 0.50 -> warn")
    print('"friendly" -> help')
    print("else -> idle")
    print()

    for item in examples:
        trust = item["trust"]
        state = item["state"]
        threat = item["threat"]

        price = price_from_state(state, trust)
        behavior = npc_behavior_from_state(state, threat)

        print(
            f"trust={trust:>6.3f} "
            f"state={state:<8} "
            f"threat={threat:>4.2f} "
            f"price={price:.2f}x "
            f"behavior={behavior}"
        )


def show_public_api_check():
    section("6. PUBLIC API CHECK")

    ghost = GhostEngine()

    print('ghost = GhostEngine()')
    print('ghost.apply_event("player", "shopkeeper", "help")')
    print('ghost.apply_event("player", "shopkeeper", "betrayal")')
    print('rel = ghost.get_relationship("player", "shopkeeper")')
    print()

    ghost.apply_event("player", "shopkeeper", "help")
    ghost.apply_event("player", "shopkeeper", "betrayal")

    rel = ghost.get_relationship("player", "shopkeeper")

    print("Engine returned:")
    print(rel)
    print()

    trust = rel["trust"]
    state = rel["state"]
    price = price_from_state(state, trust)

    print(f"trust = {trust:.3f}")
    print(f"state = {state}")
    print(f"price = {price:.2f}x")


def show_resentful_personality_example():
    section("7. RESENTFUL PERSONALITY EXAMPLE")

    pos_gain = RESENTFUL_PERSONALITY["pos_gain"]
    neg_gain = RESENTFUL_PERSONALITY["neg_gain"]

    pos = 0.0
    neg = 0.0

    print("resentful_pos_gain = 0.60")
    print("resentful_neg_gain = 1.40")
    print()
    print("trust = positive_reservoir - negative_reservoir")
    print()

    event = "greet"
    value = EVENT_VALUES[event]

    print(f"event = {event}")
    print(f"event_value = {value:.2f}")
    print()
    print("positive_next = positive + event_value * resentful_pos_gain")

    pos = clamp(pos + value * pos_gain, 0.0, 1.0)
    trust = pos - neg
    state = classify_relationship(trust)

    print(f"positive_next = 0.000 + {value:.2f} * {pos_gain:.2f}")
    print(f"positive_next = {pos:.3f}")
    print()
    print(f"trust = {pos:.3f} - {neg:.3f}")
    print(f"trust = {trust:.3f}")
    print(f"state = {state}")
    print()

    event = "help"
    value = EVENT_VALUES[event]

    print(f"event = {event}")
    print(f"event_value = {value:.2f}")
    print()
    print("positive_next = positive + event_value * resentful_pos_gain")

    old_pos = pos
    pos = clamp(pos + value * pos_gain, 0.0, 1.0)
    trust = pos - neg
    state = classify_relationship(trust)

    print(f"positive_next = {old_pos:.3f} + {value:.2f} * {pos_gain:.2f}")
    print(f"positive_next = {pos:.3f}")
    print()
    print(f"trust = {pos:.3f} - {neg:.3f}")
    print(f"trust = {trust:.3f}")
    print(f"state = {state}")
    print()

    event = "betrayal"
    value = abs(EVENT_VALUES[event])

    print(f"event = {event}")
    print(f"event_value = -{value:.2f}")
    print()
    print("negative_next = negative + abs(event_value) * resentful_neg_gain")

    old_neg = neg
    neg = clamp(neg + value * neg_gain, 0.0, 1.0)
    trust = pos - neg
    state = classify_relationship(trust)
    price = price_from_state(state, trust)

    print(f"negative_next = {old_neg:.3f} + {value:.2f} * {neg_gain:.2f}")
    print(f"negative_next = {neg:.3f}")
    print()
    print(f"trust = {pos:.3f} - {neg:.3f}")
    print(f"trust = {trust:.3f}")
    print(f"state = {state}")
    print(f"price = {price:.2f}x")
    print()

    print("base_cost = 10")
    print(f"final_cost = 10 * {price:.2f}")
    print(f"final_cost = {int(10 * price)}")

def show_maturity_volatility_example():
    section("8. MATURITY / VOLATILITY")

    print("maturity = relationship stability over repeated interactions")
    print("volatility = how strongly a relationship reacts to new events")
    print()
    print("maturity_modifier = 1.0 - maturity")
    print("positive_effective_gain = base_gain * volatility * positive_volatility * maturity_modifier")
    print("negative_effective_gain = base_gain * volatility * negative_volatility * maturity_modifier")
    print()

    print("Short relationship:")
    print("2x help, then betrayal")
    print()

    short = GhostEngine()

    short.apply_event("player", "npc", "help")
    short.apply_event("player", "npc", "help")

    before_short = short.get_relationship("player", "npc")

    short.apply_event("player", "npc", "betrayal")
    after_short = short.get_relationship("player", "npc")

    print("before betrayal:")
    print(f"trust = {before_short['trust']:.3f}")
    print(f"state = {before_short['state']}")
    print(f"maturity = {before_short['maturity']:.2f}")
    print()

    print("after betrayal:")
    print(f"trust = {after_short['trust']:.3f}")
    print(f"state = {after_short['state']}")
    print(f"maturity = {after_short['maturity']:.2f}")
    print(f"volatility = {after_short['volatility']:.2f}")
    print()

    print("Long relationship:")
    print("20x help, then betrayal")
    print()

    long = GhostEngine()

    for _ in range(20):
        long.apply_event("player", "npc", "help")

    before_long = long.get_relationship("player", "npc")

    long.apply_event("player", "npc", "betrayal")
    after_long = long.get_relationship("player", "npc")

    print("before betrayal:")
    print(f"trust = {before_long['trust']:.3f}")
    print(f"state = {before_long['state']}")
    print(f"maturity = {before_long['maturity']:.2f}")
    print()

    print("after betrayal:")
    print(f"trust = {after_long['trust']:.3f}")
    print(f"state = {after_long['state']}")
    print(f"maturity = {after_long['maturity']:.2f}")
    print(f"volatility = {after_long['volatility']:.2f}")
    print()

    print("Same event. Different history. Different outcome.")
    print()

    print("Personality comparison:")
    print("10x help, then betrayal")
    print()

    personalities = (
        "balanced",
        "forgiving",
        "resentful",
        "volatile",
    )

    print("Personality | Before  | After   | State    | Mat | Vol | PosV | NegV")
    print("--------------------------------------------------------------------")

    for personality in personalities:
        ghost = GhostEngine()
        ghost.relationships.set_personality("player", "npc", personality)

        for _ in range(10):
            ghost.apply_event("player", "npc", "help")

        before = ghost.get_relationship("player", "npc")

        ghost.apply_event("player", "npc", "betrayal")
        after = ghost.get_relationship("player", "npc")

        print(
            f"{personality:<11} "
            f"{before['trust']:>7.3f}  "
            f"{after['trust']:>7.3f}  "
            f"{after['state']:<8} "
            f"{after['maturity']:>4.2f} "
            f"{after['volatility']:>4.2f} "
            f"{after['positive_volatility']:>5.2f} "
            f"{after['negative_volatility']:>5.2f}"
        )

    print()
    print("With 10 prior helpful actions, some personalities")
    print("remain friendly after one betrayal.")
    print("Resentful and volatile profiles drop harder because")
    print("negative events carry more weight.")
    print()
    print("Maturity does not erase history.")
    print("Maturity reduces future emotional swing.")
    print("Volatility changes how strongly events hit.")
    print("Positive and negative volatility can differ.")

def main():
    print()
    print("=== GHOST MATH DEMO ===")
    print()
    print("Ghost stores internal state.")
    print("Games send events.")
    print("Ghost returns emotional state.")
    print("Games decide behavior.")

    show_clamp_math()
    show_relationship_math()
    show_tick_decay_math()
    show_state_threshold_math()
    show_game_mapping_math()
    show_public_api_check()
    show_resentful_personality_example()
    show_maturity_volatility_example()

    print()
    print("✔ Ghost math demo complete.")


if __name__ == "__main__":
    main()