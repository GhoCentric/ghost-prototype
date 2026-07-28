from ghost import GhostAPI
from ghost.events import normalize_game_action


def test_game_action_aliases_normalize_consistently():
    assert normalize_game_action("apologize") == "apology"
    assert normalize_game_action("apology") == "apology"

    assert normalize_game_action("steal") == "theft"
    assert normalize_game_action("theft") == "theft"

    assert normalize_game_action("betray") == "betrayal"
    assert normalize_game_action("betrayal") == "betrayal"


def test_steal_can_propagate_through_public_api():
    api = GhostAPI()

    packet = api.propagate_social_event(
        "player",
        "shopkeeper",
        "steal",
        observers=["guard"],
    )

    assert packet["event"] == "theft"
    assert packet["direct"]["diagnostics"]["direction"] == "negative"
    assert packet["propagated"][0]["affected"] == "guard"
    assert (
        packet["propagated"][0]["source_event"]
        == "theft"
    )


def test_propagate_event_normalizes_steal_alias():
    api = GhostAPI()

    packets = api.propagate_event(
        "player",
        "shopkeeper",
        {"type": "steal"},
        network=["guard"],
        heat=5,
    )

    assert len(packets) == 2
    assert packets[0]["event"]["type"] == "theft"
    assert packets[1]["event"]["type"] == "theft"


def test_apology_alias_preserves_public_api_behavior():
    api = GhostAPI()

    api.apply_event(
        "player",
        "shopkeeper",
        {"type": "threat"},
    )

    before = api.get_relationship(
        "player",
        "shopkeeper",
    )["trust"]

    api.apply_event(
        "player",
        "shopkeeper",
        {"type": "apologize"},
    )

    after = api.get_relationship(
        "player",
        "shopkeeper",
    )["trust"]

    assert after > before
    assert after <= 0.0
