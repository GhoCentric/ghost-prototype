"""
Developer shortcut panel for Ghost Revolution.

Run with:

python -m ghost.examples.ghost_revolution.dev_shortcuts

This module is intentionally separate from the main demo loop.
It lets developers jump directly into useful state-engine scenarios
without grinding the full rebellion.
"""

from __future__ import annotations

from collections import deque
from copy import deepcopy

from .demo import GhostRevolutionRun


PRESET_ORDER = (
    "weak_siege",
    "minimum_siege",
    "prepared_siege",
    "brutal_takeover",
    "honorable_takeover",
    "instant_king_fight",
    "instant_wounded_king_fight",
)

PRESET_LABELS = {
    "weak_siege": "Weak siege / doomed rebellion",
    "minimum_siege": "Minimum siege / wounded king fight",
    "prepared_siege": "Prepared siege / empowered king fight",
    "brutal_takeover": "Brutal takeover / high heat",
    "honorable_takeover": "Honorable takeover / lower heat",
    "instant_king_fight": "Instant prepared king fight",
    "instant_wounded_king_fight": "Instant wounded king fight",
}

PRESET_ALIASES = {
    "weak": "weak_siege",
    "minimum": "minimum_siege",
    "min": "minimum_siege",
    "prepared": "prepared_siege",
    "strong": "prepared_siege",
    "brutal": "brutal_takeover",
    "honorable": "honorable_takeover",
    "honourable": "honorable_takeover",
    "instant": "instant_king_fight",
    "king": "instant_king_fight",
    "wounded": "instant_wounded_king_fight",
}


def developer_shortcut_presets() -> tuple[str, ...]:
    return PRESET_ORDER


def normalize_developer_preset(preset: str) -> str:
    if not isinstance(preset, str) or not preset.strip():
        raise ValueError("Choose a developer shortcut preset.")

    key = preset.strip().lower().replace("-", "_").replace(" ", "_")
    key = PRESET_ALIASES.get(key, key)

    if key not in PRESET_ORDER:
        raise ValueError(
            "Unknown developer shortcut preset: "
            f"{preset!r}"
        )

    return key


def _set_if_present(game: GhostRevolutionRun, name: str, value) -> None:
    if hasattr(game, name):
        setattr(game, name, value)


def _reset_run_for_developer_shortcut(
    game: GhostRevolutionRun,
) -> None:
    _set_if_present(game, "phase", "rebellion")
    _set_if_present(game, "day", 1)
    _set_if_present(game, "actions", 0)
    _set_if_present(game, "location", "base")
    _set_if_present(game, "alive", True)
    _set_if_present(game, "captured", False)
    _set_if_present(game, "ending", "")
    _set_if_present(game, "last_packet", {})
    _set_if_present(game, "king_fight", None)
    _set_if_present(game, "siege_armed", False)


def _set_siege_numbers(
    game: GhostRevolutionRun,
    *,
    followers: int,
    weapons: int,
    armor: int,
    guards_defeated: int,
    king_control: int,
    heat: int,
    gold: int,
    food: int,
) -> None:
    game.followers = followers
    game.weapons = weapons
    game.armor = armor
    game.guards_defeated = guards_defeated
    game.king_control = king_control
    game.heat = heat
    game.gold = gold
    game.food = food


def _apply_weak_siege(game: GhostRevolutionRun) -> str:
    _set_siege_numbers(
        game,
        followers=0,
        weapons=1,
        armor=0,
        guards_defeated=0,
        king_control=10,
        heat=0,
        gold=20,
        food=3,
    )

    return (
        "Weak siege loaded. This proves the army-strength gate: "
        "the rebellion fails before reaching the king."
    )


def _apply_minimum_siege(game: GhostRevolutionRun) -> str:
    _set_siege_numbers(
        game,
        followers=30,
        weapons=5,
        armor=2,
        guards_defeated=2,
        king_control=10,
        heat=4,
        gold=55,
        food=18,
    )

    return (
        "Minimum siege loaded. The army barely reaches the king, "
        "so the player starts wounded with broken armor."
    )


