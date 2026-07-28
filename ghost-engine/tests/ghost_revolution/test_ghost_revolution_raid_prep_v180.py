from ghost.examples.ghost_revolution.demo import (
    GhostRevolutionRun,
)


def test_raid_requirements_scale_by_town():
    game = GhostRevolutionRun()

    assert (
        game.raid_requirement("ashfield")["recommended_warriors"]
        == 25
    )
    assert (
        game.raid_requirement("millcross")["recommended_warriors"]
        == 50
    )
    assert (
        game.raid_requirement("crownmarket")["recommended_warriors"]
        == 75
    )
    assert (
        game.raid_requirement("castle")["recommended_warriors"]
        == 100
    )


def test_leader_weapon_is_separate_from_army_stock():
    game = GhostRevolutionRun()

    assert game.leader_weapon_label() == "Knight's Sword [COMMON]"
    assert game.weapon_stock_total() == 1
    assert game.army_weapons_issued() == 0


def test_raid_force_cannot_exceed_available_warriors():
    game = GhostRevolutionRun()
    game.followers = 10

    assert game.set_combat_role("warriors", 7) is True
    assert game.plan_raid("ashfield") is not None

    assert game.set_raid_force(8) is False
    assert "cannot send more warriors" in game.last_action_note

    assert game.set_raid_force(7) is True


def test_raid_weapon_issue_cannot_exceed_force():
    game = GhostRevolutionRun()
    game.followers = 12

    assert game.set_combat_role("warriors", 8) is True
    assert game.plan_raid("ashfield") is not None
    assert game.set_raid_force(2) is True

    game.weapon_stock["sword"] = 4
    game.weapons = game.weapon_stock_total()

    assert game.set_raid_weapon_issue("sword", 3) is False
    assert "more weapons than raid warriors" in game.last_action_note

    assert game.set_raid_weapon_issue("sword", 2) is True




def test_raid_weapon_reservation_removes_gear_from_base_stock():
    game = GhostRevolutionRun()
    game.followers = 10
    game.weapon_stock["sword"] = 4
    game.weapons = game.weapon_stock_total()

    assert game.set_combat_role("warriors", 4) is True
    assert game.plan_raid("ashfield") is not None
    assert game.set_raid_force(4) is True
    assert game.set_raid_weapon_issue("sword", 3) is True

    assert game.weapon_stock["sword"] == 1
    assert game.army_weapons_issued() == 3
    assert game.weapons == 4


def test_raid_weapon_reservation_revision_returns_base_stock():
    game = GhostRevolutionRun()
    game.followers = 10
    game.weapon_stock["sword"] = 4
    game.weapons = game.weapon_stock_total()

    assert game.set_combat_role("warriors", 4) is True
    assert game.plan_raid("ashfield") is not None
    assert game.set_raid_force(4) is True
    assert game.set_raid_weapon_issue("sword", 3) is True
    assert game.set_raid_weapon_issue("sword", 1) is True

    assert game.weapon_stock["sword"] == 3
    assert game.army_weapons_issued() == 1
    assert game.weapons == 4


def test_cancel_raid_plan_returns_reserved_weapons_and_shields():
    game = GhostRevolutionRun()
    game.followers = 10
    game.weapon_stock["sword"] = 4
    game.shield_stock["light"] = 2
    game.weapons = game.weapon_stock_total()

    assert game.set_combat_role("warriors", 4) is True
    assert game.plan_raid("ashfield") is not None
    assert game.set_raid_force(4) is True
    assert game.set_raid_weapon_issue("sword", 3) is True
    assert game.set_raid_shield_issue("light", 2) is True

    assert game.cancel_raid_plan() is True

    assert game.raid_plan is None
    assert game.weapon_stock["sword"] == 4
    assert game.shield_stock["light"] == 2
    assert game.weapons == 4


def test_replacing_raid_plan_returns_prior_reserved_gear():
    game = GhostRevolutionRun()
    game.followers = 10
    game.weapon_stock["sword"] = 4
    game.weapons = game.weapon_stock_total()

    assert game.set_combat_role("warriors", 4) is True
    assert game.plan_raid("ashfield") is not None
    assert game.set_raid_force(4) is True
    assert game.set_raid_weapon_issue("sword", 3) is True

    assert game.plan_raid("millcross") is not None

    assert game.raid_plan["target"] == "millcross"
    assert game.weapon_stock["sword"] == 4
    assert game.army_weapons_issued() == 0
    assert game.weapons == 4


def test_training_creates_real_weapon_stock():
    game = GhostRevolutionRun()
    game.phase = "camp"
    game.actions = 3
    game.followers = 3
    game.food = 2

    swords_before = game.weapon_stock["sword"]
    weapons_before = game.weapons

    assert game.train_rebels() is True

    assert game.weapon_stock["sword"] == swords_before + 1
    assert game.weapons == weapons_before + 1

def test_raid_readiness_requires_food_force_and_weapons():
    game = GhostRevolutionRun()
    game.followers = 30

    assert game.set_combat_role("warriors", 25) is True
    assert game.plan_raid("ashfield") is not None
    assert game.set_raid_force(25) is True

    game.food = 6
    game.weapon_stock["sword"] = 18
    game.weapons = game.weapon_stock_total()

    assert game.set_raid_weapon_issue("sword", 18) is True

    readiness = game.raid_readiness("ashfield")

    assert readiness["ready"] is True
    assert readiness["food_required"] == 6
    assert readiness["recommended_weapons"] == 18


def build_ready_ashfield_raid():
    game = GhostRevolutionRun()
    game.followers = 30
    game.food = 6
    game.weapon_stock["sword"] = 18
    game._sync_weapon_total()

    assert game.set_combat_role("warriors", 25) is True
    assert game.plan_raid("ashfield") is not None
    assert game.set_raid_force(25) is True
    assert game.set_raid_weapon_issue("sword", 18) is True

    return game


def test_commit_raid_consumes_food_and_creates_active_state():
    game = build_ready_ashfield_raid()

    assert game.commit_raid() is True

    raid = game.active_raid_summary()

    assert game.raid_plan is None
    assert raid["target"] == "ashfield"
    assert raid["force"] == 25
    assert raid["food_committed"] == 6
    assert game.food == 0
    assert game.deployed_warriors() == 25
    assert game.available_warriors() == 0
    assert game.weapon_stock["sword"] == 0
    assert game.army_weapons_issued() == 18
    assert game.weapons == 18


def test_committed_raid_blocks_cancel_replan_and_role_reduction():
    game = build_ready_ashfield_raid()

    assert game.commit_raid() is True

    assert game.cancel_raid_plan() is False
    assert "already deployed" in game.last_action_note

    assert game.plan_raid("millcross") is None
    assert "already active" in game.last_action_note

    assert game.set_combat_role("warriors", 24) is False
    assert "already deployed" in game.last_action_note


def test_commit_raid_requires_ready_plan_without_mutating_state():
    game = GhostRevolutionRun()

    assert game.plan_raid("ashfield") is not None

    food_before = game.food
    stock_before = game.weapon_stock_total()

    assert game.commit_raid() is False

    assert game.active_raid is None
    assert game.raid_plan is not None
    assert game.food == food_before
    assert game.weapon_stock_total() == stock_before
