# ghocentric-ghost-engine

A deterministic state engine for persistent NPC relationships, social consequences,
epistemic state, scenario resolution, and AI-driven game systems.

Ghost is not a language model, a renderer, or a replacement for a game engine.

Ghost provides the authoritative state layer underneath higher-level systems. It
tracks what happened, validates what may change, preserves the result, and returns
JSON-safe packets that a game, simulation, dialogue layer, or optional LLM can use.

> **Core principle:** models and game code may propose events or decisions. Ghost
> owns deterministic state mutation and the record of what became true.

## Current Release

```text
Package:    ghocentric-ghost-engine
Version:    1.8.0
Python:     3.9+
Runtime dependencies: none
Validation: 1,296 passed, 1 skipped
```

The actively maintained package is this `ghost-engine/` directory.

## Installation

```bash
pip install ghocentric-ghost-engine
```

## Quick Start

`GhostAPI` is the recommended integration surface.

```python
from ghost import GhostAPI

ghost = GhostAPI()

packet = ghost.apply_event(
    "player",
    "shopkeeper",
    {
        "type": "betrayal",
        "intensity": 1.0,
    },
)

relationship = ghost.get_relationship(
    "player",
    "shopkeeper",
)

print(packet["relationship"]["state"])
print(relationship["trust"])
```

Use `GhostEngine` directly for lower-level engine access, focused tests, or
specialized integrations.

## What Ghost Owns

Ghost currently provides deterministic systems for:

- relationship state and emotional inertia;
- maturity, volatility, pressure, transitions, and diagnostics;
- social propagation and bounded world effects;
- temperament interpretation;
- threat-response policy;
- objective facts, observations, reports, beliefs, evidence, provenance, and
  explicit belief revision;
- validated scenario configuration and atomic scenario resolution;
- fight-level objective packets, initiative state, and recovery-read control;
- JSON-safe snapshots, strict restoration, and legacy snapshot migration;
- public packet validation and copy isolation;
- optional LLM prompt and response adapters.

Ghost does **not** own:

- graphics, animation, physics, pathfinding, input, or audio;
- a game's custom inventory, quest, combat, or economy implementation;
- unrestricted autonomous NPC control;
- arbitrary natural-language truth;
- hidden network calls from the deterministic core.

## The Authority Boundary

A normal integration follows this shape:

```text
game event or observation
        ↓
Ghost validates and updates authoritative state
        ↓
Ghost returns copied state, diagnostics, or a bounded policy packet
        ↓
the host game applies that result to its own mechanics and presentation
```

In v1.8.0, Ghost can return selected or locked decisions inside specific bounded
systems, such as threat-response labels and combat-control packets. It does not
automatically discover an arbitrary game's NPC abilities or execute engine-specific
functions.

A generic registered-agent capability runtime is a future layer, not a current
public guarantee.

## Relationship State

Ghost relationships use separate positive and negative reservoirs:

```text
trust = positive reservoir - negative reservoir
```

This preserves emotional history. A later helpful action does not automatically
erase betrayal, repeated abuse, or accumulated hostility.

```python
from ghost import GhostAPI

ghost = GhostAPI()

ghost.apply_event(
    "player",
    "merchant",
    {
        "type": "help",
        "intensity": 1.0,
    },
)

ghost.apply_event(
    "player",
    "merchant",
    {
        "type": "betrayal",
        "intensity": 1.0,
    },
)

relationship = ghost.get_relationship(
    "player",
    "merchant",
)

print(relationship["state"])
print(relationship["diagnostics"])
```

Public relationship packets can expose:

- trust;
- friendly, neutral, or hostile state;
- transition and trigger data;
- pressure and near-break state;
- maturity and volatility;
- positive and negative volatility;
- measurable change diagnostics.

Relationship personalities include:

```text
balanced
forgiving
resentful
volatile
```

## Social Propagation

A direct event can produce deterministic secondary effects for observers.

