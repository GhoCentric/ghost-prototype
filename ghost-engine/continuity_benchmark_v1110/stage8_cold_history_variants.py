"""Stage 8 experimental compact cold-history representations.

Stage 7 demonstrated that Ghost's 64/64/64 diagnostic histories can move out of
hot state without losing the frozen Stage-6 behavioral advantage.  Stage 8 keeps
that exact lazy+sparse behavior and changes only the representation of the cold
history sidecar.

Every compact record retains the *complete* canonical history payload losslessly,
plus a tiny independently checksummed projection index.  The projection index lets
relevance gating avoid inflating full historical payloads just to decide which
records may enter the bounded live working set.
"""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any
import zlib

from .ghost_adapter import GhostArchiveMismatchError
from . import stage7_optimization_variants as stage7


COMPACT_SCHEMA = "1.0"
COMPRESSION_LEVELS = {
    "ghost_compact_fast": 1,
    "ghost_compact_balanced": 6,
    "ghost_compact_dense": 9,
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _projection_tokens(subsystem: str, record: dict) -> list[str]:
    if subsystem == "interpretation":
        source = record.get("transitions", {})
    elif subsystem == "emotion":
        source = record.get("effective_impulses", {})
    elif subsystem == "attention":
        source = record.get("underlying_salience", {})
    else:
        raise ValueError(f"unknown cold-history subsystem: {subsystem}")
    if not isinstance(source, dict):
        raise ValueError("cold-history projection source must be a mapping")
    return sorted(str(token) for token in source)


class CompactColdHistoryArchive:
    """Lossless compressed history store with a small projection-only index."""

    def __init__(self, path: str | Path, *, compression_level: int) -> None:
        if compression_level not in {1, 6, 9}:
            raise ValueError("compression_level must be one of 1, 6, or 9")
        self.path = Path(path)
        self.compression_level = int(compression_level)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS history ("
            "subsystem TEXT NOT NULL, agent TEXT NOT NULL, sequence INTEGER NOT NULL, "
            "payload_sha256 TEXT NOT NULL, projection_sha256 TEXT NOT NULL, "
            "projection_json TEXT NOT NULL, payload_z BLOB NOT NULL, "
            "PRIMARY KEY(subsystem,agent,sequence)) WITHOUT ROWID"
        )
        self._db.commit()

    def put(self, subsystem: str, agent: str, record: dict) -> None:
        sequence = record.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
            raise ValueError("cold history record sequence must be a positive integer")
        subsystem = str(subsystem)
        agent = str(agent)
        payload = _canonical_bytes(record)
        payload_digest = hashlib.sha256(payload).hexdigest()
        projection = _canonical_bytes(_projection_tokens(subsystem, record))
        projection_digest = hashlib.sha256(projection).hexdigest()
        packed = zlib.compress(payload, self.compression_level)
        self._db.execute(
            "INSERT OR IGNORE INTO history("
            "subsystem,agent,sequence,payload_sha256,projection_sha256,projection_json,payload_z"
            ") VALUES(?,?,?,?,?,?,?)",
            (
                subsystem,
                agent,
                sequence,
                payload_digest,
                projection_digest,
                projection.decode(),
                packed,
            ),
        )
        self._db.execute(
            "DELETE FROM history WHERE subsystem=? AND agent=? AND sequence NOT IN ("
            "SELECT sequence FROM history WHERE subsystem=? AND agent=? "
            "ORDER BY sequence DESC LIMIT ?)",
            (subsystem, agent, subsystem, agent, stage7.COLD_HISTORY_LIMIT),
        )

    def count(self) -> int:
        row = self._db.execute("SELECT COUNT(*) FROM history").fetchone()
        return int(row[0])

    def bytes(self) -> int:
        self._db.commit()
        return self.path.stat().st_size

    def _decode(self, digest: str, packed: bytes) -> dict:
        try:
            payload = zlib.decompress(packed)
        except zlib.error as exc:
            raise RuntimeError("compact cold history decompression failure") from exc
        if hashlib.sha256(payload).hexdigest() != str(digest):
            raise RuntimeError("compact cold history payload integrity failure")
        value = json.loads(payload)
        if not isinstance(value, dict):
            raise RuntimeError("compact cold history payload is not a mapping")
        return value

    def records(self, subsystem: str, agent: str) -> list[dict]:
        rows = self._db.execute(
            "SELECT payload_sha256,payload_z FROM history "
            "WHERE subsystem=? AND agent=? ORDER BY sequence",
            (str(subsystem), str(agent)),
        ).fetchall()
        return [self._decode(digest, packed) for digest, packed in rows]

    def projection_rows(self, subsystem: str, agent: str) -> list[tuple[int, list[str]]]:
        rows = self._db.execute(
            "SELECT sequence,projection_sha256,projection_json FROM history "
            "WHERE subsystem=? AND agent=? ORDER BY sequence",
            (str(subsystem), str(agent)),
        ).fetchall()
        out = []
        for sequence, digest, text in rows:
            payload = str(text).encode()
            if hashlib.sha256(payload).hexdigest() != str(digest):
                raise RuntimeError("compact cold history projection integrity failure")
            tokens = json.loads(text)
            if not isinstance(tokens, list) or any(not isinstance(token, str) for token in tokens):
                raise RuntimeError("compact cold history projection is invalid")
            out.append((int(sequence), tokens))
        return out

    def manifest(self) -> dict:
        self._db.commit()
        rows = self._db.execute(
            "SELECT subsystem,agent,sequence,payload_sha256,projection_sha256 FROM history "
            "ORDER BY subsystem,agent,sequence"
        ).fetchall()
        digest = hashlib.sha256(_canonical_bytes([
            [str(a), str(b), int(c), str(d), str(e)] for a, b, c, d, e in rows
        ])).hexdigest()
        return {
            "schema": COMPACT_SCHEMA,
            "compression": "zlib",
            "level": self.compression_level,
            "records": len(rows),
            "digest": digest,
        }

    def verify_manifest(self, manifest: dict) -> None:
        if manifest != self.manifest():
            raise GhostArchiveMismatchError("compact cold history archive does not match snapshot")

    def close(self) -> None:
        self._db.commit()
        self._db.close()


class CompactColdGhostAdapter(stage7.ExperimentalGhostContinuityAdapter):
    """Stage-7 lazy+sparse Ghost with only the cold representation replaced."""

    def __init__(
        self,
        archive_path: str | Path,
        *,
        variant: str,
        snapshot: dict | None = None,
    ) -> None:
        if variant not in COMPRESSION_LEVELS:
            raise ValueError(f"unknown Stage-8 compact variant: {variant}")
        self._stage8_variant = str(variant)
        level = COMPRESSION_LEVELS[self._stage8_variant]
        original = stage7.ColdHistoryArchive

        def archive_factory(path: str | Path):
            return CompactColdHistoryArchive(path, compression_level=level)

        stage7.ColdHistoryArchive = archive_factory
        try:
            super().__init__(
                archive_path,
                lazy_time=True,
                sparse_history=True,
                snapshot=snapshot,
            )
        finally:
            stage7.ColdHistoryArchive = original

    @property
    def variant_name(self) -> str:
        return self._stage8_variant

    def _projection_score(self, subsystem: str, agent: str, tokens: list[str]) -> float:
        continuity = self._ghost.continuity.get_state(agent) or {"activation": {}}
        activation = continuity["activation"]
        emotion = self._ghost.emotional_state(agent) or {"levels": {}}
        levels = emotion["levels"]
        values = [0.0]
        if subsystem == "interpretation":
            values.extend(float(activation.get(token, 0.0)) for token in tokens)
        elif subsystem == "emotion":
            values.extend(float(levels.get(token, 0.0)) for token in tokens)
        else:
            for token in tokens:
                if token.startswith("interpretation:"):
                    values.append(float(activation.get(token.split(":", 1)[1], 0.0)))
                elif token.startswith("emotion:"):
                    values.append(float(levels.get(token.split(":", 1)[1], 0.0)))
        return max(values)

    def working_projections(self, agent: str) -> list[dict]:
        if self.cold_history is None:
            return []
        if not isinstance(self.cold_history, CompactColdHistoryArchive):
            raise RuntimeError("Stage-8 compact adapter lost compact cold archive")
        agent = str(agent)
        candidates = []
        active = self._projection_active.setdefault(agent, set())
        next_active: set[str] = set()
        for subsystem in ("interpretation", "emotion", "attention"):
            for sequence, tokens in self.cold_history.projection_rows(subsystem, agent):
                key = f"{subsystem}:{sequence}"
                score = self._projection_score(subsystem, agent, tokens)
                threshold = stage7.PROJECTION_EXIT if key in active else stage7.PROJECTION_ENTER
                if score >= threshold:
                    candidates.append((score, key, subsystem, sequence))
        candidates.sort(key=lambda row: (-row[0], row[1]))
        out = []
        for score, key, subsystem, sequence in candidates[:stage7.PROJECTION_BUDGET]:
            next_active.add(key)
            out.append({"key": key, "subsystem": subsystem, "sequence": sequence, "relevance": score})
        self._projection_active[agent] = next_active
        return out


def compact_factory(kind: str, root: str | Path, label: str, *, snapshot: dict | None = None):
    if kind not in COMPRESSION_LEVELS:
        raise ValueError(f"unknown Stage-8 compact variant: {kind}")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    return CompactColdGhostAdapter(
        root / f"{label}.ghost.sqlite",
        variant=kind,
        snapshot=snapshot,
    )


@contextmanager
def patched_stage6_factory(kind: str):
    from . import stage6_behavior_scenarios as scenarios

    original = scenarios.factory

    def factory(requested: str, root: Path, label: str, *, snapshot: dict | None = None):
        if requested == kind:
            return compact_factory(kind, root, label, snapshot=snapshot)
        return original(requested, root, label, snapshot=snapshot)

    scenarios.factory = factory
    try:
        yield scenarios
    finally:
        scenarios.factory = original


def run_stage6_quality_for_compact(kind: str, root: str | Path) -> dict:
    with patched_stage6_factory(kind) as scenarios:
        return scenarios.run_quality(kind, Path(root))
