import random
import copy

from ghost.engine import GhostEngine


def random_step():
    """Generate adversarial/broken/random step inputs."""

    intents = ["threat", "help", "greet", None, "", 123]
    actors = ["a", "b", "npc", "", None, 42]
    intensities = [-1, 0, 0.5, 1, 2, "bad", None]

    return {
        "source": random.choice(["npc_engine", None, "", 123]),
        "intent": random.choice(intents),
        "actor": random.choice(actors),
        "target": random.choice(actors),
        "intensity": random.choice(intensities),
    }


def test_fuzz_determinism_strong():
    """Strong determinism test under adversarial input."""

    seed = 1337
    random.seed(seed)

    seq = [random_step() for _ in range(2000)]

    # --- Run 1 ---
    engine1 = GhostEngine()
    snaps1 = []

    for i, step in enumerate(seq):

        try:
            engine1.step(step)
        except Exception:
            pass

        # snapshot checkpoints (every 200 steps)
        if i % 200 == 0:
            snaps1.append(copy.deepcopy(engine1.snapshot()))

    final1 = engine1.snapshot()

    # --- Run 2 (Replay) ---
    engine2 = GhostEngine()
    snaps2 = []

    for i, step in enumerate(seq):

        try:
            engine2.step(step)
        except Exception:
            pass

        if i % 200 == 0:
            snaps2.append(copy.deepcopy(engine2.snapshot()))

    final2 = engine2.snapshot()

    # --- Assertions ---
    assert snaps1 == snaps2
    assert final1 == final2
