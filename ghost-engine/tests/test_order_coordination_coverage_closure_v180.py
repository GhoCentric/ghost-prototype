
from __future__ import annotations

from copy import deepcopy
import json
import runpy
from pathlib import Path

import pytest

import ghost.examples.order_coordination as oc


def _two_items():
    runtime = oc.OrderCoordinator()
    first = runtime.add_item("add-1", "burger")["result"]["item"]["item_id"]
    second = runtime.add_item("add-2", "wrap")["result"]["item"]["item_id"]
    return runtime, first, second


def _open_ambiguity(runtime, first, second):
    return runtime.propose_modifier(
        "amb-1",
        "add_bacon",
        [first, second],
        "Put bacon on the other one.",
    )["result"]["ambiguity"]["ambiguity_id"]


def test_order_coordination_helper_validation_and_duplicate_paths():
    with pytest.raises(ValueError, match="JSON-safe"):
        oc._json_copy({"x": object()}, "x")
    with pytest.raises(ValueError, match="non-empty string"):
        oc._text("", "x")
    with pytest.raises(ValueError, match="positive integer"):
        oc._positive_int(True, "x")
    with pytest.raises(ValueError, match="non-negative integer"):
        oc._non_negative_int(-1, "x")
    with pytest.raises(ValueError, match="list or tuple"):
        oc._candidate_ids("item_001")
    with pytest.raises(ValueError, match="must not be empty"):
        oc._candidate_ids([])
    assert oc._candidate_ids(["a", "a", "b"]) == ["a", "b"]


def test_order_coordination_candidate_weight_validation():
    ids = ["a", "b"]
    assert oc._candidate_weights(ids, None) == {"a": 1.0, "b": 1.0}
    with pytest.raises(ValueError, match="dict or None"):
        oc._candidate_weights(ids, [])
    with pytest.raises(ValueError, match="match candidate"):
        oc._candidate_weights(ids, {"a": 1.0})
    with pytest.raises(ValueError, match="contain numbers"):
        oc._candidate_weights(ids, {"a": True, "b": 1.0})
    with pytest.raises(ValueError, match="finite and non-negative"):
        oc._candidate_weights(ids, {"a": float("inf"), "b": 1.0})
    with pytest.raises(ValueError, match="positive total"):
        oc._candidate_weights(ids, {"a": 0.0, "b": 0.0})
    weights = oc._candidate_weights(ids, {"a": 1.0, "b": 3.0})
    assert weights == {"a": 0.25, "b": 0.75}


def test_order_coordination_defensive_lookup_constructor_and_confirmation_blocks():
    with pytest.raises(ValueError, match="GhostAPI"):
        oc.OrderCoordinator(ghost=object())
    runtime = oc.OrderCoordinator()
    assert "no_items" in runtime.status()["blockers"]
    with pytest.raises(ValueError, match="unknown order item"):
        runtime._item("missing")
    with pytest.raises(ValueError, match="unknown ambiguity"):
        runtime._ambiguity("missing")
    with pytest.raises(oc.OrderSubmissionBlocked, match="no_items"):
        runtime.confirm_order("confirm-empty", "yes")


def test_order_coordination_resolve_rejects_resolved_non_candidate_and_bad_dominant(monkeypatch):
    runtime, first, second = _two_items()
    ambiguity_id = _open_ambiguity(runtime, first, second)
    with pytest.raises(ValueError, match="not an ambiguity candidate"):
        runtime.resolve_ambiguity("bad-target", ambiguity_id, "missing", "third")
    runtime.resolve_ambiguity("resolve", ambiguity_id, second, "second")
    with pytest.raises(ValueError, match="already resolved"):
        runtime.resolve_ambiguity("again", ambiguity_id, second, "second")

    runtime2, first2, second2 = _two_items()
    ambiguity2 = _open_ambiguity(runtime2, first2, second2)
    original = runtime2.ghost.evaluate_beliefs

    def wrong_dominant(**kwargs):
        packet = original(**kwargs)
        packet["dimensions"]["target"]["dominant_candidate"] = first2
        return packet

    monkeypatch.setattr(runtime2.ghost, "evaluate_beliefs", wrong_dominant)
    with pytest.raises(RuntimeError, match="did not resolve"):
        runtime2.resolve_ambiguity("wrong-dominant", ambiguity2, second2, "second")


def test_order_coordination_correction_validation_and_existing_target_modifier():
    runtime, first, second = _two_items()
    runtime.propose_modifier("m1", "add_bacon", [first], "first")
    runtime.propose_modifier("m2", "add_bacon", [second], "second")

    with pytest.raises(ValueError, match="source and target must differ"):
        runtime.correct_modifier("same", "add_bacon", first, first, "same")

    result = runtime.correct_modifier(
        "move",
        "add_bacon",
        first,
        second,
        "move it",
    )
    assert result["result"]["outcome"] == "modifier_corrected"
    assert runtime.order()["items"][1]["modifiers"] == ["add_bacon"]

    with pytest.raises(ValueError, match="does not contain modifier"):
        runtime.correct_modifier("missing-mod", "no_onion", first, second, "move")


