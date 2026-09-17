"""Production continuity runtime descended from Ghost M3Q-M3T.

The runtime owns only two kinds of state per agent:

* dimension-specific present relevance (interpretation activation), and
* one cross-layer foreground ``current_leader``.

Interpretation remains the owner of persistent meaning.  Emotion remains the
owner of emotional temporal physics.  Attention remains the owner of access /
flow.  Durable historical causal episodes live outside the hot snapshot in an
injected episode archive.
"""

from __future__ import annotations

from copy import deepcopy
import math
from typing import Any

from .ids import normalize_id


CONTINUITY_SNAPSHOT_SCHEMA_VERSION = "1.0"
_EPSILON = 1e-12


def _token(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _unit(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be a finite number")
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{label} must be in [0, 1]")
    return number


def _switch_threshold(value: Any) -> float:
    threshold = _unit(value, "switch_threshold")
    if threshold >= 1.0:
        raise ValueError("switch_threshold must be in [0, 1)")
    return threshold


def _bounded_positive_update(current: float, impulse: float) -> float:
    return current + impulse * (1.0 - current)


class PairwiseForeground:
    """Pairwise-relative hysteresis with exactly one semantic state variable."""

    def __init__(self, threshold: float, current_leader: str | None = None) -> None:
        self.threshold = _switch_threshold(threshold)
        if current_leader is not None:
            current_leader = _token(current_leader, "current_leader")
        self.current_leader = current_leader

    @staticmethod
    def raw_leader(values: dict[str, float]) -> tuple[str | None, float]:
        if not values:
            return None, 0.0
        name = min(values, key=lambda key: (-values[key], key))
        value = values[name]
        return (None, 0.0) if value <= 0.0 else (name, value)

    @staticmethod
    def pairwise_advantage(challenger: float, incumbent: float) -> float:
        total = challenger + incumbent
        if total <= 0.0:
            return 0.0
        return (challenger - incumbent) / total

    def step(self, tick: int, attended_salience: dict[str, float]) -> dict[str, Any]:
        if isinstance(tick, bool) or not isinstance(tick, int) or tick < 0:
            raise ValueError("tick must be a non-negative integer")
        if not isinstance(attended_salience, dict):
            raise ValueError("attended_salience must be a dict")
        values: dict[str, float] = {}
        for raw_name, raw_value in attended_salience.items():
            name = _token(raw_name, "salience name")
            if name in values:
                raise ValueError(f"duplicate salience name: {name}")
            values[name] = _unit(raw_value, f"attended_salience.{name}")
        values = dict(sorted(values.items()))

        raw, raw_value = self.raw_leader(values)
        previous = self.current_leader
        advantage = 0.0
        if raw is None:
            resolved = None
            reason = "zero_vector"
        elif previous is None or previous not in values:
            resolved = raw
            reason = "acquired"
        else:
            incumbent_value = values[previous]
            if incumbent_value <= 0.0:
                resolved = raw
                reason = "incumbent_inactive"
            elif raw == previous:
                resolved = previous
                reason = "leader_holds"
            else:
                advantage = self.pairwise_advantage(raw_value, incumbent_value)
                if advantage + _EPSILON >= self.threshold:
                    resolved = raw
                    reason = "threshold_crossed"
                else:
                    resolved = previous
                    reason = "hysteresis_retained"
        self.current_leader = resolved
        return {
            "computed_at_tick": tick,
            "threshold": self.threshold,
            "previous_leader": previous,
            "raw_leader": raw,
            "raw_leader_salience": raw_value,
            "resolved_leader": resolved,
            "resolved_leader_salience": values.get(resolved, 0.0) if resolved else 0.0,
            "pairwise_advantage": advantage,
            "reason": reason,
            "attended_salience": deepcopy(values),
        }


class ContinuityRuntime:
    """Minimal hot-state owner for M3 continuity semantics."""

    def __init__(self) -> None:
        self._agents: dict[str, dict[str, Any]] = {}

    def has_state(self) -> bool:
        return bool(self._agents)

    def agents(self) -> list[str]:
        return sorted(self._agents)

    def register_agent(
        self,
        agent: str,
        *,
        release_rate: float,
        switch_threshold: float,
    ) -> dict[str, Any]:
        agent_id = normalize_id(agent, "continuity agent")
        release_rate = _unit(release_rate, "release_rate")
        switch_threshold = _switch_threshold(switch_threshold)
        existing = self._agents.get(agent_id)
        if existing is None:
            self._agents[agent_id] = {
                "release_rate": release_rate,
                "activation": {},
                "foreground": PairwiseForeground(switch_threshold),
            }
        else:
            if not math.isclose(existing["release_rate"], release_rate, rel_tol=0.0, abs_tol=0.0):
                raise ValueError("continuity release_rate cannot change after registration")
            if not math.isclose(existing["foreground"].threshold, switch_threshold, rel_tol=0.0, abs_tol=0.0):
                raise ValueError("continuity switch_threshold cannot change after registration")
        return self.get_state(agent_id)

    def _state(self, agent: str) -> tuple[str, dict[str, Any]]:
        agent_id = normalize_id(agent, "continuity agent")
        state = self._agents.get(agent_id)
        if state is None:
            raise ValueError(f"continuity agent is not registered: {agent_id}")
        return agent_id, state

    def get_state(self, agent: str) -> dict[str, Any] | None:
        agent_id = normalize_id(agent, "continuity agent")
        state = self._agents.get(agent_id)
        if state is None:
            return None
        return {
            "agent": agent_id,
            "release_rate": state["release_rate"],
            "activation": deepcopy(dict(sorted(state["activation"].items()))),
            "current_leader": state["foreground"].current_leader,
            "switch_threshold": state["foreground"].threshold,
        }

    def ingest_interpretation_result(
        self,
        agent: str,
        result: dict[str, Any],
    ) -> list[dict[str, Any]]:
        agent_id, state = self._state(agent)
        if not isinstance(result, dict):
            raise ValueError("interpretation result must be a dict")
        if result.get("agent") != agent_id:
            raise ValueError("interpretation result agent does not match continuity agent")
        transitions = result.get("transitions")
        if not isinstance(transitions, dict):
            raise ValueError("interpretation result transitions must be a dict")
        rows = []
        for raw_dimension, transition in sorted(transitions.items()):
            dimension = _token(raw_dimension, "interpretation dimension")
            if not isinstance(transition, dict):
                raise ValueError("interpretation transition must be a dict")
            meaning = _unit(transition.get("level_after"), f"{dimension}.level_after")
            effective = transition.get("effective_impulse")
            if isinstance(effective, bool) or not isinstance(effective, (int, float)):
                raise ValueError(f"{dimension}.effective_impulse must be finite")
            effective = float(effective)
            if not math.isfinite(effective) or not -1.0 <= effective <= 1.0:
                raise ValueError(f"{dimension}.effective_impulse must be in [-1, 1]")
            cause = abs(effective)
            before = state["activation"].get(dimension, 0.0)
            after = _bounded_positive_update(before, cause)
            state["activation"][dimension] = after
            rows.append(
                {
                    "cause": "interpretation_update",
                    "dimension": dimension,
                    "meaning": meaning,
                    "effective_impulse": effective,
                    "relevance_impulse": cause,
                    "activation_before": before,
                    "activation_after": after,
                }
            )
        return rows

    def recall(self, agent: str, dimension: str, retrieval_strength: float) -> dict[str, Any]:
        _, state = self._state(agent)
        dimension = _token(dimension, "recall dimension")
        strength = _unit(retrieval_strength, "retrieval_strength")
        before = state["activation"].get(dimension, 0.0)
        after = _bounded_positive_update(before, strength)
        state["activation"][dimension] = after
        return {
            "cause": "memory_recall",
            "dimension": dimension,
            "retrieval_strength": strength,
            "activation_before": before,
            "activation_after": after,
        }

    def tick_activation(self, agent: str, *, steps: int = 1) -> dict[str, Any]:
        _, state = self._state(agent)
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
            raise ValueError("steps must be a positive integer")
        before = deepcopy(state["activation"])
        release_rate = state["release_rate"]
        retention = (1.0 - release_rate) ** steps
        for dimension in sorted(state["activation"]):
            state["activation"][dimension] *= retention
        return {
            "cause": "time",
            "steps": steps,
            "activation_before": before,
            "activation_after": deepcopy(dict(sorted(state["activation"].items()))),
        }

    def activation_aware_salience(
        self,
        agent: str,
        bridge: dict[str, Any],
    ) -> dict[str, Any]:
        _, state = self._state(agent)
        if not isinstance(bridge, dict) or not isinstance(bridge.get("salience"), dict):
            raise ValueError("salience bridge packet is invalid")
        salience = {
            str(name): float(value)
            for name, value in bridge["salience"].items()
            if not str(name).startswith("interpretation:")
        }
        for dimension, value in sorted(state["activation"].items()):
            salience[f"interpretation:{dimension}"] = value
        out = deepcopy(bridge)
        out["salience"] = dict(sorted(salience.items()))
        out["interpretation_activation"] = deepcopy(
            dict(sorted(state["activation"].items()))
        )
        return out

    def resolve_foreground(
        self,
        agent: str,
        attended_salience: dict[str, float],
        *,
        sequence: int,
    ) -> dict[str, Any]:
        _, state = self._state(agent)
        return state["foreground"].step(sequence, attended_salience)

    def snapshot(self) -> dict[str, Any]:
        agents = {}
        for agent in sorted(self._agents):
            state = self._agents[agent]
            agents[agent] = {
                "release_rate": state["release_rate"],
                "switch_threshold": state["foreground"].threshold,
                "current_leader": state["foreground"].current_leader,
                "activation": deepcopy(dict(sorted(state["activation"].items()))),
            }
        return {
            "schema_version": CONTINUITY_SNAPSHOT_SCHEMA_VERSION,
            "agents": agents,
        }

    @classmethod
    def from_snapshot(cls, snapshot: Any) -> "ContinuityRuntime":
        if not isinstance(snapshot, dict):
            raise ValueError("continuity snapshot must be a dict")
        if set(snapshot) != {"schema_version", "agents"}:
            raise ValueError("continuity snapshot has unsupported or missing keys")
        if snapshot["schema_version"] != CONTINUITY_SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(
                "unsupported continuity snapshot schema version: "
                f"{snapshot['schema_version']!r}"
            )
        if not isinstance(snapshot["agents"], dict):
            raise ValueError("continuity snapshot agents must be a dict")
        obj = cls()
        for raw_agent, raw_state in snapshot["agents"].items():
            agent = normalize_id(raw_agent, "continuity snapshot agent")
            if agent in obj._agents:
                raise ValueError(f"duplicate continuity agent: {agent}")
            if not isinstance(raw_state, dict) or set(raw_state) != {
                "release_rate",
                "switch_threshold",
                "current_leader",
                "activation",
            }:
                raise ValueError(f"invalid continuity snapshot state for {agent}")
            release_rate = _unit(raw_state["release_rate"], "release_rate")
            threshold = _switch_threshold(raw_state["switch_threshold"])
            leader = raw_state["current_leader"]
            foreground = PairwiseForeground(threshold, leader)
            activation_value = raw_state["activation"]
            if not isinstance(activation_value, dict):
                raise ValueError("continuity activation must be a dict")
            activation: dict[str, float] = {}
            for raw_dimension, raw_value in activation_value.items():
                dimension = _token(raw_dimension, "continuity activation dimension")
                if dimension in activation:
                    raise ValueError(f"duplicate continuity activation dimension: {dimension}")
                activation[dimension] = _unit(
                    raw_value,
                    f"continuity activation.{dimension}",
                )
            if leader is not None and leader.startswith("interpretation:"):
                dimension = leader.split(":", 1)[1]
                if dimension not in activation:
                    raise ValueError("continuity current_leader names missing activation")
            obj._agents[agent] = {
                "release_rate": release_rate,
                "activation": dict(sorted(activation.items())),
                "foreground": foreground,
            }
        return obj