def _apply_prepared_siege(game: GhostRevolutionRun) -> str:
    _set_siege_numbers(
        game,
        followers=40,
        weapons=8,
        armor=4,
        guards_defeated=4,
        king_control=5,
        heat=5,
        gold=80,
        food=25,
    )

    return (
        "Prepared siege loaded. The army reaches the king cleanly, "
        "so the player starts at full health with bonus damage."
    )


def _apply_brutal_takeover(game: GhostRevolutionRun) -> str:
    _set_siege_numbers(
        game,
        followers=55,
        weapons=12,
        armor=3,
        guards_defeated=8,
        king_control=3,
        heat=9,
        gold=95,
        food=16,
    )

    game.last_king_response = [
        "The king calls the rebellion a butcher's crown.",
        "Towns obey, but many obey from fear.",
    ]

    return (
        "Brutal takeover loaded. High followers and weapons, "
        "but the kingdom is hot, afraid, and scarred by force."
    )


def _apply_honorable_takeover(game: GhostRevolutionRun) -> str:
    _set_siege_numbers(
        game,
        followers=42,
        weapons=8,
        armor=4,
        guards_defeated=1,
        king_control=4,
        heat=2,
        gold=65,
        food=35,
    )

    game.last_king_response = [
        "The king struggles to paint mercy as weakness.",
        "The towns are watching how the crown is challenged.",
    ]

    return (
        "Honorable takeover loaded. Strong enough for the castle, "
        "but with lower heat and fewer defeated guards."
    )


def apply_developer_preset(
    game: GhostRevolutionRun,
    preset: str,
) -> dict:
    key = normalize_developer_preset(preset)
    _reset_run_for_developer_shortcut(game)

    if key == "weak_siege":
        note = _apply_weak_siege(game)
    elif key == "minimum_siege":
        note = _apply_minimum_siege(game)
    elif key == "prepared_siege":
        note = _apply_prepared_siege(game)
    elif key == "brutal_takeover":
        note = _apply_brutal_takeover(game)
    elif key == "honorable_takeover":
        note = _apply_honorable_takeover(game)
    elif key == "instant_king_fight":
        note = _apply_prepared_siege(game)
    elif key == "instant_wounded_king_fight":
        note = _apply_minimum_siege(game)
    else:
        raise AssertionError("Unhandled developer preset.")

    game.last_action_note = note

    warning = game.siege_warning()
    started = None

    if key in (
        "instant_king_fight",
        "instant_wounded_king_fight",
    ):
        started = game.siege_castle()

    return {
        "preset": key,
        "label": PRESET_LABELS[key],
        "note": note,
        "siege_warning": deepcopy(warning),
        "started": deepcopy(started),
        "summary": developer_state_summary(game),
    }


def create_developer_preset_run(
    preset: str,
    *,
    seed: int = 7,
) -> tuple[GhostRevolutionRun, dict]:
    game = GhostRevolutionRun(seed=seed)
    packet = apply_developer_preset(game, preset)

    return game, packet


def developer_state_summary(game: GhostRevolutionRun) -> dict:
    warning = game.siege_warning()

    return {
        "phase": getattr(game, "phase", None),
        "location": getattr(game, "location", None),
        "followers": game.followers,
        "food": game.food,
        "gold": game.gold,
        "weapons": game.weapons,
        "armor": game.armor,
        "heat": game.heat,
        "guards_defeated": game.guards_defeated,
        "king_control": game.king_control,
        "strength": warning["strength"],
        "minimum_required": warning["minimum_required"],
        "strong_threshold": warning["strong_threshold"],
        "likely_success": warning["likely_success"],
        "prepared_assault": warning["prepared_assault"],
        "wounded_start": warning["wounded_start"],
        "king_fight_active": game.king_fight is not None,
    }


