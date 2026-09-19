# Ghost Engine Coverage Results

These results were generated from the synchronized **v1.11.0 release-candidate** working tree using branch coverage. The uninstrumented release regression remains a separate gate.

Generated: `2026-09-19T20:27:34.498444+00:00`

## Summary

| Lane | Covered statements | Statement coverage | Covered branches | Branch coverage | Fully covered files |
|---|---:|---:|---:|---:|---:|
| Reusable Ghost core | 6,801 / 6,801 | 100.00% | 2,828 / 2,828 | 100.00% | 33 / 33 |
| Complete Ghost Revolution package | 7,201 / 7,201 | 100.00% | 2,744 / 2,744 | 100.00% | 19 / 19 |
| Order Coordination | 1,624 / 1,624 | 100.00% | 542 / 542 | 100.00% | 5 / 5 |

All three maintained v1.11.0 coverage lanes are at **100% executable statements and 100% branch outcomes**.

## Test Runs

```text
Core coverage lane:        2748 passed, 1 deselected, 1 warning in 713.64s (0:11:53)
Ghost Revolution lane:     700 passed, 1 warning in 74.61s (0:01:14)
Order Coordination lane:   122 passed, 1 warning in 23.83s
Release regression:        2745 passed, 1 skipped in 112.55s (0:01:52)
```

## Evidence

- `docs/coverage/v1.11.0/core.txt` / `core.json`
- `docs/coverage/v1.11.0/revolution.txt` / `revolution.json`
- `docs/coverage/v1.11.0/order_coordination.txt` / `order_coordination.json`

Coverage proves which executable statements and branch outcomes were observed by tests. It does not prove that every requirement or design choice is correct; release validation also includes explicit contracts, architecture audits, artifact inspection, isolated installation, public-version upgrade restoration, and the full release regression.
