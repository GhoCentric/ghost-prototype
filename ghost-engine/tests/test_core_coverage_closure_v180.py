from copy import deepcopy

import pytest

import ghost.api as api_module
import ghost.combat as combat
import ghost.engine as engine_module
import ghost.epistemic as epistemic
import ghost.objectives as objectives
import ghost.world as world_module
from ghost.api import GhostAPI
from ghost.engine import GhostEngine
from ghost.epistemic import EpistemicRuntime
from ghost.relationships import RelationshipGraph
from ghost.world import TownMood, WorldRuntime


def _valid_engine_snapshot():
    api = GhostAPI()
    api.apply_event(
        "actor",
        "target",
        {
            "type": "help",
            "intensity": 1.0,
        },
    )
    return api.engine.snapshot()


def _valid_dimension_packet():
    return {
        "cause": {
            "candidates": {
                "alpha": 0.6,
                "beta": 0.4,
            },
            "dominant_candidate": "alpha",
            "confidence": 0.6,
            "uncertainty": 0.4,
        },
    }


def _valid_belief_record():
    return {
        "id": "epistemic_000010",
        "kind": "belief",
        "sequence": 10,
        "tick": 0,
        "base_dimensions": {
            "cause": {
                "alpha": 0.6,
                "beta": 0.4,
            },
        },
        "base_report_quality": {},
        "dimensions": _valid_dimension_packet(),
        "evidence_ids": [],
        "holder": "alice",
        "previous_belief_id": None,
        "provenance": {
            "evidence_ids": [],
            "metadata": {},
        },
        "report_quality": {},
        "subject": "subject",
    }


@pytest.mark.parametrize(
    "value, match",
    [
        ({1: "bad"}, "keys must be strings"),
        (object(), "JSON-safe"),
    ],
)
def test_api_json_boundary_rejects_remaining_invalid_values_v180(
    value,
    match,
):
    with pytest.raises(ValueError, match=match):
        api_module._api_snapshot_json_value(
            value,
            "packet",
        )


@pytest.mark.parametrize(
    "event_map, match",
    [
        ({"": {}}, "names must be non-empty strings"),
        ({"custom": []}, "entries must be dicts"),
        ({"custom": {"": 1.0}}, "delta names must be non-empty strings"),
    ],
)
def test_api_event_map_validation_closes_invalid_shapes_v180(
    event_map,
    match,
):
    with pytest.raises(ValueError, match=match):
        api_module._validate_snapshot_event_map(
            event_map
        )


def test_api_constructor_rejects_non_mapping_config_v180():
    with pytest.raises(ValueError, match="config must be a dict"):
        GhostAPI(config=[])


def test_api_snapshot_rejects_missing_required_key_v180():
    snapshot = GhostAPI().snapshot()
    snapshot.pop("world")

    with pytest.raises(ValueError, match="missing required keys"):
        GhostAPI.from_snapshot(snapshot)


def test_api_detects_post_construction_event_map_corruption_v180():
    api = GhostAPI()
    api.event_map["help"] = []

    with pytest.raises(ValueError, match="event map entries must be dicts"):
        api.apply_event(
            "actor",
            "target",
            {"type": "help"},
        )


def test_api_custom_event_without_trust_delta_returns_packet_v180():
    api = GhostAPI(
        event_map={
            "custom": {
                "attachment": 0.25,
            },
        }
    )

    packet = api.apply_event(
        "actor",
        "target",
        {"type": "custom"},
    )

    assert packet["deltas"] == {
        "attachment": 0.25,
    }


@pytest.mark.parametrize(
    "value",
    [
        None,
        "   ",
    ],
)
def test_combat_text_rejects_non_text_and_blank_v180(value):
    with pytest.raises(ValueError, match="non-empty string"):
        combat._combat_text(value, "move")


def test_combat_integer_validator_rejects_invalid_value_v180():
    with pytest.raises(ValueError, match="non-negative integer"):
        combat._combat_non_negative_int(True, "damage")


def test_combat_recovery_lock_rejects_blank_selection_key_v180():
    with pytest.raises(ValueError, match="selection key"):
        combat.lock_combat_recovery_read_packet(
            selection_key=" ",
            proposed_move="light",
        )


def test_combat_recovery_lock_rejects_invalid_fallback_v180():
    with pytest.raises(ValueError, match="fallback move is invalid"):
        combat.lock_combat_recovery_read_packet(
            selection_key="turn-1",
            proposed_move=None,
            fallback_move="parry",
        )


def _locked_recovery_read():
    return combat.lock_combat_recovery_read_packet(
        selection_key="turn-1",
        proposed_move="light",
    )


