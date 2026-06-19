# Ghost Engine

A deterministic state engine for persistent NPC relationships, emotional inertia, social propagation, temperament-aware interpretation, and game-simulation behavior.

Ghost is not a language model.
Ghost is not an autonomous agent.
Ghost is not a chatbot framework.

Ghost is a small, test-backed Python engine that tracks how interaction history changes relationship state over time.

The core idea is simple:

NPC behavior should not reset just because the next line of dialogue starts.

Ghost gives higher-level systems a stable state layer underneath dialogue, quests, factions, reputation, trust, suspicion, hostility, forgiveness, betrayal, and social memory.

## Current Status

Ghost is now a public Python package.

Install:

    pip install ghocentric-ghost-engine

Current public release:

    ghocentric-ghost-engine==1.7.0

Runnable demos:

    ghost-demo
    ghost-npc-demo
    ghost-math-demo
    ghost-diagnostics-demo
    ghost-social-demo
    ghost-temperament-demo
    ghost-shopkeeper-demo

Current validation:

    248 passed

Ghost has been packaged, uploaded to PyPI, installed from PyPI, and verified through public CLI execution.

The active package implementation lives in:

    ghost-engine/

## Thesis

Ghost is a deterministic internal-state runtime for interactive systems.

Its purpose is to preserve consequence.

Most dialogue systems, NPC demos, and AI character layers can generate text, but they often lack a durable state core that cleanly tracks how prior events should affect future behavior.

Ghost separates state from expression.

The engine does not try to be intelligent by itself. Instead, it maintains structured relationship state that other systems can read, interpret, serialize, test, and act on.

A language model can sit above Ghost as a dialogue surface.
A game loop can sit above Ghost as a behavior controller.
A simulation can sit above Ghost as a world layer.
A game engine can sit above Ghost as the rendering and action layer.

But the state transition itself remains deterministic, inspectable, testable, and serialization-safe.

In short:

    Ghost does not decide what the character says.
    Ghost remembers why the character should feel different now.

## What Ghost Is

Ghost is a state engine for consequence.

It tracks relationship and social state across repeated events, then exposes that state through public packets that other systems can use.

Ghost currently supports:

- relationship state
- trust and hostility dynamics
- emotional inertia
- relationship transitions
- forgiveness signals
- betrayal and relationship break signals
- maturity and volatility behavior
- temperament-aware interpretation
- social propagation signals
- governance and policy helpers
- world and society runtime helpers
- JSON-safe snapshots
- public diagnostics packets
- typed public constants while keeping string compatibility

## What Ghost Is Not

Ghost is intentionally limited.

It is not:

- a large language model
- a neural network
- an autonomous agent
- a general intelligence system
- a replacement for game AI
- a replacement for dialogue writers
- a black-box decision maker

Ghost does not choose actions.
Ghost does not generate dialogue.
Ghost does not invent world state.

Ghost exposes deterministic social, emotional, diagnostic, and interpretive state.

Those limits are part of the architecture.

## Public API

The main public wrapper is:

    GhostAPI

The lower-level engine is:

    GhostEngine

General guidance:

    Use GhostAPI for normal external integrations.
    Use GhostEngine for lower-level engine-style access and tests.

Example:

    from ghost import GhostAPI

    api = GhostAPI()

    packet = api.apply_event(
        "player",
        "shopkeeper",
        {
            "type": "betrayal",
            "intensity": 1.0,
        },
    )

    relationship = api.get_relationship("player", "shopkeeper")

    print(packet)
    print(relationship)

## Typed Constants and String Compatibility

Ghost supports raw string inputs for simple JSON-friendly usage.

Example:

    api.apply_event(
        "player",
        "shopkeeper",
        {
            "type": "betrayal",
            "intensity": 1.0,
        },
    )

Ghost also includes typed public constants in:

    ghost/events.py

Current typed constant groups include:

- APIEvent
- RelationshipEvent
- TemperamentPreset
- PressureLabel
- RelationshipState

These are optional.

Raw strings remain supported for demos, JSON input, configs, and scripts.

