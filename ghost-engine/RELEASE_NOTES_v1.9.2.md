# Ghost Engine v1.9.2 — Multi-Emotion State

Ghost v1.9.2 promotes the multi-emotion runtime from development work to a
public GhostAPI contract.

## What changed

Relationship state and emotional state are now explicitly separate persistent
layers.

The relationship layer continues to accumulate positive and negative history
and derive trust plus friendly / neutral / hostile relationship state.

The new emotional layer maintains independently bounded `0..1` channels:

- anger
- fear
- grief
- hope
- joy

Each channel has its own current level, baseline, sensitivity, inertia, and
salience bias. Applications may also add custom channels and configure explicit
event impulse profiles.

## Deterministic emotional dynamics

Emotion values are not randomly generated and are not selected by an LLM.

For each event, Ghost starts with an explicit signed impulse profile, then
applies event intensity, per-agent sensitivity, and caller-owned context
modifiers. Positive impulses saturate toward `1.0`; negative impulses scale
against the current level. Time advances each channel toward its baseline using
that channel's inertia.

The default profiles are starter semantics, not claims about human psychology.
Applications can replace them.

## Spotlight hysteresis

Emotion levels update immediately, but the dominant attention spotlight is
stateful.

The raw salience leader only replaces the current spotlight when it beats the
incumbent by the configured switch margin. The v1.9.2 default margin is `0.05`.

This prevents near-tied emotions from flickering attention on every small
change while still allowing a clear challenger to take over deterministically.

## Public GhostAPI surface

The v1.9.2 emotion contract includes:

```text
register_emotional_agent
emotional_state
emotional_event_profiles
configure_emotional_event
apply_emotional_event
tick_emotions
apply_layered_event
```

`apply_layered_event` atomically applies one normalized event to both the
existing relationship layer and the target's emotional state. Ghost exposes the
resulting state and pressure; the host game, application, agent, or optional LLM
still owns the final action and presentation.

## Persistence

Emotion snapshot sub-schema: `1.1`

Legacy emotion snapshot sub-schema `1.0` remains restorable. Package version and
the top-level Ghost snapshot schema remain separate concepts.

## Validation

The v1.9.2 freeze adds a dedicated public-contract suite on top of the
multi-emotion, emotional-dynamics, and spotlight-hysteresis torture suites.

Expected synchronized Pydroid validation after this release-prep patch:

```text
1,763 passed
1 skipped
```

## Live proof

Browser demo:

https://ghocentric.github.io/ghost-prototype/

PyPI:

https://pypi.org/project/ghocentric-ghost-engine/

Source:

https://github.com/GhoCentric/ghost-prototype
