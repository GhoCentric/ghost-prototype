"""Ghost Engine v1.11 Phase 1 — persistent agent identity foundation demo."""
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
        goals=["maintain_post", "identify_threats"],
        capabilities=["question", "warn", "confront", "withdraw"],
        metadata={"faction": "millcross_watch"},
    )

    print("GHOST v1.11 — PERSISTENT AGENT RUNTIME FOUNDATION")
    print("===========================================================")
    print(json.dumps(sera.state(), indent=2, sort_keys=True))

    snapshot = ghost.snapshot()
    restored = GhostAPI.from_snapshot(snapshot)
    assert restored.snapshot() == snapshot
    assert restored.agent("sera").state() == sera.state()

    print("\nSnapshot restore: PASS")
    print("Identity continuity: PASS")
    print("Existing cognitive layers: readable through one agent handle")
    print("Observation contract: AVAILABLE — see Phase 2 observation demo")
    print("Action selection / execution: OUTSIDE AGENT FOUNDATION")
    print("LLM calls: 0")
    print("Package producer: 1.11.0")
    print("Top-level snapshot schema: 1.0 (UNCHANGED)")
    print("Agent snapshot sub-schema: 1.1 (Phase 3 current; legacy 1.0 restore supported)")
    print("\nGHOST v1.11 AGENT RUNTIME FOUNDATION: PASS")


if __name__ == "__main__":
    main()
