ghocentric-ghost-engine

A lightweight, deterministic state engine for experimenting with persistent state, temporal dynamics, emotional inertia, social propagation, and emergent behavior in interactive systems.

Ghost is NOT a language model and NOT a decision-maker.

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

Installation

pip install ghocentric-ghost-engine

Demo Commands

After installation, Ghost includes six runnable demo commands:

ghost-demo
ghost-npc-demo
ghost-shopkeeper-demo
ghost-math-demo
ghost-diagnostics-demo
ghost-social-demo

Each demo proves a different layer of the engine:

- "ghost-demo" compares Ghost emotional inertia against a linear baseline
- "ghost-npc-demo" shows Ghost API state being mapped into external NPC behavior
- "ghost-shopkeeper-demo" launches a playable terminal shopkeeper demo
- "ghost-math-demo" explains Ghost relationship math with formulas, worked examples, personality tuning, maturity, volatility, and gameplay mapping
- "ghost-diagnostics-demo" explains relationship transitions with measurable diagnostics such as trust delta, severity, pressure, maturity, and volatility
- "ghost-social-demo" demonstrates social propagation, observer effects, near-break pressure, weighted NPC reactions, and world-effect packets

Basic Usage

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

Ghost mutates state only through explicit "step()" calls.

All public-facing state is exposed as dictionaries and is safe to serialize.

Public Relationship API

Ghost includes a direct public API for working with relationships as a reusable runtime system.

You can apply emotional events directly, advance time, inspect relationship state, and propagate social effects without reaching into internal modules.

from ghost.engine import GhostEngine

ghost = GhostEngine()

ghost.apply_event("player", "shopkeeper", "help")
ghost.apply_event("player", "shopkeeper", "insult")
ghost.apply_event("player", "shopkeeper", "betrayal")

rel = ghost.get_relationship("player", "shopkeeper")

print(rel)

Example returned structure:

{
    "trust": -0.703,
    "state": "hostile",
    "transition": ("neutral", "hostile"),
    "trigger": {
        "event": "relationship_broken"
    },
    "diagnostics": {
        "event": "betrayal",
        "channel": "neg",
        "from_state": "neutral",
        "to_state": "hostile",
        "trust_before": 0.047,
        "trust_after": -0.703,
        "delta": -0.750,
        "abs_delta": 0.750,
        "direction": "negative",
        "severity": 0.750,
        "pressure": "relationship_broken",
        "near_break": False,
    },
    "maturity": 0.03,
    "volatility": 1.0,
    "positive_volatility": 1.0,
    "negative_volatility": 1.0,
}

The public relationship API includes:

ghost.apply_event(a, b, event)

ghost.tick()

ghost.get_relationship(a, b)

ghost.propagate_social_event(
    source,
    target,
    event,
    observers=None,
    weights=None,
)

These methods make Ghost usable as a direct state engine for NPC, faction, town, reputation, and social consequence systems.

What v1.1.0 Adds

v1.1.0 expanded Ghost from a proof-demo emotional model into a reusable public API.

New public behavior included:

- direct relationship event application
- public relationship inspection
- time-based relationship ticking
- relationship state output
- transition output
- trigger output
- cleaner runtime access for external systems
- reusable API surface for NPC logic

This means external systems can consume Ghost relationship state directly for things like:

- dialogue changes
- shopkeeper pricing
- guard suspicion
- faction hostility
- reputation recovery
- betrayal consequences
- forgiveness events
- long-term NPC memory

Ghost still does not decide what an NPC does.

Ghost exposes state.

Your game, simulation, LLM layer, or behavior system decides how to respond.

Emotional Inertia System

Ghost includes a deterministic emotional inertia system for modeling relationships over time.

Unlike simple accumulation or smoothing systems, relationships in Ghost:

- remember past interactions
- resist sudden changes
- decay over time
- respond differently depending on history

This enables more realistic behavior under oscillating inputs such as:

insult -> help -> insult -> help

Where traditional systems reset or average out, Ghost preserves emotional direction.

Dual-Channel Relationship Model

