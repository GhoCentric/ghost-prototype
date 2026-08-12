"""Offline replay for saved Ghost order-coordination benchmark reports.

The replay never calls a language model. It reuses every saved transcript and
raw model response, reparses them with the currently installed benchmark code,
and re-evaluates both the transcript-only and Ghost-backed paths. This allows
parser and evaluator fixes to be applied to an existing paid benchmark run
without spending additional API money.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from ghost.examples.order_coordination_benchmark import (
    BenchmarkScenario,
    build_scenarios,
)
from ghost.examples.order_coordination_live_benchmark import (
    CONFIDENCE_POLICY,
    LIVE_BENCHMARK_KIND,
    LIVE_BENCHMARK_SCHEMA_VERSION,
    _aggregate,
    _aggregate_coordination,
    _aggregate_runtime,
    _enrich_live_score,
    _paired_coordination_delta,
    _paired_delta,
    _recover_valid_final_order,
    _score_run,
    apply_ghost_backed,
    apply_transcript_only,
    parse_model_packet,
    write_report,
)


REPLAY_KIND = "offline_saved_raw_response_replay"
DEFAULT_SOURCE_REPORT = "order_coordination_live_benchmark_report.json"
DEFAULT_OUTPUT_NAME = "order_coordination_live_benchmark_report_replayed.json"


def _json_copy(value: Any, label: str = "value") -> Any:
    try:
        return json.loads(
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be JSON-safe") from exc


def _default_output_path() -> str:
    android_download = Path("/storage/emulated/0/Download")

    if android_download.is_dir():
        return str(android_download / DEFAULT_OUTPUT_NAME)

    return DEFAULT_OUTPUT_NAME


def _load_source(path: str | Path) -> tuple[dict[str, Any], str]:
    source = Path(path)

    try:
        raw = source.read_bytes()
    except OSError as exc:
        raise ValueError(f"could not read source report: {source}") from exc

    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("source report is not valid UTF-8 JSON") from exc

    if not isinstance(decoded, dict):
        raise ValueError("source report root must be an object")

    return decoded, hashlib.sha256(raw).hexdigest()


def _known_scenarios() -> dict[str, BenchmarkScenario]:
    return {scenario.scenario_id: scenario for scenario in build_scenarios()}


def _validate_source_report(source: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if source.get("benchmark_kind") != LIVE_BENCHMARK_KIND:
        raise ValueError("source report benchmark_kind is unsupported")

    calls = source.get("calls")

    if not isinstance(calls, list) or not calls:
        raise ValueError("source report calls must be a non-empty list")

    for index, call in enumerate(calls):
        if not isinstance(call, dict):
            raise ValueError(f"source call {index} must be an object")

        required = {
            "trial",
            "scenario_index",
            "scenario_id",
            "case_id",
            "transcript",
            "raw_response",
        }

        if not required.issubset(call):
            raise ValueError(f"source call {index} is missing required fields")

        if not isinstance(call["transcript"], list):
            raise ValueError(f"source call {index} transcript must be a list")

        if not isinstance(call["raw_response"], str):
            raise ValueError(f"source call {index} raw_response must be a string")

    return calls


def _scenario_for_call(
    call: Mapping[str, Any],
    scenarios: Mapping[str, BenchmarkScenario],
) -> BenchmarkScenario:
    scenario_id = call["scenario_id"]

    if not isinstance(scenario_id, str) or scenario_id not in scenarios:
        raise ValueError(f"unknown scenario_id in source report: {scenario_id!r}")

    scenario = scenarios[scenario_id]
    family = call.get("family")

    if family is not None and family != scenario.family:
        raise ValueError(
            f"scenario family mismatch for {scenario_id}: {family!r}"
        )

    return scenario


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def replay_saved_report(
    source: Mapping[str, Any],
    *,
    source_sha256: str | None = None,
) -> dict[str, Any]:
    """Re-evaluate one saved report without making any model calls."""
    calls = _validate_source_report(source)
    scenarios = _known_scenarios()
    replayed_calls: list[dict[str, Any]] = []
    baseline_results: list[dict[str, Any]] = []
    ghost_results: list[dict[str, Any]] = []

    for call_index, source_call in enumerate(calls, start=1):
        scenario = _scenario_for_call(source_call, scenarios)
        transcript = _json_copy(source_call["transcript"], "transcript")
        raw_text = source_call["raw_response"]
        trial = _positive_int(source_call["trial"], "trial")
        scenario_index = _positive_int(
            source_call["scenario_index"],
            "scenario_index",
        )
        case_id = source_call["case_id"]

        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"source call {call_index} case_id is invalid")

        recovered_order, raw_final_order_valid = _recover_valid_final_order(
            raw_text,
            scenario,
        )
        parse_error: str | None = None

        try:
            packet = parse_model_packet(raw_text, scenario, transcript)
        except ValueError as exc:
            parse_error = str(exc)
            packet = {
                "events": [],
                "final_order": recovered_order,
                "parser_repairs": [],
            }

        baseline_run = apply_transcript_only(scenario, packet)
        ghost_run = apply_ghost_backed(
            scenario,
            packet,
            operation_prefix=(
                f"offline-replay:{trial:03d}:{scenario_index:03d}:"
                f"{case_id}"
            ),
        )
        baseline_scored = _enrich_live_score(
            _score_run(scenario, baseline_run),
            baseline_run,
        )
        ghost_scored = _enrich_live_score(
            _score_run(scenario, ghost_run),
            ghost_run,
        )
        baseline_results.append(baseline_scored)
        ghost_results.append(ghost_scored)

        replayed_call = deepcopy(dict(source_call))
        replayed_call.update(
            {
                "family": scenario.family,
                "parsed_packet": packet,
                "parser_repairs": packet.get("parser_repairs", []),
                "raw_final_order_valid": raw_final_order_valid,
                "parse_error": parse_error,
                "transcript_only": baseline_scored,
                "ghost_backed": ghost_scored,
                "ghost_decisions": ghost_run["decision_log"],
                "ghost_status": ghost_run["status"],
                "offline_replay_audit": {
                    "source_parse_error": source_call.get("parse_error"),
                    "source_parser_repairs": source_call.get(
                        "parser_repairs",
                        [],
                    ),
                    "reparsed_with_schema_version": (
                        LIVE_BENCHMARK_SCHEMA_VERSION
                    ),
                },
            }
        )
        replayed_calls.append(
            _json_copy(replayed_call, f"replayed call {call_index}")
        )

    baseline_aggregate = _aggregate(baseline_results)
    ghost_aggregate = _aggregate(ghost_results)
    baseline_coordination = _aggregate_coordination(baseline_results)
    ghost_coordination = _aggregate_coordination(ghost_results)
    baseline_aggregate["coordination"] = baseline_coordination
    ghost_aggregate["coordination"] = ghost_coordination
    runtime = _aggregate_runtime(replayed_calls)

    source_runtime = source.get("runtime", {})
    source_parse_failures = (
        int(source_runtime.get("parse_failures", 0))
        if isinstance(source_runtime, dict)
        else 0
    )

    report = deepcopy(dict(source))
    report.update(
        {
            "schema_version": LIVE_BENCHMARK_SCHEMA_VERSION,
            "benchmark_kind": LIVE_BENCHMARK_KIND,
            "claim_boundary": (
                "This is an offline replay of a live paired-proposal "
                "post-intake coordination benchmark. Saved raw model "
                "responses are reparsed and re-evaluated without new "
                "model calls. It does not measure speech recognition, "
                "raw model intelligence in isolation, or production "
                "readiness."
            ),
            "pairing_rule": (
                "Each saved raw response is reused unchanged for the "
                "transcript-only and Ghost-backed evaluations. The "
                "offline replay makes zero new model calls."
            ),
            "confidence_policy": CONFIDENCE_POLICY,
            "turn_id_normalization_policy": (
                "Exact transcript ids are preferred. Common zero-padding, "
                "separator, and harmless trailing-punctuation variants "
                "such as t_05, t_5, and t08, are normalized only when "
                "they map uniquely to an existing transcript turn."
            ),
            "modes": {
                "transcript_only": baseline_aggregate,
                "ghost_backed": ghost_aggregate,
            },
            "paired_metric_delta_ghost_minus_baseline": _paired_delta(
                baseline_aggregate,
                ghost_aggregate,
            ),
            "paired_coordination_delta_ghost_minus_baseline": (
                _paired_coordination_delta(
                    baseline_coordination,
                    ghost_coordination,
                )
            ),
            "runtime": runtime,
            "calls": replayed_calls,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "offline_replay": {
                "replay_kind": REPLAY_KIND,
                "api_model_calls_made": 0,
                "source_call_count": len(calls),
                "source_schema_version": source.get("schema_version"),
                "source_generated_at_utc": source.get("generated_at_utc"),
                "source_parse_failures": source_parse_failures,
                "source_report_sha256": source_sha256,
                "replay_schema_version": LIVE_BENCHMARK_SCHEMA_VERSION,
            },
        }
    )
    return _json_copy(report, "offline replay report")


def replay_report_file(
    input_path: str | Path = DEFAULT_SOURCE_REPORT,
    output_path: str | Path | None = None,
    *,
    overwrite: bool = False,
) -> tuple[dict[str, Any], Path]:
    source_path = Path(input_path)
    destination = Path(output_path or _default_output_path())

    try:
        same_path = source_path.resolve() == destination.resolve()
    except OSError:
        same_path = source_path.absolute() == destination.absolute()

    if same_path:
        raise ValueError("replay output must not overwrite the source report")

    if destination.exists() and not overwrite:
        raise ValueError(
            f"replay output already exists: {destination}; use --overwrite"
        )

    source, source_sha256 = _load_source(source_path)
    report = replay_saved_report(source, source_sha256=source_sha256)
    written = write_report(report, destination)
    return report, written


def print_replay_summary(report: Mapping[str, Any]) -> None:
    baseline_mode = report["modes"]["transcript_only"]
    ghost_mode = report["modes"]["ghost_backed"]
    baseline = baseline_mode["metrics"]
    ghost = ghost_mode["metrics"]
    baseline_coord = baseline_mode["coordination"]
    ghost_coord = ghost_mode["coordination"]
    runtime = report["runtime"]
    replay = report["offline_replay"]

    print("=== GHOST ORDER COORDINATION OFFLINE REPLAY ===")
    print()
    print(f"Saved model calls replayed: {runtime['call_count']}")
    print(f"New API/model calls made: {replay['api_model_calls_made']}")
    print(f"Valid event packets: {runtime['valid_event_packets']}")
    print(f"Parse failures: {runtime['parse_failures']}")
    print(f"Turn-id repairs: {runtime['turn_id_repairs']}")
    print(f"Valid raw final orders: {runtime['raw_final_orders_valid']}")
    print()
    print("Transcript-only:")
    print(f"  correct final orders: {baseline['correct_final_orders']}")
    print(
        "  safe workflow completions: "
        f"{baseline_coord['safe_workflow_completions']}"
    )
    print(f"  stale confirmations accepted: {baseline['stale_confirmation_accepted']}")
    print(f"  duplicate submissions: {baseline['duplicate_submissions']}")
    print(
        "  unresolved ambiguity submitted: "
        f"{baseline['unresolved_ambiguity_submitted']}"
    )
    print()
    print("Ghost-backed:")
    print(f"  correct final orders: {ghost['correct_final_orders']}")
    print(
        "  safe workflow completions: "
        f"{ghost_coord['safe_workflow_completions']}"
    )
    print(f"  stale confirmations accepted: {ghost['stale_confirmation_accepted']}")
    print(f"  duplicate submissions: {ghost['duplicate_submissions']}")
    print(
        "  unresolved ambiguity submitted: "
        f"{ghost['unresolved_ambiguity_submitted']}"
    )
    print(
        "  guardrail interventions: "
        f"{ghost_coord['guardrail_interventions']}"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Replay a saved live order benchmark with zero new API calls."
        )
    )
    parser.add_argument(
        "--input",
        default=DEFAULT_SOURCE_REPORT,
        help="Saved live benchmark JSON report.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Corrected JSON report path. On Android the default is the "
            "Download folder."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing replay output file.",
    )
    return parser


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = _parser().parse_args(argv)
    report, destination = replay_report_file(
        args.input,
        args.output,
        overwrite=args.overwrite,
    )
    print_replay_summary(report)
    print()
    print(f"Corrected JSON report: {destination}")
    return report


if __name__ == "__main__":
    main()
