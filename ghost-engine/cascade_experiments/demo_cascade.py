from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple


Node = Tuple[int, int]
Grid = Dict[Node, Tuple[Node, ...]]


@dataclass(frozen=True)
class CascadeConfig:
    """Parameters for the deterministic grid experiment."""

    size: int = 5
    steps: int = 15
    shock: float = 1.0
    diffusion_rate: float = 0.25
    memory_decay: float = 0.85
    propagation_rate: float = 0.15
    nonlinear_exponent: float = 1.2

    def __post_init__(self) -> None:
        if self.size < 1:
            raise ValueError("size must be at least 1")
        if self.steps < 1:
            raise ValueError("steps must be at least 1")
        if not 0.0 <= self.shock <= 1.0:
            raise ValueError("shock must be between 0 and 1")
        if not 0.0 <= self.diffusion_rate <= 1.0:
            raise ValueError(
                "diffusion_rate must be between 0 and 1"
            )
        if not 0.0 <= self.memory_decay <= 1.0:
            raise ValueError(
                "memory_decay must be between 0 and 1"
            )
        if not 0.0 <= self.propagation_rate <= 1.0:
            raise ValueError(
                "propagation_rate must be between 0 and 1"
            )
        if self.nonlinear_exponent <= 0.0:
            raise ValueError(
                "nonlinear_exponent must be positive"
            )


DEFAULT_CONFIG = CascadeConfig()

# Compatibility constants retained from the original local experiment.
SIZE = DEFAULT_CONFIG.size
STEPS = DEFAULT_CONFIG.steps
SHOCK = DEFAULT_CONFIG.shock
DIFF_RATE = DEFAULT_CONFIG.diffusion_rate
GHOST_RATE = DEFAULT_CONFIG.propagation_rate


def build_grid(size: int) -> Grid:
    """Build a deterministic four-neighbor square grid."""

    if size < 1:
        raise ValueError("size must be at least 1")

    neighbors: Grid = {}

    for row in range(size):
        for column in range(size):
            node = (row, column)
            adjacent: List[Node] = []

            if row > 0:
                adjacent.append((row - 1, column))
            if row < size - 1:
                adjacent.append((row + 1, column))
            if column > 0:
                adjacent.append((row, column - 1))
            if column < size - 1:
                adjacent.append((row, column + 1))

            neighbors[node] = tuple(adjacent)

    return neighbors


def _initial_state(
    neighbors: Grid,
    config: CascadeConfig,
) -> Dict[Node, float]:
    center = (
        config.size // 2,
        config.size // 2,
    )

    if center not in neighbors:
        raise ValueError(
            "neighbors do not match config.size"
        )

    state = {
        node: 0.0
        for node in neighbors
    }

    state[center] = config.shock
    return state


def run_diffusion(
    neighbors: Grid,
    config: CascadeConfig = DEFAULT_CONFIG,
) -> List[float]:
    """Run mass-conserving diffusion and return aggregate history."""

    state = _initial_state(
        neighbors,
        config,
    )

    history: List[float] = []

    for _ in range(config.steps):
        new_state = {
            node: 0.0
            for node in neighbors
        }

        for node, value in state.items():
            degree = len(
                neighbors[node]
            )

            spread_total = (
                value
                * config.diffusion_rate
            )

            spread_each = (
                spread_total / degree
                if degree
                else 0.0
            )

            new_state[node] += (
                value - spread_total
            )

            for neighbor in neighbors[node]:
                new_state[neighbor] += (
                    spread_each
                )

        state = new_state
        history.append(
            sum(state.values())
        )

    return history


def run_ghost_style(
    neighbors: Grid,
    config: CascadeConfig = DEFAULT_CONFIG,
) -> List[float]:
    """Run the bounded memory-and-propagation conceptual model."""

    state = _initial_state(
        neighbors,
        config,
    )

    memory = {
        node: 0.0
        for node in neighbors
    }

    history: List[float] = []

    for _ in range(config.steps):
        new_state = {
            node: 0.0
            for node in neighbors
        }

        for node, value in state.items():
            memory[node] = min(
                1.0,
                (
                    memory[node]
                    * config.memory_decay
                )
                + value,
            )

            influence = min(
                1.0,
                memory[node]
                ** config.nonlinear_exponent,
            )

            degree = len(
                neighbors[node]
            )

            spread_total = (
                influence
                * config.propagation_rate
            )

            spread_each = (
                spread_total / degree
                if degree
                else 0.0
            )

            # Existing state persists.
            new_state[node] += value

            for neighbor in neighbors[node]:
                new_state[neighbor] += (
                    spread_each
                )

        # Each node remains bounded even though aggregate activation
        # can increase as more nodes become active.
        state = {
            node: min(
                1.0,
                max(0.0, value),
            )
            for node, value in new_state.items()
        }

        history.append(
            sum(state.values())
        )

    return history


# Compatibility alias retained for the original local function name.
run_ghost = run_ghost_style


def format_timeline(
    label: str,
    history: Iterable[float],
) -> str:
    """Return an ASCII timeline without mutating experiment state."""

    lines = [
        "",
        label,
    ]

    for index, value in enumerate(
        history
    ):
        bars = "#" * int(
            value * 5
        )

        lines.append(
            f"{index:02d}: "
            f"{bars} "
            f"({value:.2f})"
        )

    return "\n".join(lines)


def print_timeline(
    label: str,
    history: Iterable[float],
) -> None:
    """Print a formatted experiment timeline."""

    print(
        format_timeline(
            label,
            history,
        )
    )


def main() -> None:
    config = DEFAULT_CONFIG
    neighbors = build_grid(
        config.size
    )

    diffusion = run_diffusion(
        neighbors,
        config,
    )

    ghost_style = run_ghost_style(
        neighbors,
        config,
    )

    print("\nCASCADE EXPERIMENT")

    print_timeline(
        "BASELINE DIFFUSION "
        "(conservative)",
        diffusion,
    )

    print_timeline(
        "GHOST-STYLE CASCADE "
        "(memory + nonlinear influence)",
        ghost_style,
    )

    print("\nSUMMARY")
    print(
        "Diffusion peak:",
        f"{max(diffusion):.2f}",
    )
    print(
        "Ghost-style peak:",
        f"{max(ghost_style):.2f}",
    )
    print(
        "Per-node cap:",
        "1.00",
    )
    print()
    print(
        "This is a standalone conceptual "
        "experiment, not the Ghost runtime."
    )


if __name__ == "__main__":
    main()
