from copy import deepcopy
import json

import pytest

from ghost.epistemic import EpistemicRuntime


def _villager_belief(runtime):
    observation = runtime.observe(
        observer="villager_3",
        kind="visual",
        visible_features=[
            "royal_guards",
            "food_carts",
            "guards_departing",
        ],
        reliability=0.65,
        subject="millcross_food_loss",
        provenance={
            "location": "millcross_market",
            "witness_distance": "near",
        },
    )

    belief = runtime.evaluate_beliefs(
        holder="villager_3",
        subject="millcross_food_loss",
        candidates={
            "cause": {
                "royal_confiscation": 0.60,
                "rebel_theft": 0.10,
                "merchant_hoarding": 0.05,
                "unknown": 0.25,
            },
            "quantity": {
                "all_food_taken": 0.18,
                "some_food_taken": 0.76,
                "quantity_unknown": 0.06,
            },
        },
        report_quality={
            "direct_observation": 0.65,
            "exaggeration_likely": 0.42,
            "rumor_repetition_likely": 0.20,
            "deception_likely": 0.03,
        },
        evidence_ids=[observation["id"]],
    )

    return observation, belief


def test_fact_is_objective_and_does_not_create_belief():
    runtime = EpistemicRuntime()

    fact = runtime.record_fact(
        fact_id="millcross_food_001",
        source="game_rule",
        subject="royal_guard",
        predicate="confiscated",
        object="millcross_food",
        attributes={
            "quantity": 6,
            "route": ("market", "gate"),
        },
    )

    assert fact["kind"] == "fact"
    assert fact["attributes"] == {
        "quantity": 6,
        "route": ["market", "gate"],
    }
    assert runtime.get_belief(
        "villager_3",
        "millcross_food_loss",
    ) is None

    copied_fact = runtime.get_fact("millcross_food_001")
    copied_fact["attributes"]["quantity"] = 0

    assert runtime.get_fact(
        "millcross_food_001",
    )["attributes"]["quantity"] == 6
    assert runtime.get_fact("missing_fact") is None


def test_observation_is_actor_owned_and_does_not_infer_cause():
    runtime = EpistemicRuntime()

    observation = runtime.observe(
        observer="villager_3",
        kind="visual",
        visible_features=[
            "royal_guards",
            "food_carts",
            "guards_departing",
        ],
        reliability=0.65,
        subject="millcross_food_loss",
        provenance={"location": "millcross_market"},
    )

    assert observation["kind"] == "observation"
    assert observation["observer"] == "villager_3"
    assert observation["subject"] == "millcross_food_loss"
    assert observation["visible_features"] == [
        "royal_guards",
        "food_carts",
        "guards_departing",
    ]
    assert runtime.get_belief(
        "villager_3",
        "millcross_food_loss",
    ) is None

    observation["visible_features"].append("invented_feature")

    assert runtime.records()[0]["visible_features"] == [
        "royal_guards",
        "food_carts",
        "guards_departing",
    ]


def test_report_is_claim_not_fact_or_automatic_listener_belief():
    runtime = EpistemicRuntime()

    report = runtime.report(
        speaker="villager_3",
        audience="player",
        claim={
            "cause": "royal_confiscation",
            "quantity": "everything",
        },
        confidence=0.68,
        provenance={
            "statement": "They took everything.",
            "source_type": "direct_observation",
        },
    )

    assert report["kind"] == "report"
    assert report["audience"] == ["player"]
    assert report["claim"]["quantity"] == "everything"
    assert runtime.get_fact("millcross_food_001") is None
    assert runtime.get_belief(
        "player",
        "millcross_food_loss",
    ) is None


def test_belief_keeps_cause_quantity_and_quality_separate():
    runtime = EpistemicRuntime()
    observation, belief = _villager_belief(runtime)

    cause = belief["dimensions"]["cause"]
    quantity = belief["dimensions"]["quantity"]

    assert belief["kind"] == "belief"
    assert belief["holder"] == "villager_3"
    assert belief["evidence_ids"] == [observation["id"]]

    assert cause["dominant_candidate"] == "royal_confiscation"
    assert cause["confidence"] == pytest.approx(0.60)

    assert quantity["dominant_candidate"] == "some_food_taken"
    assert quantity["confidence"] == pytest.approx(0.76)

    assert belief["report_quality"]["direct_observation"] == (
        pytest.approx(0.65)
    )
    assert belief["report_quality"]["exaggeration_likely"] == (
        pytest.approx(0.42)
    )

    copied_belief = runtime.get_belief(
        "villager_3",
        "millcross_food_loss",
    )
    copied_belief["dimensions"]["cause"]["confidence"] = 0.0

    assert runtime.get_belief(
        "villager_3",
        "millcross_food_loss",
    )["dimensions"]["cause"]["confidence"] == pytest.approx(0.60)


