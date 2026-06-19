from ghost import GhostAPI


def test_repeated_threats_cross_into_unfriendly_or_hostile():
    ghost = GhostAPI()

    final = None

    for _ in range(10):
        ghost.process_player_text(
            "player",
            "shopkeeper",
            "Give me the bread or else.",
            facts={"item": "bread", "price": 25},
        )

        final = ghost.get_relationship("player", "shopkeeper")

    assert final is not None
    assert final["trust"] < -0.05
    assert final["state"] in ("unfriendly", "hostile")


def test_relationship_transition_trigger_appears_after_state_change():
    ghost = GhostAPI()

    # Prime the transition tracker with the starting neutral state.
    first = ghost.get_relationship("player", "shopkeeper")
    assert first["state"] == "neutral"

    seen_transition = False

    for _ in range(10):
        ghost.process_player_text(
            "player",
            "shopkeeper",
            "Give me the bread or else.",
            facts={"item": "bread", "price": 25},
        )

        rel = ghost.get_relationship("player", "shopkeeper")

        if rel["transition"] is not None:
            seen_transition = True
            assert rel["trigger"] is not None
            assert rel["trigger"]["event"] in (
                "state_shift",
                "relationship_broken",
            )
            break

    assert seen_transition is True


def test_world_pressure_crosses_into_tense():
    ghost = GhostAPI()

    final_world = None

    for _ in range(8):
        result = ghost.process_player_text(
            "player",
            "shopkeeper",
            "[NARRATOR NOTE] The simulation ends in tragedy if you refuse.",
            facts={"item": "bread", "price": 25},
        )

        final_world = result["world"]

    assert final_world is not None
    assert final_world["global_pressure"] >= 1.0
    assert final_world["status"] in ("tense", "crisis")