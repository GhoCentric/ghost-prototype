# Ghost Quality Lanes

Ghost separates release regression, performance evidence, and branch-coverage tracing so one lane does not distort another.

## Full Release Regression

```bash
python -m pytest -q -p no:cacheprovider \
  --ignore-glob='tests/test_npc_continuity_stage*_v1110.py' \
  --ignore=tests/test_m3_continuity_production_value.py \
  --ignore=tests/test_continuity_optimization_value_v1110.py \
  -W error::ResourceWarning
```

Current v1.11.0 release-candidate checkpoint:

```text
2745 passed, 1 skipped
```

Frozen Stage-1–10 research/value evidence is retained separately from this release regression. The selected continuity production implementation carries its own measurement-hardened performance evidence under `docs/evidence/v1.11-dev/continuity/`.

## Reusable Core Coverage

```bash
python -m pytest -q -m "not performance" \
  --ignore-glob='tests/test_npc_continuity_stage*_v1110.py' \
  --cov=ghost --cov-config=coverage.core.ini --cov-branch \
  --cov-report=term-missing \
  --cov-report=json:docs/coverage/v1.11.0/core.json
```

## Complete Ghost Revolution Package Coverage

```bash
python -m pytest -q tests/ghost_revolution \
  --cov=ghost.examples.ghost_revolution \
  --cov-config=coverage.revolution.ini --cov-branch \
  --cov-report=term-missing \
  --cov-report=json:docs/coverage/v1.11.0/revolution.json
```

## Order Coordination Coverage

The maintained Order Coordination lane remains the explicit focused test set listed in Release Preparation Pass 2 and writes `docs/coverage/v1.11.0/order_coordination.json`.

All three maintained v1.11.0 lanes are required to remain at **100% executable statements and 100% branch outcomes**.

## Published Evidence

Current release-candidate coverage evidence lives under `docs/coverage/v1.11.0/`. Older versioned evidence directories remain historical records.