def test_hidden_evidence_cannot_revise_belief():
    runtime = EpistemicRuntime()
    _, belief = _villager_belief(runtime)

    hidden_evidence = runtime.add_evidence(
        evidence_type="market_inventory_check",
        source="merchant_ledger",
        subject="millcross_food_loss",
        supports={
            "cause": {
                "royal_confiscation": 0.10,
            },
        },
    )

    with pytest.raises(ValueError, match="cannot access"):
        runtime.evaluate_beliefs(
            holder="villager_3",
            subject="millcross_food_loss",
            previous_belief_id=belief["id"],
            evidence_ids=[hidden_evidence["id"]],
        )


def test_evidence_revises_belief_without_erasing_history():
    runtime = EpistemicRuntime()
    observation, original = _villager_belief(runtime)

    evidence = runtime.add_evidence(
        evidence_type="market_inventory_check",
        source="merchant_ledger",
        subject="millcross_food_loss",
        available_to=["villager_3"],
        supports={
            "cause": {
                "royal_confiscation": 0.30,
            },
            "quantity": {
                "some_food_taken": 0.50,
            },
            "report_quality": {
                "exaggeration_likely": 0.20,
            },
        },
        contradicts={
            "cause": {
                "merchant_hoarding": 0.40,
            },
            "quantity": {
                "all_food_taken": 0.65,
            },
            "report_quality": {
                "direct_observation": 0.10,
            },
        },
    )

    revised = runtime.evaluate_beliefs(
        holder="villager_3",
        subject="millcross_food_loss",
        previous_belief_id=original["id"],
        evidence_ids=[evidence["id"]],
    )

    cause = revised["dimensions"]["cause"]
    quantity = revised["dimensions"]["quantity"]

    assert revised["previous_belief_id"] == original["id"]
    assert revised["evidence_ids"] == [
        observation["id"],
        evidence["id"],
    ]

    assert cause["dominant_candidate"] == "royal_confiscation"
    assert cause["confidence"] == pytest.approx(0.72)
    assert cause["candidates"]["merchant_hoarding"] == (
        pytest.approx(0.0)
    )

    assert quantity["dominant_candidate"] == "some_food_taken"
    assert quantity["confidence"] == pytest.approx(
        1.26 / 1.32
    )

    assert revised["report_quality"]["direct_observation"] == (
        pytest.approx(0.55)
    )
    assert revised["report_quality"]["exaggeration_likely"] == (
        pytest.approx(0.62)
    )

    history = runtime.records()

    assert [record["kind"] for record in history] == [
        "observation",
        "belief",
        "evidence",
        "belief",
    ]
    assert history[1]["id"] == original["id"]
    assert history[3]["id"] == revised["id"]


def test_observation_and_report_access_are_actor_limited():
    runtime = EpistemicRuntime()

    observation = runtime.observe(
        observer="witness_1",
        kind="visual",
        visible_features=["carts"],
        reliability=0.80,
        subject="market_loss",
    )

    with pytest.raises(ValueError, match="cannot access"):
        runtime.evaluate_beliefs(
            holder="merchant",
            subject="market_loss",
            candidates={"unknown": 1.0},
            evidence_ids=[observation["id"]],
        )

    report = runtime.report(
        speaker="witness_1",
        audience=("merchant", "captain"),
        claim={"cause": "royal_confiscation"},
        confidence=0.50,
    )

    merchant_belief = runtime.evaluate_beliefs(
        holder="merchant",
        subject="market_loss",
        candidates={"unknown": 1.0},
        evidence_ids=[report["id"]],
    )

    assert merchant_belief["evidence_ids"] == [report["id"]]

    with pytest.raises(ValueError, match="cannot access"):
        runtime.evaluate_beliefs(
            holder="outsider",
            subject="market_loss",
            candidates={"unknown": 1.0},
            evidence_ids=[report["id"]],
        )


