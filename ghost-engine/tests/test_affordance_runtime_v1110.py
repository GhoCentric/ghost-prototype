import copy
import json

import pytest

from ghost.affordances import (
    AFFORDANCE_SNAPSHOT_SCHEMA_VERSION,
    DEFAULT_AFFORDANCE_HISTORY_LIMIT,
    AffordanceRuntime,
)


def assert_json_safe(value):
    json.dumps(value, allow_nan=False, sort_keys=True)


def base_runtime():
    return AffordanceRuntime(history_limit=3)


def test_defaults_and_empty_reads_are_stable():
    runtime = AffordanceRuntime()
    assert runtime.history_limit == DEFAULT_AFFORDANCE_HISTORY_LIMIT
    assert runtime.has_state() is False
    assert runtime.agent_ids() == []
    assert runtime.history("sera") == []
    assert runtime.current("sera") is None
    assert runtime.current_capabilities("sera") == []
    assert runtime.snapshot() == {
        "schema_version": AFFORDANCE_SNAPSHOT_SCHEMA_VERSION,
        "history_limit": DEFAULT_AFFORDANCE_HISTORY_LIMIT,
        "sequence": 0,
        "history": {},
    }


@pytest.mark.parametrize("bad", [True, False, 0, -1, 1.5, "3", None])
def test_history_limit_requires_positive_integer(bad):
    with pytest.raises(ValueError, match="positive integer"):
        AffordanceRuntime(history_limit=bad)


def test_set_accepts_string_and_dict_candidates_and_canonicalizes_order():
    runtime = base_runtime()
    packet = runtime.set(
        " sera ",
        [
            {
                "id": "warn_player",
                "capability": "warn",
                "features": {"target": "player", "nested": {"b": 2, "a": 1}},
            },
            "question",
        ],
        allowed_capabilities=["question", "warn"],
        context={"zone": "gate", "distance": 2.0},
    )
    assert packet == {
        "sequence": 1,
        "agent": "sera",
        "candidates": [
            {"id": "question", "capability": "question", "features": {}},
            {
                "id": "warn_player",
                "capability": "warn",
                "features": {"nested": {"a": 1, "b": 2}, "target": "player"},
            },
        ],
        "context": {"distance": 2.0, "zone": "gate"},
    }
    assert runtime.has_state() is True
    assert runtime.agent_ids() == ["sera"]
    assert runtime.current("sera") == packet
    assert runtime.current_capabilities("sera") == ["question", "warn"]
    assert_json_safe(runtime.snapshot())


def test_candidate_order_does_not_change_canonical_packet():
    left = AffordanceRuntime()
    right = AffordanceRuntime()
    candidates = [
        {"id": "b", "capability": "warn", "features": {"x": 1}},
        {"id": "a", "capability": "question"},
    ]
    first = left.set(
        "sera", candidates,
        allowed_capabilities=["warn", "question"],
        context={"scene": "gate"},
    )
    second = right.set(
        "sera", list(reversed(candidates)),
        allowed_capabilities=("question", "warn"),
        context={"scene": "gate"},
    )
    assert first == second
    assert left.snapshot() == right.snapshot()


def test_features_and_context_are_copy_isolated():
    runtime = base_runtime()
    features = {"nested": [1]}
    context = {"state": {"open": True}}
    packet = runtime.set(
        "sera",
        [{"id": "question_player", "capability": "question", "features": features}],
        allowed_capabilities=["question"],
        context=context,
    )
    features["nested"].append(2)
    context["state"]["open"] = False
    packet["candidates"][0]["features"]["nested"].append(3)
    assert runtime.current("sera")["candidates"][0]["features"] == {"nested": [1]}
    assert runtime.current("sera")["context"] == {"state": {"open": True}}


@pytest.mark.parametrize("bad", [None, "question", {"id": "question"}, {"question"}])
def test_candidate_collection_requires_list_or_tuple(bad):
    runtime = base_runtime()
    with pytest.raises(ValueError, match="must be a list or tuple"):
        runtime.set("sera", bad, allowed_capabilities=["question"])


