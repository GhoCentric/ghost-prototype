"""Coverage closure for GuardSystem validation and tactical branches."""

from __future__ import annotations

import pytest

from ghost.examples.ghost_revolution.guard import GuardSystem


def test_guard_identity_and_intent_validation_branches_v180():
    guards = GuardSystem()

    with pytest.raises(ValueError, match="guard rank must be a string"):
        guards.guard_profile(None)

    with pytest.raises(ValueError, match="unknown guard rank: missing"):
        guards.guard_profile(" missing ")

    with pytest.raises(ValueError, match="guard id must be a string"):
        guards.new_guard(guard_id=None, rank="watchman")

    with pytest.raises(ValueError, match="guard id must not be empty"):
        guards.new_guard(guard_id="   ", rank="watchman")

    with pytest.raises(
        ValueError,
        match="invalid internal guard combat intent",
    ):
        guards.combat_intent(None)

    with pytest.raises(
        ValueError,
        match="invalid internal guard combat intent",
    ):
        guards.combat_intent(" missing ")


def test_tactical_move_and_free_attack_validation_branches_v180():
    guards = GuardSystem()

    with pytest.raises(ValueError, match="Choose heavy, light"):
        guards.resolve_tactical_exchange(
            rank="watchman",
            intent="open_line",
            player_move=None,
        )

    with pytest.raises(
        ValueError,
        match="Your parry opened the guard",
    ):
        guards.resolve_tactical_exchange(
            rank="watchman",
            intent="open_line",
            player_move="parry",
            free_attack=True,
        )


def test_tight_defense_covers_block_and_read_without_counter_v180():
    guards = GuardSystem()

    blocked = guards.resolve_tactical_exchange(
        rank="watchman",
        intent="tight_defense",
        player_move="heavy",
    )

    assert blocked["result"] == "blocked"
    assert blocked["wrong_reads_delta"] == 1

    read = guards.resolve_tactical_exchange(
        rank="watchman",
        intent="tight_defense",
        player_move="feint_light",
        feint_read_roll=1,
        counter_roll=21,
    )

    assert read["result"] == "feint_read"
    assert read["player_damage"] == 0
    assert "counter" not in read["message"]


@pytest.mark.parametrize(
    ("move", "result", "guard_damage", "player_damage"),
    (
        ("light", "partial_light", 1, 0),
        ("feint_heavy", "feint_through_opening", 3, 0),
        ("feint_light", "feint_through_opening", 2, 0),
        ("dodge", "dodge_no_progress", 0, 0),
        ("parry", "bad_defense", 0, 2),
    ),
)
def test_open_line_remaining_move_matrix_v180(
    move,
    result,
    guard_damage,
    player_damage,
):
    packet = GuardSystem().resolve_tactical_exchange(
        rank="watchman",
        intent="open_line",
        player_move=move,
    )

    assert packet["result"] == result
    assert packet["guard_damage"] == guard_damage
    assert packet["player_damage"] == player_damage


@pytest.mark.parametrize(
    ("move", "result", "guard_damage", "player_damage"),
    (
        ("light", "light_lands", 2, 0),
        ("heavy", "partial_heavy", 1, 0),
        ("feint_heavy", "feint_on_recovery", 3, 0),
        ("feint_light", "feint_on_recovery", 2, 0),
        ("dodge", "dodge_no_progress", 0, 0),
        ("deflect", "bad_defense", 0, 2),
    ),
)
def test_recovering_remaining_move_matrix_v180(
    move,
    result,
    guard_damage,
    player_damage,
):
    packet = GuardSystem().resolve_tactical_exchange(
        rank="watchman",
        intent="recovering",
        player_move=move,
    )

    assert packet["result"] == result
    assert packet["guard_damage"] == guard_damage
    assert packet["player_damage"] == player_damage


def test_committed_heavy_remaining_defense_paths_v180():
    guards = GuardSystem()

    dodge = guards.resolve_tactical_exchange(
        rank="watchman",
        intent="committed_heavy",
        player_move="dodge",
    )

    assert dodge["result"] == "dodge_success"

    failed = guards.resolve_tactical_exchange(
        rank="watchman",
        intent="committed_heavy",
        player_move="parry",
        technique_roll=76,
    )

    assert failed["result"] == "parry_fail"
    assert failed["player_damage"] == 3

    punished = guards.resolve_tactical_exchange(
        rank="watchman",
        intent="committed_heavy",
        player_move="heavy",
    )

    assert punished["result"] == "heavy_punish"
    assert punished["player_damage"] == 3


def test_wide_cut_remaining_defense_paths_v180():
    guards = GuardSystem()

    dodge = guards.resolve_tactical_exchange(
        rank="watchman",
        intent="wide_cut",
        player_move="dodge",
    )

    assert dodge["result"] == "dodge_success"

    failed = guards.resolve_tactical_exchange(
        rank="watchman",
        intent="wide_cut",
        player_move="deflect",
        technique_roll=71,
    )

    assert failed["result"] == "deflect_fail"
    assert failed["player_damage"] == 2

    punished = guards.resolve_tactical_exchange(
        rank="watchman",
        intent="wide_cut",
        player_move="heavy",
    )

    assert punished["result"] == "wide_punish"
    assert punished["player_damage"] == 2


def test_unknown_internal_intent_trips_exhaustiveness_guard_v180(
    monkeypatch,
):
    monkeypatch.setattr(
        GuardSystem,
        "combat_intent",
        classmethod(
            lambda cls, intent: {
                "intent": "unknown_internal_intent",
            }
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="unhandled guard combat intent",
    ):
        GuardSystem().resolve_tactical_exchange(
            rank="watchman",
            intent="ignored",
            player_move="heavy",
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    (
        ({"witnesses": 0}, "witnesses must be a positive integer"),
        ({"fear": -1}, "fear must be a non-negative integer"),
        (
            {"royal_alert": -1},
            "royal_alert must be a non-negative integer",
        ),
        (
            {"execution_memory": -1},
            "execution_memory must be a non-negative integer",
        ),
    ),
)
def test_player_loss_rejects_invalid_social_context_v180(
    overrides,
    message,
):
    kwargs = {
        "rank": "watchman",
        "roll": 100,
        "trust": 0.0,
        "fear": 0,
        "witnesses": 1,
        "royal_alert": 0,
        "execution_memory": 0,
    }
    kwargs.update(overrides)

    with pytest.raises(ValueError, match=message):
        GuardSystem().resolve_player_loss_outcome(**kwargs)


def test_player_loss_positive_trust_and_witnesses_raise_escape_v180():
    outcome = GuardSystem().resolve_player_loss_outcome(
        rank="watchman",
        roll=100,
        trust=0.25,
        fear=2,
        witnesses=3,
        royal_alert=0,
        execution_memory=0,
    )

    assert outcome["escape_chance"] == 30
    assert outcome["death_chance"] == 2
    assert outcome["detention_chance"] == 68
