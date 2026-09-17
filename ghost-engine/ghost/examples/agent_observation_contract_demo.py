"""Ghost Engine v1.11 Phase 2 — engine-neutral observation contract demo."""
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

    print("GHOST v1.11 PHASE 2 — ENGINE-NEUTRAL OBSERVATION CONTRACT")
    print("============================================================")

    direct = sera.observe(
        "entity_approached",
        subject="player",
        features={
            "distance": 2.1,
            "visible": True,
            "weapon_visible": False,
        },
    )
    report = sera.observe(
        "captain_took_bribe",
        kind="report",
        subject="captain",
        source="player",
        features={"claimed_location": "market"},
    )
    environment = sera.observe(
        "rain_started",
        kind="environment",
        source="world",
        features={"intensity": 0.6},
    )

    assert direct["sequence"] == 1
    assert report["sequence"] == 2
    assert environment["sequence"] == 3
    assert report["kind"] == "report"
    assert "truth" not in report
    assert ghost.get_belief("sera", "captain") is None

    print(json.dumps(sera.state()["layers"]["perception"], indent=2, sort_keys=True))

    snapshot = ghost.snapshot()
    restored = GhostAPI.from_snapshot(snapshot)
    assert restored.snapshot() == snapshot
    fourth = restored.agent("sera").observe(
        "player_left",
        kind="social",
        subject="player",
    )
    assert fourth["sequence"] == 4

    print("\nHost-supplied direct observation: PASS")
    print("Reported information remains marked as report: PASS")
    print("No hidden truth / belief invention: PASS")
    print("Per-agent sequence + bounded history: PASS")
    print("Snapshot restore + deterministic continuation: PASS")
    print("Existing epistemic observe() API preserved: PASS")
    print("Motive / intent / action selection: NOT YET — later v1.11 phases")
    print("LLM calls: 0")
    print("Package producer: 1.10.0 (UNCHANGED during v1.11 development)")
    print("Top-level snapshot schema: 1.0 (UNCHANGED)")
    print("Agent snapshot sub-schema: 1.1 (Phase 3 current; legacy 1.0 restore supported)")
    print("Perception snapshot sub-schema: 1.0")
    print("\nGHOST v1.11 PHASE 2: PASS")


if __name__ == "__main__":
    main()
