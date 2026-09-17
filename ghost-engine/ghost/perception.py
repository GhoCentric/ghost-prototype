"""Engine-neutral observation contract for Ghost Engine v1.11 development.

The host owns world truth and perception. Ghost receives only structured facts
that the host says one registered agent could observe. Phase 2 records those
facts deterministically; it does not infer hidden truth, mutate beliefs, choose
an action, or call an LLM.
"""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any

from .ids import normalize_id


PERCEPTION_SNAPSHOT_SCHEMA_VERSION = "1.0"
PERCEPTION_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS = frozenset({
    PERCEPTION_SNAPSHOT_SCHEMA_VERSION,
})

PERCEPTION_KINDS = frozenset({
    "direct",
    "report",
    "outcome",
    "environment",
    "social",
})

DEFAULT_PERCEPTION_HISTORY_LIMIT = 128
MAX_PERCEPTION_HISTORY_LIMIT = 4096

_SNAPSHOT_KEYS = {
    "schema_version",
    "history_limit",
    "observers",
}

_OBSERVER_STATE_KEYS = {
    "next_sequence",
    "history",
}

_OBSERVATION_KEYS = {
    "observer",
    "sequence",
    "kind",
    "event",
    "subject",
    "source",
    "features",
}


def _json_safe_copy(value: Any, label: str) -> Any:
    """Return a canonical strict-JSON-safe copy with deterministically sorted keys."""
    if value is None or isinstance(value, (str, bool, int)):
        return value

    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{label} must contain only finite numbers")
        return value

    if isinstance(value, list):
        return [
            _json_safe_copy(item, f"{label}[{index}]")
            for index, item in enumerate(value)
        ]

    if isinstance(value, dict):
        copied = {}
        for key in sorted(value):
            if not isinstance(key, str):
                raise ValueError(f"{label} keys must be strings")
            copied[key] = _json_safe_copy(value[key], f"{label}.{key}")
        return copied

    raise ValueError(f"{label} must be JSON-safe")


def _validate_history_limit(value, label: str = "observation history_limit") -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    if not 1 <= value <= MAX_PERCEPTION_HISTORY_LIMIT:
        raise ValueError(
            f"{label} must be in [1, {MAX_PERCEPTION_HISTORY_LIMIT}]"
        )
    return value


def _normalize_optional_id(value, label: str) -> str | None:
    if value is None:
        return None
    return normalize_id(value, label)


def _normalize_kind(value) -> str:
    if not isinstance(value, str):
        raise ValueError("observation kind must be a string")
    kind = value.strip().lower()
    if kind not in PERCEPTION_KINDS:
        raise ValueError(
            "unsupported observation kind: "
            f"{value!r}; expected one of {sorted(PERCEPTION_KINDS)}"
        )
    return kind


def _normalize_features(value) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("observation features must be a dict or None")
    return _json_safe_copy(value, "observation features")


def _build_observation(
    *,
    observer,
    sequence,
    kind,
    event,
    subject=None,
    source=None,
    features=None,
) -> dict:
    observer = normalize_id(observer, "observation observer")
    event = normalize_id(event, "observation event")
    kind = _normalize_kind(kind)
    subject = _normalize_optional_id(subject, "observation subject")
    source = _normalize_optional_id(source, "observation source")

    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise ValueError("observation sequence must be a positive integer")

    if kind == "report" and source is None:
        raise ValueError("report observations require an explicit source")

    return {
        "observer": observer,
        "sequence": sequence,
        "kind": kind,
        "event": event,
        "subject": subject,
        "source": source,
        "features": _normalize_features(features),
    }




def _validate_restored_observation(
    raw_packet: dict,
    *,
    observer: str,
    index: int,
    previous_sequence: int,
) -> dict:
    label = f"perception snapshot observer {observer!r} history[{index}]"
    if not isinstance(raw_packet, dict):
        raise ValueError(f"{label} must be a dict")
    unknown = set(raw_packet) - _OBSERVATION_KEYS
    if unknown:
        raise ValueError(
            f"{label} has unsupported keys: " + ", ".join(sorted(unknown))
        )
    missing = _OBSERVATION_KEYS - set(raw_packet)
    if missing:
        raise ValueError(
            f"{label} is missing required keys: " + ", ".join(sorted(missing))
        )
    packet = _build_observation(
        observer=raw_packet["observer"],
        sequence=raw_packet["sequence"],
        kind=raw_packet["kind"],
        event=raw_packet["event"],
        subject=raw_packet["subject"],
        source=raw_packet["source"],
        features=raw_packet["features"],
    )
    if packet["observer"] != observer:
        raise ValueError(
            "perception snapshot observer mismatch: "
            f"{observer!r} != {packet['observer']!r}"
        )
    if packet["sequence"] <= previous_sequence:
        raise ValueError(
            f"perception snapshot observer {observer!r} history sequence "
            "must be strictly increasing"
        )
    return packet


