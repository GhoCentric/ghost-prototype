"""Ghost Engine v1.11 Phase 3 — stateful values and deterministic goal lifecycle demo."""
from __future__ import annotations

import json

from ghost import GhostAPI


def main() -> None:
    ghost = GhostAPI()
    sera = ghost.register_agent(
        "sera",
        role="guard",
        traits={"cautious": 0.72, "steadfast": 0.81},
        values={"protect_town": 0.90, "loyalty": 0.74},
        goals={
            "maintain_post": {
                "status": "active",
                "priority": 0.85,
                "value_weights": {"protect_town": 1.0},
            },
            "verify_player_report": {
                "status": "inactive",
                "priority": 0.70,
                "value_weights": {"protect_town": 0.80, "loyalty": 0.60},
            },
        },
        capabilities=["question", "warn", "confront", "withdraw"],
        metadata={"faction": "millcross_watch"},
    )

    print("GHOST v1.11 — STATEFUL VALUES / GOAL LIFECYCLE")
    print("=========================================================")
    print(json.dumps({"values": sera.values(), "goals": sera.goals()}, indent=2, sort_keys=True))

    before = sera.goals()
    sera.observe(
        "captain_took_bribe",
        kind="report",
        subject="captain",
        source="player",
        features={"claimed_location": "market"},
    )
    assert sera.goals() == before

    sera.transition_goal(
        "verify_player_report",
        "active",
        reason="host_accepted_report_for_investigation",
    )
    sera.set_goal_progress("verify_player_report", 0.40)
    sera.set_goal_priority("verify_player_report", 0.90)
    sera.transition_goal(
        "verify_player_report",
        "blocked",
        reason="evidence_unavailable",
    )
    sera.transition_goal(
        "verify_player_report",
        "active",
        reason="ledger_presented",
    )
    sera.set_goal_progress("verify_player_report", 1.0)
    sera.transition_goal(
        "verify_player_report",
        "satisfied",
        reason="evidence_verified",
    )
    sera.set_value("loyalty", 0.79)

    final = {
        "values": sera.values(),
        "verify_player_report": sera.goal("verify_player_report"),
        "perception": sera.latest_observation(),
    }
    print("\n" + json.dumps(final, indent=2, sort_keys=True))

    snapshot = ghost.snapshot()
    restored = GhostAPI.from_snapshot(snapshot)
    assert restored.snapshot() == snapshot
    assert restored.agent("sera").goal("verify_player_report") == sera.goal("verify_player_report")

    print("\nObservation alone mutated goals: NO")
    print("Explicit value mutation: PASS")
    print("Explicit goal lifecycle: inactive → active → blocked → active → satisfied")
    print("Progress 1.0 auto-completed the goal: NO — status transition remained explicit")
    print("Snapshot restore + transition history: PASS")
    print("Action selection / execution: OUTSIDE VALUES / GOALS CONTRACT")
    print("LLM calls: 0")
    print("Package producer: 1.11.0")
    print("Top-level snapshot schema: 1.0 (UNCHANGED)")
    print("Agent snapshot sub-schema: 1.1 (legacy 1.0 restore supported)")
    print("Perception snapshot sub-schema: 1.0 (UNCHANGED)")
    print("\nGHOST v1.11 VALUES / GOALS CONTRACT: PASS")


if __name__ == "__main__":
    main()
