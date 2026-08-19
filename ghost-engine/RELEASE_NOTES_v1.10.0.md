# Ghost Engine v1.10.0 — Interpretation, Attention, and Flow

Ghost v1.10.0 adds two persistent cognitive-state layers and a read-only bridge
between them and existing emotional state.

## Objective action remains separate from meaning

The host game or application supplies an objective action and observable
features. Ghost does not reinterpret hidden world truth.

Each registered NPC can own different persistent interpretation rules,
sensitivities, baselines, and activation / release thresholds. The same
objective action can therefore produce different deterministic meaning for
different agents while the source event remains identical.

Public operations:

```text
register_interpretation_agent
configure_interpretation_rule
interpretation_state
evaluate_action_meaning
```

## Persistent attention / flow

Attention is persistent state rather than a one-shot display transform.

Flow pressure can compress what reaches the foreground without deleting or
rewriting the underlying emotional or interpretation source. Strong novelty,
threat, contradiction, or interpretation pressure can break through flow.

Public operations:

```text
register_attention_agent
attention_state
advance_attention
persistent_salience
advance_attention_from_state
```

## Read-only persistent salience bridge

`persistent_salience(...)` creates a copied, namespaced salience view across
persistent emotional and interpretation state.

`advance_attention_from_state(...)` passes that copied view into the attention
runtime. Attention may transform foreground visibility, but it does not receive
write authority over the source state.

The release therefore keeps these concepts explicit:

```text
objective action
      ↓
persistent agent-specific interpretation
      ↓
copied persistent salience
      ↓
persistent attention / flow
      ↓
attended foreground state
```

The host still owns final game-specific action execution and presentation.

## Persistence and compatibility

```text
Package version:                 1.10.0
Top-level Ghost snapshot schema: 1.0
Emotion snapshot sub-schema:     1.1
Interpretation sub-schema:       1.0
Attention sub-schema:            1.0
Runtime dependencies:            0
```

Package release numbers and snapshot schema versions remain independent.

## Validation

Release-preparation validation:

```text
Full uninstrumented suite: 2390 passed, 1 skipped
Reusable Ghost core:       100% statements / 100% branches
Ghost Revolution:          100% statements / 100% branches
Order Coordination:        100% statements / 100% branches
```

The release gate also builds and validates the wheel and source distribution,
checks package metadata and console-script declarations, and performs isolated
installs of both artifacts before the release-prep commit is pushed.

## Browser proof

The public browser proof demonstrates the same-event / different-meaning split,
foreground compression under task flow, read-only source preservation, strong
threat breakthrough, snapshot restoration, and deterministic replay.

Browser demo:

https://ghocentric.github.io/ghost-prototype/

PyPI:

https://pypi.org/project/ghocentric-ghost-engine/

Source:

https://github.com/GhoCentric/ghost-prototype
