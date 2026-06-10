# ghocentric-ghost-engine

A lightweight, deterministic internal state engine for experimenting with persistent state, temporal dynamics, emotional inertia, and emergent behavior in interactive systems.

Ghost is **NOT** a language model and **NOT** a decision-maker.

It is a minimal, stateful core designed to accumulate interaction signals over time and expose them in a clean, predictable, and serialization-safe way.

Ghost is designed to sit underneath higher-level systems such as:

- NPC behavior systems
- dialogue engines
- faction reputation systems
- shopkeeper / guard logic
- simulation sandboxes
- game AI prototypes
- LLM-driven character layers

This project is intentionally focused on architecture and correctness first.

Surface features, integrations, dialogue, reasoning, and decision-making are expected to be layered on top of the core.

## Installation

```bash
pip install ghocentric-ghost-engine
```

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

## Public Relationship API (v1.1.0)

v1.1.0 adds a direct public API for working with Ghost relationships as a reusable runtime system.

You can now apply emotional events directly, advance time, and inspect relationship state without reaching into internal modules.

```python
from ghost.engine import GhostEngine

ghost = GhostEngine()

ghost.apply_event("player", "shopkeeper", "help")
ghost.apply_event("player", "shopkeeper", "insult")
ghost.apply_event("player", "shopkeeper", "betrayal")

rel = ghost.get_relationship("player", "shopkeeper")

print(rel)
```

Example returned structure:

```python
{
    "trust": -0.703,
    "state": "hostile",
    "transition": ("neutral", "hostile"),
    "trigger": {
        "event": "relationship_broken"
    }
}
```

The public relationship API includes:

```python
ghost.apply_event(a, b, event)
ghost.tick()
ghost.get_relationship(a, b)
```

These methods make Ghost usable as a direct emotional runtime for NPC systems.

## What v1.1.0 Adds

v1.1.0 expands Ghost from a proof-demo emotional model into a reusable public API.

New public behavior includes:

- direct relationship event application
- public relationship inspection
- time-based relationship ticking
- relationship state output
- transition output
- trigger output
- cleaner runtime access for external systems
- reusable API surface for NPC logic

This means external systems can now consume Ghost relationship state directly for things like:

- dialogue changes
- shopkeeper pricing
- guard suspicion
- faction hostility
- reputation recovery
- betrayal consequences
- forgiveness events
- long-term NPC memory

Ghost still does **not** decide what an NPC does.

Ghost exposes state.

Your game, simulation, LLM layer, or behavior system decides how to respond.

## Emotional Inertia System

Ghost includes a deterministic emotional inertia system for modeling NPC relationships over time.

Unlike simple accumulation or smoothing systems, relationships in Ghost:

- remember past interactions
- resist sudden changes
- decay over time
- respond differently depending on history

This enables more realistic behavior under oscillating inputs such as:

```text
insult → help → insult → help
```

Where traditional systems reset or average out, Ghost preserves emotional direction.

## Dual-Channel Relationship Model

Relationships are no longer a single value.

Each relationship tracks:

```text
positive reservoir (pos)
negative reservoir (neg)

trust = pos - neg
```

This allows:

- damage to persist independently of recovery
- recovery to require sustained effort
- asymmetric emotional behavior

A character can receive positive input while still carrying unresolved negative history.

That means a single helpful action after betrayal does not instantly erase the betrayal.

## Emotional Dynamics

Ghost relationships include resistance, saturation, and time-based decay.

### Resistance

High negative history reduces the effectiveness of positive events.

For example, helping an NPC after repeated insults or betrayal may improve the relationship slightly, but it will not instantly restore trust.

### Saturation

Repeated positive interactions produce diminishing returns.

This prevents simple positive-event spam from producing unrealistic instant loyalty.

### Time-Based Decay

Relationships evolve over time using:

```python
ghost.tick()
```

Decay is no longer tied only to events.

This allows long-running simulations to model gradual cooling, recovery, stabilization, or emotional drift over time.

## Personality Presets

Relationships can have different emotional profiles.

```python
ghost.relationships.set_personality("A", "B", "resentful")
```

Available presets:

- balanced
- forgiving
- resentful
- volatile

Each preset modifies:

- gain sensitivity
- decay speed
- recovery behavior

Personality presets allow the same event sequence to produce different emotional outcomes depending on the relationship profile.

