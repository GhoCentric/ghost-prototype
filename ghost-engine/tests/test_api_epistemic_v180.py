from copy import deepcopy
import json

import pytest

from ghost import GhostAPI


def _seed_api():
    api = GhostAPI()

    fact = api.record_fact(
        fact_id="millcross_food_001",
        source="game_rule",
        subject="royal_guard",
        predicate="confiscated",
        object="millcross_food",
        attributes={"quantity": 6},
    )

    observation = api.observe(
        observer="villager_3",
        kind="visual",
        visible_features=[
            "royal_guards",
            "food_carts",
        ],
        reliability=0.65,
        subject="millcross_food_loss",
        provenance={"location": "millcross_market"},
    )

    belief = api.evaluate_beliefs(
        holder="villager_3",
        subject="millcross_food_loss",
        candidates={
            "cause": {
                "royal_confiscation": 0.60,
                "unknown": 0.40,
            },
        },
        report_quality={
            "direct_observation": 0.65,
            "exaggeration_likely": 0.42,
        },
        evidence_ids=[observation["id"]],
    )

    return api, fact, observation, belief


def test_api_exposes_epistemic_public_methods_v180():
    api, fact, observation, belief = _seed_api()

    assert api.get_fact(fact["fact_id"]) == fact
    assert api.get_belief(
        "villager_3",
        "millcross_food_loss",
    ) == belief

    report = api.report(
        speaker="villager_3",
        audience="player",
        claim={
            "cause": "royal_confiscation",
            "quantity": "everything",
        },
        confidence=0.68,
        source_belief_id=belief["id"],
    )

    assert report["kind"] == "report"
    assert api.get_belief(
        "player",
        "millcross_food_loss",
    ) is None

    propagated = api.propagate_belief(
        speaker="villager_3",
        audience="merchant",
        belief_id=belief["id"],
    )

    assert propagated["kind"] == "report"
    assert propagated["source_belief_id"] == belief["id"]
    assert api.get_belief(
        "merchant",
        "millcross_food_loss",
    ) is None

    evidence = api.add_evidence(
        evidence_type="market_inventory_check",
        source="merchant_ledger",
        subject="millcross_food_loss",
        available_to="villager_3",
        supports={
            "cause": {
                "royal_confiscation": 0.20,
            },
        },
    )

    revised = api.evaluate_beliefs(
        holder="villager_3",
        subject="millcross_food_loss",
        previous_belief_id=belief["id"],
        evidence_ids=[evidence["id"]],
    )

    assert revised["previous_belief_id"] == belief["id"]
    assert revised["dimensions"]["cause"][
        "dominant_candidate"
    ] == "royal_confiscation"

    belief_before_tick = deepcopy(revised)
    fact_before_tick = deepcopy(
        api.get_fact("millcross_food_001")
    )

    packet = api.tick()

    assert packet["event"] == "tick"
    assert packet["epistemic"]["kind"] == "tick"
    assert packet["epistemic"]["tick"] == 1
    assert api.get_belief(
        "villager_3",
        "millcross_food_loss",
    ) == belief_before_tick
    assert api.get_fact(
        "millcross_food_001",
    ) == fact_before_tick

    json.dumps(packet, allow_nan=False, sort_keys=True)


def test_api_epistemic_snapshot_restore_and_legacy_v180():
    source, _, _, _ = _seed_api()

    snapshot = source.snapshot()

    assert "epistemic" in snapshot
    assert snapshot["epistemic"]["records"]

    restored = GhostAPI.from_snapshot(snapshot)

    assert restored.snapshot() == snapshot

    snapshot["epistemic"]["records"][0][
        "attributes"
    ]["quantity"] = 999

    assert source.get_fact(
        "millcross_food_001",
    )["attributes"]["quantity"] == 6
    assert restored.get_fact(
        "millcross_food_001",
    )["attributes"]["quantity"] == 6

    clean_snapshot = source.snapshot()

    target = GhostAPI()
    restored_snapshot = target.restore_snapshot(clean_snapshot)

    assert restored_snapshot == clean_snapshot
    assert target.snapshot() == clean_snapshot

    legacy_snapshot = deepcopy(clean_snapshot)
    legacy_snapshot.pop("epistemic")

    legacy = GhostAPI.from_snapshot(legacy_snapshot)

    assert legacy.snapshot()["epistemic"]["records"] == []
    assert legacy.snapshot()["epistemic"]["tick"] == 0

    invalid_type = deepcopy(clean_snapshot)
    invalid_type["epistemic"] = []

    with pytest.raises(
        ValueError,
        match="snapshot epistemic must be a dict",
    ):
        GhostAPI.from_snapshot(invalid_type)

    invalid_runtime = deepcopy(clean_snapshot)
    invalid_runtime["epistemic"]["schema_version"] = "bad"

    with pytest.raises(
        ValueError,
        match="unsupported epistemic",
    ):
        GhostAPI.from_snapshot(invalid_runtime)


def test_api_epistemic_restore_replays_deterministically_v180():
    original, _, _, _ = _seed_api()
    restored = GhostAPI.from_snapshot(
        deepcopy(original.snapshot())
    )

    for api in (original, restored):
        current = api.get_belief(
            "villager_3",
            "millcross_food_loss",
        )

        evidence = api.add_evidence(
            evidence_type="guard_testimony",
            source="guard_1",
            subject="millcross_food_loss",
            available_to="villager_3",
            contradicts={
                "cause": {
                    "royal_confiscation": 0.10,
                },
            },
        )

        revised = api.evaluate_beliefs(
            holder="villager_3",
            subject="millcross_food_loss",
            previous_belief_id=current["id"],
            evidence_ids=[evidence["id"]],
        )

        packet = api.tick()

        assert revised["previous_belief_id"] == current["id"]
        assert packet["epistemic"]["tick"] == 1

    assert original.snapshot() == restored.snapshot()

