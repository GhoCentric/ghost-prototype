"""Stage 7 experimental Ghost optimization variants.

This module does not modify production Ghost.  It wraps the exact Stage-4
production API to test two cost hypotheses while preserving the frozen Stage-6
behavioral value target:

* lazy temporal materialization: ``tick`` schedules logical time and hot state is
  analytically advanced only when an event, recall, observation, or snapshot needs it;
* sparse historical hot state: raw interpretation/emotion/attention histories are
  moved to a separate SQLite cold archive while the production snapshot keeps only
  the minimum recent records required by the current schema plus a tiny threshold-
  gated projection manifest.

The combined variant applies both.  Private runtime state is touched deliberately:
this is an experiment against a hash-locked production implementation, not a public
API proposal or a production patch.
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from ghost.attention import _attention_gain, _resolve_flow

from .ghost_adapter import ADAPTER_SCHEMA, GhostArchiveMismatchError, GhostContinuityAdapter
from .stage6_behavior_policy import seeded_float


VARIANT_SCHEMA = "1.0"
SPARSE_HISTORY_OPERATION_LIMIT = 4
SPARSE_RAW_HISTORY_KEEP = 1
COLD_HISTORY_LIMIT = 64
PROJECTION_BUDGET = 3
PROJECTION_ENTER = seeded_float("stage7:projection_enter", 0.52, 0.60)
PROJECTION_EXIT = seeded_float("stage7:projection_exit", 0.38, 0.46)


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


class ColdHistoryArchive:
    """Append-only experimental store for histories removed from hot Ghost state."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS history ("
            "subsystem TEXT NOT NULL, agent TEXT NOT NULL, sequence INTEGER NOT NULL, "
            "payload_sha256 TEXT NOT NULL, payload_json TEXT NOT NULL, "
            "PRIMARY KEY(subsystem, agent, sequence))"
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_history_subsystem_agent "
            "ON history(subsystem, agent, sequence)"
        )
        self._db.commit()

    def put(self, subsystem: str, agent: str, record: dict) -> None:
        sequence = record.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
            raise ValueError("cold history record sequence must be a positive integer")
        payload = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        self._db.execute(
            "INSERT OR IGNORE INTO history(subsystem,agent,sequence,payload_sha256,payload_json) "
            "VALUES(?,?,?,?,?)",
            (str(subsystem), str(agent), sequence, digest, payload),
        )
        self._db.execute(
            "DELETE FROM history WHERE subsystem=? AND agent=? AND sequence NOT IN ("
            "SELECT sequence FROM history WHERE subsystem=? AND agent=? "
            "ORDER BY sequence DESC LIMIT ?)",
            (str(subsystem), str(agent), str(subsystem), str(agent), COLD_HISTORY_LIMIT),
        )

    def count(self) -> int:
        row = self._db.execute("SELECT COUNT(*) FROM history").fetchone()
        return int(row[0])

    def bytes(self) -> int:
        return self.path.stat().st_size

    def records(self, subsystem: str, agent: str) -> list[dict]:
        rows = self._db.execute(
            "SELECT payload_sha256,payload_json FROM history "
            "WHERE subsystem=? AND agent=? ORDER BY sequence",
            (str(subsystem), str(agent)),
        ).fetchall()
        out = []
        for digest, payload in rows:
            if hashlib.sha256(payload.encode()).hexdigest() != digest:
                raise RuntimeError("cold history integrity failure")
            out.append(json.loads(payload))
        return out

    def manifest(self) -> dict:
        self._db.commit()
        rows = self._db.execute(
            "SELECT subsystem,agent,sequence,payload_sha256 FROM history "
            "ORDER BY subsystem,agent,sequence"
        ).fetchall()
        digest = hashlib.sha256(
            _json_bytes([[str(a), str(b), int(c), str(d)] for a, b, c, d in rows])
        ).hexdigest()
        return {"schema": "1.0", "records": len(rows), "digest": digest}

    def verify_manifest(self, manifest: dict) -> None:
        if manifest != self.manifest():
            raise GhostArchiveMismatchError("cold history archive does not match snapshot")

    def close(self) -> None:
        self._db.commit()
        self._db.close()


