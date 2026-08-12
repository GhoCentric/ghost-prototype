from __future__ import annotations

import json
from pathlib import Path

import pytest

from ghost.examples.ghost_revolution.llm_bridge import LLMBridgeConfig
from ghost.examples.order_coordination_benchmark import (
    FAMILY_AMBIGUOUS,
    build_scenarios,
)
from ghost.examples.order_coordination_live_benchmark import (
    DeterministicOrderBenchmarkMockClient,
    run_live_benchmark,
)
from ghost.examples.order_coordination_report_replay import (
    REPLAY_KIND,
    replay_report_file,
    replay_saved_report,
)


def _config() -> LLMBridgeConfig:
    return LLMBridgeConfig(
        model="mock-order-model",
        max_output_tokens=1600,
        hard_max_output_tokens=1600,
        role="order_coordination_benchmark",
    )


def _source_report(limit: int = 7) -> dict:
    scenarios = build_scenarios()[:limit]
    report = run_live_benchmark(
        client=DeterministicOrderBenchmarkMockClient(),
        config=_config(),
        scenarios=scenarios,
        trials=1,
        clock=lambda: 1.0,
    )
    report["schema_version"] = "1.1"
    return report


def test_replay_makes_zero_new_model_calls_and_preserves_saved_count():
    source = _source_report()
    replayed = replay_saved_report(source, source_sha256="a" * 64)

    assert replayed["offline_replay"] == {
        "replay_kind": REPLAY_KIND,
        "api_model_calls_made": 0,
        "source_call_count": 7,
        "source_schema_version": "1.1",
        "source_generated_at_utc": source["generated_at_utc"],
        "source_parse_failures": source["runtime"]["parse_failures"],
        "source_report_sha256": "a" * 64,
        "replay_schema_version": "1.2",
    }
    assert replayed["runtime"]["call_count"] == 7


def test_replay_normalizes_turn_id_with_trailing_punctuation():
    source = _source_report(limit=1)
    packet = json.loads(source["calls"][0]["raw_response"])
    packet["events"][-1]["turn_id"] += ","
    source["calls"][0]["raw_response"] = json.dumps(packet)
    source["calls"][0]["parse_error"] = (
        "model event references unknown turn: t05,"
    )

    replayed = replay_saved_report(source)
    call = replayed["calls"][0]

    assert call["parse_error"] is None
    assert call["parser_repairs"] == [
        {
            "kind": "turn_id_normalized",
            "raw_turn_id": "t05,",
            "normalized_turn_id": "t05",
        }
    ]
    assert call["offline_replay_audit"]["source_parse_error"]


def test_replay_clears_baseline_ambiguity_after_customer_resolution():
    scenario = next(
        item for item in build_scenarios()
        if item.family == FAMILY_AMBIGUOUS
    )
    report = run_live_benchmark(
        client=DeterministicOrderBenchmarkMockClient(),
        config=_config(),
        scenarios=[scenario],
        trials=1,
        clock=lambda: 1.0,
    )

    replayed = replay_saved_report(report)
    baseline = replayed["calls"][0]["transcript_only"]

    assert baseline["metrics"]["unresolved_ambiguity_submitted"] is False
    assert baseline["coordination"]["safe_workflow_completion"] is True


def test_replay_preserves_historical_usage_cost_and_latency():
    source = _source_report(limit=1)
    source_call = source["calls"][0]
    replayed_call = replay_saved_report(source)["calls"][0]

    assert replayed_call["usage"] == source_call["usage"]
    assert replayed_call["measured_cost"] == source_call["measured_cost"]
    assert replayed_call["latency_seconds"] == source_call["latency_seconds"]
    assert replayed_call["raw_response"] == source_call["raw_response"]


def test_replay_rejects_unknown_benchmark_kind():
    source = _source_report(limit=1)
    source["benchmark_kind"] = "different"

    with pytest.raises(ValueError, match="benchmark_kind"):
        replay_saved_report(source)


def test_replay_rejects_unknown_scenario():
    source = _source_report(limit=1)
    source["calls"][0]["scenario_id"] = "unknown"

    with pytest.raises(ValueError, match="unknown scenario_id"):
        replay_saved_report(source)


def test_replay_file_refuses_to_overwrite_source(tmp_path: Path):
    source = _source_report(limit=1)
    path = tmp_path / "report.json"
    path.write_text(json.dumps(source), encoding="utf-8")

    with pytest.raises(ValueError, match="must not overwrite"):
        replay_report_file(path, path)


def test_replay_file_refuses_existing_output_without_flag(tmp_path: Path):
    source = _source_report(limit=1)
    source_path = tmp_path / "source.json"
    output_path = tmp_path / "output.json"
    source_path.write_text(json.dumps(source), encoding="utf-8")
    output_path.write_text("existing", encoding="utf-8")

    with pytest.raises(ValueError, match="already exists"):
        replay_report_file(source_path, output_path)


def test_replay_file_writes_audited_report(tmp_path: Path):
    source = _source_report(limit=1)
    source_path = tmp_path / "source.json"
    output_path = tmp_path / "output.json"
    source_path.write_text(json.dumps(source), encoding="utf-8")

    report, written = replay_report_file(source_path, output_path)
    loaded = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == output_path
    assert loaded == report
    assert loaded["offline_replay"]["api_model_calls_made"] == 0
    assert len(loaded["offline_replay"]["source_report_sha256"]) == 64
