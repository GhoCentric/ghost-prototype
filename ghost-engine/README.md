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

## Demo Commands

After installation, Ghost includes three runnable demo commands:

```bash
ghost-demo
ghost-npc-demo
ghost-shopkeeper-demo
```

Each demo proves a different layer of the engine:

- `ghost-demo` compares Ghost emotional inertia against a linear baseline
- `ghost-npc-demo` shows Ghost API state being mapped into external NPC behavior
- `ghost-shopkeeper-demo` launches a playable terminal shopkeeper demo

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

 
## Packaged Demos

Ghost includes three small demos that each prove a different layer of the engine.

### Proof Demo

The proof demo compares Ghost’s emotional inertia model against a standard linear baseline.

Run:

```bash
ghost-demo
```

Or as a module:

```bash
python -m ghost.examples.relationship_proof_demo
```

This demonstrates that Ghost retains emotional history after betrayal while a simple baseline rapidly normalizes.

Example output:

```text
Step | Event     | Baseline  | Ghost     | State
----------------------------------------------------------------------
5    | betrayal  | -0.209    | -0.750    | hostile
6    | help      | -0.107    | -0.680    | hostile
```

Key result:

```text
Ghost retained stronger negative state.
Baseline normalized more quickly.
✔ Emotional inertia confirmed.
```

### NPC API Mapping Demo

The NPC demo shows how a small external behavior layer can consume Ghost state over a deterministic 10-tick sequence.

Run:

```bash
ghost-npc-demo
```

Or as a module:

```bash
python -m ghost.examples.simple_npc_demo
```

This demo uses:

```python
engine.step(...)
engine.apply_event(a, b, event)
engine.tick()
engine.get_relationship(a, b)
```

It demonstrates threat state and relationship state working together.

Example output:

```text
Tick | Threat | Trust  | Rel      | Trig    | NPC
---------------------------------------------------
0    |   0.00 |  0.054 | neutral  | -       | idle
1    |   0.00 |  0.204 | friendly | forgive | help
5    |   1.00 | -0.768 | hostile  | broken  | refuse
9    |   0.93 | -0.510 | neutral  | deesc   | warn
```

The NPC behavior is not chosen by Ghost directly.

Ghost exposes state. The NPC code decides how to respond.

### Playable Shopkeeper Mini Game

The shopkeeper demo is a playable terminal mini game.

Run:

```bash
ghost-shopkeeper-demo
```

Or as a module:

```bash
python -m ghost.examples.shopkeeper_mini_game
```

The shopkeeper demo uses only the public `GhostEngine` API and shows how trust, emotional pressure, relationship state, prices, quest availability, and dialogue can change based on player actions.

Example status output:

```text
Trust:      -0.401
State:      neutral
Pressure:   damaged, but not broken
Price:      1.50x
Quest:      unavailable
```

Then after further damage:

```text
Trust:      -0.570
State:      hostile
Pressure:   broken
Price:      2.00x
Quest:      unavailable
Trigger:    relationship_broken
```

The mini game demonstrates that behavior can begin changing before a relationship fully breaks.

Ghost exposes the emotional state. The game logic decides how to respond.

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
pyproject.toml            build configuration
README.md                 project documentation
```

Demos are intentionally minimal and act as experimental sandboxes.

They are not representative of Ghost’s final scope.

## Status

Ghost Engine remains in early development.

As of v1.2.1:

- the deterministic interaction core is stable
- the emotional inertia runtime is available through public API methods
- the proof demo is packaged and runnable
- the NPC API mapping demo is packaged and runnable
- the playable shopkeeper mini game is packaged and runnable

This project is intended as a foundation for experimentation, research, and future system design rather than a finished product.

## Release History

## v1.2.1

- Cleaned packaged demo command structure
- Removed redundant `ghost-relationship-demo` command from the public demo set
- Restored `ghost-demo` as the relationship proof / baseline comparison demo
- Updated `ghost-npc-demo` into a deterministic 10-tick Ghost API mapping demo
- Improved NPC demo terminal formatting for phone-safe output
- Shortened NPC behavior labels and dialogue to reduce terminal wrapping
- Removed unused proof demo variable cleanup
- Clarified the final public demo suite:
  - `ghost-demo`
  - `ghost-npc-demo`
  - `ghost-shopkeeper-demo`

## v1.2.0

- Added playable terminal shopkeeper mini game
- Added `ghost-shopkeeper-demo` CLI entry point
- Added `ghost-relationship-demo` CLI entry point
- Updated public relationship demo sequence for stronger emotional inertia behavior
- Demonstrated trust, emotional pressure, relationship state, pricing, quest availability, and dialogue changes through public API usage
- Added resentful NPC personality setup to the shopkeeper demo
- Added wait/tick explanation to demonstrate time-based relationship decay
- Added emotional pressure display such as `damaged, but not broken` and `broken`
- Improved command input support for typed commands such as `buy bread`, `show status`, and `wait`

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
