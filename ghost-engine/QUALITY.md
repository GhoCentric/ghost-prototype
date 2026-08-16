# Ghost Quality Lanes

Ghost separates normal validation, performance checks, and branch-coverage
tracing so one lane does not distort another.

## Full Normal Suite

```bash
python -m pytest -q
```

Current v1.9.2 checkpoint:

```text
1763 passed, 1 skipped
```

The skipped test is intentionally gated. Normal validation does not require an
API key or a real network call.

## Performance Only

```bash
python -m pytest -q -m performance
```

Coverage instrumentation must not be used to judge performance floors.

## Reusable Core Coverage

```bash
python -m pytest -q -m "not performance" \
  --cov=ghost \
  --cov-config=coverage.core.ini \
  --cov-branch \
  --cov-report=term-missing \
  --cov-report=json:docs/coverage/v1.9.2/core.json
```

## Complete Ghost Revolution Package Coverage

```bash
python -m pytest -q tests/ghost_revolution \
  --cov=ghost.examples.ghost_revolution \
  --cov-config=coverage.revolution.ini \
  --cov-branch \
  --cov-report=term-missing \
  --cov-report=json:docs/coverage/v1.9.2/revolution.json
```

## Order Coordination Coverage

```bash
python -m pytest -q \
  tests/test_order_coordination_v180.py tests/test_order_coordination_benchmark_v180.py tests/test_order_coordination_live_benchmark_v180.py tests/test_order_coordination_report_replay_v180.py tests/test_order_coordination_coverage_closure_v180.py tests/test_order_coordination_snapshot_hardening_v180.py tests/test_release_packaging_cli_v190.py \
  --cov=ghost.examples.order_coordination --cov=ghost.examples.order_coordination_benchmark --cov=ghost.examples.order_coordination_demo --cov=ghost.examples.order_coordination_live_benchmark --cov=ghost.examples.order_coordination_report_replay \
  --cov-branch \
  --cov-report=term-missing \
  --cov-report=json:docs/coverage/v1.9.2/order_coordination.json
```

All three maintained v1.9.2 lanes are required to remain at **100% executable
statements and 100% branch outcomes**.

## Published Evidence

Current evidence lives under `docs/coverage/v1.9.2/`. Older versioned evidence
directories are retained as historical release records.
