"""
Terminal presentation layer for Ghost Revolution.

This module owns menus, formatting, event cards, and animation.
GhostRevolutionRun remains the deterministic game-state layer.
"""

from __future__ import annotations

from collections import deque
from time import sleep
import textwrap

from .demo import (
    CAMP_ACTIONS,
    CAMP_DAYS,
    LOCATIONS,
    REBELLION_ACTIONS,
    TOWN_IDS,
    GhostRevolutionRun,
)


WIDTH = 46
RECENT_EVENT_LIMIT = 6


_LLM_COST_LEDGER = {
    "strategy": 0.0,
    "narration": 0.0,
    "ambient": 0.0,
}


def _record_llm_measured_cost(role: str, result: dict) -> float | None:
    if not isinstance(result, dict):
        return None

    measured = result.get("measured_cost")

    if not isinstance(measured, dict):
        return None

    value = measured.get("total_cost")

    if not isinstance(value, (int, float)):
        return None

    normalized_role = str(role).strip().lower()

    if normalized_role not in _LLM_COST_LEDGER:
        return None

    _LLM_COST_LEDGER[normalized_role] += float(value)
    return float(value)


def _llm_cost_total() -> float:
    return round(sum(_LLM_COST_LEDGER.values()), 8)


def _measured_cost_lines(result: dict, role: str) -> list[str]:
    measured = result.get("measured_cost") if isinstance(result, dict) else None

    if not isinstance(measured, dict):
        estimate = result.get("cost_estimate", {}) if isinstance(result, dict) else {}
        return [
            "Measured token cost: unavailable",
            "Preflight estimate: "
            + str(estimate.get("total_cost_estimate")),
        ]

    return [
        "Role: " + str(role),
        "Reasoning effort: " + str(measured.get("reasoning_effort")),
        "Input tokens: " + str(measured.get("input_tokens")),
        "Cached input tokens: " + str(measured.get("cached_input_tokens")),
        "Output tokens: " + str(measured.get("output_tokens")),
        "Reasoning tokens: " + str(measured.get("reasoning_tokens")),
        "Measured token cost: $" + format(float(measured.get("total_cost", 0.0)), ".6f"),
        "Run LLM total: $" + format(_llm_cost_total(), ".6f"),
    ]


def line(char: str = "═") -> str:
    return char * WIDTH


def panel_lines(lines: list[str]) -> list[str]:
    """
    Expand multi-line content and wrap long prose safely.

    Every rendered line is guaranteed to fit inside the panel.
    """

    width = WIDTH - 2
    output = []

    for item in lines:
        raw_lines = str(item).splitlines() or [""]

        for raw_line in raw_lines:
            if not raw_line:
                output.append("")
                continue

            wrapped = textwrap.wrap(
                raw_line,
                width=width,
                break_long_words=False,
                break_on_hyphens=False,
            )

            output.extend(wrapped or [""])

    return output


def panel(title: str, lines: list[str]) -> str:
    title_text = f" {title} "
    top = "╔" + title_text.center(WIDTH - 2, "═") + "╗"

    body = [
        "║" + item.ljust(WIDTH - 2) + "║"
        for item in panel_lines(lines)
    ]

    bottom = "╚" + "═" * (WIDTH - 2) + "╝"

    return "\n".join([top, *body, bottom])


def meter(value: int, maximum: int, size: int = 10) -> str:
    safe_maximum = max(1, maximum)
    safe_value = max(0, min(value, safe_maximum))
    filled = int((safe_value / safe_maximum) * size)

    return "█" * filled + "░" * (size - filled)


def stock_label(stock: dict[str, int]) -> str:
    parts = [
        f"{name.title()} {amount}"
        for name, amount in stock.items()
        if amount > 0
    ]

    return ", ".join(parts) if parts else "None"


def action_summary(game: GhostRevolutionRun) -> str:
    maximum = (
        CAMP_ACTIONS
        if game.phase == "camp"
        else REBELLION_ACTIONS
    )

    used = maximum - game.actions

    return (
        f"Actions: {used} used / "
        f"{game.actions} left / "
        f"{maximum} total"
    )


def no_actions_message() -> str:
    return "No actions remain. End the day or leave town."


def town_status_label(
    game: GhostRevolutionRun,
    town_id: str,
) -> str:
    return game.town_condition(town_id)


def town_symbol(
    game: GhostRevolutionRun,
    town_id: str,
) -> str:
    """Return compact map markers; detail belongs in town menus."""
    town = game.towns[town_id]
    pieces = []

    if town["locked"]:
        pieces.append("[L]")

    guard_count = game.guard_count(town_id)

    if guard_count == 1:
        pieces.append("[G]")
    elif guard_count > 1:
        pieces.append(f"[G{guard_count}]")

    if game.knight_town == town_id:
        pieces.append("[K]")

    trust = game.town_trust(town_id)

    if trust >= 0.25:
        pieces.append("[+]")
    elif trust <= -0.25:
        pieces.append("[!]")

    return " ".join(pieces) or "[-]"




def town_role_icon(town_id: str) -> str:
    icons = {
        "ashfield": "[FARM]",
        "millcross": "[MARKET]",
        "crownmarket": "[CROWN]",
    }

    return icons[town_id]


def render_map(game: GhostRevolutionRun) -> str:
    markers = {
        "base": "B",
        "ashfield": "A",
        "millcross": "M",
        "crownmarket": "R",
        "castle": "C",
    }

    markers[game.location] = "@"

    crown = town_symbol(game, "crownmarket")
    mill = town_symbol(game, "millcross")
    ash = town_symbol(game, "ashfield")

    return "\n".join(
        [
            "        [ C ] KING'S CASTLE",
            "             │",
            (
                f"        [ {markers['crownmarket']} ] "
                f"Crownmarket  {crown}"
            ),
            "             │",
            (
                f"        [ {markers['millcross']} ] "
                f"Millcross    {mill}"
            ),
            "             │",
            (
                f"        [ {markers['ashfield']} ] "
                f"Ashfield     {ash}"
            ),
            "             │",
            f"        [ {markers['base']} ] HIDDEN BASE",
        ]
    )


def render_status(game: GhostRevolutionRun) -> str:
    phase = (
        f"PHASE {game.phase_number} — "
        f"{game.phase.upper()} DAY {game.phase_day}"
    )

    resources_line = (
        f"Gold {game.gold} | Food {game.food} | "
        f"Followers {game.followers}"
    )

    leader_line = (
        f"Leader: {game.leader_weapon_label()}"
    )

    armor_line = (
        f"Armor: {game.armor_item.title()}"
    )

    army_line = (
        f"Army Issued: {game.army_weapons_issued()} | "
        f"Weapon Stock: {game.weapon_stock_total()}"
    )

    raid_line = (
        (
            f"Active Raid: {game.active_raid['town']} "
            f"({game.active_raid['force']} deployed)"
        )
        if game.active_raid
        else "Active Raid: none"
    )

    heat_line = (
        f"Heat: {meter(game.heat, 10)} "
        f"{game.heat}/10"
    )

    roles = game.role_summary()

    roles_line = (
        f"Workers: {roles['workers']} | "
        f"Scouts: {roles['scouts']} | "
        f"Warriors: {roles['warriors']}"
    )

    king_line = (
        f"King Rule {meter(game.king_control, 10)} "
        f"{game.king_control}/10"
    )

    location_line = (
        f"Location: {game.location.title()}"
    )

    actions_line = action_summary(game)

    lines = [
        phase,
        "",
        render_map(game),
        "",
        resources_line,
        leader_line,
        armor_line,
        army_line,
        raid_line,
        heat_line,
        roles_line,
        king_line,
        location_line,
        actions_line,
    ]

    if game.location in game.towns:
        town = game.towns[game.location]
        relation = game.relationship(game.location)

        lines.extend(
            [
                "",
                (
                    f"{town['name']}: "
                    f"{town_role_icon(game.location)}"
                ),
                (
                    f"Condition: "
                    f"{town_status_label(game, game.location)}"
                ),
                (
                    f"Trust {relation['trust']:.3f} | "
                    f"Fear {town['fear']}/5 | "
                    f"Guards {game.guard_count(game.location)}"
                ),
                (
                    f"Recruitment today: "
                    f"{game.recruitment_available_today(game.location)} "
                    f"available"
                ),
            ]
        )

    return panel("GHOST REVOLUTION", lines)


def print_recent_events(events: deque[str]) -> None:
    if not events:
        return

    print()
    print(panel("RECENT EVENTS", list(events)))


def add_event(
    events: deque[str],
    message: str,
) -> None:
    events.appendleft(message.replace("\n", " "))


def travel_animation(
    origin: str,
    destination: str,
    cost: int,
) -> None:
    print()
    print(
        panel(
            f"TRAVELING TO {destination.upper()}",
            [
                f"Leaving {origin.title()}...",
                "",
            ],
        )
    )

    scenes = [
        "You move beneath the cover of old roads.",
        "You watch the tree line for royal patrols.",
        "The kingdom feels less safe with every mile.",
        "Smoke rises beyond the next ridge.",
    ]

    for step in range(cost):
        print(
            f"  {scenes[step % len(scenes)]} "
            f"[{step + 1}/{cost}]"
        )
        sleep(0.22)

    print()
    print(
        panel(
            "ARRIVAL",
            [
                f"You arrive in {destination.title()}.",
                "The town watches to see what you will do.",
            ],
        )
    )


def siege_narration(game: GhostRevolutionRun) -> list[str]:
    """
    Describe the siege using the scale of the rebellion.

    This is presentation only. The actual ending still comes from
    the deterministic game-state layer.
    """

    followers = game.followers

    if followers <= 0:
        opening = [
            "You stand beneath the castle walls alone.",
            "",
            "The guards do not raise an alarm at first.",
            "They simply watch as you approach.",
            "",
            "Your sword never reaches the gate.",
        ]
    elif followers < 10:
        opening = [
            "A handful of rebels gather beneath the castle walls.",
            "",
            "They came because they believed in you.",
            "The arrows begin before the first ladder reaches the gate.",
        ]
    elif followers < 35:
        opening = [
            "Dozens gather beneath the castle walls.",
            "",
            "For the first time, the crown sees a crowd",
            "that does not lower its eyes.",
        ]
    else:
        opening = [
            "The roads fill with rebel banners.",
            "",
            "Thousands of voices rise beneath the castle.",
            "Even the battlements fall silent as the kingdom arrives.",
        ]

    readiness = []

    if game.weapons <= 1:
        readiness.append("Most rebels carry little more than courage.")
    elif game.weapons >= 8:
        readiness.append("Weapons rise across the crowd like a forest of steel.")

    if game.armor >= 4:
        readiness.append("Shields and armor give the front line a chance.")
    elif game.armor <= 0:
        readiness.append("Few have armor when the arrows begin.")

    if game.king_control >= 8:
        readiness.append("The defenders stand confident behind royal banners.")
    elif game.king_control <= 3:
        readiness.append("The defenders look toward the gates with doubt.")

    support = sum(
        1
        for town_id in TOWN_IDS
        if game.town_trust(town_id) >= 0.25
    )

    if support >= 2:
        readiness.append("Voices inside the city answer your call.")
    elif game.guards_defeated >= 3:
        readiness.append("The castle has already felt the loss of its guards.")

    return opening + ([""] + readiness if readiness else [])


def siege_animation(game: GhostRevolutionRun) -> None:
    print()
    print(
        panel(
            "THE SIEGE BEGINS",
            siege_narration(game),
        )
    )

    sleep(0.30)


def king_response_card(
    events: list[str],
) -> None:
    print()
    print(panel("KINGDOM RESPONSE", events))

    sleep(0.30)


def camp_phase_card(game: GhostRevolutionRun) -> None:
    print()
    print(
        panel(
            "CAMP PHASE",
            [
                "The rebellion withdraws to hidden ground.",
                (
                    f"Camp Day {game.phase_day}/{CAMP_DAYS} "
                    f"| Actions {game.actions}"
                ),
                "Assign followers before the king responds.",
            ],
        )
    )