def test_report_source_belief_must_exist_and_belong_to_speaker():
    runtime = EpistemicRuntime()
    _, belief = _villager_belief(runtime)

    with pytest.raises(ValueError, match="does not exist"):
        runtime.report(
            speaker="villager_3",
            audience="player",
            claim={},
            confidence=0.50,
            source_belief_id="missing_belief",
        )

    with pytest.raises(ValueError, match="must own"):
        runtime.report(
            speaker="merchant",
            audience="player",
            claim={},
            confidence=0.50,
            source_belief_id=belief["id"],
        )


def test_propagated_belief_becomes_report_not_listener_belief():
    runtime = EpistemicRuntime()
    _, belief = _villager_belief(runtime)

    report = runtime.propagate_belief(
        speaker="villager_3",
        audience={"player", "merchant"},
        belief_id=belief["id"],
    )

    assert report["kind"] == "report"
    assert report["source_belief_id"] == belief["id"]
    assert report["confidence"] == pytest.approx(0.76)
    assert report["claim"]["subject"] == "millcross_food_loss"

    assert runtime.get_belief(
        "player",
        "millcross_food_loss",
    ) is None

    explicit = runtime.propagate_belief(
        speaker="villager_3",
        audience="player",
        belief_id=belief["id"],
        confidence=0.33,
    )

    assert explicit["confidence"] == pytest.approx(0.33)

    with pytest.raises(ValueError, match="must own"):
        runtime.propagate_belief(
            speaker="merchant",
            audience="player",
            belief_id=belief["id"],
        )

    with pytest.raises(ValueError, match="does not exist"):
        runtime.propagate_belief(
            speaker="villager_3",
            audience="player",
            belief_id="missing_belief",
        )


def test_flat_candidates_use_default_dimension_and_revise():
    runtime = EpistemicRuntime()

    initial = runtime.evaluate_beliefs(
        holder="player",
        subject="castle_gate",
        candidates={
            "open": 0.40,
            "closed": 0.60,
        },
    )

    assert initial["dimensions"]["default"]["dominant_candidate"] == (
        "closed"
    )

    evidence = runtime.add_evidence(
        evidence_type="gate_inspection",
        source="guard",
        subject="castle_gate",
        available_to="player",
        supports={"open": 0.50},
    )

    revised = runtime.evaluate_beliefs(
        holder="player",
        subject="castle_gate",
        previous_belief_id=initial["id"],
        evidence_ids=[evidence["id"]],
    )

    assert revised["dimensions"]["default"]["dominant_candidate"] == (
        "open"
    )
    assert revised["dimensions"]["default"]["confidence"] == (
        pytest.approx(0.60)
    )

    with pytest.raises(ValueError, match="report_quality is independent"):
        runtime.evaluate_beliefs(
            holder="player",
            subject="castle_gate",
            candidates={
                "report_quality": {
                    "direct_observation": 0.50,
                },
            },
        )


def test_evidence_subject_dimension_and_candidate_must_match():
    runtime = EpistemicRuntime()

    initial = runtime.evaluate_beliefs(
        holder="player",
        subject="food_loss",
        candidates={
            "cause": {
                "guards": 0.50,
                "rebels": 0.50,
            },
        },
    )

    foreign_subject = runtime.add_evidence(
        evidence_type="other_ledger",
        source="merchant",
        subject="other_subject",
        available_to="player",
        supports={
            "cause": {
                "guards": 0.10,
            },
        },
    )

    with pytest.raises(ValueError, match="subject does not match"):
        runtime.evaluate_beliefs(
            holder="player",
            subject="food_loss",
            previous_belief_id=initial["id"],
            evidence_ids=[foreign_subject["id"]],
        )

    wrong_dimension = runtime.add_evidence(
        evidence_type="quantity_ledger",
        source="merchant",
        subject="food_loss",
        available_to="player",
        supports={
            "quantity": {
                "some_taken": 0.10,
            },
        },
    )

    with pytest.raises(ValueError, match="dimension is absent"):
        runtime.evaluate_beliefs(
            holder="player",
            subject="food_loss",
            previous_belief_id=initial["id"],
            evidence_ids=[wrong_dimension["id"]],
        )

    wrong_candidate = runtime.add_evidence(
        evidence_type="wrong_candidate",
        source="merchant",
        subject="food_loss",
        available_to="player",
        supports={
            "cause": {
                "merchant": 0.10,
            },
        },
    )

    with pytest.raises(ValueError, match="candidate is absent"):
        runtime.evaluate_beliefs(
            holder="player",
            subject="food_loss",
            previous_belief_id=initial["id"],
            evidence_ids=[wrong_candidate["id"]],
        )