def start_developer_siege(game: GhostRevolutionRun) -> dict:
    warning = game.siege_warning()
    result = game.siege_castle()

    return {
        "warning": deepcopy(warning),
        "result": deepcopy(result),
        "summary": developer_state_summary(game),
    }


def _print_summary(packet: dict) -> None:
    summary = packet["summary"]

    print()
    print("=== DEVELOPER SHORTCUT LOADED ===")
    print("Preset:", packet["label"])
    print("Note:", packet["note"])
    print()
    print("Followers:", summary["followers"])
    print("Weapon caches:", summary["weapons"])
    print("Estimated arms:", weapon_cache_label(summary["weapons"]))
    print("Armor:", summary["armor"])
    print("Guards defeated:", summary["guards_defeated"])
    print("King control:", summary["king_control"])
    print("Heat:", summary["heat"])
    print("Food:", summary["food"])
    print("Gold:", summary["gold"])
    print()
    print("Strength:", summary["strength"])
    print("Minimum required:", summary["minimum_required"])
    print("Strong threshold:", summary["strong_threshold"])
    print("Likely success:", summary["likely_success"])
    print("Prepared assault:", summary["prepared_assault"])
    print("Wounded start:", summary["wounded_start"])

    started = packet.get("started")

    if isinstance(started, dict):
        print()
        print("=== INSTANT START RESULT ===")
        print("Outcome:", started.get("outcome"))
        print("Stage:", started.get("stage"))
        print("Tell:", started.get("tell", ""))


def _print_siege_result(packet: dict) -> None:
    result = packet["result"]

    print()
    print("=== SIEGE RESULT ===")
    print("Outcome:", result.get("outcome"))
    print("Stage:", result.get("stage", "-"))
    print("Ending type:", result.get("ending_type", "-"))

    if "ending" in result:
        print("Ending:", result["ending"])

    if "tell" in result:
        print()
        print("Tell:")
        print(result["tell"])


def _open_king_fight_menu(game: GhostRevolutionRun) -> None:
    if game.king_fight is None:
        return

    from .presentation import king_fight_menu

    events = deque(maxlen=8)
    king_fight_menu(game, events)


ENDGAME_SHORTCUT_ORDER = (
    "weak_failure",
    "champion_death",
    "castle_legend",
    "uncertain_victory",
    "clean_fate_choice",
    "crown_execute",
    "crown_jail",
    "retire_execute",
    "retire_jail",
)

ENDGAME_SHORTCUT_LABELS = {
    "weak_failure": "Weak siege failure narration",
    "champion_death": "Champion kills player narration",
    "castle_legend": "Castle-collapse legend narration",
    "uncertain_victory": "Uncertain king-fall victory narration",
    "clean_fate_choice": "Clean victory fate choice",
    "crown_execute": "Crown loop — king executed",
    "crown_jail": "Crown loop — king jailed",
    "retire_execute": "Retire Crown — execution path",
    "retire_jail": "Retire Crown — jail path",
}

ENDGAME_SHORTCUT_ALIASES = {
    "weak": "weak_failure",
    "failure": "weak_failure",
    "death": "champion_death",
    "champion": "champion_death",
    "collapse": "castle_legend",
    "legend": "castle_legend",
    "uncertain": "uncertain_victory",
    "clean": "clean_fate_choice",
    "fate": "clean_fate_choice",
    "execute": "crown_execute",
    "jail": "crown_jail",
    "retire": "retire_execute",
}