def print_legend() -> None:
    print()
    print(
        panel(
            "PLAYER LEGEND",
            [
                "@ means your current location.",
                "Travel and most actions use daily actions.",
                "Middle of Town: recruit, fight, seize supplies.",
                "Bar: one meaningful visit per town each day.",
                "Public Event: one gathering per town each day.",
                "Scout reports arrive automatically at day end.",
                "RAID A TOWN is a late-game liberation operation.",
                "Blacksmith: weapons, shields, repairs.",
                "Food Stall: buy survival supplies.",
                "Camp phase: assign followers to passive work.",
                "SIEGE THE CASTLE is always available.",
                "The king fight is turn-timed by castle collapse.",
                "After a clean victory, Retire the Crown ends the reign.",
            ],
        )
    )


def print_ghost_packet(packet: dict | None) -> None:
    if packet is None:
        return

    relation = packet["relationship"]
    world = packet["world_effects"]["state"]

    print()
    print(
        panel(
            "GHOST CONSEQUENCE",
            [
                (
                    f"Relationship: {relation['trust']:.3f} "
                    f"({relation['state']})"
                ),
                (
                    "Connected observers: "
                    f"{len(packet['propagation'].get('propagated', []))}"
                ),
                (
                    f"Pressure: "
                    f"{world['global_pressure']:.3f} "
                    f"({world['status']})"
                ),
                (
                    "Commerce: "
                    f"{packet['commerce']['service']['sale_access']}"
                ),
                f"Law: {packet['law']['action']}",
            ],
        )
    )


def hidden_base_menu(
    game: GhostRevolutionRun,
    events: deque[str],
) -> None:
    while not game.complete and game.location == "base":
        print()
        print(
            panel(
                "HIDDEN REBEL BASE",
                [
                    action_summary(game),
                    "",
                    "1. Review rebellion resources",
                    "2. Manage follower roles",
                    "3. Review camp assignments",
                    "4. RAID A TOWN",
                    "5. Player legend",
                    "6. Active raid status",
                    "0. Exit to Player Action Menu",
                ],
            )
        )
        print()

        choice = input("> ").strip()

        if choice == "0":
            return

        if choice == "1":
            print()
            print(render_status(game))
        elif choice == "2":
            follower_roles_menu(game, events)
        elif choice == "3":
            print()
            print(
                panel(
                    "CAMP ASSIGNMENTS",
                    [
                        (
                            f"Farmers {game.assignments['farmers']} | "
                            f"Foragers {game.assignments['foragers']}"
                        ),
                        (
                            f"Trainers {game.assignments['trainers']} | "
                            f"Smiths {game.assignments['smiths']}"
                        ),
                        f"Scouts {game.assignments['scouts']}",
                        (
                            "Assignments become active "
                            "during camp phase."
                        ),
                    ],
                )
            )
        elif choice == "4":
            raid_town_menu(game, events)
        elif choice == "5":
            print_legend()
        elif choice == "6":
            active_raid_panel(game)
        else:
            print("Unknown base action.")
            add_event(events, "Invalid base-menu choice.")


def follower_roles_menu(
    game: GhostRevolutionRun,
    events: deque[str],
) -> None:
    while not game.complete and game.location == "base":
        roles = game.role_summary()

        print()
        print(
            panel(
                "FOLLOWER ROLES",
                [
                    f"Followers: {game.followers}",
                    f"Workers: {roles['workers']}",
                    f"Scouts: {roles['scouts']}",
                    f"Warriors: {roles['warriors']}",
                    f"Workers free for camp: {roles['unassigned_workers']}",
                    "",
                    "1. Set scouts",
                    "2. Set warriors",
                    "0. Return to Base",
                ],
            )
        )
        print()

        choice = input("> ").strip()

        if choice == "0":
            return

        role_map = {
            "1": "scouts",
            "2": "warriors",
        }

        role = role_map.get(choice)

        if role is None:
            print("Unknown role option.")
            continue

        print(f"Set total {role}:")
        raw = input("> ").strip()

        try:
            amount = int(raw)
        except ValueError:
            print("Enter a whole number.")
            continue

        if game.set_combat_role(role, amount):
            print(game.last_action_note)
            add_event(events, game.last_action_note)
        else:
            print(game.last_action_note)
            add_event(events, game.last_action_note)


def active_raid_panel(
    game: GhostRevolutionRun,
) -> None:
    raid = game.active_raid_summary()

    if raid is None:
        print()
        print(
            panel(
                "ACTIVE RAID",
                ["No rebel force is currently deployed."],
            )
        )
        return

    weapons = sum(raid["weapon_issue"].values())
    shields = sum(raid["shield_issue"].values())

    print()
    print(
        panel(
            "ACTIVE RAID",
            [
                f"Target: {raid['town']}",
                f"Military camp: {raid['camp']}",
                f"Force deployed: {raid['force']} warriors",
                f"Weapons deployed: {weapons}",
                f"Shields deployed: {shields}",
                f"Food committed: {raid['food_committed']}",
                (
                    f"Intel: {raid['intel_level']}/3 "
                    f"(+{raid['intel_bonus']} readiness)"
                ),
                f"Approach odds: {raid['odds']}",
                "",
                "The force is in the field.",
                "Battle resolution is not active yet.",
            ],
        )
    )


def raid_plan_panel(
    game: GhostRevolutionRun,
    target: str,
) -> None:
    readiness = game.raid_readiness(target)

    print()
    print(
        panel(
            f"{readiness['town'].upper()} RAID PLAN",
            [
                f"Town condition: {readiness['condition']}",
                f"Military camp: {readiness['camp']}",
                f"Knight: {readiness['knight']}",
                f"Warlord: {readiness['warlord']}",
                f"Royal garrison: {readiness['garrison']}",
                "",
                (
                    f"Raid force: {readiness['warriors']} / "
                    f"{readiness['recommended_warriors']} "
                    "recommended"
                ),
                (
                    f"Food: {readiness['food']} available / "
                    f"{readiness['food_required']} required"
                ),
                (
                    f"Army weapons: {readiness['issued_weapons']} / "
                    f"{readiness['recommended_weapons']} "
                    "recommended"
                ),
                (
                    f"Shield issue: {readiness['issued_shields']} | "
                    f"Training: {readiness['training_level']}"
                ),
                f"Leader weapon: {readiness['leader_weapon']}",
                f"Odds: {readiness['odds']}",
                "",
                (
                    "READY FOR FUTURE RAID"
                    if readiness["ready"]
                    else "NOT READY FOR RAID"
                ),
            ],
        )
    )


def raid_preparation_menu(
    game: GhostRevolutionRun,
    events: deque[str],
    target: str,
) -> None:
    while (
        not game.complete
        and game.location == "base"
        and game.raid_plan
        and game.raid_plan["target"] == target
    ):
        readiness = game.raid_readiness(target)

        print()
        print(
            panel(
                "RAID PREPARATION",
                [
                    (
                        f"Target: {readiness['town']} | "
                        f"Recommended force: "
                        f"{readiness['recommended_warriors']}"
                    ),
                    (
                        f"Warriors: {readiness['warriors']} / "
                        f"{readiness['available_warriors']} available"
                    ),
                    (
                        f"Weapon stock: "
                        f"{stock_label(readiness['weapon_stock'])}"
                    ),
                    (
                        f"Shield stock: "
                        f"{stock_label(readiness['shield_stock'])}"
                    ),
                    "",
                    "1. Set raid force",
                    "2. Issue swords",
                    "3. Issue axes",
                    "4. Issue spears",
                    "5. Issue bows",
                    "6. Issue light shields",
                    "7. Issue medium shields",
                    "8. Issue heavy shields",
                    "9. Review raid readiness",
                    "10. Cancel plan / return gear",
                    "11. Commit raid / deploy force",
                    "0. Return to Raid Targets",
                ],
            )
        )
        print()

        choice = input("> ").strip()

        if choice == "0":
            return

        if choice == "1":
            print("Set raid force:")
            raw = input("> ").strip()

            try:
                amount = int(raw)
            except ValueError:
                print("Enter a whole number.")
                continue

            success = game.set_raid_force(amount)
        elif choice in ("2", "3", "4", "5"):
            weapon_map = {
                "2": "sword",
                "3": "axe",
                "4": "spear",
                "5": "bow",
            }

            weapon = weapon_map[choice]
            print(f"Issue how many {weapon}s?")
            raw = input("> ").strip()

            try:
                amount = int(raw)
            except ValueError:
                print("Enter a whole number.")
                continue

            success = game.set_raid_weapon_issue(
                weapon,
                amount,
            )
        elif choice in ("6", "7", "8"):
            shield_map = {
                "6": "light",
                "7": "medium",
                "8": "heavy",
            }

            shield = shield_map[choice]
            print(f"Issue how many {shield} shields?")
            raw = input("> ").strip()

            try:
                amount = int(raw)
            except ValueError:
                print("Enter a whole number.")
                continue

            success = game.set_raid_shield_issue(
                shield,
                amount,
            )
        elif choice == "9":
            raid_plan_panel(game, target)
            continue
        elif choice == "10":
            success = game.cancel_raid_plan()
        elif choice == "11":
            success = game.commit_raid()
        else:
            print("Unknown raid preparation choice.")
            continue

        print(game.last_action_note)
        add_event(events, game.last_action_note)

        if not success:
            continue


def raid_town_menu(
    game: GhostRevolutionRun,
    events: deque[str],
) -> None:
    while not game.complete and game.location == "base":
        if game.active_raid:
            active_raid_panel(game)
            print("A raid is already deployed. No second plan can be opened.")
            return

        roles = game.role_summary()

        print()
        print(
            panel(
                "RAID A TOWN",
                [
                    "Raid battles are not active yet.",
                    "Prepare forces, equipment, and supplies.",
                    "",
                    f"Warriors available: {roles['warriors']}",
                    f"Warriors deployed: {roles['deployed_warriors']}",
                    f"Food stores: {game.food}",
                    f"Weapon stock: {stock_label(game.weapon_stock)}",
                    f"Shield stock: {stock_label(game.shield_stock)}",
                    f"Leader weapon: {game.leader_weapon_label()}",
                    "",
                    "1. Ashfield — 25 warriors recommended",
                    "2. Millcross — 50 warriors recommended",
                    "3. Crownmarket — 75 warriors recommended",
                    "0. Return to Base",
                ],
            )
        )
        print()

        choice = input("> ").strip()

        if choice == "0":
            return

        target_map = {
            "1": "ashfield",
            "2": "millcross",
            "3": "crownmarket",
        }

        target = target_map.get(choice)

        if target is None:
            print("Unknown raid target.")
            continue

        readiness = game.plan_raid(target)

        if readiness is None:
            print(game.last_action_note)
            add_event(events, game.last_action_note)
            continue

        add_event(events, game.last_action_note)
        raid_preparation_menu(game, events, target)


def blacksmith_menu(
    game: GhostRevolutionRun,
    events: deque[str],
) -> None:
    options = {
        "1": ("sword", "Sword acquired."),
        "2": ("spear", "Spear acquired."),
        "3": ("shield", "Shield acquired."),
        "4": ("axe", "Axe acquired."),
        "5": ("bow", "Bow acquired."),
        "6": ("repair", "Equipment repaired."),
    }

    while not game.complete:
        print()
        print(
            panel(
                "BLACKSMITH",
                [
                    action_summary(game),
                    "",
                    "1. Sword  — 12 gold",
                    "2. Spear  — 14 gold",
                    "3. Shield — 10 gold",
                    "4. Axe    — 15 gold",
                    "5. Bow    — 16 gold",
                    "6. Repair — 6 gold",
                    "0. Exit to Town",
                ],
            )
        )
        print()

        choice = input("> ").strip()

        if choice == "0":
            return

        selected = options.get(choice)

        if selected is None:
            print("Unknown blacksmith option.")
            continue

        item, success = selected

        if game.blacksmith_buy(item):
            print(success)
            add_event(events, success)
        else:
            message = (
                game.last_action_note
                or "The blacksmith refuses the sale."
            )
            print(message)
            add_event(events, message)


