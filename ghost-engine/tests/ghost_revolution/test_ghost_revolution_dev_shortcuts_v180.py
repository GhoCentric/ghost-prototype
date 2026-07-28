from ghost.examples.ghost_revolution.dev_shortcuts import (
    apply_developer_preset,
    create_developer_preset_run,
    developer_shortcut_presets,
    normalize_developer_preset,
    start_developer_siege,
)
from ghost.examples.ghost_revolution.demo import GhostRevolutionRun


def test_developer_shortcut_presets_are_registered_v180():
    presets = developer_shortcut_presets()

    assert "weak_siege" in presets
    assert "minimum_siege" in presets
    assert "prepared_siege" in presets
    assert "brutal_takeover" in presets
    assert "honorable_takeover" in presets
    assert "instant_king_fight" in presets
    assert "instant_wounded_king_fight" in presets

    assert normalize_developer_preset("weak") == "weak_siege"
    assert normalize_developer_preset("prepared") == "prepared_siege"
    assert normalize_developer_preset("instant") == "instant_king_fight"


def test_weak_shortcut_fails_before_king_v180():
    game, packet = create_developer_preset_run("weak_siege")

    assert packet["summary"]["likely_success"] is False
    assert packet["summary"]["king_fight_active"] is False

    result = start_developer_siege(game)["result"]

    assert result["outcome"] == "failed_siege_before_king"
    assert result["ending_type"] == "failure"
    assert result["player_alive"] is False
    assert game.king_fight is None
    assert game.complete is True


def test_minimum_shortcut_reaches_king_wounded_v180():
    game, packet = create_developer_preset_run("minimum_siege")

    assert packet["summary"]["likely_success"] is True
    assert packet["summary"]["prepared_assault"] is False
    assert packet["summary"]["wounded_start"] is True

    result = start_developer_siege(game)["result"]

    assert result["outcome"] == "king_confrontation_started"
    assert result["stage"] == "king_phase_one"
    assert result["wounded_start"] is True
    assert result["player_health"] == 5
    assert game.king_fight["armor_broken"] is True


def test_prepared_shortcut_reaches_empowered_king_fight_v180():
    game, packet = create_developer_preset_run("prepared_siege")

    assert packet["summary"]["likely_success"] is True
    assert packet["summary"]["prepared_assault"] is True
    assert packet["summary"]["wounded_start"] is False

    result = start_developer_siege(game)["result"]

    assert result["outcome"] == "king_confrontation_started"
    assert result["stage"] == "king_phase_one"
    assert result["prepared_assault"] is True
    assert result["player_health"] == 10
    assert result["damage_bonus_percent"] == 0
    assert game.king_fight["armor_broken"] is False


def test_brutal_and_honorable_shortcuts_are_distinct_v180():
    brutal_game, brutal_packet = create_developer_preset_run(
        "brutal_takeover"
    )
    honorable_game, honorable_packet = create_developer_preset_run(
        "honorable_takeover"
    )

    assert brutal_packet["summary"]["likely_success"] is True
    assert honorable_packet["summary"]["likely_success"] is True

    assert brutal_game.heat > honorable_game.heat
    assert brutal_game.guards_defeated > honorable_game.guards_defeated
    assert brutal_game.followers > honorable_game.followers
    assert brutal_packet["summary"]["strength"] > (
        honorable_packet["summary"]["strength"]
    )


def test_instant_king_fight_shortcut_starts_fight_v180():
    game, packet = create_developer_preset_run("instant_king_fight")

    started = packet["started"]

    assert started["outcome"] == "king_confrontation_started"
    assert started["stage"] == "king_phase_one"
    assert packet["summary"]["king_fight_active"] is True
    assert game.king_fight is not None
    assert game.king_fight["stage"] == "king_phase_one"
    assert game.king_fight["player_health"] == 10


def test_instant_wounded_king_fight_shortcut_starts_wounded_v180():
    game, packet = create_developer_preset_run(
        "instant_wounded_king_fight"
    )

    started = packet["started"]

    assert started["outcome"] == "king_confrontation_started"
    assert started["stage"] == "king_phase_one"
    assert started["wounded_start"] is True
    assert packet["summary"]["king_fight_active"] is True
    assert game.king_fight is not None
    assert game.king_fight["player_health"] == 5
    assert game.king_fight["armor_broken"] is True


def test_apply_developer_preset_resets_terminal_state_v180():
    game = GhostRevolutionRun(seed=7)

    game.alive = False
    game.captured = True
    game.ending = "old ending"

    packet = apply_developer_preset(game, "prepared_siege")

    assert packet["preset"] == "prepared_siege"
    assert game.alive is True
    assert game.captured is False
    assert game.complete is False
    assert game.ending == ""
    assert game.king_fight is None


