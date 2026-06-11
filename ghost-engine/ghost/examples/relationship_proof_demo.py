# ghost/examples/shopkeeper_demo.py

from ghost import GhostAPI


def main():
    ghost = GhostAPI()

    gold = 100

    # -----------------------------
    # NPC LIST
    # -----------------------------
    npcs = ["shopkeeper", "blacksmith", "guard"]

    # -----------------------------
    # LOCAL AREA / RUMOR SYSTEM
    # -----------------------------
    local_heat = 0
    rumor_stage = "clean"

    print("\n=== MARKET REPUTATION DEMO ===")
    print("Actions: help, insult, steal, ask, buy, leave")
    print("Target NPC: shopkeeper (others react via rumors)\n")

    while True:
        action = input("What do you do? ").strip().lower()

        if action == "leave":
            print("\nYou leave the market.\n")
            break

        if action not in ["help", "insult", "steal", "ask", "buy"]:
            print("Invalid action.\n")
            continue

        # -----------------------------
        # EVENT MAP
        # -----------------------------
        event_map = {
            "help": ("help", 1.0),
            "insult": ("insult", 0.45),
            "steal": ("betrayal", 1.0),
        }

        # -----------------------------
        # APPLY EVENT (NOW THROUGH API)
        # -----------------------------
        if action in event_map:
            event_type, intensity = event_map[action]

            ghost.propagate_event(
                "player",
                "shopkeeper",
                {
                    "type": event_type,
                    "intensity": intensity,
                },
                npcs,
                heat=local_heat,
            )

            # -----------------------------
            # HEAT SYSTEM
            # -----------------------------
            if action == "insult":
                local_heat += 1
            elif action == "steal":
                local_heat += 3
            elif action == "help" and local_heat > 0:
                local_heat -= 1

        # -----------------------------
        # DETERMINE RUMOR STAGE
        # -----------------------------
        if local_heat <= 0:
            rumor_stage = "clean"
        elif local_heat <= 2:
            rumor_stage = "noticed"
        elif local_heat <= 4:
            rumor_stage = "talked_about"
        else:
            rumor_stage = "tainted"

        # advance time
        ghost.tick()

        # -----------------------------
        # READ ALL NPC STATES
        # -----------------------------
        print("\n--- MARKET STATUS ---")
        print(f"Gold: {gold}")
        print(f"Local reputation: {rumor_stage} (heat={local_heat})\n")

        states = {}

        for npc in npcs:
            rel = ghost.get_relationship("player", npc)
            states[npc] = rel
            print(f"{npc.upper()}: {rel['state']} ({rel['trust']:.3f})")

        print("")

        shop_state = states["shopkeeper"]["state"]
        guard_state = states["guard"]["state"]

        # -----------------------------
        # SHOP PRICING
        # -----------------------------
        base_price = 20

        if shop_state == "loyal":
            price = int(base_price * 0.5)
            behavior = "🔥 Special discounts"
        elif shop_state == "friendly":
            price = base_price
            behavior = "🙂 Fair prices"
        elif shop_state == "neutral":
            price = int(base_price * 1.25)
            behavior = "😐 Slightly higher prices"
        elif shop_state == "unfriendly":
            price = int(base_price * 1.75)
            behavior = "😒 Expensive prices"
        else:
            price = None
            behavior = "❌ Refuses service"

        print(f"Shopkeeper: {behavior}")
        print(f"Relationship is currently {shop_state.upper()}")

        # -----------------------------
        # BUY
        # -----------------------------
        if action == "buy":
            if shop_state == "hostile":
                print("Shopkeeper: 'Get out.'")
            else:
                print(f"Item price: {price} gold")

                if gold >= price:
                    gold -= price
                    print("You bought the item.")
                else:
                    print("Not enough gold.")

        # -----------------------------
        # ASK SYSTEM
        # -----------------------------
        if action == "ask":
            if shop_state in ("friendly", "loyal"):
                print("Shopkeeper shares valuable information.")
            elif shop_state == "neutral":
                print("Shopkeeper shrugs.")
            else:
                print("Shopkeeper refuses to help.")

        # -----------------------------
        # GUARD REACTION
        # -----------------------------
        if guard_state == "hostile":
            print("🛡 Guard: 'You're causing trouble. Leave now.'")

        # -----------------------------
        # STEAL CONSEQUENCES
        # -----------------------------
        if action == "steal":
            stolen = 15
            gold += stolen
            print(f"You stole {stolen} gold.")
            print("⚠ This may spread...")

        # -----------------------------
        # FEEDBACK
        # -----------------------------
        if action == "insult":
            print("You make things tense.")
        elif action == "help":
            print("You try to repair the relationship.")

        print("-" * 40)

    print("Demo ended.")


if __name__ == "__main__":
    main()
