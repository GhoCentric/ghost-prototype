import copy
import json

import pytest

from ghost.perception import (
    DEFAULT_PERCEPTION_HISTORY_LIMIT,
    MAX_PERCEPTION_HISTORY_LIMIT,
    PERCEPTION_KINDS,
    PERCEPTION_SNAPSHOT_SCHEMA_VERSION,
    PerceptionRuntime,
)


def assert_json_safe(value):
    json.dumps(value, allow_nan=False)


def test_default_runtime_starts_empty_and_exposes_bounded_contract():
    runtime = PerceptionRuntime()
    assert runtime.history_limit == DEFAULT_PERCEPTION_HISTORY_LIMIT
    assert runtime.has_state() is False
    assert runtime.observer_ids() == []
    assert runtime.history("sera") == []
    assert runtime.latest("sera") is None
    assert runtime.get_state("sera") is None
    assert PERCEPTION_KINDS == {
        "direct", "report", "outcome", "environment", "social",
    }


def test_direct_observation_normalizes_ids_and_canonicalizes_feature_key_order():
    runtime = PerceptionRuntime()
    packet = runtime.record(
        " sera ",
        " entity_approached ",
        subject=" player ",
        features={"visible": True, "distance": 2.1, "nested": {"z": 2, "a": 1}},
    )
    assert packet == {
        "observer": "sera",
        "sequence": 1,
        "kind": "direct",
        "event": "entity_approached",
        "subject": "player",
        "source": None,
        "features": {
            "distance": 2.1,
            "nested": {"a": 1, "z": 2},
            "visible": True,
        },
    }
    assert list(packet["features"]) == ["distance", "nested", "visible"]


@pytest.mark.parametrize("kind", ["direct", "outcome", "environment", "social"])
def test_non_report_kinds_allow_optional_source_and_subject(kind):
    runtime = PerceptionRuntime()
    packet = runtime.record(
        "sera", "signal", kind=kind, subject="gate", source="world", features=None,
    )
    assert packet["kind"] == kind
    assert packet["subject"] == "gate"
    assert packet["source"] == "world"
    assert packet["features"] == {}


def test_report_requires_and_preserves_explicit_source_without_truth_invention():
    runtime = PerceptionRuntime()
    with pytest.raises(ValueError, match="require an explicit source"):
        runtime.record("sera", "captain_took_bribe", kind="report", subject="captain")
    packet = runtime.record(
        "sera", "captain_took_bribe", kind=" REPORT ", subject="captain", source=" player ",
        features={"claimed_location": "market"},
    )
    assert packet["kind"] == "report"
    assert packet["source"] == "player"
    assert set(packet) == {
        "observer", "sequence", "kind", "event", "subject", "source", "features",
    }
    assert "truth" not in packet
    assert "verified" not in packet


@pytest.mark.parametrize("kind", [None, 1, True])
def test_kind_must_be_string(kind):
    runtime = PerceptionRuntime()
    with pytest.raises(ValueError, match="kind must be a string"):
        runtime.record("sera", "signal", kind=kind)
    assert runtime.has_state() is False


def test_unknown_kind_is_rejected_without_creating_state():
    runtime = PerceptionRuntime()
    with pytest.raises(ValueError, match="unsupported observation kind"):
        runtime.record("sera", "signal", kind="telepathy")
    assert runtime.snapshot()["observers"] == {}


@pytest.mark.parametrize("value", [[], "bad", 3])
def test_features_must_be_dict_or_none(value):
    runtime = PerceptionRuntime()
    with pytest.raises(ValueError, match="features must be a dict or None"):
        runtime.record("sera", "signal", features=value)
    assert runtime.has_state() is False


def test_features_accept_full_json_surface_and_are_copy_isolated():
    runtime = PerceptionRuntime()
    features = {
        "none": None,
        "text": "hello",
        "bool": True,
        "int": 2,
        "float": 0.25,
        "list": [1, False, {"nested": "yes"}],
    }
    packet = runtime.record("sera", "signal", features=features)
    features["list"][2]["nested"] = "changed"
    packet["features"]["list"].append(99)
    stored = runtime.latest("sera")
    assert stored["features"]["list"] == [1, False, {"nested": "yes"}]
    assert_json_safe(stored)