@pytest.mark.parametrize("bad", [None, "question", {"question"}, {"q": True}])
def test_allowed_capabilities_requires_list_or_tuple(bad):
    runtime = base_runtime()
    with pytest.raises(ValueError, match="allowed capabilities must be a list or tuple"):
        runtime.set("sera", [], allowed_capabilities=bad)


def test_allowed_capabilities_reject_duplicate_normalized_ids():
    runtime = base_runtime()
    with pytest.raises(ValueError, match="duplicate normalized id"):
        runtime.set("sera", [], allowed_capabilities=["question", " question "])


@pytest.mark.parametrize("bad", [1, 1.2, None, ["question"]])
def test_candidate_entry_requires_string_or_dict(bad):
    runtime = base_runtime()
    with pytest.raises(ValueError, match="string id or dict"):
        runtime.set("sera", [bad], allowed_capabilities=["question"])


def test_candidate_dict_rejects_unknown_keys_and_missing_id():
    runtime = base_runtime()
    with pytest.raises(ValueError, match="unsupported keys"):
        runtime.set(
            "sera", [{"id": "q", "capability": "question", "extra": 1}],
            allowed_capabilities=["question"],
        )
    with pytest.raises(ValueError, match="missing required key: id"):
        runtime.set(
            "sera", [{"capability": "question"}],
            allowed_capabilities=["question"],
        )


def test_candidate_capability_must_be_registered():
    runtime = base_runtime()
    before = runtime.snapshot()
    with pytest.raises(ValueError, match="not registered for agent"):
        runtime.set(
            "sera", [{"id": "attack_player", "capability": "attack"}],
            allowed_capabilities=["question"],
        )
    assert runtime.snapshot() == before


def test_candidate_default_capability_uses_candidate_id():
    runtime = base_runtime()
    packet = runtime.set(
        "sera", [{"id": "question"}], allowed_capabilities=["question"],
    )
    assert packet["candidates"][0]["capability"] == "question"


def test_duplicate_candidate_ids_are_rejected_after_normalization():
    runtime = base_runtime()
    with pytest.raises(ValueError, match="duplicate normalized candidate id"):
        runtime.set(
            "sera",
            [
                {"id": "question_player", "capability": "question"},
                {"id": " question_player ", "capability": "question"},
            ],
            allowed_capabilities=["question"],
        )


@pytest.mark.parametrize(
    "candidate, message",
    [
        ({"id": "q", "capability": "question", "features": []}, "dict or None"),
        ({"id": "q", "capability": "question", "features": {1: "x"}}, "keys must be strings"),
        ({"id": "q", "capability": "question", "features": {" ": "x"}}, "keys must be non-empty"),
        ({"id": "q", "capability": "question", "features": {"x": 1, " x ": 2}}, "duplicate normalized key"),
        ({"id": "q", "capability": "question", "features": {"x": float("nan")}}, "finite numbers"),
        ({"id": "q", "capability": "question", "features": {"x": (1, 2)}}, "strict JSON-safe"),
    ],
)
def test_candidate_features_are_strict_json_safe(candidate, message):
    runtime = base_runtime()
    with pytest.raises(ValueError, match=message):
        runtime.set("sera", [candidate], allowed_capabilities=["question"])


def test_context_must_be_dict_and_strict_json_safe():
    runtime = base_runtime()
    with pytest.raises(ValueError, match="dict or None"):
        runtime.set("sera", [], allowed_capabilities=[], context=[])
    with pytest.raises(ValueError, match="finite numbers"):
        runtime.set(
            "sera", [], allowed_capabilities=[], context={"bad": float("inf")},
        )


def test_history_limit_reads_and_bounded_storage():
    runtime = AffordanceRuntime(history_limit=2)
    for index in range(3):
        runtime.set(
            "sera", ["question"], allowed_capabilities=["question"],
            context={"index": index},
        )
    assert [item["sequence"] for item in runtime.history("sera")] == [2, 3]
    assert runtime.history("sera", limit=1)[0]["sequence"] == 3
    assert runtime.history("sera", limit=0) == []
    for bad in (True, -1, 1.2, "1"):
        with pytest.raises(ValueError, match="non-negative integer or None"):
            runtime.history("sera", limit=bad)


