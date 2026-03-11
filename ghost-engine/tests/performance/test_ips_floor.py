import time


def test_ips_floor():
    """
    Performance invariant:
    Ghost must maintain a minimum steps/sec rate.

    This prevents accidental slowdowns.
    """

    from ghost.engine import GhostEngine

    e = GhostEngine()

    STEPS = 20000  # enough for stable timing
    MIN_IPS = 50000  # adjust if needed for phone

    start = time.perf_counter()

    for _ in range(STEPS):
        e.step({
            "source": "perf",
            "intent": "threat",
            "actor": "npc",
            "intensity": 0.5
        })

    elapsed = time.perf_counter() - start
    ips = STEPS / elapsed

    print(f"\nIPS: {ips:.0f}")

    assert ips >= MIN_IPS, f"Performance dropped: {ips:.0f} < {MIN_IPS}"
