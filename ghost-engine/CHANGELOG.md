# Changelog

All notable changes to `ghocentric-ghost-engine` are documented here.

Package release numbers and snapshot schema versions are separate. A package update
does not automatically require a save-schema change.

## v1.10.0
### NPC-specific interpretation + persistent attention / flow
- Added persistent deterministic NPC-specific action interpretation so the same
  objective action can carry different configured meaning for different agents.
- Added per-agent interpretation rules, sensitivities, baselines, activation /
  release thresholds, history, provenance, and snapshot restoration.
- Added persistent deterministic attention / flow with configurable pressure,
  foreground compression, hysteresis, and strong-signal breakthrough.
- Added a read-only persistent salience bridge over emotional and interpretation
  state. Attention receives copied salience and cannot rewrite either source.
- Added `persistent_salience(...)` and `advance_attention_from_state(...)` to the
  public GhostAPI integration surface.
- Hardened failed-step atomicity, copy isolation, 128-agent isolation, long-run
  combined stress, snapshot forks, and deterministic replay across the v1.10
  cognitive layers.
- Kept Ghost's authority boundary unchanged: the host supplies objective actions
  and observable features; Ghost does not invent facts, generate dialogue, or
  choose the final NPC action.
- Package producer version advances to `1.10.0`.
- Top-level snapshot schema remains `1.0`.
- Emotion snapshot sub-schema remains `1.1`.
- Interpretation snapshot sub-schema is `1.0`.
- Attention snapshot sub-schema is `1.0`.
- Runtime dependencies remain zero.
- Current full suite: `2390 passed, 1 skipped`.
- Refreshed all maintained coverage lanes at 100% statements and branches.


## v1.9.2

### Multi-emotion state + deterministic spotlight hysteresis

- Added a separate persistent emotional-state layer alongside the existing
  relationship layer.
- Added default bounded `0..1` channels for anger, fear, grief, hope, and joy.
- Added explicit signed event impulses, per-agent sensitivities, per-channel
  inertia, baselines, salience bias, and configurable event profiles.
- Added deterministic spotlight hysteresis with a default switch margin of
  `0.05`, preventing near-tie attention flicker while allowing clear handoffs.
- Added `apply_layered_event(...)` so one normalized event can update both the
  existing relationship state and target emotional state without conflating
  the two layers.
- Added emotion snapshot sub-schema `1.1` while preserving restoration of
  legacy emotion snapshot sub-schema `1.0`.
- Kept the top-level Ghost snapshot schema at `1.0`.
- Added multi-emotion, dynamics-torture, spotlight-hysteresis, and frozen
  public-contract test suites.
- Added live browser-demo / PyPI / source links to package-facing metadata.
- Current full suite: `1763 passed, 1 skipped`.
- Refreshed all maintained coverage lanes at 100% statements and branches.

## v1.9.1

### Ghost Revolution public developer CLI

- Bumped the package/runtime producer version from `1.9.0` to `1.9.1` while
  keeping snapshot schema `1.0` unchanged.
- Added `ghost-revolution-dev` for direct access to existing late-game,
  champion, siege, and king-fight developer shortcuts without an API key.
- Added `ghost-revolution-llm-dev` for opt-in live opponent + narration LLM use.
- The live launcher requests the user's own OpenAI API key with hidden terminal
  input, does not read `.env.local`, does not write or echo the entered key, and
  restores managed environment variables on exit/error.
- Kept `httpx` optional rather than adding a base runtime dependency.
- Explicitly documents Ghost Revolution as a playable reference prototype and
  systems demonstration, not a finished game.
- Added persistent launcher and layout regression tests.
- Current full suite: `1680 passed, 1 skipped`.
- Refreshed all maintained coverage lanes at 100% statements and branches.

## v1.9.0

### Packaging and public CLI surface

- Bumped the package/runtime producer version from `1.8.0` to `1.9.0`.
- Kept `GHOST_SNAPSHOT_SCHEMA_VERSION` at `1.0`; this release does not change
  the serialized snapshot contract.
- Added public console commands `ghost-epistemic-demo`,
  `ghost-revolution-demo`, and `ghost-order-coordination-demo`.
- Added a console-safe `main()` wrapper to the Order Coordination demo.
- Added persistent v1.9 packaging/CLI regression coverage.
- Verified the built wheel and sdist with `python -m build` and `twine check`.
- Verified 55 / 55 packaged Python files and 11 / 11 console-script entry
  points from the built wheel.
- Verified an isolated pip install, real pip-generated wrapper routing for all
  11 commands, end-to-end execution of the epistemic and Order Coordination
  demos, and a separate sdist install/import.
- Current full suite: `1674 passed, 1 skipped`.

### Coverage

- Reusable Ghost core: 3,112 / 3,112
  statements and 1,276 / 1,276 branches
  covered (100% / 100%).
