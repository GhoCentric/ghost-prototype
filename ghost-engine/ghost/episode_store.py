"""Durable causal-episode storage for Ghost continuity.

This module is the production descendant of the M3T storage boundary.  Current
Ghost state stays in the normal JSON snapshot while exact historical causal
episodes live in an indexed SQLite archive.  The archive is append-only: it
never silently evicts, consolidates, or reinterprets retained episodes.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from typing import Any


EPISODE_ARCHIVE_SCHEMA = "ghost.causal_episode_archive.v1"
EPISODE_ARCHIVE_MANIFEST_SCHEMA = "ghost.causal_episode_archive_manifest.v1"
_EPSILON = 1e-12


class EpisodeCapacityError(RuntimeError):
    """Raised when an explicit archive capacity is reached."""


class EpisodeIntegrityError(RuntimeError):
    """Raised when durable archive metadata or content is inconsistent."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _finite_signed_unit(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be a finite number")
    if not -1.0 <= number <= 1.0:
        raise ValueError(f"{label} must be in [-1, 1]")
    return number


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _optional_positive_int(value: Any, label: str) -> int | None:
    if value is None:
        return None
    return _positive_int(value, label)


def _token(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _json_safe(value: Any, label: str) -> None:
    try:
        encoded = _canonical_json(value)
        json.loads(encoded)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{label} must be JSON-safe") from exc


def _sparse_profile(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        raise ValueError("emotion_profile must be a dict")
    out: dict[str, float] = {}
    for raw_name, raw_value in value.items():
        name = _token(raw_name, "emotion_profile name")
        if name in out:
            raise ValueError(f"duplicate emotion_profile name: {name}")
        number = _finite_signed_unit(raw_value, f"emotion_profile.{name}")
        if abs(number) > _EPSILON:
            out[name] = number
    return dict(sorted(out.items()))


class SQLiteEpisodeArchive:
    """Append-only indexed store for compact causal episode records."""

    ZERO_DIGEST = hashlib.sha256(b"ghost.causal_episode_archive.empty").hexdigest()
    REQUIRED_FIELDS = {
        "episode_id",
        "agent",
        "dimension",
        "interpretation_sequence",
        "interpretation_source",
        "emotion_sequence",
        "emotion_event",
        "emotion_profile",
    }

    def __init__(
        self,
        path: str | Path,
        *,
        max_records: int | None = None,
        create: bool = True,
    ) -> None:
        self.path = Path(path)
        if max_records is not None:
            max_records = _positive_int(max_records, "max_records")
        self.max_records = max_records
        self._con = sqlite3.connect(str(self.path))
        ready = False
        try:
            self._con.execute("PRAGMA foreign_keys=ON")
            self._con.execute("PRAGMA synchronous=FULL")
            self._con.execute("PRAGMA journal_mode=DELETE")
            if create:
                self._initialize()
            self._verify_schema()
            ready = True
        finally:
            if not ready:
                self._con.close()

    def _initialize(self) -> None:
        with self._con:
            self._con.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            self._con.execute(
                """
                CREATE TABLE IF NOT EXISTS episodes(
                    episode_id TEXT PRIMARY KEY,
                    agent TEXT NOT NULL,
                    dimension TEXT NOT NULL,
                    interpretation_sequence INTEGER NOT NULL,
                    interpretation_source_json TEXT NOT NULL,
                    emotion_sequence INTEGER,
                    emotion_event_json TEXT NOT NULL,
                    emotion_profile_json TEXT NOT NULL,
                    record_hash TEXT NOT NULL
                )
                """
            )
            self._con.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_episodes_agent_dimension
                ON episodes(agent, dimension, interpretation_sequence,
                            emotion_sequence, episode_id)
                """
            )
            self._set_meta_default("schema", EPISODE_ARCHIVE_SCHEMA)
            self._set_meta_default("record_count", "0")
            self._set_meta_default("content_digest", self.ZERO_DIGEST)

    def _set_meta_default(self, key: str, value: str) -> None:
        self._con.execute(
            "INSERT OR IGNORE INTO metadata(key,value) VALUES(?,?)",
            (key, value),
        )

    def _meta(self, key: str) -> str:
        row = self._con.execute(
            "SELECT value FROM metadata WHERE key=?",
            (key,),
        ).fetchone()
        if row is None:
            raise EpisodeIntegrityError(f"missing archive metadata: {key}")
        return str(row[0])

    def _verify_schema(self) -> None:
        try:
            schema = self._meta("schema")
            count = int(self._meta("record_count"))
            content_digest = self._meta("content_digest")
        except (sqlite3.DatabaseError, ValueError) as exc:
            raise EpisodeIntegrityError("invalid episode archive metadata") from exc
        if schema != EPISODE_ARCHIVE_SCHEMA:
            raise EpisodeIntegrityError("unsupported episode archive schema")
        actual = int(self._con.execute("SELECT COUNT(*) FROM episodes").fetchone()[0])
        if count != actual:
            raise EpisodeIntegrityError(
                f"archive record_count mismatch: metadata={count}, actual={actual}"
            )
        if len(content_digest) != 64:
            raise EpisodeIntegrityError("invalid archive content digest")

    @staticmethod
    def make_episode_id(
        agent: str,
        interpretation_sequence: int,
        emotion_sequence: int | None,
    ) -> str:
        agent = _token(agent, "episode agent")
        interpretation_sequence = _positive_int(
            interpretation_sequence,
            "interpretation_sequence",
        )
        emotion_sequence = _optional_positive_int(emotion_sequence, "emotion_sequence")
        emotion_part = "none" if emotion_sequence is None else str(emotion_sequence)
        return f"{agent}:i{interpretation_sequence}:e{emotion_part}"

    @classmethod
    def validate_record(cls, row: Any) -> dict[str, Any]:
        if not isinstance(row, dict) or set(row) != cls.REQUIRED_FIELDS:
            raise ValueError("invalid causal episode record shape")
        clean = deepcopy(row)
        clean["agent"] = _token(clean["agent"], "episode agent")
        clean["dimension"] = _token(clean["dimension"], "episode dimension")
        clean["interpretation_sequence"] = _positive_int(
            clean["interpretation_sequence"],
            "interpretation_sequence",
        )
        clean["emotion_sequence"] = _optional_positive_int(
            clean["emotion_sequence"],
            "emotion_sequence",
        )
        expected_id = cls.make_episode_id(
            clean["agent"],
            clean["interpretation_sequence"],
            clean["emotion_sequence"],
        )
        if clean["episode_id"] != expected_id:
            raise ValueError("episode_id does not match source sequences")
        clean["emotion_profile"] = _sparse_profile(clean["emotion_profile"])
        _json_safe(clean["interpretation_source"], "interpretation_source")
        _json_safe(clean["emotion_event"], "emotion_event")
        return clean

    @classmethod
    def record_from_entries(
        cls,
        *,
        agent: str,
        dimension: str,
        interpretation_entry: dict[str, Any],
        emotion_entry: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not isinstance(interpretation_entry, dict):
            raise ValueError("interpretation_entry must be a dict")
        transition = (interpretation_entry.get("transitions") or {}).get(dimension)
        if transition is None:
            raise ValueError(f"interpretation entry has no {dimension!r} transition")
        if float(transition.get("effective_impulse", 0.0)) <= 0.0:
            raise ValueError("episode origin must positively establish interpretation")
        interpretation_sequence = _positive_int(
            interpretation_entry.get("sequence"),
            "interpretation_entry.sequence",
        )
        if emotion_entry is None:
            emotion_sequence = None
            emotion_event = None
            profile: dict[str, float] = {}
        else:
            if not isinstance(emotion_entry, dict):
                raise ValueError("emotion_entry must be a dict or None")
            emotion_sequence = _positive_int(
                emotion_entry.get("sequence"),
                "emotion_entry.sequence",
            )
            emotion_event = emotion_entry.get("event")
            profile = _sparse_profile(emotion_entry.get("profile") or {})
        row = {
            "episode_id": cls.make_episode_id(
                agent,
                interpretation_sequence,
                emotion_sequence,
            ),
            "agent": agent,
            "dimension": dimension,
            "interpretation_sequence": interpretation_sequence,
            "interpretation_source": interpretation_entry.get("source"),
            "emotion_sequence": emotion_sequence,
            "emotion_event": emotion_event,
            "emotion_profile": profile,
        }
        return cls.validate_record(row)

    @staticmethod
    def _record_hash(record: dict[str, Any]) -> str:
        return hashlib.sha256(_canonical_json(record).encode("utf-8")).hexdigest()

    def _encode(self, record: dict[str, Any]) -> tuple[Any, ...]:
        clean = self.validate_record(record)
        return (
            clean["episode_id"],
            clean["agent"],
            clean["dimension"],
            clean["interpretation_sequence"],
            _canonical_json(clean["interpretation_source"]),
            clean["emotion_sequence"],
            _canonical_json(clean["emotion_event"]),
            _canonical_json(clean["emotion_profile"]),
            self._record_hash(clean),
        )

    def _decode(self, row: tuple[Any, ...]) -> dict[str, Any]:
        record = {
            "episode_id": row[0],
            "agent": row[1],
            "dimension": row[2],
            "interpretation_sequence": int(row[3]),
            "interpretation_source": json.loads(row[4]),
            "emotion_sequence": None if row[5] is None else int(row[5]),
            "emotion_event": json.loads(row[6]),
            "emotion_profile": json.loads(row[7]),
        }
        clean = self.validate_record(record)
        if self._record_hash(clean) != row[8]:
            raise EpisodeIntegrityError(
                f"causal episode integrity hash mismatch: {clean['episode_id']}"
            )
        return clean

    @staticmethod
    def _advance_digest(previous: str, record: dict[str, Any]) -> str:
        payload = previous.encode("ascii") + b"\0" + _canonical_json(record).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def put_record(self, record: dict[str, Any]) -> dict[str, Any]:
        clean = self.validate_record(record)
        existing = self.get(clean["episode_id"])
        if existing is not None:
            if existing != clean:
                raise ValueError(
                    f"episode id collision with different content: {clean['episode_id']}"
                )
            return existing
        count = self.count()
        if self.max_records is not None and count >= self.max_records:
            raise EpisodeCapacityError(
                f"episode archive capacity reached ({self.max_records}); "
                "no record was silently evicted"
            )
        next_digest = self._advance_digest(self._meta("content_digest"), clean)
        with self._con:
            self._con.execute(
                """
                INSERT INTO episodes(
                    episode_id,agent,dimension,interpretation_sequence,
                    interpretation_source_json,emotion_sequence,
                    emotion_event_json,emotion_profile_json,record_hash
                ) VALUES(?,?,?,?,?,?,?,?,?)
                """,
                self._encode(clean),
            )
            self._con.execute(
                "UPDATE metadata SET value=? WHERE key='record_count'",
                (str(count + 1),),
            )
            self._con.execute(
                "UPDATE metadata SET value=? WHERE key='content_digest'",
                (next_digest,),
            )
        return deepcopy(clean)

    def register(
        self,
        *,
        agent: str,
        dimension: str,
        interpretation_entry: dict[str, Any],
        emotion_entry: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return self.put_record(
            self.record_from_entries(
                agent=agent,
                dimension=dimension,
                interpretation_entry=interpretation_entry,
                emotion_entry=emotion_entry,
            )
        )

    def get(self, episode_id: str) -> dict[str, Any] | None:
        row = self._con.execute(
            """
            SELECT episode_id,agent,dimension,interpretation_sequence,
                   interpretation_source_json,emotion_sequence,
                   emotion_event_json,emotion_profile_json,record_hash
            FROM episodes WHERE episode_id=?
            """,
            (str(episode_id),),
        ).fetchone()
        return None if row is None else deepcopy(self._decode(row))

    def for_dimension(
        self,
        agent: str,
        dimension: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        agent = _token(agent, "episode agent")
        dimension = _token(dimension, "episode dimension")
        if limit is not None:
            limit = _positive_int(limit, "limit")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        sql = """
            SELECT episode_id,agent,dimension,interpretation_sequence,
                   interpretation_source_json,emotion_sequence,
                   emotion_event_json,emotion_profile_json,record_hash
            FROM episodes
            WHERE agent=? AND dimension=?
            ORDER BY interpretation_sequence,
                     COALESCE(emotion_sequence,-1),
                     episode_id
        """
        args: list[Any] = [agent, dimension]
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            args.extend([limit, offset])
        rows = self._con.execute(sql, args).fetchall()
        return [deepcopy(self._decode(row)) for row in rows]

    def resolve_dimension(self, agent: str, dimension: str) -> dict[str, Any]:
        agent = _token(agent, "episode agent")
        dimension = _token(dimension, "episode dimension")
        count = int(
            self._con.execute(
                "SELECT COUNT(*) FROM episodes WHERE agent=? AND dimension=?",
                (agent, dimension),
            ).fetchone()[0]
        )
        if count == 0:
            return {
                "status": "missing",
                "agent": agent,
                "dimension": dimension,
                "candidate_count": 0,
                "record": None,
            }
        if count > 1:
            return {
                "status": "ambiguous",
                "agent": agent,
                "dimension": dimension,
                "candidate_count": count,
                "episode_ids": [
                    row["episode_id"] for row in self.for_dimension(agent, dimension)
                ],
                "record": None,
            }
        record = self.for_dimension(agent, dimension, limit=1)[0]
        return {
            "status": "unique",
            "agent": agent,
            "dimension": dimension,
            "candidate_count": 1,
            "record": record,
        }

    def count(self) -> int:
        return int(self._meta("record_count"))

    def manifest(self) -> dict[str, Any]:
        return {
            "schema": EPISODE_ARCHIVE_MANIFEST_SCHEMA,
            "archive_schema": EPISODE_ARCHIVE_SCHEMA,
            "record_count": self.count(),
            "content_digest": self._meta("content_digest"),
        }

    def verify_manifest(self, manifest: Any) -> None:
        if manifest != self.manifest():
            raise EpisodeIntegrityError(
                "episode archive manifest does not match Ghost snapshot"
            )

    def logical_records(self) -> list[dict[str, Any]]:
        rows = self._con.execute(
            """
            SELECT episode_id,agent,dimension,interpretation_sequence,
                   interpretation_source_json,emotion_sequence,
                   emotion_event_json,emotion_profile_json,record_hash
            FROM episodes ORDER BY episode_id
            """
        ).fetchall()
        return [deepcopy(self._decode(row)) for row in rows]

    def close(self) -> None:
        history_archive = getattr(self, "_continuity_history_archive", None)
        if history_archive is not None:
            history_archive.close()
            self._continuity_history_archive = None
        self._con.close()

    def __len__(self) -> int:
        return self.count()
