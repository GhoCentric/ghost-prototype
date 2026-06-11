from ghost.engine import GhostEngine


ACTOR = "player"
TARGET = "shopkeeper"

NPC_PERSONALITY = "resentful"
NPC_PERSONALITY_NOTE = (
    "Resentful: harsher trust penalties, slower emotional recovery."
)


def clear_line():
    print()


def clamp(value, low, high):
    return max(low, min(high, value))


def trigger_label(trigger):
    if not trigger:
        return "-"

    return trigger.get("event", "-")

def emotional_pressure(state, trust):
    if state == "hostile":
        return "broken"

    if state == "friendly":
        return "stable"

    if trust <= -0.35:
        return "damaged, but not broken"

    if trust < 0.0:
        return "strained"

    if trust >= 0.05:
        return "warming"

    return "none"

def price_multiplier(state, trust):
    if state == "friendly":
        return 0.85

    if state == "hostile":
        return 2.0

    if trust < -0.35:
        return 1.5

    return 1.0


def quest_available(state, trust):
    return state == "friendly" and trust >= 0.08


def shopkeeper_mood_line(state, trust):
    if state == "hostile":
        if trust <= -0.70:
            return "Shopkeeper: \"Get out. I remember exactly what you did.\""

        return "Shopkeeper: \"You can stand there, but do not mistake that for trust.\""

    if state == "friendly":
        return "Shopkeeper: \"Good to see you again. You have been decent to me.\""

    if trust < -0.30:
        return "Shopkeeper: \"I am listening, but I have not forgotten.\""

    return "Shopkeeper: \"What do you need?\""


def action_result_text(action):
    lines = {
        "greet": "You greet the shopkeeper.",
        "help": "You help carry supplies into the shop.",
        "gift": "You offer the shopkeeper a small gift.",
        "apologize": "You apologize and try to repair the damage.",
        "insult": "You insult the shopkeeper.",
        "threat": "You threaten the shopkeeper.",
        "attack": "You attack the shopkeeper.",
        "betrayal": "You betray the shopkeeper's trust.",
        "tick": (
            "Time passes. Relationship reservoirs naturally stabilize "
            "over time due to decay constants."
        ),
    }

    return lines.get(action, "You do nothing.")


def print_status(ghost, gold):
    rel = ghost.get_relationship(ACTOR, TARGET)

    trust = rel["trust"]
    state = rel["state"]
    transition = rel["transition"]
    trigger = rel["trigger"]

    multiplier = price_multiplier(state, trust)
    quest = quest_available(state, trust)
    pressure = emotional_pressure(state, trust)

    clear_line()
    print("=== SHOPKEEPER STATUS ===")
    print(f"Gold:       {gold}")
    print(f"Trust:      {trust:.3f}")
    print(f"State:      {state}")
    print(f"Pressure:   {pressure}")
    print(f"Price:      {multiplier:.2f}x")
    print(f"Quest:      {'available' if quest else 'unavailable'}")
    if trigger:
        print(f"Last Trigger:    {trigger_label(trigger)}")
    else:
        print("Last Trigger:    none")

    if transition:
        before, after = transition
        print(f"Last Transition: {before} -> {after}")
    else:
        print("Last Transition: no state change")

    clear_line()


def print_menu():
    print("Choose an action:")
    print("1. Greet shopkeeper")
    print("2. Help shopkeeper")
    print("3. Give gift")
    print("4. Apologize")
    print("5. Insult shopkeeper")
    print("6. Threaten shopkeeper")
    print("7. Attack shopkeeper")
    print("8. Betray shopkeeper")
    print("9. Wait / Tick - relationships naturally stabilize over time")
    print("10. Ask for quest")
    print("11. Buy bread")
    print("12. Show status")
    print("0. Quit")
    clear_line()


def ask_choice():
    try:
        return input("> ").strip()
    except EOFError:
        return "0"
    except KeyboardInterrupt:
        print()
        return "0"


def handle_event(ghost, event):
    if event == "tick":
        ghost.tick()
    else:
        ghost.apply_event(ACTOR, TARGET, event)

    rel = ghost.get_relationship(ACTOR, TARGET)

    print()
    print(action_result_text(event))
    print(f"Trust is now {rel['trust']:.3f}.")
    print(f"Relationship state is now {rel['state']}.")

    if rel["transition"]:
        before, after = rel["transition"]
        print(f"State transition: {before} -> {after}")
    else:
        print("State transition: no state change")

    if rel["trigger"]:
        print(f"Trigger fired: {trigger_label(rel['trigger'])}")
    else:
        print("Trigger fired: none")

    print()
    print(shopkeeper_mood_line(rel["state"], rel["trust"]))
    print()


