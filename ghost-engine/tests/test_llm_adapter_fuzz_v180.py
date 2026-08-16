import json

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from ghost.llm_adapter import (
    build_voice_contract_prompt,
    fallback_from_stance,
)
from ghost.examples.ghost_revolution.dev_shortcuts import (
    create_endgame_shortcut,
)
from ghost.examples.ghost_revolution.llm_bridge import (
    build_crown_stance_packet,
    build_crown_voice_contract_prompt,
    estimate_llm_cost,
    LLMBridgeConfig,
)


small_text = st.text(
    min_size=0,
    max_size=300,
)

long_text = st.text(
    min_size=0,
    max_size=2000,
)

json_scalar = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-10_000, max_value=10_000),
    st.floats(
        allow_nan=False,
        allow_infinity=False,
        width=32,
    ),
    small_text,
)

json_value = st.recursive(
    json_scalar,
    lambda children: st.one_of(
        st.lists(
            children,
            max_size=8,
        ),
        st.dictionaries(
            small_text,
            children,
            max_size=8,
        ),
    ),
    max_leaves=30,
)


@given(
    scene=small_text,
    facts=st.dictionaries(
        small_text,
        json_value,
        max_size=10,
    ),
    limits=st.dictionaries(
        small_text,
        json_value,
        max_size=10,
    ),
    npc_name=long_text,
    recent_lines=st.lists(
        small_text,
        max_size=10,
    ),
)
@settings(max_examples=80, suppress_health_check=[HealthCheck.too_slow])
def test_llm_adapter_voice_contract_fuzz_v180(
    scene,
    facts,
    limits,
    npc_name,
    recent_lines,
):
    stance_packet = {
        "scene_moment": scene,
        "facts": facts,
        "limits": limits,
        "state_owner": "Ghost",
        "llm_role": "voice_renderer_only",
    }

    npc_profile = {
        "name": npc_name,
        "role": "fuzz_npc",
    }

    prompt = build_voice_contract_prompt(
        stance_packet,
        npc_profile=npc_profile,
        recent_lines=recent_lines,
    )

    assert isinstance(prompt, str)
    assert "SYSTEM: You are an NPC voice renderer." in prompt
    assert "SYSTEM: You do not decide world state." in prompt
    assert "STANCE_PACKET:" in prompt

    payload_text = prompt.split("STANCE_PACKET:\n", 1)[1]
    payload = json.loads(payload_text)

    assert payload["stance"] == stance_packet
    assert payload["npc_profile"] == npc_profile
    assert payload["recent_lines_to_avoid"] == recent_lines[-5:]


@given(
    scene=small_text,
    facts=st.dictionaries(
        small_text,
        json_value,
        max_size=10,
    ),
)
@settings(max_examples=80, suppress_health_check=[HealthCheck.too_slow])
def test_llm_adapter_fallback_never_crashes_on_fuzz_stance_v180(
    scene,
    facts,
):
    stance_packet = {
        "scene_moment": scene,
        "facts": facts,
    }

    text = fallback_from_stance(stance_packet)

    assert isinstance(text, str)
    assert text


@given(
    npc_name=long_text,
    public_outcomes=st.lists(
        small_text,
        max_size=12,
    ),
    town_memory=st.lists(
        small_text,
        max_size=12,
    ),
    npc_history=st.lists(
        small_text,
        max_size=12,
    ),
)
@settings(max_examples=40, suppress_health_check=[HealthCheck.too_slow])
def test_crown_stance_packet_survives_edge_payloads_v180(
    npc_name,
    public_outcomes,
    town_memory,
    npc_history,
):
    game, _packet = create_endgame_shortcut("crown_execute")

    packet = game.crown_npc_interaction(
        "Ashfield",
        "public_event",
        "town_elder",
        "open_dialogue",
    )

    packet["llm_context"]["npc"]["name"] = npc_name
    packet["llm_context"]["town_memory"] = town_memory
    packet["llm_context"]["npc_history"] = npc_history

    stance = build_crown_stance_packet(packet)

    stance["facts"]["public_outcomes"] = public_outcomes

    encoded = json.dumps(
        stance,
        ensure_ascii=False,
    )
    decoded = json.loads(encoded)

    assert decoded == stance
    assert decoded["state_owner"] == "Ghost"
    assert decoded["llm_role"] == "voice_renderer_only"
    assert decoded["limits"]["dialogue_only"] is True


@given(
    npc_name=long_text,
    town_memory=st.lists(
        small_text,
        max_size=12,
    ),
    npc_history=st.lists(
        small_text,
        max_size=12,
    ),
)
@settings(max_examples=40, suppress_health_check=[HealthCheck.too_slow])
def test_crown_voice_contract_and_cost_estimator_handle_mutations_v180(
    npc_name,
    town_memory,
    npc_history,
):
    game, _packet = create_endgame_shortcut("crown_execute")

    packet = game.crown_npc_interaction(
        "Ashfield",
        "public_event",
        "town_elder",
        "open_dialogue",
    )

    packet["llm_context"]["npc"]["name"] = npc_name
    packet["llm_context"]["town_memory"] = town_memory
    packet["llm_context"]["npc_history"] = npc_history

    prompt = build_crown_voice_contract_prompt(packet)

    config = LLMBridgeConfig(
        max_output_tokens=120,
        hard_max_output_tokens=150,
    )

    cost = estimate_llm_cost(
        prompt,
        config=config,
    )

    assert isinstance(prompt, str)
    assert "STANCE_PACKET:" in prompt
    assert cost["input_tokens_estimate"] >= 1
    assert cost["output_tokens_estimate"] == 120
    assert cost["max_output_tokens"] == 120
    assert cost["hard_max_output_tokens"] == 150
    assert cost["total_cost_estimate"] >= 0