def _base_snapshot():
    runtime, first, second = _two_items()
    ambiguity = _open_ambiguity(runtime, first, second)
    return runtime, ambiguity, runtime.snapshot()


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda s: s.pop("ledger"), "unsupported keys"),
        (lambda s: s.__setitem__("schema_version", "bad"), "unsupported order coordination schema"),
        (lambda s: s.__setitem__("item_sequence", -1), "non-negative integer"),
        (lambda s: s.__setitem__("confirmed_revision", s["revision"] + 1), "cannot exceed"),
        (lambda s: s.__setitem__("submitted", 1), "submitted must be a bool"),
        (lambda s: s.__setitem__("items", {}), "items must be a list"),
        (lambda s: s.__setitem__("operations", []), "operations must be a dict"),
    ],
)
def test_order_coordination_snapshot_top_level_validation(mutator, message):
    _, _, snap = _base_snapshot()
    mutator(snap)
    with pytest.raises(ValueError, match=message):
        oc.OrderCoordinator.from_snapshot(snap)


def test_order_coordination_snapshot_item_validation_matrix():
    _, _, base = _base_snapshot()

    cases = []
    s = deepcopy(base); s["items"][0] = {"x": 1}; cases.append((s, "item schema"))
    s = deepcopy(base); s["items"].append(deepcopy(s["items"][0])); s["item_sequence"] += 1; cases.append((s, "ids must be unique"))
    s = deepcopy(base); s["items"][0]["modifiers"] = "x"; cases.append((s, "modifiers must be a list"))
    s = deepcopy(base); s["items"][0]["modifiers"] = ["x", "x"]; cases.append((s, "modifiers must be unique"))
    s = deepcopy(base); s["item_sequence"] = 1; cases.append((s, "item sequence is behind"))

    for snap, message in cases:
        with pytest.raises(ValueError, match=message):
            oc.OrderCoordinator.from_snapshot(snap)
    assert len(cases) == 5


def test_order_coordination_snapshot_ambiguity_validation_matrix():
    runtime, ambiguity_id, base = _base_snapshot()
    runtime.resolve_ambiguity("resolve", ambiguity_id, runtime.order()["items"][1]["item_id"], "second")
    resolved = runtime.snapshot()

    cases = []
    s = deepcopy(base); s["ambiguities"][0] = {"x": 1}; cases.append((s, "ambiguity schema"))
    s = deepcopy(base); s["ambiguities"][0]["candidate_item_ids"] = ["missing"]; cases.append((s, "unknown order item"))
    s = deepcopy(base); s["ambiguities"][0]["observation_ids"] = "x"; cases.append((s, "observation ids must be a list"))
    s = deepcopy(base); s["ambiguities"][0]["chosen_item_id"] = "item_001"; cases.append((s, "unresolved ambiguity has resolution data"))
    s = deepcopy(resolved); s["ambiguities"][0]["chosen_item_id"] = "missing"; cases.append((s, "resolved ambiguity chose non-candidate"))
    s = deepcopy(base); s["ambiguities"][0]["status"] = "weird"; cases.append((s, "status is invalid"))
    s = deepcopy(base); s["ambiguity_sequence"] = 0; cases.append((s, "ambiguity sequence is behind"))

    for snap, message in cases:
        with pytest.raises(ValueError, match=message):
            oc.OrderCoordinator.from_snapshot(snap)
    assert len(cases) == 7


def test_order_coordination_snapshot_ledger_operation_and_submission_validation():
    runtime, ambiguity_id, base = _base_snapshot()
    cases = []

    s = deepcopy(base); s["ledger"][0] = {"x": 1}; cases.append((s, "ledger record schema"))
    s = deepcopy(base); s["ledger"][0]["sequence"] = 99; cases.append((s, "ledger sequence"))
    s = deepcopy(base); s["ledger"][0]["revision"] = s["revision"] + 1; cases.append((s, "ledger revision exceeds"))
    s = deepcopy(base); s["ledger"][0]["data"] = []; cases.append((s, "ledger data must be a dict"))

    operation_id = next(iter(base["operations"]))
    s = deepcopy(base); s["operations"][operation_id] = {"x": 1}; cases.append((s, "operation schema"))
    s = deepcopy(base); s["operations"][operation_id]["signature"] = []; cases.append((s, "operation signature must be a dict"))
    s = deepcopy(base); s["operations"][operation_id]["result"] = []; cases.append((s, "operation result must be a dict"))

    s = deepcopy(base); s["submitted"] = True; s["confirmed_revision"] = None; cases.append((s, "must have current confirmation"))
    s = deepcopy(base); s["submitted"] = True; s["confirmed_revision"] = s["revision"]; cases.append((s, "cannot have unresolved ambiguity"))

    for snap, message in cases:
        with pytest.raises(ValueError, match=message):
            oc.OrderCoordinator.from_snapshot(snap)
    assert len(cases) == 9


def test_order_coordination_snapshot_non_dict_and_status_after_submission():
    with pytest.raises(ValueError, match="must be a dict"):
        oc.OrderCoordinator.from_snapshot([])

    runtime, _, _ = _two_items()
    runtime.confirm_order("confirm", "yes")
    runtime.submit("submit")
    status = runtime.status()
    assert status["blockers"] == ["already_submitted"]
    with pytest.raises(RuntimeError, match="immutable"):
        runtime.add_item("after", "coffee")


