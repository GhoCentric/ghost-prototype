
from copy import deepcopy
import json

from ghost.examples.ghost_revolution.demo import (
    GhostRevolutionRun,
)


def _minimum_siege_game() -> GhostRevolutionRun:
    game = GhostRevolutionRun(seed=7)
    game.followers = 43
    game.weapons = 1
    game.king_control = 10
    return game


def _strong_siege_game() -> GhostRevolutionRun:
    game = GhostRevolutionRun(seed=7)
    game.followers = 60
    game.weapons = 1
    game.king_control = 10
    return game


def _start_strong_king_fight() -> GhostRevolutionRun:
    game = _strong_siege_game()
    packet = game.siege_castle()

    assert packet["outcome"] == "king_confrontation_started"
    assert packet["prepared_assault"] is True

    return game


def _reach_elite_knight(game: GhostRevolutionRun):
    first_phase = [
        "deflect",
        "feint_heavy",
        "heavy",
    ]

    packet = None

    for move in first_phase:
        packet = game.resolve_king_fight_move(move)

    assert packet["outcome"] == "elite_knight_called"
    assert game.king_fight["stage"] == "elite_knight"

    return packet


def _kill_elite_knight(game: GhostRevolutionRun):
    knight_phase = [
        "feint_heavy",
        "dodge",
        "deflect",
        "heavy",
        "feint_heavy",
    ]

    packet = None

    for move in knight_phase:
        packet = game.resolve_king_fight_move(move)

    assert packet["outcome"] == "elite_knight_defeated"
    assert game.king_fight["stage"] == "king_phase_two"

    return packet


def _finish_clean_king(game: GhostRevolutionRun):
    second_phase = [
        "deflect",
        "feint_heavy",
        "heavy",
    ]

    packet = None

    for move in second_phase:
        packet = game.resolve_king_fight_move(move)

    assert packet["outcome"] == "clean_king_victory"
    assert game.king_fight["stage"] == "fate_choice"

    return packet


def test_weak_army_fails_before_reaching_king_v180():
    game = GhostRevolutionRun(seed=7)

    packet = game.siege_castle()

    assert packet["outcome"] == "failed_siege_before_king"
    assert packet["ending_type"] == "failure"
    assert packet["king_status"] == "enthroned"
    assert packet["rebellion_status"] == "destroyed"
    assert game.alive is False
    assert game.captured is True
    assert game.complete is True
    assert game.king_fight is None

    json.dumps(packet, allow_nan=False, sort_keys=True)


def test_minimum_army_reaches_king_wounded_v180():
    game = _minimum_siege_game()
    warning = game.siege_warning()

    assert warning["strength"] == 35
    assert warning["reaches_king"] is True
    assert warning["wounded_start"] is True
    assert warning["prepared_assault"] is False

    packet = game.siege_castle()

    assert packet["outcome"] == "king_confrontation_started"
    assert packet["wounded_start"] is True
    assert packet["prepared_assault"] is False
    assert packet["player_health"] == 5
    assert packet["damage_bonus_percent"] == 0
    assert game.king_fight["armor_broken"] is True
    assert game.complete is False


def test_strong_army_reaches_king_empowered_v180():
    game = _strong_siege_game()
    warning = game.siege_warning()

    assert warning["strength"] >= warning["strong_threshold"]
    assert warning["wounded_start"] is False
    assert warning["prepared_assault"] is True

    packet = game.siege_castle()

    assert packet["outcome"] == "king_confrontation_started"
    assert packet["player_health"] == 10
    assert packet["player_max_health"] == 10
    assert packet["damage_bonus_percent"] == 0
    assert game.king_fight["armor_broken"] is False
    assert game.king_fight["stage"] == "king_phase_one"


def test_clean_king_victory_unlocks_execute_or_jail_choice_v180():
    game = _start_strong_king_fight()

    _reach_elite_knight(game)
    _kill_elite_knight(game)
    packet = _finish_clean_king(game)

    assert packet["choices"] == (
        "execute_king",
        "jail_king",
    )
    assert game.king_fight["clean_king_victory_possible"] is True
    assert game.ending == ""
    assert game.complete is False

    jail = game.choose_king_fate("jail_king")

    assert jail["outcome"] == "jail_king"
    assert jail["stage"] == "crown_loop"
    assert jail["endgame_action"] == "Retire the Crown"
    assert game.phase == "crown"
    assert game.complete is False

    visit = game.royal_visit("ashfield")

    assert visit["town"] == "ashfield"
    assert visit["view"] in {
        "beloved",
        "hopeful",
        "afraid",
        "uncertain",
    }

    ending = game.retire_crown()

    assert ending["outcome"] == "retired_crown"
    assert ending["ending_type"] == "retirement"
    assert ending["player_alive"] is True
    assert game.complete is True

    json.dumps(ending, allow_nan=False, sort_keys=True)


