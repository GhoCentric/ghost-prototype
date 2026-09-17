"""Persistent GhostAgent identity, values, and goal lifecycle for v1.11 development.

Phase 1 established durable identity. Phase 2 added the engine-neutral observation
entry point. Phase 3 made values and goals first-class persistent agent state.
Phase 4 adds bound access to the separate deterministic motive-field runtime while
keeping action selection, execution, and LLM calls outside this layer.
"""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any

from .ids import normalize_id


AGENT_SNAPSHOT_SCHEMA_VERSION = "1.1"
AGENT_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS = frozenset({"1.0", AGENT_SNAPSHOT_SCHEMA_VERSION})
GOAL_STATUSES = frozenset({"inactive", "active", "blocked", "satisfied", "abandoned"})
_GOAL_TRANSITIONS = {
    "inactive": frozenset({"active", "abandoned"}),
    "active": frozenset({"inactive", "blocked", "satisfied", "abandoned"}),
    "blocked": frozenset({"inactive", "active", "satisfied", "abandoned"}),
    "satisfied": frozenset(),
    "abandoned": frozenset(),
}
_AGENT_SNAPSHOT_KEYS = {"schema_version", "agents"}
_AGENT_RECORD_KEYS_V10 = {
    "agent_id", "role", "traits", "values", "goals", "capabilities", "metadata",
}
_AGENT_RECORD_KEYS_V11 = _AGENT_RECORD_KEYS_V10 | {"goal_states"}
_GOAL_SPEC_KEYS = {"status", "priority", "progress", "value_weights", "metadata"}
_GOAL_STATE_KEYS = _GOAL_SPEC_KEYS | {"goal_id", "transition_count", "last_transition"}
_GOAL_TRANSITION_KEYS = {"from_status", "to_status", "reason"}


def _json_safe_copy(value: Any, label: str) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{label} must contain only finite numbers")
        return value
    if isinstance(value, list):
        return [_json_safe_copy(item, f"{label}[{i}]") for i, item in enumerate(value)]
    if isinstance(value, dict):
        copied = {}
        for key in sorted(value):
            if not isinstance(key, str):
                raise ValueError(f"{label} keys must be strings")
            copied[key] = _json_safe_copy(value[key], f"{label}.{key}")
        return copied
    raise ValueError(f"{label} must be JSON-safe")


