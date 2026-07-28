"""
Deterministic Ghost Revolution automated playthroughs.

These routines use GhostRevolutionRun's normal game facade methods:
travel, recruit, work, role assignment, and end_day.

They do not simulate terminal input and do not reach into Ghost internals.
"""

from __future__ import annotations

from ghost.examples.ghost_revolution.demo import (
    GhostRevolutionRun,
)


def _finish_day(
    game: GhostRevolutionRun,
    day_number: int,
    actions: dict,
) -> dict:
    result = game.end_day()

    return {
        "day": day_number,
        "actions": actions,
        "food_before": result["day_report"]["food_before"],
        "food_after": game.food,
        "starved": result["day_report"]["starved"],
        "scout_reports": result["day_report"]["scout_reports"],
        "end_day": result,
    }


def run_seven_day_survival_and_scout_playthrough(
    seed: int = 7,
) -> dict:
    """
    Play one complete rebellion phase through the public game facade.

    Route:
    - recruit at Ashfield,
    - work enough days to maintain food,
    - assign two scouts for one safe report cycle,
    - stand scouts down before Crownmarket risk,
    - survive Day 7 and enter camp.
    """
    game = GhostRevolutionRun(seed=seed)

    day_one_actions = {
        "travel_to_ashfield": game.travel("ashfield"),
        "quiet_recruit_one": (
            game.recruit_quietly() is not None
        ),
        "ashfield_farm_work": (
            game.earn_honest_gold() is not None
        ),
        "quiet_recruit_two": (
            game.recruit_quietly() is not None
        ),
        "return_to_base": game.travel("base"),
        "assign_two_scouts": (
            game.set_combat_role("scouts", 2)
        ),
    }

    day_one = _finish_day(
        game,
        1,
        day_one_actions,
    )

    day_two_actions = {
        "travel_to_ashfield": game.travel("ashfield"),
        "ashfield_farm_work": (
            game.earn_honest_gold() is not None
        ),
        "quiet_recruitment_push": (
            game.recruit_quietly() is not None
        ),
        "return_to_base": game.travel("base"),
        "stand_down_scouts": (
            game.set_combat_role("scouts", 0)
        ),
    }

    day_two = _finish_day(
        game,
        2,
        day_two_actions,
    )

    day_three = _finish_day(
        game,
        3,
        {},
    )

    day_four_actions = {
        "travel_to_ashfield": game.travel("ashfield"),
        "ashfield_farm_work": (
            game.earn_honest_gold() is not None
        ),
        "return_to_base": game.travel("base"),
    }

    day_four = _finish_day(
        game,
        4,
        day_four_actions,
    )

    day_five = _finish_day(
        game,
        5,
        {},
    )

    day_six_actions = {
        "travel_to_ashfield": game.travel("ashfield"),
        "ashfield_farm_work": (
            game.earn_honest_gold() is not None
        ),
        "return_to_base": game.travel("base"),
    }

    day_six = _finish_day(
        game,
        6,
        day_six_actions,
    )

    day_seven = _finish_day(
        game,
        7,
        {},
    )

    information = game.information_summary()

    return {
        "route": "seven_day_survival_and_scout",
        "seed": seed,
        "days": [
            day_one,
            day_two,
            day_three,
            day_four,
            day_five,
            day_six,
            day_seven,
        ],
        "information": information,
        "final": {
            "alive": game.alive,
            "captured": game.captured,
            "ending": game.ending,
            "phase": game.phase,
            "phase_number": game.phase_number,
            "phase_day": game.phase_day,
            "location": game.location,
            "followers": game.followers,
            "food": game.food,
            "gold": game.gold,
            "scout_intel": dict(game.scout_intel),
            "roles": game.role_summary(),
        },
    }


def print_playthrough(result: dict) -> None:
    """Print one readable deterministic playthrough report."""
    print("=== GHOST REVOLUTION SCRIPTED PLAYTHROUGH ===")
    print()
    print("Route:", result["route"])
    print("Seed:", result["seed"])
    print()

    for day in result["days"]:
        action_names = ", ".join(
            day["actions"]
        ) or "end day only"

        print(
            f"DAY {day['day']}: "
            f"food {day['food_before']} -> "
            f"{day['food_after']}"
        )
        print("  Actions:", action_names)
        print("  Starved:", day["starved"])

        for report in day["scout_reports"]:
            print("  Scout:", report)

    print()
    print("=== REPORT-BASED PLAYER BELIEFS ===")

    beliefs = result["information"][
        "latest_scout_beliefs"
    ]

    for town_id in (
        "ashfield",
        "millcross",
        "crownmarket",
    ):
        belief = beliefs.get(town_id)

        if belief is not None:
            label = belief["dominant_candidate"].replace(
                "_",
                " ",
            )

            print(
                f"{town_id.title()}: "
                f"{label} "
                f"({belief['confidence']:.0%})"
            )

    final = result["final"]

    print()
    print("=== OUTCOME ===")
    print("Alive:", final["alive"])
    print("Phase:", final["phase"])
    print("Followers:", final["followers"])
    print("Food:", final["food"])
    print("Scout intel:", final["scout_intel"])
    print(
        "Outcome: survived rebellion phase -> camp"
    )


def main() -> None:
    """Run the seven-day scripted playthrough."""
    print_playthrough(
        run_seven_day_survival_and_scout_playthrough()
    )


if __name__ == "__main__":
    main()