Relationships are no longer a single value.

Each relationship tracks:

- positive reservoir ("pos")
- negative reservoir ("neg")

trust = pos - neg

This allows:

- damage to persist independently of recovery
- recovery to require sustained effort
- asymmetric emotional behavior

A character can receive positive input while still carrying unresolved negative history.

That means a single helpful action after betrayal does not instantly erase the betrayal.

Emotional Dynamics

Ghost relationships include resistance, saturation, and time-based decay.

Resistance

High negative history reduces the effectiveness of positive events.

For example, helping an NPC after repeated insults or betrayal may improve the relationship slightly, but it will not instantly restore trust.

Saturation

Repeated positive interactions produce diminishing returns.

This prevents simple positive-event spam from producing unrealistic instant loyalty.

Time-Based Decay

Relationships evolve over time using:

ghost.tick()

Decay is no longer tied only to events.

This allows long-running simulations to model gradual cooling, recovery, stabilization, or emotional drift over time.

As of v1.6.0, "tick()" returns a public readable packet instead of returning "None".

Example:

packet = ghost.tick()

print(packet["event"])
print(packet["relationships"])

Example returned structure:

{
    "event": "tick",
    "relationships": [
        {
            "a": "player",
            "b": "shopkeeper",
            "trust": -0.75075,
            "state": "hostile",
            "transition": None,
            "trigger": None,
            "diagnostics": {
                "event": "tick",
                "channel": "decay",
                "trust_before": -0.77,
                "trust_after": -0.75075,
                "delta": 0.01925,
                "direction": "positive",
                "pressure": "minor_positive_shift",
                "near_break": False,
            },
            "maturity": 0.01,
            "volatility": 1.0,
            "positive_volatility": 1.0,
            "negative_volatility": 1.0,
        }
    ],
}

Personality Presets

Relationships can have different emotional profiles.

ghost.relationships.set_personality("A", "B", "resentful")

Available presets:

- balanced
- forgiving
- resentful
- volatile

Each preset modifies:

- gain sensitivity
- decay speed
- recovery behavior
- maturity behavior
- positive volatility
- negative volatility

Personality presets allow the same event sequence to produce different emotional outcomes depending on the relationship profile.

Relationship Maturity and Volatility

v1.4.0 adds relationship maturity and volatility to Ghost's relationship runtime.

Maturity represents relationship stability over repeated interactions.

Volatility controls how strongly new events affect a relationship.

Ghost tracks:

- "maturity"
- "volatility"
- "positive_volatility"
- "negative_volatility"
- "maturity_gain"
- "maturity_cap"

Maturity does not erase history.

It reduces future emotional swing.

This means the same betrayal can produce different outcomes depending on relationship history.

A short relationship can still break immediately after betrayal.

A long relationship with repeated positive history may absorb one betrayal without instantly becoming hostile.

Positive and negative volatility can also differ.

This allows personalities to behave differently under the same event sequence:

- balanced relationships respond normally
- forgiving relationships resist negative swings
- resentful relationships are hit harder by negative events
- volatile relationships can bond quickly and drop sharply

Relationship Diagnostics

v1.5.0 adds relationship diagnostics to Ghost's public relationship output.

Diagnostics explain what changed, how strongly it changed, and why the state shifted.

Ghost exposes a "diagnostics" packet after relationship events and ticks.

Diagnostics include:

- "event"
- "channel"
- "base_amount"
- "effective_gain"
- "from_state"
- "to_state"
- "trust_before"
- "trust_after"
- "delta"
- "abs_delta"
- "direction"
- "severity"
- "maturity"
- "maturity_modifier"
- "volatility"
- "positive_volatility"
- "negative_volatility"
- "transition"
- "trigger"
- "pressure"
- "near_break"

This makes relationship changes inspectable.

A game, simulation, tool, or adapter can see not only the final relationship state, but also the measurable cause of the change.

Example diagnostic packet:

