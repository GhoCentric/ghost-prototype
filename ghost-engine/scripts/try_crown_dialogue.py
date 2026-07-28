
from __future__ import annotations

import os

from ghost.examples.ghost_revolution.dev_shortcuts import (
    create_endgame_shortcut,
)
from ghost.examples.ghost_revolution.llm_bridge import (
    GhostRevolutionLLMBridge,
    OpenAIResponsesClient,
    build_crown_voice_contract_prompt,
    config_from_environment,
    estimate_llm_cost,
    generate_crown_adapter_fallback_dialogue,
)


def main() -> None:
    print("=== TRY CROWN DIALOGUE ===")
    print("Builds one Crown Loop dialogue packet directly.")
    print("Ghost owns state. Provider only renders dialogue.")
    print()

    shortcut = os.environ.get("GHOST_CROWN_SHORTCUT", "crown_execute")
    town = os.environ.get("GHOST_CROWN_TOWN", "Ashfield")
    location = os.environ.get("GHOST_CROWN_LOCATION", "public_event")
    npc = os.environ.get("GHOST_CROWN_NPC", "town_elder")

    game, _ = create_endgame_shortcut(shortcut)

    packet = game.crown_npc_interaction(
        town,
        location,
        npc,
        "open_dialogue",
    )

    print("=== DIALOGUE TARGET ===")
    print(f"shortcut: {shortcut}")
    print(f"town: {town}")
    print(f"location: {location}")
    print(f"npc: {npc}")
    print()

    fallback = generate_crown_adapter_fallback_dialogue(packet)

    print("=== ADAPTER FALLBACK ===")
    print(fallback["text"])
    print()
    print(f"provider_called: {fallback['provider_called']}")
    print(f"provider: {fallback['provider']}")
    print()

    config = config_from_environment()
    prompt = build_crown_voice_contract_prompt(packet)
    estimate = estimate_llm_cost(prompt, config=config)

    print("=== REQUEST ESTIMATE ===")
    print(f"model: {estimate.get('model')}")
    print(
        "tokens: "
        f"{estimate.get('input_tokens_estimate')} in / "
        f"{estimate.get('output_tokens_estimate')} out"
    )
    print(f"max_output_tokens: {estimate.get('max_output_tokens')}")
    print(f"estimated_cost: {estimate.get('total_cost_estimate')}")
    print(f"pricing_note: {estimate.get('pricing_note')}")
    print()

    if os.environ.get("GHOST_REAL_LLM") != "1":
        print("=== REAL PROVIDER SKIPPED ===")
        print("Set GHOST_REAL_LLM=1 and OPENAI_API_KEY to call the provider once.")
        return

    api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is required when GHOST_REAL_LLM=1."
        )

    print("=== CALLING REAL PROVIDER ONCE ===")

    bridge = GhostRevolutionLLMBridge(
        client=OpenAIResponsesClient(),
        config=config,
    )

    result = bridge.generate_crown_dialogue(packet)

    print()
    print("=== REAL PROVIDER RESPONSE ===")
    print(result.get("text"))
    print()
    print(f"provider_called: {result.get('provider_called')}")
    print(f"model: {estimate.get('model')}")
    print(f"estimated_cost: {estimate.get('total_cost_estimate')}")


if __name__ == "__main__":
    main()
