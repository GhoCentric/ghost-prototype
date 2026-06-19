# ghocentric-ghost-engine

A lightweight, deterministic state engine for NPC relationships, persistent interactive state, emotional inertia, social propagation, temperament interpretation, and gameplay-readable diagnostics.

Ghost is not a language model.

Ghost is not an autonomous decision-maker.

Ghost does not generate dialogue, choose actions, or replace game logic.

Ghost exposes structured state. Your game, simulation, dialogue system, faction system, or optional AI layer decides what to do with that state.

## Installation

    pip install ghocentric-ghost-engine

## What Ghost Is

Ghost is a deterministic Python state engine designed to sit underneath higher-level interactive systems such as:

- NPC behavior systems
- dialogue engines
- shopkeeper and guard logic
- faction reputation systems
- town or kingdom simulation systems
- social consequence systems
- LLM-driven character layers
- game AI prototypes

Ghost tracks persistent state over time and exposes that state through clean public dictionaries.

The project is focused on architecture, deterministic behavior, serialization safety, and runtime correctness.

## Demo Commands

After installation, Ghost includes seven runnable demo commands:

    ghost-demo
    ghost-npc-demo
    ghost-shopkeeper-demo
    ghost-math-demo
    ghost-diagnostics-demo
    ghost-social-demo
    ghost-temperament-demo

Each demo proves a different layer of the engine:

- ghost-demo compares Ghost emotional inertia against a simple linear baseline
- ghost-npc-demo shows Ghost state mapped into external NPC behavior
- ghost-shopkeeper-demo runs a playable terminal shopkeeper mini game
- ghost-math-demo explains Ghost relationship math and gameplay mapping
- ghost-diagnostics-demo shows measurable relationship diagnostics
- ghost-social-demo demonstrates observer effects, social heat, and world-effect packets
- ghost-temperament-demo shows how different NPC temperaments interpret the same state differently

## Basic Usage

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

Ghost mutates state only through explicit calls such as step(), apply_event(), tick(), and propagate_social_event().

All public-facing state is dictionary-based and serialization-safe.

## Public Relationship API

Ghost includes a direct public API for working with relationships as a reusable runtime system.

    from ghost.engine import GhostEngine

    ghost = GhostEngine()

    ghost.apply_event("player", "shopkeeper", "help")
    ghost.apply_event("player", "shopkeeper", "insult")
    ghost.apply_event("player", "shopkeeper", "betrayal")

    relationship = ghost.get_relationship("player", "shopkeeper")

    print(relationship)

Example relationship output:

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

## Relationship Model

Ghost relationships use a dual-channel memory model:

    trust = positive_reservoir - negative_reservoir

Each relationship tracks:

- positive reservoir
- negative reservoir
- trust
- state
- transition
- trigger
- diagnostics
- maturity
- volatility
- positive volatility
- negative volatility

This allows relationship damage to persist independently from recovery.

A single helpful action after betrayal does not instantly erase the betrayal.

## Emotional Inertia

Ghost is designed to handle oscillating interaction patterns.

Example:

    insult -> help -> insult -> help

A simple linear system may average this out quickly.

Ghost preserves emotional direction through persistent positive and negative reservoirs.

This means repeated harm, betrayal, or hostility can continue to affect the relationship even after later positive actions.

## Relationship States

Ghost exposes readable relationship states:

    relationship["state"]        # hostile, neutral, or friendly
    relationship["transition"]   # example: ("neutral", "hostile")
    relationship["trigger"]      # example: {"event": "relationship_broken"}
    relationship["diagnostics"]  # measurable explanation of the latest change

Ghost can generate structured trigger events such as:

- relationship_broken
- deescalation
- forgiveness
- state_shift

Ghost does not perform game actions directly.

It exposes state so another system can respond.

## Diagnostics

Relationship diagnostics explain what changed, how strongly it changed, and why.

Diagnostics may include:

- event
- channel
- base amount
- effective gain
- trust before
- trust after
- delta
- absolute delta
- severity
- direction
- pressure
- near-break status
- maturity
- volatility
- transition
- trigger

This makes Ghost useful for debugging and for external systems such as dialogue, guard suspicion, faction reputation, quest access, pricing, and social consequence logic.

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

Ghost exposes the measurable state change.

The game decides what happens next.

## Relationship Maturity and Volatility

