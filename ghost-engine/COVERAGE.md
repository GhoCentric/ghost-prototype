# Ghost Engine Coverage Results

These results were generated from the synchronized **v1.8.0** Termux working
tree using branch coverage. The complete uninstrumented suite remains the
release gate.

Generated: `2026-08-12T22:48:30+00:00`
Python: `3.13.13`
pytest: `9.1.1`
coverage.py: `7.15.2`

## Summary

| Lane | Covered statements | Statement coverage | Covered branches | Branch coverage | Fully covered files |
|---|---:|---:|---:|---:|---:|
| Reusable Ghost core | 3,112 / 3,112 | 100.00% | 1,276 / 1,276 | 100.00% | 21 / 21 |
| Complete Ghost Revolution package | 7,149 / 7,149 | 100.00% | 2,736 / 2,736 | 100.00% | 18 / 18 |
| Order Coordination | 1,622 / 1,622 | 100.00% | 542 / 542 | 100.00% | 5 / 5 |

All three maintained v1.8.0 coverage lanes are at **100% executable statements
and 100% branch outcomes**.

## Test Runs

```text
Core coverage lane:        1667 passed, 1 deselected
Ghost Revolution lane:     694 passed
Order Coordination lane:   115 passed
Full uninstrumented suite:  1667 passed, 1 skipped
```

## Reusable Core

Scope: reusable modules directly under `ghost/`; `ghost/examples/` is excluded
through `coverage.core.ini`.

```text
Statements: 3,112 / 3,112
Branches:   1,276 / 1,276
Files:      21 / 21 fully covered
```

Evidence:

- [`core.txt`](docs/coverage/v1.8.0/core.txt)
- [`core.json`](docs/coverage/v1.8.0/core.json)

## Complete Ghost Revolution Package

Scope: every Python runtime file under
`ghost/examples/ghost_revolution/`, including presentation, developer tooling,
benchmarks, and deterministic campaign/combat modules.

```text
Statements: 7,149 / 7,149
Branches:   2,736 / 2,736
Files:      18 / 18 fully covered
```

Evidence:

- [`revolution.txt`](docs/coverage/v1.8.0/revolution.txt)
- [`revolution.json`](docs/coverage/v1.8.0/revolution.json)

## Order Coordination

Scope: the five application/benchmark modules beginning with
`ghost.examples.order_coordination`. This is a reference application built on
the public Ghost API, not restaurant/order logic inside core.

```text
Statements: 1,622 / 1,622
Branches:   542 / 542
Files:      5 / 5 fully covered
```

Evidence:

- [`order_coordination.txt`](docs/coverage/v1.8.0/order_coordination.txt)
- [`order_coordination.json`](docs/coverage/v1.8.0/order_coordination.json)

## Interpretation

Coverage proves which executable statements and branch outcomes were observed
by tests. It does not prove that every requirement is correct, every assertion
is meaningful, or every design choice is optimal.

The release gate therefore combines explicit architecture review, deterministic
tests, coverage audits, snapshot/rollback checks, and the complete
uninstrumented test suite.