def food_menu(
    game: GhostRevolutionRun,
    events: deque[str],
) -> None:
    options = {
        "1": ("bread", "Bread added to camp stores."),
        "2": ("meat", "Meat added to camp stores."),
        "3": ("vegetables", "Vegetables added to camp stores."),
    }

    while not game.complete:
        print()
        print(
            panel(
                "FOOD STALL",
                [
                    action_summary(game),
                    "",
                    "1. Bread      +1 food | 6 gold",
                    "2. Meat       +3 food | 14 gold",
                    "3. Vegetables +2 food | 10 gold",
                    "0. Exit to Town",
                ],
            )
        )
        print()

        choice = input("> ").strip()

        if choice == "0":
            return

        selected = options.get(choice)

        if selected is None:
            print("Unknown food-stall option.")
            continue

        item, success = selected

        if game.buy_food(item):
            print(success)
            add_event(events, success)
        else:
            message = (
                game.last_action_note
                or "You cannot afford that purchase."
            )
            print(message)
            add_event(events, message)


def goods_menu(
    game: GhostRevolutionRun,
    events: deque[str],
) -> None:
    options = {
        "1": ("seeds", "Seeds secured for future farming."),
        "2": (
            "cooking_kit",
            "Cooking equipment secured for camp.",
        ),
    }

    while not game.complete:
        print()
        print(
            panel(
                "COMMON GOODS",
                [
                    action_summary(game),
                    "",
                    "1. Seeds       | 8 gold",
                    "2. Cooking Kit | 10 gold",
                    "0. Exit to Town",
                ],
            )
        )
        print()

        choice = input("> ").strip()

        if choice == "0":
            return

        selected = options.get(choice)

        if selected is None:
            print("Unknown goods-stall option.")
            continue

        item, success = selected

        if game.buy_common_goods(item):
            print(success)
            add_event(events, success)
        else:
            message = (
                game.last_action_note
                or "The goods are beyond your reach."
            )
            print(message)
            add_event(events, message)


def guard_down_menu(
    game: GhostRevolutionRun,
    events: deque[str],
) -> None:
    status = game.guard_combat_status()

    if status is None or status["stage"] != "down":
        return

    witness_text = {
        1: "One person watches from a doorway.",
        2: "A couple of people watch from the street edge.",
        3: "Several townspeople watch in silence.",
        4: "A small crowd has gathered.",
        5: "The whole street seems to be watching.",
    }

    if status["conduct"] >= 2:
        conduct_text = "Your victory looked controlled."
    elif status["conduct"] >= 0:
        conduct_text = "The fight looked hard and uncertain."
    else:
        conduct_text = "The fight looked reckless and costly."

    while not game.complete and game.guard_combat is not None:
        print()
        print(
            panel(
                "GUARD DOWN",
                [
                    action_summary(game),
                    witness_text[
                        max(1, min(5, status["witnesses"]))
                    ],
                    conduct_text,
                    "",
                    "The guard is disarmed and alive.",
                    "",
                    "1. Take his pay pouch and leave him alive",
                    "2. Execute the guard",
                ],
            )
        )
        print()

        choice = input("> ").strip()
        packet = None

        if choice == "1":
            packet = game.resolve_guard_down("leave")
        elif choice == "2":
            packet = game.resolve_guard_down("execute")
        else:
            print("Choose 1 or 2.")
            continue

        message = (
            game.last_action_note
            or "That outcome cannot happen right now."
        )

        print(message)
        add_event(events, message)

        if packet is not None:
            print_ghost_packet(packet)

        return


def guard_combat_menu(
    game: GhostRevolutionRun,
    events: deque[str],
) -> None:
    if game.guard_combat is None:
        packet = game.fight_guard()

        message = (
            game.last_action_note
            or "That combat cannot begin right now."
        )

        print(message)
        add_event(events, message)

        if packet is not None:
            print_ghost_packet(packet)

        if game.guard_combat is None:
            return

    while not game.complete and game.guard_combat is not None:
        status = game.guard_combat_status()

        if status is None:
            return

        if status["stage"] == "down":
            guard_down_menu(game, events)
            return

        lines = [
            action_summary(game),
            f"Opponent: {status['guard_label']}",
            f"Garrison: {status['guards_remaining']} remaining",
            (
                "Player HP: "
                f"{meter(status['player_health'], status['player_max_health'])} "
                f"{status['player_health']}/{status['player_max_health']}"
            ),
            (
                "Guard HP:  "
                f"{meter(status['guard_health'], status['guard_max_health'])} "
                f"{status['guard_health']}/{status['guard_max_health']}"
            ),
            (
                f"Exchange: {status['exchange_count']} | "
                f"Royal noise: {status['combat_noise']}"
            ),
            "",
            f"Guard Tell: {status['guard_tell']}",
            "",
        ]

        if status["free_attack"]:
            lines.extend(
                [
                    "The guard lost form. Take your free attack.",
                    "",
                    "1. Heavy attack",
                    "2. Light attack",
                    "0. Break away",
                ]
            )
        else:
            lines.extend(
                [
                    "Read the body, not a counter chart.",
                    "",
                    "1. Heavy attack",
                    "2. Light attack",
                    "3. Feint into attack",
                    "4. Parry",
                    "5. Deflect",
                    "6. Dodge",
                    "0. Break away",
                ]
            )

        print()
        print(panel("GUARD COMBAT", lines))
        print()

        choice = input("> ").strip()
        packet = None
        move = None

        if choice == "0":
            packet = game.retreat_guard_combat()
        elif choice == "1":
            move = "heavy"
        elif choice == "2":
            move = "light"
        elif (
            not status["free_attack"]
            and choice == "3"
        ):
            print("Feint follow-up: 1. Heavy  2. Light  0. Cancel")
            follow_up = input("> ").strip()

            if follow_up == "1":
                move = "feint_heavy"
            elif follow_up == "2":
                move = "feint_light"
            elif follow_up == "0":
                continue
            else:
                print("Unknown feint choice.")
                continue
        elif (
            not status["free_attack"]
            and choice == "4"
        ):
            move = "parry"
        elif (
            not status["free_attack"]
            and choice == "5"
        ):
            move = "deflect"
        elif (
            not status["free_attack"]
            and choice == "6"
        ):
            move = "dodge"
        else:
            print("Unknown combat move.")
            continue

        if move is not None:
            packet = game.resolve_guard_combat_move(move)

        message = (
            game.last_action_note
            or "That combat move cannot happen right now."
        )

        print(message)
        add_event(events, message)

        if packet is not None:
            print_ghost_packet(packet)


def guard_encounter_menu(
    game: GhostRevolutionRun,
    events: deque[str],
) -> None:
    while not game.complete:
        if game.location not in game.towns:
            return

        town = game.towns[game.location]

        if not game.has_active_guard(game.location):
            message = (
                "There are no royal guards stationed in "
                f"{town['name']}."
            )
            print(message)
            add_event(events, message)
            return

        passage_active = game.guard_passage_active(
            game.location
        )

        passage = (
            "ACTIVE"
            if passage_active
            else "none"
        )

        fight_label = (
            "4. Fight guard [safe passage active]"
            if passage_active
            else "4. Fight guard"
        )

        print()
        print(
            panel(
                f"ROYAL GUARD — {town['name'].upper()}",
                [
                    action_summary(game),
                    (
                        f"Town Fear: {town['fear']} | "
                        f"Local Trust: "
                        f"{game.town_trust(game.location):.3f}"
                    ),
                    f"Royal Alert: {game.royal_alert}/5",
                    (
                        "Town Memory: "
                        f"{game.town_memory_label(game.location)}"
                    ),
                    f"Safe Passage Today: {passage}",
                    (
                        "Guards stationed: "
                        f"{game.guard_count(game.location)}"
                    ),
                    (
                        "Facing: "
                        f"{game.active_guard_label(game.location)}"
                    ),
                    "",
                    "1. Question guard",
                    "2. Bribe guard (6 gold)",
                    "3. Recruit guard",
                    fight_label,
                    "0. Leave guard encounter",
                ],
            )
        )
        print()

        choice = input("> ").strip()
        packet = None

        if choice == "0":
            return

        if choice == "1":
            packet = game.question_guard()
        elif choice == "2":
            packet = game.bribe_guard()
        elif choice == "3":
            packet = game.recruit_guard()
        elif choice == "4":
            if passage_active:
                message = (
                    "Your bribe has bought silence for today. "
                    "The guard will not draw while safe passage is active."
                )

                print(message)
                add_event(events, message)
                continue

            guard_combat_menu(game, events)

            if not game.has_active_guard(game.location):
                return

            continue
        else:
            print("Unknown guard action.")
            continue

        message = (
            game.last_action_note
            or "That guard action cannot happen right now."
        )

        print(message)
        add_event(events, message)

        if packet is not None:
            print_ghost_packet(packet)

        if not game.has_active_guard(game.location):
            return

def middle_of_town_menu(
    game: GhostRevolutionRun,
    events: deque[str],
) -> None:
    while not game.complete:
        town = game.towns.get(game.location)

        if town is None:
            return

        guard_option = (
            "3. Guard encounter"
            if game.has_active_guard(game.location)
            else "3. No royal guards stationed here"
        )

        print()
        print(
            panel(
                "MIDDLE OF TOWN",
                [
                    action_summary(game),
                    f"Royal Alert: {game.royal_alert}/5",
                    (
                        "Town Memory: "
                        f"{game.town_memory_label(game.location)}"
                    ),
                    "",
                    "1. Recruit quietly",
                    "2. Review scout reports",
                    guard_option,
                    "4. Seize royal supplies",
                    "5. Bribe town network",
                    "6. Earn honest gold",
                    "0. Exit to Town",
                ],
            )
        )
        print()

        choice = input("> ").strip()
        packet = None

        if choice == "0":
            return

        if choice == "1":
            packet = game.recruit_quietly()
            action_text = "You speak with people in the shadows."
        elif choice == "2":
            scout_intel_menu(game, events)
            continue
        elif choice == "3":
            if not game.has_active_guard(game.location):
                message = (
                    "There are no royal guards stationed in "
                    f"{town['name']}."
                )
                print(message)
                add_event(events, message)
                continue

            guard_encounter_menu(game, events)
            continue
        elif choice == "4":
            packet = game.seize_royal_supplies()
            action_text = game.last_action_note
        elif choice == "5":
            packet = game.bribe_network()
            action_text = "Coins change hands behind closed doors."
        elif choice == "6":
            packet = game.earn_honest_gold()
            action_text = game.last_action_note
        else:
            print("Unknown town action.")
            continue

        if packet is None:
            message = (
                game.last_action_note
                or (
                    no_actions_message()
                    if game.actions <= 0
                    else "That action cannot happen right now."
                )
            )

            print(message)
            add_event(events, message)
        else:
            print(action_text)
            add_event(events, action_text)

        print_ghost_packet(packet)

def resolve_town_packet(
    game: GhostRevolutionRun,
    events: deque[str],
    packet: dict | None,
    action_text: str,
    event_text: str,
) -> None:
    """
    Present one Ghost-routed town action consistently.

    The game layer owns menu flow and action economy.
    Ghost owns the persistent social consequence packet.
    """

    if packet is None:
        message = (
            game.last_action_note
            or (
                no_actions_message()
                if game.actions <= 0
                else "That action cannot happen right now."
            )
        )

        print(message)
        add_event(events, message)
        return

    print(action_text)
    add_event(events, event_text)
    print_ghost_packet(packet)


