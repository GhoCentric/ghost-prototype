# Testing and Validation

Ghost's executable test suite lives in [`../tests`](../tests).

## Current v1.9.2 Checkpoint

From the `ghost-engine/` directory:

```bash
python -m pytest -q
```

Expected synchronized checkpoint:

```text
1763 passed, 1 skipped
```

The skipped test is intentionally gated. Normal validation does not require an
API key or a real network call.

## Maintained Coverage Lanes

The authoritative commands live in [`../QUALITY.md`](../QUALITY.md). Current
machine-readable and text evidence lives under [`coverage/v1.9.2/`](coverage/v1.9.2/).

- reusable Ghost core;
- complete Ghost Revolution package;
- Order Coordination.

All three are required to remain at 100% statements and branches.

## Public v1.9.2 CLI Commands

The package exposes thirteen console commands. v1.9.2 adds:

```text
ghost-revolution-dev
ghost-revolution-llm-dev
```

`ghost-revolution-dev` exposes the existing developer shortcut panel without
requiring an API key. `ghost-revolution-llm-dev` is opt-in live mode: it requests
the user's own OpenAI API key through hidden terminal input, enables the real
opponent/narration LLM roles for that process, and restores the managed
environment afterward. Ghost remains authoritative over deterministic combat
resolution.

Ghost Revolution remains a playable reference prototype and systems
demonstration, not a finished game.