def _unit_number(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number in [0, 1]")
    numeric = float(value)
    if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise ValueError(f"{label} must be a finite number in [0, 1]")
    return numeric


def _normalize_channel_map(value: dict | None, label: str) -> dict[str, float]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a dict or None")
    normalized: dict[str, float] = {}
    for raw_key, raw_value in value.items():
        key = normalize_id(raw_key, f"{label} key")
        if key in normalized:
            raise ValueError(f"{label} contains duplicate normalized key: {key!r}")
        normalized[key] = _unit_number(raw_value, f"{label}.{key}")
    return {key: normalized[key] for key in sorted(normalized)}


def _normalize_id_list(value, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{label} must be a list, tuple, or None")
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_item in value:
        item = normalize_id(raw_item, f"{label} item")
        if item in seen:
            raise ValueError(f"{label} contains duplicate normalized id: {item!r}")
        seen.add(item)
        normalized.append(item)
    return normalized


def _normalize_role(role) -> str | None:
    if role is None:
        return None
    return normalize_id(role, "agent role")


def _normalize_goal_status(value, label: str = "goal status") -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    status = value.strip().lower()
    if status not in GOAL_STATUSES:
        raise ValueError(f"unsupported {label}: {value!r}; expected one of {sorted(GOAL_STATUSES)}")
    return status


def _normalize_reason(value, label: str = "goal transition reason") -> str | None:
    if value is None:
        return None
    return normalize_id(value, label)


def _build_goal_state(
    goal_id,
    *,
    status: str = "active",
    priority: float = 0.5,
    progress: float = 0.0,
    value_weights: dict | None = None,
    metadata: dict | None = None,
) -> dict:
    goal_id = normalize_id(goal_id, "goal id")
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise ValueError("goal metadata must be a dict or None")
    return {
        "goal_id": goal_id,
        "status": _normalize_goal_status(status),
        "priority": _unit_number(priority, "goal priority"),
        "progress": _unit_number(progress, "goal progress"),
        "value_weights": _normalize_channel_map(value_weights, "goal value_weights"),
        "metadata": _json_safe_copy(metadata, "goal metadata"),
        "transition_count": 0,
        "last_transition": None,
    }


def _normalize_goal_spec(goal_id: str, spec) -> dict:
    if spec is None:
        spec = {}
    if not isinstance(spec, dict):
        raise ValueError(f"goal spec {goal_id!r} must be a dict or None")
    unknown = set(spec) - _GOAL_SPEC_KEYS
    if unknown:
        raise ValueError(f"goal spec {goal_id!r} has unsupported keys: " + ", ".join(sorted(unknown)))
    return _build_goal_state(
        goal_id,
        status=spec.get("status", "active"),
        priority=spec.get("priority", 0.5),
        progress=spec.get("progress", 0.0),
        value_weights=spec.get("value_weights"),
        metadata=spec.get("metadata"),
    )


def _normalize_goals(value) -> tuple[list[str], dict[str, dict]]:
    if value is None:
        return [], {}
    states: dict[str, dict] = {}
    if isinstance(value, (list, tuple)):
        for raw_goal_id in value:
            goal_id = normalize_id(raw_goal_id, "agent goals item")
            if goal_id in states:
                raise ValueError(f"agent goals contains duplicate normalized id: {goal_id!r}")
            states[goal_id] = _build_goal_state(goal_id)
    elif isinstance(value, dict):
        for raw_goal_id, spec in value.items():
            goal_id = normalize_id(raw_goal_id, "agent goals key")
            if goal_id in states:
                raise ValueError(f"agent goals contains duplicate normalized id: {goal_id!r}")
            states[goal_id] = _normalize_goal_spec(goal_id, spec)
    else:
        raise ValueError("agent goals must be a list, tuple, dict, or None")
    ordered_ids = sorted(states)
    return ordered_ids, {goal_id: states[goal_id] for goal_id in ordered_ids}


def _validate_transition_packet(value, *, current_status: str, transition_count: int) -> dict | None:
    if transition_count == 0:
        if value is not None:
            raise ValueError("goal last_transition must be None when transition_count is 0")
        return None
    if not isinstance(value, dict):
        raise ValueError("goal last_transition must be a dict when transition_count is positive")
    unknown = set(value) - _GOAL_TRANSITION_KEYS
    if unknown:
        raise ValueError("goal last_transition has unsupported keys: " + ", ".join(sorted(unknown)))
    missing = _GOAL_TRANSITION_KEYS - set(value)
    if missing:
        raise ValueError("goal last_transition is missing required keys: " + ", ".join(sorted(missing)))
    from_status = _normalize_goal_status(value["from_status"], "goal transition from_status")
    to_status = _normalize_goal_status(value["to_status"], "goal transition to_status")
    reason = _normalize_reason(value["reason"])
    if from_status == to_status or to_status not in _GOAL_TRANSITIONS[from_status]:
        raise ValueError("goal last_transition contains an invalid lifecycle transition")
    if to_status != current_status:
        raise ValueError("goal last_transition to_status must equal current goal status")
    return {"from_status": from_status, "to_status": to_status, "reason": reason}


def _validate_goal_state_snapshot(raw_goal_id, value) -> dict:
    goal_id = normalize_id(raw_goal_id, "goal snapshot key")
    if not isinstance(value, dict):
        raise ValueError(f"goal snapshot record {goal_id!r} must be a dict")
    unknown = set(value) - _GOAL_STATE_KEYS
    if unknown:
        raise ValueError(f"goal snapshot record {goal_id!r} has unsupported keys: " + ", ".join(sorted(unknown)))
    missing = _GOAL_STATE_KEYS - set(value)
    if missing:
        raise ValueError(f"goal snapshot record {goal_id!r} is missing required keys: " + ", ".join(sorted(missing)))
    record_id = normalize_id(value["goal_id"], "goal snapshot goal_id")
    if record_id != goal_id:
        raise ValueError(f"goal snapshot key/id mismatch: {goal_id!r} != {record_id!r}")
    transition_count = value["transition_count"]
    if isinstance(transition_count, bool) or not isinstance(transition_count, int) or transition_count < 0:
        raise ValueError("goal transition_count must be a non-negative integer")
    state = _build_goal_state(
        goal_id,
        status=value["status"],
        priority=value["priority"],
        progress=value["progress"],
        value_weights=value["value_weights"],
        metadata=value["metadata"],
    )
    state["transition_count"] = transition_count
    state["last_transition"] = _validate_transition_packet(
        value["last_transition"], current_status=state["status"], transition_count=transition_count,
    )
    return state


class AgentRuntime:
    """Registry that gives Ghost-owned state one durable agent identity."""

    def __init__(self) -> None:
        self._agents: dict[str, dict] = {}

    def _require_agent(self, agent_id) -> dict:
        agent_id = normalize_id(agent_id, "agent id")
        record = self._agents.get(agent_id)
        if record is None:
            raise ValueError(f"agent is not registered: {agent_id}")
        return record

    def register_agent(
        self,
        agent_id,
        *,
        role=None,
        traits: dict | None = None,
        values: dict | None = None,
        goals=None,
        capabilities=None,
        metadata: dict | None = None,
    ) -> dict:
        agent_id = normalize_id(agent_id, "agent id")
        if agent_id in self._agents:
            raise ValueError(f"agent already registered: {agent_id}")
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, dict):
            raise ValueError("agent metadata must be a dict or None")
        goal_ids, goal_states = _normalize_goals(goals)
        record = {
            "agent_id": agent_id,
            "role": _normalize_role(role),
            "traits": _normalize_channel_map(traits, "agent traits"),
            "values": _normalize_channel_map(values, "agent values"),
            "goals": goal_ids,
            "goal_states": goal_states,
            "capabilities": _normalize_id_list(capabilities, "agent capabilities"),
            "metadata": _json_safe_copy(metadata, "agent metadata"),
        }
        self._agents[agent_id] = record
        return deepcopy(record)

    def get_state(self, agent_id) -> dict | None:
        agent_id = normalize_id(agent_id, "agent id")
        record = self._agents.get(agent_id)
        return deepcopy(record) if record is not None else None

    def has_agent(self, agent_id) -> bool:
        agent_id = normalize_id(agent_id, "agent id")
        return agent_id in self._agents

    def has_state(self) -> bool:
        return bool(self._agents)

    def capabilities(self, agent_id) -> list[str]:
        return list(self._require_agent(agent_id)["capabilities"])

    def add_capability(self, agent_id, capability_id) -> dict:
        record = self._require_agent(agent_id)
        capability_id = normalize_id(capability_id, "agent capability id")
        if capability_id in record["capabilities"]:
            raise ValueError(f"capability already registered for agent: {capability_id}")
        before = list(record["capabilities"])
        record["capabilities"].append(capability_id)
        record["capabilities"] = sorted(record["capabilities"])
        return {
            "agent_id": record["agent_id"],
            "capability_id": capability_id,
            "before": before,
            "after": list(record["capabilities"]),
        }

    def remove_capability(self, agent_id, capability_id) -> bool:
        record = self._require_agent(agent_id)
        capability_id = normalize_id(capability_id, "agent capability id")
        if capability_id not in record["capabilities"]:
            return False
        record["capabilities"].remove(capability_id)
        return True

    def values(self, agent_id) -> dict[str, float]:
        return deepcopy(self._require_agent(agent_id)["values"])

    def set_value(self, agent_id, value_id, weight) -> dict:
        record = self._require_agent(agent_id)
        value_id = normalize_id(value_id, "agent value id")
        after = _unit_number(weight, f"agent value {value_id}")
        before = record["values"].get(value_id)
        record["values"][value_id] = after
        record["values"] = {key: record["values"][key] for key in sorted(record["values"])}
        return {"agent_id": record["agent_id"], "value_id": value_id, "before": before, "after": after}

    def goals(self, agent_id) -> dict[str, dict]:
        return deepcopy(self._require_agent(agent_id)["goal_states"])

    def goal(self, agent_id, goal_id) -> dict | None:
        record = self._require_agent(agent_id)
        goal_id = normalize_id(goal_id, "goal id")
        state = record["goal_states"].get(goal_id)
        return deepcopy(state) if state is not None else None

    def add_goal(
        self,
        agent_id,
        goal_id,
        *,
        status: str = "active",
        priority: float = 0.5,
        progress: float = 0.0,
        value_weights: dict | None = None,
        metadata: dict | None = None,
    ) -> dict:
        record = self._require_agent(agent_id)
        state = _build_goal_state(
            goal_id, status=status, priority=priority, progress=progress,
            value_weights=value_weights, metadata=metadata,
        )
        goal_id = state["goal_id"]
        if goal_id in record["goal_states"]:
            raise ValueError(f"goal already registered for agent: {goal_id}")
        record["goal_states"][goal_id] = state
        record["goal_states"] = {key: record["goal_states"][key] for key in sorted(record["goal_states"])}
        record["goals"] = sorted(record["goal_states"])
        return deepcopy(state)

    def transition_goal(self, agent_id, goal_id, status, *, reason=None) -> dict:
        record = self._require_agent(agent_id)
        goal_id = normalize_id(goal_id, "goal id")
        state = record["goal_states"].get(goal_id)
        if state is None:
            raise ValueError(f"goal is not registered for agent: {goal_id}")
        before = state["status"]
        after = _normalize_goal_status(status)
        reason = _normalize_reason(reason)
        if after == before:
            return {
                "agent_id": record["agent_id"], "goal_id": goal_id, "changed": False,
                "from_status": before, "to_status": after, "reason": reason,
                "transition_count": state["transition_count"],
            }
        if after not in _GOAL_TRANSITIONS[before]:
            raise ValueError(f"invalid goal lifecycle transition: {before} -> {after}")
        state["status"] = after
        state["transition_count"] += 1
        state["last_transition"] = {"from_status": before, "to_status": after, "reason": reason}
        return {
            "agent_id": record["agent_id"], "goal_id": goal_id, "changed": True,
            "from_status": before, "to_status": after, "reason": reason,
            "transition_count": state["transition_count"],
        }

    def set_goal_progress(self, agent_id, goal_id, progress) -> dict:
        record = self._require_agent(agent_id)
        goal_id = normalize_id(goal_id, "goal id")
        state = record["goal_states"].get(goal_id)
        if state is None:
            raise ValueError(f"goal is not registered for agent: {goal_id}")
        before = state["progress"]
        after = _unit_number(progress, "goal progress")
        state["progress"] = after
        return {"agent_id": record["agent_id"], "goal_id": goal_id, "before": before, "after": after}

    def set_goal_priority(self, agent_id, goal_id, priority) -> dict:
        record = self._require_agent(agent_id)
        goal_id = normalize_id(goal_id, "goal id")
        state = record["goal_states"].get(goal_id)
        if state is None:
            raise ValueError(f"goal is not registered for agent: {goal_id}")
        before = state["priority"]
        after = _unit_number(priority, "goal priority")
        state["priority"] = after
        return {"agent_id": record["agent_id"], "goal_id": goal_id, "before": before, "after": after}

    def snapshot(self) -> dict:
        return {
            "schema_version": AGENT_SNAPSHOT_SCHEMA_VERSION,
            "agents": {agent_id: deepcopy(self._agents[agent_id]) for agent_id in sorted(self._agents)},
        }

    @classmethod
    def from_snapshot(cls, snapshot: dict) -> "AgentRuntime":
        if not isinstance(snapshot, dict):
            raise ValueError("agent snapshot must be a dict")
        unknown = set(snapshot) - _AGENT_SNAPSHOT_KEYS
        if unknown:
            raise ValueError("agent snapshot has unsupported keys: " + ", ".join(sorted(unknown)))
        missing = _AGENT_SNAPSHOT_KEYS - set(snapshot)
        if missing:
            raise ValueError("agent snapshot is missing required keys: " + ", ".join(sorted(missing)))
        schema_version = snapshot["schema_version"]
        if schema_version not in AGENT_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS:
            raise ValueError("unsupported agent snapshot schema version: " f"{schema_version!r}")
        agents = snapshot["agents"]
        if not isinstance(agents, dict):
            raise ValueError("agent snapshot agents must be a dict")
        runtime = cls()
        record_keys = _AGENT_RECORD_KEYS_V10 if schema_version == "1.0" else _AGENT_RECORD_KEYS_V11
        for raw_key in sorted(agents):
            key = normalize_id(raw_key, "agent snapshot key")
            record = agents[raw_key]
            if not isinstance(record, dict):
                raise ValueError(f"agent snapshot record {key!r} must be a dict")
            unknown_record = set(record) - record_keys
            if unknown_record:
                raise ValueError(f"agent snapshot record {key!r} has unsupported keys: " + ", ".join(sorted(unknown_record)))
            missing_record = record_keys - set(record)
            if missing_record:
                raise ValueError(f"agent snapshot record {key!r} is missing required keys: " + ", ".join(sorted(missing_record)))
            record_id = normalize_id(record["agent_id"], "agent snapshot agent_id")
            if record_id != key:
                raise ValueError(f"agent snapshot key/id mismatch: {key!r} != {record_id!r}")
            if schema_version == "1.0":
                runtime.register_agent(
                    record_id, role=record["role"], traits=record["traits"], values=record["values"],
                    goals=record["goals"], capabilities=record["capabilities"], metadata=record["metadata"],
                )
                continue
            goal_ids = _normalize_id_list(record["goals"], "agent snapshot goals")
            goal_states = record["goal_states"]
            if not isinstance(goal_states, dict):
                raise ValueError("agent snapshot goal_states must be a dict")
            validated_goal_states: dict[str, dict] = {}
            for raw_goal_id in sorted(goal_states):
                goal_state = _validate_goal_state_snapshot(raw_goal_id, goal_states[raw_goal_id])
                goal_id = goal_state["goal_id"]
                if goal_id in validated_goal_states:
                    raise ValueError(f"agent snapshot goal_states contains duplicate normalized id: {goal_id!r}")
                validated_goal_states[goal_id] = goal_state
            if set(goal_ids) != set(validated_goal_states):
                raise ValueError("agent snapshot goals and goal_states must reference the same ids")
            goal_specs = {
                goal_id: {
                    "status": state["status"], "priority": state["priority"], "progress": state["progress"],
                    "value_weights": state["value_weights"], "metadata": state["metadata"],
                }
                for goal_id, state in validated_goal_states.items()
            }
            runtime.register_agent(
                record_id, role=record["role"], traits=record["traits"], values=record["values"],
                goals=goal_specs, capabilities=record["capabilities"], metadata=record["metadata"],
            )
            runtime._agents[record_id]["goal_states"] = validated_goal_states
            runtime._agents[record_id]["goals"] = sorted(validated_goal_states)
        return runtime


class GhostAgent:
    """Thin bound handle for one registered agent inside a GhostAPI runtime."""

    def __init__(self, api, agent_id) -> None:
        self._api = api
        self._agent_id = normalize_id(agent_id, "agent id")

    @property
    def agent_id(self) -> str:
        return self._agent_id

    def _require_agent_id(self) -> str:
        state = self._api.agents.get_state(self._agent_id)
        if state is None:
            raise ValueError("agent must be registered before agent-state mutation")
        return state["agent_id"]

    def _require_observer_id(self) -> str:
        try:
            return self._require_agent_id()
        except ValueError as exc:
            raise ValueError(
                "observer must be a registered GhostAgent before observation"
            ) from exc

    def state(self, *, include_layers: bool = True) -> dict:
        state = self._api.agent_state(self._agent_id, include_layers=include_layers)
        if state is None:
            raise RuntimeError(f"registered agent disappeared: {self._agent_id}")
        return state

    def snapshot(self) -> dict:
        return self.state(include_layers=True)

    def values(self) -> dict[str, float]:
        return self._api.agents.values(self._require_agent_id())

    def set_value(self, value_id, weight) -> dict:
        return self._api.agents.set_value(self._require_agent_id(), value_id, weight)

    def goals(self) -> dict[str, dict]:
        return self._api.agents.goals(self._require_agent_id())

    def goal(self, goal_id) -> dict | None:
        return self._api.agents.goal(self._require_agent_id(), goal_id)

    def add_goal(
        self, goal_id, *, status: str = "active", priority: float = 0.5,
        progress: float = 0.0, value_weights: dict | None = None,
        metadata: dict | None = None,
    ) -> dict:
        return self._api.agents.add_goal(
            self._require_agent_id(), goal_id, status=status, priority=priority,
            progress=progress, value_weights=value_weights, metadata=metadata,
        )

    def transition_goal(self, goal_id, status, *, reason=None) -> dict:
        return self._api.agents.transition_goal(
            self._require_agent_id(), goal_id, status, reason=reason,
        )

    def set_goal_progress(self, goal_id, progress) -> dict:
        return self._api.agents.set_goal_progress(
            self._require_agent_id(), goal_id, progress,
        )

    def set_goal_priority(self, goal_id, priority) -> dict:
        return self._api.agents.set_goal_priority(
            self._require_agent_id(), goal_id, priority,
        )

    def capabilities(self) -> list[str]:
        return self._api.agents.capabilities(self._require_agent_id())

    def add_capability(self, capability_id) -> dict:
        return self._api.agents.add_capability(
            self._require_agent_id(), capability_id,
        )

    def remove_capability(self, capability_id) -> bool:
        return self._api._remove_agent_capability(
            self._require_agent_id(), capability_id,
        )

    def set_affordances(self, candidates, *, context: dict | None = None) -> dict:
        agent_id = self._require_agent_id()
        return self._api.affordances.set(
            agent_id,
            candidates,
            allowed_capabilities=self._api.agents.capabilities(agent_id),
            context=context,
        )

    def clear_affordances(self, *, context: dict | None = None) -> dict:
        agent_id = self._require_agent_id()
        return self._api.affordances.set(
            agent_id,
            [],
            allowed_capabilities=self._api.agents.capabilities(agent_id),
            context=context,
        )

    def affordances(self) -> dict | None:
        return self._api.affordances.current(self._require_agent_id())

    def affordance_history(self, *, limit: int | None = None) -> list[dict]:
        return self._api.affordances.history(
            self._require_agent_id(), limit=limit,
        )

    def observe(
        self, event, *, kind: str = "direct", subject=None, source=None,
        features: dict | None = None,
    ) -> dict:
        observer = self._require_observer_id()
        return self._api.perception.record(
            observer, event, kind=kind, subject=subject, source=source,
            features=features,
        )

    def observation_history(self, *, limit: int | None = None) -> list[dict]:
        return self._api.perception.history(
            self._require_observer_id(), limit=limit,
        )

    def latest_observation(self) -> dict | None:
        return self._api.perception.latest(self._require_observer_id())

    def configure_motive(self, motive_id, *, baseline=0.0, weights=None) -> dict:
        return self._api.motives.configure(
            self._require_agent_id(), motive_id, baseline=baseline, weights=weights,
        )

    def remove_motive(self, motive_id) -> bool:
        return self._api.motives.remove(self._require_agent_id(), motive_id)

    def motive_profiles(self) -> dict[str, dict]:
        return self._api.motives.profiles(self._require_agent_id())

    def motive_signals(self) -> dict:
        return self._api._agent_motive_signals(self._require_agent_id())

    def evaluate_motives(self) -> dict:
        return self._api._evaluate_agent_motives(self._require_agent_id())

    def motive_field(self) -> dict | None:
        return self._api.motives.current(self._require_agent_id())

    def motive_history(self, *, limit: int | None = None) -> list[dict]:
        return self._api.motives.history(
            self._require_agent_id(), limit=limit,
        )

    def __repr__(self) -> str:
        return f"GhostAgent(agent_id={self._agent_id!r})"
