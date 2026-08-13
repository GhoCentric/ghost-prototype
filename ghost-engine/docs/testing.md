# Testing and Validation

Ghost's executable test suite lives in [`../tests`](../tests).
Files under `docs/` are documentation only and are not a second test suite.

## Current v1.9.0 Checkpoint

From the `ghost-engine/` directory:

```bash
python -m pytest -q
```

Expected result for the synchronized v1.9.0 checkpoint:

```text
1674 passed, 1 skipped
```

The skipped test is intentionally gated. Normal validation does not require an
API key or a real network call.

## Install Development Test Tools

Ghost has no runtime dependencies. Local validation uses:

```bash
python -m pip install pytest hypothesis pytest-cov
```

## Quality Lanes

The authoritative commands and coverage boundaries are documented in
[`../QUALITY.md`](../QUALITY.md).

Published v1.9.0 results are summarized in
[`../COVERAGE.md`](../COVERAGE.md), with raw evidence under
[`coverage/v1.9.0/`](coverage/v1.9.0/).

The maintained branch-coverage lanes are:

- reusable Ghost core;
- the complete Ghost Revolution package;
- Order Coordination.

All three are expected to remain at 100% statements and branches.

## What the Suite Covers

The current suite validates, among other things:

- deterministic state evolution and bounded relationship math;
- JSON-safe public packets and copy isolation;
- snapshot validation, migration, restoration, and atomic failure behavior;
- social propagation, temperament, threat response, and policy branches;
- epistemic facts, observations, claims, evidence, provenance, beliefs, and
  revision;
- combat control, objectives, scenario configuration, and scenario runtime;
- Ghost Revolution campaign state, guards, raids, combat, feints, endgame
  routing, LLM boundaries, presentation, benchmarks, and deterministic snapshot
  forks;
- Order Coordination ambiguity, correction, confirmation freshness,
  idempotency, snapshot hardening, paired model proposals, and offline replay;
- package imports, public API contracts, packaging metadata, and CLI entry-point
  contracts;
- throughput floors.

## Reproducible Epistemic Benchmark

The controlled Ghost Revolution scenario matrix is documented in
[`../BENCHMARK_RESULTS.md`](../BENCHMARK_RESULTS.md).

Run it with:

```bash
python -m ghost.examples.ghost_revolution.benchmarks.epistemic_scenario_matrix_benchmark
```

## Public v1.9.0 Demo Commands

The package exposes eleven console commands. The three v1.9 additions are:

```text
ghost-epistemic-demo
ghost-revolution-demo
ghost-order-coordination-demo
```

The complete console-script contract is defined in `pyproject.toml` and guarded
by `tests/test_release_packaging_cli_v190.py`.

## Order Coordination Reference Tests

Run the deterministic demo with:

```bash
ghost-order-coordination-demo
```

or:

```bash
python -m ghost.examples.order_coordination_demo
```

Order Coordination is application-layer example code. The core owns generic
state/epistemic primitives; the application owns items, modifiers,
clarification, confirmation, and submission policy.

## Evidence Policy

Generated screenshots are not stored as current validation evidence because
they become stale as the package evolves. Reproducible commands,
machine-readable coverage reports, committed tests, benchmark source, and exact
terminal-output text reports are the source of truth.

Historical release evidence remains under versioned directories such as
`docs/coverage/v1.8.0/`; current v1.9.0 evidence lives under
`docs/coverage/v1.9.0/`.
