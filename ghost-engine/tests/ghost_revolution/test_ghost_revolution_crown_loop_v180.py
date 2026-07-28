
from collections import deque

from ghost.examples.ghost_revolution.dev_shortcuts import (
    create_developer_preset_run,
    create_endgame_shortcut,
)
from ghost.examples.ghost_revolution.presentation import (
    crown_loop_menu,
)


def test_crown_loop_locations_exist_for_each_town_v180():
    game, packet = create_endgame_shortcut("crown_jail")

    assert packet["stage"] == "crown_loop"

    for town in game.crown_towns():
        locations = game.crown_town_locations(town)
        ids = {location["id"] for location in locations}

        assert ids == {
            "blacksmith",
            "goods_stall",
            "public_event",
            "town_square",
        }


def test_public_event_has_three_reactive_npcs_v180():
    game, _packet = create_endgame_shortcut("crown_jail")

    packet = game.crown_visit_location(
        "Ashfield",
        "public_event",
    )

    assert packet["outcome"] == "crown_location"
    assert packet["stage"] == "crown_loop"
    assert packet["town"] == "Ashfield"
    assert packet["location"] == "public_event"
    assert packet["llm_ready"] is True
    assert packet["llm_context"]["mode"] == "crown_loop_location"

    npcs = packet["npcs"]

    assert len(npcs) == 3
    assert {npc["id"] for npc in npcs} == {
        "town_elder",
        "former_guard",
        "market_worker",
    }


def test_crown_reaction_changes_with_brutal_numbers_v180():
    brutal_game, _loaded = create_developer_preset_run(
        "brutal_takeover"
    )
    honorable_game, _loaded = create_developer_preset_run(
        "honorable_takeover"
    )

    brutal_packet = brutal_game.crown_visit_location(
        "Ashfield",
        "blacksmith",
    )
    honorable_packet = honorable_game.crown_visit_location(
        "Ashfield",
        "blacksmith",
    )

    assert brutal_packet["crown_profile"]["rule"] == "feared"
    assert honorable_packet["crown_profile"]["rule"] in {
        "trusted",
        "uncertain",
    }

    assert brutal_packet["narrative"] != honorable_packet["narrative"]


def test_crown_npc_open_dialogue_builds_llm_context_v180():
    game, _packet = create_endgame_shortcut("crown_jail")

    packet = game.crown_npc_interaction(
        "Millcross",
        "public_event",
        "former_guard",
        "open_dialogue",
    )

    assert packet["outcome"] == "crown_npc_interaction"
    assert packet["action"] == "open_dialogue"
    assert packet["llm_ready"] is True
    assert packet["llm_context"]["mode"] == "crown_loop_npc_dialogue"
    assert packet["llm_context"]["npc"]["id"] == "former_guard"
    assert packet["llm_context"]["world_numbers"]["weapon_caches"] == (
        game.weapons
    )
    assert "spoken claims" in packet["llm_context"]["instruction"]


def test_crown_npc_greet_is_deterministic_placeholder_v180():
    game, _packet = create_endgame_shortcut("crown_execute")

    first = game.crown_npc_interaction(
        "Crownmarket",
        "goods_stall",
        "stall_keeper",
        "greet",
    )
    second = game.crown_npc_interaction(
        "Crownmarket",
        "goods_stall",
        "stall_keeper",
        "greet",
    )

    assert first == second
    assert first["llm_ready"] is False
    assert "greet" in first["narrative"].lower()


def test_crown_loop_menu_enters_town_location_and_dialogue_v180(
    monkeypatch,
    capsys,
):
    game, _packet = create_endgame_shortcut("crown_jail")
    events = deque(maxlen=8)

    inputs = iter(
        [
            "1",
            "3",
            "2",
            "0",
            "0",
            "0",
        ]
    )

    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt="": next(inputs),
    )

    crown_loop_menu(game, events)

    output = capsys.readouterr().out

    assert "CROWN LOOP" in output
    assert "CROWN TOWN" in output
    assert "CROWN NPCS" in output
    assert "LLM CONTEXT PLACEHOLDER" in output
    assert "Open dialogue" in output


def test_crown_open_dialogue_prints_offline_llm_bridge_output_v180(
    capsys,
):
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_endgame_shortcut,
    )
    from ghost.examples.ghost_revolution.presentation import (
        _print_crown_packet,
    )

    game, _packet = create_endgame_shortcut("crown_execute")

    packet = game.crown_npc_interaction(
        "Ashfield",
        "public_event",
        "town_elder",
        "open_dialogue",
    )

    _print_crown_packet(packet)

    output = capsys.readouterr().out

    assert "LLM CONTEXT PLACEHOLDER" in output
    assert "ADAPTER FALLBACK DIALOGUE" in output
    assert "You ended the old king's rule" in output
    assert "Provider called: False" in output
    assert "ghost.llm_adapter.fallback_from_st" in output
    assert "ance" in output
    assert "[LLM disabled]" not in output


def test_crown_greet_does_not_print_llm_bridge_output_v180(
    capsys,
):
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_endgame_shortcut,
    )
    from ghost.examples.ghost_revolution.presentation import (
        _print_crown_packet,
    )

    game, _packet = create_endgame_shortcut("crown_execute")

    packet = game.crown_npc_interaction(
        "Ashfield",
        "public_event",
        "town_elder",
        "greet",
    )

    _print_crown_packet(packet)

    output = capsys.readouterr().out

    assert "LLM CONTEXT PLACEHOLDER" in output
    assert "ADAPTER FALLBACK DIALOGUE" not in output
    assert "[LLM disabled]" not in output


def test_crown_open_dialogue_prints_adapter_fallback_dialogue_v180(capsys):
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_endgame_shortcut,
    )
    from ghost.examples.ghost_revolution.presentation import (
        _print_crown_packet,
    )

    game, _packet = create_endgame_shortcut("crown_execute")

    packet = game.crown_npc_interaction(
        "Ashfield",
        "public_event",
        "town_elder",
        "open_dialogue",
    )

    _print_crown_packet(packet)

    output = capsys.readouterr().out

    assert "ADAPTER FALLBACK DIALOGUE" in output
    assert "You ended the old king's rule" in output
    assert "Provider called: False" in output
    assert "ghost.llm_adapter.fallback_from_st" in output
    assert "ance" in output
    assert "[LLM disabled]" not in output
