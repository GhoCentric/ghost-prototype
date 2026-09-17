"""Competent purpose-built baseline for the frozen continuity comparison.

The baseline intentionally includes durable exact episode identity, a SQLite
archive outside the hot snapshot, explicit capacity backpressure, exact recall,
and pairwise hysteresis.  It remains simpler than Ghost by directly owning
meaning, present relevance, affect, consequence state, and foreground in one
small runtime rather than delegating those semantics across Ghost subsystems.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sqlite3

from .contract import (
    BASELINE_EMOTION_RETENTION,
    BASELINE_RELEASE_RATE,
    BASELINE_SWITCH_THRESHOLD,
    ArchiveMismatchError,
    CapacityBackpressureError,
)


FOREGROUND_ACTIVE_EPSILON = 1e-8


class BaselineCapacityError(CapacityBackpressureError):
    """Purpose-built baseline capacity backpressure."""


class BaselineIntegrityError(ArchiveMismatchError):
    """Purpose-built baseline archive/snapshot integrity failure."""


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _positive_update(current: float, impulse: float) -> float:
    strength = _clamp(impulse)
    return current + strength * (1.0 - current)


class SimpleEpisodeArchive:
    SCHEMA = "1.0"

    def __init__(self, path: str | Path, *, max_records: int | None = None) -> None:
        self.path = Path(path)
        self.max_records = max_records
        self._con = sqlite3.connect(self.path)
        try:
            self._initialize()
        except Exception:
            self._con.close()
            raise

    def _initialize(self) -> None:
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS episodes(
                episode_id TEXT PRIMARY KEY,
                ordinal INTEGER NOT NULL,
                agent TEXT NOT NULL,
                dimension TEXT NOT NULL,
                source TEXT NOT NULL,
                meaning_delta REAL NOT NULL,
                emotion_json TEXT NOT NULL,
                consequence REAL NOT NULL,
                record_hash TEXT NOT NULL
            )
            """
        )
        self._con.execute(
            "CREATE INDEX IF NOT EXISTS idx_simple_episode_dimension "
            "ON episodes(agent,dimension,ordinal)"
        )
        self._con.execute(
            "CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)"
        )
        for key, value in (
            ("schema", self.SCHEMA),
            ("content_digest", "0" * 64),
        ):
            self._con.execute(
                "INSERT OR IGNORE INTO metadata(key,value) VALUES(?,?)", (key, value)
            )
        self._con.commit()
        if self._meta("schema") != self.SCHEMA:
            raise BaselineIntegrityError("unsupported baseline archive schema")

    def _meta(self, key: str) -> str:
        row = self._con.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
        if row is None:
            raise BaselineIntegrityError(f"missing baseline archive metadata: {key}")
        return str(row[0])

    def count(self) -> int:
        return int(self._con.execute("SELECT COUNT(*) FROM episodes").fetchone()[0])

    def can_accept(self) -> bool:
        return self.max_records is None or self.count() < self.max_records

    def _next_ordinal(self) -> int:
        return int(
            self._con.execute("SELECT COALESCE(MAX(ordinal),0)+1 FROM episodes").fetchone()[0]
        )

    def add(
        self,
        *,
        agent: str,
        dimension: str,
        source: str,
        meaning_delta: float,
        emotion_profile: dict[str, float],
        consequence: float,
    ) -> dict:
        if not self.can_accept():
            raise BaselineCapacityError("baseline episode archive is at explicit capacity")
        ordinal = self._next_ordinal()
        identity = {
            "agent": str(agent),
            "dimension": str(dimension),
            "ordinal": ordinal,
            "source": str(source),
        }
        episode_id = _digest(identity)
        record = {
            "episode_id": episode_id,
            "ordinal": ordinal,
            "agent": str(agent),
            "dimension": str(dimension),
            "source": str(source),
            "meaning_delta": float(meaning_delta),
            "emotion_profile": dict(sorted((str(k), float(v)) for k, v in emotion_profile.items())),
            "consequence": float(consequence),
        }
        record_hash = _digest(record)
        self._con.execute(
            "INSERT INTO episodes VALUES(?,?,?,?,?,?,?,?,?)",
            (
                episode_id,
                ordinal,
                record["agent"],
                record["dimension"],
                record["source"],
                record["meaning_delta"],
                _canonical(record["emotion_profile"]),
                record["consequence"],
                record_hash,
            ),
        )
        previous = self._meta("content_digest")
        next_digest = _digest({"previous": previous, "record": record})
        self._con.execute(
            "UPDATE metadata SET value=? WHERE key='content_digest'", (next_digest,)
        )
        self._con.commit()
        return deepcopy(record)

    def _decode(self, row) -> dict:
        record = {
            "episode_id": row[0],
            "ordinal": int(row[1]),
            "agent": row[2],
            "dimension": row[3],
            "source": row[4],
            "meaning_delta": float(row[5]),
            "emotion_profile": json.loads(row[6]),
            "consequence": float(row[7]),
        }
        if _digest(record) != row[8]:
            raise BaselineIntegrityError(f"baseline episode record hash mismatch: {row[0]}")
        return record

    def get(self, episode_id: str) -> dict | None:
        row = self._con.execute(
            "SELECT episode_id,ordinal,agent,dimension,source,meaning_delta,"
            "emotion_json,consequence,record_hash FROM episodes WHERE episode_id=?",
            (str(episode_id),),
        ).fetchone()
        return None if row is None else deepcopy(self._decode(row))

    def for_dimension(self, agent: str, dimension: str) -> list[dict]:
        rows = self._con.execute(
            "SELECT episode_id,ordinal,agent,dimension,source,meaning_delta,"
            "emotion_json,consequence,record_hash FROM episodes "
            "WHERE agent=? AND dimension=? ORDER BY ordinal,episode_id",
            (str(agent), str(dimension)),
        ).fetchall()
        return [deepcopy(self._decode(row)) for row in rows]

    def resolve_dimension(self, agent: str, dimension: str) -> dict:
        records = self.for_dimension(agent, dimension)
        if not records:
            return {"status": "missing", "candidate_count": 0, "record": None}
        if len(records) > 1:
            return {
                "status": "ambiguous",
                "candidate_count": len(records),
                "episode_ids": [row["episode_id"] for row in records],
                "record": None,
            }
        return {"status": "unique", "candidate_count": 1, "record": records[0]}

    def manifest(self) -> dict:
        return {
            "schema": self._meta("schema"),
            "record_count": self.count(),
            "content_digest": self._meta("content_digest"),
        }

    def verify_manifest(self, manifest: dict) -> None:
        if manifest != self.manifest():
            raise BaselineIntegrityError("baseline archive manifest mismatch")

    def close(self) -> None:
        self._con.close()