The goal is to reduce stringly-typed mistakes without breaking the simple public API.

## Tick Behavior

GhostAPI.tick() advances relationship and world time.

It returns a public packet containing relationship tick data and world state.

This matters because external systems should not have to inspect private internals just to see what changed after a tick.

## State and Snapshot Safety

Ghost exposes both live state and safe snapshots.

    state()

returns the live mutable engine state.

That is useful for controlled debugging and internal inspection, but it should be treated as unsafe for long-term saves or external adapter contracts.

    snapshot()

returns a JSON-safe copied snapshot.

Snapshots include metadata fields such as:

    ghost_version
    schema_version

Use snapshot output for save/load, adapter work, serialization, and external boundaries.

## ID Validation

Ghost validates public relationship IDs.

IDs are normalized before being used internally.

The current ID rules reject:

- None
- empty IDs
- whitespace-only IDs
- IDs containing the internal relationship delimiter

This protects relationship keys from malformed public input.

## Temperament Interpretation

Ghost includes a read-only temperament interpretation layer.

Temperament interpretation does not mutate relationship state.
It does not choose actions.
It does not generate dialogue.

It reads existing relationship or social packets and returns deterministic metadata for how an NPC temperament might interpret that state.

Current temperament presets include:

- calm
- anxious
- confident
- suspicious
- resentful
- loyal
- volatile

This is useful for dialogue layers, game behavior layers, and NPC presentation systems.

## Social Propagation

Ghost includes social propagation behavior and tests.

The purpose is to model how relationship events can affect observers, groups, or nearby social context without requiring an LLM to invent consequences.

Social propagation is still an active development area, but it is already part of the system direction.

## Governance, Policies, and World Runtime

Ghost includes helper systems for structured simulation logic, including:

- claim assessment
- intent assessment
- effect assessment
- stance packets
- commerce policy
- pricing policy
- law policy
- reintegration policy
- world and society runtime state
- optional LLM adapter helpers

These systems support the broader goal of making NPC and world behavior more structured, inspectable, and consequence-aware.

## Why This Exists

Ghost exists because prompt-only character behavior is fragile.

Prompting can describe a character as angry, loyal, forgiving, suspicious, or hurt, but that does not automatically create a stable state system.

Ghost focuses on the layer underneath expression:

    event happens
    state changes
    state persists
    future behavior can read that state

This allows NPCs, factions, shops, guards, and social systems to react to accumulated history instead of isolated prompts.

## Proof Points

Ghost has crossed several practical proof boundaries:

- pip install works
- CLI demos run
- public API works
- wheel and sdist build
- PyPI upload succeeded
- public install from PyPI succeeded
- relationship transitions are deterministic
- tick returns public packet data
- state and snapshot boundaries exist
- typed constants exist while strings remain supported
- ID validation exists
- temperament interpretation works
- social propagation tests exist
- public packet schema tests exist
- scale and stress tests exist

Recent local validation:

    248 passed

Recent public install verification:

    pip install ghocentric-ghost-engine
    ghost-demo

## Example Demo Output

The default demo compares Ghost against a simple linear baseline.

The baseline smooths back toward neutral.

Ghost retains emotional inertia after betrayal.

Example result:

    Baseline: Gradually smooths back toward neutral.
    Ghost: Retains emotional memory after betrayal.
    Result: Persistent emotional inertia.

This is the core behavior Ghost is designed to demonstrate.

## Scale and Stress Testing

Ghost is still early, but it is no longer only conceptual.

Local stress tests have shown public API endurance, NPC-to-NPC interaction handling, temperament interpretation under load, and relationship-pair growth.

Example standalone benchmark result on Android hardware:

    Agents: 1,000
    Ticks: 1,000
    Events processed: 20,000
    Unique relationship pairs: 20,000
    Interpretation calls: 20,000
    Memory peak: 39.51 MB
    Result: passed

This does not mean Ghost is production-scale MMO infrastructure.

It does mean Ghost can survive repeated state mutation, relationship growth, interpretation calls, and tick processing without immediately collapsing.

The next major scaling target is tick optimization for large relationship sets.

