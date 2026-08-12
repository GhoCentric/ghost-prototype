from copy import deepcopy

from ghost.examples.ghost_revolution.demo import GhostRevolutionRun


def test_demo_final_ending_packet_covers_terminal_and_live_paths_v180():
    terminal = GhostRevolutionRun()
    terminal.ending = "The crown falls."
    terminal.last_packet = {
        "outcome": "clean_king_victory",
        "ending": terminal.ending,
        "complete": True,
    }

    packet = terminal.final_ending_packet()

    assert packet == terminal.last_packet
    assert packet is not terminal.last_packet

    live = GhostRevolutionRun()
    live.king_fight = {
        "stage": "elite_knight",
        "player_health": 10,
    }

    packet = live.final_ending_packet()

    assert packet["outcome"] == "elite_knight"
    assert packet["ending"] == ""
    assert packet["complete"] is False
    assert packet["king_fight"] == live.king_fight
    assert packet["king_fight"] is not live.king_fight


def test_demo_king_fight_initiative_repairs_missing_and_invalid_state_v180():
    no_fight = GhostRevolutionRun()

    packet = no_fight._ensure_king_fight_initiative()

    assert packet["kind"] == "combat_initiative"
    assert packet["state"] == "neutral"
    assert no_fight.king_fight is None

    invalid = GhostRevolutionRun()
    invalid.king_fight = {
        "initiative": {
            "kind": "wrong_kind",
            "state": "impossible",
        }
    }

    repaired = invalid._ensure_king_fight_initiative()

    assert repaired["kind"] == "combat_initiative"
    assert repaired["state"] == "neutral"
    assert invalid.king_fight["initiative"] == repaired
    assert invalid.king_fight["initiative"] is not repaired


def test_demo_advance_initiative_without_active_fight_is_nonpersistent_v180():
    game = GhostRevolutionRun()

    packet = game._advance_king_fight_initiative(
        "player_attack_hit"
    )

    assert packet["kind"] == "combat_initiative"
    assert packet["state"] == "player_advantage"
    assert game.king_fight is None


def test_demo_initiative_event_covers_deflect_dodge_miss_and_preserve_v180():
    game = GhostRevolutionRun()

    assert game._king_fight_initiative_event(
        move="deflect",
        damage_to_enemy=0,
        damage_to_player=0,
        opponent_reaction=None,
        reaction_missed=None,
    ) == "player_deflect"

    assert game._king_fight_initiative_event(
        move="dodge",
        damage_to_enemy=0,
        damage_to_player=0,
        opponent_reaction=None,
        reaction_missed=True,
    ) == "prediction_missed_player_escape"

    assert game._king_fight_initiative_event(
        move="bait",
        damage_to_enemy=0,
        damage_to_player=0,
        opponent_reaction=None,
        reaction_missed=False,
    ) == "preserve"