def test_king_hit_blocks_clean_victory_but_not_survival_v180():
    game = _start_strong_king_fight()

    first = game.resolve_king_fight_move("heavy")

    assert first["outcome"] == "king_exchange"
    assert game.king_fight["king_has_hit_player"] is True
    assert (
        game.king_fight["clean_king_victory_possible"]
        is False
    )

    packet = first

    for move in (
        "feint_heavy",
        "heavy",
        "deflect",
    ):
        packet = game.resolve_king_fight_move(move)

        if packet["outcome"] == "elite_knight_called":
            break

    assert packet["outcome"] == "elite_knight_called"
    assert packet["stage"] == "elite_knight"
    assert game.king_fight["stage"] == "elite_knight"
    assert game.king_fight["clean_king_victory_possible"] is False
    assert game.alive is True
    assert game.complete is False
    assert "narrative" in packet
def test_knight_damage_does_not_break_clean_king_condition_v180():
    game = _start_strong_king_fight()

    _reach_elite_knight(game)

    failed = game.resolve_king_fight_move("heavy")

    assert failed["outcome"] == "elite_knight_exchange"
    assert failed["exchange"]["result"] == "failed_knight_read"
    assert failed["exchange"]["king_heal"] == 1
    assert game.king_fight["king_morale_ticks"] == 1
    assert game.king_fight["player_health"] == 7
    assert (
        game.king_fight["clean_king_victory_possible"]
        is True
    )

    for move in (
        "dodge",
        "deflect",
        "heavy",
        "feint_heavy",
        "dodge",
        "deflect",
        "heavy",
    ):
        packet = game.resolve_king_fight_move(move)

    assert packet["outcome"] == "elite_knight_defeated"
    assert game.king_fight["king_health"] == 11

    for move in (
        "deflect",
        "feint_heavy",
        "heavy",
        "deflect",
    ):
        packet = game.resolve_king_fight_move(move)

    assert packet["outcome"] == "clean_king_victory"
    assert game.king_fight["stage"] == "fate_choice"


def test_death_to_elite_knight_is_failure_with_king_mocking_v180():
    game = _minimum_siege_game()

    game.siege_castle()
    _reach_elite_knight(game)

    first = game.resolve_king_fight_move("heavy")
    second = game.resolve_king_fight_move("heavy")

    assert first["outcome"] == "elite_knight_exchange"
    assert second["outcome"] == "player_killed_by_champion"
    assert second["ending_type"] == "failure"
    assert second["king_status"] == "mocking_victor"
    assert "king_mocking_lines" in second
    assert game.alive is False
    assert game.captured is False
    assert game.complete is True


def test_castle_timer_collapse_is_legend_not_failure_v180():
    game = _start_strong_king_fight()
    game.king_fight["castle_timer"] = 1

    packet = game.resolve_king_fight_move("dodge")

    assert packet["outcome"] == "castle_collapse_legend"
    assert packet["ending_type"] == "legend"
    assert packet["rebellion_status"] == "liberated"
    assert packet["player_alive"] is True
    assert game.alive is True
    assert game.complete is True
    assert "statue" in packet["ending"]


def test_king_endgame_is_snapshot_deterministic_v180():
    source = _strong_siege_game()
    source.siege_castle()
    checkpoint = source.snapshot()

    left = GhostRevolutionRun.from_snapshot(
        deepcopy(checkpoint)
    )
    right = GhostRevolutionRun.from_snapshot(
        deepcopy(checkpoint)
    )

    moves = [
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
    ]

    left_packets = [
        left.resolve_king_fight_move(move)
        for move in moves
    ]
    right_packets = [
        right.resolve_king_fight_move(move)
        for move in moves
    ]

    assert left_packets == right_packets
    assert left.snapshot() == right.snapshot()
    assert left.king_fight["stage"] == "fate_choice"
    assert right.king_fight["stage"] == "fate_choice"

    json.dumps(left.snapshot(), allow_nan=False, sort_keys=True)


def test_endgame_action_label_flips_after_clean_crown_choice_v180():
    game = _start_strong_king_fight()

    assert game.endgame_action_label() == "Siege the Castle"

    _reach_elite_knight(game)
    _kill_elite_knight(game)
    _finish_clean_king(game)

    game.choose_king_fate("execute_king")

    assert game.endgame_action_label() == "Retire the Crown"



def test_castle_timer_starts_at_twenty_v180():
    game = _start_strong_king_fight()

    assert game.king_fight["castle_timer"] == 20


def test_last_turn_clean_king_kill_becomes_last_breath_victory_v180():
    game = _start_strong_king_fight()

    _reach_elite_knight(game)
    _kill_elite_knight(game)

    game.king_fight["castle_timer"] = 1
    game.king_fight["king_health"] = 2
    game.king_fight["intent"] = "overextended_recovery"
    game.king_fight["clean_king_victory_possible"] = True

    packet = game.resolve_king_fight_move("light")

    assert packet["outcome"] == "last_breath_king_victory"
    assert packet["ending_type"] == "legend"
    assert packet["king_status"] == "slain_by_player"
    assert packet["rebellion_status"] == "liberated"
    assert packet["player_alive"] is True
    assert game.complete is True
    assert game.alive is True
    assert "Last-Breath Victory" in packet["ending"]


