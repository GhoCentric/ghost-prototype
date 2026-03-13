# tests/bench_runtime_stress.py

import random
import time
import tracemalloc

from world.ghost_runtime import GhostRuntime


# ------------------------------------------------------------
# FAST TARGET SELECTION (O(1))
# ------------------------------------------------------------
def choose_target(rt, agents, next_agent, actor, bias_existing=0.75):
    neighbors = rt._neighbors.get(actor)

    if neighbors and random.random() < bias_existing:
        return random.choice(tuple(neighbors))

    target = random.choice(agents)

    # O(1) fallback if self-selected
    if target == actor:
        return next_agent[actor]

    return target


# ------------------------------------------------------------
# MAIN STRESS RUNNER
# ------------------------------------------------------------
def run_runtime_stress(
    n_agents=5_000,
    ticks=50,
    interactions_per_tick=5_000,
    dt=1.0,
    seed=7,
    report_every=10,
    track_mem=True,
):

    random.seed(seed)
    rt = GhostRuntime()

    # --------------------------------------------------------
    # AGENT SETUP (FASTEST POSSIBLE)
    # --------------------------------------------------------
    agents = [f"N{i}" for i in range(n_agents)]

    # O(1) deterministic fallback map
    next_agent = {
        agents[i]: agents[(i + 1) % n_agents]
        for i in range(n_agents)
    }

    choice = random.choice
    rand = random.random
    apply_event = rt.apply_event

    kinds = ("conflict", "support", "betrayal", "alliance", "argue")

    if track_mem:
        tracemalloc.start()

    t0 = time.perf_counter()
    total_events = 0

    
    # --------------------------------------------------------
    # MAIN LOOP
    # --------------------------------------------------------
    for t in range(1, ticks + 1):

        for _ in range(interactions_per_tick):

            a = choice(agents)

            b = choose_target(rt, agents, next_agent, a)

            kind = choice(kinds)
            intensity = rand() ** 0.7

            apply_event({
                "kind": kind,
                "actor_id": a,
                "target_id": b,
                "payload": {"intensity": intensity},
            })

            total_events += 1

        rt.tick(dt=dt)

        # ----------------------------------------------------
        # REPORTING
        # ----------------------------------------------------
        if (t % report_every) == 0 or t == ticks:

            elapsed = time.perf_counter() - t0
            ips = total_events / max(1e-9, elapsed)

            snap = rt.snapshot()
            emerg = rt.relationship_metrics()
            factions = rt.faction_snapshot(agents, max_nodes=400)

            tension = snap.get("global_tension", 0.0)
            stability = snap.get("stability_index", 1.0)

            rel_count = len(rt._rels)

            if track_mem:
                current, peak = tracemalloc.get_traced_memory()
                mem_str = f"mem={current/1e6:.1f}MB peak={peak/1e6:.1f}MB"
            else:
                mem_str = "mem=off"

            print(
                f"[t={t}/{ticks}] "
                f"ips={ips:,.0f} {mem_str} "
                f"| tension={tension:.3f} stability={stability:.3f} "
                f"| rels={rel_count} "
                f"| cascades={emerg.get('cascade_events')} "
                f"| strong_edges={emerg.get('strong_edges')} "
                f"| max_rivalry={emerg.get('max_rivalry'):.3f} "
                f"| factions={factions.get('factions')} "
                f"| sizes={factions.get('top_sizes')}"
            )

    if track_mem:
        tracemalloc.stop()

    if hasattr(rt, "export_relationship_graph_gexf"):
        rt.export_relationship_graph_gexf("graph_export.gexf")

    # --------------------------------------------------------
    # RETURN FINAL METRICS (NEW)
    # --------------------------------------------------------
    return {
        "ips": ips,
        "rels": rel_count,
        "cascades": emerg.get("cascade_events"),
        "strong_edges": emerg.get("strong_edges"),
        "max_rivalry": emerg.get("max_rivalry"),
        "factions": factions.get("factions"),
        "top_sizes": factions.get("top_sizes"),
        "tension": tension,
        "stability": stability,
    }


# ------------------------------------------------------------
# ENTRYPOINT (CLEAN VERSION)
# ------------------------------------------------------------
if __name__ == "__main__":

    print("\n=== SOCIAL STRESS MODE ===\n")

    stress_stats = run_runtime_stress()

    print("\n=== PERF MODE ===\n")

    perf_stats = run_runtime_stress(
        track_mem=False,
        interactions_per_tick=10_000,
        report_every=100,
    )

    print("PERF SUMMARY\n")

    print(f"IPS:           {perf_stats['ips']:,.0f}")
    print(f"Relationships: {perf_stats['rels']:,}")
    print(f"Cascades:      {perf_stats['cascades']:,}")
    print(f"Strong edges:  {perf_stats['strong_edges']}")
    print(f"Max rivalry:   {perf_stats['max_rivalry']:.3f}")
    print(f"Factions:      {perf_stats['factions']}")
    print(f"Top sizes:     {perf_stats['top_sizes']}")
    print(f"Tension:       {perf_stats['tension']:.3f}")
    print(f"Stability:     {perf_stats['stability']:.3f}")
