# ghocentric-ghost-engine

A lightweight, deterministic internal state engine for experimenting with persistent state, temporal dynamics, and emergent behavior in interactive systems.

Ghost is **NOT** a language model and **NOT** a decision-maker.  
It is a minimal, stateful core designed to accumulate interaction signals over time and expose them in a clean, predictable, and serialization-safe way.

This project is intentionally focused on architecture and correctness first. Surface features, integrations, and higher-level reasoning systems are expected to be layered on top of the core.

---

## Installation

```bash
pip install ghocentric-ghost-engine
```

---

## Basic Usage

```python
from ghost.engine import GhostEngine

engine = GhostEngine()

engine.step({
    "source": "npc_engine",
    "intent": "threat",
    "actor": "player",
    "target": "guard",
    "intensity": 0.5,
})

state = engine.state()
print(state["npc"]["threat_level"])
```

Ghost mutates state only through explicit `step()` calls.  
All public-facing state is exposed as dictionaries and is safe to serialize.

---

---

## Emotional Inertia System (v1.0.0)

Ghost now includes a deterministic emotional inertia system for modeling NPC relationships over time.

Unlike simple accumulation or smoothing systems, relationships in Ghost:

- remember past interactions
- resist sudden changes
- decay over time
- respond differently depending on history

This enables more realistic behavior under oscillating inputs such as:

insult → help → insult → help

Where traditional systems reset or average out, Ghost preserves emotional direction.

---

## Dual-Channel Relationship Model

Relationships are no longer a single value.

Each relationship now tracks:

positive reservoir (pos)
negative reservoir (neg)

trust = pos - neg

This allows:

- damage to persist independently of recovery
- recovery to require sustained effort
- asymmetric emotional behavior

---

## Emotional Dynamics

Ghost relationships now include:

Resistance

High negative history reduces the effectiveness of positive events.

Saturation

Repeated positive interactions produce diminishing returns.

Time-Based Decay

Relationships evolve over time using:

ghost.tick()

Decay is no longer tied only to events.

---

## Personality Presets

Relationships can now have different emotional profiles:

ghost.engine.relationships.set_personality("A", "B", "resentful")

Available presets:

- balanced
- forgiving
- resentful
- volatile

Each preset modifies:

- gain sensitivity
- decay speed
- recovery behavior

---

## Relationship State System

Ghost now exposes human-readable relationship states:

rel = ghost.get_relationship("A", "B")

rel["state"]        # "hostile", "neutral", "friendly"
rel["transition"]   # ("neutral", "hostile")
rel["trigger"]      # {"event": "relationship_broken"}

---

## Event Triggers

State transitions generate structured events:

- "relationship_broken"
- "deescalation"
- "forgiveness"
- "state_shift"

These can be used by external systems for:

- dialogue changes
- combat behavior
- faction reactions
- narrative events

---

## Oscillation Behavior (Key Difference)

Ghost is specifically designed to handle oscillating interaction patterns.

Example:

sequence = ["insult", "insult", "help", "help"]

Produces:

- escalation into hostility
- resistance to recovery
- gradual de-escalation (not instant reset)

This behavior cannot be replicated by:

- additive systems ("trust += delta")
- low-pass filters (exponential smoothing)

Proof Demo (v1.0.0)

Ghost now includes a deterministic proof demo comparing its emotional inertia model against a standard linear baseline.

Run:

```bash
python examples/relationship_proof_demo.py
```

What this demonstrates:

Two systems receive the exact same sequence of inputs:

    help → help → insult → help → help → betrayal → help

Baseline (linear smoothing):
- Gradually returns toward neutral
- Does not retain strong emotional history

Ghost:
- Accumulates emotional weight
- Resists recovery after damage
- Maintains directional state over time

Example Output:

```
Step | Event     | Baseline | Ghost   | State
------------------------------------------------
5    | betrayal  | -0.121   | -0.703  | hostile
6    | help      | -0.036   | -0.628  | hostile
```

Key Observation:

Even after positive input ("help"), Ghost remains in a hostile state due to accumulated negative history, while the baseline system rapidly normalizes.

This demonstrates:

- persistent emotional memory  
- resistance to reversal  
- non-linear recovery behavior  

The demo also exposes:

state transitions (friendly → hostile)  
trigger events (relationship_broken, forgiveness, etc.)  
gameplay-relevant consequences of emotional state  

This serves as a minimal, reproducible proof that Ghost behaves fundamentally differently from traditional smoothing or accumulation systems.
---

## New API Additions

ghost.apply_event(a, b, event)
ghost.tick()
ghost.get_relationship(a, b)

New fields returned:

{
    "trust": float,
    "state": str,
    "transition": tuple | None,
    "trigger": dict | None
}

