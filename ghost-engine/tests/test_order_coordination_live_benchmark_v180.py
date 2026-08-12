import json
from pathlib import Path

import pytest

from ghost.examples.order_coordination_benchmark import (
    FAMILY_ORDER,
)
from ghost.examples.order_coordination_live_benchmark import (
    CONFIDENCE_POLICY,
    INTERVENTION_KEYS,
    DeterministicOrderBenchmarkMockClient,
    _config_for_cli,
    _ideal_mock_packet,
    apply_ghost_backed,
    apply_transcript_only,
    build_extraction_prompt,
    build_transcript,
    main,
    parse_model_packet,
    run_live_benchmark,
    select_scenarios,
    write_report,
)


def _config():
    return _config_for_cli(
        model="test-model",
        max_output_tokens=800,
    )


def test_live_scenario_selection_is_balanced_and_full_v180():
    selected = select_scenarios(limit=7)
    full = select_scenarios(full=True)

    assert len(selected) == 7
    assert {item.family for item in selected} == set(FAMILY_ORDER)
    assert len(full) == 100
    assert len({item.scenario_id for item in full}) == 100


def test_live_prompt_does_not_leak_expected_answer_or_family_v180():
    scenario = select_scenarios(limit=7)[1]
    transcript = build_transcript(scenario)
    prompt = build_extraction_prompt(scenario, transcript)

    assert "expected_modifier_target" not in prompt
    assert '"family"' not in prompt
    assert scenario.family not in prompt
    assert scenario.scenario_id not in prompt
    assert "INPUT_PACKET_JSON:" in prompt
    assert "item_001" in prompt
    assert "item_002" in prompt


def test_live_mock_reuses_one_model_call_for_both_modes_v180():
    scenarios = select_scenarios(limit=7)
    client = DeterministicOrderBenchmarkMockClient()
    report = run_live_benchmark(
        client=client,
        config=_config(),
        scenarios=scenarios,
        trials=2,
    )

    assert client.call_count == 14
    assert report["runtime"]["call_count"] == 14
    assert report["scenario_instances"] == 14
    assert len(report["calls"]) == 14
    assert all(call["raw_response"] for call in report["calls"])
    assert all(call["parsed_packet"] for call in report["calls"])
    assert all(call["parse_error"] is None for call in report["calls"])
    assert "Exactly one model call" in report["pairing_rule"]


def test_live_mock_proves_safety_gates_without_claiming_model_gain_v180():
    report = run_live_benchmark(
        client=DeterministicOrderBenchmarkMockClient(),
        config=_config(),
        scenarios=select_scenarios(limit=7),
        trials=1,
    )
    baseline = report["modes"]["transcript_only"]["metrics"]
    ghost = report["modes"]["ghost_backed"]["metrics"]

    assert baseline["correct_final_orders"] == 7
    assert ghost["correct_final_orders"] == 7
    assert baseline["stale_confirmation_accepted"] == 1
    assert ghost["stale_confirmation_accepted"] == 0
    assert baseline["duplicate_submissions"] == 2
    assert ghost["duplicate_submissions"] == 0
    assert ghost["unsafe_attempts_blocked"] >= 3
    assert "post-intake" in report["claim_boundary"]


def test_live_packet_parser_rejects_unknown_turn_v180():
    scenario = select_scenarios(limit=1)[0]
    transcript = build_transcript(scenario)
    packet = {
        "events": [
            {
                "turn_id": "t99",
                "event_type": "submit_request",
                "modifier": "",
                "candidate_item_ids": [],
                "item_id": "",
                "quantity": 0,
                "confidence": 1.0,
                "is_correction": False,
                "note": "",
            }
        ],
        "final_order": {
            "items": [
                {
                    "item_id": "item_001",
                    "product": scenario.first_product,
                    "quantity": scenario.first_quantity,
                    "modifiers": [],
                },
                {
                    "item_id": "item_002",
                    "product": scenario.second_product,
                    "quantity": 1,
                    "modifiers": [scenario.modifier],
                },
            ]
        },
    }

    with pytest.raises(ValueError, match="unknown turn"):
        parse_model_packet(
            json.dumps(packet),
            scenario,
            transcript,
        )


def test_live_benchmark_preserves_malformed_raw_response_v180():
    class MalformedClient:
        provider_name = "malformed_test_client"

        def __call__(self, prompt, *, config):
            del prompt, config
            return {
                "text": "not-json",
                "usage": None,
                "model": "test-model",
                "response_id": "bad_001",
            }

    report = run_live_benchmark(
        client=MalformedClient(),
        config=_config(),
        scenarios=select_scenarios(limit=1),
        trials=1,
    )
    call = report["calls"][0]

    assert report["runtime"]["parse_failures"] == 1
    assert call["raw_response"] == "not-json"
    assert call["parse_error"] == "model response is not valid JSON"
    assert report["modes"]["transcript_only"]["metrics"][
        "incorrect_final_orders"
    ] == 1


