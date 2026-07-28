"""Opt-in local performance regression guard for GhostEngine."""

from __future__ import annotations

import os
import time
from statistics import median

import pytest

from ghost.engine import GhostEngine


WARMUP_STEPS = 2_000
MEASURED_STEPS = 20_000
SAMPLES = 3
MIN_MEDIAN_IPS = 50_000

RUN_LOCAL_PERFORMANCE_GUARD = (
    os.environ.get("GHOST_RUN_PERFORMANCE") == "1"
)


def measure_ips() -> float:
    """Measure one warmed-up deterministic engine workload."""

    engine = GhostEngine()

    step = {
        "source": "perf",
        "intent": "threat",
        "actor": "npc",
        "intensity": 0.5,
    }

    for _ in range(WARMUP_STEPS):
        engine.step(step)

    started = time.perf_counter_ns()

    for _ in range(MEASURED_STEPS):
        engine.step(step)

    elapsed_ns = time.perf_counter_ns() - started

    assert elapsed_ns > 0

    return (
        MEASURED_STEPS
        * 1_000_000_000
        / elapsed_ns
    )


@pytest.mark.performance
@pytest.mark.skipif(
    not RUN_LOCAL_PERFORMANCE_GUARD,
    reason=(
        "local performance guard is opt-in; run "
        "GHOST_RUN_PERFORMANCE=1 pytest -q -m performance"
    ),
)
def test_ips_floor():
    """Median throughput must resist accidental slowdowns."""

    samples = [
        measure_ips()
        for _ in range(SAMPLES)
    ]

    median_ips = median(samples)

    assert median_ips >= MIN_MEDIAN_IPS, (
        "Performance dropped below the local regression floor: "
        f"median={median_ips:.0f} IPS, "
        f"samples={[round(sample) for sample in samples]}, "
        f"floor={MIN_MEDIAN_IPS}."
    )
