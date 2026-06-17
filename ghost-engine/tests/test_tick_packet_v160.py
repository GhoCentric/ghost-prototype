import json
from typing import Any, Dict, cast

from ghost.engine import GhostEngine


Packet = Dict[str, Any]


def tick(engine: GhostEngine) -> Packet:
    run_tick = getattr(
        engine,
        "tick",
    )

    return cast(Packet, run_tick())


def item(obj: Any, key: str) -> Any:
    return obj[key]


def test_tick_returns_public_packet():
    g = GhostEngine()

    g.apply_event("player", "npc", "betrayal")

    packet = tick(g)

    assert item(packet, "event") == "tick"

    relationships = item(packet, "relationships")
    assert len(relationships) == 1

    rel = relationships[0]
    diagnostics = item(rel, "diagnostics")

    assert item(rel, "a") in ("npc", "player")
    assert item(rel, "b") in ("npc", "player")
    assert item(diagnostics, "event") == "tick"
    assert item(diagnostics, "channel") == "decay"

    json.dumps(packet)


def test_tick_packet_matches_relationship_readback():
    g = GhostEngine()

    g.apply_event("player", "npc", "betrayal")

    packet = tick(g)
    rel = g.get_relationship("player", "npc")

    relationships = item(packet, "relationships")
    tick_rel = relationships[0]

    tick_diagnostics = item(tick_rel, "diagnostics")
    rel_diagnostics = item(rel, "diagnostics")

    assert item(tick_rel, "trust") == item(rel, "trust")
    assert item(tick_rel, "state") == item(rel, "state")
    assert item(tick_diagnostics, "pressure") == item(
        rel_diagnostics,
        "pressure",
    )