def test_last_turn_uncertain_king_kill_becomes_last_breath_victory_v180():
    game = _start_strong_king_fight()

    _reach_elite_knight(game)
    _kill_elite_knight(game)

    game.king_fight["castle_timer"] = 1
    game.king_fight["king_health"] = 2
    game.king_fight["intent"] = "overextended_recovery"
    game.king_fight["king_has_hit_player"] = True
    game.king_fight["clean_king_victory_possible"] = False

    packet = game.resolve_king_fight_move("light")

    assert packet["outcome"] == "last_breath_king_victory"
    assert packet["ending_type"] == "legend"
    assert packet["king_status"] == "slain_by_player"
    assert packet["rebellion_status"] == "liberated"
    assert game.complete is True


def test_phase_one_transition_preserves_trigger_exchange_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    fight = game.king_fight

    fight["king_health"] = (
        fight["king_half_health"] + 2
    )

    fight["intent"] = "crown_guard"

    packet = game.resolve_king_fight_move(
        "feint_heavy"
    )

    assert packet["outcome"] == (
        "elite_knight_called"
    )

    trigger = packet["transition_trigger"]

    assert trigger["source_stage"] == (
        "king_phase_one"
    )

    assert trigger["destination_stage"] == (
        "elite_knight"
    )

    assert trigger["player_move"] == (
        "feint_heavy"
    )

    assert trigger["king_intent"] == (
        "crown_guard"
    )

    assert trigger["result"] == "correct_read"
    assert trigger["king_damage"] > 0
    assert trigger["player_damage"] == 0
    assert trigger["damage_target"] == "king"
    assert trigger["last_attack_landed"] is True
    assert trigger["reaction_owner"] == "king"
    assert trigger["summoner"] == "king"

    assert trigger["summoned_actor"] == (
        "the King's Champion"
    )

    assert trigger["required_sequence"] == [
        "final_phase_one_exchange",
        "king_reacts_to_final_exchange",
        "king_summons_champion",
        "champion_enters",
    ]


def test_parry_opening_transition_preserves_trigger_exchange_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "prepared_king"
    )

    fight = game.king_fight

    fight["king_health"] = (
        fight["king_half_health"] + 2
    )

    fight["intent"] = "crown_guard"

    fight["parry_opening"] = {
        "source": "player_parry",
        "intent": "royal_lunge",
        "damage_bonus": 1,
        "guaranteed_next_attack": True,
        "allowed_moves": (
            "heavy",
            "light",
        ),
    }

    packet = game.resolve_king_fight_move(
        "heavy"
    )

    assert packet["outcome"] == (
        "elite_knight_called"
    )

    trigger = packet["transition_trigger"]

    assert trigger["player_move"] == "heavy"

    assert trigger["result"] == (
        "parry_opening_hit"
    )

    assert trigger["king_damage"] > 0
    assert trigger["last_attack_landed"] is True
    assert trigger["damage_target"] == "king"


def test_death_to_king_has_distinct_mocking_lines_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, _packet = create_fight_stage_shortcut(
        "king_phase_two"
    )

    game.king_fight["player_health"] = 1
    game.king_fight["intent"] = "crown_guard"

    packet = game.resolve_king_fight_move(
        "heavy"
    )

    assert packet["outcome"] == (
        "player_killed_by_king"
    )

    assert packet["ending_type"] == "failure"

    lines = packet[
        "king_mocking_lines"
    ]

    assert lines == [
        (
            "All that fire, and you still "
            "died at my feet."
        ),
        (
            "Let the towns remember what "
            "became of the knight who "
            "challenged his king."
        ),
    ]


def test_king_and_champion_deaths_use_distinct_mocking_lines_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    king_game, _packet = (
        create_fight_stage_shortcut(
            "king_phase_two"
        )
    )

    king_game.king_fight[
        "player_health"
    ] = 1

    king_game.king_fight[
        "intent"
    ] = "crown_guard"

    king_packet = (
        king_game.resolve_king_fight_move(
            "heavy"
        )
    )

    champion_game, _packet = (
        create_fight_stage_shortcut(
            "elite_knight"
        )
    )

    champion_game.king_fight[
        "player_health"
    ] = 1

    champion_game.king_fight[
        "intent"
    ] = "champion_lunge"

    champion_packet = (
        champion_game.resolve_king_fight_move(
            "heavy"
        )
    )

    assert (
        king_packet["king_mocking_lines"]
        != champion_packet[
            "king_mocking_lines"
        ]
    )