def handle_quest(ghost):
    rel = ghost.get_relationship(ACTOR, TARGET)

    trust = rel["trust"]
    state = rel["state"]

    print()

    if quest_available(state, trust):
        print("Shopkeeper: \"There is something you can help me with.\"")
        print("Quest offered: Recover a missing supply crate.")
        ghost.apply_event(ACTOR, TARGET, "help")
        print("Accepting the quest improves the relationship slightly.")
    elif state == "hostile":
        print("Shopkeeper: \"A quest? From me? After what you did? No.\"")
    else:
        print("Shopkeeper: \"Not yet. I need to know I can trust you first.\"")

    print()


def handle_buy_bread(ghost, gold):
    base_price = 10
    rel = ghost.get_relationship(ACTOR, TARGET)

    trust = rel["trust"]
    state = rel["state"]
    multiplier = price_multiplier(state, trust)

    price = int(base_price * multiplier)

    print()

    if gold < price:
        print(f"Bread costs {price} gold. You only have {gold}.")
        print("Shopkeeper: \"Come back when you can pay.\"")
        print()
        return gold

    gold -= price

    print(f"You buy bread for {price} gold.")

    if state == "hostile":
        print("Shopkeeper: \"Take it and leave.\"")
    elif state == "friendly":
        print("Shopkeeper: \"Fresh from this morning. I saved you a good loaf.\"")
    else:
        print("Shopkeeper: \"Here. Standard price.\"")

    print()

    return gold


def main():
    ghost = GhostEngine()
    gold = 50

    ghost.relationships.set_personality(ACTOR, TARGET, NPC_PERSONALITY)

    print()
    print("=== GHOST SHOPKEEPER MINI GAME ===")
    print()
    print("This playable demo uses only the public GhostEngine API:")
    print()
    print("  ghost.apply_event(a, b, event)")
    print("  ghost.tick()")
    print("  ghost.get_relationship(a, b)")
    print()
    print("Your choices change the shopkeeper's emotional state.")
    print("The shopkeeper's trust affects prices, quests, and dialogue.")
    print()
    print(f"NPC Personality Loaded: {NPC_PERSONALITY}")
    print(f"Personality Effect: {NPC_PERSONALITY_NOTE}")
    print()
    print(shopkeeper_mood_line("neutral", 0.0))
    print()

    while True:
        print_status(ghost, gold)
        print_menu()

        choice = ask_choice().lower().strip()

        command_map = {
            "1": "greet",
            "greet": "greet",
            "greet shopkeeper": "greet",
            "hello": "greet",
            "hi": "greet",

            "2": "help",
            "help": "help",
            "help shopkeeper": "help",

            "3": "gift",
            "gift": "gift",
            "give gift": "gift",
            "give a gift": "gift",

            "4": "apologize",
            "apologize": "apologize",
            "sorry": "apologize",
            "say sorry": "apologize",

            "5": "insult",
            "insult": "insult",
            "insult shopkeeper": "insult",

            "6": "threat",
            "threat": "threat",
            "threaten": "threat",
            "threaten shopkeeper": "threat",

            "7": "attack",
            "attack": "attack",
            "attack shopkeeper": "attack",

            "8": "betrayal",
            "betray": "betrayal",
            "betrayal": "betrayal",
            "betray shopkeeper": "betrayal",

            "9": "tick",
            "wait": "tick",
            "time": "tick",
            "pass time": "tick",

            "10": "quest",
            "quest": "quest",
            "ask quest": "quest",
            "ask for quest": "quest",

            "11": "buy",
            "buy": "buy",
            "buy bread": "buy",
            "bread": "buy",

            "12": "status",
            "status": "status",
            "show status": "status",

            "0": "quit",
            "q": "quit",
            "quit": "quit",
            "exit": "quit",
        }

        command = command_map.get(choice)

        if command == "quit":
            print()
            print("Exiting shopkeeper demo.")
            print()
            break

        if command in (
            "greet",
            "help",
            "gift",
            "apologize",
            "insult",
            "threat",
            "attack",
            "betrayal",
            "tick",
        ):
            handle_event(ghost, command)
        elif command == "quest":
            handle_quest(ghost)
        elif command == "buy":
            gold = handle_buy_bread(ghost, gold)
        elif command == "status":
            continue
        else:
            print()
            print("Unknown choice.")
            print("Type a number like 11, or a command like 'buy bread'.")
            print()


if __name__ == "__main__":
    main()
