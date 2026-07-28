from ghost.examples.ghost_revolution.demo import (
    GhostRevolutionRun,
)


def test_dashboard_relationship_uses_runtime_player_actor():
    game = GhostRevolutionRun()
    game.location = "ashfield"

    packet = game.recruit_quietly()

    assert packet is not None
    assert game.relationship("ashfield")["trust"] == (
        packet["relationship"]["trust"]
    )


def test_failed_recruitment_does_not_spend_action():
    game = GhostRevolutionRun()
    game.location = "ashfield"
    game.recruited_today["ashfield"] = (
        game.recruitment_limit_today("ashfield")
    )

    actions_before = game.actions

    packet = game.recruit_quietly()

    assert packet is None
    assert game.actions == actions_before
    assert "no more willing recruits" in game.last_action_note


def test_failed_food_purchase_does_not_spend_action():
    game = GhostRevolutionRun()
    game.location = "ashfield"
    game.gold = 0

    actions_before = game.actions

    assert game.buy_food("bread") is False
    assert game.actions == actions_before
    assert game.gold == 0


def test_every_town_has_honest_gold_work():
    for town_id in ("ashfield", "millcross", "crownmarket"):
        game = GhostRevolutionRun()
        game.location = town_id

        if town_id == "crownmarket":
            game.knight_town = "ashfield"

        gold_before = game.gold
        packet = game.earn_honest_gold()

        assert packet is not None
        assert game.gold > gold_before


def test_food_need_scales_with_follower_count():
    game = GhostRevolutionRun()

    assert game.daily_food_need() == 1

    game.followers = 6
    assert game.daily_food_need() == 2

    game.followers = 20
    assert game.daily_food_need() == 3

    game.followers = 40
    assert game.daily_food_need() == 4


def test_blacksmith_tracks_weapon_type():
    game = GhostRevolutionRun()
    game.location = "ashfield"
    game.gold = 100

    assert game.blacksmith_buy("axe") is True
    assert game.primary_weapon == "axe"
    assert game.weapons == 2