def test_snapshot_roundtrip_and_deterministic_continuation():
    runtime = base_runtime()
    runtime.set(
        "sera", ["question"], allowed_capabilities=["question", "warn"],
        context={"step": 1},
    )
    snapshot = runtime.snapshot()
    restored = AffordanceRuntime.from_snapshot(copy.deepcopy(snapshot))
    assert restored.snapshot() == snapshot
    left = runtime.set(
        "sera", ["warn"], allowed_capabilities=["question", "warn"],
        context={"step": 2},
    )
    right = restored.set(
        "sera", ["warn"], allowed_capabilities=["question", "warn"],
        context={"step": 2},
    )
    assert left == right
    assert runtime.snapshot() == restored.snapshot()


def valid_snapshot():
    runtime = AffordanceRuntime(history_limit=3)
    runtime.set(
        "sera",
        [
            {"id": "question_player", "capability": "question"},
            {"id": "warn_player", "capability": "warn"},
        ],
        allowed_capabilities=["question", "warn"],
        context={"scene": "gate"},
    )
    runtime.set(
        "rowan", ["wait"], allowed_capabilities=["wait"], context={"scene": "shop"},
    )
    return runtime.snapshot()


def test_snapshot_rejects_non_dict_unknown_missing_and_bad_schema():
    with pytest.raises(ValueError, match="must be a dict"):
        AffordanceRuntime.from_snapshot([])
    snap = valid_snapshot()
    extra = copy.deepcopy(snap)
    extra["extra"] = 1
    with pytest.raises(ValueError, match="unsupported keys"):
        AffordanceRuntime.from_snapshot(extra)
    missing = copy.deepcopy(snap)
    missing.pop("history")
    with pytest.raises(ValueError, match="missing required keys"):
        AffordanceRuntime.from_snapshot(missing)
    schema = copy.deepcopy(snap)
    schema["schema_version"] = "9.9"
    with pytest.raises(ValueError, match="unsupported affordance snapshot schema"):
        AffordanceRuntime.from_snapshot(schema)


def test_snapshot_rejects_bad_top_level_numeric_and_history_shapes():
    snap = valid_snapshot()
    bad_limit = copy.deepcopy(snap)
    bad_limit["history_limit"] = 0
    with pytest.raises(ValueError, match="positive integer"):
        AffordanceRuntime.from_snapshot(bad_limit)
    bad_sequence = copy.deepcopy(snap)
    bad_sequence["sequence"] = -1
    with pytest.raises(ValueError, match="non-negative integer"):
        AffordanceRuntime.from_snapshot(bad_sequence)
    bad_history = copy.deepcopy(snap)
    bad_history["history"] = []
    with pytest.raises(ValueError, match="history must be a dict"):
        AffordanceRuntime.from_snapshot(bad_history)


def test_snapshot_rejects_non_string_history_key():
    snap = valid_snapshot()
    snap["history"][1] = snap["history"].pop("sera")
    with pytest.raises(ValueError, match="history keys must be strings"):
        AffordanceRuntime.from_snapshot(snap)


def test_snapshot_rejects_duplicate_normalized_agents_and_bad_record_lists():
    snap = valid_snapshot()
    duplicate = copy.deepcopy(snap)
    duplicate["history"][" sera "] = copy.deepcopy(duplicate["history"]["sera"])
    with pytest.raises(ValueError, match="duplicate normalized agent"):
        AffordanceRuntime.from_snapshot(duplicate)

    non_list = copy.deepcopy(snap)
    non_list["history"]["sera"] = {}
    with pytest.raises(ValueError, match="must be a list"):
        AffordanceRuntime.from_snapshot(non_list)

    empty = copy.deepcopy(snap)
    empty["history"]["sera"] = []
    with pytest.raises(ValueError, match="must not be empty"):
        AffordanceRuntime.from_snapshot(empty)

    too_many = copy.deepcopy(snap)
    too_many["history_limit"] = 1
    too_many["history"]["sera"] = too_many["history"]["sera"] * 2
    with pytest.raises(ValueError, match="exceeds history_limit"):
        AffordanceRuntime.from_snapshot(too_many)