def bar_menu(
    game: GhostRevolutionRun,
    events: deque[str],
) -> None:
    while (
        not game.complete
        and game.location in game.towns
        and game.phase == "rebellion"
    ):
        print()
        print(
            panel(
                "BAR",
                [
                    action_summary(game),
                    "",
                    "1. Gather rumors",
                    "2. Recruit quietly",
                    "3. Speak with locals",
                    "4. Earn small local work",
                    "0. Return to Town",
                ],
            )
        )
        print()

        choice = input("> ").strip()

        if choice == "0":
            return

        if choice == "1":
            packet = game.bar_rumor()
            resolve_town_packet(
                game,
                events,
                packet,
                "Whispers travel faster than royal patrols.",
                "You gather rumors at the bar.",
            )
        elif choice == "2":
            packet = game.bar_recruit_quietly()
            resolve_town_packet(
                game,
                events,
                packet,
                "You speak with possible rebels in the shadows.",
                "You recruit quietly through the bar.",
            )
        elif choice == "3":
            packet = game.bar_rumor()
            resolve_town_packet(
                game,
                events,
                packet,
                "You listen before you ask anyone to risk anything.",
                "You speak with locals at the bar.",
            )
        elif choice == "4":
            packet = game.bar_local_work()
            resolve_town_packet(
                game,
                events,
                packet,
                game.last_action_note,
                "You earn honest local work at the bar.",
            )
        else:
            print("Unknown bar action.")


def public_event_menu(
    game: GhostRevolutionRun,
    events: deque[str],
) -> None:
    if not game.begin_public_event():
        print(game.last_action_note)
        add_event(events, game.last_action_note)
        return

    while (
        not game.complete
        and game.location in game.towns
        and game.phase == "rebellion"
    ):
        used = game.public_event_summary()["used_actions"]

        def label(key: str, text: str) -> str:
            if key in used:
                return f"[USED] {text}"

            return f"[OPEN] {text}"

        print()
        print(
            panel(
                "LOCAL PUBLIC EVENT",
                [
                    action_summary(game),
                    (
                        f"Gold: {game.gold} | "
                        f"Followers: {game.followers}"
                    ),
                    "",
                    label("speech", "1. Speak publicly"),
                    label("recruit", "2. Recruit from the crowd"),
                    label("rally", "3. Calm fear / rally people"),
                    "",
                    "0. Leave Event",
                ],
            )
        )
        print()

        choice = input("> ").strip()

        if choice == "0":
            game.leave_public_event()
            print(game.last_action_note)
            add_event(events, game.last_action_note)
            return

        if choice == "1":
            packet = game.speak_publicly()
            resolve_town_packet(
                game,
                events,
                packet,
                "You step before the gathered crowd.",
                "You speak publicly and draw royal attention.",
            )
        elif choice == "2":
            packet = game.recruit_openly()
            resolve_town_packet(
                game,
                events,
                packet,
                "People step forward after hearing your call.",
                "You recruit openly from the crowd.",
            )
        elif choice == "3":
            packet = game.rally_people()
            resolve_town_packet(
                game,
                events,
                packet,
                "You give the crowd a reason not to surrender to fear.",
                "You rally people and lower local fear.",
            )
        else:
            print("Unknown public-event action.")

def town_arrival_menu(
    game: GhostRevolutionRun,
    events: deque[str],
) -> None:
    descriptions = {
        "ashfield": (
            "A poor outer town. Farms and frightened families."
        ),
        "millcross": (
            "A labor town where commerce can become rebellion."
        ),
        "crownmarket": (
            "The king's shadow stretches across every stall."
        ),
    }

    while (
        not game.complete
        and game.location in game.towns
        and game.phase == "rebellion"
    ):
        town = game.towns[game.location]

        print()
        print(
            panel(
                town["name"].upper(),
                [
                    action_summary(game),
                    (
                        f"Gold: {game.gold} | "
                        f"Followers: {game.followers}"
                    ),
                    "",
                    descriptions[game.location],
                    f"Role: {town_role_icon(game.location)}",
                    (
                        f"Condition: "
                        f"{town_status_label(game, game.location)}"
                    ),
                    (
                        f"Recruitment available: "
                        f"{game.recruitment_available_today(game.location)}"
                    ),
                    "",
                    "1. Blacksmith",
                    "2. Food Stall",
                    "3. Common Goods Stall",
                    "4. Middle of Town",
                    "5. Bar",
                    "6. Local Public Event",
                    "0. Exit to Kingdom Map",
                ],
            )
        )
        print()

        choice = input("> ").strip()

        if choice == "0":
            return

        if choice == "1":
            blacksmith_menu(game, events)
        elif choice == "2":
            food_menu(game, events)
        elif choice == "3":
            goods_menu(game, events)
        elif choice == "4":
            middle_of_town_menu(game, events)
        elif choice == "5":
            bar_menu(game, events)
        elif choice == "6":
            public_event_menu(game, events)
        else:
            print("Unknown town destination.")


def enter_current_location(
    game: GhostRevolutionRun,
    events: deque[str],
) -> None:
    """
    Open the location marked with @ on the map.
    """

    if game.location == "base":
        hidden_base_menu(game, events)
    elif game.location in game.towns:
        town_arrival_menu(game, events)
    else:
        print("There is nothing to enter here.")
        add_event(events, "Current location has no enterable menu.")


def scout_intel_menu(
    game: GhostRevolutionRun,
    events: deque[str],
) -> None:
    summary = game.scout_report_summary()

    reports = summary["last_reports"] or [
        "No scout reports have arrived yet.",
    ]

    scout_beliefs = summary["information"][
        "latest_scout_beliefs"
    ]

    belief_lines = [
        (
            f"{town_id.title()}: "
            f"{belief['dominant_candidate'].replace('_', ' ')} "
            f"({belief['confidence']:.0%})"
        )
        for town_id, belief in sorted(
            scout_beliefs.items()
        )
    ] or [
        "No scout report has been evaluated yet.",
    ]

    lines = [
        (
            f"Assigned scouts: "
            f"{summary['assigned_scouts']}"
        ),
        (
            "Daily report capacity: "
            f"{summary['assigned_scouts']}"
        ),
        (
            f"Reports filed today: "
            f"{summary['reports_today']}"
        ),
        (
            f"Scouts captured: "
            f"{summary['scouts_captured']}"
        ),
        "",
        (
            f"Ashfield intel: "
            f"{summary['intel']['ashfield']}/3"
        ),
        (
            f"Millcross intel: "
            f"{summary['intel']['millcross']}/3"
        ),
        (
            f"Crownmarket intel: "
            f"{summary['intel']['crownmarket']}/3"
        ),
        (
            "Crownmarket capture risk: "
            f"{summary['crownmarket_capture_risk']}%"
        ),
        "",
        "LATEST REPORTS:",
        *reports,
        "",
        "PLAYER BELIEFS (REPORT-BASED):",
        *belief_lines,
    ]

    print()
    print(panel("SCOUT REPORTS", lines))

def kingdom_map_menu(
    game: GhostRevolutionRun,
    events: deque[str],
) -> None:
    print()
    print(
        panel(
            "KINGDOM MAP",
            [
                    action_summary(game),
                    "",
                render_map(game),
                "",
                "Choose a numbered route below.",
            ],
        )
    )

    choices = []

    for destination in LOCATIONS:
        if destination == game.location:
            continue

        cost = game.travel_cost(destination)
        choices.append(destination)

        print(
            f"{len(choices)}. {destination.title()} "
            f"({cost} action{'s' if cost != 1 else ''})"
        )

    print("0. Cancel")
    print()

    choice = input("> ").strip()

    if choice == "0":
        return

    try:
        destination = choices[int(choice) - 1]
    except (ValueError, IndexError):
        print("Invalid travel choice.")
        add_event(events, "Invalid kingdom-map choice.")
        return

    origin = game.location
    cost = game.travel_cost(destination)

    if game.travel(destination):
        travel_animation(origin, destination, cost)
        add_event(
            events,
            f"Traveled from {origin.title()} to "
            f"{destination.title()}.",
        )

        if destination in game.towns:
            town_arrival_menu(game, events)
        elif destination == "base":
            hidden_base_menu(game, events)
    else:
        print("Travel failed. The route is blocked or too costly.")
        add_event(events, "Travel attempt failed.")


def camp_menu(
    game: GhostRevolutionRun,
    events: deque[str],
) -> None:
    camp_phase_card(game)

    assignment_map = {
        "1": "farmers",
        "2": "foragers",
        "3": "trainers",
        "4": "smiths",
        "5": "scouts",
    }

    while not game.complete and game.phase == "camp":
        print()
        print(
            panel(
                "CAMP COMMAND",
                [
                    action_summary(game),
                    "",
                    (
                        f"Farmers {game.assignments['farmers']} | "
                        f"Foragers {game.assignments['foragers']}"
                    ),
                    (
                        f"Trainers {game.assignments['trainers']} | "
                        f"Smiths {game.assignments['smiths']}"
                    ),
                    f"Scouts {game.assignments['scouts']}",
                    f"Unassigned followers: {game.available_workers()}",
                    "",
                    "1. Set farmers",
                    "2. Set foragers",
                    "3. Set trainers",
                    "4. Set smiths",
                    "5. Set scouts",
                    "6. Train rebels now",
                    "7. End camp day",
                    "8. Player legend",
                    "0. Quit",
                ],
            )
        )
        print()

        choice = input("> ").strip()

        if choice == "0":
            game.quit_game = True
        elif choice in assignment_map:
            print("Assign how many followers?")
            raw = input("> ").strip()

            try:
                amount = int(raw)
            except ValueError:
                print("Enter a whole number.")
                continue

            if game.set_assignment(
                assignment_map[choice],
                amount,
            ):
                message = (
                    f"{assignment_map[choice].title()} "
                    f"assignment set to {amount}."
                )
                print(message)
                add_event(events, message)
            else:
                print("Assignment rejected.")
                add_event(events, "Invalid camp assignment.")
        elif choice == "6":
            if game.train_rebels():
                print("Rebels train beneath torchlight.")
                add_event(events, "Camp training produced a weapon.")
            else:
                print("Training is unavailable.")
        elif choice == "7":
            result = game.end_day()
            output = result.get("camp_output")

            if output:
                add_event(
                    events,
                    (
                        "Camp output: "
                        f"+{output['food_gain']} food, "
                        f"+{output['gold_gain']} gold, "
                        f"+{output['weapon_gain']} weapons."
                    ),
                )

            if result.get("king_response"):
                king_response_card(result["king_response"])

                for event in result["king_response"]:
                    add_event(events, event)
        elif choice == "8":
            print_legend()
        else:
            print("Unknown camp action.")


def print_endgame_packet(packet: dict | None) -> None:
    if packet is None:
        return

    lines = [
        f"Outcome: {packet.get('outcome', 'unknown')}",
    ]

    if "stage" in packet:
        lines.append(f"Stage: {packet['stage']}")

    if "castle_timer" in packet:
        lines.append(
            f"Castle Timer: {packet['castle_timer']} turns"
        )

    if "player_health" in packet:
        lines.append(f"Player HP: {packet['player_health']}")

    if "king_health" in packet:
        lines.append(f"King HP: {packet['king_health']}")

    if "elite_knight_health" in packet:
        lines.append(
            f"Champion HP: {packet['elite_knight_health']}"
        )

    exchange = packet.get("exchange")

    if isinstance(exchange, dict):
        lines.extend(
            [
                "",
                f"Read result: {exchange.get('result', '-')}",
                exchange.get("message", ""),
            ]
        )

    if "choices" in packet:
        lines.extend(
            [
                "",
                "Choice unlocked: execute or jail the king.",
            ]
        )

    if packet.get("tell"):
        lines.extend(["", f"Tell: {packet['tell']}"])

    if packet.get("note"):
        lines.extend(["", packet["note"]])

    if packet.get("ending"):
        lines.extend(["", packet["ending"]])

    print()
    wounded_start_explanation = packet.get(
        "wounded_start_explanation"
    )

    if wounded_start_explanation:
        lines.append("")

        for item in wounded_start_explanation:
            lines.append(str(item))

    developer_cause = packet.get("developer_cause")

    if developer_cause:
        lines.append("")
        lines.append("Developer cause:")

        for item in developer_cause:
            lines.append(str(item))

    print(panel("ENDGAME PACKET", lines))


