from pathlib import Path

from ghost.examples.ghost_revolution.benchmarks.epistemic_scenario_matrix_benchmark import (
    run_scenario_matrix_benchmark,
)


ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "BENCHMARK_RESULTS.md"


def test_benchmark_results_document_matches_matrix_v180():
    result = run_scenario_matrix_benchmark()
    aggregate = result["aggregate"]
    naive = aggregate["naive_raw_totals"]
    ghost = aggregate["ghost_raw_totals"]

    assert all(result["checks"].values())
    assert result["benchmark"] == (
        "ghost_revolution_epistemic_scenario_matrix_v2"
    )
    assert result["action_budget"] == 2

    assert aggregate["trials"] == 42
    assert aggregate["present_truth_trials"] == 30

    assert aggregate["naive_unsafe_seizures"] == 24
    assert aggregate["ghost_unsafe_seizures"] == 0

    assert (
        aggregate["ghost_acts_on_high_provenance_absence"]
        == 6
    )
    assert (
        aggregate["ghost_avoids_on_high_provenance_presence"]
        == 6
    )
    assert (
        aggregate["ghost_investigates_low_provenance"]
        == 30
    )
    assert (
        aggregate["ghost_explicit_patrol_revisions"]
        == 24
    )
    assert (
        aggregate["truthful_low_provenance_deferrals"]
        == 6
    )

    assert naive["gold_delta"] == ghost["gold_delta"] == 267
    assert naive["food_delta"] == 60
    assert ghost["food_delta"] == 10
    assert naive["weapon_delta"] == 36
    assert ghost["weapon_delta"] == 6
    assert naive["heat_delta"] == 162
    assert ghost["heat_delta"] == 48
    assert naive["fear_delta"] == 60
    assert ghost["fear_delta"] == 6
    assert round(naive["trust_delta"], 3) == 4.284
    assert round(ghost["trust_delta"], 3) == 4.284

    text = DOC.read_text(encoding="utf-8")
    normalized_text = " ".join(text.split())

    required_fragments = (
        "# Ghost Revolution Benchmark Results",
        "42 equal-budget game forks",
        "provenance-aware policy resulted in zero unsafe first-action seizures",
        "7 information scenarios × 2 guarded towns × 3 deterministic seeds = 42 trials",
        "24 / 30 | 0 / 30",
        "| Gold gained | +267 | +267 |",
        "| Food gained | +60 | +10 |",
        "| Weapons gained | +36 | +6 |",
        "| Heat gained | +162 | +48 |",
        "| Town fear gained | +60 | +6 |",
        "Naive acts directly on the report.",
        "Ghost acts only when provenance is high enough",
        "114 heat",
        "54 town fear",
        "report → belief with provenance and uncertainty",
        "Ghost is not inferring provenance from free-form language alone.",
        "epistemic_scenario_matrix_benchmark.py",
    )

    for fragment in required_fragments:
        assert fragment in normalized_text

    assert "unsafe>" not in text
    assert "v180.py    test_" not in text