Ghost relationships support maturity and volatility.

Maturity represents relationship stability over repeated interactions.

Volatility controls how strongly new events affect a relationship.

Ghost tracks:

- maturity
- volatility
- positive_volatility
- negative_volatility
- maturity_gain
- maturity_cap

Maturity does not erase history.

Maturity reduces future emotional swing.

This means the same betrayal can produce different outcomes depending on relationship history.

A short relationship can break immediately after betrayal.

A long relationship with repeated positive history may absorb one betrayal without instantly becoming hostile.

Positive and negative volatility can also differ.

This allows personalities to behave differently under the same event sequence.

## Personality Presets

Relationships can have different emotional profiles.

    ghost.relationships.set_personality("A", "B", "resentful")

Available relationship presets include:

- balanced
- forgiving
- resentful
- volatile

Each preset can affect:

- gain sensitivity
- decay speed
- recovery behavior
- maturity behavior
- positive volatility
- negative volatility

The same event sequence can produce different emotional outcomes depending on the relationship profile.

## Near-Break Pressure

Neutral does not always mean calm.

Ghost can detect a strained neutral state through near_break.

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

This lets external systems react before a relationship fully becomes hostile.

Near-break pressure can support:

- warning dialogue
- higher prices
- quest denial
- access restriction
- guard suspicion
- faction tension
- town pressure

## Social Propagation

Ghost can propagate a direct relationship event to observers.

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

Social propagation can expose:

- direct relationship damage
- observer trust changes
- social heat
- pressure labels
- weighted observer reactions
- world-effect packets

Example propagation output:

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
            }
        ],
        "world_effects": {
            "pressure_delta": 0.20,
            "fear_delta": 0.08,
            "resentment_delta": 0.08,
            "order_delta": -0.04,
            "guard_suspicion_delta": 0.35,
        },
    }

This can support systems such as:

- rumors
- guard suspicion
- faction pressure
- town reputation
- public betrayal consequences
- social escalation

Ghost still does not decide what observers do.

It exposes the state packet.

## Social Heat

Social heat measures how much a direct relationship event should matter to observers or world systems.

The current pressure ordering is:

    relationship_broken > near_break > major_negative_shift > state_shift > normal shifts

This means a full relationship break creates more social heat than a strained neutral state.

Social heat is exposed in propagation packets as:

    packet["heat"]

External systems can use heat to scale:

- rumor strength
- guard suspicion
- town fear
- faction reaction
- world pressure
- observer trust loss
- escalation chance

## Temperament Layer

v1.7.0 adds deterministic NPC temperament interpretation.

The same relationship state can be interpreted differently by different NPC profiles.

Example temperament profiles include:

- calm
- anxious
- confident
- suspicious
- resentful
- loyal
- volatile

Temperament output can include:

- emotional_read
- stance
- fear
- suspicion
- anger
- confidence
- loyalty
- relief
- intensity

The temperament layer does not choose actions.

It gives external systems structured interpretation metadata.

Example external mapping:

- anxious_guard -> avoid or call help
- confident_guard -> confront
- suspicious_guard -> restrict access
- resentful_guard -> escalate
- loyal_guard -> hesitate
- volatile_guard -> overreact

Ghost exposes state.

Your game decides the behavior.

## Packaged Demos

## ghost-demo

The proof demo compares Ghost emotional inertia against a standard linear baseline.

Run:

    ghost-demo

Or:

    python -m ghost.examples.relationship_proof_demo

This demonstrates that Ghost retains emotional history after betrayal while a simple baseline rapidly normalizes.

## ghost-npc-demo

The NPC demo shows how a small external behavior layer can consume Ghost state over a deterministic 10-tick sequence.

Run:

    ghost-npc-demo

Or:

    python -m ghost.examples.simple_npc_demo

This demo uses:

- engine.step(...)
- engine.apply_event(a, b, event)
- engine.tick()
- engine.get_relationship(a, b)

The NPC behavior is not chosen by Ghost directly.

Ghost exposes state. The NPC code decides how to respond.

## ghost-shopkeeper-demo

The shopkeeper demo is a playable terminal mini game.

Run:

    ghost-shopkeeper-demo

Or:

    python -m ghost.examples.shopkeeper_mini_game

The shopkeeper demo uses only the public GhostEngine API and shows how trust, pressure, relationship state, prices, quest availability, and dialogue can change based on player actions.