def test_order_coordination_remaining_duplicate_and_lookup_branches():
    runtime, first, second = _two_items()
    first_apply = runtime.propose_modifier("direct-1", "no_onion", [first], "first")
    repeated = runtime.propose_modifier("direct-2", "no_onion", [first], "first again")
    assert first_apply["result"]["outcome"] == "modifier_applied"
    assert repeated["result"]["outcome"] == "modifier_already_present"

    amb1 = runtime.propose_modifier("amb-a", "x", [first, second], "other")["result"]["ambiguity"]["ambiguity_id"]
    amb2 = runtime.propose_modifier("amb-b", "y", [first, second], "other")["result"]["ambiguity"]["ambiguity_id"]
    assert runtime._ambiguity(amb2)["ambiguity_id"] == amb2

    runtime.propose_modifier("existing-second", "add_bacon", [second], "second")
    amb3 = runtime.propose_modifier("amb-c", "add_bacon", [first, second], "other")["result"]["ambiguity"]["ambiguity_id"]
    resolved = runtime.resolve_ambiguity("amb-c-resolve", amb3, second, "second")
    assert resolved["result"]["outcome"] == "ambiguity_resolved"


import ghost.examples.order_coordination_benchmark as ob


def _scenario(family=ob.FAMILY_CLEAN, scenario_id="case"):
    return ob.BenchmarkScenario(
        scenario_id=scenario_id,
        family=family,
        first_product="burger",
        second_product="wrap",
        modifier="add_bacon",
        first_quantity=1,
        expected_modifier_target=(
            1 if family in {ob.FAMILY_CORRECTION, ob.FAMILY_STALE} else 2
        ),
    )


def _summary_report():
    metrics = {key: 0 for key in ob.METRIC_KEYS}
    return {
        "scenario_count": 1,
        "clean_control_count": 1,
        "injected_fault_count": 0,
        "modes": {
            "transcript_only": {"metrics": dict(metrics)},
            "ghost_backed": {"metrics": dict(metrics)},
        },
    }


def test_order_benchmark_matrix_defensive_guards(monkeypatch):
    monkeypatch.setattr(ob, "FAMILY_ORDER", (ob.FAMILY_CLEAN,))
    with pytest.raises(RuntimeError, match="100 scenarios"):
        ob.build_scenarios()

    monkeypatch.setattr(
        ob,
        "FAMILY_ORDER",
        (
            ob.FAMILY_CLEAN,
            ob.FAMILY_AMBIGUOUS,
            ob.FAMILY_AMBIGUOUS,
            ob.FAMILY_CORRECTION,
            ob.FAMILY_STALE,
            ob.FAMILY_DUPLICATE,
            ob.FAMILY_QUANTITY,
        ),
    )
    with pytest.raises(RuntimeError, match="ids must be unique"):
        ob.build_scenarios()


def test_order_benchmark_transcript_runtime_defensive_paths():
    runtime = ob._TranscriptOnlyRuntime()
    first = runtime.add_item("burger")
    second = runtime.add_item("wrap")
    runtime.merge_modifier_target("x", first)
    runtime.merge_modifier_target("x", first)
    runtime.set_modifier_target("x", second)
    assert runtime.order()["items"][1]["modifiers"] == ["x"]
    with pytest.raises(ValueError, match="unknown item"):
        runtime._item("missing")

    bad = _scenario("unsupported")
    with pytest.raises(ValueError, match="unsupported scenario family"):
        ob._run_transcript_only(bad)


def test_order_benchmark_ghost_submit_success_and_unsupported_family():
    runtime = oc.OrderCoordinator()
    runtime.add_item("a", "burger")
    runtime.confirm_order("c", "yes")
    assert ob._ghost_submit(runtime, "s") is True

    with pytest.raises(ValueError, match="unsupported scenario family"):
        ob._run_ghost_backed(_scenario("unsupported"))


def test_order_benchmark_forced_unsafe_acceptance_flags(monkeypatch):
    monkeypatch.setattr(ob, "_ghost_submit", lambda runtime, operation_id: True)
    ambiguous = ob._run_ghost_backed(_scenario(ob.FAMILY_AMBIGUOUS, "amb"))
    stale = ob._run_ghost_backed(_scenario(ob.FAMILY_STALE, "stale"))
    contradiction = ob._run_ghost_backed(_scenario(ob.FAMILY_CONTRADICTION, "contra"))
    assert ambiguous["unresolved_ambiguity_submitted"] is True
    assert stale["stale_confirmation_accepted"] is True
    assert contradiction["unresolved_ambiguity_submitted"] is True


def test_order_benchmark_skips_final_confirmation_with_fake_runtime(monkeypatch):
    class FakeRuntime:
        def propose_modifier(self, *args, **kwargs):
            return {"result": {}}

        def status(self):
            return {"confirmed_revision": 1, "revision": 1}

        def confirm_order(self, *args, **kwargs):
            raise AssertionError("should not confirm")

        def submit(self, operation_id):
            return {
                "result": {
                    "order": {
                        "items": [
                            {"item_id": "item_001", "product": "burger", "quantity": 1, "modifiers": []},
                            {"item_id": "item_002", "product": "wrap", "quantity": 1, "modifiers": ["add_bacon"]},
                        ]
                    }
                }
            }

        def snapshot(self):
            return {"ghost": {"epistemic": {"records": []}}, "ledger": []}

    monkeypatch.setattr(
        ob,
        "_base_ghost_runtime",
        lambda scenario: (FakeRuntime(), "item_001", "item_002"),
    )
    result = ob._run_ghost_backed(_scenario(ob.FAMILY_CLEAN, "skip-confirm"))
    assert result["submission_count"] == 1


