# ghost-engine  
Internal state reasoning engine (proof-of-architecture)

---

## Minimal Working Proof

This repository contains a runnable, deterministic Python state engine with no machine learning dependencies.

If you want to skip conceptual framing and inspect concrete behavior first, start here:

- **State representation and persistence**  
  `ghost/state/`

- **Deterministic routing and strategy selection**  
  `ghost/routing/`

- **Meta-regulation, stability controls, and internal monitoring**  
  `ghost/runtime/`  
  `ghost/probes/`

- **Externalized memory and recall mechanics**  
  `ghost/memory/`

These modules collectively demonstrate that Ghost maintains internal state coherence, enforces deterministic routing rules, and survives invalid or unknown commands **before** any language model interaction occurs.

The language model (when enabled) is treated strictly as a black-box language surface. All state evolution, constraint enforcement, and routing decisions occur independently of probabilistic text generation.

---

## Thesis

Ghost is an internal state reasoning engine designed to generate consistent, structured advisory outputs without hallucination or false agency.

Ghost is not an autonomous agent, not a general intelligence, and not a replacement for large language models. It is a proof-of-architecture demonstrating how symbolic state, deterministic control, and constrained probabilistic language generation can interact to produce coherent, persistent behavior that cannot be achieved through prompt engineering alone.

---

## Architectural Overview

Ghost uses a deterministic internal-state kernel with an optional probabilistic language surface.

Ghost is a hybrid cognitive architecture in which probabilistic language generation is explicitly subordinated to symbolic state, constraint enforcement, and deterministic routing. The language model functions strictly as a language surface, not as the cognitive core.

See the full architecture breakdown here:

- `docs/architecture.md`

## Core Properties

- Cost-efficient, token-disciplined architecture with high signal per token  
- Persistent symbolic state kernel from which personality-like behavior emerges  
- Deterministic, low-variance output prioritizing stability over novelty  
- Externalized memory, belief, and contradiction tracking  
- Explicit hallucination reduction via constraint grounding and state enforcement  
- Full observability of internal cognitive variables  
- Constraint-first design philosophy  
- Intentionally non-agentic (no autonomous goals, actions, or self-direction)

This design prevents stylistic drift, minimizes prompt-level manipulation, and anchors output to persistent internal state rather than transient user phrasing.

---

## 🔬 Structural Cascade Validation

Ghost was evaluated under controlled cascade experiments designed to isolate structural causality from stochastic effects.

### Setup

We ran multi-node cascade simulations (10–20 agents) under identical conditions:

- identical topology  
- identical stimulus  
- identical parameters  
- zero randomness  

Two models were compared:

- **Ghost cascade model** (clamped, memory-coupled)  
- **Control diffusion model** (unconstrained baseline)

### Results

Under identical conditions:

- Ghost produced stable propagation with contained collapse  
- Control model collapsed rapidly and globally  

We then ran identical Ghost simulations twice.

👉 Collapse timelines matched **exactly across runs**

This demonstrates:

- deterministic long-horizon cascade behavior  
- ablation-backed structural causality  
- non-stochastic containment dynamics  

### Reproduce

```bash
cd ghost-engine/cascade_experiments
python compare_runs.py
```

---

## Development Constraints

Ghost was built locally under extreme constraints:

- Mobile-only development environment  
- No formal computer science training  
- No external frameworks  
- Entire system constructed incrementally over approximately two years  

Large language models were used only for syntax assistance and surface-level language handling. All architectural decisions, state logic, and control mechanisms were manually designed and implemented.

---

## State and Stability Model

Ghost maintains a measurable internal state across interactions, including:

- Emotional vectors  
- Belief tension metrics  
- Contradiction tracking  
- Meta-regulatory stability controls  

These variables directly influence routing, response shaping, and output constraints. State persists across calls, enabling continuity without conversational memory tricks or prompt scaffolding.

The system is optimized for consistency, reliability, and coherence rather than novelty or performative intelligence.

---

## Hallucination Resistance

### What “Hallucination” Means in This Project

When this project refers to hallucination, it does **not** mean semantic correctness or factual accuracy guarantees from a language model.

In Ghost, hallucination refers to:

- Fabricated internal state (invented memories, beliefs, or emotions)  
- False agency (claims of autonomy, intent, or capability the system does not have)  
- Unconstrained behavioral drift caused by prompt phrasing  
- Output that violates internal state constraints or routing rules  

Ghost reduces these failure modes through:

- Deterministic state enforcement  
- Explicit output gating and strategy routing  
- Separation of internal reasoning state from language generation  
- Prohibition of fabricated capabilities or memory  

This is an architectural constraint problem, not a model-scale or temperature-tuning solution.

---

## Proof-of-Architecture Status

Ghost is not a finished system. It is a proof-of-architecture.

Despite its early state, Ghost already exhibits hybrid behavior emerging from the interaction of symbolic state, deterministic control layers, and probabilistic language modeling — behavior that cannot be replicated through prompt engineering alone.

---

## Potential Applications

### Internal-State Reasoning for NPC Systems

Ghost was explored as an internal-state reasoning layer for non-player characters (NPCs).

Rather than directly controlling NPC behavior, Ghost:

- Interprets in-world experiences symbolically  
- Maintains an internal representation of encounters  
- Outputs structured advisory signals  

These signals can bias existing decision systems by prioritizing actions, altering response tendencies, or surfacing emergent goals — without scripted emotional models or narrative paths.

---

## Broader System Integration

Ghost is designed to function as a modular internal-state reasoning layer that can augment:

- Game engines  
- Simulations  
- Decision-support tools  
- LLM-based interfaces  

It enhances these systems by providing stable, interpretable, state-driven advisory outputs.

---

## Roadmap

Planned architectural milestones and future development phases are documented in:

- `ROADMAP.md`

---

## License

Licensed under the Apache License 2.0.

---

## Closing

Ghost demonstrates that meaningful, consistent behavior can emerge from constraint, structure, and state — not from scale, autonomy, or imitation of human cognition.

It is intentionally limited.  
And those limits **are** the architecture.