def normalize_endgame_shortcut(shortcut: str) -> str:
    if not isinstance(shortcut, str) or not shortcut.strip():
        raise ValueError(
            "Choose an endgame shortcut."
        )

    key = (
        shortcut
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    key = ENDGAME_SHORTCUT_ALIASES.get(
        key,
        key,
    )

    if key not in ENDGAME_SHORTCUT_ORDER:
        raise ValueError(
            "Unknown endgame shortcut: "
            f"{shortcut!r}"
        )

    return key


def _start_preset_siege(
    preset: str,
    *,
    seed: int = 7,
) -> tuple[GhostRevolutionRun, dict, dict]:
    game, loaded = create_developer_preset_run(
        preset,
        seed=seed,
    )

    started = loaded.get("started")

    if not isinstance(started, dict):
        started = start_developer_siege(
            game
        )["result"]

    return game, loaded, started


def create_fight_stage_shortcut(
    destination: str,
    *,
    seed: int = 7,
) -> tuple[GhostRevolutionRun, dict]:
    key = (
        destination
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    aliases = {
        "wounded": "wounded_king",
        "minimum": "wounded_king",
        "prepared": "prepared_king",
        "king": "prepared_king",
        "champion": "elite_knight",
        "elite": "elite_knight",
        "phase_two": "king_phase_two",
        "phase2": "king_phase_two",
    }

    key = aliases.get(key, key)

    if key == "wounded_king":
        game, _loaded, packet = _start_preset_siege(
            "minimum_siege",
            seed=seed,
        )

        packet = attach_developer_cause(
            game,
            packet,
            key,
        )

        return game, packet

    if key == "prepared_king":
        game, _loaded, packet = _start_preset_siege(
            "prepared_siege",
            seed=seed,
        )

        packet = attach_developer_cause(
            game,
            packet,
            key,
        )

        return game, packet

    if key == "elite_knight":
        game, _packet = create_fight_stage_shortcut(
            "prepared_king",
            seed=seed,
        )

        fight = game.king_fight

        fight["king_health"] = fight["king_half_health"]

        packet = game._transition_to_elite_knight()

        packet = attach_developer_cause(
            game,
            packet,
            key,
        )

        return game, packet

    if key == "king_phase_two":
        game, _packet = create_fight_stage_shortcut(
            "elite_knight",
            seed=seed,
        )

        fight = game.king_fight

        fight["stage"] = "king_phase_two"
        fight["elite_knight_health"] = 0
        fight["king_health"] = fight["king_half_health"]
        fight["exchange_count"] = 0
        fight["intent"] = game._king_intent(0)

        game.last_action_note = (
            "The King's Champion is already down. "
            "The king steps forward for the final phase."
        )

        packet = {
            "outcome": "elite_knight_defeated",
            "stage": "king_phase_two",
            "king_health": fight["king_health"],
            "player_health": fight["player_health"],
            "castle_timer": fight["castle_timer"],
            "tell": game._king_intent_tell(
                fight["intent"]
            ),
        }

        packet = attach_developer_cause(
            game,
            packet,
            key,
        )

        return game, packet

    raise ValueError(
        "Unknown fight-stage shortcut: "
        f"{destination!r}"
    )


WEAPONS_PER_CACHE_MIN = 5
WEAPONS_PER_CACHE_MAX = 8


def weapon_cache_range(
    caches: int,
) -> tuple[int, int]:
    return (
        caches * WEAPONS_PER_CACHE_MIN,
        caches * WEAPONS_PER_CACHE_MAX,
    )


def weapon_cache_label(
    caches: int,
) -> str:
    low, high = weapon_cache_range(caches)

    return (
        f"{caches} caches "
        f"(arms about {low}-{high} fighters)"
    )


def wounded_start_explanation(
    game: GhostRevolutionRun,
    packet: dict,
) -> list[str]:
    if not isinstance(packet, dict):
        return []

    wounded = packet.get("wounded_start") is True

    if not wounded:
        wounded = (
            packet.get("outcome")
            == "king_confrontation_started"
            and packet.get("stage") == "king_phase_one"
            and packet.get("player_health") == 5
        )

    if not wounded:
        return []

    warning = game.siege_warning()

    return [
        "Wounded start:",
        (
            "The rebellion reaches the throne, but only barely. "
            "The army is strong enough to breach the castle, not "
            "strong enough to shield you through the final push."
        ),
        (
            "You begin at half health because the approach broke "
            "your armor before the king fight starts."
        ),
        (
            "Cause: strength "
            f"{warning['strength']} reached minimum "
            f"{warning['minimum_required']} but stayed below strong "
            f"threshold {warning['strong_threshold']}."
        ),
        (
            "Army: "
            f"followers {game.followers}; "
            f"weapon caches {weapon_cache_label(game.weapons)}; "
            f"armor {game.armor}; "
            f"guards defeated {game.guards_defeated}."
        ),
    ]

def developer_cause_lines(
    game: GhostRevolutionRun,
    packet: dict,
    shortcut: str | None = None,
) -> list[str]:
    warning = game.siege_warning()
    outcome = packet.get("outcome", "-")
    stage = packet.get("stage", "-")

    lines = [
        f"Shortcut: {shortcut or '-'}",
        f"Outcome: {outcome}",
        f"Stage: {stage}",
        (
            "Strength: "
            f"{warning['strength']} / minimum "
            f"{warning['minimum_required']} / strong "
            f"{warning['strong_threshold']}"
        ),
        (
            "Army: "
            f"followers {game.followers}; "
            f"weapon caches {weapon_cache_label(game.weapons)}; "
            f"armor {game.armor}; "
            f"guards defeated {game.guards_defeated}"
        ),
        (
            "Kingdom: "
            f"heat {game.heat}; "
            f"king control {game.king_control}; "
            f"food {game.food}; "
            f"gold {game.gold}"
        ),
        (
            "Siege flags: "
            f"likely success {warning['likely_success']}; "
            f"prepared assault {warning['prepared_assault']}; "
            f"wounded start {warning['wounded_start']}"
        ),
    ]

    fight = getattr(game, "king_fight", None)

    if isinstance(fight, dict):
        lines.append(
            "Fight: "
            f"stage {fight.get('stage', '-')}; "
            f"timer {fight.get('castle_timer', '-')}; "
            f"player HP {fight.get('player_health', '-')}; "
            f"king HP {fight.get('king_health', '-')}; "
            f"Champion HP {fight.get('elite_knight_health', '-')}"
        )
        lines.append(
            "Clean path: "
            f"possible {fight.get('clean_king_victory_possible', '-')}; "
            f"king hit player {fight.get('king_has_hit_player', '-')}; "
            f"king morale ticks {fight.get('king_morale_ticks', '-')}"
        )

        fate = (
            fight.get("king_fate")
            or fight.get("chosen_fate")
            or fight.get("king_fate_choice")
            or fight.get("fate")
        )

        if fate:
            lines.append(f"Crown fate: {fate}")

    wounded_lines = wounded_start_explanation(
        game,
        packet,
    )

    if wounded_lines:
        lines.append(
            "Wounded reason: barely met siege minimum; "
            "below prepared assault threshold."
        )

    lines.append(
        "Final flags: "
        f"complete {game.complete}; "
        f"alive {game.alive}; "
        f"captured {game.captured}"
    )

    return lines


def attach_developer_cause(
    game: GhostRevolutionRun,
    packet: dict,
    shortcut: str | None = None,
) -> dict:
    if not isinstance(packet, dict):
        return packet

    packet = deepcopy(packet)

    wounded_lines = wounded_start_explanation(
        game,
        packet,
    )

    if wounded_lines:
        packet["wounded_start_explanation"] = wounded_lines

        narrative = " ".join(wounded_lines[1:3])
        packet["narrative"] = narrative
        packet["note"] = narrative

    packet["developer_cause"] = developer_cause_lines(
        game,
        packet,
        shortcut,
    )

    return packet

def create_endgame_shortcut(
    shortcut: str,
    *,
    seed: int = 7,
) -> tuple[GhostRevolutionRun, dict]:
    key = normalize_endgame_shortcut(shortcut)

    if key == "weak_failure":
        game, _loaded, packet = _start_preset_siege(
            "weak_siege",
            seed=seed,
        )

        packet = attach_developer_cause(
            game,
            packet,
            key,
        )

        return game, packet

    if key == "champion_death":
        game, _packet = create_fight_stage_shortcut(
            "elite_knight",
            seed=seed,
        )

        packet = game._finish_player_death(
            killer="elite_knight"
        )

        packet = attach_developer_cause(
            game,
            packet,
            key,
        )

        return game, packet

    if key == "castle_legend":
        game, _packet = create_fight_stage_shortcut(
            "prepared_king",
            seed=seed,
        )

        game.king_fight["castle_timer"] = 1
        packet = game._advance_castle_timer()

        if packet is None:
            raise RuntimeError(
                "Castle-collapse shortcut did not finish."
            )

        packet = attach_developer_cause(
            game,
            packet,
            key,
        )

        return game, packet

    if key == "uncertain_victory":
        game, _packet = create_fight_stage_shortcut(
            "king_phase_two",
            seed=seed,
        )

        fight = game.king_fight

        fight["king_has_hit_player"] = True
        fight["clean_king_victory_possible"] = False
        fight["king_health"] = 0

        packet = game._finish_uncertain_king_victory()

        packet = attach_developer_cause(
            game,
            packet,
            key,
        )

        return game, packet

    if key == "clean_fate_choice":
        game, _packet = create_fight_stage_shortcut(
            "king_phase_two",
            seed=seed,
        )

        fight = game.king_fight

        fight["king_has_hit_player"] = False
        fight["clean_king_victory_possible"] = True
        fight["king_health"] = 0

        packet = game._enter_king_fate_choice()

        packet = attach_developer_cause(
            game,
            packet,
            key,
        )

        return game, packet

    if key == "crown_execute":
        game, _packet = create_endgame_shortcut(
            "clean_fate_choice",
            seed=seed,
        )

        packet = game.choose_king_fate(
            "execute_king"
        )

        packet = attach_developer_cause(
            game,
            packet,
            key,
        )

        return game, packet

    if key == "crown_jail":
        game, _packet = create_endgame_shortcut(
            "clean_fate_choice",
            seed=seed,
        )

        packet = game.choose_king_fate(
            "jail_king"
        )

        packet = attach_developer_cause(
            game,
            packet,
            key,
        )

        return game, packet

    if key == "retire_execute":
        game, _packet = create_endgame_shortcut(
            "crown_execute",
            seed=seed,
        )

        packet = game.retire_crown()

        packet = attach_developer_cause(
            game,
            packet,
            key,
        )

        return game, packet

    if key == "retire_jail":
        game, _packet = create_endgame_shortcut(
            "crown_jail",
            seed=seed,
        )

        packet = game.retire_crown()

        packet = attach_developer_cause(
            game,
            packet,
            key,
        )

        return game, packet

    raise AssertionError(
        "Unhandled endgame shortcut."
    )


def _print_direct_packet(packet: dict) -> None:
    import os

    from .presentation import print_endgame_packet

    stage = packet.get("stage")
    outcome = packet.get("outcome")

    opens_king_fight = (
        stage in (
            "king_phase_one",
            "elite_knight",
            "king_phase_two",
        )
        or outcome == "king_confrontation_started"
    )

    llm_fight_mode = (
        os.environ.get("GHOST_REAL_LLM") == "1"
        or os.environ.get("GHOST_DEV_LLM_NARRATION") == "1"
    )

    if (
        opens_king_fight
        and llm_fight_mode
        and os.environ.get("GHOST_LLM_DEBUG") != "1"
    ):
        return

    print()
    print_endgame_packet(packet)


def _open_crown_loop_menu(
    game: GhostRevolutionRun,
) -> None:
    if game.king_fight is None:
        return

    from .presentation import crown_loop_menu

    events = deque(maxlen=8)
    crown_loop_menu(game, events)


def _show_endgame_shortcut(
    game: GhostRevolutionRun,
    packet: dict,
) -> None:
    _print_direct_packet(packet)

    if game.complete:
        return

    stage = packet.get("stage")

    if stage == "fate_choice":
        print()
        print("Opening the king fate choice.")
        _open_king_fight_menu(game)
        return

    if stage == "crown_loop":
        print()
        print("Opening the Crown Loop.")
        _open_crown_loop_menu(game)


def run_endgame_shortcut_panel() -> None:
    choice_map = {
        "1": "weak_failure",
        "2": "champion_death",
        "3": "castle_legend",
        "4": "uncertain_victory",
        "5": "clean_fate_choice",
        "6": "crown_execute",
        "7": "crown_jail",
        "8": "retire_execute",
        "9": "retire_jail",
    }

    while True:
        print()
        print("=== ENDGAME / CROWN SHORTCUTS ===")
        print("1. Weak siege failure narration")
        print("2. Champion kills player narration")
        print("3. Castle-collapse legend narration")
        print("4. Uncertain king-fall victory narration")
        print("5. Clean victory fate choice")
        print("6. Crown Loop — king executed")
        print("7. Crown Loop — king jailed")
        print("8. Final retirement narration — execution")
        print("9. Final retirement narration — jail")
        print("0. Back")

        choice = input("> ").strip()

        if choice == "0":
            return

        shortcut = choice_map.get(choice)

        if shortcut is None:
            print("Unknown shortcut.")
            continue

        game, packet = create_endgame_shortcut(
            shortcut
        )

        _show_endgame_shortcut(
            game,
            packet,
        )

def run_developer_shortcut_panel() -> None:
    while True:
        print()
        print("=== GHOST REVOLUTION DEVELOPER SHORTCUTS ===")
        print("1. Weak siege failure")
        print("2. Wounded king fight")
        print("3. Prepared king fight")
        print("4. Jump directly to the Champion")
        print("5. Jump directly to king phase two")
        print("6. Brutal takeover state + king fight")
        print("7. Honorable takeover state + king fight")
        print("8. Endgame / Crown shortcuts")
        print("0. Quit")

        choice = input("> ").strip()

        if choice == "0":
            return

        if choice == "1":
            game, packet = create_endgame_shortcut(
                "weak_failure"
            )

            _show_endgame_shortcut(
                game,
                packet,
            )
            continue

        if choice == "2":
            game, packet = create_fight_stage_shortcut(
                "wounded_king"
            )

            _print_direct_packet(packet)
            _open_king_fight_menu(game)
            continue

        if choice == "3":
            game, packet = create_fight_stage_shortcut(
                "prepared_king"
            )

            _print_direct_packet(packet)
            _open_king_fight_menu(game)
            continue

        if choice == "4":
            game, packet = create_fight_stage_shortcut(
                "elite_knight"
            )

            _print_direct_packet(packet)
            _open_king_fight_menu(game)
            continue

        if choice == "5":
            game, packet = create_fight_stage_shortcut(
                "king_phase_two"
            )

            _print_direct_packet(packet)
            _open_king_fight_menu(game)
            continue

        if choice in {"6", "7"}:
            preset = (
                "brutal_takeover"
                if choice == "6"
                else "honorable_takeover"
            )

            game, loaded, result = _start_preset_siege(
                preset
            )

            _print_summary(loaded)
            _print_direct_packet(result)
            _open_king_fight_menu(game)
            continue

        if choice == "8":
            run_endgame_shortcut_panel()
            continue

        print("Unknown shortcut.")


def main() -> None:
    run_developer_shortcut_panel()


if __name__ == "__main__":
    main()