def test_live_report_writer_round_trips_raw_calls_v180(tmp_path):
    report = run_live_benchmark(
        client=DeterministicOrderBenchmarkMockClient(),
        config=_config(),
        scenarios=select_scenarios(limit=2),
        trials=1,
    )
    destination = write_report(
        report,
        tmp_path / "nested" / "live.json",
    )

    assert destination.is_file()
    restored = json.loads(destination.read_text(encoding="utf-8"))
    assert restored == report
    assert restored["calls"][0]["raw_response"]


def test_live_real_calls_are_explicitly_env_gated_v180(monkeypatch):
    monkeypatch.delenv("GHOST_REAL_LLM", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="off by default"):
        main(["--limit", "1"])


def test_live_module_has_main_guard_v180():
    path = Path(
        "ghost/examples/order_coordination_live_benchmark.py"
    )
    source = path.read_text(encoding="utf-8")

    assert 'if __name__ == "__main__":' in source
    assert "GHOST_REAL_LLM" in source
    assert "OPENAI_API_KEY" in source
    assert "OpenAIResponsesClient" in source



def test_live_turn_id_normalization_repairs_common_variants_v180():
    scenario = select_scenarios(limit=1)[0]
    transcript = build_transcript(scenario)
    packet = _ideal_mock_packet(scenario, transcript)
    packet["events"][0]["turn_id"] = "t_02"
    packet["events"][-1]["turn_id"] = "t_5"

    parsed = parse_model_packet(
        json.dumps(packet),
        scenario,
        transcript,
    )

    assert parsed["events"][0]["turn_id"] == "t02"
    assert parsed["events"][-1]["turn_id"] == "t05"
    assert len(parsed["parser_repairs"]) == 2
    assert parsed["parser_repairs"][0]["raw_turn_id"] == "t_02"
    assert parsed["parser_repairs"][1]["normalized_turn_id"] == "t05"


def test_live_turn_id_normalization_repairs_trailing_punctuation_v180():
    scenario = next(
        item
        for item in select_scenarios(limit=7)
        if item.family == "stale_confirmation"
    )
    transcript = build_transcript(scenario)
    packet = _ideal_mock_packet(scenario, transcript)
    packet["events"][-2]["turn_id"] = "t08,"
    packet["events"][-1]["turn_id"] = "t09;"

    parsed = parse_model_packet(
        json.dumps(packet),
        scenario,
        transcript,
    )

    assert parsed["events"][-2]["turn_id"] == "t08"
    assert parsed["events"][-1]["turn_id"] == "t09"
    assert parsed["parser_repairs"][-2] == {
        "kind": "turn_id_normalized",
        "raw_turn_id": "t08,",
        "normalized_turn_id": "t08",
    }
    assert parsed["parser_repairs"][-1]["raw_turn_id"] == "t09;"


def test_live_baseline_clears_customer_resolved_ambiguity_v180():
    scenario = next(
        item
        for item in select_scenarios(limit=7)
        if item.family == "ambiguous_target_guess"
    )
    transcript = build_transcript(scenario)
    packet = _ideal_mock_packet(scenario, transcript)
    correction = packet["events"][2]
    correction["candidate_item_ids"] = []
    correction["item_id"] = "item_002"
    correction["is_correction"] = True

    parsed = parse_model_packet(
        json.dumps(packet),
        scenario,
        transcript,
    )
    baseline = apply_transcript_only(scenario, parsed)

    assert baseline["submission_count"] == 1
    assert baseline["unresolved_ambiguity_submitted"] is False


def test_live_confidence_is_advisory_and_audited_v180():
    class ZeroConfidenceClient(DeterministicOrderBenchmarkMockClient):
        def __call__(self, prompt, *, config):
            result = super().__call__(prompt, config=config)
            packet = json.loads(result["text"])

            for event in packet["events"]:
                event["confidence"] = 0.0

            result["text"] = json.dumps(packet, sort_keys=True)
            return result

    report = run_live_benchmark(
        client=ZeroConfidenceClient(),
        config=_config(),
        scenarios=select_scenarios(limit=1),
        trials=1,
    )
    call = report["calls"][0]

    assert report["confidence_policy"] == CONFIDENCE_POLICY
    assert report["modes"]["ghost_backed"]["metrics"][
        "correct_final_orders"
    ] == 1
    assert all(
        decision["model_confidence"] == 0.0
        for decision in call["ghost_decisions"]
    )
    assert all(
        decision["confidence_role"] == "advisory_model_metadata"
        for decision in call["ghost_decisions"]
    )


