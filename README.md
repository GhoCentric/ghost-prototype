# Ghost Engine

A deterministic state engine for persistent NPC relationships, social consequences,
epistemic state, scenario resolution, and AI-driven game systems.

> **Core principle:** game code or models may propose events or decisions. Ghost owns
> deterministic state mutation and the record of what became true.

## Start Here

**Live browser demo:** https://ghocentric.github.io/ghost-prototype/

**Active implementation:** [`ghost-engine/ghost/`](ghost-engine/ghost/)

**Direct audit links:**

- [`GhostAPI`](ghost-engine/ghost/api.py) — recommended public integration surface
- [`GhostEngine`](ghost-engine/ghost/engine.py) — lower-level engine implementation
- [`relationships.py`](ghost-engine/ghost/relationships.py) — persistent relationship state
- [`epistemic.py`](ghost-engine/ghost/epistemic.py) — facts, observations, reports, beliefs, evidence, revision
- [`tests/`](ghost-engine/tests/) — test suite
- [`QUALITY.md`](ghost-engine/QUALITY.md) — validation commands and quality lanes
- [`COVERAGE.md`](ghost-engine/COVERAGE.md) — coverage reports
- [PyPI v1.9.1](https://pypi.org/project/ghocentric-ghost-engine/1.9.1/)
- [Immutable v1.9.1 source](https://github.com/GhoCentric/ghost-prototype/tree/v1.9.1/ghost-engine/ghost)

The repository also contains older prototype material from earlier development stages.
**`ghost-engine/` is the actively maintained public package.** If you are reviewing
Ghost's current core, begin there.

## Current Release

```text
Package:              ghocentric-ghost-engine
Version:              1.9.1
Python:               3.9+
Runtime dependencies: none
Release validation:   1,680 passed, 1 skipped
```

Install:

```bash
pip install ghocentric-ghost-engine
```

The full package documentation lives at [`ghost-engine/README.md`](ghost-engine/README.md).

## What Ghost Does

Ghost provides deterministic systems for persistent state underneath a host game,
simulation, dialogue layer, or optional LLM. Current public areas include:

- relationship state and emotional inertia;
- maturity, volatility, pressure, transitions, and diagnostics;
- weighted social propagation and bounded world effects;
- temperament interpretation;
- threat-response policy;
- objective facts, observations, reports, beliefs, evidence, provenance, and explicit belief revision;
- validated scenario configuration and atomic scenario resolution;
- fight-level objective, initiative, and recovery-read control packets;
- JSON-safe snapshots, strict restoration, and legacy snapshot migration;
- public packet validation and copy isolation;
- optional LLM prompt/response adapters above the deterministic state layer.

Ghost does **not** own graphics, animation, physics, pathfinding, audio, a host game's
custom inventory/quest/economy implementation, or unrestricted autonomous NPC control.

## Authority Boundary

```text
game event / observation / evidence
                ↓
Ghost validates and updates authoritative state
                ↓
Ghost returns copied state / diagnostics / bounded policy packets
                ↓
host game or application presents and executes the result
```

Ghost is the state layer. The host system owns presentation and engine-specific action
execution.

## Determinism, Not Random Output

Ghost's state-transition path is deterministic: the same starting state plus the same
ordered inputs produces the same resulting state.

The live browser demo includes a **Run Same Input Twice** check. It creates two fresh
`GhostAPI` instances, applies the identical event sequence independently, canonicalizes
the returned state as JSON, compares the two outputs directly, and displays SHA-256
hashes for both runs.

The trust values shown in the relationship demo are state values derived from accumulated
history and transition rules. They are not random draws, and relationship trust is not
presented as a universal 0–1 output scale.

## Browser Demo

The public demo at https://ghocentric.github.io/ghost-prototype/ loads Pyodide in the
browser, installs the released `ghocentric-ghost-engine==1.9.1` wheel from PyPI, and uses
Ghost's returned packets to drive the visual presentation.

The browser demo makes **0 LLM calls at runtime**.

That statement describes the demo's execution path. It does **not** mean an LLM was not
used during development.

The demo currently shows:

1. **Same event, different history** — identical betrayal input resolves differently after different accumulated relationship histories.
2. **Social propagation** — one direct event produces differently weighted secondary effects for observers.
3. **Epistemic revision** — objective fact, spoken report, evidence, and actor belief remain separate; later evidence revises belief without rewriting the fact.
4. **Deterministic replay** — two independent runs of the same setup and ordered inputs are compared directly.

## Minimal API Example

```python
from ghost import GhostAPI

ghost = GhostAPI()

ghost.apply_event(
    "player",
    "shopkeeper",
    {
        "type": "help",
        "intensity": 1.0,
    },
)

ghost.apply_event(
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

print(relationship["trust"])
print(relationship["state"])
print(relationship["diagnostics"])
```

The important part is not the printed number by itself. The next event is evaluated
against the state that already exists.

## Epistemic Boundary

Ghost separates:

```text
objective fact
    ≠ observation
    ≠ spoken report
    ≠ belief
```

A report does not automatically become truth, and receiving a report does not silently
force an actor to believe it. Beliefs are explicitly evaluated, actor-owned,
provenance-aware, and linked across revisions.

## Optional LLM Layer

Ghost does not require an LLM.

Where an LLM is used by a host application or reference demo, the intended boundary is:

```text
LLM proposes
Ghost validates or resolves deterministic state
host application presents the result
```

The deterministic core does not make hidden network calls.

## Development Disclosure

Ghost's implementation workflow is AI-assisted. Architecture, product direction, state
contracts, testing decisions, and acceptance criteria are human-directed.

The phrase **"0 LLM calls at runtime"** on the browser demo refers specifically to that
demo's execution. The development workflow and runtime architecture are separate claims.

## Reference Applications

`ghost-engine/ghost/examples/ghost_revolution/` is a playable reference implementation
used to exercise Ghost under a larger persistent game loop.

`ghost-engine/ghost/examples/order_coordination.py` is a separate application-layer proof
for authoritative state, ambiguity, evidence, correction, confirmation, and rollback.

Those applications demonstrate Ghost. Their game/order concepts are not universal Ghost
core concepts.

## License

MIT. See [`LICENSE`](LICENSE).
