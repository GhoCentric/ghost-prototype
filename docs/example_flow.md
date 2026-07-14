# Example Flow

This example shows how Ghost can connect a direct relationship
event to social consequences while leaving external game behavior
under application control.

## Scenario

A player betrays a shopkeeper.

The game wants to update:

- the direct player-to-shopkeeper relationship
- nearby observers
- social heat
- world-effect values
- later NPC behavior

## Step 1: Create the Relationship Runtime

```python
from ghost.engine import GhostEngine

ghost = GhostEngine()
```

## Step 2: Establish Prior History

```python
ghost.apply_event(
    "player",
    "shopkeeper",
    "help",
)

ghost.tick()

before = ghost.get_relationship(
    "player",
    "shopkeeper",
)
```

`before` is an authoritative relationship packet.

It may contain trust, state, maturity, volatility, diagnostics, and
transition information.

## Step 3: Apply and Propagate the Event

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

`propagate_social_event(...)` applies the direct betrayal once and
then produces the bounded observer and world-effect results derived
from that event.

Calling `apply_event(...)` first would record a separate additional
betrayal, so the two operations should not be combined for the same
single event.

Ghost deterministically updates its owned relationship state.

The application does not need to infer the change from generated
dialogue.

It can inspect both the stored relationship and the direct result
inside the propagation packet:

```python
relationship = ghost.get_relationship(
    "player",
    "shopkeeper",
)

direct = packet["direct"]

print(
    relationship["trust"]
)

print(
    relationship["state"]
)

print(
    relationship["diagnostics"]
)

print(
    direct
)
```

Depending on prior history and relationship parameters, the event
may create a major negative shift, near-break pressure, or an
actual relationship break.

## Step 4: Inspect the Propagation Packet

The propagation packet can expose:

```text
direct relationship result
observer relationship changes
social heat
pressure
severity
world-effect deltas
```

The guard does not have to receive the same change as the
shopkeeper. Observer weights keep secondary effects explicit.

## Step 5: Map the Packet into Game Behavior

The game reads Ghost state and performs its own external actions.

```python
guard_state = ghost.get_relationship(
    "player",
    "guard",
)

heat = packet["heat"]

if (
    guard_state["state"] == "hostile"
    or heat >= 0.8
):
    access = "blocked"

elif heat >= 0.4:
    access = "restricted"

else:
    access = "normal"
```

`access` belongs to the game layer.

Ghost supplied the causal state. The game decided how that state
affects entry to the market.

## Step 6: Use the Wider Facade

Applications that need epistemic, temperament, threat, governance,
world-state, commerce, or law features can use `GhostAPI`.

```python
from ghost.api import GhostAPI

api = GhostAPI()

api.apply_event(
    "player",
    "guard",
    "betrayal",
)

relationship = api.get_relationship(
    "player",
    "guard",
)

interpreted = (
    api.interpret_relationship_packet(
        npc="guard",
        relationship=relationship,
        temperament="suspicious",
    )
)
```

The interpretation packet does not replace the underlying
relationship record. It gives the application structured metadata
for that NPC profile.

## Step 7: Add Epistemic State

Consider a second question:

```text
Is an elite knight currently present in Crownmarket?
```

The application may provide:

- an objective world fact
- a scout observation
- a merchant report
- patrol evidence
- candidate beliefs
- provenance for each source

The public epistemic flow is:

```text
record_fact(...)
-> observe(...) or report(...)
-> add_evidence(...)
-> evaluate_beliefs(...)
-> get_belief(...)
-> later evidence
-> evaluate_beliefs(...) again
```

The merchant report is not automatically treated as objective
truth.

A listener can hold a belief with uncertainty, investigate, receive
stronger evidence, and revise that belief while the original report
remains in the record.

## Step 8: Optional Language Rendering

An optional language model or template system can receive the
resolved state packet and produce a line such as:

```text
"We're closed. The guard wants to speak with you."
```

That sentence does not mutate the relationship or world state.

The authoritative sequence remains:

```text
external event
-> deterministic Ghost mutation
-> structured result packet
-> external behavior mapping
-> optional narration
```

## Why This Flow Matters

The event has one traceable causal path:

```text
betrayal
-> direct trust damage
-> relationship pressure
-> observer propagation
-> social heat
-> game access restriction
-> optional dialogue
```

Dialogue is the visible surface, not the source of truth.

## Limits

This example does not claim that Ghost determines the universally
correct behavior for every game.

It demonstrates that:

- state changes are explicit
- history persists
- secondary effects are inspectable
- beliefs can remain separate from facts
- generated language does not own state
- external behavior remains under application control
