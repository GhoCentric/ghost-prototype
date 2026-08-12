# Cascade Experiment

This folder contains a small, deterministic **conceptual experiment** that
compares conservative diffusion with a memory-driven nonlinear cascade.

It is intentionally separate from the production Ghost runtime:

- it does not import or execute `GhostEngine`;
- it is not included in the installed `ghocentric-ghost-engine` package;
- it is not a performance benchmark or evidence for production behavior;
- it exists only to make one state-dynamics idea easy to inspect.

## Run

From the `ghost-engine/` directory:

```bash
python -m cascade_experiments.demo_cascade
```

## Compared Models

### Baseline diffusion

A fixed portion of each node's current value moves to its grid neighbors.
The total signal is conserved, so the aggregate remains approximately `1.0`.

### Ghost-style conceptual cascade

Each node keeps bounded memory of prior activation. That memory creates a
bounded nonlinear influence packet that can propagate while existing node
state persists. Aggregate activation can therefore grow across the network,
while every node remains capped at `1.0`.

The phrase **Ghost-style** describes the experiment's memory-and-propagation
idea. It does not mean this script is running the public Ghost API.

## Files

```text
cascade_experiments/
    __init__.py
    README.md
    demo_cascade.py
```

The experiment has no third-party dependencies and uses no randomness.
