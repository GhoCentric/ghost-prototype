
"""
Offline LLM bridge scaffold for Ghost Revolution.

This module does not call any external API by itself.

Ghost owns the deterministic world state.
The future LLM layer only receives a prepared packet and generates
surface dialogue from that packet.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Mapping, Any


DEFAULT_INPUT_COST_PER_MILLION = 0.15
DEFAULT_CACHED_INPUT_COST_PER_MILLION = 0.015
DEFAULT_OUTPUT_COST_PER_MILLION = 0.60
DEFAULT_OPENAI_MODEL = os.environ.get("GHOST_LLM_MODEL", "gpt-4.1-mini")
DEFAULT_MAX_OUTPUT_TOKENS = 220
HARD_MAX_OUTPUT_TOKENS = 300
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
OPENAI_MODEL_ENV = "OPENAI_MODEL"

STRATEGY_ROLE = "strategy"
NARRATION_ROLE = "narration"
AMBIENT_ROLE = "ambient"

ROLE_DEFAULTS = {
    STRATEGY_ROLE: {
        "model": "gpt-5.6-sol",
        "reasoning_effort": "medium",
        "model_env": "GHOST_LLM_STRATEGY_MODEL",
        "reasoning_env": "GHOST_LLM_STRATEGY_REASONING",
        "max_output_tokens": 768,
        "hard_max_output_tokens": 1024,
        "prompt_cache_key": "ghost-revolution-strategy-v180",
    },
    NARRATION_ROLE: {
        "model": "gpt-5.6-terra",
        "reasoning_effort": "none",
        "model_env": "GHOST_LLM_NARRATION_MODEL",
        "reasoning_env": "GHOST_LLM_NARRATION_REASONING",
        "max_output_tokens": 220,
        "hard_max_output_tokens": 300,
        "prompt_cache_key": "ghost-revolution-narration-v180",
    },
    AMBIENT_ROLE: {
        "model": "gpt-5.6-luna",
        "reasoning_effort": "none",
        "model_env": "GHOST_LLM_AMBIENT_MODEL",
        "reasoning_env": "GHOST_LLM_AMBIENT_REASONING",
        "max_output_tokens": 120,
        "hard_max_output_tokens": 180,
        "prompt_cache_key": "ghost-revolution-ambient-v180",
    },
}

MODEL_TOKEN_PRICING = {
    "gpt-5.6-sol": {
        "input": 5.00,
        "cached_input": 0.50,
        "output": 30.00,
    },
    "gpt-5.6-terra": {
        "input": 2.50,
        "cached_input": 0.25,
        "output": 15.00,
    },
    "gpt-5.6-luna": {
        "input": 1.00,
        "cached_input": 0.10,
        "output": 6.00,
    },
}

VALID_REASONING_EFFORTS = {
    "none",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
}


@dataclass(frozen=True)
class LLMBridgeConfig:
    model: str = DEFAULT_OPENAI_MODEL
    input_cost_per_million_tokens: float = (
        DEFAULT_INPUT_COST_PER_MILLION
    )
    cached_input_cost_per_million_tokens: float = (
        DEFAULT_CACHED_INPUT_COST_PER_MILLION
    )
    output_cost_per_million_tokens: float = (
        DEFAULT_OUTPUT_COST_PER_MILLION
    )
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    hard_max_output_tokens: int = HARD_MAX_OUTPUT_TOKENS
    reasoning_effort: str | None = None
    role: str = "generic"
    structured_output_name: str | None = None
    structured_output_schema: Mapping[str, Any] | None = None
    prompt_cache_key: str | None = None


def _pricing_for_model(model: str) -> dict[str, float] | None:
    normalized = str(model).strip().lower()

    for model_id, pricing in MODEL_TOKEN_PRICING.items():
        if normalized == model_id or normalized.startswith(model_id + "-"):
            return dict(pricing)

    return None


def _validated_reasoning_effort(value: Any) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip().lower()

    if normalized not in VALID_REASONING_EFFORTS:
        raise ValueError(
            "reasoning_effort must be one of: "
            + ", ".join(sorted(VALID_REASONING_EFFORTS))
        )

    return normalized


def config_for_role(
    role: str,
    *,
    base: LLMBridgeConfig | None = None,
) -> LLMBridgeConfig:
    normalized_role = str(role).strip().lower()

    if normalized_role not in ROLE_DEFAULTS:
        raise ValueError(
            "role must be strategy, narration, or ambient."
        )

    defaults = ROLE_DEFAULTS[normalized_role]
    active = base or LLMBridgeConfig()

    role_model = os.getenv(str(defaults["model_env"]))
    legacy_model = os.getenv(OPENAI_MODEL_ENV) or os.getenv(
        "GHOST_LLM_MODEL"
    )
    model = role_model or legacy_model or str(defaults["model"])

    reasoning_value = os.getenv(
        str(defaults["reasoning_env"]),
        str(defaults["reasoning_effort"]),
    )
    reasoning_effort = _validated_reasoning_effort(reasoning_value)

    pricing = _pricing_for_model(model)

    if pricing is None:
        input_price = active.input_cost_per_million_tokens
        cached_input_price = (
            active.cached_input_cost_per_million_tokens
        )
        output_price = active.output_cost_per_million_tokens
    else:
        input_price = pricing["input"]
        cached_input_price = pricing["cached_input"]
        output_price = pricing["output"]

    if base is None:
        max_output_tokens = int(defaults["max_output_tokens"])
        hard_max_output_tokens = int(defaults["hard_max_output_tokens"])
        prompt_cache_key = str(defaults["prompt_cache_key"])
    else:
        max_output_tokens = active.max_output_tokens
        hard_max_output_tokens = active.hard_max_output_tokens
        prompt_cache_key = (
            active.prompt_cache_key
            or str(defaults["prompt_cache_key"])
        )

    return LLMBridgeConfig(
        model=model,
        input_cost_per_million_tokens=input_price,
        cached_input_cost_per_million_tokens=cached_input_price,
        output_cost_per_million_tokens=output_price,
        max_output_tokens=max_output_tokens,
        hard_max_output_tokens=hard_max_output_tokens,
        reasoning_effort=reasoning_effort,
        role=normalized_role,
        structured_output_name=active.structured_output_name,
        structured_output_schema=active.structured_output_schema,
        prompt_cache_key=prompt_cache_key,
    )


def rough_token_count(text: str) -> int:
    if not text:
        return 0

    return max(1, (len(text) + 3) // 4)


def estimate_llm_cost(
    prompt: str,
    *,
    expected_output_tokens: int = 220,
    config: LLMBridgeConfig | None = None,
) -> dict:
    active_config = config or LLMBridgeConfig()
    input_tokens = rough_token_count(prompt)
    requested_output_tokens = max(0, int(expected_output_tokens))
    output_tokens = min(
        requested_output_tokens,
        effective_output_token_limit(active_config),
    )

    input_cost = (
        input_tokens
        / 1_000_000
        * active_config.input_cost_per_million_tokens
    )

    output_cost = (
        output_tokens
        / 1_000_000
        * active_config.output_cost_per_million_tokens
    )

    warning = None

    if requested_output_tokens > output_tokens:
        warning = (
            "Output tokens capped by hard_max_output_tokens: "
            f"requested {requested_output_tokens}, capped {output_tokens}."
        )

    return {
        "model": active_config.model,
        "input_tokens_estimate": input_tokens,
        "output_tokens_estimate": output_tokens,
        "requested_output_tokens": requested_output_tokens,
        "max_output_tokens": active_config.max_output_tokens,
        "hard_max_output_tokens": active_config.hard_max_output_tokens,
        "input_cost_estimate": round(input_cost, 8),
        "output_cost_estimate": round(output_cost, 8),
        "total_cost_estimate": round(input_cost + output_cost, 8),
        "cost_warning": warning,
        "pricing_note": (
            "Rough estimate only. Update config with the "
            "provider's current per-million-token prices."
        ),
    }


def _nonnegative_int(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0

    return max(0, parsed)


def measured_llm_cost(
    usage: Mapping[str, Any] | None,
    *,
    config: LLMBridgeConfig,
    response_model: str | None = None,
) -> dict | None:
    if not isinstance(usage, Mapping):
        return None

    input_tokens = _nonnegative_int(usage.get("input_tokens"))
    output_tokens = _nonnegative_int(usage.get("output_tokens"))
    total_tokens = _nonnegative_int(usage.get("total_tokens"))

    input_details = usage.get("input_tokens_details")
    output_details = usage.get("output_tokens_details")

    if not isinstance(input_details, Mapping):
        input_details = {}

    if not isinstance(output_details, Mapping):
        output_details = {}

    cached_input_tokens = min(
        input_tokens,
        _nonnegative_int(input_details.get("cached_tokens")),
    )
    uncached_input_tokens = input_tokens - cached_input_tokens
    reasoning_tokens = min(
        output_tokens,
        _nonnegative_int(output_details.get("reasoning_tokens")),
    )

    model = response_model or config.model
    pricing = _pricing_for_model(model)

    if pricing is None:
        input_price = config.input_cost_per_million_tokens
        cached_input_price = (
            config.cached_input_cost_per_million_tokens
        )
        output_price = config.output_cost_per_million_tokens
    else:
        input_price = pricing["input"]
        cached_input_price = pricing["cached_input"]
        output_price = pricing["output"]

    uncached_input_cost = (
        uncached_input_tokens / 1_000_000 * input_price
    )
    cached_input_cost = (
        cached_input_tokens / 1_000_000 * cached_input_price
    )
    output_cost = output_tokens / 1_000_000 * output_price
    total_cost = uncached_input_cost + cached_input_cost + output_cost

    return {
        "source": "response_usage",
        "model": model,
        "role": config.role,
        "reasoning_effort": config.reasoning_effort,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "uncached_input_tokens": uncached_input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "visible_output_tokens": max(0, output_tokens - reasoning_tokens),
        "total_tokens": total_tokens or input_tokens + output_tokens,
        "uncached_input_cost": round(uncached_input_cost, 8),
        "cached_input_cost": round(cached_input_cost, 8),
        "output_cost": round(output_cost, 8),
        "total_cost": round(total_cost, 8),
        "pricing_note": (
            "Measured from Responses API token usage. "
            "Excludes non-token fees and unusual service-tier adjustments."
        ),
    }


def normalize_client_result(value: Any) -> dict:
    if isinstance(value, str):
        return {
            "text": value,
            "usage": None,
            "model": None,
            "response_id": None,
        }

    if isinstance(value, Mapping):
        text = value.get("text", value.get("output_text", ""))

        return {
            "text": str(text or ""),
            "usage": value.get("usage"),
            "model": value.get("model"),
            "response_id": value.get("response_id", value.get("id")),
        }

    return {
        "text": str(value),
        "usage": None,
        "model": None,
        "response_id": None,
    }


def _require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping.")

    return value


def build_crown_loop_prompt(packet: Mapping[str, Any]) -> str:
    packet = _require_mapping(packet, "packet")

    llm_context = _require_mapping(
        packet.get("llm_context"),
        "packet['llm_context']",
    )

    ruler_profile = _require_mapping(
        llm_context.get("ruler_profile"),
        "llm_context['ruler_profile']",
    )

    npc = llm_context.get("npc")

    if npc is None:
        available_npcs = llm_context.get("available_npcs", ())

        if available_npcs:
            npc = tuple(available_npcs)[0]
        else:
            npc = {
                "name": "Unknown NPC",
                "role": "unknown",
                "reaction": "unknown",
            }

    npc = _require_mapping(npc, "npc")

    world_numbers = llm_context.get("world_numbers")

    if not isinstance(world_numbers, Mapping):
        world_numbers = {
            "followers": ruler_profile.get("followers"),
            "food": ruler_profile.get("food"),
            "gold": ruler_profile.get("gold"),
            "weapon_caches": ruler_profile.get("weapon_caches"),
            "armor": ruler_profile.get("armor"),
            "heat": ruler_profile.get("heat"),
            "guards_defeated": ruler_profile.get(
                "guards_defeated"
            ),
            "king_control": ruler_profile.get("king_control"),
        }

    town_memory = llm_context.get("town_memory")

    if not town_memory:
        town_memory_lines = [
            "- No confirmed town memories provided.",
            "- Do not invent past town events.",
        ]
    else:
        town_memory_lines = [
            f"- {memory}"
            for memory in town_memory
        ]

    npc_history = llm_context.get("npc_history")

    if not npc_history:
        npc_history_lines = [
            "- No direct prior conversation recorded.",
            (
                "- NPC is reacting from public reputation, "
                "role, and town context only."
            ),
        ]
    else:
        npc_history_lines = [
            f"- {history}"
            for history in npc_history
        ]

    reaction = npc.get("reaction")

    reaction_meanings = {
        "uncertainty": (
            "Cautious respect mixed with unresolved fear. "
            "The NPC should not pledge full loyalty yet, "
            "and should not openly rebel."
        ),
        "fear": (
            "Fearful and guarded. The NPC should avoid open "
            "defiance but may sound tense or careful."
        ),
        "trust": (
            "Respectful and hopeful, but still grounded in "
            "what the NPC could know."
        ),
        "resentment": (
            "Bitter or suspicious. The NPC may challenge the "
            "player, but should not invent crimes."
        ),
    }

    reaction_meaning = reaction_meanings.get(
        reaction,
        (
            "React according to the named reaction, but do not "
            "invent facts beyond the packet."
        ),
    )

    lines = [
        "You are generating dialogue for Ghost Revolution.",
        "",
        "Hard rule:",
        "- Ghost owns the deterministic world state.",
        "- Do not invent new world facts.",
        "- Do not treat spoken claims as automatic truth.",
        (
            "- React through the NPC's role, memory, fear, "
            "trust, and uncertainty."
        ),
        "",
        "Scene:",
        f"- Town: {llm_context.get('town')}",
        f"- Location: {llm_context.get('location')}",
        f"- Mode: {llm_context.get('mode')}",
        "",
        "NPC:",
        f"- Name: {npc.get('name')}",
        f"- Role: {npc.get('role')}",
        f"- Reaction: {reaction}",
        f"- Dialogue hook: {npc.get('dialogue_hook')}",
        "",
        "Reaction meaning:",
        f"- {reaction_meaning}",
        "",
        "Ruler profile:",
        f"- Rule profile: {ruler_profile.get('rule')}",
        f"- Crown fate: {ruler_profile.get('fate')}",
        f"- Fear score: {ruler_profile.get('fear_score')}",
        f"- Mercy score: {ruler_profile.get('mercy_score')}",
        "",
        "World numbers:",
        f"- Followers: {world_numbers.get('followers')}",
        f"- Food: {world_numbers.get('food')}",
        f"- Gold: {world_numbers.get('gold')}",
        f"- Weapon caches: {world_numbers.get('weapon_caches')}",
        f"- Armor: {world_numbers.get('armor')}",
        f"- Heat: {world_numbers.get('heat')}",
        f"- Guards defeated: {world_numbers.get('guards_defeated')}",
        f"- King control: {world_numbers.get('king_control')}",
        "",
        "Town memory:",
        *town_memory_lines,
        "",
        "NPC known history with player:",
        *npc_history_lines,
        "",
        "NPC knowledge limits:",
        "- NPC does not know exact scores or hidden counters.",
        "- NPC must not mention fear score, mercy score, heat, or king_control.",
        (
            "- NPC must not know the exact number of weapon caches "
            "unless town memory says those caches are public."
        ),
        (
            "- NPC may know public outcomes: the old king is gone, "
            "the player took the crown, guards were defeated, "
            "and towns are watching."
        ),
        (
            "- NPC may suspect armed support exists, but should not "
            "know exact hidden logistics."
        ),
        (
            "- NPC must not claim a personal meeting, promise, rescue, "
            "betrayal, massacre, or miracle unless the packet provides it."
        ),
        "",
        "Output format:",
        "- Return only the NPC dialogue line.",
        "- No speaker label.",
        "- No explanation.",
        "- No markdown.",
        "- Maximum 60 words.",
        "",
        "Player-visible task:",
        "Write 1 short NPC response.",
        "Keep it grounded in the packet above.",
        (
            "Do not mention scores directly unless the NPC would "
            "naturally say it."
        ),
        "Do not make the NPC all-knowing.",
    ]

    return "\n".join(lines)


def effective_output_token_limit(
    config: LLMBridgeConfig,
) -> int:
    requested = max(0, int(config.max_output_tokens))
    hard_cap = max(1, int(config.hard_max_output_tokens))

    return min(requested, hard_cap)


def config_from_environment(
    *,
    base: LLMBridgeConfig | None = None,
) -> LLMBridgeConfig:
    active = base or LLMBridgeConfig()
    if active.role in ROLE_DEFAULTS:
        model = active.model
    else:
        model = os.getenv(OPENAI_MODEL_ENV, active.model)
    pricing = _pricing_for_model(model)

    if pricing is None:
        input_price = active.input_cost_per_million_tokens
        cached_input_price = (
            active.cached_input_cost_per_million_tokens
        )
        output_price = active.output_cost_per_million_tokens
    else:
        input_price = pricing["input"]
        cached_input_price = pricing["cached_input"]
        output_price = pricing["output"]

    if active.role in ROLE_DEFAULTS:
        reasoning_effort = active.reasoning_effort
    else:
        reasoning_effort = _validated_reasoning_effort(
            os.getenv(
                "GHOST_LLM_REASONING_EFFORT",
                active.reasoning_effort,
            )
        )

    return LLMBridgeConfig(
        model=model,
        input_cost_per_million_tokens=input_price,
        cached_input_cost_per_million_tokens=cached_input_price,
        output_cost_per_million_tokens=output_price,
        max_output_tokens=active.max_output_tokens,
        hard_max_output_tokens=active.hard_max_output_tokens,
        reasoning_effort=reasoning_effort,
        role=active.role,
        structured_output_name=active.structured_output_name,
        structured_output_schema=active.structured_output_schema,
        prompt_cache_key=active.prompt_cache_key,
    )

class NullLLMClient:
    """
    Safe local client used by tests and demos.

    It proves the bridge wiring without sending data anywhere.
    """

    def __call__(
        self,
        prompt: str,
        *,
        config: LLMBridgeConfig,
    ) -> str:
        return (
            "[LLM disabled] "
            "Prompt is ready for a provider, but no external "
            "model was called."
        )


class DeterministicCrownMockClient:
    """
    Local deterministic Crown Loop dialogue mock.

    This client never calls a network provider.
    It is useful for testing the Crown Loop dialogue path while
    OpenAI billing, API quota, or provider access is unavailable.

    The mock reads only the prompt text and returns one grounded
    NPC dialogue line.
    """

    provider_name: str = "deterministic_crown_mock"

    def __call__(
        self,
        prompt: str,
        *,
        config: LLMBridgeConfig,
    ) -> str:
        del config

        def prompt_value(label: str) -> str:
            prefix = f"- {label}:"

            for raw_line in prompt.splitlines():
                line = raw_line.strip()

                if line.startswith(prefix):
                    return line[len(prefix):].strip().lower()

            return ""

        reaction = prompt_value("Reaction")
        fate = prompt_value("Crown fate")
        rule = prompt_value("Rule profile")

        if fate == "execute_king" and reaction == "uncertainty":
            return (
                "You ended the old king's rule, and Ashfield sees food "
                "in the stores, but an execution leaves a shadow. We "
                "will not cheer blindly, and we will not rise against "
                "you tonight. Rule carefully, and let your crown prove "
                "what your blade cannot."
            )

        if fate == "jail_king" and reaction in {"trust", "uncertainty"}:
            return (
                "Ashfield has seen enough cruelty from crowns. Sparing "
                "the old king does not make you weak; it gives the town "
                "a reason to hope this rule may be different. Hope is "
                "not loyalty yet, but it is a beginning."
            )

        if rule == "feared" or reaction == "fear":
            return (
                "Ashfield will not test your crown tonight. The streets "
                "are quiet because people are careful, not because their "
                "hearts are settled. Rule with more than fear, or fear "
                "will be the only thing that answers you."
            )

        if rule == "trusted" or reaction == "trust":
            return (
                "People are watching you with cautious hope. Food reached "
                "homes, the old rule has ended, and the town can breathe "
                "again. Keep your promises plain and your hand steady, "
                "and Ashfield may learn to call you king."
            )

        return (
            "Ashfield has heard enough to listen, but not enough to kneel "
            "without question. The old king is gone, the crown is yours, "
            "and every town is waiting to see whether your rule brings "
            "shelter or another shadow."
        )

class OpenAIResponsesClient:
    """
    Optional real OpenAI Responses API client.

    This client is never used unless explicitly passed into
    GhostRevolutionLLMBridge.

    It reads OPENAI_API_KEY from the environment and refuses to run
    without it.

    This implementation uses direct HTTPS through httpx so Android /
    Pydroid does not need the newer openai Python SDK or jiter.
    """

    endpoint: str = "https://api.openai.com/v1/responses"

    def __init__(
        self,
        api_key_env: str = OPENAI_API_KEY_ENV,
        timeout_seconds: float = 90.0,
    ) -> None:
        self.api_key_env = api_key_env
        self.timeout_seconds = timeout_seconds

    def __call__(
        self,
        prompt: str,
        *,
        config: LLMBridgeConfig,
    ) -> dict:
        api_key = os.getenv(self.api_key_env)

        if not api_key:
            raise RuntimeError(
                f"{self.api_key_env} is not set. "
                "The real OpenAI client is off by default."
            )

        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError(
                "httpx is required for OpenAIResponsesClient."
            ) from exc

        active_config = config_from_environment(
            base=config,
        )

        payload = {
            "model": active_config.model,
            "input": prompt,
            "max_output_tokens": effective_output_token_limit(
                active_config
            ),
            "store": False,
        }

        if active_config.prompt_cache_key:
            payload["prompt_cache_key"] = active_config.prompt_cache_key

        if active_config.reasoning_effort is not None:
            payload["reasoning"] = {
                "effort": active_config.reasoning_effort,
            }

        if (
            active_config.structured_output_name
            and isinstance(
                active_config.structured_output_schema,
                Mapping,
            )
        ):
            payload["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": active_config.structured_output_name,
                    "strict": True,
                    "schema": dict(
                        active_config.structured_output_schema
                    ),
                }
            }

        response = httpx.post(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout_seconds,
        )

        if response.status_code >= 400:
            raise RuntimeError(
                "OpenAI Responses API request failed "
                f"with HTTP {response.status_code}: "
                f"{response.text}"
            )

        data = response.json()

        output_text = data.get("output_text")
        parts = []

        if not output_text:
            for item in data.get("output", []):
                for block in item.get("content", []):
                    text = block.get("text")

                    if text:
                        parts.append(text)

            if parts:
                output_text = "\n".join(parts)

        if not output_text:
            output_text = str(data)

        return {
            "text": output_text,
            "usage": data.get("usage"),
            "model": data.get("model", active_config.model),
            "response_id": data.get("id"),
        }




KING_FIGHT_MARTIAL_TELL_PROFILES = {
    "royal_lunge": {
        "mechanical_truth": "committed center-line thrust",
        "safe_rendering_space": (
            "rear heel plants",
            "point lines up with the sternum",
            "front shoulder narrows behind the guard",
            "hips drive straight down the center",
            "weight commits forward before the blade arrives",
        ),
    },
    "crown_guard": {
        "mechanical_truth": "closed guard baiting direct pressure",
        "safe_rendering_space": (
            "blade stays high and still",
            "elbows lock tight behind the royal guard",
            "front foot refuses to give ground",
            "the opening looks too clean",
            "his shoulders wait instead of chase",
        ),
    },
    "overextended_recovery": {
        "mechanical_truth": "late recovery after overcommitted cut",
        "safe_rendering_space": (
            "cut carries past the center",
            "crown-side shoulder hangs open",
            "rear foot drags before his guard returns",
            "wrist turns late after the swing",
            "breathing breaks for one exposed beat",
        ),
    },
    "shield_wall": {
        "mechanical_truth": "closed shield wall",
        "safe_rendering_space": (
            "shield edge plants into the stone",
            "knees settle behind the wall",
            "blade waits behind the rim",
            "a direct cut has nowhere to land",
        ),
    },
    "champion_lunge": {
        "mechanical_truth": "armored launch into a straight attack",
        "safe_rendering_space": (
            "helmet dips before the charge",
            "rear leg coils under the armor",
            "shield shoulder turns into the line",
            "blade point fixes before he launches",
        ),
    },
    "wide_execution": {
        "mechanical_truth": "wide committed execution cut",
        "safe_rendering_space": (
            "blade circles outside the shoulder",
            "hips open before the cut falls",
            "shield pulls away from the center",
            "the swing needs room before it bites",
        ),
    },
    "open_recovery": {
        "mechanical_truth": "late guard recovery",
        "safe_rendering_space": (
            "ash drags under the back foot",
            "shield returns a breath too late",
            "blade hangs low after the last cut",
            "armor turns before the guard closes",
        ),
    },
}

KING_FIGHT_VOICE_CONTRACT = (
    "Write one vivid, cinematic second-person fight beat.",
    "Keep it tight: one or two complete sentences, 35 to 55 words.",
    "End with a complete sentence. Never trail off mid-thought.",
    "Do not sound like a debug log, placeholder, or tired narrator.",
    "Narrate only the exchange Ghost just resolved.",
    "Describe only the current packet's move and result.",
    "Treat facts.resolved_exchange_truth as authoritative.",
    "The enemy owns facts.intent and facts.martial_tell_profile.",
    "The player performs only the move named in "
    "facts.resolved_exchange_truth.player_move.",
    "Preserve the exact actor, action, target, and damage direction "
    "in facts.resolved_exchange_truth.",
    "Never assign the enemy's shield, guard, posture, or intent "
    "to the player.",
    "Do not give the player a shield unless "
    "facts.resolved_exchange_truth.player_uses_shield_in_this_exchange "
    "is true.",
    "Never replay a previous attack, defense, or setup.",
    "For king_forced_response, narrate only the current "
    "recovery move and its resolved effect.",
    "Do not combine a previous exchange with the current one.",
    "Do not narrate facts.tell as if it already happened.",
    "The UI will print the next tell separately, so do not include the next tell unless facts.outcome is a transition or ending.",
    "Do not merely copy facts.message or facts.tell word for word.",
    "Use concrete blade, footwork, smoke, heat, balance, and pressure.",
    "Avoid vague destiny, generic tension, and repeated flame filler.",
    "You may render combat mechanics with fresh medieval combat language, but do not change the mechanic and must not create a new intent.",
    "Do not assign enemy tell body cues to the player.",
    "If facts.king_defense exists, narrate the king's parry or deflect as a resolved reaction, not as a tell.",
    "If facts.parry_opening exists, treat the player's parry as control that creates or spends an opening, not direct damage.",
    "If facts.forced_response exists, mention the player's restricted recovery without adding new options.",
    "If facts.ending exists, treat it as final and decisive.",
    "Do not say the outcome is uncertain unless facts.outcome says it is.",
    "Do not decide damage, survival, death, victory, or state.",
    "Only describe the packet Ghost already resolved.",
)

def build_king_fight_stance_packet(
    packet: Mapping[str, Any],
) -> dict:
    safe_packet = packet if isinstance(packet, Mapping) else {}
    exchange = safe_packet.get("exchange")

    if not isinstance(exchange, Mapping):
        exchange = {}

    outcome = safe_packet.get("outcome")
    stage = safe_packet.get("stage")
    is_forced_resolution = (
        outcome == "king_forced_response"
    )

    intent = exchange.get("intent")
    move = exchange.get("move")
    result = exchange.get("result")

    reaction_plan = exchange.get(
        "opponent_reaction_plan"
    )

    reaction_plan_label = exchange.get(
        "opponent_reaction_plan_label"
    )

    reaction_plan_predictive = exchange.get(
        "reaction_plan_predictive"
    )

    reaction_plan_matched = exchange.get(
        "reaction_plan_matched"
    )

    reaction_plan_missed = exchange.get(
        "reaction_plan_missed"
    )

    reaction_miss_exposed_enemy = exchange.get(
        "reaction_miss_exposed_enemy"
    )

    resolution_source = exchange.get(
        "resolution_source"
    )

    intent_display_names = {
        "royal_lunge": "committed royal lunge",
        "crown_guard": "closed royal guard",
        "overextended_recovery": (
            "exposed recovery"
        ),
        "shield_wall": "shield wall",
        "champion_lunge": (
            "committed Champion lunge"
        ),
        "wide_execution": (
            "wide execution cut"
        ),
        "open_recovery": (
            "exposed recovery"
        ),
    }

    move_display_names = {
        "heavy": "heavy attack",
        "light": "light attack",
        "feint_heavy": (
            "heavy feint and follow-up"
        ),
        "feint_light": (
            "light feint and follow-up"
        ),
        "parry": "parry",
        "deflect": "deflection",
        "dodge": "dodge",
    }

    intent_display_name = (
        intent_display_names.get(
            intent,
            "committed tactic",
        )
    )

    move_display_name = (
        move_display_names.get(
            move,
            "response",
        )
    )

    if stage == "elite_knight":
        enemy_actor = "elite_knight"
        enemy_display_name = "the King's Champion"
        enemy_damage = exchange.get(
            "elite_knight_damage",
            0,
        )
    else:
        enemy_actor = "king"
        enemy_display_name = "the king"
        enemy_damage = exchange.get(
            "king_damage",
            0,
        )

    if not isinstance(
        enemy_damage,
        (int, float),
    ):
        enemy_damage = 0

    player_damage = exchange.get(
        "player_damage",
        0,
    )

    if not isinstance(
        player_damage,
        (int, float),
    ):
        player_damage = 0

    player_uses_shield = False

    enemy_uses_shield = (
        stage == "elite_knight"
        and intent == "shield_wall"
    )

    damage_target = (
        enemy_actor
        if enemy_damage > 0
        else None
    )

    required_actor_action_target = (
        exchange.get("message")
    )

    if resolution_source == "reaction_plan":
        required_actor_action_target = (
            enemy_display_name.capitalize()
            + "'s precommitted physical counter "
            "matches the player's committed move and "
            "directly resolves the exchange. Narrate "
            "only the physical counter described here: "
            + str(
                exchange.get("message")
                or ""
            )
            + " Do not name the hidden reaction plan "
            "or any mechanical field."
        )

    elif resolution_source == "base_intent":
        required_actor_action_target = (
            enemy_display_name.capitalize()
            + "'s "
            + intent_display_name
            + " defeats the player's "
            + move_display_name
            + ". "
        )

        if reaction_plan_missed is True:
            required_actor_action_target += (
                "A separate hidden prediction did not "
                "match the player's move. It did not "
                "resolve the exchange. Do not mention "
                "or describe that hidden prediction."
            )
        else:
            required_actor_action_target += (
                "The underlying tactic alone resolves "
                "the exchange. Do not mention hidden "
                "reaction mechanics."
            )

    elif (
        result == "correct_read"
        and move in (
            "feint_heavy",
            "feint_light",
        )
    ):
        follow_up = (
            "heavy"
            if move == "feint_heavy"
            else "light"
        )

        if intent == "shield_wall":
            required_actor_action_target = (
                "The shield wall belongs to "
                + enemy_display_name
                + ". The player feints to draw "
                + enemy_display_name
                + "'s shield out of position, then lands a "
                + follow_up
                + " follow-up on "
                + enemy_display_name
                + ". The player does not use a shield."
            )
        elif intent == "crown_guard":
            required_actor_action_target = (
                "The closed royal guard belongs to "
                + enemy_display_name
                + ". The player feints to draw that guard "
                "out of position, then lands a "
                + follow_up
                + " follow-up on "
                + enemy_display_name
                + "."
            )
        else:
            required_actor_action_target = (
                "The player uses a feint to move "
                + enemy_display_name
                + "'s defense out of position, then lands a "
                + follow_up
                + " follow-up on "
                + enemy_display_name
                + "."
            )

    elif (
        result == "correct_read"
        and move == "dodge"
    ):
        required_actor_action_target = (
            "The player dodges "
            + enemy_display_name
            + "'s attack. The player takes no damage "
            "and does not damage the enemy."
        )

    elif (
        result == "correct_read"
        and move == "parry"
    ):
        required_actor_action_target = (
            "The player parries "
            + enemy_display_name
            + "'s committed attack and gains control "
            "of the exchange."
        )

    elif result == "king_hit":
        required_actor_action_target = (
            enemy_display_name.capitalize()
            + " hits the player. The player's attempted "
            "response does not damage the enemy."
        )

    elif result == "forced_recovered":
        required_actor_action_target = (
            "The player performs only the recovery move "
            + str(move)
            + " and escapes the forced follow-up. "
            "Do not replay the previous attack."
        )

    resolved_exchange_truth = {
        "player_actor": "player",
        "enemy_actor": enemy_actor,
        "enemy_display_name": enemy_display_name,
        "intent_owner": (
            enemy_actor
            if intent is not None
            else None
        ),
        "martial_profile_owner": (
            enemy_actor
            if intent is not None
            else None
        ),
        "player_move": move,
        "player_move_display_name": (
            move_display_name
        ),
        "enemy_intent": intent,
        "enemy_intent_display_name": (
            intent_display_name
        ),
        "result": result,
        "resolution_source": (
            resolution_source
        ),
        "opponent_reaction_plan": (
            reaction_plan
        ),
        "opponent_reaction_plan_label": (
            reaction_plan_label
        ),
        "reaction_plan_predictive": (
            reaction_plan_predictive
        ),
        "reaction_plan_matched": (
            reaction_plan_matched
        ),
        "reaction_plan_missed": (
            reaction_plan_missed
        ),
        "reaction_miss_exposed_enemy": (
            reaction_miss_exposed_enemy
        ),
        "damage_dealt_by_player": enemy_damage,
        "damage_target": damage_target,
        "damage_received_by_player": player_damage,
        "player_uses_shield_in_this_exchange": (
            player_uses_shield
        ),
        "enemy_uses_shield_in_this_exchange": (
            enemy_uses_shield
        ),
        "required_actor_action_target": (
            required_actor_action_target
        ),
        "forbidden_role_reversals": [
            "Do not assign the enemy intent to the player.",
            "Do not assign the enemy martial profile to the player.",
            "Do not describe the player using a shield in this exchange.",
            "Do not change who dealt or received damage.",
            (
                "Do not credit a hidden reaction plan "
                "with success unless "
                "reaction_plan_matched is true."
            ),
            (
                "When resolution_source is base_intent, "
                "describe the underlying tactic rather "
                "than an untriggered hidden reaction."
            ),
            (
                "Do not quote raw snake_case identifiers "
                "or internal resolution-source values in "
                "cinematic narration."
            ),
        ],
    }

    if outcome in ("player_death", "player_killed_by_king"):
        scene_moment = "king_fight_player_death"
    elif outcome == "clean_king_victory":
        scene_moment = "king_fight_clean_victory"
    elif outcome == "uncertain_king_fall":
        scene_moment = "king_fight_uncertain_victory"
    elif outcome == "castle_collapse":
        scene_moment = "king_fight_castle_collapse"
    elif stage == "elite_knight":
        scene_moment = "elite_knight_exchange"
    else:
        scene_moment = "king_fight_exchange"

    facts = {
        "voice_contract": list(KING_FIGHT_VOICE_CONTRACT),
        "outcome": outcome,
        "stage": stage,
        "move": exchange.get("move"),
        "expected": exchange.get("expected"),
        "intent": (
            None
            if is_forced_resolution
            else exchange.get("intent")
        ),
        "result": exchange.get("result"),
        "intent_display_name": (
            intent_display_name
        ),
        "move_display_name": (
            move_display_name
        ),
        "resolution_source": (
            resolution_source
        ),
        "opponent_reaction_plan": (
            reaction_plan
        ),
        "opponent_reaction_plan_label": (
            reaction_plan_label
        ),
        "reaction_plan_predictive": (
            reaction_plan_predictive
        ),
        "reaction_plan_matched": (
            reaction_plan_matched
        ),
        "reaction_plan_missed": (
            reaction_plan_missed
        ),
        "reaction_miss_exposed_enemy": (
            reaction_miss_exposed_enemy
        ),
        "king_damage": exchange.get("king_damage"),
        "elite_knight_damage": exchange.get(
            "elite_knight_damage"
        ),
        "enemy_damage": enemy_damage,
        "player_damage": player_damage,
        "resolved_exchange_truth": (
            resolved_exchange_truth
        ),
        "message": exchange.get("message"),
        "valid_responses": list(exchange.get("valid_responses", ())),
        "king_defense": (
            None
            if is_forced_resolution
            else exchange.get("king_defense")
        ),
        "parry_opening": (
            safe_packet.get("parry_opening")
            or exchange.get("parry_opening")
            or exchange.get("parry_opening_used")
        ),
        "forced_response": (
            None
            if is_forced_resolution
            else (
                safe_packet.get("forced_response")
                or exchange.get("forced_response")
            )
        ),
        "forced_recovery_resolved": (
            is_forced_resolution
        ),
        "martial_tell_profile": (
            None
            if (
                is_forced_resolution
                or not isinstance(
                    KING_FIGHT_MARTIAL_TELL_PROFILES.get(
                        intent
                    ),
                    Mapping,
                )
            )
            else {
                "owner_actor": enemy_actor,
                "owner_display_name": (
                    enemy_display_name
                ),
                "describes": (
                    "Enemy posture before the player's "
                    "resolved response."
                ),
                "mechanical_truth": (
                    KING_FIGHT_MARTIAL_TELL_PROFILES[
                        intent
                    ].get("mechanical_truth")
                ),
                "safe_rendering_space": list(
                    KING_FIGHT_MARTIAL_TELL_PROFILES[
                        intent
                    ].get(
                        "safe_rendering_space",
                        (),
                    )
                ),
                "ownership_rule": (
                    "Every posture cue in this profile "
                    "belongs to the enemy, never the player."
                ),
            }
        ),
        "player_health": safe_packet.get("player_health"),
        "king_health": safe_packet.get("king_health"),
        "elite_knight_health": safe_packet.get("elite_knight_health"),
        "castle_timer": safe_packet.get("castle_timer"),
        "clean_king_victory_possible": safe_packet.get(
            "clean_king_victory_possible"
        ),
        "tell": None,
        "upcoming_tell_hidden": (
            safe_packet.get("tell") is not None
        ),
        "note": safe_packet.get("note"),
        "narrative": safe_packet.get("narrative"),
        "ending": safe_packet.get("ending"),
    }

    return {
        "scene_moment": scene_moment,
        "facts": facts,
        "limits": {
            "must_follow_voice_contract": True,
            "narration_only": True,
            "no_speaker_label": True,
            "no_markdown": True,
            "max_words": 65,
            "no_new_damage": True,
            "no_new_deaths": True,
            "no_hidden_state_claims": True,
            "must_not_change_outcome": True,
            "player_text_cannot_create_hidden_facts": True,
            "may_not_mention": [
                "fear score",
                "mercy score",
                "heat",
                "king_control",
                "hidden counter",
                "hidden counters",
                "exact weapon caches",
                "royal_lunge",
                "crown_guard",
                "overextended_recovery",
                "shield_wall",
                "champion_lunge",
                "wide_execution",
                "open_recovery",
                "read_feint",
                "parry_heavy",
                "deflect_light",
                "dodge_heavy",
                "break_parry",
                "beat_deflect",
                "track_dodge",
                "hold_center",
                "genuine_opening",
                "commit_attack",
                "base_intent",
                "player_counter",
                "reaction_plan",
            ],
        },
        "state_owner": "Ghost",
        "llm_role": "fight_narrator_only",
    }


def build_king_fight_voice_contract_prompt(
    packet: Mapping[str, Any],
    recent_lines: Sequence[str] | None = None,
) -> str:
    from ghost.llm_adapter import build_voice_contract_prompt

    stance_packet = build_king_fight_stance_packet(packet)

    default_lines = list(KING_FIGHT_VOICE_CONTRACT)

    return build_voice_contract_prompt(
        stance_packet,
        npc_profile={
            "name": "Ghost Fight Narrator",
            "role": "fight_narrator",
        },
        recent_lines=list(recent_lines or default_lines),
    )


def generate_king_fight_adapter_fallback_narration(
    packet: Mapping[str, Any],
) -> dict:
    safe_packet = packet if isinstance(packet, Mapping) else {}
    exchange = safe_packet.get("exchange")

    if not isinstance(exchange, Mapping):
        exchange = {}

    outcome = safe_packet.get("outcome")
    result = exchange.get("result")
    move = exchange.get("move")
    message = exchange.get("message")
    tell = safe_packet.get("tell")
    ending = safe_packet.get("ending")

    resolution_source = exchange.get(
        "resolution_source"
    )

    reaction_plan = exchange.get(
        "opponent_reaction_plan"
    )

    reaction_plan_label = exchange.get(
        "opponent_reaction_plan_label"
    )

    reaction_plan_missed = exchange.get(
        "reaction_plan_missed"
    )

    stage = safe_packet.get("stage")
    intent = exchange.get("intent")

    if stage == "elite_knight":
        enemy_name = "The Champion"
    else:
        enemy_name = "The king"

    intent_phrases = {
        "royal_lunge": "committed royal lunge",
        "crown_guard": "closed royal guard",
        "overextended_recovery": (
            "recovery trap"
        ),
        "shield_wall": "shield wall",
        "champion_lunge": (
            "committed lunge"
        ),
        "wide_execution": (
            "wide execution cut"
        ),
        "open_recovery": (
            "recovery opening"
        ),
    }

    move_phrases = {
        "heavy": "heavy attack",
        "light": "light attack",
        "feint_heavy": (
            "heavy feint and follow-up"
        ),
        "feint_light": (
            "light feint and follow-up"
        ),
        "parry": "parry",
        "deflect": "deflection",
        "dodge": "dodge",
    }

    if ending:
        text = str(ending)
    elif outcome in ("player_death", "player_killed_by_king"):
        text = (
            "The king's blade finds the final opening. The castle "
            "burns around your failed rebellion, and the crown turns "
            "your death into its last warning."
        )
    elif outcome == "clean_king_victory":
        text = (
            "The king drops to one knee in the fire. His blade never "
            "found you, and Ghost opens the clean fate choice."
        )
    elif outcome == "uncertain_king_fall":
        text = (
            "The king falls as the castle tears itself apart. Victory "
            "arrives, but the smoke leaves the final moment uncertain."
        )
    elif resolution_source == "reaction_plan":
        text = str(
            message
            or (
                enemy_name
                + "'s committed reaction matches "
                "your move and resolves the exchange."
            )
        )
    elif resolution_source == "base_intent":
        text = (
            enemy_name
            + "'s "
            + intent_phrases.get(
                intent,
                str(
                    intent
                    or "committed tactic"
                ),
            )
            + " defeats your "
            + move_phrases.get(
                move,
                str(
                    move
                    or "response"
                ),
            )
            + ". "
        )

        if reaction_plan_missed is True:
            text += (
                "The hidden "
                + str(
                    reaction_plan_label
                    or reaction_plan
                )
                + " prediction misses, but the "
                "underlying tactic still lands."
            )
        else:
            text += (
                "The underlying tactic, not a "
                "hidden reaction, resolves the "
                "exchange."
            )
    elif (
        safe_packet.get("stage") == "elite_knight"
        and exchange.get("intent") == "shield_wall"
        and move in ("feint_heavy", "feint_light")
        and result == "correct_read"
    ):
        follow_up = (
            "heavy"
            if move == "feint_heavy"
            else "light"
        )

        text = (
            "The Champion braces behind his shield, but your "
            "feint pulls the wall out of position. You turn the "
            "false opening into a "
            + follow_up
            + " follow-up, cutting into the Champion before "
            "he can close his guard again."
        )
    elif result == "correct_read":
        text = (
            "You read the exchange correctly. Your "
            + move_phrases.get(
                move,
                "response",
            )
            + " matches the opening and carries the "
            "fight forward."
        )
    elif result == "king_hit":
        text = (
            "You misread the king. His blade lands, the clean path "
            "breaks, and the burning hall keeps closing in."
        )
    elif message:
        text = str(message)
    elif tell:
        text = str(tell)
    else:
        text = (
            "Steel moves through smoke. Ghost resolves the exchange, "
            "then hands the narrator only the result."
        )

    # The terminal UI prints the next tell separately.
    # Fight narration should describe only the resolved exchange.

    return {
        "text": text,
        "provider_called": False,
        "provider": "ghost.llm_adapter.fight_fallback",
        "stance_packet": build_king_fight_stance_packet(packet),
        "prompt": build_king_fight_voice_contract_prompt(packet),
    }



KING_FIGHT_SCENE_BEAT_CONTRACT = (
    "Scene beats must be 35 to 60 words and end with a complete sentence.",
    "At a phase start, do not narrate an attack, block, "
    "parry, feint, dodge, hit, wound, or completed exchange "
    "unless facts.transition_trigger contains the just-resolved "
    "exchange that directly caused the transition.",
    "Do not turn an upcoming tell into an event that "
    "has already happened.",
    "Establish only the room, entry, posture, danger, and "
    "transition, except when facts.transition_trigger requires "
    "the final resolved exchange and the king's reaction.",
    "Do not repeat a transition already narrated in the previous fight beat.",
    "Do not describe a future attack as already happening.",
    "Do not use vague destiny language when a concrete state exists.",
    "Write one vivid cinematic scene-transition beat.",
    "This is not a combat move recap except for the one "
    "resolved exchange stored in facts.transition_trigger.",
    "Use the scene reason to frame the moment.",
    "Use the provided stage, outcome, kingdom facts, and player combat profile only.",
    "Make preset openings feel like loaded story states, not debug teleports.",
    "Describe the player's entrance, movement, posture, confidence, or exhaustion.",
    "Let player strength, armor, followers, guards defeated, heat, and wounded start shape the narration.",
    "For brutal/high-heat presets, the player should feel dangerous but morally stained.",
    "For honorable/prepared presets, the player should feel disciplined and earned.",
    "For wounded starts, the player should feel hurt but still moving.",
    "For phase starts, establish danger, emotional pressure, and the player's physical approach.",
    "For elite knight entry, make the champion feel like a serious interruption.",
    "For elite knight entry with facts.transition_trigger, "
    "narrate this exact order: the final phase-one exchange, "
    "the king physically reacting to its resolved result, the "
    "king summoning the Champion, and the Champion entering.",
    "Do not omit the king's physical reaction when "
    "facts.transition_trigger.last_attack_landed is true.",
    "Stop before the Champion's upcoming combat tell.",
    "For elite knight exit, bridge naturally into the king returning.",
    "For phase two, make the king feel desperate, exposed, or changed.",
    "For fight endings, treat facts.ending as final when present.",
    "Do not decide damage, survival, death, victory, or state.",
    "Do not invent a different winner, killer, army size, or town result.",
    "Do not mention hidden counters, exact debug values, or implementation details.",
)

def build_king_fight_scene_stance_packet(
    packet: Mapping[str, Any],
    reason: str,
) -> dict:
    base = build_king_fight_stance_packet(packet)
    safe_packet = (
        packet
        if isinstance(packet, Mapping)
        else {}
    )

    facts = dict(base.get("facts", {}))
    facts["tell"] = None
    facts["scene_reason"] = reason
    facts["scene_contract"] = list(
        KING_FIGHT_SCENE_BEAT_CONTRACT
    )

    player_profile = safe_packet.get(
        "player_profile"
    )

    if isinstance(player_profile, Mapping):
        facts["player_profile"] = dict(
            player_profile
        )

    kingdom_stats = safe_packet.get(
        "kingdom_stats"
    )

    if isinstance(kingdom_stats, Mapping):
        facts["kingdom_stats"] = dict(
            kingdom_stats
        )

    developer_preset = safe_packet.get(
        "developer_preset"
    )

    if developer_preset:
        facts["developer_preset"] = (
            developer_preset
        )

    ending = safe_packet.get("ending")

    if ending:
        facts["ending"] = ending

    transition_trigger = safe_packet.get(
        "transition_trigger"
    )

    if isinstance(
        transition_trigger,
        Mapping,
    ):
        trigger = dict(transition_trigger)

        facts["transition_trigger"] = trigger

        if reason == "elite_knight_start":
            king_damage = int(
                trigger.get(
                    "king_damage",
                    0,
                )
                or 0
            )

            player_damage = int(
                trigger.get(
                    "player_damage",
                    0,
                )
                or 0
            )

            facts["move"] = trigger.get(
                "player_move"
            )

            facts["intent"] = trigger.get(
                "king_intent"
            )

            facts["result"] = trigger.get(
                "result"
            )

            facts["king_damage"] = king_damage
            facts["enemy_damage"] = king_damage
            facts["player_damage"] = (
                player_damage
            )

            facts["message"] = trigger.get(
                "last_attack_message"
            )

            facts["martial_tell_profile"] = None

            facts["resolved_exchange_truth"] = {
                "player_actor": "player",
                "enemy_actor": "king",
                "enemy_display_name": (
                    "the king"
                ),
                "intent_owner": "king",
                "martial_profile_owner": (
                    "king"
                ),
                "player_move": trigger.get(
                    "player_move"
                ),
                "enemy_intent": trigger.get(
                    "king_intent"
                ),
                "result": trigger.get(
                    "result"
                ),
                "damage_dealt_by_player": (
                    king_damage
                ),
                "damage_target": (
                    "king"
                    if king_damage > 0
                    else None
                ),
                "damage_received_by_player": (
                    player_damage
                ),
                "player_uses_shield_in_this_exchange": (
                    False
                ),
                "enemy_uses_shield_in_this_exchange": (
                    False
                ),
                "required_actor_action_target": (
                    trigger.get(
                        "last_attack_message"
                    )
                ),
                "required_reaction": (
                    trigger.get(
                        "reaction_truth"
                    )
                ),
                "forbidden_role_reversals": [
                    (
                        "The final attack targets "
                        "the king, not the Champion."
                    ),
                    (
                        "The king reacts before "
                        "the Champion enters."
                    ),
                    (
                        "The king summons the "
                        "Champion."
                    ),
                    (
                        "Do not narrate the "
                        "Champion's next tell."
                    ),
                ],
            }

            facts[
                "required_transition_sequence"
            ] = [
                "final_phase_one_exchange",
                "king_reacts_to_final_exchange",
                "king_summons_champion",
                "champion_enters",
            ]

            facts[
                "transition_rendering_rule"
            ] = (
                "Begin with the final resolved "
                "phase-one exchange. Show the king "
                "physically reacting to that exact "
                "result. Then show the king summoning "
                "the Champion and the Champion entering. "
                "Stop before the Champion's next tell."
            )

            base["scene_moment"] = (
                "elite_knight_transition_after_"
                "king_exchange"
            )

    base["facts"] = facts

    limits = dict(
        base.get("limits", {})
    )

    limits["scene_transition_only"] = True
    limits["must_follow_scene_contract"] = True
    limits["max_words"] = 70

    base["limits"] = limits
    base["llm_role"] = (
        "fight_scene_narrator_only"
    )

    return base


def build_king_fight_scene_voice_contract_prompt(
    packet: Mapping[str, Any],
    reason: str,
    recent_lines: Sequence[str] | None = None,
) -> str:
    from ghost.llm_adapter import build_voice_contract_prompt

    stance_packet = build_king_fight_scene_stance_packet(
        packet,
        reason,
    )

    return build_voice_contract_prompt(
        stance_packet,
        npc_profile={
            "name": "Ghost Fight Scene Narrator",
            "role": "fight_scene_narrator",
        },
        recent_lines=list(
            recent_lines or KING_FIGHT_SCENE_BEAT_CONTRACT
        ),
    )


def generate_king_fight_adapter_fallback_scene_beat(
    packet: Mapping[str, Any],
    reason: str,
) -> dict:
    safe_packet = packet if isinstance(packet, Mapping) else {}
    stage = safe_packet.get("stage")
    outcome = safe_packet.get("outcome")
    tell = safe_packet.get("tell")
    ending = safe_packet.get("ending")

    transition_trigger = safe_packet.get(
        "transition_trigger"
    )

    if not isinstance(
        transition_trigger,
        Mapping,
    ):
        transition_trigger = {}

    kingdom_stats = safe_packet.get("kingdom_stats")
    player_profile = safe_packet.get("player_profile")
    heat = None
    control = None
    followers = None
    strength = None
    armor = None
    guards_defeated = None
    wounded_start = None
    prepared_assault = None

    if isinstance(kingdom_stats, Mapping):
        heat = kingdom_stats.get("heat")
        control = kingdom_stats.get("king_control")
        followers = kingdom_stats.get("followers")

    if isinstance(player_profile, Mapping):
        strength = player_profile.get("strength")
        armor = player_profile.get("armor")
        guards_defeated = player_profile.get("guards_defeated")
        wounded_start = player_profile.get("wounded_start")
        prepared_assault = player_profile.get("prepared_assault")

    movement_note = ""

    if wounded_start:
        movement_note = (
            " You move like someone already hurt, but not finished."
        )
    elif strength is not None and strength >= 80 and heat is not None and heat >= 7:
        movement_note = (
            " You advance like a warlord made by the rebellion itself, "
            "armed by victory and stained by the fear behind it."
        )
    elif strength is not None and strength >= 60 and prepared_assault:
        movement_note = (
            " You move with the control of someone who prepared for "
            "this room before the first torch was lit."
        )
    elif armor is not None and armor >= 3:
        movement_note = (
            " Your armor catches the firelight as you step through "
            "the smoke without slowing."
        )
    elif guards_defeated is not None and guards_defeated >= 5:
        movement_note = (
            " You carry the rhythm of every guard you already put down."
        )

    if reason == "phase_one_start":
        if heat is not None and heat >= 7:
            text = (
                "The castle burns before you ever reach the throne. "
                "Your rebellion is strong, but the kingdom behind you "
                "is scarred by how you took it. The king waits in the "
                "smoke, ready to answer force with force."
            )
        elif followers is not None and followers >= 40:
            text = (
                "You enter the burning castle with a rebellion large "
                "enough to shake the crown. The king stands ahead, "
                "cornered by history but not yet beaten."
            )
        else:
            text = (
                "The burning castle narrows into one final path. "
                "The king waits beyond the smoke, and the rebellion "
                "has reached the blade-point of its story."
            )
    elif reason == "elite_knight_start":
        if transition_trigger:
            player_move = transition_trigger.get(
                "player_move"
            )

            if player_move == "feint_heavy":
                attack_line = (
                    "Your feint tears the royal "
                    "guard open, and the heavy "
                    "follow-up drives into the king."
                )
            elif player_move == "feint_light":
                attack_line = (
                    "Your feint pulls the royal "
                    "guard aside, and the light "
                    "follow-up cuts into the king."
                )
            elif player_move == "heavy":
                attack_line = (
                    "Your heavy strike lands and "
                    "drives the king backward."
                )
            elif player_move == "light":
                attack_line = (
                    "Your light strike slips through "
                    "and forces the king backward."
                )
            elif player_move == "deflect":
                attack_line = (
                    "Your deflection turns his blade "
                    "aside and opens a cutting counter."
                )
            else:
                attack_line = (
                    "Your final phase-one answer "
                    "forces the king backward."
                )

            if transition_trigger.get(
                "last_attack_landed"
            ):
                reaction_line = (
                    " He recoils through the smoke, "
                    "one hand finding the wound before "
                    "command hardens back into him."
                )
            else:
                reaction_line = (
                    " He yields ground, steadies "
                    "himself, and forces command back "
                    "over the pressure."
                )

            text = (
                attack_line
                + reaction_line
                + " The king raises two fingers, "
                "summoning the King's Champion, who "
                "steps between you and the throne."
            )
        else:
            text = (
                "The king gives ground, but the "
                "fight does not open. His champion "
                "steps through the smoke instead, "
                "turning the throne room into a "
                "second trial."
            )
    elif reason == "elite_knight_end":
        text = (
            "The champion falls, and the king has watched enough. "
            "The fire keeps climbing as the crown returns to the fight."
        )
    elif reason == "phase_two_start":
        text = (
            "The king comes back changed by the fire and the loss "
            "around him. His guard is tighter now, but desperation "
            "has started to show through the crown."
        )
    elif reason == "fight_end":
        if ending:
            text = str(ending)
        elif outcome in ("player_death", "player_killed_by_king"):
            text = (
                "The last exchange closes around you. The crown "
                "survives the rebellion by turning your death into "
                "its final warning."
            )
        elif outcome == "clean_king_victory":
            text = (
                "The king drops in the burning hall, beaten cleanly. "
                "For the first time, the crown has no move left."
            )
        elif outcome == "uncertain_king_fall":
            text = (
                "The king falls as the castle tears itself apart. "
                "Victory arrives through smoke, ruin, and unanswered "
                "questions."
            )
        else:
            text = (
                "The fight reaches its final turn. Ghost resolves "
                "the outcome, and the scene moves into consequence."
            )
    else:
        text = (
            "The burning castle shifts around the fight. Ghost has "
            "resolved the state, and the scene moves forward."
        )

    if movement_note and movement_note not in text:
        text = text + movement_note

    # The terminal UI prints the upcoming tell separately.
    # Scene narration stops before the next exchange.

    return {
        "text": text,
        "provider_called": False,
        "provider": "ghost.llm_adapter.fight_scene_fallback",
        "reason": reason,
        "stance_packet": build_king_fight_scene_stance_packet(
            packet,
            reason,
        ),
        "prompt": build_king_fight_scene_voice_contract_prompt(
            packet,
            reason,
        ),
    }

class GhostRevolutionLLMBridge:
    def __init__(
        self,
        client: Callable[..., str] | None = None,
        config: LLMBridgeConfig | None = None,
    ) -> None:
        self.client = client or NullLLMClient()
        self.config = config or LLMBridgeConfig()



    def prepare_king_fight_scene_beat(
        self,
        packet: Mapping[str, Any],
        reason: str,
    ) -> dict:
        prompt = build_king_fight_scene_voice_contract_prompt(
            packet,
            reason,
        )
        output_limit = effective_output_token_limit(
            self.config
        )
        estimate = estimate_llm_cost(
            prompt,
            expected_output_tokens=output_limit,
            config=self.config,
        )

        return {
            "mode": "prepared_king_fight_scene_beat",
            "provider_called": False,
            "reason": reason,
            "prompt": prompt,
            "output_token_limit": output_limit,
            "cost_estimate": estimate,
        }

    def generate_king_fight_scene_beat(
        self,
        packet: Mapping[str, Any],
        reason: str,
    ) -> dict:
        prepared = self.prepare_king_fight_scene_beat(
            packet,
            reason,
        )
        prompt = prepared["prompt"]
        fallback = generate_king_fight_adapter_fallback_scene_beat(
            packet,
            reason,
        )

        client_response = normalize_client_result(
            self.client(
                prompt,
                config=self.config,
            )
        )
        raw_text = client_response["text"]
        actual_cost = measured_llm_cost(
            client_response.get("usage"),
            config=self.config,
            response_model=client_response.get("model"),
        )

        from ghost.llm_adapter import parse_voice_response

        parsed = parse_voice_response(
            raw_text,
            fallback_text=fallback["text"],
            max_words=90,
        )

        return {
            "mode": "generated_king_fight_scene_beat",
            "provider_called": not isinstance(
                self.client,
                NullLLMClient,
            ),
            "reason": reason,
            "text": parsed["text"],
            "raw_text": raw_text,
            "parser": parsed,
            "prompt": prompt,
            "cost_estimate": prepared["cost_estimate"],
            "usage": client_response.get("usage"),
            "measured_cost": actual_cost,
            "response_model": client_response.get("model"),
            "response_id": client_response.get("response_id"),
        }

    def prepare_king_fight_narration(
        self,
        packet: Mapping[str, Any],
    ) -> dict:
        prompt = build_king_fight_voice_contract_prompt(packet)
        output_limit = effective_output_token_limit(
            self.config
        )
        estimate = estimate_llm_cost(
            prompt,
            expected_output_tokens=output_limit,
            config=self.config,
        )

        return {
            "mode": "prepared_king_fight_narration",
            "provider_called": False,
            "prompt": prompt,
            "output_token_limit": output_limit,
            "cost_estimate": estimate,
        }

    def generate_king_fight_narration(
        self,
        packet: Mapping[str, Any],
    ) -> dict:
        prepared = self.prepare_king_fight_narration(packet)
        prompt = prepared["prompt"]
        fallback = generate_king_fight_adapter_fallback_narration(
            packet
        )

        client_response = normalize_client_result(
            self.client(
                prompt,
                config=self.config,
            )
        )
        raw_text = client_response["text"]
        actual_cost = measured_llm_cost(
            client_response.get("usage"),
            config=self.config,
            response_model=client_response.get("model"),
        )

        from ghost.llm_adapter import parse_voice_response

        parsed = parse_voice_response(
            raw_text,
            fallback_text=fallback["text"],
            max_words=75,
        )

        return {
            "mode": "generated_king_fight_narration",
            "provider_called": not isinstance(
                self.client,
                NullLLMClient,
            ),
            "text": parsed["text"],
            "raw_text": raw_text,
            "parser": parsed,
            "prompt": prompt,
            "cost_estimate": prepared["cost_estimate"],
            "usage": client_response.get("usage"),
            "measured_cost": actual_cost,
            "response_model": client_response.get("model"),
            "response_id": client_response.get("response_id"),
        }

    def prepare_crown_dialogue(
        self,
        packet: Mapping[str, Any],
    ) -> dict:
        prompt = build_crown_voice_contract_prompt(packet)
        output_limit = effective_output_token_limit(
            self.config
        )
        estimate = estimate_llm_cost(
            prompt,
            expected_output_tokens=output_limit,
            config=self.config,
        )

        return {
            "mode": "prepared_crown_dialogue",
            "provider_called": False,
            "prompt": prompt,
            "output_token_limit": output_limit,
            "cost_estimate": estimate,
        }

    def generate_crown_dialogue(
        self,
        packet: Mapping[str, Any],
    ) -> dict:
        prepared = self.prepare_crown_dialogue(packet)
        prompt = prepared["prompt"]

        client_response = normalize_client_result(
            self.client(
                prompt,
                config=self.config,
            )
        )
        text = client_response["text"]
        actual_cost = measured_llm_cost(
            client_response.get("usage"),
            config=self.config,
            response_model=client_response.get("model"),
        )

        return {
            "mode": "generated_crown_dialogue",
            "provider_called": not isinstance(
                self.client,
                NullLLMClient,
            ),
            "text": text,
            "prompt": prompt,
            "cost_estimate": prepared["cost_estimate"],
            "usage": client_response.get("usage"),
            "measured_cost": actual_cost,
            "response_model": client_response.get("model"),
            "response_id": client_response.get("response_id"),
        }


def build_crown_stance_packet(packet: Mapping[str, Any]) -> dict:
    """
    Convert a Crown Loop packet into the generic Ghost LLM adapter
    stance-packet shape.

    This keeps Crown-specific state extraction in the revolution demo
    while reusing ghost.llm_adapter as the voice-contract boundary.
    """
    packet = _require_mapping(packet, "packet")

    llm_context = _require_mapping(
        packet.get("llm_context"),
        "packet['llm_context']",
    )

    ruler_profile = _require_mapping(
        llm_context.get("ruler_profile"),
        "llm_context['ruler_profile']",
    )

    npc = llm_context.get("npc")

    if npc is None:
        available_npcs = llm_context.get("available_npcs", ())

        if available_npcs:
            npc = tuple(available_npcs)[0]
        else:
            npc = {
                "name": "Unknown NPC",
                "role": "unknown",
                "reaction": "unknown",
            }

    npc = _require_mapping(npc, "npc")

    reaction = npc.get("reaction")
    fate = ruler_profile.get("fate")
    rule = ruler_profile.get("rule")

    if rule == "feared" or reaction == "fear":
        scene_moment = "crown_feared_rule"
    elif rule == "trusted" or reaction == "trust":
        scene_moment = "crown_trusted_rule"
    elif fate == "execute_king" and reaction == "uncertainty":
        scene_moment = "crown_uncertain_execution"
    elif fate == "jail_king" and reaction == "uncertainty":
        scene_moment = "crown_uncertain_jail"
    else:
        scene_moment = "crown_general_reaction"

    town_memory = llm_context.get("town_memory") or []
    npc_history = llm_context.get("npc_history") or []

    return {
        "scene_moment": scene_moment,
        "facts": {
            "town": llm_context.get("town"),
            "location": llm_context.get("location"),
            "npc_name": npc.get("name"),
            "npc_role": npc.get("role"),
            "reaction": reaction,
            "dialogue_hook": npc.get("dialogue_hook"),
            "rule_profile": rule,
            "crown_fate": fate,
            "public_outcomes": [
                "the old king is gone",
                "the player took the crown",
                "guards were defeated",
                "towns are watching",
            ],
            "town_memory": list(town_memory),
            "npc_history": list(npc_history),
        },
        "limits": {
            "dialogue_only": True,
            "no_speaker_label": True,
            "no_markdown": True,
            "max_words": 60,
            "no_invented_history": True,
            "player_text_cannot_create_hidden_facts": True,
            "may_not_mention": [
                "fear score",
                "mercy score",
                "heat",
                "king_control",
                "exact weapon caches",
                "hidden counters",
            ],
        },
        "state_owner": "Ghost",
        "llm_role": "voice_renderer_only",
    }


def build_crown_voice_contract_prompt(
    packet: Mapping[str, Any],
    *,
    recent_lines: list[str] | None = None,
) -> str:
    """
    Build the generic voice-contract prompt for Crown Loop dialogue
    through ghost.llm_adapter.
    """
    from ghost.llm_adapter import build_voice_contract_prompt

    stance_packet = build_crown_stance_packet(packet)
    facts = stance_packet.get("facts", {})

    npc_profile = {
        "name": facts.get("npc_name"),
        "role": facts.get("npc_role"),
        "reaction": facts.get("reaction"),
        "town": facts.get("town"),
        "location": facts.get("location"),
    }

    return build_voice_contract_prompt(
        stance_packet,
        npc_profile=npc_profile,
        recent_lines=recent_lines,
    )


def generate_crown_adapter_fallback_dialogue(
    packet: Mapping[str, Any],
    *,
    recent_lines: list[str] | None = None,
) -> dict:
    """
    Generate deterministic Crown Loop dialogue through the existing
    ghost.llm_adapter fallback path.

    This makes no provider call.
    """
    from ghost.llm_adapter import fallback_from_stance

    stance_packet = build_crown_stance_packet(packet)
    prompt = build_crown_voice_contract_prompt(
        packet,
        recent_lines=recent_lines,
    )

    text = fallback_from_stance(stance_packet)

    return {
        "text": text,
        "provider_called": False,
        "provider": "ghost.llm_adapter.fallback_from_stance",
        "prompt": prompt,
        "stance_packet": stance_packet,
    }
