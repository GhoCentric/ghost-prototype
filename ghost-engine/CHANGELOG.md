## v1.8.0 — Deterministic Threat-Response Policy

### Added
- Deterministic, read-only threat-response policy for NPC behavior layers
- Public `evaluate_threat_response(...)` API
- Public `evaluate_npc_threat_response(...)` API for live Ghost relationships
- Response recommendations:
  - fight
  - call_guards
  - confront
  - surrender
  - flee
  - freeze
  - warn
  - ignore
- `ghost-threat-response-demo` runnable public demo
- JSON-safe response packets with normalized caller context,
  Ghost-derived signals, response scores, selected response, reason,
  and relationship interpretation

### Hardening
- Deterministic tie-breaking and bounded non-negative score output
- Context normalization for malformed booleans, counts, non-dict inputs,
  negative values, NaN, and infinity
- Strict relationship packet and diagnostics mapping validation
- Explicit rejection of non-finite relationship values
- Read-only evaluation guarantees: input relationship packets are not mutated

### Validation
- Added adversarial threat-response tests for malformed context,
  malformed relationship packets, missing diagnostics, NaN/infinity,
  schema completeness, JSON safety, deterministic repetition,
  insertion-order independence, and public API parity
- Full package suite passed: 484 tests

## v0.1.2 — Invariant-Verified Core

### Added
- Property-based testing using Hypothesis
- Formal invariants for threat dynamics:
  - Threat level is never negative
  - Threat accumulation is monotonic w.r.t. intensity
  - Threat decays monotonically in absence of new input
- Typed internal step representation (`GhostStep`)
  - Canonical internal format for structured engine input
  - Enables invariant testing without exposing internal types
- Strict separation between internal types and public state
- Actor-specific threat memory invariants

### Fixed
- Internal type leakage from `GhostStep` into public engine state
- Ambiguous input handling between dict-based and typed steps
- Environment contamination caused by parallel package installs

### Guarantees
- Engine state mutates only via explicit `step()` calls
- Public API remains dict-based and serialization-safe
- Internal logic may use typed representations (`GhostStep`) without leaking
- Core engine behavior is invariant under randomized adversarial input