def test_order_benchmark_duplicate_replay_mismatch_and_extra_accept(monkeypatch):
    class MismatchRuntime:
        def propose_modifier(self, *args, **kwargs):
            return {"result": {}}

        def status(self):
            return {"confirmed_revision": 1, "revision": 1}

        def submit(self, operation_id):
            count = getattr(self, "count", 0) + 1
            self.count = count
            return {
                "marker": count,
                "result": {
                    "order": {
                        "items": [
                            {"item_id": "item_001", "product": "burger", "quantity": 1, "modifiers": []},
                            {"item_id": "item_002", "product": "wrap", "quantity": 1, "modifiers": ["add_bacon"]},
                        ]
                    }
                },
            }

        def snapshot(self):
            return {"ghost": {"epistemic": {"records": []}}, "ledger": []}

    monkeypatch.setattr(
        ob,
        "_base_ghost_runtime",
        lambda scenario: (MismatchRuntime(), "item_001", "item_002"),
    )
    with pytest.raises(RuntimeError, match="idempotent replay"):
        ob._run_ghost_backed(_scenario(ob.FAMILY_DUPLICATE, "mismatch"))

    class AcceptRuntime(MismatchRuntime):
        def submit(self, operation_id):
            if operation_id.endswith(":submit"):
                packet = {
                    "result": {
                        "order": {
                            "items": [
                                {"item_id": "item_001", "product": "burger", "quantity": 1, "modifiers": []},
                                {"item_id": "item_002", "product": "wrap", "quantity": 1, "modifiers": ["add_bacon"]},
                            ]
                        }
                    }
                }
                return packet
            return {
                "result": {
                    "order": {
                        "items": [
                            {"item_id": "item_001", "product": "burger", "quantity": 1, "modifiers": []},
                            {"item_id": "item_002", "product": "wrap", "quantity": 1, "modifiers": ["add_bacon"]},
                        ]
                    }
                }
            }

    monkeypatch.setattr(
        ob,
        "_base_ghost_runtime",
        lambda scenario: (AcceptRuntime(), "item_001", "item_002"),
    )
    accepted = ob._run_ghost_backed(_scenario(ob.FAMILY_DUPLICATE, "accept"))
    assert accepted["submission_count"] == 2


def test_order_benchmark_aggregate_schema_guard(monkeypatch):
    monkeypatch.setattr(ob, "METRIC_KEYS", ("different",))
    with pytest.raises(RuntimeError, match="schema drifted"):
        ob._aggregate([])


def test_order_benchmark_print_summary_and_main_branches(monkeypatch, tmp_path, capsys):
    report = _summary_report()
    ob.print_summary(report)
    assert "Transcript-only" in capsys.readouterr().out

    monkeypatch.setattr(ob, "run_benchmark", lambda: report)
    no_json = ob.main(["--no-json"])
    destination = tmp_path / "report.json"
    with_json = ob.main(["--json", str(destination)])
    assert no_json == report
    assert with_json == report
    assert destination.is_file()


def test_order_benchmark_main_guard_executes(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["order_coordination_benchmark.py", "--no-json"])
    result = runpy.run_path(
        str(local_benchmark_path := Path(__file__).resolve().parents[1] / "ghost" / "examples" / "order_coordination_benchmark.py"),
        run_name="__main__",
    )
    assert "main" in result


import os
import ghost.examples.order_coordination_live_benchmark as ol


def _live_scenario(family=ob.FAMILY_CLEAN):
    return next(
        s for s in ob.build_scenarios()
        if s.family == family
    )


def _valid_live_packet(scenario=None):
    scenario = scenario or _live_scenario()
    transcript = ol.build_transcript(scenario)
    return scenario, transcript, ol._ideal_mock_packet(scenario, transcript)


def test_live_validation_helpers_transcript_and_selection(monkeypatch):
    with pytest.raises(ValueError, match="JSON-safe"):
        ol._json_copy({"x": object()}, "x")
    with pytest.raises(ValueError, match="positive integer"):
        ol._positive_int(0, "x")
    with pytest.raises(ValueError, match="numeric"):
        ol._finite_probability(True, "p")
    with pytest.raises(ValueError, match="between 0 and 1"):
        ol._finite_probability(2.0, "p")
    with pytest.raises(ValueError, match="unsupported scenario family"):
        ol.build_transcript(_scenario("unsupported"))

    monkeypatch.setattr(
        ol,
        "build_scenarios",
        lambda: [_scenario("not-in-family", "orphan")],
    )
    assert ol.select_scenarios(limit=1) == []


def test_live_turn_map_and_turn_reference_validation():
    with pytest.raises(ValueError, match="turn ids must be unique"):
        ol._turn_map([
            {"turn_id": "t01", "source": "customer", "text": "a"},
            {"turn_id": "t01", "source": "customer", "text": "b"},
        ])

    turns = {"t01": {"source": "customer", "text": "a"}}
    with pytest.raises(ValueError, match="non-empty string"):
        ol._normalize_turn_reference("", turns)
    with pytest.raises(ValueError, match="unknown turn"):
        ol._normalize_turn_reference("nonsense", turns)
    with pytest.raises(ValueError, match="unknown turn"):
        ol._normalize_turn_reference("t99", turns)
    assert ol._normalize_turn_reference("t01", turns)[0] == "t01"