{
    "event": "betrayal",
    "channel": "neg",
    "base_amount": 0.7,
    "effective_gain": 0.7546,
    "from_state": "friendly",
    "to_state": "hostile",
    "trust_before": 0.2009,
    "trust_after": -0.5537,
    "delta": -0.7546,
    "abs_delta": 0.7546,
    "direction": "negative",
    "severity": 0.7546,
    "maturity": 0.02,
    "maturity_modifier": 0.98,
    "volatility": 1.0,
    "positive_volatility": 1.0,
    "negative_volatility": 1.0,
    "transition": ("friendly", "hostile"),
    "trigger": {
        "event": "relationship_broken"
    },
    "pressure": "relationship_broken",
    "near_break": False,
}

Diagnostics are designed to support systems such as:

- NPC-to-NPC social propagation
- faction reputation changes
- guard suspicion
- town pressure
- expression metadata
- external debug tools
- gameplay consequence systems

Ghost still does not decide what happens next.

Ghost exposes the measurable state change so another system can decide how to respond.

Near-Break Pressure

v1.6.0 adds "near_break" pressure.

Neutral no longer only means calm.

A relationship can be technically neutral while still being strained and close to hostile.

Example:

{
    "trust": -0.538,
    "state": "neutral",
    "diagnostics": {
        "pressure": "near_break",
        "near_break": True,
        "direction": "negative",
        "severity": 0.655,
    }
}

This allows external systems to distinguish between:

- calm neutral
- recovering neutral
- uncertain neutral
- strained neutral
- barely restrained neutral

A game can use this state to change dialogue, pricing, access, guard suspicion, faction pressure, or future consequences before the relationship fully breaks.

Social Propagation

v1.6.0 adds social propagation through the public API.

Social propagation lets one direct relationship event create bounded secondary effects on observers.

Example:

from ghost.engine import GhostEngine

ghost = GhostEngine()

packet = ghost.propagate_social_event(
    source="player",
    target="shopkeeper",
    event="betrayal",
    observers=["guard", "elder", "rival"],
    weights={
        "guard": 1.0,
        "elder": 0.7,
        "rival": 0.25,
    },
)

print(packet)

Example returned structure:

{
    "source": "player",
    "target": "shopkeeper",
    "event": "betrayal",
    "heat": 1.0,
    "severity": 0.77,
    "pressure": "relationship_broken",
    "direct": {
        "trust": -0.77,
        "state": "hostile",
        "diagnostics": {
            "pressure": "relationship_broken",
            "near_break": False,
        },
    },
    "propagated": [
        {
            "affected": "guard",
            "source_event": "betrayal",
            "source_pressure": "relationship_broken",
            "heat": 1.0,
            "trust_delta": -0.20,
            "relationship": {
                "trust": -0.20,
                "state": "neutral",
            },
        },
        {
            "affected": "elder",
            "source_event": "betrayal",
            "source_pressure": "relationship_broken",
            "heat": 1.0,
            "trust_delta": -0.14,
            "relationship": {
                "trust": -0.14,
                "state": "neutral",
            },
        },
        {
            "affected": "rival",
            "source_event": "betrayal",
            "source_pressure": "relationship_broken",
            "heat": 1.0,
            "trust_delta": -0.05,
            "relationship": {
                "trust": -0.05,
                "state": "neutral",
            },
        },
    ],
    "world_effects": {
        "pressure_delta": 0.20,
        "fear_delta": 0.08,
        "resentment_delta": 0.08,
        "order_delta": -0.04,
        "guard_suspicion_delta": 0.35,
    },
}

Social propagation is bounded and deterministic.

Observers can react at different strengths through weights.

This allows external systems to model effects such as:

- guards hearing about a theft
- towns reacting to betrayal
- faction reputation shifting
- rumors spreading through a social graph
- local hostility increasing after public violence
- world pressure rising after major relationship damage

Ghost still does not decide what observers do.

Ghost exposes the propagated state packet.

The game decides how to respond.

Social Heat

v1.6.0 adds social heat.

Social heat measures how much a direct relationship event should matter to observers or world systems.

The current pressure ordering is:

relationship_broken > near_break > major_negative_shift > state_shift > normal shifts

