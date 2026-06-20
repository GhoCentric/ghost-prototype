from ghost import GhostAPI


def _help(api):
    api.apply_event(
        "player",
        "shopkeeper",
        {
            "type": "help",
            "intensity": 1.0,
        },
    )


def test_repeated_help_cannot_exceed_default_positive_cap():
    api = GhostAPI()

    for _ in range(100):
        _help(api)

    relationship = api.get_relationship(
        "player",
        "shopkeeper",
    )

    assert relationship["trust"] <= 3.25


def test_relationship_can_use_lower_positive_cap():
    api = GhostAPI()

    api.engine.relationships.set_params(
        "player",
        "shopkeeper",
        positive_reservoir_cap=0.50,
    )

    for _ in range(100):
        _help(api)

    relationship = api.get_relationship(
        "player",
        "shopkeeper",
    )

    assert relationship["trust"] <= 0.50
