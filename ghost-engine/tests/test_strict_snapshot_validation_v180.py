from copy import deepcopy

import pytest

from ghost.api import GhostAPI
from ghost.engine import GhostEngine
from ghost.epistemic import EpistemicRuntime
from ghost.world import WorldRuntime


class ConstructorBlockedEngine(
    GhostEngine
):
    def __init__(
        self,
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "engine constructor must not run"
        )


class ConstructorBlockedAPI(
    GhostAPI
):
    def __init__(
        self,
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "API constructor must not run"
        )


def _populated_api() -> GhostAPI:
    api = GhostAPI()

    api.apply_event(
        "player",
        "merchant",
        {
            "type": "betrayal",
            "intensity": 0.75,
        },
    )

    api.propagate_social_event(
        source="player",
        target="merchant",
        event="insult",
        observers=[
            "guard",
            "elder",
        ],
        weights={
            "guard": 1.0,
            "elder": 0.5,
        },
        intensity=0.5,
    )

    api.record_world_event(
        "raid",
        actor="player",
        target="millcross",
        details={
            "nested": {
                "count": 2,
            },
        },
    )

    return api


def _populated_epistemic() -> EpistemicRuntime:
    runtime = EpistemicRuntime()

    runtime.record_fact(
        fact_id="fact_raid",
        source="world",
        subject="royal_raid",
        predicate="occurred",
        object="millcross",
        attributes={
            "confirmed": True,
        },
    )

    observation = runtime.observe(
        observer="guard",
        kind="visual",
        visible_features=[
            "royal_banner",
            "empty_crates",
        ],
        reliability=0.9,
        subject="royal_raid",
        provenance={
            "location": "millcross",
        },
    )

    evidence = runtime.add_evidence(
        evidence_type="inventory_check",
        source="warehouse",
        subject="royal_raid",
        supports={
            "cause": {
                "royal_confiscation": 0.4,
            },
            "report_quality": {
                "directly_observed": 0.2,
            },
        },
        contradicts={
            "cause": {
                "bandit_raid": 0.1,
            },
        },
        available_to=[
            "guard",
        ],
        provenance={
            "ledger": "warehouse_7",
        },
    )

    belief = runtime.evaluate_beliefs(
        holder="guard",
        subject="royal_raid",
        candidates={
            "cause": {
                "royal_confiscation": 0.6,
                "bandit_raid": 0.4,
            },
        },
        report_quality={
            "directly_observed": 0.7,
        },
        evidence_ids=[
            observation["id"],
            evidence["id"],
        ],
        provenance={
            "reason": "initial assessment",
        },
    )

    runtime.report(
        speaker="guard",
        audience=[
            "merchant",
        ],
        claim={
            "subject": "royal_raid",
        },
        confidence=0.8,
        source_belief_id=belief["id"],
        provenance={
            "channel": "spoken",
        },
    )

    runtime.tick()

    return runtime


def test_strict_engine_snapshot_roundtrip_v180():
    engine = _populated_api().engine
    snapshot = engine.snapshot()

    restored = GhostEngine.from_snapshot(
        deepcopy(snapshot)
    )

    assert restored.snapshot() == snapshot


def test_engine_restore_still_bypasses_constructor_v180():
    snapshot = _populated_api().engine.snapshot()

    restored = (
        ConstructorBlockedEngine
        .from_snapshot(
            deepcopy(snapshot)
        )
    )

    assert isinstance(
        restored,
        ConstructorBlockedEngine,
    )

    assert restored.snapshot() == snapshot


@pytest.mark.parametrize(
    (
        "field",
        "bad_value",
        "match",
    ),
    [
        (
            "cycles",
            "not-an-int",
            "non-negative integer",
        ),
        (
            "agents",
            [],
            "agents must be a dict",
        ),
        (
            "npc",
            [],
            "npc must be a dict",
        ),
        (
            "neighbors",
            [],
            "neighbors must be a dict",
        ),
        (
            "relationships",
            [],
            "relationships must be a dict",
        ),
        (
            "social_propagation",
            {},
            "social_propagation must be a list",
        ),
    ],
)
def test_engine_snapshot_rejects_wrong_core_types_v180(
    field,
    bad_value,
    match,
):
    snapshot = _populated_api().engine.snapshot()
    snapshot[field] = bad_value

    with pytest.raises(
        ValueError,
        match=match,
    ):
        GhostEngine.from_snapshot(
            snapshot
        )


