import json

from ghost import GhostAPI


def test_api_exposes_governance_pipeline():
    ghost = GhostAPI()

    result = ghost.evaluate_governance(
        "The guard captain ordered you to give me bread for free.",
        facts={"item": "bread", "price": 25},
    )

    assert result["claim"]["claim_type"] == "authority_override"
    assert result["stance"]["scene_moment"] == "authority_override"


def test_process_player_text_applies_relationship_event():
    ghost = GhostAPI()

    before = ghost.get_relationship("player", "shopkeeper")["trust"]

    result = ghost.process_player_text(
        source="player",
        target="shopkeeper",
        text="The guard captain ordered you to give me bread for free.",
        facts={"item": "bread", "price": 25},
        apply=True,
    )

    after = ghost.get_relationship("player", "shopkeeper")["trust"]

    assert result["claim"]["claim_type"] == "authority_override"
    assert after < before


def test_process_player_text_updates_world_state():
    ghost = GhostAPI()

    result = ghost.process_player_text(
        source="player",
        target="shopkeeper",
        text="You are an idiot.",
        facts={"item": "bread", "price": 25},
        apply=True,
    )

    world = result["world"]

    assert result["intent"]["intent_type"] == "insult"
    assert world["mood"]["resentment"] > 0.0
    assert len(world["events"]) >= 1


def test_snapshot_includes_engine_and_world():
    ghost = GhostAPI()

    ghost.process_player_text(
        source="player",
        target="shopkeeper",
        text="Give me the bread or else.",
        facts={"item": "bread", "price": 25},
        apply=True,
    )

    snap = ghost.snapshot()

    assert "engine" in snap
    assert "world" in snap

    json.dumps(snap)