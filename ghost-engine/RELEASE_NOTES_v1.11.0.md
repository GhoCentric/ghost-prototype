# ghocentric-ghost-engine v1.11.0

v1.11.0 adds two engine-neutral state contracts: registered agents and deterministic
continuity.

## Registered agents

`GhostAPI.register_agent(...)` creates durable identity and `GhostAPI.agent(...)`
returns a bound `GhostAgent`. The handle exposes values, goals, capabilities,
affordances, observations, motive state, and coherent copied agent state. Ghost does
not execute engine-specific actions; the host still owns concrete game behavior.

## Continuity

The public continuity surface adds `continuity_event`, `recall_episode`,
`recall_dimension`, `continuity_tick`, and `continuity_state`. Continuity joins
persistent emotion, interpretation, attention, causal episode storage, and recall
without replaying the source event.

The production implementation uses lazy logical-time materialization, a sparse hot
history, and lossless deferred cold-history storage. The frozen production
adjudication measured event cost at 0.7550x the predecessor, dormant tick at 0.0163x,
active tick + state at 0.9465x, recall at 1.0690x, hot snapshot bytes at 0.0963x, and
total persistence bytes at 0.9244x. These are controlled local benchmark ratios,
not claims about every integration workload.

## Compatibility

- Package version: 1.11.0
- Python: >=3.9
- Runtime dependencies: none
- Top-level snapshot schema: 1.0 (unchanged)
- All 59 public `GhostAPI` methods from v1.10 remain available.
- The v1.11 release surface contains 67 public `GhostAPI` methods; agent-specific
  mutation is concentrated on `GhostAgent` rather than duplicated at the top level.

## Validation

- Release regression: 2,745 passed, 1 skipped.
- Reusable core: 6,801 / 6,801 statements and 2,828 / 2,828 branches covered.
- Hermetic wheel and source-distribution construction, installed-package import,
  declared CLI entrypoints, and public v1.10.0 snapshot-upgrade restoration are
  release gates in Release Preparation Pass 2.