This means a full relationship break creates more social heat than a strained neutral state, and a strained neutral state creates more social heat than an ordinary minor shift.

Social heat is exposed in social propagation packets as:

packet["heat"]

External systems can use heat to scale:

- rumor strength
- guard suspicion
- town fear
- faction reaction
- world pressure
- observer trust loss
- escalation chance

Relationship State System

Ghost exposes human-readable relationship states.

rel = ghost.get_relationship("A", "B")

rel["state"]        # "hostile", "neutral", "friendly"
rel["transition"]   # ("neutral", "hostile")
rel["trigger"]      # {"event": "relationship_broken"}
rel["diagnostics"]  # measurable explanation of the latest change
rel["maturity"]     # relationship stability over repeated interactions
rel["volatility"]   # general event sensitivity

Relationship state gives external systems a clean way to respond to emotional history without needing to interpret raw internal values.

Relationship diagnostics give external systems a clean way to understand how strongly the relationship changed and why.

Event Triggers

State transitions generate structured events.

Examples include:

- relationship_broken
- deescalation
- forgiveness
- state_shift

These can be used by external systems for:

- dialogue changes
- combat behavior
- faction reactions
- narrative events
- shopkeeper behavior
- guard escalation
- reputation consequences

Ghost does not perform those actions directly.

It exposes the state, trigger information, and diagnostics so another system can decide what to do.

Oscillation Behavior

Ghost is specifically designed to handle oscillating interaction patterns.

Example:

sequence = ["insult", "insult", "help", "help"]

Produces:

- escalation into hostility
- resistance to recovery
- gradual de-escalation, not instant reset

This behavior cannot be replicated by:

- additive systems, such as "trust += delta"
- low-pass filters, such as exponential smoothing

Ghost introduces stateful emotional inertia, not just value smoothing.

Packaged Demos

Ghost includes six small demos that each prove a different layer of the engine.

Proof Demo

The proof demo compares Ghost’s emotional inertia model against a standard linear baseline.

Run:

ghost-demo

Or as a module:

python -m ghost.examples.relationship_proof_demo

This demonstrates that Ghost retains emotional history after betrayal while a simple baseline rapidly normalizes.

Example output:

Step | Event     | Baseline  | Ghost     | State
----------------------------------------------------------------------
5    | betrayal  | -0.209    | -0.750    | hostile
6    | help      | -0.107    | -0.680    | hostile

Key result:

Ghost retained stronger negative state.
Baseline normalized more quickly.
✔ Emotional inertia confirmed.

NPC API Mapping Demo

The NPC demo shows how a small external behavior layer can consume Ghost state over a deterministic 10-tick sequence.

Run:

ghost-npc-demo

Or as a module:

python -m ghost.examples.simple_npc_demo

This demo uses:

engine.step(...)
engine.apply_event(a, b, event)
engine.tick()
engine.get_relationship(a, b)

It demonstrates threat state and relationship state working together.

Example output:

Tick | Threat | Trust  | Rel      | Trig    | NPC
---------------------------------------------------
0    |   0.00 |  0.054 | neutral  | -       | idle
1    |   0.00 |  0.204 | friendly | forgive | help
5    |   1.00 | -0.768 | hostile  | broken  | refuse
9    |   0.93 | -0.510 | neutral  | deesc   | warn

The NPC behavior is not chosen by Ghost directly.

Ghost exposes state. The NPC code decides how to respond.

Playable Shopkeeper Mini Game

The shopkeeper demo is a playable terminal mini game.

Run:

ghost-shopkeeper-demo

Or as a module:

python -m ghost.examples.shopkeeper_mini_game

The shopkeeper demo uses only the public GhostEngine API and shows how trust, emotional pressure, relationship state, prices, quest availability, and dialogue can change based on player actions.

Example status output:

Trust:      -0.401
State:      neutral
Pressure:   damaged, but not broken
Price:      1.50x
Quest:      unavailable

Then after further damage:

Trust:      -0.570
State:      hostile
Pressure:   broken
Price:      2.00x
Quest:      unavailable
Trigger:    relationship_broken