def king_fight_stage_label(stage: str) -> str:
    labels = {
        "king_phase_one": "King Fight — Phase One",
        "elite_knight": "The King's Champion",
        "king_phase_two": "King Fight — Phase Two",
        "fate_choice": "The King's Fate",
        "crown_loop": "Crown Loop",
    }

    return labels.get(stage, stage.replace("_", " ").title())


def _king_fight_move_from_choice(choice: str) -> str | None:
    return {
        "1": "heavy",
        "2": "light",
        "4": "parry",
        "5": "deflect",
        "6": "dodge",
    }.get(choice)




def _king_fight_llm_enabled() -> bool:
    import os

    return (
        os.environ.get("GHOST_REAL_LLM") == "1"
        or os.environ.get("GHOST_DEV_LLM_NARRATION") == "1"
    )


def _print_king_fight_mocking_lines(
    packet: dict,
) -> None:
    if not isinstance(packet, dict):
        return

    raw_lines = packet.get(
        "king_mocking_lines"
    )

    if not isinstance(
        raw_lines,
        (list, tuple),
    ):
        return

    lines = [
        str(line).strip()
        for line in raw_lines
        if str(line).strip()
    ]

    if not lines:
        return

    print()
    print(
        panel(
            "THE KING'S FINAL WORD",
            [
                '"' + line + '"'
                for line in lines
            ],
        )
    )

def _print_king_fight_llm_narration(packet: dict) -> None:
    import os

    from ghost.examples.ghost_revolution.llm_bridge import (
        GhostRevolutionLLMBridge,
        OpenAIResponsesClient,
        config_for_role,
        generate_king_fight_adapter_fallback_narration,
    )

    if os.environ.get("GHOST_REAL_LLM") == "1":
        try:
            bridge = GhostRevolutionLLMBridge(
                client=OpenAIResponsesClient(),
                config=config_for_role("narration"),
            )

            result = bridge.generate_king_fight_narration(packet)
            estimate = result.get("cost_estimate", {})
            _record_llm_measured_cost("narration", result)

            lines = [
                result.get("text", ""),
            ]

            if os.environ.get("GHOST_LLM_DEBUG") == "1":
                lines.extend(
                    [
                        "",
                        f"Provider called: {result.get('provider_called')}",
                        f"Model: {result.get('response_model') or estimate.get('model')}",
                        *_measured_cost_lines(result, "narration"),
                    ]
                )

            print()
            print(panel("REAL LLM FIGHT BEAT", lines))
            return
        except Exception as exc:
            fallback = generate_king_fight_adapter_fallback_narration(
                packet
            )

            lines = [
                fallback.get("text", ""),
            ]

            if os.environ.get("GHOST_LLM_DEBUG") == "1":
                lines.extend(
                    [
                        "",
                        "Provider called: False",
                        "Provider: ghost.llm_adapter.fight_fallback",
                        "Real provider failed safely.",
                        f"Error: {type(exc).__name__}",
                    ]
                )

            print()
            print(panel("LLM FAILED - SAFE FIGHT BEAT", lines))
            return

    if os.environ.get("GHOST_DEV_LLM_NARRATION") == "1":
        result = generate_king_fight_adapter_fallback_narration(
            packet
        )

        lines = [
            result.get("text", ""),
        ]

        if os.environ.get("GHOST_LLM_DEBUG") == "1":
            lines.extend(
                [
                    "",
                    f"Provider called: {result.get('provider_called')}",
                    f"Provider: {result.get('provider')}",
                ]
            )

        print()
        print(panel("ADAPTER FIGHT BEAT", lines))


def _king_fight_scene_reason_for_stage(stage: str) -> str | None:
    return {
        "king_phase_one": "phase_one_start",
        "elite_knight": "elite_knight_start",
        "king_phase_two": "phase_two_start",
    }.get(stage)


def _king_fight_scene_seen(game, reason: str) -> bool:
    seen = getattr(game, "_ghost_llm_scene_beats_seen", None)

    if seen is None:
        seen = set()
        setattr(game, "_ghost_llm_scene_beats_seen", seen)

    if reason in seen:
        return True

    seen.add(reason)
    return False


def _king_fight_kingdom_stats(game) -> dict:
    stats_func = getattr(game, "_final_kingdom_stats", None)

    if callable(stats_func):
        try:
            stats = stats_func()
        except Exception:
            stats = {}
    else:
        stats = {}

    return stats if isinstance(stats, dict) else {}


def _king_fight_player_profile(game) -> dict:
    stats = _king_fight_kingdom_stats(game)

    def number_from(value):
        if isinstance(value, bool):
            return None

        if isinstance(value, (int, float)):
            return value

        return None

    def first_number(*names):
        for name in names:
            value = number_from(stats.get(name))

            if value is not None:
                return value

            value = number_from(getattr(game, name, None))

            if value is not None:
                return value

        return None

    def first_value(*names):
        for name in names:
            if name in stats and stats.get(name) is not None:
                return stats.get(name)

            value = getattr(game, name, None)

            if value is not None:
                return value

        return None

    followers = first_number("followers")
    weapon_caches = first_number("weapon_caches")
    armor = first_number("armor")
    guards_defeated = first_number("guards_defeated")
    heat = first_number("heat")
    king_control = first_number("king_control")

    prepared_assault = first_value("prepared_assault")
    wounded_start = first_value("wounded_start")
    likely_success = first_value("likely_success")

    strength = first_number(
        "strength",
        "siege_strength",
        "rebel_strength",
    )

    if strength is None:
        for method_name in (
            "siege_strength",
            "_siege_strength",
            "calculate_siege_strength",
            "_calculate_siege_strength",
        ):
            method = getattr(game, method_name, None)

            if not callable(method):
                continue

            try:
                value = method()
            except TypeError:
                continue

            strength = number_from(value)

            if strength is not None:
                break

    if strength is None:
        strength = (
            int(followers or 0)
            + int(weapon_caches or 0) * 4
            + int(armor or 0) * 3
            + int(guards_defeated or 0) * 2
        )

        if king_control is not None and king_control > 5:
            strength -= int(king_control - 5)

    profile = {
        "strength": strength,
        "followers": followers,
        "weapon_caches": weapon_caches,
        "armor": armor,
        "guards_defeated": guards_defeated,
        "heat": heat,
        "king_control": king_control,
        "prepared_assault": prepared_assault,
        "wounded_start": wounded_start,
        "likely_success": likely_success,
    }

    estimated_arms = first_value("estimated_arms")

    if estimated_arms is not None:
        profile["estimated_arms"] = estimated_arms

    return {
        key: value
        for key, value in profile.items()
        if value is not None
    }


def _king_fight_scene_packet_from_status(
    game,
    status: dict,
    reason: str,
) -> dict:
    packet = dict(status)
    packet["outcome"] = reason
    packet["stage"] = status.get("stage")
    packet["upcoming_tell"] = status.get("tell")
    packet["tell"] = None
    packet["kingdom_stats"] = _king_fight_kingdom_stats(game)
    packet["player_profile"] = _king_fight_player_profile(game)

    return packet


def _king_fight_packet_is_final_scene(packet: dict) -> bool:
    outcome = packet.get("outcome")

    return outcome in (
        "player_death",
        "player_killed_by_king",
        "clean_king_victory",
        "last_breath_king_victory",
        "uncertain_king_fall",
        "castle_collapse",
    ) or bool(packet.get("ending"))


def _print_king_fight_transition_receipt(
    packet: dict,
) -> None:
    """Print exact Ghost-owned phase-transition damage in debug mode."""
    if not _king_fight_llm_opponent_debug_enabled():
        return

    transition = packet.get(
        "transition_trigger"
    )

    if not isinstance(transition, dict):
        return

    damage = int(
        transition.get("king_damage", 0)
        or 0
    )
    health = int(
        transition.get(
            "king_health_after_final_attack",
            0,
        )
        or 0
    )
    threshold = int(
        transition.get(
            "king_half_health",
            0,
        )
        or 0
    )
    move = str(
        transition.get("player_move")
    )

    print()
    print(
        panel(
            "GHOST PHASE RECEIPT",
            [
                f"Resolved move: {move}",
                f"Damage dealt to king: {damage}",
                f"King HP after strike: {health}",
                (
                    "Champion threshold: "
                    f"{threshold} HP"
                ),
                (
                    "Transition truth: the king remains "
                    "alive and calls the Champion at "
                    "half health."
                ),
            ],
        )
    )


def _print_king_fight_scene_beat(
    packet: dict,
    reason: str,
) -> None:
    import os

    from ghost.examples.ghost_revolution.llm_bridge import (
        GhostRevolutionLLMBridge,
        OpenAIResponsesClient,
        config_for_role,
        generate_king_fight_adapter_fallback_scene_beat,
    )

    if os.environ.get("GHOST_REAL_LLM") == "1":
        try:
            bridge = GhostRevolutionLLMBridge(
                client=OpenAIResponsesClient(),
                config=config_for_role("narration"),
            )

            result = bridge.generate_king_fight_scene_beat(
                packet,
                reason,
            )
            estimate = result.get("cost_estimate", {})
            _record_llm_measured_cost("narration", result)

            lines = [
                result.get("text", ""),
            ]

            if os.environ.get("GHOST_LLM_DEBUG") == "1":
                lines.extend(
                    [
                        "",
                        f"Reason: {reason}",
                        f"Provider called: {result.get('provider_called')}",
                        f"Model: {result.get('response_model') or estimate.get('model')}",
                        *_measured_cost_lines(result, "narration"),
                    ]
                )

            print()
            print(panel("REAL LLM SCENE BEAT", lines))
            return
        except Exception as exc:
            fallback = generate_king_fight_adapter_fallback_scene_beat(
                packet,
                reason,
            )

            lines = [
                fallback.get("text", ""),
            ]

            if os.environ.get("GHOST_LLM_DEBUG") == "1":
                lines.extend(
                    [
                        "",
                        f"Reason: {reason}",
                        "Provider called: False",
                        "Provider: ghost.llm_adapter.fight_scene_fallback",
                        "Real provider failed safely.",
                        f"Error: {type(exc).__name__}",
                    ]
                )

            print()
            print(panel("LLM FAILED - SAFE SCENE BEAT", lines))
            return

    if os.environ.get("GHOST_DEV_LLM_NARRATION") == "1":
        result = generate_king_fight_adapter_fallback_scene_beat(
            packet,
            reason,
        )

        lines = [
            result.get("text", ""),
        ]

        if os.environ.get("GHOST_LLM_DEBUG") == "1":
            lines.extend(
                [
                    "",
                    f"Reason: {reason}",
                    f"Provider called: {result.get('provider_called')}",
                    f"Provider: {result.get('provider')}",
                ]
            )

        print()
        print(panel("ADAPTER SCENE BEAT", lines))



