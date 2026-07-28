from ghost.examples.ghost_revolution.demo import GhostRevolutionRun


def _prepared_king_fight():
    game = GhostRevolutionRun(seed=7)

    game.followers = 40
    game.weapons = 8
    game.armor = 4
    game.guards_defeated = 4
    game.king_control = 5

    packet = game.siege_castle()

    assert packet["outcome"] == "king_confrontation_started"
    assert packet["stage"] == "king_phase_one"

    return game


def _enter_elite_knight_stage():
    game = _prepared_king_fight()

    game.resolve_king_fight_move("deflect")
    game.resolve_king_fight_move("feint_heavy")
    packet = game.resolve_king_fight_move("heavy")

    assert packet["outcome"] == "elite_knight_called"
    assert packet["stage"] == "elite_knight"

    return game, packet


def test_king_dodge_does_not_damage_king_v180():
    game = _prepared_king_fight()

    packet = game.resolve_king_fight_move("dodge")
    exchange = packet["exchange"]

    assert packet["outcome"] == "king_exchange"
    assert exchange["move"] == "dodge"
    assert exchange["intent"] == "royal_lunge"
    assert exchange["result"] == "correct_read"
    assert exchange["player_damage"] == 0
    assert exchange["king_damage"] == 0
    assert packet["king_health"] == 20
    assert "does not wound" in exchange["message"]


def test_king_to_champion_transition_gets_narrative_v180():
    game, packet = _enter_elite_knight_stage()

    assert game.king_fight["stage"] == "elite_knight"
    assert "narrative" in packet
    assert "note" in packet
    assert "King's Champion steps between you and the throne" in (
        packet["narrative"]
    )
    assert packet["tell"].startswith(packet["narrative"])
    assert "The King's Champion sets his shield like a wall" in (
        packet["tell"]
    )
    assert game.last_action_note == packet["tell"]


def test_elite_knight_dodge_does_not_damage_champion_v180():
    game, _packet = _enter_elite_knight_stage()

    first = game.resolve_king_fight_move("feint_heavy")

    assert first["outcome"] == "elite_knight_exchange"
    assert first["elite_knight_health"] == 10

    packet = game.resolve_king_fight_move("dodge")
    exchange = packet["exchange"]

    assert packet["outcome"] == "elite_knight_exchange"
    assert exchange["move"] == "dodge"
    assert exchange["intent"] == "champion_lunge"
    assert exchange["result"] == "correct_read"
    assert exchange["player_damage"] == 0
    assert exchange["elite_knight_damage"] == 0
    assert packet["elite_knight_health"] == 10
    assert "does not cut through his armor" in exchange["message"]


def test_existing_clean_victory_route_still_reaches_fate_choice_v180():
    game = _prepared_king_fight()

    moves = (
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
    )

    packet = None

    for move in moves:
        packet = game.resolve_king_fight_move(move)

    assert packet["outcome"] == "clean_king_victory"
    assert packet["stage"] == "fate_choice"
    assert game.king_fight["stage"] == "fate_choice"
    assert game.king_fight["clean_king_victory_possible"] is True
    assert game.complete is False

