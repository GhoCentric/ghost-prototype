import json

import pytest

from ghost import GhostAPI
from ghost.objectives import (
    COMBAT_OBJECTIVE_PRIORITIES,
    build_combat_objective_packet,
)


def _objective(**overrides):
    values = {
        "actor": "king",
        "target": "player",
        "actor_health": 20,
        "actor_max_health": 20,
        "target_health": 4,
        "target_max_health": 10,
        "turns_remaining": 13,
        "expected_damage_per_success": 3,
        "deadline_label": "castle collapse",
    }
    values.update(overrides)

    return build_combat_objective_packet(
        **values
    )


def test_combat_objective_is_ghost_owned_and_json_safe_v180():
    packet = _objective()

    assert packet["kind"] == "combat_objective"
    assert packet["state_owner"] == "Ghost"
    assert packet["outcome_authority"] == "Ghost"
    assert packet["policy_role"] == "proposal_only"
    assert packet["status"] == "active"

    json.dumps(
        packet,
        allow_nan=False,
    )


def test_combat_objective_defines_fight_level_goal_v180():
    packet = _objective()

    assert packet["primary_goal"] == (
        "Defeat player before castle collapse."
    )

    assert packet["success_condition"] == (
        "player reaches zero health before castle collapse."
    )

    assert "receives another action" in (
        packet["continuation_rule"]
    )

    assert "current and future exchanges" in (
        packet["optimization_rule"]
    )

    assert "variety" in (
        packet["exploration_rule"]
    )


def test_combat_objective_derives_finishing_horizon_v180():
    tactical = _objective()[
        "tactical_state"
    ]

    assert tactical[
        "successful_exchanges_to_defeat_target"
    ] == 2

    assert tactical[
        "current_exchange_can_standard_finish"
    ] is False

    assert tactical[
        "future_exchange_required_for_standard_finish"
    ] is True

    assert tactical[
        "target_acts_again_if_exchange_nonterminal"
    ] is True

    assert tactical[
        "finishing_opportunity"
    ] is True

    assert tactical["pressure_band"] == (
        "finishing_window"
    )


def test_combat_objective_marks_immediate_finish_v180():
    tactical = _objective(
        target_health=3,
    )["tactical_state"]

    assert tactical[
        "successful_exchanges_to_defeat_target"
    ] == 1

    assert tactical[
        "current_exchange_can_standard_finish"
    ] is True

    assert tactical["pressure_band"] == (
        "immediate_finish"
    )


def test_combat_objective_terminal_statuses_v180():
    complete = _objective(
        target_health=0,
    )

    failed = _objective(
        actor_health=0,
    )

    deadline_failed = _objective(
        turns_remaining=0,
    )

    assert complete["status"] == "complete"
    assert failed["status"] == "failed"
    assert deadline_failed["status"] == "failed"

    assert complete[
        "tactical_state"
    ]["pressure_band"] == "terminal"


def test_combat_objective_returns_fresh_priorities_v180():
    first = _objective()
    first["priorities"].append(
        "caller mutation"
    )

    second = _objective()

    assert second["priorities"] == list(
        COMBAT_OBJECTIVE_PRIORITIES
    )

    assert "caller mutation" not in (
        second["priorities"]
    )


@pytest.mark.parametrize(
    (
        "overrides",
        "match",
    ),
    [
        (
            {"actor": "player"},
            "actor and target must differ",
        ),
        (
            {"actor_health": 21},
            "actor health cannot exceed",
        ),
        (
            {"target_health": 11},
            "target health cannot exceed",
        ),
        (
            {"turns_remaining": -1},
            "turns remaining",
        ),
        (
            {"expected_damage_per_success": 0},
            "positive integer",
        ),
        (
            {"expected_damage_per_success": True},
            "non-negative integer",
        ),
    ],
)
def test_combat_objective_rejects_invalid_state_v180(
    overrides,
    match,
):
    with pytest.raises(
        ValueError,
        match=match,
    ):
        _objective(
            **overrides
        )


def test_api_combat_objective_is_read_only_v180():
    api = GhostAPI()
    before = api.snapshot()

    packet = api.build_combat_objective(
        actor="king",
        target="player",
        actor_health=20,
        actor_max_health=20,
        target_health=4,
        target_max_health=10,
        turns_remaining=13,
        expected_damage_per_success=3,
        deadline_label="castle collapse",
    )

    after = api.snapshot()

    assert packet["state_owner"] == "Ghost"
    assert after == before
