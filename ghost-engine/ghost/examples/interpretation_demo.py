"""Ghost v1.10.0 development demo: objective action != NPC interpretation."""

from __future__ import annotations

from copy import deepcopy

from ghost import GhostAPI


def _configure(api: GhostAPI) -> None:
    api.register_interpretation_agent(
        "sera",
        baseline={"betrayal": 0.10, "cooperation": 0.05},
        thresholds={
            "betrayal": {"enter": 0.60, "exit": 0.40},
            "cooperation": 0.70,
        },
        rules={
            "action:report_evidence_to_guards": {
                "betrayal": 0.15,
                "cooperation": 0.05,
            },
            "confidential_evidence_shared": {"betrayal": 0.70},
            "authority_involved": {"betrayal": 0.10},
        },
    )
    api.register_interpretation_agent(
        "rowan",
        baseline={"betrayal": 0.02, "cooperation": 0.12},
        thresholds={
            "betrayal": 0.75,
            "cooperation": 0.55,
        },
        rules={
            "action:report_evidence_to_guards": {"cooperation": 0.65},
            "confidential_evidence_shared": {"betrayal": 0.05},
            "authority_involved": {"cooperation": 0.10},
        },
    )


def _meaning_line(packet: dict) -> str:
    active = packet["active_interpretations"]
    state = packet["state"]
    if active:
        meanings = ", ".join(
            f"{name}={state['levels'][name]:.3f}"
            for name in active
        )
        return meanings
    strongest = packet["strongest_interpretation"]
    if strongest is None:
        return "no active interpretation"
    return f"no threshold crossed; strongest={strongest} {packet['strongest_level']:.3f}"


def run_demo() -> dict:
    ghost = GhostAPI()
    _configure(ghost)

    features = {
        "confidential_evidence_shared": 1.0,
        "authority_involved": 1.0,
    }
    sera = ghost.evaluate_action_meaning(
        "sera",
        "report_evidence_to_guards",
        features,
        source="player",
        provenance={"evidence_id": "millcross-ledger"},
    )
    rowan = ghost.evaluate_action_meaning(
        "rowan",
        "report_evidence_to_guards",
        features,
        source="player",
        provenance={"evidence_id": "millcross-ledger"},
    )

    accumulation = GhostAPI()
    accumulation.register_interpretation_agent(
        "merchant",
        baseline={"betrayal": 0.05},
        thresholds={"betrayal": {"enter": 0.60, "exit": 0.40}},
        rules={"small_breach": {"betrayal": 0.25}},
    )
    small_breaches = []
    for _ in range(4):
        packet = accumulation.evaluate_action_meaning(
            "merchant",
            "break_minor_promise",
            {"small_breach": 1.0},
            source="player",
        )
        small_breaches.append(packet)

    snapshot = ghost.snapshot()
    restored = GhostAPI.from_snapshot(deepcopy(snapshot))
    snapshot_match = restored.snapshot() == snapshot

    return {
        "sera": sera,
        "rowan": rowan,
        "small_breaches": small_breaches,
        "snapshot_match": snapshot_match,
    }


def main() -> None:
    result = run_demo()
    sera = result["sera"]
    rowan = result["rowan"]

    print("GHOST v1.10.0 DEVELOPMENT — NPC ACTION INTERPRETATION")
    print("=====================================================")
    print("No RNG. No LLM. Ghost does not choose the action.")
    print()
    print("OBJECTIVE ACTION")
    print("  player -> report_evidence_to_guards")
    print("  confidential_evidence_shared=1.0")
    print("  authority_involved=1.0")
    print()
    print("SAME ACTION, DIFFERENT NPC MEANING")
    print(f"  Sera:  {_meaning_line(sera)}")
    print(f"  Rowan: {_meaning_line(rowan)}")
    print()
    print("ACCUMULATED SMALL BREACHES")
    for index, packet in enumerate(result["small_breaches"], 1):
        level = packet["state"]["levels"]["betrayal"]
        active = "ACTIVE" if "betrayal" in packet["active_interpretations"] else "below threshold"
        print(f"  breach {index}: betrayal={level:.3f}  {active}")
    print()
    print("SNAPSHOT / RESTORE")
    print(f"  identical: {result['snapshot_match']}")
    print()
    print("The game defines what happened.")
    print("Each NPC's configured state defines what that action means to them.")


if __name__ == "__main__":
    main()