def test_features_reject_non_string_keys_non_json_values_and_nonfinite_floats():
    runtime = PerceptionRuntime()
    with pytest.raises(ValueError, match="keys must be strings"):
        runtime.record("sera", "signal", features={1: "bad"})
    with pytest.raises(ValueError, match="JSON-safe"):
        runtime.record("sera", "signal", features={"bad": {1, 2}})
    with pytest.raises(ValueError, match="finite numbers"):
        runtime.record("sera", "signal", features={"bad": float("nan")})
    assert runtime.has_state() is False


@pytest.mark.parametrize("field,value", [
    ("observer", None), ("observer", ""), ("observer", "bad|id"),
    ("event", None), ("event", ""), ("event", "bad|event"),
    ("subject", ""), ("subject", "bad|subject"),
    ("source", ""), ("source", "bad|source"),
])
def test_public_ids_use_existing_ghost_id_contract(field, value):
    runtime = PerceptionRuntime()
    kwargs = {"observer": "sera", "event": "signal", "subject": None, "source": None}
    kwargs[field] = value
    with pytest.raises(ValueError):
        runtime.record(
            kwargs["observer"], kwargs["event"],
            subject=kwargs["subject"], source=kwargs["source"],
        )
    assert runtime.has_state() is False


def test_sequences_are_monotonic_per_observer_and_histories_are_isolated():
    runtime = PerceptionRuntime()
    a1 = runtime.record("sera", "one")
    b1 = runtime.record("rowan", "one")
    a2 = runtime.record("sera", "two")
    assert [a1["sequence"], a2["sequence"]] == [1, 2]
    assert b1["sequence"] == 1
    assert [p["event"] for p in runtime.history("sera")] == ["one", "two"]
    assert [p["event"] for p in runtime.history("rowan")] == ["one"]
    assert runtime.observer_ids() == ["rowan", "sera"]


def test_bounded_history_rolls_old_entries_without_resetting_sequence():
    runtime = PerceptionRuntime(history_limit=2)
    for event in ("one", "two", "three"):
        runtime.record("sera", event)
    state = runtime.get_state("sera")
    assert [p["sequence"] for p in state["history"]] == [2, 3]
    assert state["next_sequence"] == 4
    assert state["history_limit"] == 2


def test_history_read_limit_and_copy_isolation():
    runtime = PerceptionRuntime(history_limit=4)
    for event in ("one", "two", "three"):
        runtime.record("sera", event)
    last_two = runtime.history("sera", limit=2)
    last_two[0]["event"] = "changed"
    assert [p["event"] for p in runtime.history("sera", limit=2)] == ["two", "three"]
    assert [p["event"] for p in runtime.history("sera")] == ["one", "two", "three"]


@pytest.mark.parametrize("bad", [True, 0, -1, MAX_PERCEPTION_HISTORY_LIMIT + 1, 1.5, "2"])
def test_history_limit_validation_applies_to_runtime_and_reads(bad):
    with pytest.raises(ValueError, match="history_limit|history read limit"):
        PerceptionRuntime(history_limit=bad)
    runtime = PerceptionRuntime()
    runtime.record("sera", "one")
    with pytest.raises(ValueError, match="history read limit"):
        runtime.history("sera", limit=bad)
    assert runtime.latest("sera")["event"] == "one"


def test_snapshot_is_sorted_json_safe_copy_isolated_and_roundtrips():
    runtime = PerceptionRuntime(history_limit=3)
    runtime.record("zeta", "signal", features={"x": [1]})
    runtime.record("alpha", "signal", kind="environment")
    snapshot = runtime.snapshot()
    assert snapshot["schema_version"] == PERCEPTION_SNAPSHOT_SCHEMA_VERSION
    assert list(snapshot["observers"]) == ["alpha", "zeta"]
    assert_json_safe(snapshot)
    restored = PerceptionRuntime.from_snapshot(snapshot)
    assert restored.snapshot() == snapshot
    snapshot["observers"]["zeta"]["history"][0]["features"]["x"].append(2)
    assert restored.latest("zeta")["features"]["x"] == [1]