## ghost-math-demo

The math demo explains the small mathematical contract behind Ghost.

Run:

    ghost-math-demo

Or:

    python -m ghost.examples.ghost_math_helper

This demo walks through:

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

## ghost-diagnostics-demo

The diagnostics demo explains the measurable diagnostic packet behind relationship changes.

Run:

    ghost-diagnostics-demo

Or:

    python -m ghost.examples.relationship_diagnostics_demo

This demo shows what changed, how hard it changed, and why.

## ghost-social-demo

The social propagation demo shows how a direct relationship event can create bounded secondary effects on observers and world-level pressure.

Run:

    ghost-social-demo

Or:

    python -m ghost.examples.social_propagation_demo

This demo shows:

- direct relationship damage
- observer reactions
- weighted propagation
- relationship_broken social heat
- near_break social heat
- world-effect packets
- JSON-safe propagation output
- deterministic social consequence state

## ghost-temperament-demo

The temperament demo shows how the same relationship state can be interpreted through different NPC temperament profiles.

Run:

    ghost-temperament-demo

Or:

    python -m ghost.examples.temperament_demo

This demo shows that Ghost does not pick an action, write dialogue, or decide combat.

Ghost exposes deterministic interpretation metadata.

## Validation

Current v1.7.0 validation:

    248 tests passing

The test suite includes:

- deterministic replay tests
- public API tests
- packet schema tests
- public numeric boundary tests
- ID validation tests
- snapshot isolation tests
- JSON-safety tests
- relationship invariant tests
- social propagation tests
- temperament tests
- scale-safety tests
- mathematical invariant tests
- property-based fuzz tests
- test-suite quality checks

## Design Guarantees

Ghost is designed around these principles:

- deterministic runtime behavior
- explicit state mutation
- dictionary-based public state
- serialization-safe snapshots
- bounded state changes
- no hidden LLM calls
- no autonomous action selection
- no dialogue generation
- no internal typed object leakage through public state

Ghost is a state engine.

External systems decide behavior.

## Ghost Does Not

Ghost does not:

- choose actions
- generate dialogue
- interpret natural language
- replace an LLM
- act as an autonomous agent
- store memory implicitly
- decide what a character should do

These responsibilities belong to external systems that consume Ghost state.

## Project Structure

    ghost/              core engine modules
    ghost/examples/     packaged CLI demos
    tests/              runtime, property, regression, and invariant tests
    pyproject.toml      package configuration
    README.md           project documentation

## Status

Ghost Engine remains in early development.

As of v1.7.0:

- the deterministic interaction core is stable
- the public relationship API is available
- relationship maturity and volatility are available
- relationship diagnostics are available
- near-break pressure is available
- social propagation is available
- observer weighting is available
- social heat is available
- world-effect packets are available
- tick() returns a public readable packet
- temperament interpretation metadata is available
- seven CLI demos are packaged and runnable
- the full test suite passes with 248 tests

This project is intended as a foundation for experimentation, research, and future system design rather than a finished product.

## Release History

## v1.7.0

- Added deterministic NPC temperament interpretation layer
- Added ghost-temperament-demo CLI entry point
- Added ghost.examples.temperament_demo
- Added temperament profiles such as calm, anxious, confident, suspicious, resentful, loyal, and volatile
- Added temperament interpretation metadata for fear, suspicion, anger, confidence, loyalty, relief, stance, emotional_read, and intensity
- Added stricter public numeric validation for NaN, infinity, invalid relationship intensity, invalid social heat, and invalid temperament values
- Added stronger ID validation and normalization behavior
- Hardened GhostEngine.step() so bad public input does not mutate public state before validation
- Added public packet schema tests
- Added adversarial public-number tests
- Added ironclad boundary tests
- Added mathematical invariant tests
- Added snapshot metadata tests
- Added scale-safety tests
- Added test-suite quality checks
- Confirmed full regression suite passes with 248 tests

## v1.6.0

- Added social propagation through ghost.propagate_social_event(...)
- Added direct event plus observer-effect propagation packets
- Added weighted observers for different reaction strengths
- Added bounded social heat calculation
- Added social heat pressure ordering
- Added near_break pressure for strained neutral relationships
- Added near_break boolean to diagnostics
- Added world-effect packets for social propagation
- Added pressure, fear, resentment, order, and guard suspicion deltas to propagation output
- Added public readable tick packets from ghost.tick()
- Added ghost-social-demo CLI entry point
- Added ghost.examples.social_propagation_demo
- Added social propagation tests
- Added tick packet tests
- Confirmed full regression suite passes with v1.6.0 behavior

