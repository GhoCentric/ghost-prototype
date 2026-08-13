# Ghost Quality Lanes

Ghost separates normal validation, performance checks, and branch-coverage
tracing so one lane does not distort another.

## Full Normal Suite

Runs every maintained test, including local performance regression checks.

```bash
python -m pytest -q
```

Current v1.9.0 checkpoint:

```text
1674 passed, 1 skipped
```

The skipped test is intentionally gated and normal validation does not require a
real network call.

## Performance Only

Runs throughput checks without coverage tracing.

```bash
python -m pytest -q -m performance
```

Coverage instrumentation must not be used to judge performance floors.

## Reusable Core Coverage

Measures the reusable `ghost` package while excluding `ghost/examples/` through
`coverage.core.ini`.

```bash
python -m pytest -q -m "not performance"   --cov=ghost   --cov-config=coverage.core.ini   --cov-report=term-missing   --cov-report=json:docs/coverage/v1.9.0/core.json
```

Release target: 100% executable statements and 100% branch outcomes.

## Complete Ghost Revolution Package Coverage

Measures every Python runtime file under
`ghost.examples.ghost_revolution`, including presentation, developer tooling,
benchmarks, and the campaign runtime.

```bash
python -m pytest -q tests/ghost_revolution   --cov=ghost.examples.ghost_revolution   --cov-config=coverage.revolution.ini   --cov-branch   --cov-report=term-missing   --cov-report=json:docs/coverage/v1.9.0/revolution.json
```

Release target: 100% executable statements and 100% branch outcomes.

## Order Coordination Coverage

Measures all five Order Coordination application/benchmark modules with their
focused tests. The v1.9.0 release packaging test is included because it covers
the public console-safe `order_coordination_demo.main()` wrapper.

```bash
python -m pytest -q   tests/test_order_coordination_v180.py   tests/test_order_coordination_benchmark_v180.py   tests/test_order_coordination_live_benchmark_v180.py   tests/test_order_coordination_report_replay_v180.py   tests/test_order_coordination_coverage_closure_v180.py   tests/test_order_coordination_snapshot_hardening_v180.py   tests/test_release_packaging_cli_v190.py   --cov=ghost.examples.order_coordination   --cov=ghost.examples.order_coordination_benchmark   --cov=ghost.examples.order_coordination_demo   --cov=ghost.examples.order_coordination_live_benchmark   --cov=ghost.examples.order_coordination_report_replay   --cov-branch   --cov-report=term-missing   --cov-report=json:docs/coverage/v1.9.0/order_coordination.json
```

Release target: 100% executable statements and 100% branch outcomes.

## Published Evidence

Current human-readable and machine-readable results live under:

```text
COVERAGE.md
docs/coverage/v1.9.0/
```

The previous `docs/coverage/v1.8.0/` directory is retained unchanged as
historical release evidence.

The JSON files preserve per-file coverage data. The text files preserve the
exact pytest/coverage output from the publication run.

## Policy

Coverage is a release-quality signal, not a substitute for requirement review.
A path should be classified before it is hidden, excluded, or deleted.

Current v1.9.0 targets:

- reusable core: 100% statements and branches;
- complete Ghost Revolution package: 100% statements and branches;
- Order Coordination: 100% statements and branches;
- performance: normal pytest only, never judged under coverage tracing;
- full uninstrumented suite: release gate;
- mutation testing: future work on a conventional CI/Linux environment.