The mini game demonstrates that behavior can begin changing before a relationship fully breaks.

Ghost exposes the emotional state. The game logic decides how to respond.

Ghost Math Demo

The math demo explains the small mathematical contract behind Ghost.

Run:

ghost-math-demo

Or as a module:

python -m ghost.examples.ghost_math_helper

This demo walks through Ghost relationship math step by step:

- clamp behavior
- relationship reservoirs
- trust calculation
- tick decay
- state thresholds
- game behavior mapping
- balanced personality math
- resentful personality math
- maturity behavior
- volatility behavior
- positive and negative volatility
- short-history versus long-history betrayal outcomes
- personality-specific relationship outcomes

Example output:

trust = positive_reservoir - negative_reservoir

positive_next = 0.024 + 0.12 * 0.60
positive_next = 0.096

negative_next = 0.000 + 0.70 * 1.40
negative_next = 0.980

trust = 0.096 - 0.980
trust = -0.884
state = hostile

price = 2.00x

base_cost = 10
final_cost = 10 * 2.00
final_cost = 20

v1.4.0 also demonstrates maturity and split volatility:

maturity_modifier = 1.0 - maturity

positive_effective_gain =
    base_gain * volatility * positive_volatility * maturity_modifier

negative_effective_gain =
    base_gain * volatility * negative_volatility * maturity_modifier

Short relationship: 2x help, then betrayal
after betrayal: trust = -0.554 state = hostile maturity = 0.03

Long relationship: 20x help, then betrayal
after betrayal: trust = 0.940 state = friendly maturity = 0.21

This demo is intended as a developer-facing reference for understanding how Ghost turns deterministic relationship math into gameplay-readable output.

Ghost still does not choose actions.

Ghost exposes state. The game logic decides what to do with that state.

Ghost Diagnostics Demo

The diagnostics demo explains the measurable diagnostic packet behind relationship changes.

Run:

ghost-diagnostics-demo

Or as a module:

python -m ghost.examples.relationship_diagnostics_demo

This demo shows how Ghost exposes what changed, how hard it changed, and why.

It demonstrates:

- short relationship break diagnostics
- long relationship betrayal resistance
- volatile personality diagnostics
- strained neutral / near-break diagnostics
- trust before and after
- trust delta
- severity
- direction
- pressure
- effective gain
- maturity
- volatility
- split positive and negative volatility

Example output:

Diagnostics:
event:                betrayal
channel:              neg
from_state:           friendly
to_state:             hostile
trust_before:         0.201
trust_after:          -0.554
delta:                -0.755
abs_delta:            0.755
direction:            negative
severity:             0.755
pressure:             relationship_broken
near_break:           False
base_amount:          0.700
effective_gain:       0.755
maturity:             0.020
maturity_modifier:    0.980
volatility:           1.00
positive_volatility:  1.00
negative_volatility:  1.00

The diagnostics demo is intended as a developer-facing inspection tool.

It shows how Ghost turns relationship changes into measurable data that external systems can use.

Ghost still does not choose actions.

Ghost exposes diagnostics. The game logic decides what to do with them.

Ghost Social Propagation Demo

v1.6.0 adds a social propagation demo.

Run:

ghost-social-demo

Or as a module:

python -m ghost.examples.social_propagation_demo

This demo shows how a direct relationship event can create bounded secondary effects on observers and world-level pressure.

It demonstrates:

- direct relationship damage
- observer reactions
- weighted propagation
- relationship_broken social heat
- near_break social heat
- world-effect packets
- JSON-safe propagation output
- deterministic social consequence state

Example output:

Direct event:
  source:       player
  target:       shopkeeper
  event:        betrayal
  trust:        -0.770
  state:        hostile
  pressure:     relationship_broken
  heat:         1.000
  near_break:   False

Propagated effects:
  guard   delta=-0.200 trust=-0.200 state=neutral pressure=negative_shift
  elder   delta=-0.140 trust=-0.140 state=neutral pressure=minor_negative_shift
  rival   delta=-0.050 trust=-0.050 state=neutral pressure=minor_negative_shift