def test_live_final_order_validation_matrix():
    scenario, _, packet = _valid_live_packet()
    valid = packet["final_order"]

    cases = []
    cases.append(([], "schema is invalid"))
    cases.append(({"items": []}, "exactly two items"))
    s = deepcopy(valid); s["items"][0] = {"x": 1}; cases.append((s, "item schema"))
    s = deepcopy(valid); s["items"][0]["item_id"] = "bad"; cases.append((s, "item ids are invalid"))
    s = deepcopy(valid); s["items"][1]["item_id"] = s["items"][0]["item_id"]; cases.append((s, "item ids are invalid"))
    s = deepcopy(valid); s["items"][0]["product"] = ""; cases.append((s, "product is invalid"))
    s = deepcopy(valid); s["items"][0]["quantity"] = 0; cases.append((s, "positive integer"))
    s = deepcopy(valid); s["items"][0]["modifiers"] = "x"; cases.append((s, "modifiers must be a list"))
    s = deepcopy(valid); s["items"][0]["modifiers"] = ["", "x"]; cases.append((s, "modifier is invalid"))

    for value, message in cases:
        with pytest.raises(ValueError, match=message):
            ol._validate_final_order(value)

    s = deepcopy(valid)
    s["items"][0]["modifiers"] = ["x", "x"]
    normalized = ol._validate_final_order(s)
    assert normalized["items"][0]["modifiers"] == ["x"]


def test_live_final_order_missing_required_id_branch(monkeypatch):
    scenario, _, packet = _valid_live_packet()
    valid = deepcopy(packet["final_order"])
    monkeypatch.setattr(ol, "VALID_ITEM_IDS", {"item_001", "item_002", "item_003"})
    with pytest.raises(ValueError, match="missing a required item"):
        ol._validate_final_order(valid)


def test_live_model_packet_top_level_validation():
    scenario = _live_scenario()
    transcript = ol.build_transcript(scenario)
    with pytest.raises(ValueError, match="empty"):
        ol.parse_model_packet("", scenario, transcript)
    with pytest.raises(ValueError, match="not valid JSON"):
        ol.parse_model_packet("{", scenario, transcript)
    with pytest.raises(ValueError, match="schema is invalid"):
        ol.parse_model_packet(json.dumps({"events": []}), scenario, transcript)
    with pytest.raises(ValueError, match="at most 64"):
        ol.parse_model_packet(
            json.dumps({"events": [{}] * 65, "final_order": ol._fallback_order(scenario)}),
            scenario,
            transcript,
        )
    assert transcript[0]["turn_id"] == "t01"


def test_live_model_event_validation_matrix():
    scenario, transcript, packet = _valid_live_packet()
    base = deepcopy(packet["events"][0])

    cases = []

    event = {"x": 1}
    cases.append((event, "schema is invalid"))

    event = deepcopy(base); event["event_type"] = "bogus"; cases.append((event, "unsupported event type"))
    event = deepcopy(base); event["modifier"] = None; cases.append((event, "modifier must be a string"))
    event = deepcopy(base); event["item_id"] = None; cases.append((event, "item_id must be a string"))
    event = deepcopy(base); event["item_id"] = "item_999"; cases.append((event, "item_id is invalid"))
    event = deepcopy(base); event["candidate_item_ids"] = "x"; cases.append((event, "must be a list"))
    event = deepcopy(base); event["candidate_item_ids"] = ["item_999"]; cases.append((event, "candidate item id is invalid"))
    event = deepcopy(base); event["quantity"] = True; cases.append((event, "quantity must be an integer"))
    event = deepcopy(base); event["quantity"] = -1; cases.append((event, "quantity must be non-negative"))
    event = deepcopy(base); event["confidence"] = 2.0; cases.append((event, "between 0 and 1"))
    event = deepcopy(base); event["is_correction"] = 1; cases.append((event, "is_correction must be a bool"))
    event = deepcopy(base); event["note"] = None; cases.append((event, "note must be a string"))

    for event, message in cases:
        candidate = {"events": [event], "final_order": packet["final_order"]}
        with pytest.raises(ValueError, match=message):
            ol.parse_model_packet(json.dumps(candidate), scenario, transcript)

    event = deepcopy(base)
    event["candidate_item_ids"] = ["item_002", "item_002"]
    parsed = ol.parse_model_packet(
        json.dumps({"events": [event], "final_order": packet["final_order"]}),
        scenario,
        transcript,
    )
    assert parsed["events"][0]["candidate_item_ids"] == ["item_002"]


def test_live_apply_transcript_only_unresolved_submit():
    scenario = _live_scenario(ob.FAMILY_AMBIGUOUS)
    transcript = ol.build_transcript(scenario)
    packet = ol._ideal_mock_packet(scenario, transcript)
    # Remove the customer clarification so the ambiguity remains open.
    packet["events"] = [packet["events"][0], packet["events"][-1]]
    parsed = ol.parse_model_packet(json.dumps(packet), scenario, transcript)
    result = ol.apply_transcript_only(scenario, parsed)
    assert result["unresolved_ambiguity_submitted"] is True