def test_snapshot_continuation_preserves_next_sequence_after_rolling_history():
    runtime = PerceptionRuntime(history_limit=2)
    for event in ("one", "two", "three"):
        runtime.record("sera", event)
    restored = PerceptionRuntime.from_snapshot(runtime.snapshot())
    packet = restored.record("sera", "four")
    assert packet["sequence"] == 4
    assert [p["sequence"] for p in restored.history("sera")] == [3, 4]


@pytest.mark.parametrize("snapshot", [None, [], "bad"])
def test_snapshot_requires_dict(snapshot):
    with pytest.raises(ValueError, match="snapshot must be a dict"):
        PerceptionRuntime.from_snapshot(snapshot)
    assert not isinstance(snapshot, dict)


def test_snapshot_rejects_unknown_missing_schema_limit_and_observer_container_errors():
    valid = PerceptionRuntime().snapshot()
    unknown = copy.deepcopy(valid)
    unknown["future"] = 1
    with pytest.raises(ValueError, match="unsupported keys"):
        PerceptionRuntime.from_snapshot(unknown)

    missing = copy.deepcopy(valid)
    missing.pop("observers")
    with pytest.raises(ValueError, match="missing required keys"):
        PerceptionRuntime.from_snapshot(missing)

    bad_schema = copy.deepcopy(valid)
    bad_schema["schema_version"] = "9.9"
    with pytest.raises(ValueError, match="unsupported perception snapshot schema"):
        PerceptionRuntime.from_snapshot(bad_schema)

    bad_limit = copy.deepcopy(valid)
    bad_limit["history_limit"] = 0
    with pytest.raises(ValueError, match="history_limit"):
        PerceptionRuntime.from_snapshot(bad_limit)

    bad_observers = copy.deepcopy(valid)
    bad_observers["observers"] = []
    with pytest.raises(ValueError, match="observers must be a dict"):
        PerceptionRuntime.from_snapshot(bad_observers)
    assert valid["observers"] == {}


def _valid_observer_snapshot():
    runtime = PerceptionRuntime(history_limit=2)
    runtime.record("sera", "one")
    return runtime.snapshot()


def test_snapshot_rejects_observer_state_shape_and_next_sequence_errors():
    valid = _valid_observer_snapshot()

    not_dict = copy.deepcopy(valid)
    not_dict["observers"]["sera"] = []
    with pytest.raises(ValueError, match="must be a dict"):
        PerceptionRuntime.from_snapshot(not_dict)

    unknown = copy.deepcopy(valid)
    unknown["observers"]["sera"]["future"] = 1
    with pytest.raises(ValueError, match="unsupported keys"):
        PerceptionRuntime.from_snapshot(unknown)

    missing = copy.deepcopy(valid)
    missing["observers"]["sera"].pop("history")
    with pytest.raises(ValueError, match="missing required keys"):
        PerceptionRuntime.from_snapshot(missing)

    for bad in (True, 0, "2"):
        changed = copy.deepcopy(valid)
        changed["observers"]["sera"]["next_sequence"] = bad
        with pytest.raises(ValueError, match="next_sequence"):
            PerceptionRuntime.from_snapshot(changed)
    assert PerceptionRuntime.from_snapshot(valid).snapshot() == valid


def test_snapshot_rejects_history_container_length_and_packet_shape_errors():
    valid = _valid_observer_snapshot()

    not_list = copy.deepcopy(valid)
    not_list["observers"]["sera"]["history"] = {}
    with pytest.raises(ValueError, match="history must be a list"):
        PerceptionRuntime.from_snapshot(not_list)

    too_long = copy.deepcopy(valid)
    too_long["history_limit"] = 1
    too_long["observers"]["sera"]["history"].append(
        copy.deepcopy(too_long["observers"]["sera"]["history"][0])
    )
    with pytest.raises(ValueError, match="history exceeds history_limit"):
        PerceptionRuntime.from_snapshot(too_long)

    not_dict = copy.deepcopy(valid)
    not_dict["observers"]["sera"]["history"][0] = []
    with pytest.raises(ValueError, match=r"history\[0\].*dict"):
        PerceptionRuntime.from_snapshot(not_dict)

    unknown = copy.deepcopy(valid)
    unknown["observers"]["sera"]["history"][0]["future"] = 1
    with pytest.raises(ValueError, match="unsupported keys"):
        PerceptionRuntime.from_snapshot(unknown)

    missing = copy.deepcopy(valid)
    missing["observers"]["sera"]["history"][0].pop("features")
    with pytest.raises(ValueError, match="missing required keys"):
        PerceptionRuntime.from_snapshot(missing)
    assert valid["observers"]["sera"]["history"][0]["event"] == "one"


