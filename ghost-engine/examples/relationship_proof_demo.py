from ghost import GhostAPI


# -----------------------------
# BASELINE MODEL (NO MEMORY)
# -----------------------------
def baseline_step(prev, value, alpha=0.2):
    trust = prev * (1 - alpha) + value * alpha
    return max(min(trust, 1.0), -1.0)


# -----------------------------
# RUN DEMO
# -----------------------------
def run_demo():
    ghost = GhostAPI()

    print("\n=== GHOST vs BASELINE PROOF DEMO ===\n")

    sequence = [
        ("help", 0.3),
        ("help", 0.3),

        ("insult", -0.5),  # BIG betrayal

        ("help", 0.3),
        ("help", 0.3),

        ("betrayal", 1.0),  # repeated damage

        ("help", 0.3),
    ]

    baseline = 0.0
    g_trust = 0.0

    print(f"{'Step':<4} | {'Event':<7} | {'Baseline':<8} | {'Ghost':<8} | {'State':<12} | {'Δ'}")
    print("-" * 75)

    for i, (event, val) in enumerate(sequence):
        # --- baseline ---
        baseline = baseline_step(baseline, val)

        # --- ghost ---
        ghost.apply_event("A", "B", {
            "type": event,
            "intensity": abs(val)
        })
        ghost.engine.relationships.tick()

        rel = ghost.get_relationship("A", "B")
        g_trust = rel["trust"]

        # 🔥 REAL STATE FROM ENGINE
        state = rel.get("state", "unknown")

        diff = g_trust - baseline
        trigger = rel.get("trigger")

        # -----------------------------
        # IMPACT TAGGING (CLEAN)
        # -----------------------------
        impact = ""

        if i > 0:
            if g_trust < baseline:
                impact = "<- holding"
            if g_trust < -0.1:
                impact = "<- degrading"

        print(
            f"{i:<4} | "
            f"{event:<7} | "
            f"{baseline:<8.3f} | "
            f"{g_trust:<8.3f} | "
            f"{state:<12} | "
            f"{diff:+.3f} {impact}"
        )

        if trigger:
            trigger_event = trigger.get("event")

            if trigger_event == "relationship_broken":
                print("    ⚠ RELATIONSHIP BROKEN")

            elif trigger_event == "forgiveness":
                print("    ✓ trust improved")

            elif trigger_event == "deescalation":
                print("    ↓ tension reduced")

            else:
                print(f"    ↔ state shift ({trigger.get('from')} → {trigger.get('to')})")
  
    # -----------------------------
    # INTERPRETATION
    # -----------------------------
    print("\n--- INTERPRETATION ---")
    print("Baseline = forgets quickly (smooth recovery)")
    print("Ghost    = carries emotional weight (inertia)")
    print("Difference shows memory + resistance to change\n")

    # -----------------------------
    # FINAL VERDICT
    # -----------------------------
    print("=== FINAL VERDICT ===")

    if g_trust < baseline:
        print("Ghost retained negative emotional state.")
        print("Baseline recovered.")
        print("-> Emotional inertia confirmed.")
    else:
        print("No meaningful difference detected.")


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    run_demo()