def test_live_unresolved_lookup_and_submission_categories():
    runtime = oc.OrderCoordinator()
    first = runtime.add_item("a", "burger")["result"]["item"]["item_id"]
    second = runtime.add_item("b", "wrap")["result"]["item"]["item_id"]
    runtime.propose_modifier("amb1", "x", [first, second], "other")
    runtime.propose_modifier("amb2", "y", [first, second], "other")
    found = ol._unresolved_for_modifier(runtime, "y")
    assert found["modifier"] == "y"

    assert ol._submission_block_category(["already_submitted"]) == "duplicate_submission_blocks"
    assert ol._submission_block_category(["unresolved_ambiguity:1"]) == "unresolved_ambiguity_submission_blocks"
    assert ol._submission_block_category(["current_revision_not_confirmed"]) == "stale_confirmation_submission_blocks"
    assert ol._submission_block_category(["something"]) == "other_guardrail_blocks"


def _event_for(transcript, turn_id, event_type, **updates):
    source_turn = next(t for t in transcript if t["turn_id"] == turn_id)
    event = {
        "turn_id": turn_id,
        "raw_turn_id": turn_id,
        "turn_id_repaired": False,
        "event_type": event_type,
        "modifier": "",
        "candidate_item_ids": [],
        "item_id": "",
        "quantity": 0,
        "confidence": 1.0,
        "is_correction": False,
        "note": "",
        "source": source_turn["source"],
        "source_text": source_turn["text"],
        "turn_rank": [t["turn_id"] for t in transcript].index(turn_id),
    }
    event.update(updates)
    return event


def test_live_apply_ghost_invalid_target_and_item_id_fallback():
    scenario = _live_scenario()
    transcript = ol.build_transcript(scenario)
    invalid = _event_for(transcript, "t02", "modifier_claim", modifier=scenario.modifier)
    fallback = _event_for(
        transcript,
        "t02",
        "modifier_claim",
        modifier=scenario.modifier,
        item_id="item_002",
    )
    packet = {"events": [invalid, fallback], "final_order": ol._fallback_order(scenario)}
    result = ol.apply_ghost_backed(scenario, packet, operation_prefix="invalid-target")
    assert result["intervention_counts"]["invalid_modifier_target_blocks"] == 1
    assert any(d["decision"] == "modifier_applied_or_confirmed" for d in result["decision_log"])


def test_live_apply_ghost_ambiguity_already_open_and_modifier_exception():
    scenario = _live_scenario(ob.FAMILY_AMBIGUOUS)
    transcript = ol.build_transcript(scenario)
    multi1 = _event_for(
        transcript, "t02", "modifier_claim",
        modifier=scenario.modifier,
        candidate_item_ids=["item_001", "item_002"],
    )
    multi2 = deepcopy(multi1)
    multi2["turn_id"] = "t04"
    multi2["raw_turn_id"] = "t04"
    multi2["source"] = "customer"
    multi2["source_text"] = next(t["text"] for t in transcript if t["turn_id"] == "t04")
    multi2["turn_rank"] = 3
    packet = {"events": [multi1, multi2], "final_order": ol._fallback_order(scenario)}
    result = ol.apply_ghost_backed(scenario, packet, operation_prefix="double-amb")
    assert any(d["decision"] == "ambiguity_already_open" for d in result["decision_log"])

    clean = _live_scenario()
    clean_t = ol.build_transcript(clean)
    events = [
        _event_for(clean_t, "t02", "modifier_claim", modifier=clean.modifier, candidate_item_ids=["item_002"]),
        _event_for(clean_t, "t04", "confirmation"),
        _event_for(clean_t, "t05", "submit_request"),
        _event_for(clean_t, "t02", "modifier_claim", modifier=clean.modifier, candidate_item_ids=["item_001"]),
    ]
    result2 = ol.apply_ghost_backed(clean, {"events": events, "final_order": ol._fallback_order(clean)}, operation_prefix="after-submit")
    assert any("modifier_proposal_blocked" in d["decision"] for d in result2["decision_log"])


def test_live_apply_ghost_quantity_confirmation_and_context_branches():
    scenario = _live_scenario()
    transcript = ol.build_transcript(scenario)
    events = [
        _event_for(transcript, "t01", "quantity_claim", item_id="item_001", quantity=99),
        _event_for(transcript, "t01", "handoff_summary"),
    ]
    result = ol.apply_ghost_backed(
        scenario,
        {"events": events, "final_order": ol._fallback_order(scenario)},
        operation_prefix="quantity-context",
    )
    assert result["intervention_counts"]["post_intake_quantity_rejections"] == 1
    assert any(d["decision"] == "recorded_customer_context" for d in result["decision_log"])

    ambiguous = _live_scenario(ob.FAMILY_AMBIGUOUS)
    amb_t = ol.build_transcript(ambiguous)
    amb_events = [
        _event_for(amb_t, "t02", "modifier_claim", modifier=ambiguous.modifier, candidate_item_ids=["item_001", "item_002"]),
        _event_for(amb_t, "t05", "confirmation"),
    ]
    blocked = ol.apply_ghost_backed(
        ambiguous,
        {"events": amb_events, "final_order": ol._fallback_order(ambiguous)},
        operation_prefix="confirm-block",
    )
    assert any(d["decision"] == "confirmation_blocked" for d in blocked["decision_log"])

    clean_t = ol.build_transcript(scenario)
    after_submit = [
        _event_for(clean_t, "t02", "modifier_claim", modifier=scenario.modifier, candidate_item_ids=["item_002"]),
        _event_for(clean_t, "t04", "confirmation"),
        _event_for(clean_t, "t05", "submit_request"),
        _event_for(clean_t, "t04", "confirmation"),
    ]
    after = ol.apply_ghost_backed(
        scenario,
        {"events": after_submit, "final_order": ol._fallback_order(scenario)},
        operation_prefix="confirm-after",
    )
    assert any(d["decision"] == "confirmation_after_submission_blocked" for d in after["decision_log"])


