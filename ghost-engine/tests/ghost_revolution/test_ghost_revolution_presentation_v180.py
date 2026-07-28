from ghost.examples.ghost_revolution.demo import (
    GhostRevolutionRun,
)
from collections import deque
from pathlib import Path
from unittest.mock import patch

from ghost.examples.ghost_revolution.presentation import (
    action_summary,
    bar_menu,
    enter_current_location,
    panel,
    print_final_result,
    public_event_menu,
    render_map,
    render_status,
    siege_narration,
)


def test_map_displays_current_location_and_town_conditions():
    game = GhostRevolutionRun()
    game.location = "millcross"
    game.knight_town = "millcross"

    output = render_map(game)

    assert "[ @ ] Millcross" in output
    assert "[G2]" in output
    assert "[K]" in output
    assert "[GUARDS 2]" not in output
    assert "[KNIGHT]" not in output



def test_status_panel_displays_rebellion_resources():
    game = GhostRevolutionRun()
    game.followers = 4
    game.food = 8
    game.gold = 31
    game.heat = 4

    output = render_status(game)

    assert "Followers 4" in output
    assert "Food 8" in output
    assert "Gold 31" in output
    assert "4/10" in output
    assert "PLAYER" not in output


def test_panel_wraps_long_story_text_without_cutting_words():
    output = panel(
        "STORY",
        [
            "The siege fails. You are publicly executed "
            "for conspiracy against the crown.",
        ],
    )

    assert "publicly executed" in output
    assert "against the crown." in output

    for line in output.splitlines():
        assert len(line) <= 46


def test_panel_keeps_multiline_map_inside_box():
    output = panel(
        "MAP",
        [
            "        [ C ] KING'S CASTLE\n"
            "             │\n"
            "        [ @ ] Ashfield",
        ],
    )

    for line in output.splitlines():
        assert line.startswith(("╔", "║", "╚"))
        assert line.endswith(("╗", "║", "╝"))


def test_siege_narration_changes_when_player_is_alone():
    game = GhostRevolutionRun()
    lines = siege_narration(game)

    assert "You stand beneath the castle walls alone." in lines
    assert "Your sword never reaches the gate." in lines


def test_siege_narration_changes_for_large_rebellion():
    game = GhostRevolutionRun()
    game.followers = 40
    game.weapons = 8
    game.armor = 4
    game.king_control = 2
    game.towns["ashfield"]["recruited"] = 6
    game.towns["millcross"]["recruited"] = 6

    for target in (
        "ashfield",
        "millcross",
        "ashfield",
        "millcross",
        "ashfield",
        "millcross",
    ):
        game.runtime.resolve_action(
            {
                "type": "help",
                "target": target,
            }
        )

    lines = siege_narration(game)

    assert "The roads fill with rebel banners." in lines
    assert "Weapons rise across the crowd like a forest of steel." in lines
    assert "Shields and armor give the front line a chance." in lines




def test_bar_menu_loops_after_real_action_until_return():
    game = GhostRevolutionRun()
    game.location = "ashfield"
    events = deque(maxlen=6)

    with patch(
        "builtins.input",
        side_effect=["1", "0"],
    ) as mocked_input:
        bar_menu(game, events)

    assert mocked_input.call_count == 2
    assert game.actions == 5
    assert game.heat == 0
    assert game.last_packet is not None
    assert game.last_packet["action"]["type"] == "help"
    assert game.last_packet["action"]["target"] == "ashfield"
    assert events[0] == "You gather rumors at the bar."


def test_public_event_menu_loops_after_real_action_until_return():
    game = GhostRevolutionRun()
    game.location = "ashfield"
    events = deque(maxlen=6)

    with patch(
        "builtins.input",
        side_effect=["1", "0"],
    ) as mocked_input:
        public_event_menu(game, events)

    assert mocked_input.call_count == 2
    assert game.actions == 5
    assert game.towns["ashfield"]["fear"] == 0
    assert game.last_packet is not None
    assert game.last_packet["action"]["type"] == "help"
    assert game.last_packet["action"]["target"] == "ashfield"

    assert (
        "You speak publicly and draw royal attention."
        in events
    )

    assert events[0] == (
        "The gathering in Ashfield disperses for today."
    )

def test_action_summary_shows_used_left_and_total():
    game = GhostRevolutionRun()

    assert (
        action_summary(game)
        == "Actions: 0 used / 6 left / 6 total"
    )

    assert game.travel("ashfield")

    assert (
        action_summary(game)
        == "Actions: 1 used / 5 left / 6 total"
    )


def test_enter_current_location_uses_hidden_base_menu():
    game = GhostRevolutionRun()
    events = deque(maxlen=6)

    with patch(
        "ghost.examples.ghost_revolution.presentation.hidden_base_menu"
    ) as mocked_menu:
        enter_current_location(game, events)

    mocked_menu.assert_called_once_with(game, events)


def test_final_result_distinguishes_player_quit(capsys):
    game = GhostRevolutionRun()
    game.quit_game = True

    print_final_result(game)

    output = capsys.readouterr().out

    assert "Campaign paused by player." in output


def test_blacksmith_purchase_preserves_named_leader_weapon():
    game = GhostRevolutionRun()
    game.location = "ashfield"
    game.gold = 100

    leader_before = game.leader_weapon_label()

    assert game.blacksmith_buy("sword") is True

    assert game.leader_weapon_label() == leader_before
    assert game.weapon_stock["sword"] == 2


def test_player_menu_no_longer_lists_redundant_enter_option():
    source = Path(
        "ghost/examples/ghost_revolution/presentation.py"
    ).read_text()

    assert '"2. Enter Hidden Rebel Base"' not in source
    assert '"2. Enter Current Town"' not in source
    assert '"@. Enter current location"' in source

def test_guard_combat_presentation_uses_health_and_tactical_options():
    source = Path(
        "ghost/examples/ghost_revolution/presentation.py"
    ).read_text()

    assert "Player HP:" in source
    assert "Guard HP:" in source
    assert "Feint into attack" in source
    assert "Parry" in source
    assert "Deflect" in source
    assert "Dodge" in source
    assert "Feint follow-up" in source
    assert "Hold guard" not in source
    assert "Round:" not in source