def king_fight_move_menu_lines(status: dict) -> list[str]:
    parry_opening = status.get("parry_opening")

    if isinstance(parry_opening, dict):
        return [
            "Opening: Your parry broke the king's line.",
            "Your next attack is guaranteed to land.",
            "",
            "1. Heavy attack — 5 damage",
            "2. Light attack — 3 damage",
            "7. Show fight status",
            "0. There is no retreat",
        ]

    bait = status.get("bait_response")

    if isinstance(bait, dict):
        return [
            "Your bait drew a commitment.",
            "The opponent already locked a hidden recovery.",
            "quick_retaliation is answered by parry.",
            "guard_recovery is answered by light attack.",
            "A wrong answer deals no damage; the opponent recovers.",
            "",
            "1. Light attack",
            "2. Parry",
            "3. Let the opening pass",
            "7. Show fight status",
            "0. There is no retreat",
        ]

    forced = status.get("forced_response")

    if isinstance(forced, dict):
        allowed = tuple(forced.get("allowed_moves", ()))

        lines = [
            "You are off balance.",
            "The opponent already locked a hidden light-or-dodge read.",
            "A matched read denies the recovery with no damage.",
            "A missed light read deals 1; a missed dodge read escapes.",
            "Only these reactions are available:",
            "",
        ]

        if "light" in allowed:
            lines.append("2. Light attack")

        if "dodge" in allowed:
            lines.append("6. Dodge")

        lines.extend(
            [
                "7. Show fight status",
                "0. There is no retreat",
            ]
        )

        return lines

    return [
        "1. Heavy attack",
        "2. Light attack",
        "3. Feint / bait",
        "4. Parry",
        "5. Deflect",
        "6. Dodge",
        "7. Show fight status",
        "0. There is no retreat",
    ]


def _king_fight_mark_transition_scene_seen(
    game,
    packet: dict,
) -> None:
    if not isinstance(packet, dict):
        return

    outcome = packet.get("outcome")
    stage = packet.get("stage")

    reasons = []

    if outcome == "elite_knight_called" or stage == "elite_knight":
        reasons.append("elite_knight_start")

    if outcome == "elite_knight_defeated" or stage == "king_phase_two":
        reasons.append("phase_two_start")

    if not reasons:
        return

    seen = getattr(game, "_ghost_llm_scene_beats_seen", None)

    if seen is None:
        seen = set()
    elif not isinstance(seen, set):
        seen = set(seen)

    for reason in reasons:
        seen.add(reason)

    setattr(game, "_ghost_llm_scene_beats_seen", seen)



def _king_fight_llm_opponent_enabled() -> bool:
    import os

    return (
        os.environ.get(
            "GHOST_LLM_OPPONENT"
        )
        == "1"
    )


def _king_fight_llm_opponent_debug_enabled() -> bool:
    import os

    return (
        os.environ.get(
            "GHOST_LLM_OPPONENT_DEBUG"
        )
        == "1"
        or os.environ.get(
            "GHOST_LLM_DEBUG"
        )
        == "1"
    )





def _king_fight_control_source_label(
    value,
) -> str:
    return {
        "llm_commitment_ghost_resolution": (
            "LLM commitment / Ghost resolution"
        ),
        "llm_combat_action_ghost_matrix": (
            "LLM combat action / Ghost matrix"
        ),
        "ghost_forced_continuation": (
            "Ghost forced continuation"
        ),
        "ghost_parry_continuation": (
            "Ghost parry continuation"
        ),
        "ghost_resolution": "Ghost resolution",
    }.get(
        value,
        str(value),
    )


def _king_fight_locked_audit_once(
    game,
    observation: dict,
) -> None:
    """
    Reveal the resolved exchange before a Ghost-owned continuation.

    A forced response or parry opening does not request a new LLM
    commitment, but the commitment that created the continuation must
    still become visible after resolution.
    """
    if not _king_fight_llm_opponent_debug_enabled():
        return

    locked_reason = observation.get("locked_reason")

    if locked_reason not in {
        "forced_response_pending",
        "parry_opening_pending",
    }:
        return

    previous = observation.get(
        "previous_exchange_evidence"
    )

    if not isinstance(previous, dict):
        return

    reveal_key = (
        str(observation.get("selection_key")),
        str(locked_reason),
        str(previous.get("result")),
    )

    seen = getattr(
        game,
        "_ghost_llm_locked_audits_seen",
        None,
    )

    if not isinstance(seen, set):
        seen = set()

    if reveal_key in seen:
        return

    seen.add(reveal_key)
    setattr(
        game,
        "_ghost_llm_locked_audits_seen",
        seen,
    )

    predictive = previous.get(
        "reaction_plan_predictive"
    )

    if predictive is False:
        matched = "Not applicable"
        triggered = "Not applicable"
        missed = "Not applicable"
        exposed = "Not applicable"
    else:
        matched = str(
            previous.get("reaction_plan_matched")
        )
        triggered = str(
            previous.get("reaction_plan_triggered")
        )
        missed = str(
            previous.get("reaction_plan_missed")
        )
        exposed = str(
            previous.get(
                "reaction_miss_exposed_enemy"
            )
        )

    continuation_label = {
        "forced_response_pending": (
            "Ghost forced-response continuation"
        ),
        "parry_opening_pending": (
            "Ghost parry-opening continuation"
        ),
        "bait_response_pending": (
            "Ghost bait-response continuation"
        ),
    }.get(locked_reason, "Ghost continuation")

    lines = [
        (
            "Enemy: "
            + str(
                observation.get(
                    "enemy_display_name"
                )
            )
        ),
        (
            "Previous tactic: "
            + str(
                previous.get(
                    "enemy_intent_label"
                )
            )
        ),
        (
            "Previous hidden reaction: "
            + str(
                previous.get(
                    "opponent_reaction_plan_label"
                )
            )
        ),
        (
            "Previous combat action: "
            + str(
                previous.get(
                    "opponent_combat_action"
                )
            )
        ),
        (
            "Previous reaction predictive: "
            + str(predictive)
        ),
        (
            "Previous reaction matched: "
            + matched
        ),
        (
            "Previous reaction triggered: "
            + triggered
        ),
        (
            "Previous prediction missed: "
            + missed
        ),
        (
            "Previous miss exposed enemy: "
            + exposed
        ),
        (
            "Previous exposure bonus: "
            + str(
                previous.get(
                    "reaction_miss_bonus"
                )
            )
        ),
        (
            "Previous resolution source: "
            + str(
                previous.get(
                    "resolution_source"
                )
            )
        ),
        (
            "Previous control source: "
            + _king_fight_control_source_label(
                previous.get(
                    "opponent_control_source"
                )
            )
        ),
        (
            "Previous intent reason: "
            + str(
                previous.get(
                    "opponent_intent_reason"
                )
            )
        ),
        (
            "Previous reaction reason: "
            + str(
                previous.get(
                    "opponent_reaction_reason"
                )
            )
        ),
        "New tactic selection: deferred",
        (
            "Selection lock: "
            + str(locked_reason)
        ),
        (
            "Current control source: "
            + continuation_label
        ),
        "Provider called: False",
        (
            "Reason: the resolved LLM commitment "
            "opened a Ghost-authoritative continuation"
        ),
    ]

    print()
    print(
        panel(
            "AI OPPONENT AUDIT",
            lines,
        )
    )


def _select_king_fight_llm_opponent_intent(
    game,
) -> dict | None:
    import os

    observation = (
        game.king_fight_opponent_observation()
    )

    if not isinstance(
        observation,
        dict,
    ):
        return None

    existing_audit = observation.get(
        "existing_audit"
    )

    if isinstance(
        existing_audit,
        dict,
    ):
        return existing_audit

    if not observation.get(
        "selection_required"
    ):
        _king_fight_locked_audit_once(
            game,
            observation,
        )
        return None

    result = None

    try:
        if (
            os.environ.get(
                "GHOST_REAL_LLM"
            )
            != "1"
        ):
            audit = (
                game
                .apply_king_fight_opponent_intent(
                    None,
                    selection_key=(
                        observation[
                            "selection_key"
                        ]
                    ),
                    provider_called=False,
                    parser_reason=(
                        "provider_disabled"
                    ),
                    reaction_parser_reason=(
                        "provider_disabled"
                    ),
                )
            )
        else:
            from ghost.examples.ghost_revolution.llm_bridge import (
                OpenAIResponsesClient,
                config_for_role,
            )

            from ghost.examples.ghost_revolution.opponent_ai import (
                GhostFightOpponentBridge,
            )

            bridge = GhostFightOpponentBridge(
                client=OpenAIResponsesClient(),
                config=(
                    config_for_role("strategy")
                ),
            )

            result = (
                bridge
                .generate_king_fight_opponent_intent(
                    observation
                )
            )

            _record_llm_measured_cost("strategy", result)

            parser = result.get(
                "parser",
                {},
            )

            audit = (
                game
                .apply_king_fight_opponent_intent(
                    result.get(
                        "proposed_candidate"
                    ),
                    proposed_reaction_plan=(
                        result.get(
                            "proposed_reaction_candidate"
                        )
                    ),
                    proposed_forced_response_read=(
                        result.get(
                            "proposed_forced_response_read_candidate"
                        )
                    ),
                    proposed_combat_action=(
                        result.get(
                            "proposed_combat_action_candidate"
                        )
                    ),
                    proposed_feint_prediction=(
                        result.get(
                            "proposed_feint_prediction"
                        )
                    ),
                    selection_key=(
                        observation[
                            "selection_key"
                        ]
                    ),
                    provider_called=bool(
                        result.get(
                            "provider_called"
                        )
                    ),
                    parser_reason=(
                        parser.get(
                            "reason"
                        )
                    ),
                    reaction_parser_reason=(
                        parser.get(
                            "reaction_plan_reason"
                        )
                    ),
                    proposal_reason=(
                        result.get(
                            "proposal_reason"
                        )
                    ),
                    intent_explanation=(
                        result.get(
                            "intent_reason"
                        )
                    ),
                    reaction_explanation=(
                        result.get(
                            "reaction_reason"
                        )
                    ),
                )
            )
    except Exception as exc:
        error_detail = str(exc).strip()
        if len(error_detail) > 180:
            error_detail = error_detail[:177] + "..."
        error_reason = (
            "provider_error:"
            + type(exc).__name__
            + ((":" + error_detail) if error_detail else "")
        )

        audit = (
            game
            .apply_king_fight_opponent_intent(
                None,
                selection_key=(
                    observation[
                        "selection_key"
                    ]
                ),
                provider_called=False,
                parser_reason=(
                    error_reason
                ),
                reaction_parser_reason=(
                    error_reason
                ),
            )
        )

    if (
        _king_fight_llm_opponent_debug_enabled()
    ):
        previous = observation.get(
            "previous_exchange_evidence"
        )

        previous_intent = None
        previous_reaction = None
        previous_predictive = None
        previous_matched = None
        previous_triggered = None
        previous_missed = None
        previous_exposed = None
        previous_bonus = None
        previous_resolution = None
        previous_control_source = None
        previous_intent_reason = None
        previous_reaction_reason = None
        previous_forced_read = None
        previous_forced_read_matched = None
        previous_initiative = None

        if isinstance(previous, dict):
            previous_intent = previous.get(
                "enemy_intent_label"
            )

            previous_reaction = previous.get(
                "opponent_reaction_plan_label"
            )

            previous_predictive = previous.get(
                "reaction_plan_predictive"
            )

            previous_matched = previous.get(
                "reaction_plan_matched"
            )

            previous_triggered = previous.get(
                "reaction_plan_triggered"
            )

            previous_missed = previous.get(
                "reaction_plan_missed"
            )

            previous_exposed = previous.get(
                "reaction_miss_exposed_enemy"
            )

            previous_bonus = previous.get(
                "reaction_miss_bonus"
            )

            previous_resolution = previous.get(
                "resolution_source"
            )

            previous_control_source = previous.get(
                "opponent_control_source"
            )

            previous_intent_reason = previous.get(
                "opponent_intent_reason"
            )

            previous_reaction_reason = previous.get(
                "opponent_reaction_reason"
            )

            previous_forced_read = previous.get(
                "forced_response_read"
            )

            previous_forced_read_matched = previous.get(
                "forced_response_read_matched"
            )

            initiative_after = previous.get(
                "initiative_after"
            )

            if isinstance(initiative_after, dict):
                previous_initiative = initiative_after.get(
                    "state"
                )

        if previous_predictive is False:
            matched_display = "Not applicable"
            triggered_display = "Not applicable"
            missed_display = "Not applicable"
            exposed_display = "Not applicable"
        else:
            matched_display = str(
                previous_matched
            )

            triggered_display = str(
                previous_triggered
            )

            missed_display = str(
                previous_missed
            )

            exposed_display = str(
                previous_exposed
            )

        lines = [
            (
                "Enemy: "
                + str(
                    observation.get(
                        "enemy_display_name"
                    )
                )
            ),
            (
                "Previous tactic: "
                + str(previous_intent)
            ),
            (
                "Previous hidden reaction: "
                + str(previous_reaction)
            ),
            (
                "Previous combat action: "
                + str(
                    previous.get("opponent_combat_action")
                    if isinstance(previous, dict)
                    else None
                )
            ),
            (
                "Previous reaction predictive: "
                + str(previous_predictive)
            ),
            (
                "Previous reaction matched: "
                + matched_display
            ),
            (
                "Previous reaction triggered: "
                + triggered_display
            ),
            (
                "Previous prediction missed: "
                + missed_display
            ),
            (
                "Previous miss exposed enemy: "
                + exposed_display
            ),
            (
                "Previous exposure bonus: "
                + str(previous_bonus)
            ),
            (
                "Previous resolution source: "
                + str(previous_resolution)
            ),
            (
                "Previous control source: "
                + _king_fight_control_source_label(
                    previous_control_source
                )
            ),
            (
                "Previous intent reason: "
                + str(previous_intent_reason)
            ),
            (
                "Previous reaction reason: "
                + str(previous_reaction_reason)
            ),
            (
                "Previous forced read: "
                + str(previous_forced_read)
            ),
            (
                "Previous forced read matched: "
                + str(previous_forced_read_matched)
            ),
            (
                "Previous initiative: "
                + str(previous_initiative)
            ),
            (
                "Previous feint prediction: "
                + str(
                    previous.get("predicted_feint_subtype")
                    if isinstance(previous, dict)
                    else None
                )
            ),
            (
                "Previous selected feint defense: "
                + str(
                    previous.get("selected_feint_defense")
                    if isinstance(previous, dict)
                    else None
                )
            ),
            (
                "Previous feint utility: "
                + str(
                    previous.get("feint_defense_utility")
                    if isinstance(previous, dict)
                    else None
                )
            ),
            (
                "Previous bait result: "
                + str(
                    previous.get("bait_result")
                    if isinstance(previous, dict)
                    else None
                )
            ),
            (
                "Previous bait recovery: "
                + str(
                    previous.get("bait_hidden_recovery")
                    if isinstance(previous, dict)
                    else None
                )
            ),
            (
                "Previous bait response: "
                + str(
                    previous.get("bait_player_response")
                    if isinstance(previous, dict)
                    else None
                )
            ),
            "Proposed tactic: hidden until resolution",
            "Selected tactic: hidden until resolution",
            "Current reaction plan: locked by Ghost",
            "Current forced read: locked by Ghost",
            (
                "Intent accepted: "
                + str(
                    audit.get(
                        "accepted"
                    )
                )
            ),
            (
                "Reaction accepted: "
                + str(
                    audit.get(
                        "reaction_plan_accepted"
                    )
                )
            ),
            (
                "Intent fallback: "
                + str(
                    audit.get(
                        "fallback_used"
                    )
                )
            ),
            (
                "Reaction fallback: "
                + str(
                    audit.get(
                        "reaction_plan_fallback_used"
                    )
                )
            ),
            (
                "Forced read accepted: "
                + str(
                    audit.get(
                        "forced_response_read_accepted"
                    )
                )
            ),
            (
                "Forced read fallback: "
                + str(
                    audit.get(
                        "forced_response_read_fallback_used"
                    )
                )
            ),
            (
                "Forced read validation: "
                + str(
                    audit.get(
                        "forced_response_read_reason"
                    )
                )
            ),
            (
                "Intent validation: "
                + str(
                    audit.get(
                        "reason"
                    )
                )
            ),
            (
                "Reaction validation: "
                + str(
                    audit.get(
                        "reaction_plan_reason"
                    )
                )
            ),
            "Intent reason: hidden until resolution",
            "Reaction reason: hidden until resolution",
        ]

        if isinstance(result, dict):
            estimate = result.get(
                "cost_estimate",
                {},
            )

            lines.extend(
                [
                    (
                        "Provider called: "
                        + str(
                            result.get(
                                "provider_called"
                            )
                        )
                    ),
                    (
                        "Model: "
                        + str(
                            result.get("response_model")
                            or estimate.get("model")
                        )
                    ),
                    *_measured_cost_lines(
                        result,
                        "strategy",
                    ),
                ]
            )

        print()
        print(
            panel(
                "AI OPPONENT AUDIT",
                lines,
            )
        )

    return audit