## Architecture

Ghost is built around deterministic state transitions.

At a high level:

    input event
    validation
    relationship state mutation
    transition detection
    diagnostics packet
    optional interpretation layer
    external system response

The engine is designed to keep the core separate from surface expression.

This makes it easier to test, inspect, serialize, and integrate.

## Current Package Area

The actively maintained package lives in:

    ghost-engine/

Important package modules include:

    ghost/api.py
    ghost/engine.py
    ghost/relationships.py
    ghost/events.py
    ghost/temperament.py
    ghost/governance.py
    ghost/policies.py
    ghost/world.py
    ghost/step.py
    ghost/ids.py
    ghost/examples/
    tests/

The repository also contains older prototype material from earlier development stages.

The current public package should be treated as the main active implementation.

## Use Cases

Ghost is intended for systems such as:

- NPC relationship engines
- dialogue systems
- faction reputation systems
- shopkeeper behavior
- guard suspicion systems
- social simulation prototypes
- game AI middleware
- LLM-driven character layers
- simulation sandboxes
- Unity gameplay prototypes
- Unreal Engine gameplay prototypes
- Godot gameplay prototypes

Ghost does not replace those systems.

It gives them persistent relationship state to build on.

## Game Engine Direction

Ghost is designed to become useful as a lightweight state middleware layer for game engines.

Long-term adapter targets include:

- Unity-facing adapter layer
- Unreal Engine-facing adapter layer
- Godot-facing adapter layer
- JSON-first packet contracts
- adapter-style error packets
- stable schema/version metadata
- external save/load boundaries
- dialogue-layer metadata
- NPC and faction consequence packets

The goal is not to make Ghost a full engine.

The goal is to make Ghost easy for external engines to ask:

    What changed?
    Why did it change?
    What state should my NPC, faction, shop, or guard system react to?

## Development Notes

Ghost was built under unusual constraints:

- Android-first workflow
- mobile terminal development
- pure Python core
- no machine learning dependency
- incremental architecture over time

That Android-first workflow is not part of the engine API.

It is part of the proof story.

Ghost was built, tested, packaged, uploaded to PyPI, installed from PyPI, and CLI-verified through a mobile workflow.

The project is intentionally focused on architecture, correctness, and demonstrable behavior before polish.

## Roadmap Direction

Current public release:

    v1.7.0

Near-term cleanup:

- clarify GhostEngine vs GhostAPI responsibilities
- keep typed constants/enums while preserving string compatibility
- continue strengthening schema tests for public packets
- document state() as live and unsafe for external persistence
- document snapshot() as safe for serialization
- continue validating GhostAPI.tick() packet behavior
- continue relationship count, tick, propagation, and temperament scale tests
- add adapter-style error packets before v2.0

Next feature direction:

    v1.7.1 - API cleanup and documentation
    v1.8.0 - Social consequence game loop
    v1.9.0 - Expression metadata output
    v2.0.0 - Unity, Unreal Engine, and Godot-facing adapter layer

Long-term direction:

- Ghost as lightweight NPC state middleware
- Ghost as a consequence layer under dialogue systems
- Ghost as a persistent social-state runtime for interactive worlds
- Ghost as a JSON-safe state core for external game-engine adapters

## Install

Install the package:

    pip install ghocentric-ghost-engine

Run the main demo:

    ghost-demo

Run the shopkeeper mini-game:

    ghost-shopkeeper-demo

Run the temperament demo:

    ghost-temperament-demo

Run the social propagation demo:

    ghost-social-demo

## Core Principle

Ghost does not choose actions.

Ghost does not generate dialogue.

Ghost does not invent world state.

Ghost exposes deterministic social, emotional, diagnostic, and interpretive state.

## License

See the repository license file.

## Closing

Ghost is built around a simple claim:

Consistent behavior comes from persistent state, not from better prompt wording alone.

Ghost does not pretend to be conscious.
Ghost does not pretend to be autonomous.
Ghost does not pretend to be a complete game AI.

It is a deterministic state engine for consequence, memory, and relationship change.

Those limits are the architecture.