def _restore_perception_observer_state(
    state: dict,
    *,
    observer: str,
    history_limit: int,
) -> tuple[list[dict], int]:
    if not isinstance(state, dict):
        raise ValueError(f"perception snapshot observer {observer!r} must be a dict")
    unknown = set(state) - _OBSERVER_STATE_KEYS
    if unknown:
        raise ValueError(
            f"perception snapshot observer {observer!r} has unsupported keys: "
            + ", ".join(sorted(unknown))
        )
    missing = _OBSERVER_STATE_KEYS - set(state)
    if missing:
        raise ValueError(
            f"perception snapshot observer {observer!r} is missing required keys: "
            + ", ".join(sorted(missing))
        )
    next_sequence = state["next_sequence"]
    if (
        isinstance(next_sequence, bool)
        or not isinstance(next_sequence, int)
        or next_sequence < 1
    ):
        raise ValueError(
            f"perception snapshot observer {observer!r} next_sequence "
            "must be a positive integer"
        )
    history = state["history"]
    if not isinstance(history, list):
        raise ValueError(
            f"perception snapshot observer {observer!r} history must be a list"
        )
    if len(history) > history_limit:
        raise ValueError(
            f"perception snapshot observer {observer!r} history exceeds history_limit"
        )
    validated: list[dict] = []
    previous = 0
    for index, raw_packet in enumerate(history):
        packet = _validate_restored_observation(
            raw_packet,
            observer=observer,
            index=index,
            previous_sequence=previous,
        )
        previous = packet["sequence"]
        validated.append(packet)
    if validated:
        if next_sequence != validated[-1]["sequence"] + 1:
            raise ValueError(
                f"perception snapshot observer {observer!r} next_sequence "
                "must immediately follow the latest retained observation"
            )
    elif next_sequence != 1:
        raise ValueError(
            f"perception snapshot observer {observer!r} empty history "
            "requires next_sequence 1"
        )
    return validated, next_sequence


class PerceptionRuntime:
    """Persistent bounded observation ledger, partitioned by observing agent."""

    def __init__(self, *, history_limit: int = DEFAULT_PERCEPTION_HISTORY_LIMIT) -> None:
        self._history_limit = _validate_history_limit(history_limit)
        self._history: dict[str, list[dict]] = {}
        self._next_sequence: dict[str, int] = {}

    @property
    def history_limit(self) -> int:
        return self._history_limit

    def record(
        self,
        observer,
        event,
        *,
        kind: str = "direct",
        subject=None,
        source=None,
        features: dict | None = None,
    ) -> dict:
        observer = normalize_id(observer, "observation observer")
        sequence = self._next_sequence.get(observer, 1)
        packet = _build_observation(
            observer=observer,
            sequence=sequence,
            kind=kind,
            event=event,
            subject=subject,
            source=source,
            features=features,
        )

        history = self._history.setdefault(observer, [])
        history.append(packet)
        if len(history) > self._history_limit:
            del history[: len(history) - self._history_limit]
        self._next_sequence[observer] = sequence + 1
        return deepcopy(packet)

    def history(self, observer, *, limit: int | None = None) -> list[dict]:
        observer = normalize_id(observer, "observation observer")
        history = self._history.get(observer, [])
        if limit is None:
            selected = history
        else:
            limit = _validate_history_limit(limit, "observation history read limit")
            selected = history[-limit:]
        return deepcopy(selected)

    def latest(self, observer) -> dict | None:
        observer = normalize_id(observer, "observation observer")
        history = self._history.get(observer)
        if not history:
            return None
        return deepcopy(history[-1])

    def get_state(self, observer) -> dict | None:
        observer = normalize_id(observer, "observation observer")
        if observer not in self._next_sequence:
            return None
        return {
            "observer": observer,
            "history_limit": self._history_limit,
            "next_sequence": self._next_sequence[observer],
            "history": deepcopy(self._history[observer]),
        }

    def has_state(self) -> bool:
        return bool(self._next_sequence)

    def observer_ids(self) -> list[str]:
        """Return registered perception-ledger owners in stable order."""
        return sorted(self._next_sequence)

    def snapshot(self) -> dict:
        return {
            "schema_version": PERCEPTION_SNAPSHOT_SCHEMA_VERSION,
            "history_limit": self._history_limit,
            "observers": {
                observer: {
                    "next_sequence": self._next_sequence[observer],
                    "history": deepcopy(self._history[observer]),
                }
                for observer in sorted(self._next_sequence)
            },
        }

    @classmethod
    def from_snapshot(cls, snapshot: dict) -> "PerceptionRuntime":
        if not isinstance(snapshot, dict):
            raise ValueError("perception snapshot must be a dict")
        unknown = set(snapshot) - _SNAPSHOT_KEYS
        if unknown:
            raise ValueError(
                "perception snapshot has unsupported keys: "
                + ", ".join(sorted(unknown))
            )
        missing = _SNAPSHOT_KEYS - set(snapshot)
        if missing:
            raise ValueError(
                "perception snapshot is missing required keys: "
                + ", ".join(sorted(missing))
            )
        schema_version = snapshot["schema_version"]
        if schema_version not in PERCEPTION_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS:
            raise ValueError(
                "unsupported perception snapshot schema version: "
                f"{schema_version!r}"
            )
        history_limit = _validate_history_limit(snapshot["history_limit"])
        observers = snapshot["observers"]
        if not isinstance(observers, dict):
            raise ValueError("perception snapshot observers must be a dict")
        runtime = cls(history_limit=history_limit)
        for raw_observer in sorted(observers):
            observer = normalize_id(raw_observer, "perception snapshot observer")
            history, next_sequence = _restore_perception_observer_state(
                observers[raw_observer],
                observer=observer,
                history_limit=history_limit,
            )
            runtime._history[observer] = history
            runtime._next_sequence[observer] = next_sequence
        return runtime

