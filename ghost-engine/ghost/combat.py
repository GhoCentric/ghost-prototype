"""
Deterministic combat-control packets for Ghost v1.8.0.

Ghost owns committed recovery reads and initiative transitions. A game
supplies concrete legal moves and applies returned damage to its own
health model. External policies may propose reads, but Ghost validates,
locks, reveals, and resolves them.
"""

from __future__ import annotations

from typing import Any, Mapping


COMBAT_CONTROL_SCHEMA_VERSION = "1.0"

COMBAT_INITIATIVE_STATES = (
    "enemy_advantage",
    "neutral",
    "player_advantage",
)

COMBAT_RECOVERY_MOVES = (
    "light",
    "dodge",
)


_INITIATIVE_TRANSITIONS = {
    "fight_started": (
        "neutral",
        "The duel begins without established control.",
    ),
    "stage_transition": (
        "neutral",
        "A new opponent or phase resets immediate control.",
    ),
    "player_attack_hit": (
        "player_advantage",
        "A landed attack gives the player control of the next beat.",
    ),
    "player_parry": (
        "player_advantage",
        "The successful parry turns the opponent's force into player control.",
    ),
    "player_deflect": (
        "player_advantage",
        "The deflection redirects pressure and gives the player control.",
    ),
    "player_dodge": (
        "neutral",
        "The dodge escapes pressure without establishing offensive control.",
    ),
    "enemy_hit": (
        "enemy_advantage",
        "The opponent's landed hit preserves offensive control.",
    ),
    "enemy_counter": (
        "enemy_advantage",
        "A correct hidden counter gives the opponent control.",
    ),
    "prediction_missed_player_hit": (
        "player_advantage",
        "The missed prediction permits a landed player attack.",
    ),
    "prediction_missed_player_escape": (
        "neutral",
        "The missed prediction lets the player escape back to neutral.",
    ),
    "forced_recovery_denied": (
        "enemy_advantage",
        "The opponent correctly reads the restricted recovery and keeps control.",
    ),
    "forced_light_landed": (
        "player_advantage",
        "The opponent misses the recovery read and the light cut steals control.",
    ),
    "forced_dodge_escaped": (
        "neutral",
        "The opponent misses the recovery read and the dodge resets the duel.",
    ),
    "player_bait": (
        "player_advantage",
        "A successful bait gives the player control of the hidden recovery beat.",
    ),
    "bait_read_denied": (
        "enemy_advantage",
        "The opponent refuses the bait and keeps control without damage.",
    ),
    "bait_light_landed": (
        "player_advantage",
        "The bait exposes guard recovery and the light cut steals control.",
    ),
    "bait_parry_success": (
        "player_advantage",
        "The bait draws quick retaliation and the parry turns it into control.",
    ),
    "bait_recovery_denied": (
        "enemy_advantage",
        "The opponent recognizes the bait midway and recovers control.",
    ),
    "preserve": (
        None,
        "The exchange preserves the existing initiative state.",
    ),
}