class PurposeBuiltContinuity:
    SNAPSHOT_SCHEMA = "1.0"

    def __init__(
        self,
        archive_path: str | Path,
        *,
        max_records: int | None = None,
        snapshot: dict | None = None,
    ) -> None:
        self.archive = SimpleEpisodeArchive(archive_path, max_records=max_records)
        self._agents: dict[str, dict] = {}
        try:
            if snapshot is not None:
                self._restore(snapshot)
        except Exception:
            self.archive.close()
            raise

    def _agent(self, agent: str) -> dict:
        key = str(agent)
        if key not in self._agents:
            self._agents[key] = {
                "meaning": {},
                "activation": {},
                "emotion": dict((name, 0.0) for name in BASELINE_EMOTION_RETENTION),
                "trust": 0.0,
                "foreground": None,
                "tick": 0,
            }
        return self._agents[key]

    def _resolve_foreground(self, state: dict) -> None:
        values = dict(sorted(state["activation"].items()))
        raw = None if not values else min(values, key=lambda key: (-values[key], key))
        if raw is not None and values[raw] <= FOREGROUND_ACTIVE_EPSILON:
            raw = None
        previous = state["foreground"]
        if raw is None:
            state["foreground"] = None
        elif previous is None or previous not in values or values.get(previous, 0.0) <= 0.0:
            state["foreground"] = raw
        elif raw != previous:
            challenger = values[raw]
            incumbent = values[previous]
            total = challenger + incumbent
            advantage = 0.0 if total <= 0.0 else (challenger - incumbent) / total
            if advantage + 1e-12 >= BASELINE_SWITCH_THRESHOLD:
                state["foreground"] = raw

    def event(
        self,
        agent: str,
        *,
        source: str,
        dimension: str,
        meaning_delta: float,
        relevance: float,
        emotion_profile: dict[str, float] | None = None,
        consequence: float = 0.0,
    ) -> dict:
        state = self._agent(agent)
        before = deepcopy(state)
        if not self.archive.can_accept():
            raise BaselineCapacityError("baseline episode archive is at explicit capacity")
        profile = {} if emotion_profile is None else dict(emotion_profile)
        try:
            record = self.archive.add(
                agent=agent,
                dimension=dimension,
                source=source,
                meaning_delta=meaning_delta,
                emotion_profile=profile,
                consequence=consequence,
            )
            state["meaning"][dimension] = _clamp(
                state["meaning"].get(dimension, 0.0) + float(meaning_delta)
            )
            state["activation"][dimension] = _positive_update(
                state["activation"].get(dimension, 0.0), relevance
            )
            for name, impulse in profile.items():
                state["emotion"][name] = _positive_update(
                    state["emotion"].get(name, 0.0), impulse
                )
            state["trust"] += float(consequence)
            self._resolve_foreground(state)
            return record
        except Exception:
            self._agents[str(agent)] = before
            raise

    def revise(self, agent: str, dimension: str, meaning_delta: float) -> None:
        state = self._agent(agent)
        state["meaning"][dimension] = _clamp(
            state["meaning"].get(dimension, 0.0) + float(meaning_delta)
        )
        state["activation"][dimension] = _positive_update(
            state["activation"].get(dimension, 0.0), abs(float(meaning_delta))
        )
        self._resolve_foreground(state)

    def tick(self, agent: str, steps: int = 1) -> None:
        state = self._agent(agent)
        retention = (1.0 - BASELINE_RELEASE_RATE) ** int(steps)
        for dimension in state["activation"]:
            state["activation"][dimension] *= retention
        for name, value in state["emotion"].items():
            state["emotion"][name] = value * (BASELINE_EMOTION_RETENTION[name] ** int(steps))
        state["tick"] += int(steps)
        self._resolve_foreground(state)

    def recall_episode(self, episode_id: str, strength: float) -> dict:
        record = self.archive.get(episode_id)
        if record is None:
            raise KeyError(f"unknown baseline episode: {episode_id}")
        state = self._agent(record["agent"])
        meaning_before = deepcopy(state["meaning"])
        state["activation"][record["dimension"]] = _positive_update(
            state["activation"].get(record["dimension"], 0.0), strength
        )
        for name, impulse in record["emotion_profile"].items():
            state["emotion"][name] = _positive_update(
                state["emotion"].get(name, 0.0), float(impulse) * float(strength)
            )
        self._resolve_foreground(state)
        return {
            "status": "explicit_episode",
            "episode_id": record["episode_id"],
            "record": deepcopy(record),
            "meaning_unchanged": state["meaning"] == meaning_before,
        }

    def recall_dimension(self, agent: str, dimension: str, strength: float) -> dict:
        lookup = self.archive.resolve_dimension(agent, dimension)
        if lookup["status"] != "unique":
            return deepcopy(lookup)
        result = self.recall_episode(lookup["record"]["episode_id"], strength)
        return {
            "status": "unique",
            "candidate_count": 1,
            "record": deepcopy(lookup["record"]),
            "recall": result,
        }

    def episodes_for_dimension(self, agent: str, dimension: str) -> list[dict]:
        return self.archive.for_dimension(agent, dimension)

    def get_episode(self, episode_id: str) -> dict | None:
        return self.archive.get(episode_id)

    def archive_manifest(self) -> dict:
        return self.archive.manifest()

    def near_tie_trace(self, steps: int = 100) -> list[str | None]:
        state = self._agent("__near_tie_probe__")
        trace = []
        for tick in range(int(steps)):
            if tick % 2 == 0:
                state["activation"] = {"anger": 0.5001, "threat": 0.4999}
            else:
                state["activation"] = {"anger": 0.4999, "threat": 0.5001}
            self._resolve_foreground(state)
            trace.append(state["foreground"])
        return trace

    def observe(self, agent: str) -> dict:
        state = deepcopy(self._agent(agent))
        return {
            "meaning": dict(sorted(state["meaning"].items())),
            "activation": dict(sorted(state["activation"].items())),
            "emotion": dict(sorted(state["emotion"].items())),
            "trust": state["trust"],
            "foreground": state["foreground"],
            "tick": state["tick"],
            "episode_count": self.archive.count(),
        }

    def snapshot(self) -> dict:
        return {
            "schema": self.SNAPSHOT_SCHEMA,
            "agents": deepcopy(dict(sorted(self._agents.items()))),
            "episode_archive": self.archive.manifest(),
        }

    def _restore(self, snapshot: dict) -> None:
        if not isinstance(snapshot, dict) or set(snapshot) != {
            "schema", "agents", "episode_archive"
        }:
            raise BaselineIntegrityError("baseline hot snapshot is invalid")
        if snapshot["schema"] != self.SNAPSHOT_SCHEMA:
            raise BaselineIntegrityError("unsupported baseline hot snapshot schema")
        self.archive.verify_manifest(snapshot["episode_archive"])
        self._agents = deepcopy(snapshot["agents"])

    def close(self) -> None:
        self.archive.close()