def test_live_stale_flow_blocks_then_reconfirms_and_completes_v180():
    scenarios = select_scenarios(limit=7)
    report = run_live_benchmark(
        client=DeterministicOrderBenchmarkMockClient(),
        config=_config(),
        scenarios=scenarios,
        trials=1,
    )
    stale = next(
        call for call in report["calls"] if call["family"] == "stale_confirmation"
    )

    assert stale["transcript_only"]["coordination"][
        "safe_workflow_completion"
    ] is False
    assert stale["ghost_backed"]["coordination"][
        "safe_workflow_completion"
    ] is True
    assert stale["ghost_backed"]["submission_count"] == 1
    assert stale["ghost_status"]["submitted"] is True
    assert any(
        decision["decision"] == "submission_blocked"
        for decision in stale["ghost_decisions"]
    )
    assert any(
        decision["decision"] == "current_revision_confirmed"
        and decision["turn_id"] == "t08"
        for decision in stale["ghost_decisions"]
    )
    assert any(
        decision["decision"] == "submission_accepted"
        and decision["turn_id"] == "t09"
        for decision in stale["ghost_decisions"]
    )


def test_live_guardrail_intervention_taxonomy_balances_v180():
    report = run_live_benchmark(
        client=DeterministicOrderBenchmarkMockClient(),
        config=_config(),
        scenarios=select_scenarios(limit=7),
        trials=1,
    )
    coordination = report["modes"]["ghost_backed"]["coordination"]
    counts = coordination["intervention_counts"]

    assert set(counts) == set(INTERVENTION_KEYS)
    assert coordination["guardrail_interventions"] == sum(counts.values())
    assert counts["stale_confirmation_submission_blocks"] == 1
    assert counts["duplicate_submission_blocks"] == 1
    assert counts["non_authoritative_submission_blocks"] == 1
    assert report["modes"]["ghost_backed"]["metrics"][
        "unsafe_attempts_blocked"
    ] == coordination["guardrail_interventions"]


def test_live_quantity_summary_is_not_a_false_intervention_v180():
    scenario = select_scenarios(limit=1)[0]
    transcript = build_transcript(scenario)
    packet = _ideal_mock_packet(scenario, transcript)
    packet["events"].insert(
        0,
        {
            "turn_id": "t01",
            "event_type": "quantity_claim",
            "modifier": "",
            "candidate_item_ids": ["item_001", "item_002"],
            "item_id": "",
            "quantity": 0,
            "confidence": 0.0,
            "is_correction": False,
            "note": "Combined intake summary.",
        },
    )
    parsed = parse_model_packet(
        json.dumps(packet),
        scenario,
        transcript,
    )
    run = apply_ghost_backed(
        scenario,
        parsed,
        operation_prefix="quantity-summary-test",
    )

    assert run["intervention_counts"][
        "post_intake_quantity_rejections"
    ] == 0
    assert any(
        decision["decision"] == "quantity_claim_observed_without_mutation"
        for decision in run["decision_log"]
    )


def test_live_event_parse_failure_preserves_valid_final_order_v180():
    scenario = select_scenarios(limit=1)[0]
    transcript = build_transcript(scenario)
    packet = _ideal_mock_packet(scenario, transcript)
    packet["events"][0]["turn_id"] = "t99"

    class BadTurnClient:
        provider_name = "bad_turn_test_client"

        def __call__(self, prompt, *, config):
            del prompt, config
            return {
                "text": json.dumps(packet, sort_keys=True),
                "usage": None,
                "model": "test-model",
                "response_id": "bad_turn_001",
            }

    report = run_live_benchmark(
        client=BadTurnClient(),
        config=_config(),
        scenarios=[scenario],
        trials=1,
    )
    call = report["calls"][0]

    assert report["runtime"]["parse_failures"] == 1
    assert report["runtime"]["raw_final_orders_valid"] == 1
    assert call["raw_final_order_valid"] is True
    assert "unknown turn" in call["parse_error"]
    assert call["transcript_only"]["metrics"]["correct_final_order"] is True
    assert call["ghost_backed"]["metrics"]["correct_final_order"] is False
    assert call["ghost_backed"]["coordination"][
        "safe_workflow_completion"
    ] is False


def test_live_report_exposes_reliability_policies_v180():
    report = run_live_benchmark(
        client=DeterministicOrderBenchmarkMockClient(),
        config=_config(),
        scenarios=select_scenarios(limit=1),
        trials=1,
    )

    assert report["schema_version"] == "1.2"
    assert "advisory metadata" in report["confidence_policy"]
    assert "t_05" in report["turn_id_normalization_policy"]
    assert "t08," in report["turn_id_normalization_policy"]
    assert "safe_workflow_completions" in report[
        "paired_coordination_delta_ghost_minus_baseline"
    ]