def _combat_text(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a non-empty string")

    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")

    if not normalized:
        raise ValueError(f"{label} must be a non-empty string")

    return normalized


def _combat_non_negative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")

    return value


def advance_combat_initiative_packet(
    *,
    previous_state: str,
    event: str,
) -> dict:
    """Advance one authoritative Ghost initiative state."""
    previous_state = _combat_text(
        previous_state,
        "combat initiative previous state",
    )

    if previous_state not in COMBAT_INITIATIVE_STATES:
        raise ValueError("combat initiative previous state is invalid")

    event = _combat_text(event, "combat initiative event")

    if event not in _INITIATIVE_TRANSITIONS:
        raise ValueError("combat initiative event is invalid")

    configured_state, reason = _INITIATIVE_TRANSITIONS[event]
    next_state = previous_state if configured_state is None else configured_state

    if next_state == previous_state:
        shift = "held"
    elif next_state == "neutral":
        shift = "reset"
    else:
        shift = "changed"

    return {
        "schema_version": COMBAT_CONTROL_SCHEMA_VERSION,
        "kind": "combat_initiative",
        "state_owner": "Ghost",
        "previous_state": previous_state,
        "state": next_state,
        "event": event,
        "shift": shift,
        "reason": reason,
    }


def lock_combat_recovery_read_packet(
    *,
    selection_key: str,
    proposed_move: str | None,
    fallback_move: str = "dodge",
) -> dict:
    """Validate and lock a hidden light-or-dodge recovery prediction."""
    if not isinstance(selection_key, str) or not selection_key.strip():
        raise ValueError("combat recovery selection key must be a non-empty string")

    fallback_move = _combat_text(
        fallback_move,
        "combat recovery fallback move",
    )

    if fallback_move not in COMBAT_RECOVERY_MOVES:
        raise ValueError("combat recovery fallback move is invalid")

    normalized = None

    if isinstance(proposed_move, str) and proposed_move.strip():
        normalized = _combat_text(
            proposed_move,
            "combat recovery proposed move",
        )

    accepted = normalized in COMBAT_RECOVERY_MOVES
    selected_move = normalized if accepted else fallback_move

    if accepted:
        reason = "accepted"
    elif normalized is None:
        reason = "missing_recovery_read"
    else:
        reason = "illegal_recovery_read"

    return {
        "schema_version": COMBAT_CONTROL_SCHEMA_VERSION,
        "kind": "combat_recovery_read",
        "state_owner": "Ghost",
        "selection_key": selection_key.strip(),
        "proposed_move": normalized,
        "selected_move": selected_move,
        "accepted": accepted,
        "fallback_used": not accepted,
        "reason": reason,
        "legal_moves": list(COMBAT_RECOVERY_MOVES),
        "hidden_until_resolution": True,
        "locked": True,
    }


def resolve_combat_recovery_packet(
    *,
    read_packet: Mapping[str, Any],
    player_move: str,
    light_damage: int = 1,
) -> dict:
    """
    Resolve a previously locked recovery read without randomness.

    A matched read denies the recovery but deals no damage. A missed light
    read lets the player's one-damage cut land. A missed dodge read lets the
    player escape. The opponent never receives a free damage roll here.
    """
    if not isinstance(read_packet, Mapping):
        raise ValueError("combat recovery read packet must be a mapping")

    if read_packet.get("kind") != "combat_recovery_read":
        raise ValueError("combat recovery read packet kind is invalid")

    if read_packet.get("schema_version") != COMBAT_CONTROL_SCHEMA_VERSION:
        raise ValueError("combat recovery read schema is unsupported")

    if read_packet.get("locked") is not True:
        raise ValueError("combat recovery read must be locked")

    predicted_move = _combat_text(
        read_packet.get("selected_move"),
        "combat recovery selected move",
    )

    if predicted_move not in COMBAT_RECOVERY_MOVES:
        raise ValueError("combat recovery selected move is invalid")

    player_move = _combat_text(
        player_move,
        "combat recovery player move",
    )

    if player_move not in COMBAT_RECOVERY_MOVES:
        raise ValueError("combat recovery player move is invalid")

    light_damage = _combat_non_negative_int(
        light_damage,
        "combat recovery light damage",
    )

    matched = player_move == predicted_move

    if matched:
        result = "forced_recovery_denied"
        damage_to_opponent = 0
        initiative_event = "forced_recovery_denied"
    elif player_move == "light":
        result = "forced_light_landed"
        damage_to_opponent = light_damage
        initiative_event = "forced_light_landed"
    else:
        result = "forced_dodge_escaped"
        damage_to_opponent = 0
        initiative_event = "forced_dodge_escaped"

    return {
        "schema_version": COMBAT_CONTROL_SCHEMA_VERSION,
        "kind": "combat_recovery_resolution",
        "state_owner": "Ghost",
        "selection_key": read_packet.get("selection_key"),
        "predicted_move": predicted_move,
        "player_move": player_move,
        "matched": matched,
        "result": result,
        "damage_to_opponent": damage_to_opponent,
        "damage_to_player": 0,
        "initiative_event": initiative_event,
        "random_used": False,
        "read_revealed": True,
    }