World effects:
  pressure_delta:        +0.200
  fear_delta:            +0.080
  resentment_delta:      +0.080
  order_delta:           -0.040
  guard_suspicion_delta: +0.350

The demo also shows strained neutral:

target state:     neutral
target trust:     -0.538
pressure:         near_break
heat:             0.855
near_break:       True

The social propagation demo is intended to show how Ghost can support external systems such as guard suspicion, town reputation, faction pressure, rumor spread, and campaign consequences.

Ghost still does not choose actions.

Ghost exposes state. The game decides what happens next.

Relationship Runtime Summary

Ghost relationships provide:

- dual-channel emotional memory
- resistance and saturation modeling
- time-based decay
- public tick packets
- per-relationship personality tuning
- relationship maturity
- general volatility
- split positive and negative volatility
- state interpretation
- transition tracking
- trigger events
- relationship diagnostics
- near-break pressure
- trust delta tracking
- severity tracking
- public relationship inspection
- direct event application
- social propagation
- observer weighting
- social heat
- world-effect packets

Ghost remains a deterministic state engine.

It tracks and exposes state.

External systems decide how to use that state.

Core Design Principles

- deterministic, persistent state core
- explicit state transitions via "step()"
- direct relationship events via "apply_event()"
- time advancement via "tick()"
- social propagation via "propagate_social_event()"
- no hidden execution or side effects
- public API remains dict-based and serialization-safe
- internal typed representations may exist but never leak
- designed to be expanded around a stable core

Ghost Does NOT

Ghost does not:

- choose actions
- generate dialogue
- interpret semantics
- replace an LLM
- act as an autonomous agent
- store memory implicitly
- decide what a character should do

These responsibilities belong to external systems that consume Ghost’s state.

Ghost provides the persistent state those systems can use.

Stability & Guarantees

Ghost maintains deterministic runtime guarantees across public engine state.

The engine guarantees:

- deterministic runtime behavior, meaning same inputs produce same outputs
- explicit, bounded state mutation per step
- actor state updates across interactions
- actor-level threat accumulation tracking
- pairwise relationship mutation with symmetric consistency
- bounded cascade propagation across interaction networks
- bounded social propagation through observer packets
- deterministic nonlinear modulation of global system tension
- passive decay behavior during idle cycles
- fully JSON-safe public state and immutable snapshots

These guarantees hold under repeated execution, long-run simulation, and adversarial input streams.

Architectural Expansion

Recent releases introduced a multi-agent interaction model on top of Ghost’s deterministic state core.

Agent State Mutation

Agents maintain evolving internal state, such as mood, tension, and last intent, and react deterministically to interaction signals.

Relationship Graph

Pairwise relationships evolve through explicit interaction deltas, supporting long-term system memory without hidden state.

Bounded Cascade Propagation

Signals propagate deterministically through local interaction networks with strict bounds to prevent runaway behavior.

Social Propagation

Direct relationship events can now propagate bounded secondary effects to observers.

This allows a game layer to model rumors, guard suspicion, town pressure, and faction reaction without Ghost deciding behavior directly.

Global System Tension

The engine tracks shared system pressure across interactions using deterministic nonlinear modulation.

Actor Threat Memory

Agents maintain explicit per-actor threat accumulation history for structured introspection.

Idle-State Decay Dynamics

Bounded passive decay improves long-run stability and prevents runaway system pressure.

Testing Philosophy

Ghost uses property-based testing and invariant validation rather than relying solely on example-driven tests.

Core validation includes:

- determinism verification
- bounded-state guarantees
- serialization safety validation
- public state safety checks
- long-run stability checks
- relationship diagnostics checks
- social propagation checks
- tick packet checks

This ensures the engine remains correct and predictable as new systems are layered on top.

Project Structure

ghost/                    core engine modules
ghost/examples/            packaged demos
tests/                    invariant and runtime tests
pyproject.toml             build configuration
README.md                  project documentation

Demos are intentionally minimal and act as experimental sandboxes.

They are not representative of Ghost’s final scope.

