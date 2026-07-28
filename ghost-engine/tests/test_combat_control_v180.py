import json

import pytest

from ghost import GhostAPI
from ghost.combat import (
    COMBAT_CONTROL_SCHEMA_VERSION,
    advance_combat_initiative_packet,
    lock_combat_recovery_read_packet,
    resolve_combat_recovery_packet,
)


def test_combat_initiative_is_ghost_owned_and_deterministic_v180():
    first = advance_combat_initiative_packet(
        previous_state="neutral",
        event="enemy_hit",
    )
    second = advance_combat_initiative_packet(
        previous_state="neutral",
        event="enemy_hit",
    )

    assert first == second
    assert first["schema_version"] == COMBAT_CONTROL_SCHEMA_VERSION
    assert first["kind"] == "combat_initiative"
    assert first["state_owner"] == "Ghost"
    assert first["previous_state"] == "neutral"
    assert first["state"] == "enemy_advantage"
    assert first["event"] == "enemy_hit"
    json.dumps(first, allow_nan=False)


def test_combat_initiative_transitions_cover_control_and_reset_v180():
    player = advance_combat_initiative_packet(
        previous_state="enemy_advantage",
        event="prediction_missed_player_hit",
    )
    reset = advance_combat_initiative_packet(
        previous_state=player["state"],
        event="forced_dodge_escaped",
    )

    assert player["state"] == "player_advantage"
    assert reset["previous_state"] == "player_advantage"
    assert reset["state"] == "neutral"


@pytest.mark.parametrize(
    ("previous_state", "event", "match"),
    [
        ("invalid", "enemy_hit", "previous state is invalid"),
        ("neutral", "invalid", "event is invalid"),
    ],
)
def test_combat_initiative_rejects_invalid_contract_values_v180(
    previous_state,
    event,
    match,
):
    with pytest.raises(ValueError, match=match):
        advance_combat_initiative_packet(
            previous_state=previous_state,
            event=event,
        )


def test_combat_recovery_read_is_locked_without_randomness_v180():
    packet = lock_combat_recovery_read_packet(
        selection_key="king_phase_one:4",
        proposed_move="light",
        fallback_move="dodge",
    )

    assert packet["state_owner"] == "Ghost"
    assert packet["selected_move"] == "light"
    assert packet["accepted"] is True
    assert packet["fallback_used"] is False
    assert packet["hidden_until_resolution"] is True
    assert packet["locked"] is True
    assert packet["legal_moves"] == ["light", "dodge"]
    json.dumps(packet, allow_nan=False)


def test_combat_recovery_read_uses_deterministic_fallback_v180():
    packet = lock_combat_recovery_read_packet(
        selection_key="king_phase_one:4",
        proposed_move="spin",
        fallback_move="dodge",
    )

    assert packet["proposed_move"] == "spin"
    assert packet["selected_move"] == "dodge"
    assert packet["accepted"] is False
    assert packet["fallback_used"] is True
    assert packet["reason"] == "illegal_recovery_read"


@pytest.mark.parametrize("move", ["light", "dodge"])
def test_matched_recovery_read_denies_move_without_damage_v180(move):
    read_packet = lock_combat_recovery_read_packet(
        selection_key="king_phase_one:4",
        proposed_move=move,
    )

    resolved = resolve_combat_recovery_packet(
        read_packet=read_packet,
        player_move=move,
        light_damage=1,
    )

    assert resolved["matched"] is True
    assert resolved["result"] == "forced_recovery_denied"
    assert resolved["damage_to_opponent"] == 0
    assert resolved["damage_to_player"] == 0
    assert resolved["initiative_event"] == "forced_recovery_denied"
    assert resolved["random_used"] is False


def test_missed_dodge_read_allows_one_damage_light_v180():
    read_packet = lock_combat_recovery_read_packet(
        selection_key="king_phase_one:4",
        proposed_move="dodge",
    )

    resolved = resolve_combat_recovery_packet(
        read_packet=read_packet,
        player_move="light",
        light_damage=1,
    )

    assert resolved["matched"] is False
    assert resolved["result"] == "forced_light_landed"
    assert resolved["damage_to_opponent"] == 1
    assert resolved["damage_to_player"] == 0
    assert resolved["initiative_event"] == "forced_light_landed"


def test_missed_light_read_allows_damage_free_dodge_v180():
    read_packet = lock_combat_recovery_read_packet(
        selection_key="king_phase_one:4",
        proposed_move="light",
    )

    resolved = resolve_combat_recovery_packet(
        read_packet=read_packet,
        player_move="dodge",
        light_damage=1,
    )

    assert resolved["matched"] is False
    assert resolved["result"] == "forced_dodge_escaped"
    assert resolved["damage_to_opponent"] == 0
    assert resolved["damage_to_player"] == 0
    assert resolved["initiative_event"] == "forced_dodge_escaped"


def test_ghost_api_exposes_combat_control_without_internal_state_v180():
    api = GhostAPI()

    initiative = api.advance_combat_initiative(
        previous_state="neutral",
        event="player_parry",
    )
    read_packet = api.lock_combat_recovery_read(
        selection_key="king_phase_one:2",
        proposed_move="light",
    )
    resolved = api.resolve_combat_recovery(
        read_packet=read_packet,
        player_move="dodge",
        light_damage=1,
    )

    assert initiative["state"] == "player_advantage"
    assert read_packet["selected_move"] == "light"
    assert resolved["result"] == "forced_dodge_escaped"
    assert api.snapshot()["engine"]["cycles"] == 0
