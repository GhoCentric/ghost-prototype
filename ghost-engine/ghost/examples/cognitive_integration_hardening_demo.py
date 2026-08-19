from __future__ import annotations

import copy

from ghost import GhostAPI


def build_runtime() -> GhostAPI:
    api = GhostAPI()
    api.register_emotional_agent(
        "sera",
        initial={"anger": 0.62, "fear": 0.28},
    )
    api.register_interpretation_agent(
        "sera",
        initial={"betrayal": 0.58, "cooperation": 0.22},
        rules={
            "action:report": {"betrayal": 0.45},
            "confidential_evidence_shared": {"betrayal": 0.35},
        },
    )
    api.register_attention_agent(
        "sera",
        initial_flow_pressure=0.92,
        flow_active=True,
    )
    return api


def main() -> None:
    print("GHOST v1.10.0 DEVELOPMENT — PHASE 6 COGNITIVE INTEGRATION HARDENING")
    print("=======================================================================")
    print("Emotion + interpretation remain persistent. Attention is read-only access.")

    api = build_runtime()
    api.apply_emotional_event("sera", "betrayal", source="player")
    api.evaluate_action_meaning(
        "sera",
        "report",
        features={"confidential_evidence_shared": 1.0},
        source="player",
    )

    bridge = api.persistent_salience("sera")
    print("\nCOHERENT SOURCE VIEW")
    print(f"  emotion revision:        {bridge['sources']['emotion']['revision']}")
    print(f"  interpretation revision: {bridge['sources']['interpretation']['revision']}")
    print(f"  dimensions:              {len(bridge['salience'])}")

    before_sources = (
        copy.deepcopy(api.emotional_state("sera")),
        copy.deepcopy(api.interpretation_state("sera")),
    )
    compressed = api.advance_attention_from_state(
        "sera",
        signals={"task_focus": 1.0, "repetition": 1.0, "stability": 1.0},
    )["attention"]
    print("\nFLOW-COMPRESSED ACCESS")
    print(f"  flow active:    {compressed['flow_active_after']}")
    print(f"  attention gain: {compressed['attention_gain']:.3f}")
    print(
        "  betrayal:      "
        f"{compressed['underlying_salience']['interpretation:betrayal']:.3f} -> "
        f"{compressed['attended_salience']['interpretation:betrayal']:.3f}"
    )
    print(
        "  sources unchanged: "
        f"{api.emotional_state('sera') == before_sources[0] and api.interpretation_state('sera') == before_sources[1]}"
    )

    before_failure = copy.deepcopy(api.snapshot())
    try:
        api.advance_attention_from_state("sera", signals={"threat": 9.0})
    except ValueError:
        pass
    print("\nFAILED-STEP ATOMICITY")
    print(f"  rejected step changed state: {api.snapshot() != before_failure}")

    breakthrough = api.advance_attention_from_state(
        "sera",
        signals={"threat": 1.0},
    )["attention"]
    print("\nBREAKTHROUGH")
    print(f"  breakthrough:   {breakthrough['breakthrough']}")
    print(f"  attention gain: {breakthrough['attention_gain']:.3f}")

    snapshot = api.snapshot()
    left = GhostAPI.from_snapshot(copy.deepcopy(snapshot))
    right = GhostAPI.from_snapshot(copy.deepcopy(snapshot))
    a = left.advance_attention_from_state("sera", signals={"novelty": 0.3})
    b = right.advance_attention_from_state("sera", signals={"novelty": 0.3})
    print("\nSNAPSHOT FORK REPLAY")
    print(f"  next packet identical: {a == b}")
    print(f"  next snapshot identical: {left.snapshot() == right.snapshot()}")

    print("\nNo RNG. No LLM. No bridge snapshot layer. No action selection.")
    print("Phase 6 hardens the integration boundary before the Git checkpoint.")


if __name__ == "__main__":
    main()
