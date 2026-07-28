# Ghost Revolution Benchmark Results

> **Controlled result:** Across 42 equal-budget game forks, Ghost's
> provenance-aware policy resulted in zero unsafe first-action seizures
> during knight-present misinformation scenarios. The naive
> “reports are truth” baseline made 24.

## What Was Tested

The scenario matrix uses:

```text
7 information scenarios × 2 guarded towns × 3 deterministic seeds = 42 trials
```

Each trial creates a fresh `GhostRevolutionRun`, configures an objective
scenario state, saves one JSON-safe game snapshot, and restores that exact
snapshot for each policy branch.

Every branch receives exactly **2 actions**.

```text
Naive policy:
report claim → immediate action

Ghost policy:
report → actor belief → provenance check
→ investigate when needed → evidence
→ revised belief → action

Oracle policy:
hidden objective truth for audit only
```

The oracle is not a fair competitor. It exists only to show the safety
outcome available with direct objective truth.

## Headline Result

| Metric | Naive reports = truth | Ghost provenance policy |
|---|---:|---:|
| Total controlled trials | 42 | 42 |
| Action budget per trial | 2 | 2 |
| Unsafe first-action seizures when knight present | 24 / 30 | 0 / 30 |
| High-provenance truthful absence handled correctly | 6 / 6 | 6 / 6 |
| High-provenance truthful presence handled correctly | 6 / 6 | 6 / 6 |
| Low-provenance / ambiguous inputs investigated | N/A | 30 / 30 |
| Explicit patrol-evidence belief revisions | N/A | 24 |
| Truthful low-provenance opportunity deferrals | 0 | 6 |

The two “6 / 6” rows do not mean the policies reasoned the same way.
Naive acts directly on the report. Ghost acts only when provenance is high
enough, avoids action when high-provenance information says the knight is
present, and investigates lower-quality or conflicting information before
committing to a costly move.

## Raw Game Tradeoff

No composite “Ghost wins” score is used. The raw consequences remain
visible.

| Aggregate across 42 trials | Naive | Ghost |
|---|---:|---:|
| Gold gained | +267 | +267 |
| Food gained | +60 | +10 |
| Weapons gained | +36 | +6 |
| Heat gained | +162 | +48 |
| Town fear gained | +60 | +6 |
| Royal alert change | +0 | +0 |
| Town-trust change | +4.284 | +4.284 |

The provenance-aware route gave up:

```text
50 food
30 weapons
```

Compared with the naive route, it avoided:

```text
114 heat
54 town fear
```

That is an explicit strategic tradeoff, not hidden utility weighting.

## Scenario Coverage

Each scenario contains 6 trials: 2 guarded towns × 3 deterministic seeds.

| Scenario | Objective truth | Expected Ghost behavior | Observed Ghost behavior |
|---|---|---|---|
| Truthful high-provenance absence | Knight absent | Act | Seized supplies 6 / 6 |
| Truthful low-provenance absence | Knight absent | Investigate | Investigated 6 / 6 |
| Truthful high-provenance presence | Knight present | Avoid | Avoided seizure 6 / 6 |
| Deceptive false absence | Knight present | Investigate | Investigated 6 / 6; revised 6 / 6 |
| Weak-evidence false absence | Knight present | Investigate | Investigated 6 / 6; revised 6 / 6 |
| Ambiguous false absence | Knight present | Investigate | Investigated 6 / 6; revised 6 / 6 |
| Contradictory sources false absence | Knight present | Investigate | Investigated 6 / 6; revised 6 / 6 |

## What This Establishes

Under identical game forks, equal action budgets, and the same public
reports, Ghost's epistemic separation changes actual game choices:

```text
report → belief with provenance and uncertainty
→ investigation when evidence quality is weak
→ player-visible evidence
→ belief revision
→ different game action
→ different heat and fear outcome
```

The result is reproducible through deterministic snapshots, exact branch
restoration, and test coverage.

## Limits

This is not a claim of general intelligence, universal superiority, or a
general-purpose truth detector.

The scenarios are deliberately constructed, and report quality is supplied
by benchmark scenario configuration. Ghost is not inferring provenance from
free-form language alone.

The matrix currently covers Millcross and Crownmarket because the real
`question_guard()` facade action requires active guards. It evaluates a
two-action horizon, not a full campaign or endgame.

## Reproduce

Run the complete matrix:

```bash
python -m ghost.examples.ghost_revolution.benchmarks.epistemic_scenario_matrix_benchmark
```

Run its focused tests:

```bash
pytest -q tests/ghost_revolution/test_ghost_revolution_epistemic_scenario_matrix_v180.py
```

Relevant files:

```text
ghost/examples/ghost_revolution/benchmarks/
    epistemic_decision_benchmark.py
    epistemic_fair_fork_benchmark.py
    epistemic_scenario_matrix_benchmark.py

tests/ghost_revolution/
    test_ghost_revolution_epistemic_benchmark_v180.py
    test_ghost_revolution_epistemic_fair_fork_benchmark_v180.py
    test_ghost_revolution_epistemic_scenario_matrix_v180.py
    test_ghost_revolution_game_snapshot_v180.py
    test_ghost_revolution_benchmark_results_v180.py
```

