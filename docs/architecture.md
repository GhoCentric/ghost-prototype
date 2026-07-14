# Ghost Engine Architecture

Ghost is a deterministic state engine.

It receives explicit events or structured inputs, updates owned
state through bounded rules, and returns inspectable packets to the
calling application.

It is not a language model and does not require one.

## High-Level Flow

```text
external event or structured input
                |
                v
      public API validation
                |
                v
   deterministic state subsystem
                |
                v
    diagnostics / result packet
                |
                v
   external application behavior
```

Optional language-model integration occurs after, or around, this
deterministic boundary. A model may propose or describe something,
but it does not become authoritative merely because it generated
text.

## Public Runtime Surfaces

### GhostEngine

`ghost.engine.GhostEngine` is the focused relationship runtime.

Its core public operations include:

```text
apply_event(a, b, event)
tick()
get_relationship(a, b)
propagate_social_event(...)
```

This surface is useful for NPC relationships, faction standing,
shopkeeper logic, guard reactions, reputation, and other persistent
pairwise state.

### GhostAPI

`ghost.api.GhostAPI` is the wider facade.

It coordinates public capabilities that include:

- relationship events and ticks
- social propagation
- world effects and world state
- epistemic facts, observations, reports, evidence, and beliefs
- temperament interpretation
- threat-response evaluation
- governance evaluation
- commerce and pricing evaluation
- law and reintegration evaluation
- snapshot creation and restoration
- optional voice-prompt and deterministic fallback helpers

The facade does not erase subsystem boundaries. It provides a
single integration point over them.

## Relationship Runtime

Relationship state is persistent and directional.

Ghost maintains separate positive and negative history rather than
reducing every interaction to one temporary score.

A relationship packet may expose:

```text
trust
state
transition
trigger
diagnostics
maturity
volatility
positive_volatility
negative_volatility
```

The application can use that packet to change prices, access,
dialogue availability, guard suspicion, faction behavior, quests,
or other game systems.

Ghost supplies the state. The application supplies the presentation
and external side effects.

## Social Propagation

A direct event can create bounded secondary effects for observers.

Social propagation may produce:

- direct relationship results
- weighted observer changes
- social heat
- pressure labels
- world-effect deltas
- JSON-safe result packets

Observer effects are not required to equal the direct event.
Weights and social heat allow downstream consequences to remain
explicit and inspectable.

## Epistemic Runtime

The epistemic layer separates several concepts that language-driven
systems often collapse together:

```text
objective fact
observation
report
evidence
belief
provenance
confidence
revision
propagation
```

A report is not automatically treated as objective truth.

A speaker may be mistaken, deceptive, uncertain, or repeating
secondhand information. Ghost can store the report, record available
evidence, evaluate candidate beliefs, and later revise a belief
without rewriting the underlying objective record.

The public epistemic operations include:

```text
record_fact(...)
observe(...)
report(...)
add_evidence(...)
evaluate_beliefs(...)
get_belief(...)
propagate_belief(...)
```

This is a state-management and evidence-accounting layer. It is not
a universal truth detector and does not infer reliable provenance
from arbitrary prose by itself.

## Interpretation Layers

Temperament and threat-response evaluation consume authoritative
state and produce structured interpretation packets.

Temperament can make the same relationship state appear different
to different NPC profiles without changing the underlying
relationship history.

Threat-response evaluation can combine:

- relationship state
- temperament
- explicit context
- deterministic policy rules

The resulting packet can guide an external behavior system while
keeping the policy path visible.

## Governance and Scenario Policies

The integrated facade contains deterministic evaluators for areas
such as:

- claims and intent assessment
- effect assessment
- governance
- commerce
- prices
- law
- punishment and reintegration
- world events and world effects

These evaluators return structured decisions or state changes.

They do not independently execute real-world actions. A game or
application chooses how to apply the result.

## Snapshot Boundary

Ghost supports snapshot-based persistence.

Snapshots allow an application to:

- save engine state
- restore a prior state
- create equal starting points for deterministic comparisons
- test alternative branches from the same history
- serialize state without relying on hidden model memory

The epistemic runtime and integrated API both expose snapshot
operations.

Ghost Revolution benchmarks use exact snapshot restoration to
compare different policies from the same game state.

## LLM Boundary

Language models are optional.

Two supported integration patterns are demonstrated by the current
project.

### Narration

An LLM receives a resolved state packet and renders prose.

The model does not decide the authoritative damage, relationship
transition, world state, death, timer, or legal outcome.

### Proposed Intent

In Ghost Revolution, an opponent strategist may propose a legal
tactic and a hidden reaction plan.

The deterministic runtime then:

```text
validates proposal
-> locks accepted intent
-> applies deterministic fallback when invalid
-> waits for player commitment
-> resolves the exchange
-> exposes the resolved packet
-> allows narration of that packet
```

There is no requirement that model-generated reasoning be accepted
as state truth.

## Authority Table

| Concern | Authority |
|---|---|
| Relationship mutation | Ghost |
| Social propagation | Ghost |
| Belief records and revision | Ghost |
| World-effect deltas | Ghost |
| Snapshot state | Ghost |
| Deterministic policy result | Ghost |
| External animation | Application |
| UI and terminal presentation | Application |
| Final dialogue wording | Template or optional LLM |
| Model proposal legality | Ghost validation |
| External database writes | Application |

## Design Guarantees

The architecture is designed around:

- deterministic state transitions
- explicit inputs
- bounded state
- inspectable diagnostics
- serialization-safe packets
- reproducible snapshots
- separation of state authority from generated language
- deterministic fallback paths

Specific guarantees are established by tests for specific modules
and scenarios. They should not be generalized into claims of total
AI safety, universal correctness, or universal superiority.

## Non-Goals

Ghost does not claim to be:

- a general intelligence
- a consciousness model
- a complete autonomous agent
- a general-purpose truth detector
- a replacement for an application or game engine
- proof that every downstream behavior will be correct
