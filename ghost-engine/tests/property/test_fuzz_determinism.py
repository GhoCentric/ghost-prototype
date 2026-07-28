"""Replayable adversarial-input determinism tests."""

from __future__ import annotations

import copy
import random
from typing import Any

from ghost.engine import GhostEngine


TRACE_LENGTH = 2_000
CHECKPOINT_INTERVAL = 200


def build_adversarial_trace(
    seed: int,
    length: int = TRACE_LENGTH,
) -> list[dict[str, Any]]:
    """Build one reproducible mix of accepted and rejected inputs."""

    rng = random.Random(seed)

    intents = (
        "threat",
        "help",
        "greet",
        None,
        "",
        123,
    )

    actors = (
        "a",
        "b",
        "npc",
        " guard ",
        "",
        "   ",
        None,
        42,
        "bad|id",
    )

    intensities = (
        -1,
        0,
        0.5,
        1,
        2,
        "bad",
        None,
        True,
        float("nan"),
        float("inf"),
    )

    return [
        {
            "source": rng.choice(
                ("npc_engine", None, "", 123)
            ),
            "intent": rng.choice(intents),
            "actor": rng.choice(actors),
            "target": rng.choice(actors),
            "intensity": rng.choice(intensities),
        }
        for _ in range(length)
    ]


def replay_trace(
    trace: list[dict[str, Any]],
) -> dict[str, Any]:
    """Replay a trace and retain its accepted/rejected transcript."""

    engine = GhostEngine()
    outcomes = []
    checkpoints = []
    accepted_steps = 0

    for index, raw_step in enumerate(trace, start=1):
        before = engine.snapshot()

        try:
            engine.step(copy.deepcopy(raw_step))
        except (TypeError, ValueError) as error:
            after = engine.snapshot()

            assert after == before, (
                "Rejected public input mutated engine state at "
                f"trace position {index}."
            )

            outcomes.append(
                (
                    "rejected",
                    type(error).__name__,
                    str(error),
                )
            )
        else:
            accepted_steps += 1
            after = engine.snapshot()

            assert after["cycles"] == accepted_steps
            assert after["npc"]["threat_level"] >= 0.0

            outcomes.append(
                (
                    "accepted",
                    after["cycles"],
                    after["npc"]["threat_level"],
                )
            )

        if index % CHECKPOINT_INTERVAL == 0:
            checkpoints.append(engine.snapshot())

    return {
        "outcomes": outcomes,
        "checkpoints": checkpoints,
        "final": engine.snapshot(),
    }


def test_fuzz_determinism_strong():
    """Accepted and rejected public inputs must replay identically."""

    trace = build_adversarial_trace(seed=1337)

    first = replay_trace(trace)
    second = replay_trace(trace)

    assert first == second
    assert any(
        item[0] == "accepted"
        for item in first["outcomes"]
    )
    assert any(
        item[0] == "rejected"
        for item in first["outcomes"]
    )
