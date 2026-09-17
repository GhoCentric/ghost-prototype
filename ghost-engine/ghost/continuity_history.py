"""Lossless compact storage for continuity diagnostic history.

Exact causal episodes remain owned by :mod:`ghost.episode_store`.  This sidecar
stores only the pre-existing bounded interpretation, emotion, and attention
history that would otherwise occupy every hot Ghost snapshot.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any
import zlib

from .episode_store import EpisodeIntegrityError


CONTINUITY_HISTORY_SCHEMA = "ghost.continuity_history.v1"
CONTINUITY_HISTORY_MANIFEST_SCHEMA = "ghost.continuity_history_manifest.v1"
COMPRESSION_LEVEL = 6
COLD_HISTORY_LIMIT = 64


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _history_tokens(subsystem: str, record: dict[str, Any]) -> list[str]:
    if subsystem == "interpretation":
        source = record.get("transitions", {})
    elif subsystem == "emotion":
        source = record.get("effective_impulses", {})
    elif subsystem == "attention":
        source = record.get("underlying_salience", {})
    else:
        raise ValueError(f"unknown continuity-history subsystem: {subsystem}")
    if not isinstance(source, dict):
        raise ValueError("continuity-history projection source must be a mapping")
    return sorted(str(token) for token in source)


def _positive_sequence(record: dict[str, Any]) -> int:
    sequence = record.get("sequence")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise ValueError("continuity-history sequence must be a positive integer")
    return sequence


class PendingContinuityHistory:
    def __init__(self) -> None:
        self._rows: dict[tuple[str, str, int], dict[str, Any]] = {}

    def stage(self, rows: list[tuple[str, str, dict[str, Any]]]) -> None:
        clean: list[tuple[tuple[str, str, int], dict[str, Any]]] = []
        touched: set[tuple[str, str]] = set()
        for subsystem, agent, record in rows:
            subsystem = str(subsystem)
            agent = str(agent)
            _history_tokens(subsystem, record)
            key = (subsystem, agent, _positive_sequence(record))
            existing = self._rows.get(key)
            if existing is not None and existing != record:
                raise EpisodeIntegrityError("pending continuity-history sequence collision with different content")
            clean.append((key, deepcopy(record)))
            touched.add((subsystem, agent))
        for key, record in clean:
            self._rows[key] = record
        for subsystem, agent in touched:
            keys = sorted(
                key for key in self._rows
                if key[:2] == (subsystem, agent)
            )
            for key in keys[:-COLD_HISTORY_LIMIT]:
                del self._rows[key]

    def rows(self) -> list[tuple[str, str, dict[str, Any]]]:
        return [
            (subsystem, agent, deepcopy(record))
            for (subsystem, agent, _), record in sorted(self._rows.items())
        ]

    def records(self, subsystem: str, agent: str) -> list[dict[str, Any]]:
        return [
            deepcopy(record)
            for (name, owner, _), record in sorted(self._rows.items())
            if (name, owner) == (str(subsystem), str(agent))
        ]

    def projection_rows(self, subsystem: str, agent: str) -> list[tuple[int, list[str]]]:
        return [
            (sequence, _history_tokens(name, record))
            for (name, owner, sequence), record in sorted(self._rows.items())
            if (name, owner) == (str(subsystem), str(agent))
        ]



class CompactContinuityHistoryArchive:
    """Lossless zlib-6 sidecar for bounded subsystem diagnostic history."""

    def __init__(self, path: str | Path, *, create: bool = True) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(str(self.path))
        ready = False
        try:
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
                "CREATE TABLE IF NOT EXISTS metadata("
                "key TEXT PRIMARY KEY,value TEXT NOT NULL)"
            )
            self._con.execute(
                "CREATE TABLE IF NOT EXISTS history("
                "subsystem TEXT NOT NULL,agent TEXT NOT NULL,sequence INTEGER NOT NULL,"
                "payload_sha256 TEXT NOT NULL,projection_sha256 TEXT NOT NULL,"
                "projection_json TEXT NOT NULL,payload_z BLOB NOT NULL,"
                "PRIMARY KEY(subsystem,agent,sequence)) WITHOUT ROWID"
            )
            self._con.execute(
                "CREATE INDEX IF NOT EXISTS idx_continuity_history_agent "
                "ON history(agent,subsystem,sequence)"
            )
            self._con.execute(
                "INSERT OR IGNORE INTO metadata(key,value) VALUES('schema',?)",
                (CONTINUITY_HISTORY_SCHEMA,),
            )

    def _verify_schema(self) -> None:
        try:
            row = self._con.execute(
                "SELECT value FROM metadata WHERE key='schema'"
            ).fetchone()
        except sqlite3.DatabaseError as exc:
            raise EpisodeIntegrityError("invalid continuity-history archive") from exc
        if row is None or str(row[0]) != CONTINUITY_HISTORY_SCHEMA:
            raise EpisodeIntegrityError("unsupported continuity-history archive schema")

    @staticmethod
    def _encoded_row(
        subsystem: str,
        agent: str,
        record: dict[str, Any],
    ) -> tuple[Any, ...]:
        subsystem = str(subsystem)
        agent = str(agent)
        sequence = _positive_sequence(record)
        payload = _canonical_bytes(record)
        projection = _canonical_bytes(_history_tokens(subsystem, record))
        return (
            subsystem,
            agent,
            sequence,
            hashlib.sha256(payload).hexdigest(),
            hashlib.sha256(projection).hexdigest(),
            projection.decode("utf-8"),
            zlib.compress(payload, COMPRESSION_LEVEL),
        )

    def store_batch(
        self,
        rows: list[tuple[str, str, dict[str, Any]]],
    ) -> None:
        """Atomically store one diagnostic-history batch and trim its cold window."""
        if not rows:
            return
        encoded = [self._encoded_row(*row) for row in rows]
        touched = sorted({(row[0], row[1]) for row in encoded})
        with self._con:
            for row in encoded:
                existing = self._con.execute(
                    "SELECT payload_sha256,projection_sha256 FROM history "
                    "WHERE subsystem=? AND agent=? AND sequence=?",
                    row[:3],
                ).fetchone()
                if existing is not None:
                    if tuple(map(str, existing)) != (str(row[3]), str(row[4])):
                        raise EpisodeIntegrityError(
                            "continuity-history sequence collision with different content"
                        )
                    continue
                self._con.execute(
                    "INSERT INTO history("
                    "subsystem,agent,sequence,payload_sha256,projection_sha256,"
                    "projection_json,payload_z) VALUES(?,?,?,?,?,?,?)",
                    row,
                )
            for subsystem, agent in touched:
                self._con.execute(
                    "DELETE FROM history WHERE subsystem=? AND agent=? AND sequence NOT IN ("
                    "SELECT sequence FROM history WHERE subsystem=? AND agent=? "
                    "ORDER BY sequence DESC LIMIT ?)",
                    (
                        subsystem,
                        agent,
                        subsystem,
                        agent,
                        COLD_HISTORY_LIMIT,
                    ),
                )

    @staticmethod
    def _decode(payload_hash: str, packed: bytes) -> dict[str, Any]:
        try:
            payload = zlib.decompress(packed)
        except zlib.error as exc:
            raise EpisodeIntegrityError(
                "continuity-history decompression failure"
            ) from exc
        if hashlib.sha256(payload).hexdigest() != str(payload_hash):
            raise EpisodeIntegrityError("continuity-history payload integrity failure")
        try:
            value = json.loads(payload)
        except (TypeError, ValueError) as exc:
            raise EpisodeIntegrityError("continuity-history payload is invalid JSON") from exc
        if not isinstance(value, dict):
            raise EpisodeIntegrityError("continuity-history payload is not a mapping")
        return value

    def records(self, subsystem: str, agent: str) -> list[dict[str, Any]]:
        rows = self._con.execute(
            "SELECT payload_sha256,payload_z FROM history "
            "WHERE subsystem=? AND agent=? ORDER BY sequence",
            (str(subsystem), str(agent)),
        ).fetchall()
        return [deepcopy(self._decode(digest, packed)) for digest, packed in rows]

    def projection_rows(
        self,
        subsystem: str,
        agent: str,
    ) -> list[tuple[int, list[str]]]:
        rows = self._con.execute(
            "SELECT sequence,projection_sha256,projection_json FROM history "
            "WHERE subsystem=? AND agent=? ORDER BY sequence",
            (str(subsystem), str(agent)),
        ).fetchall()
        out: list[tuple[int, list[str]]] = []
        for sequence, digest, text in rows:
            payload = str(text).encode("utf-8")
            if hashlib.sha256(payload).hexdigest() != str(digest):
                raise EpisodeIntegrityError(
                    "continuity-history projection integrity failure"
                )
            try:
                tokens = json.loads(text)
            except (TypeError, ValueError) as exc:
                raise EpisodeIntegrityError(
                    "continuity-history projection is invalid"
                ) from exc
            if not isinstance(tokens, list) or any(
                not isinstance(token, str) for token in tokens
            ):
                raise EpisodeIntegrityError("continuity-history projection is invalid")
            out.append((int(sequence), list(tokens)))
        return out

    def count(self) -> int:
        row = self._con.execute("SELECT COUNT(*) FROM history").fetchone()
        return int(row[0])

    def manifest(self) -> dict[str, Any]:
        self._con.commit()
        rows = self._con.execute(
            "SELECT subsystem,agent,sequence,payload_sha256,projection_sha256 "
            "FROM history ORDER BY subsystem,agent,sequence"
        ).fetchall()
        digest = hashlib.sha256(
            _canonical_bytes(
                [
                    [str(a), str(b), int(c), str(d), str(e)]
                    for a, b, c, d, e in rows
                ]
            )
        ).hexdigest()
        return {
            "schema": CONTINUITY_HISTORY_MANIFEST_SCHEMA,
            "archive_schema": CONTINUITY_HISTORY_SCHEMA,
            "compression": "zlib",
            "level": COMPRESSION_LEVEL,
            "record_count": len(rows),
            "content_digest": digest,
        }

    def verify_manifest(self, manifest: Any) -> None:
        if manifest != self.manifest():
            raise EpisodeIntegrityError(
                "continuity-history archive does not match Ghost snapshot"
            )

    def close(self) -> None:
        self._con.commit()
        self._con.close()