class ExperimentalGhostContinuityAdapter(GhostContinuityAdapter):
    """Exact production Ghost wrapped with Stage-7 cost experiments."""

    def __init__(
        self,
        archive_path: str | Path,
        *,
        lazy_time: bool,
        sparse_history: bool,
        snapshot: dict | None = None,
    ) -> None:
        self.lazy_time = bool(lazy_time)
        self.sparse_history = bool(sparse_history)
        self._pending_steps: dict[str, int] = {}
        self._pending_calls: dict[str, int] = {}
        self._projection_active: dict[str, set[str]] = {}
        archive_path = Path(archive_path)
        self.cold_history = (
            ColdHistoryArchive(archive_path.with_suffix(".history.sqlite"))
            if self.sparse_history
            else None
        )
        try:
            super().__init__(archive_path, snapshot=snapshot)
            if self.sparse_history:
                self._configure_sparse_limits()
                self._sparsify_all()
        except Exception:
            if self.cold_history is not None:
                self.cold_history.close()
            raise

    @property
    def variant_name(self) -> str:
        if self.lazy_time and self.sparse_history:
            return "ghost_lazy_sparse"
        if self.lazy_time:
            return "ghost_lazy"
        if self.sparse_history:
            return "ghost_sparse"
        return "ghost_current"

    def _configure_sparse_limits(self) -> None:
        # Keep enough temporary room that a new record cannot evict an old record
        # before the controller archives it.  _sparsify_* drives the actual hot
        # record count down to <= 1 after each operation.
        self._ghost.interpretations.history_limit = SPARSE_HISTORY_OPERATION_LIMIT
        self._ghost.emotions.history_limit = SPARSE_HISTORY_OPERATION_LIMIT
        self._ghost.attention.history_limit = SPARSE_HISTORY_OPERATION_LIMIT

    def _restore(self, snapshot: dict) -> None:
        if not isinstance(snapshot, dict) or snapshot.get("schema") != VARIANT_SCHEMA:
            raise GhostArchiveMismatchError("invalid Stage-7 Ghost variant snapshot")
        expected = {"schema", "variant", "base", "pending_steps", "pending_calls", "cold_history"}
        if set(snapshot) != expected or snapshot["variant"] != self.variant_name:
            raise GhostArchiveMismatchError("Stage-7 Ghost variant snapshot mismatch")
        super()._restore(snapshot["base"])
        self._pending_steps = {str(k): int(v) for k, v in snapshot["pending_steps"].items()}
        self._pending_calls = {str(k): int(v) for k, v in snapshot["pending_calls"].items()}
        if self.sparse_history:
            assert self.cold_history is not None
            self.cold_history.verify_manifest(snapshot["cold_history"])
        elif snapshot["cold_history"] is not None:
            raise GhostArchiveMismatchError("unexpected cold history manifest")

    def _ensure_agent(self, agent: str) -> None:
        super()._ensure_agent(agent)
        self._pending_steps.setdefault(str(agent), 0)
        self._pending_calls.setdefault(str(agent), 0)
        if self.sparse_history:
            self._configure_sparse_limits()

    def tick(self, agent: str, steps: int = 1) -> None:
        if not self.lazy_time:
            super().tick(agent, steps=steps)
            if self.sparse_history:
                self._sparsify_all()
            return
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
            raise ValueError("steps must be a positive integer")
        agent = str(agent)
        self._ensure_agent(agent)
        self._pending_steps[agent] += steps
        self._pending_calls[agent] += 1
        self._ticks[agent] = self._ticks.get(agent, 0) + steps

    def _materialize(self, agent: str) -> None:
        agent = str(agent)
        self._ensure_agent(agent)
        self._ghost._ensure_continuity_agent(agent)
        steps = self._pending_steps.get(agent, 0)
        calls = self._pending_calls.get(agent, 0)
        if not self.lazy_time or steps <= 0:
            return

        # Exact source-owned analytical emotional decay, but without allocating
        # the production tick packet or writing diagnostic history.
        emotion_state = self._ghost.emotions._agents[agent]
        for name in sorted(emotion_state["levels"]):
            baseline = emotion_state["baseline"].get(name, 0.0)
            inertia = emotion_state["inertia"].get(
                name, self._ghost.emotions._default_inertia(name)
            )
            value = baseline + (emotion_state["levels"][name] - baseline) * (inertia ** steps)
            emotion_state["levels"][name] = max(0.0, min(1.0, value))
        self._ghost.emotions._resolve_spotlight(emotion_state)

        continuity_state = self._ghost.continuity._agents[agent]
        retention = (1.0 - continuity_state["release_rate"]) ** steps
        for dimension in sorted(continuity_state["activation"]):
            continuity_state["activation"][dimension] *= retention

        # Production attention advances once per public tick call, regardless of
        # the tick's ``steps`` value.  Empty-signal release has a closed form.
        attention_state = self._ghost.attention._agents[agent]
        config = attention_state["config"]
        pressure = attention_state["flow_pressure"] * ((1.0 - config["release_rate"]) ** calls)
        pressure = max(0.0, min(1.0, pressure))
        attention_state["flow_pressure"] = pressure
        attention_state["flow_active"] = _resolve_flow(
            bool(attention_state["flow_active"]), pressure, config
        )

        bridge = self._ghost.persistent_salience(agent)
        bridge = self._ghost.continuity.activation_aware_salience(agent, bridge)
        gain = _attention_gain(
            bool(attention_state["flow_active"]), pressure, config, False
        )
        attended = {
            name: max(0.0, min(1.0, float(value) * gain))
            for name, value in bridge["salience"].items()
        }
        self._ghost.continuity.resolve_foreground(
            agent, attended, sequence=self._ghost.attention._sequence
        )
        self._pending_steps[agent] = 0
        self._pending_calls[agent] = 0
        if self.sparse_history:
            self._sparsify_all()

    def _materialize_all(self) -> None:
        for agent in sorted(set(self._pending_steps) | set(self._ticks)):
            self._materialize(agent)

    def event(self, agent: str, **kwargs) -> dict:
        self._materialize(str(agent))
        packet = super().event(agent, **kwargs)
        if self.sparse_history:
            self._sparsify_all()
        return packet

    def revise(self, agent: str, dimension: str, meaning_delta: float) -> None:
        self._materialize(str(agent))
        super().revise(agent, dimension, meaning_delta)
        if self.sparse_history:
            self._sparsify_all()

    def recall_episode(self, episode_id: str, strength: float) -> dict:
        record = self.archive.get(str(episode_id))
        if record is not None:
            self._materialize(record["agent"])
        packet = super().recall_episode(episode_id, strength)
        if self.sparse_history:
            self._sparsify_all()
        return packet

    def recall_dimension(self, agent: str, dimension: str, strength: float) -> dict:
        self._materialize(str(agent))
        packet = super().recall_dimension(agent, dimension, strength)
        if self.sparse_history:
            self._sparsify_all()
        return packet

    def observe(self, agent: str) -> dict:
        self._materialize(str(agent))
        return super().observe(agent)

    def _record_score(self, subsystem: str, agent: str, record: dict) -> float:
        continuity = self._ghost.continuity.get_state(agent) or {"activation": {}}
        activation = continuity["activation"]
        emotion = self._ghost.emotional_state(agent) or {"levels": {}}
        levels = emotion["levels"]
        if subsystem == "interpretation":
            dimensions = record.get("transitions", {})
            return max([0.0, *(float(activation.get(name, 0.0)) for name in dimensions)])
        if subsystem == "emotion":
            names = record.get("effective_impulses", {})
            return max([0.0, *(float(levels.get(name, 0.0)) for name in names)])
        salience = record.get("underlying_salience", {})
        values = []
        for token in salience:
            if str(token).startswith("interpretation:"):
                values.append(float(activation.get(str(token).split(":", 1)[1], 0.0)))
            elif str(token).startswith("emotion:"):
                values.append(float(levels.get(str(token).split(":", 1)[1], 0.0)))
        return max([0.0, *values])

    def _sparsify_subsystem(self, subsystem: str, runtime: Any) -> None:
        assert self.cold_history is not None
        for agent, state in sorted(runtime._agents.items()):
            history = list(state.get("history", []))
            if len(history) <= SPARSE_RAW_HISTORY_KEEP:
                continue
            keep = history[-SPARSE_RAW_HISTORY_KEEP:]
            for record in history[:-SPARSE_RAW_HISTORY_KEEP]:
                self.cold_history.put(subsystem, agent, record)
            state["history"] = deepcopy(keep)

    def _sparsify_all(self) -> None:
        if not self.sparse_history:
            return
        self._configure_sparse_limits()
        self._sparsify_subsystem("interpretation", self._ghost.interpretations)
        self._sparsify_subsystem("emotion", self._ghost.emotions)
        self._sparsify_subsystem("attention", self._ghost.attention)

    def working_projections(self, agent: str) -> list[dict]:
        if not self.sparse_history or self.cold_history is None:
            return []
        candidates = []
        active = self._projection_active.setdefault(str(agent), set())
        next_active: set[str] = set()
        for subsystem in ("interpretation", "emotion", "attention"):
            for record in self.cold_history.records(subsystem, str(agent)):
                key = f"{subsystem}:{record['sequence']}"
                score = self._record_score(subsystem, str(agent), record)
                threshold = PROJECTION_EXIT if key in active else PROJECTION_ENTER
                if score >= threshold:
                    candidates.append((score, key, subsystem, int(record["sequence"])))
        candidates.sort(key=lambda row: (-row[0], row[1]))
        out = []
        for score, key, subsystem, sequence in candidates[:PROJECTION_BUDGET]:
            next_active.add(key)
            out.append({"key": key, "subsystem": subsystem, "sequence": sequence, "relevance": score})
        self._projection_active[str(agent)] = next_active
        return out

    def hot_history_counts(self) -> dict[str, int]:
        return {
            "interpretation": sum(len(state["history"]) for state in self._ghost.interpretations._agents.values()),
            "emotion": sum(len(state["history"]) for state in self._ghost.emotions._agents.values()),
            "attention": sum(len(state["history"]) for state in self._ghost.attention._agents.values()),
        }

    def snapshot(self) -> dict:
        self._materialize_all()
        if self.sparse_history:
            self._sparsify_all()
        base = {
            "schema": ADAPTER_SCHEMA,
            "ghost": self._ghost.snapshot(),
            "ticks": deepcopy(dict(sorted(self._ticks.items()))),
            "episode_archive": self.archive.manifest(),
        }
        return {
            "schema": VARIANT_SCHEMA,
            "variant": self.variant_name,
            "base": base,
            "pending_steps": deepcopy(dict(sorted(self._pending_steps.items()))),
            "pending_calls": deepcopy(dict(sorted(self._pending_calls.items()))),
            "cold_history": None if self.cold_history is None else self.cold_history.manifest(),
        }

    def close(self) -> None:
        try:
            super().close()
        finally:
            if self.cold_history is not None:
                self.cold_history.close()
                self.cold_history = None