def king_fight_menu(
    game: GhostRevolutionRun,
    events: deque[str],
) -> None:
    while not game.complete and game.king_fight is not None:
        status = game.king_fight_status()

        if status is None:
            return

        if _king_fight_llm_opponent_enabled():
            _select_king_fight_llm_opponent_intent(
                game
            )

            status = game.king_fight_status()

            if status is None:
                return

            public_tell = (
                game
                .king_fight_opponent_public_tell()
            )

            if isinstance(
                public_tell,
                dict,
            ):
                status["tell"] = (
                    public_tell.get(
                        "tell",
                        status.get("tell"),
                    )
                )

        stage = status["stage"]

        scene_reason = _king_fight_scene_reason_for_stage(stage)

        if (
            scene_reason is not None
            and _king_fight_llm_enabled()
            and not _king_fight_scene_seen(game, scene_reason)
        ):
            scene_packet = _king_fight_scene_packet_from_status(
                game,
                status,
                scene_reason,
            )
            _print_king_fight_scene_beat(
                scene_packet,
                scene_reason,
            )

        if stage == "crown_loop":
            crown_loop_menu(game, events)
            return

        if stage == "fate_choice":
            print()
            print(
                panel(
                    "KING DEFEATED",
                    [
                        "The king is beaten in the burning castle.",
                        "Only a clean fight gives you this choice.",
                        "",
                        "1. Execute the king",
                        "2. Jail the king",
                        "0. Hold your blade",
                    ],
                )
            )
            print()

            choice = input("> ").strip()

            if choice == "0":
                return
            if choice == "1":
                packet = game.choose_king_fate("execute_king")
            elif choice == "2":
                packet = game.choose_king_fate("jail_king")
            else:
                print("Unknown king-fate choice.")
                continue

            message = game.last_action_note or "The crown changes hands."
            print(message)
            add_event(events, message)
            print_endgame_packet(packet)
            return

        if stage not in (
            "king_phase_one",
            "elite_knight",
            "king_phase_two",
        ):
            print_endgame_packet(game.final_ending_packet())
            return

        lines = [
            f"Stage: {king_fight_stage_label(stage)}",
            f"Castle collapse: {status['castle_timer']} turns",
            (
                "Player HP: "
                f"{meter(status['player_health'], status['player_max_health'])} "
                f"{status['player_health']}/{status['player_max_health']}"
            ),
        ]

        initiative = status.get("initiative")

        if isinstance(initiative, dict):
            lines.append(
                "Initiative: "
                + str(
                    initiative.get("state", "neutral")
                ).replace("_", " ").title()
            )

        if _king_fight_llm_opponent_enabled():
            lines.extend(
                [
                    "",
                    "Opponent control: LLM strategy / Ghost state authority",
                ]
            )

        if stage == "elite_knight":
            lines.append(
                "Champion HP: "
                f"{meter(status['elite_knight_health'], status['elite_knight_max_health'])} "
                f"{status['elite_knight_health']}/"
                f"{status['elite_knight_max_health']}"
            )
            lines.append(
                f"King morale ticks: {status['king_morale_ticks']}"
            )
        else:
            lines.append(
                "King HP:    "
                f"{meter(status['king_health'], status['king_max_health'])} "
                f"{status['king_health']}/{status['king_max_health']}"
            )

        tell_label = (
            "Observed tell"
            if _king_fight_llm_opponent_enabled()
            else "Tell"
        )

        lines.extend(
            [
                "",
                f"{tell_label}: {status['tell']}",
                "",
                *king_fight_move_menu_lines(status),
            ]
        )

        print()
        print(panel("BURNING CASTLE", lines))
        print()

        choice = input("> ").strip()
        move = None

        if choice in ("q", "quit", "back"):
            print("Leaving the fight panel.")
            return
        if choice == "0":
            print("The castle is collapsing. There is no retreat.")
            continue
        if choice == "7":
            continue

        parry_opening = status.get(
            "parry_opening"
        )
        forced_response = status.get(
            "forced_response"
        )

        if isinstance(parry_opening, dict):
            if choice == "1":
                move = "heavy"
            elif choice == "2":
                move = "light"
            else:
                print(
                    "The parry opening only allows "
                    "a heavy or light attack."
                )
                continue
        elif isinstance(forced_response, dict):
            if choice == "2":
                move = "light"
            elif choice == "6":
                move = "dodge"
            else:
                print(
                    "While off balance, choose "
                    "light attack or dodge."
                )
                continue
        elif isinstance(status.get("bait_response"), dict):
            if choice == "1":
                move = "light"
            elif choice == "2":
                move = "parry"
            elif choice == "3":
                move = "pass"
            else:
                print(
                    "During a bait opening, choose "
                    "light, parry, or let it pass."
                )
                continue
        elif choice == "3":
            print("Feint choice: 1. Heavy  2. Light  3. Pure bait  4. Cancel")
            follow_up = input("> ").strip()

            if follow_up == "1":
                move = "feint_heavy"
            elif follow_up == "2":
                move = "feint_light"
            elif follow_up == "3":
                move = "feint_bait"
            elif follow_up in ("0", "4"):
                continue
            else:
                print("Unknown feint choice.")
                continue
        else:
            move = _king_fight_move_from_choice(choice)

        if move is None:
            print("Unknown king-fight move.")
            continue

        packet = game.resolve_king_fight_move(move)
        message = game.last_action_note or "The burning castle shifts."

        add_event(events, message)

        if _king_fight_llm_enabled():
            outcome = (
                packet.get("outcome")
                if isinstance(packet, dict)
                else None
            )

            _king_fight_mark_transition_scene_seen(
                game,
                packet,
            )

            if outcome == "elite_knight_called":
                _print_king_fight_transition_receipt(
                    packet
                )
                _print_king_fight_scene_beat(
                    packet,
                    "elite_knight_start",
                )
            elif outcome == "elite_knight_defeated":
                _print_king_fight_scene_beat(
                    packet,
                    "phase_two_start",
                )
            elif _king_fight_packet_is_final_scene(
                packet
            ):
                _print_king_fight_scene_beat(packet, "fight_end")
                _print_king_fight_mocking_lines(
                    packet
                )
            else:
                _print_king_fight_llm_narration(packet)
        else:
            print(message)
            print_endgame_packet(packet)


def _print_crown_kingdom_stats(game) -> None:
    if hasattr(game, "_final_kingdom_stats"):
        stats = game._final_kingdom_stats()
    else:
        stats = {}

    lines = [
        f"Followers:       {getattr(game, 'followers', '-')}",
        f"Food:            {getattr(game, 'food', '-')}",
        f"Gold:            {getattr(game, 'gold', '-')}",
        f"Weapon caches:   {getattr(game, 'weapons', '-')}",
        f"Armor:           {getattr(game, 'armor', '-')}",
        f"King Control:    {getattr(game, 'king_control', '-')}",
        f"Guards Defeated: {getattr(game, 'guards_defeated', '-')}",
    ]

    if isinstance(stats, dict):
        lines.append("")
        lines.append(
            "Status: "
            + str(stats.get("status", "Crown loop still active."))
        )

    print(panel("FINAL KINGDOM STATS", lines))


