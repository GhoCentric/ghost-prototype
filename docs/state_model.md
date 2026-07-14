# Ghost State Model

Ghost stores explicit, inspectable state.

The engine is not built around one universal state vector. It uses
several related state domains, each with its own update rules and
output packets.

## Relationship State

Relationship state is directional and persistent.

A relationship is identified by two entities:

```text
source -> target
```

The reverse relationship may have different state.

Ghost uses separate positive and negative reservoirs:

```text
trust = positive_reservoir - negative_reservoir
```

This preserves the difference between accumulated positive history
and accumulated damage.

A later positive event does not simply delete a prior betrayal.

### Core Relationship Fields

A public relationship packet may include:

- trust
- readable state
- latest transition
- transition trigger
- diagnostics
- maturity
- volatility
- positive volatility
- negative volatility

Readable relationship states currently include states such as:

```text
hostile
neutral
friendly
```

### Diagnostics

Diagnostics explain the latest mutation.

Depending on the event and path, fields may include:

- event
- channel
- base amount
- effective gain
- trust before
- trust after
- delta
- absolute delta
- direction
- severity
- pressure
- near-break status
- transition
- trigger
- maturity
- volatility

These fields allow external systems to distinguish a small negative
shift from a relationship break even when both are technically
negative events.

### Maturity and Volatility

Maturity represents accumulated relationship stability.

Volatility determines how strongly future events move the
relationship.

Positive and negative volatility can differ, allowing two
relationships with similar trust to respond differently to the
same new event.

Maturity does not erase history. It modifies future sensitivity.

## Temporal State

`tick()` advances time-dependent engine behavior.

Temporal updates may decay or stabilize values according to the
current subsystem rules.

Time does not automatically reset the relationship to neutral.
Persistent history and asymmetry remain part of the model.

## Near-Break and Pressure State

Ghost can distinguish between:

- ordinary movement
- major negative movement
- near-break pressure
- an actual relationship break
- de-escalation
- forgiveness
- other state shifts

Pressure labels make the meaning of a transition explicit for
downstream systems.

## Social State

Social propagation converts one direct event into bounded effects
on observers and world systems.

A propagation packet may contain:

- source
- target
- event
- direct relationship result
- observer results
- observer weights
- heat
- severity
- pressure
- world effects

Social heat represents how strongly a direct event should matter
outside the original relationship.

External systems may map heat into:

- rumor strength
- guard suspicion
- town fear
- faction pressure
- public reputation
- escalation risk

World-effect values are deltas or structured state updates, not
commands to animate or narrate a particular response.

## Temperament State

Temperament is an interpretation layer over authoritative state.

Supported profiles include examples such as:

- calm
- anxious
- confident
- suspicious
- resentful
- loyal
- volatile

Temperament output may include:

- emotional read
- stance
- fear
- suspicion
- anger
- confidence
- loyalty
- relief
- intensity

Temperament does not rewrite the relationship history.

Two NPCs can receive the same relationship packet and interpret it
differently while the authoritative trust and event history remain
unchanged.

## Threat-Response State

Threat-response evaluation combines explicit inputs such as:

- NPC identity
- relationship state
- temperament
- supplied context

It returns a deterministic response packet suitable for an external
guard, dialogue, or behavior layer.

This is policy evaluation, not autonomous world execution.

## Epistemic State

The epistemic runtime tracks what is true, what was observed, what
was reported, what evidence exists, and what an actor currently
believes.

These are separate record types.

### Objective Facts

Facts describe authoritative world state supplied by the
application.

A fact can include:

- fact identifier
- source
- subject
- predicate
- object
- attributes

### Observations

Observations describe visible or measured information available to
an observer.

They can include:

- observer
- kind
- visible features
- reliability
- provenance
- subject

An observation is evidence available to an actor. It is not
necessarily a complete objective fact.

### Reports

Reports represent claims communicated between actors.

A report can track:

- speaker
- audience
- claim
- confidence
- source belief
- provenance

Reports are not promoted to truth automatically.

### Evidence

Evidence can support or contradict candidate beliefs.

It may include:

- evidence type
- source
- supported candidates
- contradicted candidates
- subject
- actors who can access it
- provenance

### Beliefs

Beliefs belong to a holder and subject.

Belief evaluation can consider:

- candidate interpretations
- available evidence
- report quality
- previous belief state
- provenance

The resulting belief may expose confidence and uncertainty without
changing the objective fact record.

### Revision

New evidence can revise a prior belief.

The system can preserve:

```text
earlier report
earlier belief
new evidence
revised belief
provenance chain
```

This allows deterministic correction without pretending that the
earlier actor possessed knowledge they did not have.

### Propagation

A belief can be reported or propagated to another actor while
remaining distinct from objective state.

The listener can evaluate the claim using its own evidence and
confidence path.

## Governance and World State

The integrated API also maintains or evaluates structured state for:

- verified world facts
- claims and assessed intent
- effects
- governance decisions
- commerce access
- prices
- law
- warnings
- punishment
- reintegration
- world events
- world-effect deltas

These systems use explicit records and deterministic evaluation
rather than free-form language as state authority.

## Serialization

Public state packets and snapshots are designed to remain
serialization-safe.

Snapshot support is used for:

- persistence
- deterministic replay
- branch comparison
- tests
- benchmark forks
- restoring epistemic history

## What State Does Not Mean

Ghost state should not be interpreted as proof that an NPC:

- is conscious
- experiences human emotion
- has unrestricted agency
- knows objective truth
- has formed a plan unless a plan record explicitly exists

State is an engineering representation used to preserve causality,
history, policy, and uncertainty.
