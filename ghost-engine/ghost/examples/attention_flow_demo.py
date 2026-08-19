"""Small deterministic v1.10.0 development demo for attention / flow."""

from ghost import GhostAPI


def _signals(focus, repetition, stability, novelty=0.0, threat=0.0):
    return {
        "task_focus": focus,
        "repetition": repetition,
        "stability": stability,
        "novelty": novelty,
        "threat": threat,
        "contradiction": 0.0,
        "interpretation_impulse": 0.0,
    }


def main() -> None:
    api = GhostAPI()
    api.register_attention_agent("Sera")
    persistent = {"betrayal": 0.78, "anger": 0.62}

    print("GHOST v1.10.0 DEVELOPMENT — PERSISTENT ATTENTION / FLOW")
    print("========================================================")
    print("No RNG. No timer pulse. Underlying emotion is not erased.")
    print()
    print("PERSISTENT INTERNAL SALIENCE")
    print(f"  betrayal={persistent['betrayal']:.2f}  anger={persistent['anger']:.2f}")
    print()
    print("TASK ABSORPTION")

    trajectory = [
        _signals(0.88, 0.55, 0.82, novelty=0.12),
        _signals(0.94, 0.72, 0.88, novelty=0.06),
        _signals(0.97, 0.86, 0.91, novelty=0.03),
        _signals(1.00, 0.94, 0.95),
        _signals(1.00, 1.00, 0.97),
        _signals(1.00, 1.00, 1.00),
        _signals(1.00, 1.00, 1.00),
        _signals(1.00, 1.00, 1.00),
    ]

    last = None
    for index, signals in enumerate(trajectory, 1):
        last = api.advance_attention(
            "Sera",
            signals,
            persistent,
            source="repair_cart",
        )
        print(
            f"  step {index}: pressure={last['flow_pressure_after']:.3f} "
            f"flow={str(last['flow_active_after']):5s} "
            f"gain={last['attention_gain']:.3f}"
        )

    print()
    print("DULL / FLOW MOMENT")
    print(
        "  underlying betrayal="
        f"{last['underlying_salience']['betrayal']:.3f}"
    )
    print(
        "  attended betrayal ="
        f"{last['attended_salience']['betrayal']:.3f}"
    )
    print("  The betrayal still exists. Access to it is temporarily compressed.")

    interrupted = api.advance_attention(
        "Sera",
        _signals(1.0, 1.0, 1.0, threat=1.0),
        persistent,
        source="world",
        provenance={"event": "castle_fire"},
    )
    print()
    print("STRONG EVENT BREAKTHROUGH")
    print(f"  breakthrough: {interrupted['breakthrough']}")
    print(f"  resurfaced:   {interrupted['resurfaced']}")
    print(f"  attention gain: {interrupted['attention_gain']:.3f}")
    print(
        "  attended betrayal: "
        f"{interrupted['attended_salience']['betrayal']:.3f}"
    )

    restored = GhostAPI.from_snapshot(api.snapshot())
    print()
    print("SNAPSHOT / RESTORE")
    print(f"  identical: {restored.snapshot() == api.snapshot()}")
    print()
    print("Flow emerges from signal history, not an interval.")
    print("Emotion/meaning persists underneath transient attention.")
    print("Ghost still does not choose the NPC's final action.")


if __name__ == "__main__":
    main()
