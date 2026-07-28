from collections import deque
from pathlib import Path
from unittest.mock import patch

from ghost.examples.ghost_revolution.demo import GhostRevolutionRun
from ghost.examples.ghost_revolution.presentation import (
    crown_loop_menu,
    king_fight_menu,
    siege_menu,
)


def _strong_siege_game():
    game = GhostRevolutionRun(seed=7)
    game.followers = 40
    game.weapons = 8
    game.armor = 4
    game.guards_defeated = 4
    game.king_control = 5
    return game


def _reach_clean_fate_choice(game):
    for move in (
        "deflect",
        "feint_heavy",
        "heavy",
        "feint_heavy",
        "dodge",
        "deflect",
        "heavy",
        "feint_heavy",
        "deflect",
        "feint_heavy",
        "heavy",
    ):
        packet = game.resolve_king_fight_move(move)
    assert packet["outcome"] == "clean_king_victory"
    assert game.king_fight["stage"] == "fate_choice"


def test_siege_menu_starts_playable_king_fight_v180(capsys):
    game = _strong_siege_game()
    game.siege_armed = True
    events = deque(maxlen=6)

    with patch(
        "ghost.examples.ghost_revolution.presentation.siege_animation"
    ), patch(
        "ghost.examples.ghost_revolution.presentation.king_fight_menu"
    ) as fight_menu:
        siege_menu(game, events)

    output = capsys.readouterr().out

    assert "KING FIGHT STARTED" in output
    assert "Castle Timer:" in output
    assert game.king_fight is not None
    assert game.king_fight["stage"] == "king_phase_one"
    fight_menu.assert_called_once_with(game, events)
    assert events[0] == "The rebellion launched the final siege."


def test_siege_menu_warning_shows_strength_thresholds_v180(capsys):
    game = _strong_siege_game()
    events = deque(maxlen=6)

    siege_menu(game, events)

    output = capsys.readouterr().out

    assert "SIEGE THE CASTLE" in output
    assert "Siege strength:" in output
    assert "Minimum needed:" in output
    assert "Strong assault:" in output
    assert "Press 4 again immediately to begin." in output
    assert game.siege_armed is True


def test_king_fight_menu_resolves_turn_and_hides_clean_flag_v180(capsys):
    game = _strong_siege_game()
    game.siege_castle()
    game.king_fight["castle_timer"] = 1
    events = deque(maxlen=6)

    with patch("builtins.input", return_value="1"):
        king_fight_menu(game, events)

    output = capsys.readouterr().out

    assert "BURNING CASTLE" in output
    assert "There is no retreat" in output
    assert "ENDGAME PACKET" in output
    assert "castle_collapse_legend" in output
    assert game.complete is True
    assert game.ending
    assert "clean_king_victory_possible" not in output


def test_king_fight_menu_can_choose_jail_after_clean_victory_v180(capsys):
    game = _strong_siege_game()
    game.siege_castle()
    _reach_clean_fate_choice(game)
    events = deque(maxlen=6)

    with patch("builtins.input", return_value="2"):
        king_fight_menu(game, events)

    output = capsys.readouterr().out

    assert "KING DEFEATED" in output
    assert "Jail the king" in output
    assert game.phase == "crown"
    assert game.king_fight["stage"] == "crown_loop"
    assert game.endgame_action_label() == "Retire the Crown"
    assert game.complete is False


def test_crown_loop_menu_visits_town_then_retires_crown_v180(capsys):
    game = _strong_siege_game()
    game.siege_castle()
    _reach_clean_fate_choice(game)
    game.choose_king_fate("execute_king")
    events = deque(maxlen=6)

    with patch("builtins.input", side_effect=["1", "0", "4"]):
        crown_loop_menu(game, events)

    output = capsys.readouterr().out

    assert "CROWN LOOP" in output
    assert "Visit Ashfield" in output
    assert "Retire the Crown" in output
    assert "retired_crown" in output
    assert game.complete is True
    assert game.ending


def test_player_menu_uses_dynamic_endgame_action_label_v180():
    source = Path(
        "ghost/examples/ghost_revolution/presentation.py"
    ).read_text(encoding="utf-8")

    assert "game.endgame_action_label().upper()" in source
    assert "Retire the Crown" in source
    assert "clean_king_victory_possible" not in source


def test_mocking_lines_print_after_final_scene_v180(
    capsys,
):
    from ghost.examples.ghost_revolution import (
        presentation,
    )

    presentation._print_king_fight_mocking_lines(
        {
            "king_mocking_lines": [
                "First final line.",
                "Second final line.",
            ],
        }
    )

    output = capsys.readouterr().out

    assert "THE KING'S FINAL WORD" in output
    assert "First final line." in output
    assert "Second final line." in output


def test_final_scene_hook_prints_mocking_dialogue_v180():
    from pathlib import Path

    source = Path(
        "ghost/examples/ghost_revolution/"
        "presentation.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        '_print_king_fight_scene_beat(packet, "fight_end")'
        in source
    )

    assert (
        "_print_king_fight_mocking_lines("
        in source
    )