def test_engine_snapshot_rejects_missing_required_field_v180():
    snapshot = _populated_api().engine.snapshot()
    del snapshot["relationships"]

    with pytest.raises(
        ValueError,
        match="missing required keys",
    ):
        GhostEngine.from_snapshot(
            snapshot
        )


def test_engine_snapshot_rejects_bad_metadata_v180():
    snapshot = _populated_api().engine.snapshot()
    snapshot["schema_version"] = "bad"

    with pytest.raises(
        ValueError,
        match="unsupported engine snapshot schema",
    ):
        GhostEngine.from_snapshot(
            snapshot
        )

    snapshot = _populated_api().engine.snapshot()
    snapshot["ghost_version"] = ""

    with pytest.raises(
        ValueError,
        match="ghost version cannot be empty",
    ):
        GhostEngine.from_snapshot(
            snapshot
        )


def test_engine_snapshot_rejects_relationship_numeric_strings_v180():
    snapshot = _populated_api().engine.snapshot()

    pair_key = next(
        iter(
            snapshot["relationships"]
        )
    )

    snapshot[
        "relationships"
    ][pair_key]["pos"] = "not-a-number"

    with pytest.raises(
        ValueError,
        match="field pos must be a finite number",
    ):
        GhostEngine.from_snapshot(
            snapshot
        )


def test_engine_snapshot_rejects_inconsistent_trust_v180():
    snapshot = _populated_api().engine.snapshot()

    pair_key = next(
        iter(
            snapshot["relationships"]
        )
    )

    snapshot[
        "relationships"
    ][pair_key]["trust"] = 999.0

    with pytest.raises(
        ValueError,
        match="trust must equal pos - neg",
    ):
        GhostEngine.from_snapshot(
            snapshot
        )


def test_engine_snapshot_rejects_asymmetric_neighbors_v180():
    snapshot = _populated_api().engine.snapshot()

    snapshot["neighbors"]["player"].remove(
        "merchant"
    )

    with pytest.raises(
        ValueError,
        match="neighbor graph must be symmetric",
    ):
        GhostEngine.from_snapshot(
            snapshot
        )


def test_ghost_api_roundtrip_uses_strict_restore_v180():
    api = _populated_api()
    snapshot = api.snapshot()

    restored = GhostAPI.from_snapshot(
        deepcopy(snapshot)
    )

    assert restored.snapshot() == snapshot


def test_api_restore_still_bypasses_constructor_v180():
    snapshot = _populated_api().snapshot()

    restored = (
        ConstructorBlockedAPI
        .from_snapshot(
            deepcopy(snapshot)
        )
    )

    assert isinstance(
        restored,
        ConstructorBlockedAPI,
    )

    assert restored.snapshot() == snapshot


def test_ghost_api_rejects_unknown_top_level_field_v180():
    snapshot = _populated_api().snapshot()
    snapshot["unexpected"] = True

    with pytest.raises(
        ValueError,
        match="unsupported keys",
    ):
        GhostAPI.from_snapshot(
            snapshot
        )


def test_ghost_api_preserves_legacy_optional_fields_v180():
    snapshot = _populated_api().snapshot()

    snapshot.pop("ghost_version")
    snapshot.pop("epistemic")
    snapshot.pop("event_map")
    snapshot.pop(
        "transitions",
        None,
    )

    restored = GhostAPI.from_snapshot(
        snapshot
    )

    assert isinstance(
        restored,
        GhostAPI,
    )

    assert restored.epistemic.snapshot() == {
        "schema_version": "1.0",
        "tick": 0,
        "sequence": 0,
        "records": [],
    }


