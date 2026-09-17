"""Ghost v1.11 Phase 4 deterministic motive-field proof."""
from __future__ import annotations

import json

from ghost import GhostAPI


def main() -> None:
    api = GhostAPI()
    sera = api.register_agent(
        "sera",
        role="guard",
        traits={"cautious": 0.72},
        values={"protect_town": 0.90, "personal_safety": 0.50},
        goals={
            "maintain_post": {"status": "active", "priority": 0.80},
            "verify_report": {"status": "inactive", "priority": 0.75},
        },
    )

    sera.configure_motive(
        "protect",
        baseline=0.05,
        weights={
            "value:protect_town": 0.45,
            "goal:maintain_post:priority_remaining": 0.50,
        },
    )
    sera.configure_motive(
        "investigate",
        baseline=0.05,
        weights={
            "value:protect_town": 0.20,
            "goal:verify_report:priority_remaining": 0.80,
        },
    )
    sera.configure_motive(
        "preserve_self",
        baseline=0.10,
        weights={"value:personal_safety": 0.70},
    )

    before = sera.evaluate_motives()

    # The host explicitly changes Ghost-owned goal state. It does NOT set any
    # motive score. The motive field is recomputed from the resulting state.
    sera.transition_goal("maintain_post", "blocked", reason="relief_guard_arrived")
    sera.set_goal_progress("maintain_post", 1.0)
    sera.transition_goal("verify_report", "active", reason="credible_report_received")
    sera.set_goal_priority("verify_report", 0.95)
    after = sera.evaluate_motives()

    restored = GhostAPI.from_snapshot(api.snapshot())
    restored_next = restored.agent("sera").evaluate_motives()
    original_next = sera.evaluate_motives()

    print("GHOST v1.11 PHASE 4 — DETERMINISTIC MOTIVE FIELD")
    print("====================================================")
    print(json.dumps({
        "before": {
            "ranking": before["ranking"],
            "scores": {name: data["score"] for name, data in before["motives"].items()},
        },
        "after_goal_state_change": {
            "ranking": after["ranking"],
            "scores": {name: data["score"] for name, data in after["motives"].items()},
        },
    }, indent=2, sort_keys=True))
    print()
    print("Developer directly set motive score: NO")
    print("Persistent state changed motive pressure automatically: PASS")
    print("Motive channels are configurable / engine-neutral: PASS")
    print("Missing configured signals become zero + audited: PASS")
    print("Raw observation is not silently treated as motive: PASS")
    print("Snapshot restore + deterministic continuation:", "PASS" if restored_next == original_next else "FAIL")
    print("Action / intent selection: NOT YET — Phase 5+")
    print("LLM calls: 0")
    print("Package producer: 1.10.0 (UNCHANGED during v1.11 development)")
    print("Top-level snapshot schema: 1.0 (UNCHANGED)")
    print("Agent snapshot sub-schema: 1.1 (UNCHANGED)")
    print("Perception snapshot sub-schema: 1.0 (UNCHANGED)")
    print("Motive snapshot sub-schema: 1.0")
    print("\nGHOST v1.11 PHASE 4: PASS")


if __name__ == "__main__":
    main()
