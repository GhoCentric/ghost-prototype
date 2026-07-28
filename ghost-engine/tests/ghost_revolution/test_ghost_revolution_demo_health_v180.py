import inspect
import json
from pathlib import Path
import subprocess
import sys

from ghost.examples.ghost_revolution.demo import (
    GhostRevolutionRun,
    REBELLION_DAYS,
)


ROOT = Path(__file__).resolve().parents[2]


def compact_state(game):
    return {
        "phase": game.phase,
        "phase_number": game.phase_number,
        "phase_day": game.phase_day,
        "actions": game.actions,
        "location": game.location,
        "followers": game.followers,
        "gold": game.gold,
        "food": game.food,
        "weapons": game.weapons,
        "armor": game.armor,
        "seeds": game.seeds,
        "heat": game.heat,
        "king_control": game.king_control,
        "knight_town": game.knight_town,
        "scout_intel": game.scout_intel,
        "towns": game.towns,
        "assignments": game.assignments,
        "world": game.current_world(),
        "snapshot": game.runtime.api.snapshot(),
    }


def scripted_path(game):
    results = []

    results.append(game.travel("ashfield"))
    results.append(game.recruit_quietly())
    results.append(game.raid_supplies())
    results.append(game.end_day())

    return {
        "results": results,
        "state": compact_state(game),
    }


def test_import_is_noninteractive_and_clean():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import ghost.examples.ghost_revolution.demo; "
                "print('IMPORT_OK')"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "IMPORT_OK"
    assert result.stderr.strip() == ""


def test_runtime_class_has_no_direct_terminal_input():
    source = inspect.getsource(GhostRevolutionRun)

    assert "input(" not in source
    assert "os.system(" not in source
    assert "time.sleep(" not in source


def test_scripted_replay_is_deterministic_and_json_safe():
    left = GhostRevolutionRun(seed=7)
    right = GhostRevolutionRun(seed=7)

    left_result = scripted_path(left)
    right_result = scripted_path(right)

    assert left_result == right_result

    json.dumps(left_result, sort_keys=True)


def test_failed_travel_does_not_mutate_state():
    game = GhostRevolutionRun(seed=7)

    before = compact_state(game)

    assert game.travel("base") is False

    assert compact_state(game) == before


def test_camp_assignments_reject_more_workers_than_followers():
    game = GhostRevolutionRun(seed=7)
    game.followers = 2

    for _ in range(REBELLION_DAYS):
        game.end_day()

    before = compact_state(game)

    assert game.set_assignment("farmers", 3) is False

    assert compact_state(game) == before


def test_locked_town_blocks_personal_travel_without_mutation():
    game = GhostRevolutionRun(seed=7)
    game.towns["millcross"]["locked"] = True

    before = compact_state(game)

    assert game.travel("millcross") is False

    assert compact_state(game) == before


def test_starvation_path_ends_cleanly():
    game = GhostRevolutionRun(seed=7)

    for _ in range(20):
        if not game.alive:
            break

        game.end_day()

    assert game.alive is False
    assert game.ending == "Your rebellion starves and scatters."
    assert game.food == 0

    json.dumps(compact_state(game), sort_keys=True)