## v1.5.0

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
- Added ghost-diagnostics-demo CLI entry point
- Added ghost.examples.relationship_diagnostics_demo
- Added tests for relationship diagnostics behavior
- Added tests for diagnostics through get_relationship()
- Added tests for diagnostics JSON safety

## v1.4.0

- Added relationship maturity
- Added relationship volatility
- Added split positive and negative volatility
- Added maturity gain and maturity cap fields
- Exposed maturity through public relationship output
- Exposed volatility through public relationship output
- Exposed positive and negative volatility through public relationship output
- Updated personality presets with maturity and volatility behavior
- Expanded ghost-math-demo with maturity and volatility examples
- Demonstrated short-history versus long-history betrayal outcomes
- Demonstrated personality-specific relationship outcomes
- Added tests for relationship maturity and volatility behavior

## v1.3.0

- Added ghost-math-demo CLI entry point
- Added ghost.examples.ghost_math_helper
- Added developer-facing math demo for Ghost relationship mechanics
- Documented clamp behavior, relationship reservoirs, trust calculation, tick decay, and state thresholds
- Added balanced personality math walkthrough
- Added resentful personality math walkthrough
- Demonstrated how relationship state maps into gameplay behavior such as price changes and NPC behavior
- Updated the public demo suite

## v1.2.1

- Cleaned packaged demo command structure
- Removed redundant ghost-relationship-demo command from the public demo set
- Restored ghost-demo as the relationship proof and baseline comparison demo
- Updated ghost-npc-demo into a deterministic 10-tick Ghost API mapping demo
- Improved NPC demo terminal formatting for phone-safe output
- Shortened NPC behavior labels and dialogue to reduce terminal wrapping
- Removed unused proof demo variable cleanup

## v1.2.0

- Added playable terminal shopkeeper mini game
- Added ghost-shopkeeper-demo CLI entry point
- Added playable terminal demo behavior for shopkeeper interactions
- Demonstrated trust, emotional pressure, relationship state, pricing, quest availability, and dialogue changes through public API usage
- Added resentful NPC personality setup to the shopkeeper demo
- Added wait and tick explanation to demonstrate time-based relationship decay
- Added emotional pressure display such as damaged but not broken and broken
- Improved command input support for typed commands such as buy bread, show status, and wait

## v1.1.1

- Fixed missing public GhostEngine.apply_event() wrapper
- Fixed missing public GhostEngine.tick() wrapper
- Fixed missing public GhostEngine.get_relationship() wrapper
- Added missing relationship graph support for public event application
- Confirmed public relationship API returns trust, state, transition, and trigger output directly from GhostEngine

## v1.1.0

- Added public relationship runtime API
- Added ghost.apply_event(a, b, event)
- Added ghost.tick()
- Added ghost.get_relationship(a, b)
- Exposed relationship trust through public API
- Exposed relationship state through public API
- Exposed relationship transitions through public API
- Exposed structured relationship triggers through public API
- Expanded Ghost from proof-demo behavior into reusable runtime behavior
- Made emotional inertia directly usable by external NPC, dialogue, faction, and simulation systems

## v1.0.1

- Finalized proof demo packaging
- Added ghost-demo CLI entry point
- Added proper demo main() entry point
- Packaged proof demo inside ghost.examples
- Made proof demo runnable without cloning the repository

## v1.0.0

- Promoted Ghost from basic state experiments into an emotional inertia runtime
- Introduced dual-channel emotional memory model with positive and negative reservoirs
- Replaced single-value trust updates with persistent emotional accumulation using pos - neg
- Added resistance mechanics where negative history reduces the effectiveness of positive events
- Added saturation mechanics with diminishing returns on repeated positive interactions
- Implemented time-based relationship decay via tick()
- Added per-relationship parameter system for gain and decay tuning
- Introduced personality presets: balanced, forgiving, resentful, volatile
- Added relationship state classification
- Implemented transition detection between relationship states
- Added structured trigger system with relationship_broken, deescalation, forgiveness, and state_shift
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
