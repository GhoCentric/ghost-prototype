from ghost import GhostAPI


def _run_public_social_scenario():
    api = GhostAPI()

    packet = api.propagate_social_event(
        "player",
        "captain",
        "betrayal",
        observers=["guard", "merchant"],
        weights={
            "guard": 1.0,
            "merchant": 0.5,
        },
    )

    guard = api.interpret_social_packet(
        "guard",
        packet,
        temperament="resentful",
    )

    merchant = api.interpret_social_packet(
        "merchant",
        packet,
        temperament="calm",
    )

    return {
        "packet": packet,
        "guard": guard,
        "merchant": merchant,
    }


def test_public_social_propagation_bridge_exists():
    api = GhostAPI()

    assert hasattr(api, "propagate_social_event")


def test_public_social_propagation_feeds_interpreter():
    result = _run_public_social_scenario()

    packet = result["packet"]
    guard = result["guard"]
    merchant = result["merchant"]

    assert packet["source"] == "player"
    assert packet["target"] == "captain"
    assert packet["event"] == "betrayal"
    assert "direct" in packet
    assert "propagated" in packet
    assert "world_effects" in packet

    affected = [
        item["affected"]
        for item in packet["propagated"]
    ]

    assert affected == ["guard", "merchant"]

    assert guard["npc"] == "guard"
    assert merchant["npc"] == "merchant"

    # The outer packet preserves the originating incident.
    assert packet["event"] == "betrayal"

    # Each observer receives a derived local relationship update.
    assert guard["source_event"] == "social_propagation"
    assert merchant["source_event"] == "social_propagation"

    assert isinstance(guard["interpretation"], dict)
    assert isinstance(merchant["interpretation"], dict)


def test_public_social_propagation_is_deterministic():
    first = _run_public_social_scenario()
    second = _run_public_social_scenario()

    assert first == second
