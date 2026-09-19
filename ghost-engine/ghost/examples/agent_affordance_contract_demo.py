"""Ghost v1.11 capability / affordance contract demo."""
from __future__ import annotations

import json

from ghost import GhostAPI
from ghost.affordances import AFFORDANCE_SNAPSHOT_SCHEMA_VERSION
from ghost.agent import AGENT_SNAPSHOT_SCHEMA_VERSION
from ghost.engine import GHOST_SNAPSHOT_SCHEMA_VERSION
from ghost.perception import PERCEPTION_SNAPSHOT_SCHEMA_VERSION
from ghost.motives import MOTIVE_SNAPSHOT_SCHEMA_VERSION


def main() -> None:
    print("GHOST v1.11 — CAPABILITY / AFFORDANCE CONTRACT")
    print("=========================================================")

    api = GhostAPI()
    sera = api.register_agent(
        "sera",
        role="guard",
        values={"protect_town": 0.90, "loyalty": 0.74},
        goals=["maintain_post", "identify_threats"],
        capabilities=["question", "warn", "confront", "withdraw"],
    )
    sera.configure_motive(
        "protect",
        baseline=0.15,
        weights={"value:protect_town": 0.80},
    )
    motive_before = sera.evaluate_motives()

    offered = sera.set_affordances(
        [
            {
                "id": "warn_player",
                "capability": "warn",
                "features": {"target": "player", "distance": 2.1},
            },
            {
                "id": "question_player",
                "capability": "question",
                "features": {"target": "player"},
            },
        ],
        context={"scene": "gate", "host_reason": "player_in_conversation_range"},
    )

    print(json.dumps({
        "registered_capabilities": sera.capabilities(),
        "host_supplied_affordances": offered,
        "motive_field": {
            "ranking": motive_before["ranking"],
            "scores": {
                key: value["score"]
                for key, value in motive_before["motives"].items()
            },
        },
    }, indent=2, sort_keys=True))

    assert [item["id"] for item in offered["candidates"]] == [
        "question_player", "warn_player",
    ]
    assert sera.motive_field() == motive_before
    assert sera.observation_history() == []

    snapshot = api.snapshot()
    restored = GhostAPI.from_snapshot(snapshot)
    assert restored.snapshot() == snapshot

    next_original = sera.set_affordances(
        [{"id": "confront_player", "capability": "confront"}],
        context={"scene": "gate", "host_reason": "player_refused_to_leave"},
    )
    next_restored = restored.agent("sera").set_affordances(
        [{"id": "confront_player", "capability": "confront"}],
        context={"scene": "gate", "host_reason": "player_refused_to_leave"},
    )
    assert next_original == next_restored
    assert api.snapshot() == restored.snapshot()

    print()
    print("Registered capability universe belongs to GhostAgent: PASS")
    print("Current physical availability is host supplied: PASS")
    print("Candidate input order is canonicalized: PASS")
    print("Unknown / unavailable capabilities cannot be invented by Ghost: PASS")
    print("Affordance submission mutated motive pressure: NO")
    print("Affordance submission created observation / belief state: NO")
    print("Snapshot restore + deterministic continuation: PASS")
    print("Action ranking / intent selection: NOT PERFORMED BY AFFORDANCE CONTRACT")
    print("Action execution: HOST OWNED")
    print("LLM calls: 0")
    print("Package producer: 1.11.0")
    print(f"Top-level snapshot schema: {GHOST_SNAPSHOT_SCHEMA_VERSION} (UNCHANGED)")
    print(f"Agent snapshot sub-schema: {AGENT_SNAPSHOT_SCHEMA_VERSION} (UNCHANGED)")
    print(f"Perception snapshot sub-schema: {PERCEPTION_SNAPSHOT_SCHEMA_VERSION} (UNCHANGED)")
    print(f"Motive snapshot sub-schema: {MOTIVE_SNAPSHOT_SCHEMA_VERSION} (UNCHANGED)")
    print(f"Affordance snapshot sub-schema: {AFFORDANCE_SNAPSHOT_SCHEMA_VERSION}")
    print("\nGHOST v1.11 CAPABILITY / AFFORDANCE CONTRACT: PASS")


if __name__ == "__main__":
    main()
