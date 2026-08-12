import json

from ghost.examples.order_coordination_benchmark import (
    FAMILY_AMBIGUOUS,
    FAMILY_CLEAN,
    FAMILY_CONTRADICTION,
    FAMILY_CORRECTION,
    FAMILY_DUPLICATE,
    FAMILY_QUANTITY,
    FAMILY_STALE,
    build_scenarios,
    run_benchmark,
    write_report,
)


def _result(report, mode, family):
    return next(
        item
        for item in report["results"][mode]
        if item["scenario"]["family"] == family
    )


def test_benchmark_matrix_is_fixed_unique_and_exactly_100_v180():
    scenarios = build_scenarios()

    assert len(scenarios) == 100
    assert len({item.scenario_id for item in scenarios}) == 100
    assert sum(item.family == FAMILY_CLEAN for item in scenarios) == 10

    for family in (
        FAMILY_AMBIGUOUS,
        FAMILY_CORRECTION,
        FAMILY_STALE,
        FAMILY_DUPLICATE,
        FAMILY_QUANTITY,
        FAMILY_CONTRADICTION,
    ):
        assert sum(item.family == family for item in scenarios) == 15


def test_benchmark_is_json_safe_and_deterministic_v180():
    first = run_benchmark()
    second = run_benchmark()

    assert first == second
    json.dumps(first, allow_nan=False, sort_keys=True)
    assert first["benchmark_kind"] == (
        "deterministic_coordination_fault_injection"
    )
    assert "not natural model accuracy" in first["claim_boundary"]


def test_aggregate_results_prove_fault_containment_v180():
    report = run_benchmark()
    baseline = report["modes"]["transcript_only"]["metrics"]
    ghost = report["modes"]["ghost_backed"]["metrics"]

    assert baseline == {
        "correct_final_orders": 40,
        "wrong_modifier_targets": 45,
        "forgotten_corrections": 15,
        "unresolved_ambiguity_submitted": 15,
        "stale_confirmation_accepted": 15,
        "duplicate_submissions": 15,
        "incorrect_quantities": 15,
        "contradictory_final_states": 15,
        "incorrect_final_orders": 60,
        "unsafe_attempts_blocked": 0,
    }
    assert ghost == {
        "correct_final_orders": 100,
        "wrong_modifier_targets": 0,
        "forgotten_corrections": 0,
        "unresolved_ambiguity_submitted": 0,
        "stale_confirmation_accepted": 0,
        "duplicate_submissions": 0,
        "incorrect_quantities": 0,
        "contradictory_final_states": 0,
        "incorrect_final_orders": 0,
        "unsafe_attempts_blocked": 60,
    }


def test_clean_controls_match_in_both_modes_v180():
    report = run_benchmark()
    baseline = _result(report, "transcript_only", FAMILY_CLEAN)
    ghost = _result(report, "ghost_backed", FAMILY_CLEAN)

    assert baseline["final_order"] == baseline["expected_order"]
    assert ghost["final_order"] == ghost["expected_order"]
    assert baseline["metrics"]["incorrect_final_order"] is False
    assert ghost["metrics"]["incorrect_final_order"] is False


def test_ambiguity_is_guessed_by_baseline_and_blocked_by_ghost_v180():
    report = run_benchmark()
    baseline = _result(report, "transcript_only", FAMILY_AMBIGUOUS)
    ghost = _result(report, "ghost_backed", FAMILY_AMBIGUOUS)

    assert baseline["metrics"]["wrong_modifier_target"] is True
    assert baseline["metrics"][
        "unresolved_ambiguity_submitted"
    ] is True
    assert ghost["metrics"]["wrong_modifier_target"] is False
    assert ghost["metrics"][
        "unresolved_ambiguity_submitted"
    ] is False
    assert ghost["metrics"]["unsafe_attempts_blocked"] == 1


def test_correction_stale_duplicate_quantity_and_conflict_are_contained_v180():
    report = run_benchmark()

    correction_base = _result(
        report,
        "transcript_only",
        FAMILY_CORRECTION,
    )
    correction_ghost = _result(
        report,
        "ghost_backed",
        FAMILY_CORRECTION,
    )
    assert correction_base["metrics"]["forgotten_correction"] is True
    assert correction_ghost["metrics"]["forgotten_correction"] is False

    stale_base = _result(report, "transcript_only", FAMILY_STALE)
    stale_ghost = _result(report, "ghost_backed", FAMILY_STALE)
    assert stale_base["metrics"][
        "stale_confirmation_accepted"
    ] is True
    assert stale_ghost["metrics"][
        "stale_confirmation_accepted"
    ] is False
    assert stale_ghost["metrics"]["unsafe_attempts_blocked"] == 1

    duplicate_base = _result(
        report,
        "transcript_only",
        FAMILY_DUPLICATE,
    )
    duplicate_ghost = _result(
        report,
        "ghost_backed",
        FAMILY_DUPLICATE,
    )
    assert duplicate_base["metrics"]["duplicate_submission"] is True
    assert duplicate_ghost["metrics"]["duplicate_submission"] is False
    assert duplicate_ghost["metrics"]["unsafe_attempts_blocked"] == 1

    quantity_base = _result(
        report,
        "transcript_only",
        FAMILY_QUANTITY,
    )
    quantity_ghost = _result(
        report,
        "ghost_backed",
        FAMILY_QUANTITY,
    )
    assert quantity_base["metrics"]["incorrect_quantity"] is True
    assert quantity_ghost["metrics"]["incorrect_quantity"] is False

    conflict_base = _result(
        report,
        "transcript_only",
        FAMILY_CONTRADICTION,
    )
    conflict_ghost = _result(
        report,
        "ghost_backed",
        FAMILY_CONTRADICTION,
    )
    assert conflict_base["metrics"][
        "contradictory_final_state"
    ] is True
    assert conflict_ghost["metrics"][
        "contradictory_final_state"
    ] is False
    assert conflict_ghost["metrics"]["unsafe_attempts_blocked"] == 1


def test_report_writer_round_trips_exact_json_v180(tmp_path):
    report = run_benchmark()
    destination = write_report(
        report,
        tmp_path / "nested" / "report.json",
    )

    assert destination.is_file()
    assert json.loads(destination.read_text()) == report
