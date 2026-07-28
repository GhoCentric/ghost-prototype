from ghost.examples.ghost_revolution.demo import (
    GhostRevolutionRun,
)


def test_follower_roles_keep_total_within_followers():
    game = GhostRevolutionRun()
    game.followers = 12

    assert game.set_combat_role("warriors", 7) is True
    assert game.set_combat_role("scouts", 3) is True

    roles = game.role_summary()

    assert roles["warriors"] == 7
    assert roles["scouts"] == 3
    assert roles["workers"] == 2


def test_camp_assignments_cannot_exceed_worker_group():
    game = GhostRevolutionRun()
    game.followers = 10

    assert game.set_combat_role("warriors", 8) is True

    game.phase = "camp"

    assert game.set_assignment("farmers", 3) is False
    assert game.set_assignment("farmers", 2) is True


def test_raid_plan_requires_hidden_base():
    game = GhostRevolutionRun()
    game.location = "ashfield"

    result = game.plan_raid("ashfield")

    assert result is None
    assert "hidden base" in game.last_action_note.lower()


def test_raid_plan_records_target_without_spending_action():
    game = GhostRevolutionRun()
    game.followers = 30

    assert game.set_combat_role("warriors", 25) is True

    actions_before = game.actions

    readiness = game.plan_raid("ashfield")

    assert readiness is not None
    assert readiness["camp"] == "Eastwatch Camp"
    assert readiness["warlord"] == "Garran the Iron Hand"
    assert game.raid_plan["target"] == "ashfield"
    assert game.actions == actions_before


def test_raid_readiness_warns_when_force_is_small():
    game = GhostRevolutionRun()
    game.followers = 12

    assert game.set_combat_role("warriors", 8) is True
    assert game.plan_raid("millcross") is not None
    assert game.set_raid_force(8) is True

    readiness = game.raid_readiness("millcross")

    assert readiness["ready"] is False
    assert readiness["recommended_warriors"] == 50
    assert readiness["warriors"] == 8