def _print_crown_packet(packet):
    def _local_print_box(title, lines):
        width = 44
        title_text = f" {title} "
        left = max(0, (width - len(title_text)) // 2)
        right = max(0, width - len(title_text) - left)

        print("╔" + ("═" * left) + title_text + ("═" * right) + "╗")

        for raw_line in lines:
            text = str(raw_line)

            if not text:
                print("║" + (" " * width) + "║")
                continue

            while text:
                chunk = text[:width]
                text = text[width:]
                print("║" + chunk.ljust(width) + "║")

        print("╚" + ("═" * width) + "╝")

    print_endgame_packet(packet)

    crown_profile = packet.get("crown_profile")

    if crown_profile:
        _print_crown_kingdom_stats(crown_profile)

    llm_context = packet.get("llm_context")

    if llm_context:
        lines = [
            "LLM bridge: ready",
            f"Mode: {llm_context.get('mode')}",
            f"Town: {llm_context.get('town')}",
            f"Location: {llm_context.get('location')}",
        ]

        npc = llm_context.get("npc")

        if npc:
            lines.extend(
                [
                    f"NPC: {npc.get('name')}",
                    f"Role: {npc.get('role')}",
                    f"Reaction: {npc.get('reaction')}",
                ]
            )

        _local_print_box(
            "LLM CONTEXT PLACEHOLDER",
            lines,
        )

    if (
        packet.get("llm_ready") is True
        and isinstance(llm_context, dict)
        and llm_context.get("mode") == "crown_loop_npc_dialogue"
        and packet.get("action") == "open_dialogue"
    ):
        from ghost.examples.ghost_revolution.llm_bridge import (
            generate_crown_adapter_fallback_dialogue,
        )

        result = generate_crown_adapter_fallback_dialogue(packet)
        text = result.get("text", "")

        _local_print_box(
            "ADAPTER FALLBACK DIALOGUE",
            [
                text,
                "",
                f"Provider called: {result.get('provider_called')}",
                f"Provider: {result.get('provider')}",
            ],
        )


def _crown_town_menu(game, events, town: str) -> None:
    while True:
        locations = game.crown_town_locations(town)

        lines = [
            f"{town}",
            "Choose where the new king appears.",
            "",
        ]

        for index, location in enumerate(locations, start=1):
            lines.append(f"{index}. {location['label']}")

        lines.append("0. Back to towns")

        print(panel("CROWN TOWN", lines))

        choice = input("> ").strip().lower()

        if choice in {"0", "q", "quit", "back"}:
            return

        if not choice.isdigit():
            print("Unknown crown-loop location.")
            continue

        number = int(choice)

        if number < 1 or number > len(locations):
            print("Unknown crown-loop location.")
            continue

        location = locations[number - 1]
        packet = game.crown_visit_location(
            town,
            location["id"],
        )

        _print_crown_packet(packet)
        add_event(
            events,
            packet.get("narrative", packet.get("ending", "")),
        )

        _crown_location_menu(
            game,
            events,
            packet,
        )


def _crown_location_menu(game, events, packet: dict) -> None:
    town = packet["town"]
    location = packet["location"]
    npcs = list(packet.get("npcs", ()))

    while True:
        lines = [
            packet.get("location_label", location),
            "NPC reactions are deterministic placeholders.",
            "Open dialogue only builds the future LLM packet.",
            "",
        ]

        option = 1
        option_map = {}

        for npc in npcs:
            lines.append(
                f"{option}. Greet {npc['name']}"
            )
            option_map[str(option)] = (
                npc["id"],
                "greet",
            )
            option += 1

            lines.append(
                f"{option}. Open dialogue with {npc['name']}"
            )
            option_map[str(option)] = (
                npc["id"],
                "open_dialogue",
            )
            option += 1

        lines.append("0. Back to town")

        print(panel("CROWN NPCS", lines))

        choice = input("> ").strip().lower()

        if choice in {"0", "q", "quit", "back"}:
            return

        selected = option_map.get(choice)

        if selected is None:
            print("Unknown crown-loop NPC option.")
            continue

        npc_id, action = selected

        result = game.crown_npc_interaction(
            town,
            location,
            npc_id,
            action,
        )

        _print_crown_packet(result)
        add_event(
            events,
            result.get("narrative", result.get("ending", "")),
        )

def crown_loop_menu(game, events) -> None:
    while (
        game.king_fight is not None
        and not game.complete
        and game.king_fight.get("stage") == "crown_loop"
    ):
        towns = game.crown_towns()

        lines = [
            "The rebellion is over. The crown is yours.",
            "The towns now react to how you took it.",
            "",
        ]

        for index, town in enumerate(towns, start=1):
            lines.append(f"{index}. Visit {town}")

        lines.extend(
            [
                "4. Retire the Crown",
                "5. Final kingdom stats",
                "0. Continue ruling",
            ]
        )

        print(panel("CROWN LOOP", lines))

        choice = input("> ").strip().lower()

        if choice in {"0", "q", "quit", "back"}:
            return

        if choice in {"1", "2", "3"}:
            town = towns[int(choice) - 1]

            _crown_town_menu(
                game,
                events,
                town,
            )
            continue

        if choice == "4":
            result = game.retire_crown()
            print_endgame_packet(result)
            add_event(
                events,
                result.get("ending", ""),
            )
            return

        if choice == "5":
            _print_crown_kingdom_stats(game)
            continue

        print("Unknown crown-loop choice.")


def siege_menu(
    game: GhostRevolutionRun,
    events: deque[str],
) -> None:
    if game.endgame_action_label() == "Retire the Crown":
        crown_loop_menu(game, events)
        return

    if not game.siege_armed:
        game.siege_armed = True
        warning = game.siege_warning()

        lines = [
            "Are you sure you want to do this?",
            "The siege decides whether you reach the king.",
            "",
            f"Siege strength: {warning['strength']}",
            f"Minimum needed: {warning['minimum_required']}",
            f"Strong assault: {warning['strong_threshold']}",
        ]

        if warning["reaches_king"]:
            lines.append("Your army can breach the castle.")
        else:
            lines.append("Your army is not ready for the walls.")

        if warning["wounded_start"]:
            lines.append("You may reach the king wounded.")
        elif warning["prepared_assault"]:
            lines.append("Your army can carry you in prepared.")

        if game.followers > 0:
            lines.extend(
                [
                    "",
                    "Are you willing to risk the lives",
                    "of the followers who trust you?",
                ]
            )

        lines.extend(
            [
                "",
                "Press 4 again immediately to begin.",
                "Choose any other action to cancel.",
            ]
        )

        print()
        print(panel("!!! SIEGE THE CASTLE !!!", lines))
        return

    siege_animation(game)
    result = game.siege_castle()

    title = (
        "KING FIGHT STARTED"
        if result.get("outcome") == "king_confrontation_started"
        else "SIEGE RESULT"
    )

    lines = [
        f"Outcome: {result.get('outcome', '-')}",
        f"Siege Score: {result.get('score', '-')}",
    ]

    if result.get("outcome") == "king_confrontation_started":
        lines.extend(
            [
                f"Player HP: {result['player_health']}/"
                f"{result['player_max_health']}",
                f"Castle Timer: {result['castle_timer']} turns",
                "Duel Damage: Heavy 4 / Light 2",
                "Parry Opening: Heavy 5 / Light 3",
                "",
                game.last_action_note,
                "",
                f"Tell: {result['tell']}",
            ]
        )
    else:
        lines.extend(["", result.get("ending", game.last_action_note)])

    print()
    print(panel(title, lines))

    add_event(events, "The rebellion launched the final siege.")

    if (
        result.get("outcome") == "king_confrontation_started"
        and not game.complete
    ):
        king_fight_menu(game, events)


def print_intro() -> None:
    print()
    print(
        panel(
            "GHOST REVOLUTION",
            [
                "You were once a knight of the crown.",
                "You broke your oath when you saw",
                "what the king had become.",
                "",
                "Gather whoever will listen.",
                "The kingdom will remember how you win.",
            ],
        )
    )
    print()


def print_day_report(
    game: GhostRevolutionRun,
    result: dict,
) -> None:
    report = result.get("day_report")

    if not report:
        return

    if report["starved"]:
        title = "REBELLION STARVES"
        lines = [
            f"Food needed: {report['food_used']}",
            f"Food before night: {report['food_before']}",
            f"You and {report['followers_fed']} rebels go hungry.",
            "The rebellion scatters from hunger.",
        ]
    else:
        title = "DAY ENDS"
        lines = [
            f"Food used: {report['food_used']}",
            f"You fed: {report.get('leader_fed', 1)}",
            f"Rebels fed: {report['followers_fed']}",
            f"Food remaining: {game.food}",
            (
                "Camp phase begins."
                if result.get("phase_change") == "camp"
                else f"Next: Rebellion Day {game.phase_day}."
            ),
        ]

    print()
    print(panel(title, lines))


def print_final_result(game: GhostRevolutionRun) -> None:
    print()
    print(
        panel(
            "FINAL RESULT",
            [
                f"Followers:       {game.followers}",
                f"Food:            {game.food}",
                f"Gold:            {game.gold}",
                f"Weapon caches:         {game.weapons}",
                f"Armor:           {game.armor}",
                f"King Control:    {game.king_control}",
                f"Guards Defeated: {game.guards_defeated}",
                "",
                (
                    f"Ending: {game.ending}"
                    if game.ending
                    else (
                        "Status: Campaign paused by player."
                        if game.quit_game
                        else "Status: Campaign remains unresolved."
                    )
                ),
            ],
        )
    )


def run_presentation() -> None:
    game = GhostRevolutionRun()
    events: deque[str] = deque(maxlen=RECENT_EVENT_LIMIT)

    add_event(
        events,
        "The rebellion begins at the hidden base.",
    )

    print_intro()

    while not game.complete:
        if game.phase == "camp":
            camp_menu(game, events)
            continue

        if (
            game.king_fight is not None
            and not game.complete
        ):
            king_fight_menu(game, events)
            continue

        print()
        print(render_status(game))
        print_recent_events(events)

        print()
        print(
            panel(
                "PLAYER ACTION MENU",
                [
                    action_summary(game),
                    (
                        f"Gold: {game.gold} | "
                        f"Followers: {game.followers} | "
                        f"Warriors: {game.available_warriors()}"
                    ),
                    "",
                    "1. Travel / Kingdom Map",
                    "@. Enter current location",
                    "3. Review Scout Reports",
                    "Tip: travel and town actions use daily actions.",
                    (
                        "4. !!! "
                        f"{game.endgame_action_label().upper()}"
                        " !!!"
                    ),
                    "5. End Rebellion Day",
                    "6. Player Legend",
                    "0. Quit",
                ],
            )
        )
        print()

        choice = input("> ").strip()

        if choice != "4":
            game.siege_armed = False

        if choice == "0":
            game.quit_game = True
            add_event(events, "You abandoned the rebellion.")
        elif choice == "1":
            kingdom_map_menu(game, events)
        elif choice == "@":
            enter_current_location(game, events)
        elif choice == "3":
            scout_intel_menu(game, events)
        elif choice == "4":
            siege_menu(game, events)
        elif choice == "5":
            result = game.end_day()

            print_day_report(game, result)

            for report in result.get(
                "day_report",
                {},
            ).get("scout_reports", []):
                add_event(events, report)

            if result.get("phase_change") == "camp":
                print()
                print(
                    panel(
                        "PHASE COMPLETE",
                        [
                            "Seven rebellion days have passed.",
                            "Your camp enters two days of downtime.",
                        ],
                    )
                )
                add_event(
                    events,
                    "The rebellion phase ends. Camp begins.",
                )
            elif game.alive:
                report = result.get("day_report", {})
                add_event(
                    events,
                    (
                        f"Day ended: used "
                        f"{report.get('food_used', 0)} food. "
                        f"You fed: {report.get('leader_fed', 1)} | "
                        f"Rebels fed: "
                        f"{report.get('followers_fed', 0)}."
                    ),
                )
        elif choice == "6":
            print_legend()
        else:
            print("Unknown player action.")

    print_final_result(game)
    print()
    print("Run complete.")