- Complete Ghost Revolution package:
  7,149 / 7,149 statements
  and 2,736 / 2,736 branches
  covered (100% / 100%).
- Order Coordination: 1,624 / 1,624
  statements and 542 / 542 branches
  covered (100% / 100%).
- Added fresh versioned evidence under `docs/coverage/v1.9.0/`; the committed
  `docs/coverage/v1.8.0/` evidence remains unchanged as historical evidence.

## v1.8.0 — Epistemic State, Combat Control, Scenarios, and Runtime Hardening

### Epistemic state

- Added objective fact records that remain separate from actor knowledge.
- Added actor-owned observations, reports, evidence, beliefs, provenance,
  confidence, and explicit belief revision.
- Added public `GhostAPI` operations:
  - `record_fact`
  - `get_fact`
  - `observe`
  - `report`
  - `add_evidence`
  - `evaluate_beliefs`
  - `get_belief`
  - `propagate_belief`
- Reports no longer become objective truth or forced beliefs.
- Belief revisions preserve previous-belief links and append-only history.
- Epistemic state now participates in ticking, JSON-safe snapshots, strict
  validation, and deterministic restoration.
- Added a public epistemic smoke demo.

### Threat response and combat control

- Added deterministic threat-response policy with bounded response labels:
  `fight`, `call_guards`, `confront`, `surrender`, `flee`, `freeze`, `warn`,
  and `ignore`.
- Added `evaluate_threat_response(...)` and
  `evaluate_npc_threat_response(...)`.
- Added fight-level objective packets.
- Added authoritative combat-initiative transitions.
- Added hidden recovery-read locking and deterministic recovery resolution.
- Added strict normalization and validation for combat-control packets.

### Scenario runtime

- Added validated, JSON-safe scenario configuration.
- Added deterministic `ScenarioRuntime`.
- Added atomic action resolution with checkpoint restoration after rejection.
- Added intensity-authority and branch-contract coverage.

### Ghost Revolution reference implementation

- Added the terminal Ghost Revolution package under
  `ghost.examples.ghost_revolution`.
- Added town memory, guards, raids, preparation, endgame state, Crown outcomes,
  game snapshots, developer shortcuts, and terminal presentation.
- Added controlled epistemic benchmarks that branch from identical saved states.
- Added optional real-LLM strategy, narration, and ambient-scene bridges.
- Added a king and Champion fight with:
  - heavy and light attacks;
  - feint-heavy, feint-light, and pure bait;
  - parry, deflect, and dodge;
  - separate prediction and physical action;
  - deterministic symmetric resolution;
  - initiative, recovery, openings, and audit packets.
- Added Android development and cinematic launchers.

Ghost Revolution remains a game-specific reference demo. Its towns, combat damage,
menus, and presentation are not universal Ghost-core concepts.


### Order Coordination reference application

- Added `ghost.examples.order_coordination` as an application-layer proof built
  on the public `GhostAPI`; no restaurant/order concepts were added to core.
- Added explicit ambiguous-target state, customer clarification, evidence-backed
  belief revision, correction handling, confirmation revision binding,
  idempotent operation IDs, submission gating, and JSON-safe snapshots.
- Hardened snapshot restoration for correction and confirmation record schemas,
  item references, epistemic observation/belief references, revision
  consistency, and ledger consistency.
- Added deterministic, paired live-model, and offline-replay benchmark tools.
- The live benchmark reuses one raw model proposal across transcript-only and
  Ghost-backed modes and treats model confidence as advisory metadata.
- Order Coordination remains a narrow reference application rather than a
  production ordering product or universal Ghost-core domain.

### Snapshot and restoration hardening

Seven audit areas were closed:

1. **Configuration ownership**
   - default configuration and event maps no longer share mutable state;
   - caller-owned configuration is copied at the public boundary;
   - intentionally empty custom event maps remain authoritative.

2. **Read semantics**
   - read APIs no longer create relationship pairs or rewrite live state;
   - unknown reads remain non-mutating.

3. **Mutation authority**
   - relationship changes route through one authoritative mutation pipeline;
   - duplicate or bypass mutation paths were removed or covered.

4. **Atomic compound operations**
   - failed compound actions restore the complete prior checkpoint;
   - partial relationship, world, scenario, and epistemic mutation is rejected.

5. **Restoration trust boundary**
   - snapshots are validated before runtime construction;
   - nested relationships, neighbors, world state, event maps, epistemic records,
     and references receive strict shape and semantic validation.

6. **Version and schema compatibility**
   - package version and snapshot schema version are independent;
   - supported legacy `1.7.5` metadata is migrated;
   - unknown schemas remain rejected.

7. **Public output isolation**
   - public packets, registry reads, relationships, snapshots, and nested values
     are copied so caller mutation cannot silently rewrite internal state.