Status

Ghost Engine remains in early development.

As of v1.6.0:

- the deterministic interaction core is stable
- the public relationship API is available
- relationship maturity and volatility are available through public relationship state
- relationship diagnostics are available through public relationship state
- near-break pressure is available through diagnostics
- social propagation is available through public API
- observer weighting is available through social propagation
- social heat is exposed through propagation packets
- world-effect packets are exposed through propagation packets
- "tick()" returns a public readable packet
- the proof demo is packaged and runnable
- the NPC API mapping demo is packaged and runnable
- the playable shopkeeper mini game is packaged and runnable
- the Ghost math demo is packaged and runnable
- the Ghost diagnostics demo is packaged and runnable
- the Ghost social propagation demo is packaged and runnable

This project is intended as a foundation for experimentation, research, and future system design rather than a finished product.

Release History

v1.6.0

- Added social propagation through "ghost.propagate_social_event(...)"
- Added direct event plus observer-effect propagation packets
- Added weighted observers for different reaction strengths
- Added bounded social heat calculation
- Added social heat pressure ordering:
  - relationship_broken
  - near_break
  - major_negative_shift
  - state_shift
  - normal shifts
- Added "near_break" pressure for strained neutral relationships
- Added "near_break" boolean to diagnostics
- Added world-effect packets for social propagation
- Added pressure, fear, resentment, order, and guard suspicion deltas to propagation output
- Added public readable tick packets from "ghost.tick()"
- Added "ghost-social-demo" CLI entry point
- Added "ghost.examples.social_propagation_demo"
- Added social propagation tests
- Added tick packet tests
- Confirmed full regression suite passes with v1.6.0 behavior

v1.5.0

- Added relationship diagnostics output
- Added diagnostic packets to public relationship state
- Added trust before and trust after tracking
- Added trust delta and absolute delta tracking
- Added direction labels for positive, negative, and stable changes
- Added severity calculation for relationship changes
- Added pressure labels for relationship transitions and major shifts
- Added effective gain reporting after maturity and volatility modifiers
- Added maturity and volatility values to diagnostics
- Added diagnostics for relationship tick decay
- Added JSON-safe diagnostics validation
- Added "ghost-diagnostics-demo" CLI entry point
- Added "ghost.examples.relationship_diagnostics_demo"
- Added tests for relationship diagnostics behavior
- Added tests for diagnostics through "get_relationship()"
- Added tests for diagnostics JSON safety

v1.4.0

- Added relationship maturity
- Added relationship volatility
- Added split positive and negative volatility
- Added maturity gain and maturity cap fields
- Exposed maturity through public relationship output
- Exposed volatility through public relationship output
- Exposed positive and negative volatility through public relationship output
- Updated personality presets with maturity and volatility behavior
- Expanded "ghost-math-demo" with maturity and volatility examples
- Demonstrated short-history versus long-history betrayal outcomes
- Demonstrated personality-specific relationship outcomes
- Added tests for relationship maturity and volatility behavior

v1.3.0

- Added "ghost-math-demo" CLI entry point
- Added "ghost.examples.ghost_math_helper"
- Added developer-facing math demo for Ghost relationship mechanics
- Documented clamp behavior, relationship reservoirs, trust calculation, tick decay, and state thresholds
- Added balanced personality math walkthrough
- Added resentful personality math walkthrough
- Demonstrated how relationship state maps into gameplay behavior such as price changes and NPC behavior
- Updated the public demo suite:
  - "ghost-demo"
  - "ghost-npc-demo"
  - "ghost-shopkeeper-demo"
  - "ghost-math-demo"

v1.2.1

- Cleaned packaged demo command structure
- Removed redundant "ghost-relationship-demo" command from the public demo set
- Restored "ghost-demo" as the relationship proof / baseline comparison demo
- Updated "ghost-npc-demo" into a deterministic 10-tick Ghost API mapping demo
- Improved NPC demo terminal formatting for phone-safe output
- Shortened NPC behavior labels and dialogue to reduce terminal wrapping
- Removed unused proof demo variable cleanup
- Clarified the final public demo suite:
  - "ghost-demo"
  - "ghost-npc-demo"
  - "ghost-shopkeeper-demo"