@pytest.mark.parametrize(
    "mutation, match",
    [
        (lambda _packet: [], "must be a mapping"),
        (lambda packet: {**packet, "kind": "wrong"}, "kind is invalid"),
        (
            lambda packet: {**packet, "schema_version": "9.9"},
            "schema is unsupported",
        ),
        (lambda packet: {**packet, "locked": False}, "must be locked"),
        (
            lambda packet: {**packet, "selected_move": "heavy"},
            "selected move is invalid",
        ),
    ],
)
def test_combat_recovery_resolution_rejects_invalid_read_packets_v180(
    mutation,
    match,
):
    packet = mutation(_locked_recovery_read())

    with pytest.raises(ValueError, match=match):
        combat.resolve_combat_recovery_packet(
            read_packet=packet,
            player_move="light",
        )


def test_combat_recovery_resolution_rejects_invalid_player_move_v180():
    with pytest.raises(ValueError, match="player move is invalid"):
        combat.resolve_combat_recovery_packet(
            read_packet=_locked_recovery_read(),
            player_move="heavy",
        )


@pytest.mark.parametrize(
    "value, helper, match",
    [
        (
            float("nan"),
            lambda value: engine_module._engine_snapshot_json_value(
                value,
                "snapshot",
            ),
            "finite numbers",
        ),
        (
            {1: "bad"},
            lambda value: engine_module._engine_snapshot_json_value(
                value,
                "snapshot",
            ),
            "keys must be strings",
        ),
        (
            object(),
            lambda value: engine_module._engine_snapshot_json_value(
                value,
                "snapshot",
            ),
            "JSON-safe",
        ),
        (
            3,
            lambda value: engine_module._engine_snapshot_text(
                value,
                "text",
            ),
            "must be a string",
        ),
        (
            float("inf"),
            lambda value: engine_module._engine_snapshot_number(
                value,
                "number",
            ),
            "finite number",
        ),
    ],
)
def test_engine_private_snapshot_guards_close_invalid_values_v180(
    value,
    helper,
    match,
):
    with pytest.raises(ValueError, match=match):
        helper(value)


def test_engine_relationship_validator_rejects_non_mapping_v180():
    with pytest.raises(ValueError, match="must be a dict"):
        engine_module._validate_engine_relationship(
            "actor|target",
            [],
        )


def test_engine_relationship_validator_accepts_sparse_legacy_packet_v180():
    result = engine_module._validate_engine_relationship(
        "actor|target",
        {
            "state": "neutral",
        },
    )

    assert result is None


@pytest.mark.parametrize(
    "relationship, match",
    [
        ({"pos": -0.1}, "cannot be negative"),
        ({"diagnostics": []}, "diagnostics must be a dict"),
        ({"transition": ["neutral"]}, "must contain two state strings"),
        ({"trigger": []}, "trigger must be a dict"),
    ],
)
def test_engine_relationship_validator_closes_remaining_shape_guards_v180(
    relationship,
    match,
):
    with pytest.raises(ValueError, match=match):
        engine_module._validate_engine_relationship(
            "actor|target",
            relationship,
        )


def _assert_engine_snapshot_rejected(mutator, match, monkeypatch=None):
    snapshot = _valid_engine_snapshot()
    mutator(snapshot)

    with pytest.raises(ValueError, match=match):
        engine_module._validate_engine_snapshot(snapshot)


@pytest.mark.parametrize(
    "mutator, match",
    [
        (
            lambda snapshot: snapshot["npc"].pop("threat_level"),
            "missing threat_level",
        ),
        (
            lambda snapshot: snapshot["npc"].__setitem__("threat_level", -1.0),
            "cannot be negative",
        ),
        (
            lambda snapshot: snapshot["npc"].pop("last_intent"),
            "missing last_intent",
        ),
        (
            lambda snapshot: snapshot["relationships"].__setitem__(
                "invalid",
                snapshot["relationships"]["actor|target"],
            ),
            "relationship key.*is invalid",
        ),
        (
            lambda snapshot: snapshot["relationships"].__setitem__(
                "target|actor",
                deepcopy(snapshot["relationships"]["actor|target"]),
            ),
            "duplicate relationship pair",
        ),
        (
            lambda snapshot: snapshot["neighbors"].__setitem__("actor", "target"),
            "neighbor lists must be lists",
        ),
        (
            lambda snapshot: snapshot["neighbors"].__setitem__(
                "actor",
                ["actor"],
            ),
            "cannot neighbor itself",
        ),
        (
            lambda snapshot: snapshot["neighbors"].__setitem__(
                "actor",
                ["target", "target"],
            ),
            "contains duplicates",
        ),
        (
            lambda snapshot: snapshot.__setitem__(
                "neighbors",
                {
                    "actor": [],
                    "target": [],
                },
            ),
            "must exist in the neighbor graph",
        ),
        (
            lambda snapshot: snapshot.__setitem__(
                "social_propagation",
                [{} for _ in range(26)],
            ),
            "cannot contain more than 25",
        ),
        (
            lambda snapshot: snapshot.__setitem__(
                "social_propagation",
                ["bad"],
            ),
            "must contain only dict packets",
        ),
    ],
)
def test_engine_snapshot_closes_remaining_validation_paths_v180(
    mutator,
    match,
):
    assert callable(mutator)
    _assert_engine_snapshot_rejected(mutator, match)