def optimized_factory(kind: str, root: str | Path, label: str, *, snapshot: dict | None = None):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    config = {
        "ghost_current": (False, False),
        "ghost_lazy": (True, False),
        "ghost_sparse": (False, True),
        "ghost_lazy_sparse": (True, True),
    }.get(str(kind))
    if config is None:
        raise ValueError(f"unknown Stage-7 optimization variant: {kind}")
    lazy, sparse = config
    return ExperimentalGhostContinuityAdapter(
        root / f"{label}.ghost.sqlite",
        lazy_time=lazy,
        sparse_history=sparse,
        snapshot=snapshot,
    )


@contextmanager
def patched_stage6_factory(kind: str):
    """Run frozen Stage-6 scenarios against a Stage-7 adapter without editing them."""
    from . import stage6_behavior_scenarios as scenarios

    original = scenarios.factory

    def factory(requested: str, root: Path, label: str, *, snapshot: dict | None = None):
        if requested == kind:
            return optimized_factory(kind, root, label, snapshot=snapshot)
        return original(requested, root, label, snapshot=snapshot)

    scenarios.factory = factory
    try:
        yield scenarios
    finally:
        scenarios.factory = original


def run_stage6_quality_for_variant(kind: str, root: str | Path) -> dict:
    with patched_stage6_factory(kind) as scenarios:
        return scenarios.run_quality(kind, Path(root))
