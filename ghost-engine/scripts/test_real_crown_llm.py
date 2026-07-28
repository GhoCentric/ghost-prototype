
"""
Manual real-provider smoke test for Ghost Revolution Crown Loop LLM.

This script is intentionally not wired into the game menu.

It only calls the real provider when BOTH are true:

    OPENAI_API_KEY is set
    GHOST_REAL_LLM=1 is set

Run from the repo root:

    cd "/storage/emulated/0/ghost-engine"

Dry run, no provider call:

    python scripts/test_real_crown_llm.py

Real call:

    OPENAI_API_KEY="your_key" \
    GHOST_REAL_LLM=1 \
    python scripts/test_real_crown_llm.py

Optional model override:

    OPENAI_MODEL="gpt-4.1-mini" \
    OPENAI_API_KEY="your_key" \
    GHOST_REAL_LLM=1 \
    python scripts/test_real_crown_llm.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from ghost.examples.ghost_revolution.dev_shortcuts import (  # noqa: E402
    create_endgame_shortcut,
)
from ghost.examples.ghost_revolution.llm_bridge import (  # noqa: E402
    GhostRevolutionLLMBridge,
    LLMBridgeConfig,
    OpenAIResponsesClient,
)


REAL_CALL_FLAG = "GHOST_REAL_LLM"


def build_crown_packet() -> dict:
    game, _packet = create_endgame_shortcut("crown_execute")

    return game.crown_npc_interaction(
        "Ashfield",
        "public_event",
        "town_elder",
        "open_dialogue",
    )


def print_cost_estimate(result: dict) -> None:
    estimate = result.get("cost_estimate", {})

    print()
    print("=== ESTIMATED REQUEST SIZE ===")
    print(
        "model:",
        estimate.get("model"),
    )
    print(
        "input_tokens_estimate:",
        estimate.get("input_tokens_estimate"),
    )
    print(
        "output_tokens_estimate:",
        estimate.get("output_tokens_estimate"),
    )
    print(
        "requested_output_tokens:",
        estimate.get("requested_output_tokens"),
    )
    print(
        "max_output_tokens:",
        estimate.get("max_output_tokens"),
    )
    print(
        "hard_max_output_tokens:",
        estimate.get("hard_max_output_tokens"),
    )
    print(
        "total_cost_estimate:",
        estimate.get("total_cost_estimate"),
    )

    warning = estimate.get("cost_warning")

    if warning:
        print("cost_warning:", warning)

    print(
        "pricing_note:",
        estimate.get("pricing_note"),
    )


def main() -> int:
    packet = build_crown_packet()

    config = LLMBridgeConfig(
        max_output_tokens=120,
        hard_max_output_tokens=150,
    )

    bridge = GhostRevolutionLLMBridge(
        client=OpenAIResponsesClient(),
        config=config,
    )

    prepared = bridge.prepare_crown_dialogue(packet)

    print("=== REAL CROWN LLM SMOKE TEST ===")
    print("This script is isolated from the normal game menu.")
    print("Ghost owns the deterministic state.")
    print("The provider only generates surface dialogue.")
    print_cost_estimate(prepared)

    print()
    print("=== PROMPT PREVIEW ===")
    print(prepared["prompt"])

    if os.getenv(REAL_CALL_FLAG) != "1":
        print()
        print("=== PROVIDER CALL SKIPPED ===")
        print(
            f"Set {REAL_CALL_FLAG}=1 and OPENAI_API_KEY "
            "to run one real provider call."
        )
        return 0

    if not os.getenv("OPENAI_API_KEY"):
        print()
        print("=== PROVIDER CALL BLOCKED ===")
        print("OPENAI_API_KEY is not set.")
        return 2

    print()
    print("=== CALLING REAL PROVIDER ONCE ===")

    result = bridge.generate_crown_dialogue(packet)

    print()
    print("=== PROVIDER RESPONSE ===")
    print(result["text"])

    print()
    print("provider_called:", result["provider_called"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