```python
packet = ghost.propagate_social_event(
    source="player",
    target="shopkeeper",
    event="betrayal",
    observers=[
        "guard",
        "elder",
        "rival",
    ],
    weights={
        "guard": 1.0,
        "elder": 0.7,
        "rival": 0.25,
    },
)
```

Propagation packets can contain:

- the direct relationship result;
- bounded observer trust changes;
- social heat;
- pressure labels;
- fear, resentment, order, and guard-suspicion deltas;
- copied relationship and world-state data.

## Epistemic State

Ghost separates objective runtime truth from what actors observe, report, believe,
and later revise.

```text
objective fact
    ≠ observation
    ≠ spoken report
    ≠ belief
```

A report does not become truth, and receiving a report does not silently force a
belief.

```python
from ghost import GhostAPI

ghost = GhostAPI()

ghost.record_fact(
    fact_id="millcross_food_001",
    source="game_rule",
    subject="royal_guard",
    predicate="confiscated",
    object="millcross_food",
    attributes={
        "quantity": 6,
    },
)

report = ghost.report(
    speaker="villager_3",
    audience="player",
    claim={
        "statement": "They took everything.",
    },
    confidence=0.82,
)

assert ghost.get_belief(
    "player",
    "millcross_food_loss",
) is None
```

Public epistemic operations include:

```text
record_fact
get_fact
observe
report
add_evidence
evaluate_beliefs
get_belief
propagate_belief
```

Beliefs are actor-owned, provenance-aware, explicitly evaluated, and linked across
revisions. Epistemic state is included in snapshots and deterministic restoration.

Run the public smoke demo:

```bash
python -m ghost.examples.epistemic_api_smoke_demo
```

## Threat-Response Policy

Ghost can evaluate a bounded set of deterministic response labels from persistent
relationship state, temperament, and explicit caller-owned context.

```python
packet = ghost.evaluate_npc_threat_response(
    npc="merchant",
    source="player",
    target="merchant",
    temperament="anxious",
    context={
        "player_armed": True,
        "player_aiming": True,
        "escape_route": True,
    },
)

print(packet["selected_response"])
```

Current labels are:

```text
fight
call_guards
confront
surrender
flee
freeze
warn
ignore
```

The policy is read-only. It returns a recommendation packet; it does not animate or
execute the response.

## Combat Control

The public core includes small deterministic combat-control contracts:

```text
build_combat_objective
advance_combat_initiative
lock_combat_recovery_read
resolve_combat_recovery
```

These packets validate objective pressure, initiative transitions, hidden recovery
reads, and deterministic resolution without randomness.

They are not a universal combat system. Ghost Revolution uses them as part of a
larger game-specific reference implementation.

## Scenario Runtime

`ScenarioRuntime` wraps `GhostAPI` with validated JSON-safe scenario configuration
and atomic action resolution.

A rejected action restores the prior checkpoint instead of leaving partial state
behind. This provides a tested boundary for game-specific facades without moving
their presentation logic into Ghost core.

## Snapshots and Restoration

Use `snapshot()` for saves and external boundaries.

```python
snapshot = ghost.snapshot()

restored = GhostAPI.from_snapshot(
    snapshot
)

assert restored.snapshot() == snapshot
```

Snapshots include separate package and schema metadata:

```text
ghost_version
schema_version
```

Package release numbers and snapshot schema versions are intentionally independent.
The current runtime validates complete snapshot structure, rejects unsupported
schemas, migrates supported legacy metadata, and restores copied state.

`state()` is a live mutable view intended for controlled inspection. Do not use it
as a save-file or external adapter contract.

## Optional LLM Layer

Ghost does not require an LLM.

The package includes optional helpers and the Ghost Revolution reference demo,
where an LLM can propose constrained strategy or narration while deterministic game
state remains authoritative.

The reference rule is:

```text
LLM proposes
Ghost validates or resolves
the host game presents the result
```

API keys are caller-owned and read from environment configuration. They are not
embedded in the package.

