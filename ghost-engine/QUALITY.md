# Ghost Quality Lanes

Ghost uses separate quality lanes so terminal demos, coverage tracing,
and performance checks do not distort one another.

## Full Normal Suite

Runs every test, including local performance regression checks.

    pytest -q

## Performance Only

Runs local throughput checks without coverage tracing.

    pytest -q -m performance

## Core Coverage

Measures Ghost core modules while excluding examples and terminal demos.

    REPORT_DIR="quality-reports/core_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$REPORT_DIR"

    pytest -q -m "not performance" \
      --cov=ghost \
      --cov-config=coverage.core.ini \
      --cov-report=term \
      --cov-report="json:$REPORT_DIR/coverage.json"

## Ghost Revolution Runtime Coverage

Measures the deterministic Revolution runtime only:

- configuration
- social bridge
- raid domain
- campaign facade

Terminal presentation remains outside this lane.

    REPORT_DIR="quality-reports/revolution_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$REPORT_DIR"

    pytest -q -m "not performance" \
      --cov=ghost.examples.ghost_revolution_config \
      --cov=ghost.examples.ghost_revolution_social \
      --cov=ghost.examples.ghost_revolution_raid \
      --cov=ghost.examples.ghost_revolution_demo \
      --cov-config=coverage.revolution.ini \
      --cov-report=term \
      --cov-report="json:$REPORT_DIR/coverage.json"

## Policy

Do not add a fail-under threshold until every missing path is reviewed.

A missing path must be classified as one of:

1. reachable behavior that needs a test
2. defensive behavior that needs an invalid-input test
3. obsolete code that should be deleted
4. terminal presentation behavior belonging in its own lane

Target:

- Core lane: 100 percent statements and branches
- Revolution runtime lane: 100 percent statements and branches
- Performance: normal pytest only, never coverage-traced
- Mutation testing: later, on GitHub Actions or normal Linux
