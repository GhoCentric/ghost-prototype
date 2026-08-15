# Ghost Engine Coverage Results

These results were generated from the synchronized **v1.9.1** release working
tree using branch coverage. The complete uninstrumented suite remains the
release gate.

Generated: `2026-08-15T19:20:08+00:00`

## Summary

| Lane | Covered statements | Statement coverage | Covered branches | Branch coverage | Fully covered files |
|---|---:|---:|---:|---:|---:|
| Reusable Ghost core | 3,112 / 3,112 | 100.00% | 1,276 / 1,276 | 100.00% | 21 / 21 |
| Complete Ghost Revolution package | 7,201 / 7,201 | 100.00% | 2,744 / 2,744 | 100.00% | 19 / 19 |
| Order Coordination | 1,624 / 1,624 | 100.00% | 542 / 542 | 100.00% | 5 / 5 |

All three maintained v1.9.1 coverage lanes are at **100% executable statements
and 100% branch outcomes**.

## Test Runs

```text
Core coverage lane:        1680 / 0
Ghost Revolution lane:     700 / 0
Order Coordination lane:   122 / 0
Full uninstrumented suite:  1680 passed, 1 skipped
```

## Evidence

- `docs/coverage/v1.9.1/core.txt` / `core.json`
- `docs/coverage/v1.9.1/revolution.txt` / `revolution.json`
- `docs/coverage/v1.9.1/order_coordination.txt` / `order_coordination.json`

## Interpretation

Coverage proves which executable statements and branch outcomes were observed
by tests. It does not prove that every requirement or design choice is correct;
release validation also includes explicit contracts, artifact inspection,
isolated installation, and the full test suite.
