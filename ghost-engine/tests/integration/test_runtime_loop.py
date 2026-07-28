"""Deterministic long-run integration coverage for GhostEngine."""

from __future__ import annotations

from collections import Counter
import copy
import random

from ghost.engine import GhostEngine


STEPS = 10_000
CHECKPOINT_INTERVAL = 1_000


def build_runtime_trace(
    seed: int,
    steps: int = STEPS,
) -> list[dict | None]:
    """Build a valid, replayable runtime workload."""

    rng = random.Random(seed)
    actors = ("a", "b", "c", "d")
    intents = ("greet", "help", "threat")
    trace: list[dict | None] = []

    for _ in range(steps):
        if rng.randrange(5) == 0:
            trace.append(None)
            continue

        trace.append(
            {
                "source": "runtime",
                "intent": rng.choice(intents),
                "actor": rng.choice(actors),
                "target": (
                    rng.choice(actors)
                    if rng.randrange(2)
                    else None
                ),
                "intensity": rng.random(),
            }
        )

    return trace


def replay_runtime_trace(
    trace: list[dict | None],
) -> dict:
    """Run a workload while checking cycle and state invariants."""

    engine = GhostEngine()
    checkpoints = []

    for cycle, step in enumerate(trace, start=1):
        result = engine.step(copy.deepcopy(step))
        state = engine.state()

        assert result is state
        assert state["cycles"] == cycle
        assert state["npc"]["threat_level"] >= 0.0

        for actor_data in state["npc"].get(
            "actors",
            {},
        ).values():
            assert actor_data["threat_count"] >= 0

        if cycle % CHECKPOINT_INTERVAL == 0:
            checkpoints.append(engine.snapshot())

    return {
        "checkpoints": checkpoints,
        "final": engine.snapshot(),
    }


def test_runtime_loop_stability():
    """A long mixed runtime trace must be deterministic and lossless."""

    trace = build_runtime_trace(seed=9_173)

    left = replay_runtime_trace(trace)
    right = replay_runtime_trace(trace)

    assert left == right

    expected_threat_counts = Counter(
        step["actor"]
        for step in trace
        if step is not None
        and step["intent"] == "threat"
    )

    actor_memory = left["final"]["npc"].get(
        "actors",
        {},
    )

    assert {
        actor: data["threat_count"]
        for actor, data in actor_memory.items()
    } == dict(expected_threat_counts)