def test_live_apply_ghost_unknown_intervention_category(monkeypatch):
    scenario = _live_scenario()
    transcript = ol.build_transcript(scenario)
    event = _event_for(transcript, "t02", "modifier_claim", modifier=scenario.modifier)
    monkeypatch.setattr(ol, "_empty_intervention_counts", lambda: {})
    with pytest.raises(RuntimeError, match="unknown intervention category"):
        ol.apply_ghost_backed(
            scenario,
            {"events": [event], "final_order": ol._fallback_order(scenario)},
            operation_prefix="bad-category",
        )


def test_live_runtime_aggregates_and_mock_defensive_paths():
    assert ol._percentile([], 0.5) == 0.0
    calls = [
        {
            "latency_seconds": 1.0,
            "parse_error": None,
            "parser_repairs": [],
            "raw_final_order_valid": True,
            "measured_cost": {
                "input_tokens": 1,
                "cached_input_tokens": 2,
                "output_tokens": 3,
                "reasoning_tokens": 4,
                "total_tokens": 10,
                "total_cost": 0.25,
            },
        }
    ]
    agg = ol._aggregate_runtime(calls)
    assert agg["usage"]["total_tokens"] == 10
    assert agg["usage"]["total_cost"] == 0.25

    client = ol.DeterministicOrderBenchmarkMockClient()
    with pytest.raises(RuntimeError, match="missing input packet"):
        client("bad prompt", config=ol._config_for_cli(model="x", max_output_tokens=10))

    with pytest.raises(ValueError, match="unsupported scenario family"):
        ol._ideal_mock_packet(_scenario("unsupported"), [])

    recovered, valid = ol._recover_valid_final_order("{}", _live_scenario())
    assert valid is False
    assert recovered["items"][0]["item_id"] == "item_001"

    class Nameless:
        pass

    assert ol._client_name(Nameless()) == "Nameless"


def test_live_run_benchmark_argument_validation():
    config = ol._config_for_cli(model="x", max_output_tokens=10)
    scenario = _live_scenario()
    with pytest.raises(ValueError, match="client must be callable"):
        ol.run_live_benchmark(client=None, config=config, scenarios=[scenario])
    with pytest.raises(ValueError, match="config must be"):
        ol.run_live_benchmark(client=lambda *a, **k: "", config=object(), scenarios=[scenario])
    with pytest.raises(ValueError, match="must not be empty"):
        ol.run_live_benchmark(client=lambda *a, **k: "", config=config, scenarios=[])


def test_live_run_benchmark_client_exception_and_summary(capsys):
    class RaisingClient:
        def __call__(self, prompt, *, config):
            raise LookupError("boom")

    report = ol.run_live_benchmark(
        client=RaisingClient(),
        config=ol._config_for_cli(model="x", max_output_tokens=10),
        scenarios=[_live_scenario()],
        trials=1,
        clock=iter([1.0, 1.25]).__next__,
    )
    assert "LookupError: boom" == report["calls"][0]["parse_error"]
    ol.print_summary(report)
    out = capsys.readouterr().out
    assert "GHOST LIVE ORDER COORDINATION BENCHMARK" in out
    assert "intervention categories" in out


def test_live_main_mock_real_gate_and_real_client_branch(monkeypatch, tmp_path):
    mock_out = tmp_path / "mock.json"
    mock_report = ol.main([
        "--mock",
        "--limit", "1",
        "--trials", "1",
        "--output", str(mock_out),
    ])
    assert mock_out.is_file()
    assert mock_report["runtime"]["call_count"] == 1

    monkeypatch.setenv(ol.REAL_LLM_ENV, "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        ol.main(["--limit", "1", "--trials", "1", "--output", str(tmp_path / "no-key.json")])

    class FakeReal(ol.DeterministicOrderBenchmarkMockClient):
        provider_name = "fake-real"

    fake = FakeReal()
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setattr(ol, "OpenAIResponsesClient", lambda: fake)
    real_out = tmp_path / "real.json"
    report = ol.main([
        "--limit", "1",
        "--trials", "1",
        "--output", str(real_out),
    ])
    assert real_out.is_file()
    assert report["provider"] == "fake-real"


def test_live_main_guard_executes(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "order_coordination_live_benchmark.py",
            "--mock",
            "--limit", "1",
            "--trials", "1",
            "--output", str(tmp_path / "guard.json"),
        ],
    )
    path = Path(__file__).resolve().parents[1] / "ghost" / "examples" / "order_coordination_live_benchmark.py"
    result = runpy.run_path(str(path), run_name="__main__")
    assert "main" in result
    assert (tmp_path / "guard.json").is_file()


import ghost.examples.order_coordination_report_replay as orr


def _replay_source(limit=1):
    scenarios = ob.build_scenarios()[:limit]
    report = ol.run_live_benchmark(
        client=ol.DeterministicOrderBenchmarkMockClient(),
        config=ol._config_for_cli(model="mock", max_output_tokens=100),
        scenarios=scenarios,
        trials=1,
        clock=lambda: 1.0,
    )
    return report