v1.2.0

- Added playable terminal shopkeeper mini game
- Added "ghost-shopkeeper-demo" CLI entry point
- Added playable terminal demo behavior for shopkeeper interactions
- Demonstrated trust, emotional pressure, relationship state, pricing, quest availability, and dialogue changes through public API usage
- Added resentful NPC personality setup to the shopkeeper demo
- Added wait/tick explanation to demonstrate time-based relationship decay
- Added emotional pressure display such as damaged, but not broken and broken
- Improved command input support for typed commands such as buy bread, show status, and wait

v1.1.1

- Fixed missing public "GhostEngine.apply_event()" wrapper
- Fixed missing public "GhostEngine.tick()" wrapper
- Fixed missing public "GhostEngine.get_relationship()" wrapper
- Added missing relationship graph support for public event application
- Confirmed public relationship API returns trust, state, transition, and trigger output directly from "GhostEngine"

v1.1.0

- Added public relationship runtime API
- Added "ghost.apply_event(a, b, event)"
- Added "ghost.tick()"
- Added "ghost.get_relationship(a, b)"
- Exposed relationship trust through public API
- Exposed relationship state through public API
- Exposed relationship transitions through public API
- Exposed structured relationship triggers through public API
- Expanded Ghost from proof-demo behavior into reusable runtime behavior
- Made emotional inertia directly usable by external NPC, dialogue, faction, and simulation systems

v1.0.1

- Finalized proof demo packaging
- Added "ghost-demo" CLI entry point
- Added proper demo "main()" entry point
- Packaged proof demo inside "ghost.examples"
- Made proof demo runnable without cloning the repository

v1.0.0

- Promoted Ghost from basic state experiments into an emotional inertia runtime
- Introduced dual-channel emotional memory model with positive and negative reservoirs
- Replaced single-value trust updates with persistent emotional accumulation using "pos - neg"
- Added resistance mechanics where negative history reduces the effectiveness of positive events
- Added saturation mechanics with diminishing returns on repeated positive interactions
- Implemented time-based relationship decay via "tick()"
- Added per-relationship parameter system for gain and decay tuning
- Introduced personality presets: balanced, forgiving, resentful, volatile
- Added relationship state classification from hostile to loyal spectrum
- Implemented transition detection between relationship states
- Added structured trigger system with "relationship_broken", "deescalation", "forgiveness", and "state_shift"
- Expanded public API to expose state, transitions, and triggers
- Established emotional inertia model as a first-class runtime system

v0.2.2

- Fixed public state serialization issue in relationship subsystem
- Replaced set-based storage with JSON-safe structures
- Strengthened invariant coverage across runtime state

v0.2.1

- Added actor-level threat accumulation tracking
- Introduced deterministic nonlinear system modulation
- Implemented passive idle-cycle decay
- Added immutable JSON-safe snapshots

v0.2.0

- Introduced multi-agent state mutation
- Added relationship mutation logic
- Implemented bounded cascade propagation
- Achieved deterministic runtime guarantees

v0.1.x

- Foundational architecture releases
v1.7.0
Added deterministic NPC temperament interpretation layer
Added ghost-temperament-demo CLI entry point
Added ghost.examples.temperament_demo
Added temperament profiles such as calm, anxious, confident, suspicious, resentful, loyal, and volatile
Added temperament interpretation metadata for fear, suspicion, anger, confidence, loyalty, relief, stance, emotional_read, and intensity
Added stricter public numeric validation for NaN, infinity, invalid relationship intensity, invalid social heat, and invalid temperament values
Added stronger ID validation and normalization behavior
Hardened GhostEngine.step() so bad public input does not mutate public state before validation
Added public packet schema tests
Added adversarial public-number tests
Added ironclad boundary tests
Added mathematical invariant tests
Added snapshot metadata tests
Added scale-safety tests
Added test-suite quality checks
Confirmed full regression suite passes with 248 tests
