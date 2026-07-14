# Ghost Engine Documentation

This directory documents the current public architecture of
`ghocentric-ghost-engine` version 1.8.0.

Ghost is a deterministic Python state engine for persistent
interactive systems. It is designed to sit underneath game logic,
NPC behavior, reputation systems, social simulations, policy
systems, and optional language-model interfaces.

Ghost owns structured state and deterministic state transitions.
External applications decide how those packets become animation,
dialogue, UI, quests, combat presentation, or other side effects.

## Documentation Index

- [`architecture.md`](architecture.md)
  explains the current engine layers, authority boundaries,
  snapshots, deterministic resolution, and optional LLM integration.

- [`state_model.md`](state_model.md)
  describes relationship state, social propagation, temperament,
  threat evaluation, epistemic records, world state, and diagnostics.

- [`example_flow.md`](example_flow.md)
  walks through a public-API interaction from direct relationship
  change to social consequences and external game behavior.

## Installation

```bash
pip install ghocentric-ghost-engine
```

## Installed Demo Commands

The package currently installs eight terminal demos:

```text
ghost-demo
ghost-npc-demo
ghost-shopkeeper-demo
ghost-math-demo
ghost-diagnostics-demo
ghost-social-demo
ghost-temperament-demo
ghost-threat-response-demo
```

These demos cover different parts of the public engine:

- relationship persistence and emotional inertia
- external NPC behavior mapping
- a playable shopkeeper loop
- relationship math
- diagnostic packets
- social propagation and world effects
- temperament interpretation
- threat-response evaluation

Ghost Revolution is a larger development example built on top of
the engine. It demonstrates persistent town memory, social
consequences, epistemic state, deterministic combat resolution,
and optional LLM narration.

## Public Surfaces

The current package exposes two primary integration surfaces.

`GhostEngine` provides the focused relationship runtime:

```python
from ghost.engine import GhostEngine

ghost = GhostEngine()

ghost.apply_event(
    "player",
    "shopkeeper",
    "help",
)

relationship = ghost.get_relationship(
    "player",
    "shopkeeper",
)
```

`GhostAPI` provides the wider integrated facade:

```python
from ghost.api import GhostAPI

ghost = GhostAPI()

ghost.apply_event(
    "player",
    "shopkeeper",
    "betrayal",
)

snapshot = ghost.snapshot()
```

The wider facade includes relationship, social, epistemic,
governance, world-state, commerce, law, reintegration,
temperament, threat-response, and adapter-related methods.

## Authority Boundary

Ghost may deterministically resolve:

- state transitions
- relationship changes
- diagnostics
- observer propagation
- social heat
- world-effect deltas
- belief evaluation and revision
- structured policy results
- legal move validation in integrated examples

Ghost does not directly perform external side effects such as:

- rendering animation
- displaying dialogue
- moving a game character
- charging a real payment
- modifying an external database without application code
- granting an LLM authority over engine state

The application consumes Ghost packets and decides how to represent
or apply them.

## Source of Truth

The package implementation, public tests, `pyproject.toml`, and the
root `README.md` are the source of truth for released behavior.

These documents explain the architecture without replacing the API
contract or promising behavior that is not present in the package.