def test_replay_helpers_and_default_output_path(monkeypatch, tmp_path):
    with pytest.raises(ValueError, match="JSON-safe"):
        orr._json_copy({"x": object()}, "x")

    real_path = Path

    class MissingDownload:
        def is_dir(self):
            return False

    def fake_missing_path(value):
        if str(value) == "/storage/emulated/0/Download":
            return MissingDownload()
        return real_path(value)

    monkeypatch.setattr(orr, "Path", fake_missing_path)
    assert orr._default_output_path() == orr.DEFAULT_OUTPUT_NAME

    def fake_path(value):
        if str(value) == "/storage/emulated/0/Download":
            return tmp_path
        return real_path(value)

    monkeypatch.setattr(orr, "Path", fake_path)
    assert orr._default_output_path() == str(tmp_path / orr.DEFAULT_OUTPUT_NAME)

    with pytest.raises(ValueError, match="positive integer"):
        orr._positive_int(0, "x")


def test_replay_load_source_validation(tmp_path):
    with pytest.raises(ValueError, match="could not read"):
        orr._load_source(tmp_path / "missing.json")

    bad_utf = tmp_path / "bad_utf.json"
    bad_utf.write_bytes(b"\xff")
    with pytest.raises(ValueError, match="not valid UTF-8 JSON"):
        orr._load_source(bad_utf)

    bad_json = tmp_path / "bad_json.json"
    bad_json.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid UTF-8 JSON"):
        orr._load_source(bad_json)

    list_json = tmp_path / "list.json"
    list_json.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="root must be an object"):
        orr._load_source(list_json)

    good = tmp_path / "good.json"
    good.write_text('{"x":1}', encoding="utf-8")
    decoded, digest = orr._load_source(good)
    assert decoded == {"x": 1}
    assert len(digest) == 64


def test_replay_source_report_call_validation_matrix():
    base = _replay_source()
    cases = []
    s = deepcopy(base); s["calls"] = []; cases.append((s, "non-empty list"))
    s = deepcopy(base); s["calls"] = ["x"]; cases.append((s, "must be an object"))
    s = deepcopy(base); del s["calls"][0]["case_id"]; cases.append((s, "missing required fields"))
    s = deepcopy(base); s["calls"][0]["transcript"] = "x"; cases.append((s, "transcript must be a list"))
    s = deepcopy(base); s["calls"][0]["raw_response"] = {}; cases.append((s, "raw_response must be a string"))

    for source, message in cases:
        with pytest.raises(ValueError, match=message):
            orr.replay_saved_report(source)
    assert len(cases) == 5


def test_replay_scenario_family_case_id_and_parse_failure_branches():
    source = _replay_source()

    mismatch = deepcopy(source)
    mismatch["calls"][0]["family"] = "wrong"
    with pytest.raises(ValueError, match="family mismatch"):
        orr.replay_saved_report(mismatch)

    bad_case = deepcopy(source)
    bad_case["calls"][0]["case_id"] = ""
    with pytest.raises(ValueError, match="case_id is invalid"):
        orr.replay_saved_report(bad_case)

    parse_fail = deepcopy(source)
    parse_fail["calls"][0]["raw_response"] = "not-json"
    report = orr.replay_saved_report(parse_fail)
    assert report["calls"][0]["parse_error"] == "model response is not valid JSON"

    no_runtime = deepcopy(source)
    no_runtime["runtime"] = []
    report2 = orr.replay_saved_report(no_runtime)
    assert report2["offline_replay"]["source_parse_failures"] == 0


def test_replay_resolve_oserror_fallback_branch(monkeypatch):
    class FakePath:
        def __init__(self, value):
            self.value = str(value)

        def resolve(self):
            raise OSError("no resolve")

        def absolute(self):
            return self.value

        def exists(self):
            return False

        def __str__(self):
            return self.value

    monkeypatch.setattr(orr, "Path", FakePath)
    with pytest.raises(ValueError, match="must not overwrite"):
        orr.replay_report_file("same", "same")


def test_replay_summary_parser_main_and_guard(tmp_path, monkeypatch, capsys):
    source = _replay_source()
    source_path = tmp_path / "source.json"
    output_path = tmp_path / "output.json"
    source_path.write_text(json.dumps(source), encoding="utf-8")

    report = orr.main([
        "--input", str(source_path),
        "--output", str(output_path),
        "--overwrite",
    ])
    assert output_path.is_file()
    assert report["offline_replay"]["api_model_calls_made"] == 0
    assert "OFFLINE REPLAY" in capsys.readouterr().out

    guard_output = tmp_path / "guard.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "order_coordination_report_replay.py",
            "--input", str(source_path),
            "--output", str(guard_output),
            "--overwrite",
        ],
    )
    path = Path(__file__).resolve().parents[1] / "ghost" / "examples" / "order_coordination_report_replay.py"
    result = runpy.run_path(str(path), run_name="__main__")
    assert "main" in result
    assert guard_output.is_file()


import ghost.examples.order_coordination_demo as od


def test_order_coordination_demo_and_main_guard(capsys):
    result = od.run_demo()
    assert result["status"]["submitted"] is True
    assert result["submitted"]["submitted"] is True
    assert "GHOST ORDER COORDINATION DEMO" in capsys.readouterr().out

    path = Path(__file__).resolve().parents[1] / "ghost" / "examples" / "order_coordination_demo.py"
    namespace = runpy.run_path(str(path), run_name="__main__")
    assert "run_demo" in namespace
