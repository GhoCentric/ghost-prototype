# Ghost Engine Coverage Results

These results were generated from the synchronized **v1.9.2** release working
tree using branch coverage. The complete uninstrumented suite remains the
release gate.

Generated: `2026-08-16T19:33:35+00:00`

## Summary

| Lane | Covered statements | Statement coverage | Covered branches | Branch coverage | Fully covered files |
|---|---:|---:|---:|---:|---:|
| Reusable Ghost core | 3,498 / 3,498 | 100.00% | 1,418 / 1,418 | 100.00% | 22 / 22 |
| Complete Ghost Revolution package | 7,201 / 7,201 | 100.00% | 2,744 / 2,744 | 100.00% | 19 / 19 |
| Order Coordination | 1,624 / 1,624 | 100.00% | 542 / 542 | 100.00% | 5 / 5 |

All three maintained v1.9.2 coverage lanes are at **100% executable statements
and 100% branch outcomes**.

## Test Runs

```text
Core coverage lane:        1763 / 0
Ghost Revolution lane:     700 / 0
Order Coordination lane:   122 / 0
Full uninstrumented suite:  1763 passed, 1 skipped
```

## Evidence

- `docs/coverage/v1.9.2/core.txt` / `core.json`
- `docs/coverage/v1.9.2/revolution.txt` / `revolution.json`
- `docs/coverage/v1.9.2/order_coordination.txt` / `order_coordination.json`

## Interpretation

Coverage proves which executable statements and branch outcomes were observed
by tests. It does not prove that every requirement or design choice is correct;
release validation also includes explicit contracts, artifact inspection,
isolated installation, and the full test suite.