def test_evidence_cannot_remove_every_candidate_weight():
    runtime = EpistemicRuntime()

    initial = runtime.evaluate_beliefs(
        holder="player",
        subject="gate_status",
        candidates={
            "cause": {
                "guards": 1.0,
            },
        },
    )

    evidence = runtime.add_evidence(
        evidence_type="contradiction",
        source="ledger",
        subject="gate_status",
        available_to="player",
        contradicts={
            "cause": {
                "guards": 1.0,
            },
        },
    )

    with pytest.raises(ValueError, match="removed all candidate weight"):
        runtime.evaluate_beliefs(
            holder="player",
            subject="gate_status",
            previous_belief_id=initial["id"],
            evidence_ids=[evidence["id"]],
        )

    with pytest.raises(ValueError, match="positive total weight"):
        runtime.evaluate_beliefs(
            holder="player",
            subject="empty",
            candidates={"unknown": 0.0},
        )

    with pytest.raises(ValueError, match="non-negative"):
        runtime.add_evidence(
            evidence_type="bad_weight",
            source="ledger",
            supports={
                "cause": {
                    "guards": -0.10,
                },
            },
        )


def test_ticks_and_fact_revisions_are_append_only_and_json_safe():
    runtime = EpistemicRuntime()

    first = runtime.record_fact(
        fact_id="market_stock",
        source="ledger",
        subject="merchant",
        predicate="has",
        object="food",
        attributes={"quantity": 12},
    )

    tick = runtime.tick()

    second = runtime.record_fact(
        fact_id="market_stock",
        source="ledger",
        subject="merchant",
        predicate="has",
        object="food",
        attributes={"quantity": 6},
    )

    records = runtime.records()

    assert first["id"] == "epistemic_000001"
    assert tick["id"] == "epistemic_000002"
    assert tick["tick"] == 1
    assert second["id"] == "epistemic_000003"

    assert runtime.get_fact(
        "market_stock",
    )["attributes"]["quantity"] == 6

    assert [record["kind"] for record in records] == [
        "fact",
        "tick",
        "fact",
    ]

    records[0]["attributes"]["quantity"] = 999

    assert runtime.records()[0]["attributes"]["quantity"] == 12
    json.dumps(runtime.records(), sort_keys=True)


def test_invalid_inputs_and_revision_rules_fail_cleanly():
    runtime = EpistemicRuntime()

    with pytest.raises(ValueError, match="JSON-safe"):
        runtime.record_fact(
            fact_id="bad",
            source="world",
            subject="guard",
            predicate="has",
            object="food",
            attributes={"bad": {1, 2}},
        )

    with pytest.raises(ValueError, match="must not be empty"):
        runtime.observe(
            observer="villager",
            kind="visual",
            visible_features=[],
            reliability=0.50,
        )

    with pytest.raises(ValueError, match="must be a number"):
        runtime.observe(
            observer="villager",
            kind="visual",
            visible_features=["cart"],
            reliability=True,
        )

    with pytest.raises(ValueError, match="audience must not be empty"):
        runtime.report(
            speaker="villager",
            audience=[],
            claim={},
            confidence=0.50,
        )

    with pytest.raises(ValueError, match="claim must be a dict"):
        runtime.report(
            speaker="villager",
            audience="player",
            claim=[],
            confidence=0.50,
        )

    with pytest.raises(ValueError, match="availability"):
        runtime.add_evidence(
            evidence_type="bad_availability",
            source="ledger",
            available_to=123,
        )

    initial = runtime.evaluate_beliefs(
        holder="player",
        subject="gate",
        candidates={"open": 1.0},
    )

    with pytest.raises(ValueError, match="does not exist"):
        runtime.evaluate_beliefs(
            holder="player",
            subject="gate",
            previous_belief_id="missing_belief",
        )

    with pytest.raises(ValueError, match="revisions use"):
        runtime.evaluate_beliefs(
            holder="player",
            subject="gate",
            candidates={"open": 1.0},
            previous_belief_id=initial["id"],
        )

    with pytest.raises(ValueError, match="holder does not match"):
        runtime.evaluate_beliefs(
            holder="merchant",
            subject="gate",
            previous_belief_id=initial["id"],
        )

    with pytest.raises(ValueError, match="subject does not match"):
        runtime.evaluate_beliefs(
            holder="player",
            subject="other_gate",
            previous_belief_id=initial["id"],
        )
