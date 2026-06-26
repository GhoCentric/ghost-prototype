"""
Ghost v1.8.0 threat-response demo.

The same player threat can produce different deterministic response
recommendations because NPC temperament, relationship memory, and local
game context differ.

Ghost does not execute these actions.
A game layer decides how to animate or apply them.
"""

from ghost.api import GhostAPI


def print_header(title):
    print()
    print("=" * 64)
    print(title)
    print("=" * 64)


def show(packet):
    signals = packet["signals"]

    print(f"NPC:          {packet['npc']}")
    print(f"Temperament:  {packet['temperament']}")
    print(f"Response:     {packet['response']}")
    print(f"Reason:       {packet['reason']}")
    print()
    print(
        "Signals: "
        f"threat={signals['threat']:.3f} "
        f"fear={signals['fear']:.3f} "
        f"anger={signals['anger']:.3f} "
        f"confidence={signals['confidence']:.3f}"
    )
    print(
        "Context: "
        f"player_armed={packet['context']['player_armed']} "
        f"npc_armed={packet['context']['npc_armed']} "
        f"escape={packet['context']['escape_route']} "
        f"guards={packet['context']['guard_nearby']}"
    )


def main():
    print_header("GHOST THREAT-RESPONSE DEMO")

    print("Ghost reads persistent relationship state plus")
    print("explicit game context and returns a deterministic")
    print("response recommendation.")
    print()

    api = GhostAPI()

    relationship = api.apply_event(
        "player",
        "merchant",
        {"type": "threat", "intensity": 0.90},
    )

    print_header("Same threat. Different NPC conditions.")

    cases = [
        (
            "anxious_civilian",
            "anxious",
            {
                "player_armed": True,
                "player_aiming": True,
                "escape_route": True,
            },
        ),
        (
            "cornered_civilian",
            "anxious",
            {
                "player_armed": True,
                "player_aiming": True,
                "escape_route": False,
            },
        ),
        (
            "armed_rival",
            "resentful",
            {
                "player_armed": True,
                "player_attacking": True,
                "npc_armed": True,
                "allies_nearby": 2,
                "escape_route": False,
            },
        ),
        (
            "market_guard",
            "suspicious",
            {
                "player_armed": True,
                "player_aiming": True,
                "guard_nearby": True,
                "authority_present": True,
                "crowd_size": 8,
            },
        ),
    ]

    for npc, temperament, context in cases:
        print()
        print("-" * 64)

        packet = api.evaluate_threat_response(
            npc=npc,
            relationship=relationship,
            temperament=temperament,
            context=context,
        )

        show(packet)

    print_header("What this proves")

    print("The player threat is not mapped to one fixed reaction.")
    print("Ghost relationship memory and temperament change the read.")
    print("Game context changes the response recommendation.")
    print()
    print("Ghost still does not animate, attack, flee, or call guards.")
    print("The game layer executes the returned response.")
    print()
    print("✔ Ghost threat-response demo complete")


if __name__ == "__main__":
    main()