## Relationship State System

Ghost exposes human-readable relationship states.

```python
rel = ghost.get_relationship("A", "B")

rel["state"]       # "hostile", "neutral", "friendly"
rel["transition"]  # ("neutral", "hostile")
rel["trigger"]     # {"event": "relationship_broken"}
```

Relationship state gives external systems a clean way to respond to emotional history without needing to interpret raw internal values.

## Event Triggers

State transitions generate structured events.

Examples include:

- `relationship_broken`
- `deescalation`
- `forgiveness`
- `state_shift`

These can be used by external systems for:

- dialogue changes
- combat behavior
- faction reactions
- narrative events
- shopkeeper behavior
- guard escalation
- reputation consequences

Ghost does not perform those actions directly.

It exposes the emotional state and trigger information so another system can decide what to do.

## Oscillation Behavior

Ghost is specifically designed to handle oscillating interaction patterns.

Example:

```python
sequence = ["insult", "insult", "help", "help"]
```

Produces:

- escalation into hostility
- resistance to recovery
- gradual de-escalation, not instant reset

This behavior cannot be replicated by:

- additive systems, such as `trust += delta`
- low-pass filters, such as exponential smoothing

Ghost introduces **stateful emotional inertia**, not just value smoothing.

## Proof Demo

Ghost includes a deterministic proof demo comparing its emotional inertia model against a standard linear baseline.

The proof demo is packaged with the library and can be run after installation.

### Run

As a CLI tool:

```bash
ghost-demo
```

Or as a module:

```bash
python -m ghost.examples.relationship_proof_demo
```

### What This Demonstrates

Two systems receive the exact same sequence of inputs:

```text
help → help → insult → help → help → betrayal → help
```

### Baseline Linear Smoothing

The baseline:

- gradually returns toward neutral
- does not retain strong emotional history
- reacts mostly to recent input

### Ghost Emotional Inertia

Ghost:

- accumulates emotional weight
- resists recovery after damage
- maintains directional state over time
- exposes relationship state and triggers

### Example Output

```text
Step | Event     | Baseline | Ghost   | State
------------------------------------------------
5    | betrayal  | -0.121   | -0.703  | hostile
6    | help      | -0.036   | -0.628  | hostile
```

### Key Observation

Even after positive input such as `help`, Ghost remains in a hostile state due to accumulated negative history, while the baseline system rapidly normalizes.

### What This Proves

- persistent emotional memory
- resistance to reversal
- non-linear recovery behavior
- relationship state transitions
- gameplay-relevant emotional consequences

## Proof Demo Packaging Fix (v1.0.1)

v1.0.1 finalized the proof demo as a fully packaged, runnable experience.

The demo became:

- accessible via CLI with `ghost-demo`
- import-safe with a proper `main()` entry point
- packaged inside the library under `ghost.examples`
- usable without cloning the repository

This ensures that any developer installing Ghost through pip can immediately run and verify the system behavior.

## Relationship Runtime Summary

Ghost relationships provide:

- dual-channel emotional memory
- resistance and saturation modeling
- time-based decay
- per-relationship personality tuning
- state interpretation
- transition tracking
- trigger events
- public relationship inspection
- direct event application

Ghost is no longer just a state engine.

It is a deterministic emotional inertia runtime for NPC systems.

## Core Design Principles

- deterministic, persistent state core
- explicit state transitions via `step()`
- no hidden execution or side effects
- public API remains dict-based and serialization-safe
- internal typed representations may exist but never leak
- designed to be expanded around a stable core

## Ghost Does NOT

Ghost does not:

- choose actions
- generate dialogue
- interpret semantics
- replace an LLM
- act as an autonomous agent
- store memory implicitly
- decide what a character should do

These responsibilities belong to external systems that consume Ghost’s state.

Ghost provides the persistent emotional state those systems can use.

## Stability & Guarantees

Ghost maintains deterministic runtime guarantees across public engine state.

The engine guarantees:

- deterministic runtime behavior, meaning same inputs produce same outputs
- explicit, bounded state mutation per step
- actor state updates across interactions
- actor-level threat accumulation tracking
- pairwise relationship mutation with symmetric consistency
- bounded cascade propagation across interaction networks
- deterministic nonlinear modulation of global system tension
- passive decay behavior during idle cycles
- fully JSON-safe public state and immutable snapshots