def test_epistemic_coverage_branch_gaps_v180():
    runtime = EpistemicRuntime()

    with pytest.raises(ValueError, match="non-empty string"):
        runtime.record_fact(
            fact_id="",
            source="world",
            subject="guard",
            predicate="has",
            object="food",
        )

    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        runtime.observe(
            observer="villager",
            kind="visual",
            visible_features=["cart"],
            reliability=1.01,
        )

    with pytest.raises(ValueError, match="must be a number"):
        runtime.add_evidence(
            evidence_type="bad_weight_type",
            source="ledger",
            supports={
                "cause": {
                    "guards": "high",
                },
            },
        )

    with pytest.raises(ValueError, match="list or tuple"):
        runtime.evaluate_beliefs(
            holder="player",
            subject="gate",
            candidates={"open": 1.0},
            evidence_ids="not_a_list",
        )

    with pytest.raises(ValueError, match="must be a dict"):
        runtime.evaluate_beliefs(
            holder="player",
            subject="gate",
            candidates=[],
        )

    with pytest.raises(ValueError, match="must not be empty"):
        runtime.evaluate_beliefs(
            holder="player",
            subject="gate",
            candidates={},
        )

    with pytest.raises(ValueError, match="non-empty dict"):
        runtime.evaluate_beliefs(
            holder="player",
            subject="gate",
            candidates={
                "cause": {},
            },
        )

    with pytest.raises(ValueError, match="dict or None"):
        runtime.evaluate_beliefs(
            holder="player",
            subject="gate",
            candidates={"open": 1.0},
            report_quality=[],
        )

    with pytest.raises(ValueError, match="dict or None"):
        runtime.add_evidence(
            evidence_type="bad_support_shape",
            source="ledger",
            supports=[],
        )

    empty_evidence = runtime.add_evidence(
        evidence_type="empty_adjustments",
        source="ledger",
        supports={},
        contradicts={},
    )

    assert empty_evidence["supports"] == {
        "dimensions": {},
        "report_quality": {},
    }
    assert empty_evidence["contradicts"] == {
        "dimensions": {},
        "report_quality": {},
    }

    duplicate_report = runtime.report(
        speaker="witness",
        audience=["player", "player"],
        claim={},
        confidence=0.50,
    )

    assert duplicate_report["audience"] == ["player"]

    duplicate_belief = runtime.evaluate_beliefs(
        holder="player",
        subject="market_loss",
        candidates={"unknown": 1.0},
        evidence_ids=[
            duplicate_report["id"],
            duplicate_report["id"],
        ],
    )

    assert duplicate_belief["evidence_ids"] == [
        duplicate_report["id"],
    ]


def test_epistemic_metadata_validation_coverage_v180():
    runtime = EpistemicRuntime()

    with pytest.raises(ValueError, match="fact attributes"):
        runtime.record_fact(
            fact_id="bad_fact",
            source="world",
            subject="guard",
            predicate="has",
            object="food",
            attributes=[],
        )

    with pytest.raises(ValueError, match="list or tuple"):
        runtime.observe(
            observer="villager",
            kind="visual",
            visible_features="cart",
            reliability=0.50,
        )

    with pytest.raises(ValueError, match="observation provenance"):
        runtime.observe(
            observer="villager",
            kind="visual",
            visible_features=["cart"],
            reliability=0.50,
            provenance=[],
        )

    with pytest.raises(ValueError, match="report provenance"):
        runtime.report(
            speaker="villager",
            audience="player",
            claim={},
            confidence=0.50,
            provenance=[],
        )

    with pytest.raises(ValueError, match="evidence provenance"):
        runtime.add_evidence(
            evidence_type="ledger",
            source="merchant",
            provenance=[],
        )

    with pytest.raises(ValueError, match="belief provenance"):
        runtime.evaluate_beliefs(
            holder="player",
            subject="gate",
            candidates={"open": 1.0},
            provenance=[],
        )


