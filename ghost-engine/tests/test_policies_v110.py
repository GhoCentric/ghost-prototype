from ghost import GhostAPI


def test_commerce_blocks_claim_effects_but_allows_normal_purchase():
    ghost = GhostAPI()

    decision = ghost.evaluate_commerce(
        severity=0.0,
        blacklisted=False,
        town_status="normal",
        claim_blocked_effects=("free_item", "price_waiver"),
    )

    assert decision["sale_access"] == "normal"
    assert decision["purchase_allowed"] is True
    assert "free_item" in decision["blocked_effects"]


def test_commerce_refuses_expelled_player():
    ghost = GhostAPI()

    decision = ghost.evaluate_commerce(
        severity=0.0,
        blacklisted=False,
        town_status="expelled",
    )

    assert decision["sale_access"] == "refused"
    assert decision["purchase_allowed"] is False
    assert decision["price_visible"] is False


def test_pricing_policy_relationship_price():
    ghost = GhostAPI()

    decision = ghost.compute_price(
        item="bread",
        base_price=20,
        relationship_state="neutral",
        sale_access="normal",
    )

    assert decision["final_price"] == 25
    assert decision["relationship_state"] == "neutral"


def test_pricing_policy_restricted_markup():
    ghost = GhostAPI()

    decision = ghost.compute_price(
        item="bread",
        base_price=20,
        relationship_state="neutral",
        sale_access="restricted",
        severity=0.5,
    )

    assert decision["final_price"] == 50
    assert decision["sale_access"] == "restricted"


def test_law_policy_detention_threshold():
    ghost = GhostAPI()

    decision = ghost.evaluate_law(
        severity=1.6,
        argument_pressure=0,
        warning_count=0,
        post_arrest_watch=0,
        release_grace=0,
    )

    assert decision["status"] == "detention"
    assert decision["action"] == "detain"


def test_reintegration_policy_resistance_blocks_recovery():
    ghost = GhostAPI()

    decision = ghost.evaluate_reintegration(
        served_punishment=True,
        current_trust=-0.8,
        arrest_count=1,
        resistance_remaining=2,
    )

    assert decision["allowed"] is False
    assert decision["recovery_multiplier"] == 0.5