## Ghost Revolution Reference Demo

`ghost.examples.ghost_revolution` is a terminal reference implementation used to
exercise Ghost under a larger persistent game loop.

It demonstrates:

- towns that retain player-history consequences;
- relationships, social pressure, and epistemic belief state;
- guarded-town reports, evidence, investigation, and belief revision;
- raid preparation, recruitment, heat, and kingdom pressure;
- deterministic snapshots and branch restoration;
- a king and Champion fight with LLM strategy proposals;
- separate opponent prediction and physical combat action;
- symmetric heavy, light, feint, bait, parry, deflect, and dodge options;
- Ghost-authoritative combat resolution and audit packets;
- LLM narration conditioned on accumulated game state.

Ghost Revolution is an example and test laboratory. Its towns, king, menus, combat
damage, and presentation are not universal Ghost-core concepts.

Local Android launchers included in the repository are:

```bash
./run-llm-ai-dev.sh
./run-llm-ai-cinematic.sh
```

They expect a local `.env.local` containing `OPENAI_API_KEY`. Do not commit that
file.

## Packaged CLI Demos

The installed package exposes:

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

Each demo exercises a different public layer without requiring a cloned repository.

## Controlled Benchmark

`BENCHMARK_RESULTS.md` records a deterministic 42-trial Ghost Revolution benchmark
that compares a naive “reports are truth” policy with Ghost's provenance-aware
policy under equal two-action budgets.

The benchmark is deliberately narrow. It demonstrates that separating reports,
evidence, and belief revision changes actual game decisions and their heat/fear
consequences. It is not a claim of general intelligence or a general-purpose truth
detector.

Reproduce it with:

```bash
python -m ghost.examples.ghost_revolution.benchmarks.epistemic_scenario_matrix_benchmark
```

## Quality Lanes

See `QUALITY.md` for exact commands.

```bash
pytest -q
pytest -q -m performance
```

Coverage is separated into core and Ghost Revolution runtime lanes so terminal
presentation and local performance tests do not distort each other.

Current synchronized repository validation:

```text
1,296 passed
1 skipped
146 Python test files
```

## Project Layout

```text
ghost/
    api.py
    engine.py
    relationships.py
    epistemic.py
    threat_response.py
    combat.py
    objectives.py
    scenario.py
    scenario_runtime.py
    examples/

tests/
    ghost_revolution/
    integration/
    performance/
    property/
    regression/

BENCHMARK_RESULTS.md
QUALITY.md
coverage.core.ini
coverage.revolution.ini
pyproject.toml
```

## Design Guarantees

Ghost is built around:

- deterministic runtime behavior;
- explicit mutation;
- bounded numerical state;
- validated public inputs;
- copied public outputs;
- JSON-safe packet contracts;
- atomic compound operations;
- strict snapshot restoration;
- package-version and schema-version separation;
- no silent conversion of reports into truth;
- no arbitrary LLM mutation of authoritative state.

## Current Limits

Ghost v1.8.0 is still an alpha package.

Current limitations include:

- Python is the authoritative implementation;
- Unreal and Godot adapters do not exist yet;
- generic agent registration and capability binding are not public yet;
- host games still own engine-specific execution;
- Ghost Revolution is a terminal reference demo rather than a finished commercial
  game;
- benchmark scenarios are controlled and intentionally narrow.

## Roadmap Direction

The next architectural goal is an engine-neutral agent action runtime:

```text
register agent and capabilities
submit observation
select one legal action
report execution result
update persistent state
```

Only after that contract is stable should Unreal and Godot adapters expose thin
engine-facing components around the same Ghost authority.

## Development Note

Ghost was designed by Shane Heckathorn and built through an AI-assisted,
Android-first development workflow using extensive deterministic tests, audits,
backups, and reproducible terminal patches.

The implementation workflow is AI-assisted. The architecture, product direction,
state contracts, testing decisions, and acceptance criteria are human-directed.

## License

MIT. See the repository license.