---

## Summary of v1.0.0

v1.0.0 introduces a structured emotional runtime layer on top of the deterministic state core:

- dual-channel emotional memory
- resistance and saturation modeling
- time-based decay
- per-relationship personality tuning
- state interpretation and transition tracking
- event trigger system

Ghost is no longer just a state engine.

It is now a deterministic emotional inertia runtime for NPC systems.

---

## Core Design Principles

- Deterministic, persistent state core  
- Explicit state transitions via `step()`  
- No hidden execution or side effects  
- Public API remains dict-based and serialization-safe  
- Internal typed representations may exist but never leak  
- Designed to be expanded around a stable core  

### Ghost does NOT:

- Choose actions  
- Generate dialogue  
- Interpret semantics  
- Store memory implicitly  

These responsibilities belong to external systems that consume Ghost’s state.

---

## Stability & Guarantees (v0.2.2)

Ghost Engine v0.2.2 strengthens runtime correctness and serialization guarantees across public engine state.

The engine guarantees:

- Deterministic runtime behavior (same inputs → same outputs)  
- Explicit, bounded state mutation per step  
- Actor state updates across interactions  
- Actor-level threat accumulation tracking  
- Pairwise relationship mutation with symmetric consistency  
- Bounded cascade propagation across interaction networks  
- Deterministic nonlinear modulation of global system tension  
- Passive decay behavior during idle cycles  
- Fully JSON-safe public state and immutable snapshots  

These guarantees hold under repeated execution, long-run simulation, and adversarial input streams.

---

## Architectural Expansion (v0.2.x)

Recent releases introduce the first fully operational multi-agent interaction model on top of Ghost’s deterministic state core.

### Key Capabilities

**Agent State Mutation**  
Agents maintain evolving internal state (mood, tension, last intent) and react deterministically to interaction signals.

**Relationship Graph**  
Pairwise relationships evolve through explicit interaction deltas, supporting long-term system memory without hidden state.

**Bounded Cascade Propagation**  
Signals propagate deterministically through local interaction networks with strict bounds to prevent runaway behavior.

**Global System Tension**  
The engine tracks shared system pressure across interactions using deterministic nonlinear modulation.

**Actor Threat Memory**  
Agents maintain explicit per-actor threat accumulation history for structured introspection.

**Idle-State Decay Dynamics**  
Bounded passive decay improves long-run stability and prevents runaway system pressure.

---

## Testing Philosophy

Ghost uses property-based testing and invariant validation rather than relying solely on example-driven tests.

Core validation includes:

- determinism verification  
- bounded-state guarantees  
- serialization safety validation  

This ensures the engine remains correct and predictable as new systems are layered on top.

---

## Project Structure

```
ghost/        core engine modules  
tests/        invariant and runtime tests  
npc_demo.py   experimental sandbox  
pyproject.toml build configuration  
```

Demos are intentionally minimal and act as experimental sandboxes.  
They are not representative of Ghost’s final scope.

---

## Status

Ghost Engine remains in early development.

As of v0.2.x:

- The deterministic interaction core is stable  
- APIs may still evolve  
- Higher-level systems remain intentionally external  

This project is intended as a foundation for experimentation, research, and future system design rather than a finished product.

---

## Release History

v1.0.0

- Promoted Ghost from state engine to emotional inertia runtime
- Introduced dual-channel emotional memory model (positive / negative reservoirs)
- Replaced single-value trust updates with persistent emotional accumulation ("pos - neg")
- Added resistance mechanics (negative history reduces effectiveness of positive events)
- Added saturation mechanics (diminishing returns on repeated positive interactions)
- Implemented time-based relationship decay via "tick()" (decoupled from event updates)
- Added per-relationship parameter system (gain + decay tuning)
- Introduced personality presets (balanced, forgiving, resentful, volatile)
- Added relationship state classification (hostile → loyal spectrum)
- Implemented transition detection between relationship states
- Added structured trigger system (relationship_broken, deescalation, forgiveness, state_shift)
- Expanded public API to expose state, transitions, and triggers
- Established emotional inertia model as a first-class runtime system

**v0.2.2**
- Fixed public state serialization issue in relationship subsystem  
- Replaced set-based storage with JSON-safe structures  
- Strengthened invariant coverage across runtime state  

**v0.2.1**
- Added actor-level threat accumulation tracking  
- Introduced deterministic nonlinear system modulation  
- Implemented passive idle-cycle decay  
- Added immutable JSON-safe snapshots  

**v0.2.0**
- Introduced multi-agent state mutation  
- Added relationship mutation logic  
- Implemented bounded cascade propagation  
- Achieved deterministic runtime guarantees  

**v0.1.x**
- Foundational architecture releases