These guarantees hold under repeated execution, long-run simulation, and adversarial input streams.

## Architectural Expansion

Recent releases introduced a multi-agent interaction model on top of Ghost’s deterministic state core.

### Agent State Mutation

Agents maintain evolving internal state, such as mood, tension, and last intent, and react deterministically to interaction signals.

### Relationship Graph

Pairwise relationships evolve through explicit interaction deltas, supporting long-term system memory without hidden state.

### Bounded Cascade Propagation

Signals propagate deterministically through local interaction networks with strict bounds to prevent runaway behavior.

### Global System Tension

The engine tracks shared system pressure across interactions using deterministic nonlinear modulation.

### Actor Threat Memory

Agents maintain explicit per-actor threat accumulation history for structured introspection.

### Idle-State Decay Dynamics

Bounded passive decay improves long-run stability and prevents runaway system pressure.

## Testing Philosophy

Ghost uses property-based testing and invariant validation rather than relying solely on example-driven tests.

Core validation includes:

- determinism verification
- bounded-state guarantees
- serialization safety validation
- public state safety checks
- long-run stability checks

This ensures the engine remains correct and predictable as new systems are layered on top.

## Project Structure

```text
ghost/                   core engine modules
ghost/examples/           packaged demos
tests/                   invariant and runtime tests
npc_demo.py               experimental sandbox
pyproject.toml            build configuration
README.md                 project documentation
```

Demos are intentionally minimal and act as experimental sandboxes.

They are not representative of Ghost’s final scope.

## Status

Ghost Engine remains in early development.

As of v1.1.1:

- the deterministic interaction core is stable
- the emotional inertia runtime is available through public API methods

This project is intended as a foundation for experimentation, research, and future system design rather than a finished product.

## Release History

## v1.1.1

- Fixed missing public `GhostEngine.apply_event()` wrapper
- Fixed missing public `GhostEngine.tick()` wrapper
- Fixed missing public `GhostEngine.get_relationship()` wrapper
- Added missing relationship graph support for public event application
- Confirmed public relationship API returns trust, state, transition, and trigger output directly from `GhostEngine`

## v1.1.0

- Added public relationship runtime API
- Added `ghost.apply_event(a, b, event)`
- Added `ghost.tick()`
- Added `ghost.get_relationship(a, b)`
- Exposed relationship trust through public API
- Exposed relationship state through public API
- Exposed relationship transitions through public API
- Exposed structured relationship triggers through public API
- Expanded Ghost from proof-demo behavior into reusable runtime behavior
- Made emotional inertia directly usable by external NPC, dialogue, faction, and simulation systems

## v1.0.1

- Finalized proof demo packaging
- Added `ghost-demo` CLI entry point
- Added proper demo `main()` entry point
- Packaged proof demo inside `ghost.examples`
- Made proof demo runnable without cloning the repository

## v1.0.0

- Promoted Ghost from state engine to emotional inertia runtime
- Introduced dual-channel emotional memory model with positive and negative reservoirs
- Replaced single-value trust updates with persistent emotional accumulation using `pos - neg`
- Added resistance mechanics where negative history reduces the effectiveness of positive events
- Added saturation mechanics with diminishing returns on repeated positive interactions
- Implemented time-based relationship decay via `tick()`
- Added per-relationship parameter system for gain and decay tuning
- Introduced personality presets: balanced, forgiving, resentful, volatile
- Added relationship state classification from hostile to loyal spectrum
- Implemented transition detection between relationship states
- Added structured trigger system with `relationship_broken`, `deescalation`, `forgiveness`, and `state_shift`
- Expanded public API to expose state, transitions, and triggers
- Established emotional inertia model as a first-class runtime system

## v0.2.2

- Fixed public state serialization issue in relationship subsystem
- Replaced set-based storage with JSON-safe structures
- Strengthened invariant coverage across runtime state

## v0.2.1

- Added actor-level threat accumulation tracking
- Introduced deterministic nonlinear system modulation
- Implemented passive idle-cycle decay
- Added immutable JSON-safe snapshots

## v0.2.0

- Introduced multi-agent state mutation
- Added relationship mutation logic
- Implemented bounded cascade propagation
- Achieved deterministic runtime guarantees

## v0.1.x

- Foundational architecture releases
