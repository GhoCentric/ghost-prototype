"""Ghost v1.10.0 development demo: read-only persistent salience bridge."""

from copy import deepcopy

from ghost import GhostAPI


def main() -> None:
    ghost = GhostAPI()
    ghost.register_emotional_agent(
        "sera",
        initial={"anger": 0.62, "fear": 0.28},
    )
    ghost.register_interpretation_agent(
        "sera",
        initial={"betrayal": 0.78, "cooperation": 0.14},
    )
    ghost.register_attention_agent(
        "sera",
        initial_flow_pressure=0.90,
        flow_active=True,
    )

    emotions_before = deepcopy(ghost.emotional_state("sera"))
    meanings_before = deepcopy(ghost.interpretation_state("sera"))

    bridged = ghost.advance_attention_from_state(
        "sera",
        signals={
            "task_focus": 1.0,
            "repetition": 1.0,
            "stability": 1.0,
        },
        provenance={"task": "repair_cart"},
    )

    print("GHOST v1.10.0 DEVELOPMENT — READ-ONLY SALIENCE BRIDGE")
    print("=========================================================")
    print("Attention reads persistent state. It cannot write it back.\n")
    print("PERSISTENT SOURCE SALIENCE")
    for name, value in bridged["bridge"]["salience"].items():
        if value > 0.0:
            print(f"  {name:<28} {value:.3f}")

    record = bridged["attention"]
    print("\nFLOW-COMPRESSED ACCESS")
    print(f"  flow active:    {record['flow_active_after']}")
    print(f"  attention gain: {record['attention_gain']:.3f}")
    print(
        "  betrayal:      "
        f"{record['underlying_salience']['interpretation:betrayal']:.3f} -> "
        f"{record['attended_salience']['interpretation:betrayal']:.3f}"
    )

    print("\nSOURCE IMMUTABILITY")
    print(f"  emotions unchanged:       {ghost.emotional_state('sera') == emotions_before}")
    print(f"  interpretations unchanged:{ghost.interpretation_state('sera') == meanings_before}")

    breakthrough = ghost.advance_attention_from_state(
        "sera",
        signals={"threat": 1.0},
    )["attention"]
    print("\nBREAKTHROUGH")
    print(f"  breakthrough:   {breakthrough['breakthrough']}")
    print(f"  attention gain: {breakthrough['attention_gain']:.3f}")
    print(
        "  betrayal:      "
        f"{breakthrough['attended_salience']['interpretation:betrayal']:.3f}"
    )

    print("\nThe bridge is stateless and adds no snapshot layer.")
    print("Ghost still does not choose the NPC's final action.")


if __name__ == "__main__":
    main()