def test_epistemic_missing_record_and_quality_paths_v180():
    runtime = EpistemicRuntime()

    assert runtime._available_to(
        {"kind": "fact"},
        "player",
    ) is False

    with pytest.raises(ValueError, match="unknown epistemic record"):
        runtime.evaluate_beliefs(
            holder="player",
            subject="gate",
            candidates={"open": 1.0},
            evidence_ids=["missing_record"],
        )

    fact = runtime.record_fact(
        fact_id="gate_truth",
        source="world",
        subject="castle_gate",
        predicate="is",
        object="closed",
    )

    with pytest.raises(ValueError, match="must reference"):
        runtime.evaluate_beliefs(
            holder="player",
            subject="gate",
            candidates={"open": 1.0},
            evidence_ids=[fact["id"]],
        )

    original = runtime.evaluate_beliefs(
        holder="player",
        subject="gate",
        candidates={
            "open": 0.50,
            "closed": 0.50,
        },
        report_quality={
            "direct_observation": 0.50,
        },
    )

    unknown_quality = runtime.add_evidence(
        evidence_type="quality_check",
        source="ledger",
        subject="gate",
        available_to="player",
        supports={
            "report_quality": {
                "exaggeration_likely": 0.10,
            },
        },
    )

    with pytest.raises(ValueError, match="signal is absent"):
        runtime.evaluate_beliefs(
            holder="player",
            subject="gate",
            previous_belief_id=original["id"],
            evidence_ids=[unknown_quality["id"]],
        )

    with pytest.raises(
        ValueError,
        match="new beliefs require candidate weights",
    ):
        runtime.evaluate_beliefs(
            holder="player",
            subject="missing_candidates",
        )

