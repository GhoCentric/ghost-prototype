# Ghost Engine Coverage Results

These results were generated from the synchronized **v1.10.0** release-prep
working tree using branch coverage. The complete uninstrumented suite remains
the release gate.

Generated: `2026-08-19T17:20:32.980209+00:00`

## Summary

| Lane | Covered statements | Statement coverage | Covered branches | Branch coverage | Fully covered files |
|---|---:|---:|---:|---:|---:|
| Reusable Ghost core | 4,433 / 4,433 | 100.00% | 1,898 / 1,898 | 100.00% | 25 / 25 |
| Complete Ghost Revolution package | 7,201 / 7,201 | 100.00% | 2,744 / 2,744 | 100.00% | 19 / 19 |
| Order Coordination | 1,624 / 1,624 | 100.00% | 542 / 542 | 100.00% | 5 / 5 |

All three maintained v1.10.0 coverage lanes are at **100% executable
statements and 100% branch outcomes**.

## Test Runs

```text
Core coverage lane:        2390 passed, 0 skipped
Ghost Revolution lane:     700 passed, 0 skipped
Order Coordination lane:   122 passed, 0 skipped
Full uninstrumented suite: 2390 passed, 1 skipped
```

## Evidence

- `docs/coverage/v1.10.0/core.txt` / `core.json`
- `docs/coverage/v1.10.0/revolution.txt` / `revolution.json`
- `docs/coverage/v1.10.0/order_coordination.txt` / `order_coordination.json`

## Interpretation

Coverage proves which executable statements and branch outcomes were observed
by tests. It does not prove that every requirement or design choice is correct;
release validation also includes explicit contracts, artifact inspection,
isolated installation, and the full test suite.
