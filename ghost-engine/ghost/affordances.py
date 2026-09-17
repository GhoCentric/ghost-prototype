"""Engine-neutral capability / affordance contract for GhostAgent.

Ghost does not inspect a game engine to discover what an NPC can physically do.
The host owns world capability checks and submits the actions currently available.
This runtime validates, canonicalizes, persists, and audits that submitted set.
It does not rank candidates, choose an intent, execute behavior, infer hidden world
truth, or mutate motive pressure.
"""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any

from .ids import normalize_id


AFFORDANCE_SNAPSHOT_SCHEMA_VERSION = "1.0"
AFFORDANCE_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS = ("1.0",)
DEFAULT_AFFORDANCE_HISTORY_LIMIT = 128

_SNAPSHOT_KEYS = {
    "schema_version",
    "history_limit",
    "sequence",
    "history",
}
_RECORD_KEYS = {
    "sequence",
    "agent",
    "candidates",
    "context",
}
_CANDIDATE_KEYS = {
    "id",
    "capability",
    "features",
}
_INPUT_CANDIDATE_KEYS = {
    "id",
    "capability",
    "features",
}


def _positive_int(value, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _non_negative_int(value, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _json_copy(value: Any, label: str) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{label} must contain only finite numbers")
        return value
    if isinstance(value, list):
        return [
            _json_copy(item, f"{label}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for raw_key, item in value.items():
            if not isinstance(raw_key, str):
                raise ValueError(f"{label} keys must be strings")
            key = raw_key.strip()
            if not key:
                raise ValueError(f"{label} keys must be non-empty strings")
            if key in normalized:
                raise ValueError(f"{label} contains duplicate normalized key: {key!r}")
            normalized[key] = _json_copy(item, f"{label}.{key}")
        return {key: normalized[key] for key in sorted(normalized)}
    raise ValueError(f"{label} must be strict JSON-safe data")


def _metadata(value, label: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a dict or None")
    return _json_copy(value, label)


def _capability_set(value) -> set[str]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("allowed capabilities must be a list or tuple")
    normalized: set[str] = set()
    for raw in value:
        item = normalize_id(raw, "allowed capability")
        if item in normalized:
            raise ValueError(f"allowed capabilities contains duplicate normalized id: {item!r}")
        normalized.add(item)
    return normalized


def _candidate(value, *, allowed: set[str], label: str) -> dict:
    if isinstance(value, str):
        candidate_id = normalize_id(value, f"{label} id")
        capability = candidate_id
        features = {}
    elif isinstance(value, dict):
        unknown = set(value) - _INPUT_CANDIDATE_KEYS
        if unknown:
            raise ValueError(
                f"{label} has unsupported keys: " + ", ".join(sorted(unknown))
            )
        if "id" not in value:
            raise ValueError(f"{label} is missing required key: id")
        candidate_id = normalize_id(value["id"], f"{label} id")
        raw_capability = value.get("capability", candidate_id)
        capability = normalize_id(raw_capability, f"{label} capability")
        features = _metadata(value.get("features"), f"{label} features")
    else:
        raise ValueError(f"{label} must be a string id or dict")

    if capability not in allowed:
        raise ValueError(
            f"{label} capability is not registered for agent: {capability}"
        )
    return {
        "id": candidate_id,
        "capability": capability,
        "features": features,
    }


def _candidates(value, *, allowed: set[str], label: str) -> list[dict]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{label} must be a list or tuple")
    normalized: dict[str, dict] = {}
    for index, raw in enumerate(value):
        item = _candidate(raw, allowed=allowed, label=f"{label}[{index}]")
        candidate_id = item["id"]
        if candidate_id in normalized:
            raise ValueError(
                f"{label} contains duplicate normalized candidate id: {candidate_id!r}"
            )
        normalized[candidate_id] = item
    return [normalized[key] for key in sorted(normalized)]


def _validate_stored_candidate(value, *, label: str) -> dict:
    if not isinstance(value, dict) or set(value) != _CANDIDATE_KEYS:
        raise ValueError(f"{label} has invalid keys")
    candidate_id = normalize_id(value["id"], f"{label} id")
    capability = normalize_id(value["capability"], f"{label} capability")
    features = _metadata(value["features"], f"{label} features")
    return {
        "id": candidate_id,
        "capability": capability,
        "features": features,
    }


def _validate_record(value, *, agent: str, snapshot_sequence: int, label: str) -> dict:
    if not isinstance(value, dict) or set(value) != _RECORD_KEYS:
        raise ValueError(f"{label} has invalid keys")
    sequence = _positive_int(value["sequence"], f"{label}.sequence")
    if sequence > snapshot_sequence:
        raise ValueError(f"{label}.sequence exceeds snapshot sequence")
    record_agent = normalize_id(value["agent"], f"{label}.agent")
    if record_agent != agent:
        raise ValueError(f"{label}.agent does not match history owner")
    raw_candidates = value["candidates"]
    if not isinstance(raw_candidates, list):
        raise ValueError(f"{label}.candidates must be a list")
    candidates: list[dict] = []
    seen: set[str] = set()
    previous_id: str | None = None
    for index, raw in enumerate(raw_candidates):
        candidate = _validate_stored_candidate(
            raw, label=f"{label}.candidates[{index}]",
        )
        candidate_id = candidate["id"]
        if candidate_id in seen:
            raise ValueError(f"{label}.candidates contains duplicate id: {candidate_id!r}")
        if previous_id is not None and candidate_id <= previous_id:
            raise ValueError(f"{label}.candidates must be canonically ordered by id")
        seen.add(candidate_id)
        previous_id = candidate_id
        candidates.append(candidate)
    return {
        "sequence": sequence,
        "agent": record_agent,
        "candidates": candidates,
        "context": _metadata(value["context"], f"{label}.context"),
    }


class AffordanceRuntime:
    """Persistent audit of host-supplied, currently available agent actions."""

    def __init__(self, history_limit: int = DEFAULT_AFFORDANCE_HISTORY_LIMIT) -> None:
        self.history_limit = _positive_int(
            history_limit, "affordance history_limit",
        )
        self._sequence = 0
        self._history: dict[str, list[dict]] = {}

    def has_state(self) -> bool:
        return bool(self._history)

    def agent_ids(self) -> list[str]:
        return sorted(self._history)

    def history(self, agent, *, limit: int | None = None) -> list[dict]:
        agent = normalize_id(agent, "affordance agent")
        records = self._history.get(agent, [])
        if limit is None:
            return deepcopy(records)
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError(
                "affordance history limit must be a non-negative integer or None"
            )
        if limit == 0:
            return []
        return deepcopy(records[-limit:])

    def current(self, agent) -> dict | None:
        records = self.history(agent, limit=1)
        return records[0] if records else None

    def set(
        self,
        agent,
        candidates,
        *,
        allowed_capabilities,
        context: dict | None = None,
    ) -> dict:
        agent = normalize_id(agent, "affordance agent")
        allowed = _capability_set(allowed_capabilities)
        normalized_candidates = _candidates(
            candidates,
            allowed=allowed,
            label="affordance candidates",
        )
        normalized_context = _metadata(context, "affordance context")
        self._sequence += 1
        record = {
            "sequence": self._sequence,
            "agent": agent,
            "candidates": normalized_candidates,
            "context": normalized_context,
        }
        records = self._history.setdefault(agent, [])
        records.append(deepcopy(record))
        if len(records) > self.history_limit:
            del records[: len(records) - self.history_limit]
        return deepcopy(record)

    def current_capabilities(self, agent) -> list[str]:
        current = self.current(agent)
        if current is None:
            return []
        return sorted({item["capability"] for item in current["candidates"]})

    def snapshot(self) -> dict:
        return {
            "schema_version": AFFORDANCE_SNAPSHOT_SCHEMA_VERSION,
            "history_limit": self.history_limit,
            "sequence": self._sequence,
            "history": deepcopy(self._history),
        }

    @classmethod
    def from_snapshot(cls, snapshot: dict) -> "AffordanceRuntime":
        if not isinstance(snapshot, dict):
            raise ValueError("affordance snapshot must be a dict")
        unknown = set(snapshot) - _SNAPSHOT_KEYS
        if unknown:
            raise ValueError(
                "affordance snapshot has unsupported keys: "
                + ", ".join(sorted(unknown))
            )
        missing = _SNAPSHOT_KEYS - set(snapshot)
        if missing:
            raise ValueError(
                "affordance snapshot is missing required keys: "
                + ", ".join(sorted(missing))
            )
        if snapshot["schema_version"] != AFFORDANCE_SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(
                "unsupported affordance snapshot schema version: "
                f"{snapshot['schema_version']!r}"
            )
        runtime = cls(
            history_limit=_positive_int(
                snapshot["history_limit"], "affordance snapshot history_limit",
            )
        )
        sequence = _non_negative_int(
            snapshot["sequence"], "affordance snapshot sequence",
        )
        raw_history = snapshot["history"]
        if not isinstance(raw_history, dict):
            raise ValueError("affordance snapshot history must be a dict")

        history: dict[str, list[dict]] = {}
        seen_agents: set[str] = set()
        seen_sequences: set[int] = set()
        max_sequence = 0
        for raw_agent, records in raw_history.items():
            if not isinstance(raw_agent, str):
                raise ValueError("affordance snapshot history keys must be strings")
            agent = normalize_id(raw_agent, "affordance snapshot history agent")
            if agent in seen_agents:
                raise ValueError(
                    f"affordance snapshot history contains duplicate normalized agent: {agent}"
                )
            seen_agents.add(agent)
            if not isinstance(records, list):
                raise ValueError(
                    f"affordance snapshot history for {agent} must be a list"
                )
            if not records:
                raise ValueError(
                    f"affordance snapshot history for {agent} must not be empty"
                )
            if len(records) > runtime.history_limit:
                raise ValueError(
                    f"affordance snapshot history for {agent} exceeds history_limit"
                )
            validated: list[dict] = []
            previous_sequence = 0
            for index, raw_record in enumerate(records):
                label = f"affordance snapshot history {agent}[{index}]"
                record = _validate_record(
                    raw_record,
                    agent=agent,
                    snapshot_sequence=sequence,
                    label=label,
                )
                record_sequence = record["sequence"]
                if record_sequence <= previous_sequence:
                    raise ValueError(f"{label}.sequence is invalid")
                if record_sequence in seen_sequences:
                    raise ValueError(f"{label}.sequence is duplicated globally")
                previous_sequence = record_sequence
                seen_sequences.add(record_sequence)
                max_sequence = max(max_sequence, record_sequence)
                validated.append(record)
            history[agent] = validated

        if seen_sequences and max_sequence != sequence:
            raise ValueError(
                "latest affordance history sequence must equal affordance snapshot sequence"
            )
        if not seen_sequences and sequence != 0:
            raise ValueError(
                "empty affordance history requires affordance snapshot sequence 0"
            )
        runtime._sequence = sequence
        runtime._history = {agent: history[agent] for agent in sorted(history)}
        return runtime