def test_snapshot_rejects_record_shape_sequence_and_agent_errors():
    snap = valid_snapshot()
    invalid_keys = copy.deepcopy(snap)
    invalid_keys["history"]["sera"][0]["extra"] = 1
    with pytest.raises(ValueError, match="invalid keys"):
        AffordanceRuntime.from_snapshot(invalid_keys)

    zero_seq = copy.deepcopy(snap)
    zero_seq["history"]["sera"][0]["sequence"] = 0
    with pytest.raises(ValueError, match="positive integer"):
        AffordanceRuntime.from_snapshot(zero_seq)

    exceeds = copy.deepcopy(snap)
    exceeds["history"]["sera"][0]["sequence"] = exceeds["sequence"] + 1
    with pytest.raises(ValueError, match="exceeds snapshot sequence"):
        AffordanceRuntime.from_snapshot(exceeds)

    owner = copy.deepcopy(snap)
    owner["history"]["sera"][0]["agent"] = "rowan"
    with pytest.raises(ValueError, match="does not match history owner"):
        AffordanceRuntime.from_snapshot(owner)


def test_snapshot_rejects_candidate_shape_duplicate_and_noncanonical_order():
    snap = valid_snapshot()
    non_list = copy.deepcopy(snap)
    non_list["history"]["sera"][0]["candidates"] = {}
    with pytest.raises(ValueError, match="candidates must be a list"):
        AffordanceRuntime.from_snapshot(non_list)

    bad_keys = copy.deepcopy(snap)
    bad_keys["history"]["sera"][0]["candidates"][0]["extra"] = 1
    with pytest.raises(ValueError, match="invalid keys"):
        AffordanceRuntime.from_snapshot(bad_keys)

    duplicate = copy.deepcopy(snap)
    first = duplicate["history"]["sera"][0]["candidates"][0]
    duplicate["history"]["sera"][0]["candidates"][1] = copy.deepcopy(first)
    with pytest.raises(ValueError, match="duplicate id"):
        AffordanceRuntime.from_snapshot(duplicate)

    order = copy.deepcopy(snap)
    order["history"]["sera"][0]["candidates"].reverse()
    with pytest.raises(ValueError, match="canonically ordered"):
        AffordanceRuntime.from_snapshot(order)


def test_snapshot_rejects_stored_candidate_and_context_json_errors():
    snap = valid_snapshot()
    bad_feature = copy.deepcopy(snap)
    bad_feature["history"]["sera"][0]["candidates"][0]["features"] = []
    with pytest.raises(ValueError, match="dict or None"):
        AffordanceRuntime.from_snapshot(bad_feature)

    bad_context = copy.deepcopy(snap)
    bad_context["history"]["sera"][0]["context"] = []
    with pytest.raises(ValueError, match="dict or None"):
        AffordanceRuntime.from_snapshot(bad_context)


def test_snapshot_rejects_non_increasing_and_globally_duplicate_sequences():
    runtime = AffordanceRuntime(history_limit=4)
    runtime.set("sera", ["question"], allowed_capabilities=["question"])
    runtime.set("sera", ["question"], allowed_capabilities=["question"])
    runtime.set("rowan", ["wait"], allowed_capabilities=["wait"])
    snap = runtime.snapshot()

    non_increasing = copy.deepcopy(snap)
    non_increasing["history"]["sera"][1]["sequence"] = 1
    with pytest.raises(ValueError, match="sequence is invalid"):
        AffordanceRuntime.from_snapshot(non_increasing)

    duplicated = copy.deepcopy(snap)
    duplicated["history"]["rowan"][0]["sequence"] = 2
    with pytest.raises(ValueError, match="duplicated globally"):
        AffordanceRuntime.from_snapshot(duplicated)


def test_snapshot_requires_sequence_to_match_latest_record_or_zero_when_empty():
    snap = valid_snapshot()
    too_high = copy.deepcopy(snap)
    too_high["sequence"] += 1
    with pytest.raises(ValueError, match="latest affordance history sequence"):
        AffordanceRuntime.from_snapshot(too_high)

    empty = AffordanceRuntime().snapshot()
    empty["sequence"] = 1
    with pytest.raises(ValueError, match="empty affordance history"):
        AffordanceRuntime.from_snapshot(empty)