Additional cleanup:

- unified world-pressure classification;
- retired duplicate public relationship constants;
- accepted, validated, and dropped inert legacy transition state during restore;
- stopped emitting the obsolete snapshot `transitions` field;
- normalized game-action and caller-context handling;
- expanded finite-number and JSON-safety checks.

### Quality and validation

- Added separate normal, performance, core-coverage, and Ghost Revolution
  coverage lanes.
- Added branch-contract, atomicity, restoration, copy-isolation, fuzz,
  normalization, benchmark, architecture, and continuation-integrity tests.
- Current synchronized repository result:

```text
1,667 passed
1 skipped
```

- Reusable Ghost core: 100% statements and branches.
- Complete Ghost Revolution package: 100% statements and branches.
- Order Coordination reference application: 100% statements and branches.

- Added `QUALITY.md`, `BENCHMARK_RESULTS.md`, `coverage.core.ini`, and
  `coverage.revolution.ini`.

## v1.7.5 — Public Social-Propagation Bridge

- Exposed the social-propagation bridge through the recommended public API.
- Preserved JSON-safe packets and bounded observer/world effects.
- Added public integration and regression coverage.

## v1.7.4 — Governance Language and Threat Bands

- Added apology-language governance support.
- Added warning, implied-retaliation, coercive-ultimatum, and direct-harm threat
  bands.
- Added negation, reported-speech, third-party-warning, self-defense, and
  clause-aware threat guards.
- Added bounded apology recovery and resistance to apology spam.

## v1.7.3 — Relationship Shock and Stability Breach

- Added a bounded positive goodwill reservoir cap.
- Added mature-relationship stability-breach behavior for betrayal.
- Added high-severity negative-event shock handling.
- Added maturity resistance floors and recent-event magnitude diagnostics.

## v1.7.2 — Persistent Distrust

- Added wary emotional reads for materially negative neutral relationships.
- Added reserved stance.
- Preserved near-break state during structural recovery.
- Stabilized diagnostics for microscopic decay drift.

## v1.7.1 — Public API Cleanup

- Established `GhostAPI` as the recommended integration boundary.
- Clarified `GhostAPI` versus `GhostEngine`.
- Added versioned JSON-safe snapshot metadata.
- Added typed constants while preserving string compatibility.
- Strengthened ID, packet-schema, state/snapshot, and installed-package tests.

## v1.7.0 — Temperament Interpretation and Boundary Hardening

- Added deterministic temperament interpretation.
- Added calm, anxious, confident, suspicious, resentful, loyal, and volatile
  profiles.
- Added stricter public numeric validation, scale checks, snapshot checks, and
  mathematical invariants.

## v1.6.0 — Social Propagation

- Added weighted observer propagation.
- Added social heat, near-break pressure, world-effect packets, and public tick
  packets.
- Added the social-propagation CLI demo.

## v1.5.0 — Relationship Diagnostics

- Added trust-before/trust-after values, deltas, severity, pressure, transition,
  trigger, maturity, and volatility diagnostics.
- Added tick-decay diagnostics and JSON-safe diagnostic validation.

## v1.4.0 — Relationship Maturity and Volatility

- Added maturity, volatility, positive volatility, negative volatility, maturity
  gain, and maturity cap.
- Added personality-specific relationship stability behavior.

## v1.3.0 — Ghost Math Demo

- Added the packaged math demo.
- Documented reservoirs, trust calculation, decay, thresholds, maturity, and
  volatility behavior.

## v1.2.1 — Demo Cleanup

- Simplified packaged demo commands.
- Improved the deterministic NPC demo and phone-safe terminal output.

## v1.2.0 — Shopkeeper Mini Game

- Added the playable shopkeeper terminal demo.
- Connected relationship state to prices, quest access, dialogue, and time-based
  decay.

## v1.1.1 — Public Relationship Wrappers

- Fixed and verified public `apply_event`, `tick`, and `get_relationship`
  wrappers.

## v1.1.0 — Public Relationship Runtime

- Added the reusable public relationship API.
- Exposed trust, state, transitions, triggers, and emotional inertia.

## v1.0.1 — Packaged Proof Demo

- Added the installable `ghost-demo` entry point.

## v1.0.0 — Emotional Inertia Runtime

- Introduced separate positive and negative relationship reservoirs.
- Added resistance, saturation, decay, personality presets, transitions, and
  structured triggers.

## v0.2.x — Deterministic Multi-Agent Prototype

- Added multi-agent state mutation, relationship mutation, bounded propagation,
  actor threat memory, idle decay, JSON-safe snapshots, and serialization
  hardening.

## v0.1.x — Foundational Architecture

- Established the explicit deterministic state-transition core and early
  invariant tests.
