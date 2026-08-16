"""Small deterministic proof of Ghost's independent emotional-state layer."""

from ghost import GhostAPI


def _prime_relationship(ghost):
    for _ in range(20):
        ghost.apply_event(
            "player",
            "guard",
            {"type": "help", "intensity": 1.0},
        )


def _print_vector(label, packet):
    layered = packet["layered_state"]
    print(label)
    print(
        "  relationship:",
        layered["relationship_state"],
        f"trust={layered['trust']:+.3f}",
    )
    for name, value in layered["emotional_levels"].items():
        print(f"  {name:>6}: {value:.3f}")
    print(
        "  spotlight:",
        layered["dominant_emotion"],
        f"salience={layered['dominant_salience']:.3f}",
    )
    print()


def main():
    balanced = GhostAPI()
    fear_sensitive = GhostAPI()

    fear_sensitive.register_emotional_agent(
        "guard",
        sensitivities={
            "anger": 0.50,
            "fear": 3.00,
            "grief": 0.50,
        },
    )

    _prime_relationship(balanced)
    _prime_relationship(fear_sensitive)

    event = {"type": "betrayal", "intensity": 1.0}
    a = balanced.apply_layered_event("player", "guard", event)
    b = fear_sensitive.apply_layered_event("player", "guard", event)

    print("GHOST MULTI-EMOTION LAYER")
    print("===========================")
    print("Same relationship history. Same betrayal. No randomness.\n")
    _print_vector("BALANCED EMOTIONAL SENSITIVITY", a)
    _print_vector("FEAR-SENSITIVE AGENT", b)

    print("The relationship result is the same.")
    print("The emotional vectors are not.")
    print("Ghost exposes the pressure; the host still owns the action.")


if __name__ == "__main__":
    main()