def test_ghost_api_rejects_invalid_event_map_numbers_v180():
    snapshot = _populated_api().snapshot()

    snapshot["event_map"]["help"][
        "trust"
    ] = "not-a-number"

    with pytest.raises(
        ValueError,
        match="event_map delta",
    ):
        GhostAPI.from_snapshot(
            snapshot
        )


def test_world_snapshot_roundtrip_v180():
    world = _populated_api().world
    snapshot = world.to_dict()

    restored = WorldRuntime.from_dict(
        deepcopy(snapshot)
    )

    assert restored.to_dict() == snapshot


def test_world_snapshot_rejects_unknown_field_v180():
    snapshot = _populated_api().world.to_dict()
    snapshot["unexpected"] = True

    with pytest.raises(
        ValueError,
        match="unsupported keys",
    ):
        WorldRuntime.from_dict(
            snapshot
        )


def test_world_snapshot_recalculates_contradictory_status_v180():
    snapshot = _populated_api().world.to_dict()
    snapshot["global_pressure"] = 2.5
    snapshot["status"] = "normal"

    restored = WorldRuntime.from_dict(
        snapshot
    )

    assert restored.status == "crisis"


def test_world_snapshot_rejects_malformed_event_v180():
    snapshot = _populated_api().world.to_dict()

    snapshot["events"][0][
        "details"
    ] = []

    with pytest.raises(
        ValueError,
        match="event details must be a dict",
    ):
        WorldRuntime.from_dict(
            snapshot
        )


def test_epistemic_empty_snapshot_allows_idle_tick_v180():
    snapshot = {
        "schema_version": "1.0",
        "tick": 5,
        "sequence": 0,
        "records": [],
    }

    restored = EpistemicRuntime.from_snapshot(
        deepcopy(snapshot)
    )

    assert restored.snapshot() == snapshot


def test_epistemic_real_runtime_snapshot_roundtrip_v180():
    runtime = _populated_epistemic()
    snapshot = runtime.snapshot()

    restored = EpistemicRuntime.from_snapshot(
        deepcopy(snapshot)
    )

    assert restored.snapshot() == snapshot


def test_epistemic_report_confidence_is_probability_v180():
    runtime = _populated_epistemic()
    snapshot = runtime.snapshot()

    report = next(
        record
        for record in snapshot["records"]
        if record["kind"] == "report"
    )

    report["confidence"] = "certain"

    with pytest.raises(
        ValueError,
        match="report confidence",
    ):
        EpistemicRuntime.from_snapshot(
            snapshot
        )


def test_epistemic_report_rejects_unknown_belief_v180():
    runtime = _populated_epistemic()
    snapshot = runtime.snapshot()

    report = next(
        record
        for record in snapshot["records"]
        if record["kind"] == "report"
    )

    report["source_belief_id"] = (
        "epistemic_999999"
    )

    with pytest.raises(
        ValueError,
        match="source belief does not exist",
    ):
        EpistemicRuntime.from_snapshot(
            snapshot
        )


def test_epistemic_belief_rejects_future_evidence_v180():
    runtime = _populated_epistemic()
    snapshot = runtime.snapshot()

    belief = next(
        record
        for record in snapshot["records"]
        if record["kind"] == "belief"
    )

    belief["evidence_ids"].append(
        "epistemic_999999"
    )

    belief["provenance"][
        "evidence_ids"
    ].append(
        "epistemic_999999"
    )

    with pytest.raises(
        ValueError,
        match="future or unknown record",
    ):
        EpistemicRuntime.from_snapshot(
            snapshot
        )


def test_epistemic_belief_confidence_math_v180():
    runtime = _populated_epistemic()
    snapshot = runtime.snapshot()

    belief = next(
        record
        for record in snapshot["records"]
        if record["kind"] == "belief"
    )

    dimension = next(
        iter(
            belief["dimensions"].values()
        )
    )

    dimension["uncertainty"] = 0.9

    with pytest.raises(
        ValueError,
        match="must total 1.0",
    ):
        EpistemicRuntime.from_snapshot(
            snapshot
        )
