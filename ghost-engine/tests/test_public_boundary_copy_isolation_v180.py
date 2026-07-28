from ghost.api import GhostAPI
from ghost.world import WorldRuntime


def test_relationship_read_packets_are_deep_copied_v180():
    api = GhostAPI()

    api.apply_event(
        "player",
        "merchant",
        {"type": "betrayal"},
    )

    packet = api.get_relationship(
        "player",
        "merchant",
    )

    packet["trigger"]["event"] = "tampered"
    packet["diagnostics"]["pressure"] = "tampered"

    packet["diagnostics"]["trigger"]["event"] = (
        "tampered"
    )

    fresh = api.get_relationship(
        "player",
        "merchant",
    )

    assert fresh["trigger"]["event"] == (
        "relationship_broken"
    )

    assert fresh["diagnostics"]["pressure"] == (
        "relationship_broken"
    )

    assert fresh["diagnostics"]["trigger"]["event"] == (
        "relationship_broken"
    )

    raw_packet = api.engine.relationships.get(
        "player",
        "merchant",
    )

    raw_packet["diagnostics"]["pressure"] = (
        "tampered"
    )

    fresh_raw = api.engine.relationships.get(
        "player",
        "merchant",
    )

    assert fresh_raw["diagnostics"]["pressure"] == (
        "relationship_broken"
    )


def test_relationship_tick_packet_is_deep_copied_v180():
    api = GhostAPI()

    api.apply_event(
        "player",
        "merchant",
        {"type": "betrayal"},
    )

    tick_packet = api.tick()

    tick_relationship = tick_packet[
        "relationships"
    ][0]

    original_pressure = tick_relationship[
        "diagnostics"
    ]["pressure"]

    tick_relationship[
        "diagnostics"
    ]["pressure"] = "tampered"

    fresh = api.get_relationship(
        "player",
        "merchant",
    )

    assert fresh["diagnostics"]["pressure"] == (
        original_pressure
    )


def test_social_propagation_packets_and_log_are_isolated_v180():
    api = GhostAPI()

    packet = api.propagate_social_event(
        source="player",
        target="merchant",
        event="betrayal",
        observers=["guard"],
    )

    original_fear_delta = packet[
        "world_effects"
    ]["fear_delta"]

    packet["direct"]["diagnostics"]["pressure"] = (
        "tampered"
    )

    packet["propagated"][0]["relationship"][
        "diagnostics"
    ]["pressure"] = "tampered"

    packet["world_effects"]["fear_delta"] = 99.0

    first_log = (
        api.engine.relationships.propagation_log()
    )

    assert first_log[0]["direct"]["diagnostics"][
        "pressure"
    ] == "relationship_broken"

    assert first_log[0]["propagated"][0][
        "relationship"
    ]["diagnostics"]["pressure"] != "tampered"

    assert first_log[0]["world_effects"][
        "fear_delta"
    ] == original_fear_delta

    first_log[0]["world_effects"][
        "fear_delta"
    ] = 77.0

    second_log = (
        api.engine.relationships.propagation_log()
    )

    assert second_log[0]["world_effects"][
        "fear_delta"
    ] == original_fear_delta


def test_world_event_inputs_and_outputs_are_deep_copied_v180():
    api = GhostAPI()

    details = {
        "nested": {
            "value": 1,
        },
    }

    returned = api.record_world_event(
        "raid",
        actor="player",
        target="millcross",
        details=details,
    )

    details["nested"]["value"] = 2

    returned["details"]["nested"][
        "value"
    ] = 3

    fresh = api.world_state()

    assert fresh["events"][0]["details"][
        "nested"
    ]["value"] == 1

    fresh["events"][0]["details"][
        "nested"
    ]["value"] = 4

    second = api.world_state()

    assert second["events"][0]["details"][
        "nested"
    ]["value"] == 1

    snapshot = api.snapshot()

    snapshot["world"]["events"][0][
        "details"
    ]["nested"]["value"] = 5

    assert api.snapshot()["world"]["events"][0][
        "details"
    ]["nested"]["value"] == 1


def test_world_restore_copies_nested_event_payloads_v180():
    payload = {
        "mood": {
            "fear": 0.0,
            "order": 0.5,
            "commerce": 1.0,
            "resentment": 0.0,
        },
        "events": [
            {
                "type": "raid",
                "actor": "player",
                "target": "millcross",
                "details": {
                    "nested": {
                        "value": 1,
                    },
                },
            },
        ],
        "global_pressure": 0.0,
        "status": "normal",
    }

    runtime = WorldRuntime.from_dict(
        payload
    )

    payload["events"][0]["details"][
        "nested"
    ]["value"] = 9

    assert runtime.to_dict()["events"][0][
        "details"
    ]["nested"]["value"] == 1