def test_engine_relationship_key_type_defense_is_independently_enforced_v180(
    monkeypatch,
):
    snapshot = _valid_engine_snapshot()
    relationship = snapshot["relationships"].pop("actor|target")
    snapshot["relationships"] = {
        7: relationship,
    }

    monkeypatch.setattr(
        engine_module,
        "_engine_snapshot_json_value",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(ValueError, match="relationship keys must be strings"):
        engine_module._validate_engine_snapshot(snapshot)


@pytest.mark.parametrize(
    "call, match",
    [
        (
            lambda: epistemic._epistemic_snapshot_mapping([], "mapping"),
            "must be a dict",
        ),
        (
            lambda: epistemic._epistemic_snapshot_text_list(
                [],
                "values",
                allow_empty=False,
            ),
            "must not be empty",
        ),
        (
            lambda: epistemic._validate_epistemic_weight_dimensions(
                {},
                "dimensions",
                allow_empty=False,
            ),
            "must not be empty",
        ),
        (
            lambda: epistemic._validate_epistemic_weight_dimensions(
                {"cause": {}},
                "dimensions",
                allow_empty=True,
            ),
            "dimension 'cause' must not be empty",
        ),
        (
            lambda: epistemic._validate_epistemic_weight_dimensions(
                {"cause": {"alpha": 0.0}},
                "dimensions",
                allow_empty=True,
            ),
            "must have positive weight",
        ),
        (
            lambda: epistemic._validate_epistemic_adjustments(
                {"dimensions": {}, "wrong": {}},
                "adjustments",
            ),
            "unsupported keys",
        ),
    ],
)
def test_epistemic_helper_guards_close_remaining_paths_v180(call, match):
    with pytest.raises(ValueError, match=match):
        call()


def test_epistemic_optional_text_accepts_none_v180():
    assert (
        epistemic._epistemic_snapshot_optional_text(
            None,
            "optional",
        )
        is None
    )


@pytest.mark.parametrize(
    "mutator, match",
    [
        (
            lambda packet: packet.clear(),
            "dimensions must not be empty",
        ),
        (
            lambda packet: packet["cause"].__setitem__("extra", True),
            "unsupported fields",
        ),
        (
            lambda packet: packet["cause"].__setitem__("candidates", {}),
            "candidates must not be empty",
        ),
        (
            lambda packet: packet["cause"].__setitem__(
                "candidates",
                {"alpha": 0.8, "beta": 0.3},
            ),
            "probabilities must total 1.0",
        ),
        (
            lambda packet: packet["cause"].__setitem__(
                "dominant_candidate",
                "missing",
            ),
            "dominant candidate is absent",
        ),
        (
            lambda packet: packet["cause"].__setitem__(
                "dominant_candidate",
                "beta",
            ),
            "dominant candidate is inconsistent",
        ),
        (
            lambda packet: packet["cause"].__setitem__(
                "confidence",
                0.7,
            ),
            "confidence is inconsistent",
        ),
    ],
)
def test_epistemic_belief_dimension_validation_closes_paths_v180(
    mutator,
    match,
):
    packet = _valid_dimension_packet()
    mutator(packet)

    with pytest.raises(ValueError, match=match):
        epistemic._validate_epistemic_packet_dimensions(packet)


def test_epistemic_access_check_rejects_non_evidence_record_kind_v180():
    assert not epistemic._epistemic_record_accessible_to(
        {"kind": "fact"},
        "alice",
    )


def _tick_record():
    return {
        "id": "epistemic_000001",
        "kind": "tick",
        "sequence": 1,
        "tick": 0,
    }


def test_epistemic_semantics_rejects_missing_kind_fields_v180():
    record = _tick_record()
    record.pop("id")

    with pytest.raises(ValueError, match="missing fields"):
        epistemic._validate_epistemic_record_semantics(
            record,
            {},
            {},
        )


def test_epistemic_semantics_rejects_unknown_kind_fields_v180():
    record = _tick_record()
    record["extra"] = True

    with pytest.raises(ValueError, match="unsupported fields"):
        epistemic._validate_epistemic_record_semantics(
            record,
            {},
            {},
        )


def test_epistemic_report_source_belief_must_belong_to_speaker_v180():
    record = {
        "id": "epistemic_000010",
        "kind": "report",
        "sequence": 10,
        "tick": 0,
        "audience": ["carol"],
        "claim": {"subject": "subject"},
        "confidence": 0.8,
        "provenance": {},
        "source_belief_id": "belief-1",
        "speaker": "bob",
    }

    with pytest.raises(ValueError, match="speaker must own source belief"):
        epistemic._validate_epistemic_record_semantics(
            record,
            {},
            {
                "belief-1": {
                    "holder": "alice",
                },
            },
        )


@pytest.mark.parametrize(
    "configure, match",
    [
        (
            lambda record, prior, beliefs: (
                record["evidence_ids"].append("fact-1"),
                record["provenance"]["evidence_ids"].append("fact-1"),
                prior.__setitem__("fact-1", {"kind": "fact"}),
            ),
            "must reference observations, reports, or evidence",
        ),
        (
            lambda record, prior, beliefs: (
                record["evidence_ids"].append("obs-1"),
                record["provenance"]["evidence_ids"].append("obs-1"),
                prior.__setitem__(
                    "obs-1",
                    {
                        "kind": "observation",
                        "observer": "bob",
                        "subject": "subject",
                    },
                ),
            ),
            "holder cannot access",
        ),
        (
            lambda record, prior, beliefs: (
                record["evidence_ids"].append("evidence-1"),
                record["provenance"]["evidence_ids"].append("evidence-1"),
                prior.__setitem__(
                    "evidence-1",
                    {
                        "kind": "evidence",
                        "available_to": ["alice"],
                        "subject": "different-subject",
                    },
                ),
            ),
            "evidence subject does not match",
        ),
        (
            lambda record, prior, beliefs: record.__setitem__(
                "previous_belief_id",
                "missing-belief",
            ),
            "previous belief does not exist",
        ),
        (
            lambda record, prior, beliefs: (
                record.__setitem__("previous_belief_id", "prior-belief"),
                beliefs.__setitem__(
                    "prior-belief",
                    {
                        "holder": "bob",
                        "subject": "subject",
                    },
                ),
            ),
            "previous belief holder does not match",
        ),
        (
            lambda record, prior, beliefs: (
                record.__setitem__("previous_belief_id", "prior-belief"),
                beliefs.__setitem__(
                    "prior-belief",
                    {
                        "holder": "alice",
                        "subject": "different-subject",
                    },
                ),
            ),
            "previous belief subject does not match",
        ),
        (
            lambda record, prior, beliefs: record["provenance"].__setitem__(
                "extra",
                True,
            ),
            "provenance has unsupported keys",
        ),
        (
            lambda record, prior, beliefs: record["provenance"][
                "evidence_ids"
            ].append("different"),
            "provenance evidence ids do not match",
        ),
    ],
)
def test_epistemic_belief_semantics_closes_remaining_guards_v180(
    configure,
    match,
):
    record = _valid_belief_record()
    prior = {}
    beliefs = {}
    configure(record, prior, beliefs)

    with pytest.raises(ValueError, match=match):
        epistemic._validate_epistemic_record_semantics(
            record,
            prior,
            beliefs,
        )


def test_epistemic_restore_rejects_record_missing_common_fields_v180():
    snapshot = {
        "schema_version": "1.0",
        "sequence": 1,
        "tick": 0,
        "records": [
            {
                "kind": "tick",
                "sequence": 1,
                "tick": 0,
            },
        ],
    }

    with pytest.raises(ValueError, match="missing common fields"):
        EpistemicRuntime.from_snapshot(snapshot)


@pytest.mark.parametrize(
    "value",
    [
        5,
        "   ",
    ],
)
def test_objective_text_rejects_non_text_and_blank_v180(value):
    with pytest.raises(ValueError, match="non-empty string"):
        objectives._objective_text(value, "actor")


def test_objective_health_band_covers_critical_v180():
    assert objectives._objective_health_band(1, 4) == "critical"


@pytest.mark.parametrize(
    "turns, expected",
    [
        (3, "deadline_critical"),
        (5, "deadline_urgent"),
    ],
)
def test_objective_pressure_band_covers_deadline_states_v180(
    turns,
    expected,
):
    assert (
        objectives._objective_pressure_band(
            status="active",
            successes_required=3,
            turns_remaining=turns,
        )
        == expected
    )


def test_relationship_zero_trust_delta_preserves_reservoirs_v180():
    graph = RelationshipGraph({})
    relationship = graph.apply_delta(
        "actor",
        "target",
        {"trust": 0.0},
    )

    assert relationship["trust"] == 0.0
    assert relationship["pos"] == 0.0
    assert relationship["neg"] == 0.0


def test_relationship_event_spec_rejects_non_mapping_v180():
    graph = RelationshipGraph({})

    with pytest.raises(ValueError, match="specification must be a dict"):
        graph._resolve_event_spec(
            "custom",
            [],
        )


def test_relationship_custom_extra_delta_is_resolved_and_applied_v180():
    graph = RelationshipGraph({})

    relationship = graph.apply_event(
        "actor",
        "target",
        "custom",
        event_spec={
            "trust": 0.0,
            "courage": 0.4,
        },
    )

    assert graph._rels["actor|target"]["courage"] == 0.4


@pytest.mark.parametrize(
    "kwargs, match",
    [
        (
            {"event": "unknown-event"},
            "Unknown relationship event",
        ),
        (
            {"event": "help", "observers": "observer"},
            "observers must be a list or tuple",
        ),
        (
            {"event": "help", "weights": []},
            "weights must be a dict",
        ),
    ],
)
def test_social_propagation_rejects_remaining_invalid_inputs_v180(
    kwargs,
    match,
):
    graph = RelationshipGraph({})

    with pytest.raises(ValueError, match=match):
        graph.propagate_social_event(
            source="actor",
            target="target",
            **kwargs,
        )


class _UnhashableObserver:
    __hash__ = None

    def __str__(self):
        return "observer"


def test_social_propagation_handles_unhashable_stringable_observer_v180():
    graph = RelationshipGraph({})

    packet = graph.propagate_social_event(
        source="actor",
        target="target",
        event="help",
        observers=[_UnhashableObserver()],
        weights={"observer": 0.5},
    )

    assert packet["propagated"][0]["affected"] == "observer"


@pytest.mark.parametrize(
    "value, helper, match",
    [
        (
            None,
            lambda value: world_module._world_snapshot_json_value(
                value,
                "world",
            ),
            None,
        ),
        (
            {1: "bad"},
            lambda value: world_module._world_snapshot_json_value(
                value,
                "world",
            ),
            "keys must be strings",
        ),
        (
            object(),
            lambda value: world_module._world_snapshot_json_value(
                value,
                "world",
            ),
            "JSON-safe",
        ),
        (
            None,
            lambda value: world_module._world_snapshot_optional_text(
                value,
                "text",
            ),
            None,
        ),
        (
            7,
            lambda value: world_module._world_snapshot_optional_text(
                value,
                "text",
            ),
            "string or None",
        ),
    ],
)
def test_world_private_snapshot_helpers_close_paths_v180(
    value,
    helper,
    match,
):
    if match is None:
        assert helper(value) is None
    else:
        with pytest.raises(ValueError, match=match):
            helper(value)


def test_town_mood_apply_updates_all_fields_v180():
    mood = TownMood()

    mood.apply(
        {
            "fear_delta": 0.2,
            "order_delta": -0.1,
            "commerce_delta": -0.2,
            "resentment_delta": 0.3,
        }
    )

    assert mood.to_dict() == {
        "fear": 0.2,
        "order": 0.4,
        "commerce": 0.8,
        "resentment": 0.3,
    }


@pytest.mark.parametrize(
    "payload, match",
    [
        (
            {"mood": {"unknown": 0.0}},
            "mood has unsupported keys",
        ),
        (
            {
                "events": [
                    {
                        "type": "event",
                        "actor": "",
                        "target": "",
                        "details": {},
                    }
                    for _ in range(26)
                ],
            },
            "more than 25 entries",
        ),
        (
            {
                "events": [
                    {
                        "type": "event",
                        "extra": True,
                    },
                ],
            },
            "event 0 has unsupported keys",
        ),
        (
            {
                "events": [
                    {
                        "type": " ",
                    },
                ],
            },
            "event type must be a non-empty string",
        ),
    ],
)
def test_world_restore_closes_remaining_validation_paths_v180(
    payload,
    match,
):
    with pytest.raises(ValueError, match=match):
        WorldRuntime.from_dict(payload)
