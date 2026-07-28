"""Regression tests for Ghost Revolution map and guard-menu UX."""

from __future__ import annotations

from collections import deque
from unittest.mock import patch

from ghost.examples.ghost_revolution.demo import (
    GhostRevolutionRun,
)
from ghost.examples.ghost_revolution.presentation import (
    guard_encounter_menu,
    kingdom_map_menu,
    middle_of_town_menu,
    render_map,
)


def test_render_map_uses_location_symbols_not_input_numbers():
    game = GhostRevolutionRun()

    output = render_map(game)

    assert "[ A ] Ashfield" in output
    assert "[ M ] Millcross" in output
    assert "[ R ] Crownmarket" in output
    assert "[ C ] KING'S CASTLE" in output

    assert "[ 1 ]" not in output
    assert "[ 2 ]" not in output
    assert "[ 3 ]" not in output


def test_kingdom_map_choice_one_still_travels_to_ashfield(
    capsys,
):
    game = GhostRevolutionRun()
    events = deque(maxlen=6)

    with patch(
        "ghost.examples.ghost_revolution.presentation"
        ".travel_animation"
    ), patch(
        "ghost.examples.ghost_revolution.presentation"
        ".town_arrival_menu"
    ) as town_menu, patch(
        "builtins.input",
        return_value="1",
    ):
        kingdom_map_menu(game, events)

    output = capsys.readouterr().out

    assert "[ A ] Ashfield" in output
    assert "1. Ashfield (1 action)" in output
    assert game.location == "ashfield"

    town_menu.assert_called_once_with(game, events)


def test_guardless_middle_menu_is_visible_and_not_silent(
    capsys,
):
    game = GhostRevolutionRun()
    game.location = "ashfield"
    events = deque(maxlen=6)

    with patch(
        "ghost.examples.ghost_revolution.presentation"
        ".guard_encounter_menu"
    ) as guard_menu, patch(
        "builtins.input",
        side_effect=["3", "0"],
    ):
        middle_of_town_menu(game, events)

    output = capsys.readouterr().out

    message = (
        "There are no royal guards stationed in Ashfield."
    )

    assert "3. No royal guards stationed here" in output
    assert message in output
    assert events[0] == message
    assert game.actions == 6

    guard_menu.assert_not_called()


def test_guard_encounter_direct_call_is_not_silent(capsys):
    game = GhostRevolutionRun()
    game.location = "ashfield"
    events = deque(maxlen=6)

    guard_encounter_menu(game, events)

    output = capsys.readouterr().out

    message = (
        "There are no royal guards stationed in Ashfield."
    )

    assert message in output
    assert events[0] == message


def test_guard_option_remains_available_in_guarded_town(capsys):
    game = GhostRevolutionRun()
    game.location = "millcross"
    events = deque(maxlen=6)

    with patch(
        "builtins.input",
        return_value="0",
    ):
        middle_of_town_menu(game, events)

    output = capsys.readouterr().out

    assert "3. Guard encounter" in output
    assert "No royal guards stationed here" not in output