def test_snapshot_rejects_observer_mismatch_sequence_order_and_next_sequence_gap():
    runtime = PerceptionRuntime(history_limit=3)
    runtime.record("sera", "one")
    runtime.record("sera", "two")
    valid = runtime.snapshot()

    mismatch = copy.deepcopy(valid)
    mismatch["observers"]["sera"]["history"][0]["observer"] = "rowan"
    with pytest.raises(ValueError, match="observer mismatch"):
        PerceptionRuntime.from_snapshot(mismatch)

    order = copy.deepcopy(valid)
    order["observers"]["sera"]["history"][1]["sequence"] = 1
    with pytest.raises(ValueError, match="strictly increasing"):
        PerceptionRuntime.from_snapshot(order)

    gap = copy.deepcopy(valid)
    gap["observers"]["sera"]["next_sequence"] = 9
    with pytest.raises(ValueError, match="immediately follow"):
        PerceptionRuntime.from_snapshot(gap)
    assert PerceptionRuntime.from_snapshot(valid).latest("sera")["event"] == "two"


def test_snapshot_empty_history_requires_next_sequence_one():
    snapshot = PerceptionRuntime().snapshot()
    snapshot["observers"] = {"sera": {"next_sequence": 2, "history": []}}
    with pytest.raises(ValueError, match="empty history"):
        PerceptionRuntime.from_snapshot(snapshot)
    snapshot["observers"]["sera"]["next_sequence"] = 1
    restored = PerceptionRuntime.from_snapshot(snapshot)
    assert restored.get_state("sera") == {
        "observer": "sera", "history_limit": DEFAULT_PERCEPTION_HISTORY_LIMIT,
        "next_sequence": 1, "history": [],
    }


def test_snapshot_revalidates_packet_sequence_kind_report_source_and_features():
    valid = _valid_observer_snapshot()
    packet = valid["observers"]["sera"]["history"][0]

    for field, bad in (("sequence", True), ("sequence", 0), ("kind", "telepathy")):
        changed = copy.deepcopy(valid)
        changed["observers"]["sera"]["history"][0][field] = bad
        with pytest.raises(ValueError):
            PerceptionRuntime.from_snapshot(changed)

    report = copy.deepcopy(valid)
    report["observers"]["sera"]["history"][0]["kind"] = "report"
    report["observers"]["sera"]["history"][0]["source"] = None
    with pytest.raises(ValueError, match="require an explicit source"):
        PerceptionRuntime.from_snapshot(report)

    bad_features = copy.deepcopy(valid)
    bad_features["observers"]["sera"]["history"][0]["features"] = []
    with pytest.raises(ValueError, match="features must be a dict"):
        PerceptionRuntime.from_snapshot(bad_features)
    assert packet["sequence"] == 1


def test_identical_inputs_produce_identical_runtime_snapshots():
    first = PerceptionRuntime(history_limit=4)
    second = PerceptionRuntime(history_limit=4)
    sequence = [
        ("direct", "entity_approached", "player", None, {"distance": 2.1}),
        ("report", "captain_took_bribe", "captain", "player", {"location": "market"}),
        ("environment", "rain_started", None, "world", {"intensity": 0.6}),
    ]
    for runtime in (first, second):
        for kind, event, subject, source, features in sequence:
            runtime.record(
                "sera", event, kind=kind, subject=subject, source=source, features=features,
            )
    assert first.snapshot() == second.snapshot()