def test_open_king_fight_menu_passes_deque_event_log_v180(
    monkeypatch,
):
    from ghost.examples.ghost_revolution import dev_shortcuts
    from ghost.examples.ghost_revolution import presentation

    game, _packet = create_developer_preset_run(
        "instant_king_fight"
    )

    seen = {}

    def fake_king_fight_menu(active_game, events):
        events.appendleft("event works")
        seen["same_game"] = active_game is game
        seen["event_log"] = list(events)

    monkeypatch.setattr(
        presentation,
        "king_fight_menu",
        fake_king_fight_menu,
    )

    dev_shortcuts._open_king_fight_menu(game)

    assert seen["same_game"] is True
    assert seen["event_log"] == ["event works"]


def test_fight_stage_shortcuts_reach_distinct_destinations_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    wounded, wounded_packet = create_fight_stage_shortcut(
        "wounded_king"
    )
    prepared, prepared_packet = create_fight_stage_shortcut(
        "prepared_king"
    )
    champion, champion_packet = create_fight_stage_shortcut(
        "elite_knight"
    )
    phase_two, phase_two_packet = create_fight_stage_shortcut(
        "king_phase_two"
    )

    assert wounded_packet["stage"] == "king_phase_one"
    assert wounded.king_fight["player_health"] == 5

    assert prepared_packet["stage"] == "king_phase_one"
    assert prepared.king_fight["player_health"] == 10

    assert champion_packet["stage"] == "elite_knight"
    assert champion.king_fight["stage"] == "elite_knight"

    assert phase_two_packet["stage"] == "king_phase_two"
    assert phase_two.king_fight["stage"] == "king_phase_two"


def test_direct_uncertain_victory_shortcut_finishes_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_endgame_shortcut,
    )

    game, packet = create_endgame_shortcut(
        "uncertain_victory"
    )

    assert packet["outcome"] == "uncertain_king_fall"
    assert game.complete is True
    assert game.alive is True
    assert packet["ending"]


def test_direct_clean_and_crown_shortcuts_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_endgame_shortcut,
    )

    clean_game, clean_packet = create_endgame_shortcut(
        "clean_fate_choice"
    )

    assert clean_packet["outcome"] == "clean_king_victory"
    assert clean_packet["stage"] == "fate_choice"
    assert clean_game.complete is False

    crown_game, crown_packet = create_endgame_shortcut(
        "crown_jail"
    )

    assert crown_packet["stage"] == "crown_loop"
    assert crown_game.king_fight["stage"] == "crown_loop"
    assert crown_game.endgame_action_label() == "Retire the Crown"
    assert crown_game.complete is False


def test_direct_retirement_shortcut_finishes_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_endgame_shortcut,
    )

    game, packet = create_endgame_shortcut(
        "retire_execute"
    )

    assert game.complete is True
    assert packet["ending"]
    assert "retir" in packet["ending"].lower()


def test_endgame_shortcut_packets_include_developer_cause_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_endgame_shortcut,
    )

    game, packet = create_endgame_shortcut(
        "retire_execute"
    )

    assert game.complete is True
    assert "developer_cause" in packet

    cause_text = "\n".join(packet["developer_cause"])

    assert "Shortcut: retire_execute" in cause_text
    assert "Outcome: retired_crown" in cause_text
    assert "Strength:" in cause_text
    assert "Army:" in cause_text
    assert "Kingdom:" in cause_text
    assert "Final flags:" in cause_text


def test_print_endgame_packet_shows_developer_cause_v180(
    capsys,
):
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_endgame_shortcut,
    )
    from ghost.examples.ghost_revolution.presentation import (
        print_endgame_packet,
    )

    _game, packet = create_endgame_shortcut(
        "retire_jail"
    )

    print_endgame_packet(packet)

    output = capsys.readouterr().out

    assert "Developer cause:" in output
    assert "Shortcut: retire_jail" in output
    assert "Strength:" in output
    assert "Army:" in output
    assert "Kingdom:" in output


def test_weapon_cache_label_explains_scale_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        weapon_cache_label,
        weapon_cache_range,
    )

    assert weapon_cache_range(8) == (40, 64)
    assert weapon_cache_label(8) == (
        "8 caches (arms about 40-64 fighters)"
    )


def test_wounded_shortcut_packet_explains_half_health_v180():
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )

    game, packet = create_fight_stage_shortcut(
        "wounded_king"
    )

    assert game.king_fight["player_health"] == 5
    assert "wounded_start_explanation" in packet
    assert "developer_cause" in packet

    explanation = "\n".join(
        packet["wounded_start_explanation"]
    )
    cause = "\n".join(packet["developer_cause"])

    assert "Wounded start:" in explanation
    assert "half health" in explanation
    assert "below strong threshold" in explanation
    assert "weapon caches" in explanation
    assert "Wounded reason:" in cause


def test_print_endgame_packet_shows_wounded_start_reason_v180(
    capsys,
):
    from ghost.examples.ghost_revolution.dev_shortcuts import (
        create_fight_stage_shortcut,
    )
    from ghost.examples.ghost_revolution.presentation import (
        print_endgame_packet,
    )

    _game, packet = create_fight_stage_shortcut(
        "wounded_king"
    )

    print_endgame_packet(packet)

    output = capsys.readouterr().out

    assert "Wounded start:" in output
    assert "half health" in output
    assert "weapon caches" in output
    assert "Developer cause:" in output