def _snapshot_runtime():
    runtime = EpistemicRuntime()

    runtime.record_fact(
        fact_id="millcross_food_001",
        source="game_rule",
        subject="royal_guard",
        predicate="confiscated",
        object="millcross_food",
        attributes={"quantity": 6},
    )

    observation = runtime.observe(
        observer="villager_3",
        kind="visual",
        visible_features=[
            "royal_guards",
            "food_carts",
        ],
        reliability=0.65,
        subject="millcross_food_loss",
    )

    original = runtime.evaluate_beliefs(
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

    runtime.propagate_belief(
        speaker="villager_3",
        audience="player",
        belief_id=original["id"],
    )

    evidence = runtime.add_evidence(
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

    runtime.evaluate_beliefs(
        holder="villager_3",
        subject="millcross_food_loss",
        previous_belief_id=original["id"],
        evidence_ids=[evidence["id"]],
    )

    runtime.tick()

    return runtime


def test_epistemic_snapshot_round_trip_preserves_ledger_v180():
    source = _snapshot_runtime()
    snapshot = source.snapshot()
    restored = EpistemicRuntime.from_snapshot(snapshot)

    assert snapshot["schema_version"] == "1.0"
    assert snapshot["sequence"] == len(snapshot["records"])
    assert snapshot["tick"] == 1
    assert restored.snapshot() == snapshot

    assert restored.get_fact(
        "millcross_food_001",
    )["attributes"]["quantity"] == 6

    assert restored.get_belief(
        "villager_3",
        "millcross_food_loss",
    ) == source.get_belief(
        "villager_3",
        "millcross_food_loss",
    )

    json.dumps(snapshot, allow_nan=False, sort_keys=True)

    snapshot["records"][0]["attributes"]["quantity"] = 999

    assert source.get_fact(
        "millcross_food_001",
    )["attributes"]["quantity"] == 6
    assert restored.get_fact(
        "millcross_food_001",
    )["attributes"]["quantity"] == 6


def test_epistemic_snapshot_restores_deterministic_continuation_v180():
    original = _snapshot_runtime()
    restored = EpistemicRuntime.from_snapshot(
        deepcopy(original.snapshot())
    )

    for runtime in (original, restored):
        current = runtime.get_belief(
            "villager_3",
            "millcross_food_loss",
        )
        evidence = runtime.add_evidence(
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
        revised = runtime.evaluate_beliefs(
            holder="villager_3",
            subject="millcross_food_loss",
            previous_belief_id=current["id"],
            evidence_ids=[evidence["id"]],
        )
        tick = runtime.tick()

        assert revised["previous_belief_id"] == current["id"]
        assert tick["tick"] == 2

    assert original.snapshot() == restored.snapshot()


def test_epistemic_snapshot_rejects_invalid_top_level_packets_v180():
    empty = EpistemicRuntime.from_snapshot(
        EpistemicRuntime().snapshot()
    )

    assert empty.records() == []

    with pytest.raises(ValueError, match="must be a dict"):
        EpistemicRuntime.from_snapshot([])

    bad_keys = EpistemicRuntime().snapshot()
    bad_keys.pop("records")

    with pytest.raises(ValueError, match="unsupported keys"):
        EpistemicRuntime.from_snapshot(bad_keys)

    bad_schema = EpistemicRuntime().snapshot()
    bad_schema["schema_version"] = "not-supported"

    with pytest.raises(ValueError, match="unsupported epistemic"):
        EpistemicRuntime.from_snapshot(bad_schema)

    bad_tick = EpistemicRuntime().snapshot()
    bad_tick["tick"] = True

    with pytest.raises(ValueError, match="non-negative integer"):
        EpistemicRuntime.from_snapshot(bad_tick)

    bad_sequence = EpistemicRuntime().snapshot()
    bad_sequence["sequence"] = -1

    with pytest.raises(ValueError, match="non-negative integer"):
        EpistemicRuntime.from_snapshot(bad_sequence)

    bad_records = EpistemicRuntime().snapshot()
    bad_records["records"] = {}

    with pytest.raises(ValueError, match="records must be a list"):
        EpistemicRuntime.from_snapshot(bad_records)

    mismatch = EpistemicRuntime().snapshot()
    mismatch["sequence"] = 1

    with pytest.raises(ValueError, match="sequence must match"):
        EpistemicRuntime.from_snapshot(mismatch)


def test_epistemic_snapshot_rejects_invalid_ledger_records_v180():
    source = _snapshot_runtime()
    snapshot = source.snapshot()

    not_a_record = deepcopy(snapshot)
    not_a_record["records"][0] = []

    with pytest.raises(ValueError, match="record must be a dict"):
        EpistemicRuntime.from_snapshot(not_a_record)

    bad_id = deepcopy(snapshot)
    bad_id["records"][0]["id"] = "incorrect"

    with pytest.raises(ValueError, match="record id is invalid"):
        EpistemicRuntime.from_snapshot(bad_id)

    bad_sequence = deepcopy(snapshot)
    bad_sequence["records"][0]["sequence"] = 2

    with pytest.raises(
        ValueError,
        match="record sequence is invalid",
    ):
        EpistemicRuntime.from_snapshot(bad_sequence)

    bad_kind = deepcopy(snapshot)
    bad_kind["records"][0]["kind"] = "unknown"

    with pytest.raises(ValueError, match="record kind is invalid"):
        EpistemicRuntime.from_snapshot(bad_kind)

    bad_record_tick = deepcopy(snapshot)
    bad_record_tick["records"][0]["tick"] = True

    with pytest.raises(ValueError, match="non-negative integer"):
        EpistemicRuntime.from_snapshot(bad_record_tick)

    future_record_tick = deepcopy(snapshot)
    future_record_tick["records"][0]["tick"] = 2

    with pytest.raises(ValueError, match="record tick is invalid"):
        EpistemicRuntime.from_snapshot(future_record_tick)

    reversed_record_tick = deepcopy(snapshot)
    reversed_record_tick["records"][1]["tick"] = 1

    with pytest.raises(ValueError, match="record tick is invalid"):
        EpistemicRuntime.from_snapshot(reversed_record_tick)

    bad_final_tick = deepcopy(snapshot)
    bad_final_tick["tick"] = 2

    with pytest.raises(
        ValueError,
        match="tick does not match records",
    ):
        EpistemicRuntime.from_snapshot(bad_final_tick)

    bad_fact = deepcopy(snapshot)
    bad_fact["records"][0]["fact_id"] = ""

    with pytest.raises(ValueError, match="fact id"):
        EpistemicRuntime.from_snapshot(bad_fact)

    bad_belief = deepcopy(snapshot)

    for record in bad_belief["records"]:
        if record["kind"] == "belief":
            record["holder"] = ""
            break

    with pytest.raises(ValueError, match="belief holder"):
        EpistemicRuntime.from_snapshot(bad_belief)

