from copy import deepcopy
import json

import pytest

from ghost.examples.ghost_revolution.config import (
    TOWN_IDS,
    build_revolution_scenario,
)
from ghost.examples.ghost_revolution.demo import (
    GAME_SNAPSHOT_SCHEMA_VERSION,
    GhostRevolutionRun,
)
from ghost.examples.ghost_revolution.social import (
    GhostRevolutionSocialBridge,
)
from ghost.examples.ghost_revolution.town_memory import (
    TownMemory,
)


def _seed_complex_game() -> GhostRevolutionRun:
    game = GhostRevolutionRun(seed=17)
    game.followers = 3
    game.food = 20

    assert game.set_combat_role("scouts", 1) is True

    first_day = game.end_day()

    assert first_day["day_report"]["scout_reports"]

    assert game.set_combat_role("scouts", 0) is True
    assert game.set_combat_role("warriors", 2) is True
    assert game.plan_raid("ashfield") is not None
    assert game.set_raid_force(2) is True
    assert game.set_raid_weapon_issue("sword", 1) is True

    game._record_town_execution_memory(
        "millcross",
        "uncertain",
    )

    assert game.travel("millcross") is True
    assert game.question_guard() is None
    assert game.begin_public_event() is True
    assert game.rally_people() is not None

    return game


def test_game_snapshot_round_trip_preserves_full_fork_state_v180():
    source = _seed_complex_game()
    snapshot = source.snapshot()
    restored = GhostRevolutionRun.from_snapshot(snapshot)

    assert snapshot["schema_version"] == (
        GAME_SNAPSHOT_SCHEMA_VERSION
    )
    assert restored.snapshot() == snapshot

    assert restored.information_summary() == (
        source.information_summary()
    )
    assert restored.raid_plan == source.raid_plan
    assert restored.public_event_summary() == (
        source.public_event_summary()
    )
    assert restored.town_memory_label("millcross") == (
        source.town_memory_label("millcross")
    )
    assert restored.runtime.api.snapshot() == (
        source.runtime.api.snapshot()
    )

    json.dumps(snapshot, allow_nan=False, sort_keys=True)

    snapshot["state"]["towns"]["millcross"]["fear"] = 999
    snapshot["state"]["public_event_state"]["millcross"][
        "used_actions"
    ].append("tampered")
    snapshot["social"]["information_entries"][0][
        "message"
    ] = "tampered"

    assert source.towns["millcross"]["fear"] != 999
    assert "tampered" not in source.public_event_summary()[
        "used_actions"
    ]
    assert source.information_summary()["entries"][0][
        "message"
    ] != "tampered"
    assert restored.towns["millcross"]["fear"] != 999


def test_game_snapshot_restores_rng_for_deterministic_continuation_v180():
    source = GhostRevolutionRun(seed=7)
    source.knight_town = "ashfield"

    assert source.travel("millcross") is True

    checkpoint = source.snapshot()
    left = GhostRevolutionRun.from_snapshot(
        deepcopy(checkpoint)
    )
    right = GhostRevolutionRun.from_snapshot(
        deepcopy(checkpoint)
    )

    for game in (left, right):
        assert game.seize_royal_supplies() is None
        assert game.earn_honest_gold() is not None
        assert game.end_day()["day_report"]["starved"] is False

    assert left.snapshot() == right.snapshot()


def test_game_restore_snapshot_replaces_existing_run_in_place_v180():
    source = _seed_complex_game()
    checkpoint = source.snapshot()

    target = GhostRevolutionRun(seed=99)
    target.gold = 999
    target.food = 0
    target.knight_town = "ashfield"

    restored = target.restore_snapshot(checkpoint)

    assert restored == checkpoint
    assert target.snapshot() == checkpoint


def test_game_snapshot_rejects_invalid_packets_v180():
    source = GhostRevolutionRun(seed=7)
    snapshot = source.snapshot()

    with pytest.raises(ValueError, match="must be a dict"):
        GhostRevolutionRun.from_snapshot([])

    bad_keys = deepcopy(snapshot)
    bad_keys.pop("state")

    with pytest.raises(ValueError, match="unsupported keys"):
        GhostRevolutionRun.from_snapshot(bad_keys)

    bad_schema = deepcopy(snapshot)
    bad_schema["schema_version"] = "bad"

    with pytest.raises(
        ValueError,
        match="unsupported Ghost Revolution",
    ):
        GhostRevolutionRun.from_snapshot(bad_schema)

    bad_state = deepcopy(snapshot)
    bad_state["state"]["actions"] = True

    with pytest.raises(ValueError, match="numeric state"):
        GhostRevolutionRun.from_snapshot(bad_state)

    bad_rng = deepcopy(snapshot)
    bad_rng["rng_state"] = []

    with pytest.raises(ValueError, match="RNG state"):
        GhostRevolutionRun.from_snapshot(bad_rng)

    bad_events = deepcopy(snapshot)
    bad_events["state"]["public_event_state"][
        "ashfield"
    ]["used_actions"] = "not-a-list"

    with pytest.raises(ValueError, match="public event"):
        GhostRevolutionRun.from_snapshot(bad_events)

    bad_raid = deepcopy(snapshot)
    bad_raid["state"]["raid_state"] = {}

    with pytest.raises(ValueError, match="raid state"):
        GhostRevolutionRun.from_snapshot(bad_raid)


def test_social_and_town_memory_snapshots_reject_invalid_inputs_v180():
    bridge = GhostRevolutionSocialBridge(
        build_revolution_scenario()
    )
    social_snapshot = bridge.snapshot()
    restored_bridge = GhostRevolutionSocialBridge.from_snapshot(
        social_snapshot
    )

    assert restored_bridge.snapshot() == social_snapshot

    with pytest.raises(ValueError, match="must be a dict"):
        GhostRevolutionSocialBridge.from_snapshot([])

    bad_social_keys = deepcopy(social_snapshot)
    bad_social_keys.pop("api")

    with pytest.raises(ValueError, match="unsupported keys"):
        GhostRevolutionSocialBridge.from_snapshot(
            bad_social_keys
        )

    bad_social_schema = deepcopy(social_snapshot)
    bad_social_schema["schema_version"] = "bad"

    with pytest.raises(ValueError, match="unsupported social"):
        GhostRevolutionSocialBridge.from_snapshot(
            bad_social_schema
        )

    bad_information = deepcopy(social_snapshot)
    bad_information["information_sequence"] = 1

    with pytest.raises(ValueError, match="information sequence"):
        GhostRevolutionSocialBridge.from_snapshot(
            bad_information
        )

    memory = TownMemory(TOWN_IDS)
    memory.record_execution("millcross", "rejected")
    memory_snapshot = memory.snapshot()
    restored_memory = TownMemory.from_snapshot(
        TOWN_IDS,
        memory_snapshot,
    )

    assert restored_memory.snapshot() == memory_snapshot

    with pytest.raises(ValueError, match="must be a dict"):
        TownMemory.from_snapshot(TOWN_IDS, [])

    with pytest.raises(ValueError, match="unsupported keys"):
        TownMemory.from_snapshot(TOWN_IDS, {})

    bad_towns = deepcopy(memory_snapshot)
    bad_towns["execution_memory"].pop("millcross")

    with pytest.raises(ValueError, match="towns are invalid"):
        TownMemory.from_snapshot(TOWN_IDS, bad_towns)

    bad_value = deepcopy(memory_snapshot)
    bad_value["execution_memory"]["millcross"] = True

    with pytest.raises(ValueError, match="non-negative integer"):
        TownMemory.from_snapshot(TOWN_IDS, bad_value)

