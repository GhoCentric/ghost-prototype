# ghocentric-ghost-engine

A lightweight, deterministic internal state engine for experimenting with
persistent state, temporal dynamics, and emergent behavior in interactive systems.

Ghost is NOT a language model and NOT a decision-maker.
It is a minimal, stateful core designed to accumulate interaction signals over time
and expose them in a clean, predictable, and serialization-safe way.

This project is intentionally focused on architecture and correctness first.
Surface features, integrations, and higher-level reasoning systems are expected
to be layered on top of the core in later versions.

---

INSTALLATION

pip install ghocentric-ghost-engine

---

BASIC USAGE

from ghost.engine import GhostEngine

engine = GhostEngine()

engine.step({
    "source": "npc_engine",
    "intent": "threat",
    "actor": "player",
    "intensity": 0.5,
})

state = engine.state()
print(state["npc"]["threat_level"])

Ghost mutates state only via explicit step() calls.
All public-facing state is exposed as dictionaries and is safe to serialize.

---

CORE DESIGN PRINCIPLES

- Deterministic, persistent state core
- Explicit state transitions via step()
- No hidden execution or side effects
- Public API remains dict-based and serialization-safe
- Internal typed representations may exist but never leak
- Designed to be expanded around a stable core, not bloated prematurely

Ghost does NOT:
- Choose actions
- Generate dialogue
- Interpret semantics
- Store memory implicitly

Those behaviors belong to external systems that consume Ghost’s state.

---

STABILITY & GUARANTEES (v0.1.2)

Ghost Engine v0.1.2 establishes a formally verified core protected by
property-based testing using Hypothesis.

Verified invariants include:
- Threat level is never negative
- Threat accumulation is monotonic with respect to input intensity
- Threat decays monotonically in the absence of new input
- Actor-specific threat memory remains consistent
- Internal step types never leak into public engine state
- Engine state mutates only through explicit step() calls

These guarantees hold under randomized and adversarial input.

ARCHITECTURAL EXPANSION (v0.1.3)

Version 0.1.3 introduces the first structural components required for modeling
multi-agent interaction systems on top of Ghost's deterministic state core.

This release does not change the fundamental guarantees of the engine.
Instead, it expands the internal architecture to support scalable interaction graphs.

New components include:

AgentRegistry
A centralized registry responsible for managing and resolving agents participating in the simulation.  
This allows Ghost to maintain consistent references to actors across interactions without introducing hidden state.

Neighbor Index
Relationships between agents are now indexed through a neighbor structure rather than requiring full scans of the relationship table.

Example conceptually:

("Alice","Bob") → relationship

Previously required scanning the entire relationship set to answer:

Who interacts with Alice?

With the neighbor index:

neighbors["Alice"] → {"Bob", "Charlie", "Dave"}

This allows constant-time queries of an agent's interaction network.

Why This Matters

These changes allow Ghost-based systems to scale toward:

- 100k+ agents
- millions of relationships
- fast simulation steps

while preserving the deterministic, explicit-state philosophy of the engine.

The interaction architecture introduced in v0.1.3 lays the groundwork for future systems such as:

- social modeling
- alliances and betrayal
- trade networks
- large-scale emergent agent worlds

---

TESTING PHILOSOPHY

Ghost uses property-based testing to validate behavioral invariants rather than
relying solely on example-driven tests.

This ensures the engine remains correct and predictable as new systems and features
are layered on top in future versions.

---

PROJECT STRUCTURE

ghost/           core engine modules
tests/           invariant and property-based tests
npc_demo.py      experimental sandbox for new ideas
pyproject.toml   build and packaging configuration

Demos are intentionally minimal and act as experimental sandboxes.
They are not representative of Ghost’s final scope.

---

STATUS

Ghost Engine is in early development.
The core architecture is stable as of v0.1.2, but APIs may evolve as new layers are added.

This project is intended as a foundation for experimentation, research, and
future system design rather than a finished product.

RELEASE HISTORY

v0.1.3
AgentRegistry and neighbor indexing for scalable multi-agent interaction graphs.

v0.1.2
Formal invariant verification using property-based testing.

v0.1.1
Core threat accumulation improvements.

v0.1.0
Initial public architecture release.
