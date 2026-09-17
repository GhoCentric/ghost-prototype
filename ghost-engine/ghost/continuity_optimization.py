"""Lazy temporal materialization and sparse hot-history control for continuity.

This controller does not own temporal physics or episodic memory. Emotion,
attention, and continuity remain the owners of their state transitions; this
module only defers when those source-owned transitions are materialized and
moves bounded diagnostic history out of the hot snapshot.
"""

from __future__ import annotations

from copy import deepcopy
import sqlite3
from typing import Any

from .attention import _attention_gain
from .continuity_history import (
    COMPRESSION_LEVEL,
    CompactContinuityHistoryArchive,
    PendingContinuityHistory,
)
from .episode_store import EpisodeIntegrityError, SQLiteEpisodeArchive
from .salience_bridge import build_salience_bridge


CONTINUITY_OPTIMIZATION_SCHEMA = "ghost.continuity_optimization.v1"
HOT_HISTORY_KEEP = 1
PROJECTION_BUDGET = 3
PROJECTION_ENTER = 0.5677369475438927
PROJECTION_EXIT = 0.44304749212474753


class ContinuityOptimizationRuntime:
    """Internal lazy-time and sparse-history controller for GhostAPI."""

    def __init__(
        self,
        *,
        emotions: Any,
        interpretations: Any,
        attention: Any,
        continuity: Any,
        episode_store: Any,
        history_manifest: dict[str, Any] | None = None,
    ) -> None:
        self.emotions = emotions
        self.interpretations = interpretations
        self.attention = attention
        self.continuity = continuity
        self._pending_steps: dict[str, int] = {}
        self._pending_calls: dict[str, int] = {}
        self._projection_active: dict[str, set[str]] = {}
        self._pending_history = PendingContinuityHistory()
        self.history, history_is_new = self._attach_history(episode_store)
        ready = False
        try:
            if history_manifest is None:
                if self.history is not None and self.history.count() != 0:
                    # A fresh API may intentionally share an episode archive with
                    # an existing runtime (M3 supports archive-only recall).  Cold
                    # diagnostic history is snapshot-paired, so an unpaired runtime
                    # must ignore rather than consume or mutate that sidecar.
                    self.history = None
            elif self.history is None:
                raise EpisodeIntegrityError(
                    "snapshot requires SQLiteEpisodeArchive continuity-history sidecar"
                )
            else:
                self.history.verify_manifest(deepcopy(history_manifest))
            ready = True
        finally:
            if not ready and history_is_new and self.history is not None:
                self.history.close()
                episode_store._continuity_history_archive = None

    @staticmethod
    def _attach_history(
        episode_store: Any,
    ) -> tuple[CompactContinuityHistoryArchive | None, bool]:
        if not isinstance(episode_store, SQLiteEpisodeArchive):
            return None, False
        attached = getattr(episode_store, "_continuity_history_archive", None)
        if attached is not None:
            return attached, False
        path = episode_store.path.with_suffix(".continuity-history.sqlite")
        archive = CompactContinuityHistoryArchive(path)
        episode_store._continuity_history_archive = archive
        return archive, True

    def schedule(self, agent: str, steps: int) -> dict[str, Any]:
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
            raise ValueError("steps must be a positive integer")
        agent = str(agent)
        self._pending_steps[agent] = self._pending_steps.get(agent, 0) + steps
        self._pending_calls[agent] = self._pending_calls.get(agent, 0) + 1
        return {
            "agent": agent,
            "steps": steps,
            "deferred": True,
            "pending_steps": self._pending_steps[agent],
            "pending_calls": self._pending_calls[agent],
        }

    def has_pending(self, agent: str) -> bool:
        return self._pending_steps.get(str(agent), 0) > 0

    def materialize(self, agent: str) -> None:
        """Apply deferred time through the subsystems that own temporal physics."""
        agent = str(agent)
        steps = self._pending_steps.get(agent, 0)
        calls = self._pending_calls.get(agent, 0)
        if steps <= 0:
            return
        if self.continuity.get_state(agent) is None:
            raise RuntimeError("pending continuity time references unregistered agent")

        if self.emotions.get_state(agent) is not None:
            self.emotions.tick(agent, steps=steps)
        self.continuity.tick_activation(agent, steps=steps)

        attention_state = self.attention.get_state(agent)
        if attention_state is not None:
            self.attention._advance_idle_time(agent, calls)
            attention_state = self.attention.get_state(agent)
            emotion_state = self.emotions.get_state(agent)
            interpretation_state = self.interpretations.get_state(agent)
            bridge = build_salience_bridge(
                agent,
                emotion_state=emotion_state,
                interpretation_state=interpretation_state,
                include_emotions=True,
                include_interpretations=True,
            )
            bridge = self.continuity.activation_aware_salience(agent, bridge)
            gain = _attention_gain(
                bool(attention_state["flow_active"]),
                float(attention_state["flow_pressure"]),
                attention_state["config"],
                False,
            )
            attended = {
                name: max(0.0, min(1.0, float(value) * gain))
                for name, value in bridge["salience"].items()
            }
            self.continuity.resolve_foreground(
                agent,
                attended,
                sequence=self.attention._sequence,
            )

        self._pending_steps[agent] = 0
        self._pending_calls[agent] = 0

    def materialize_all(self) -> None:
        for agent in sorted(self._pending_steps):
            self.materialize(agent)

    def compact(self, agent: str, *, strict: bool = False) -> bool:
        """Stage derived history in memory; persist it only at strict boundaries."""
        if self.history is None:
            return True
        agent = str(agent)
        plans: list[tuple[Any, list[dict[str, Any]]]] = []
        rows: list[tuple[str, str, dict[str, Any]]] = []
        for subsystem, runtime in (
            ("interpretation", self.interpretations),
            ("emotion", self.emotions),
            ("attention", self.attention),
        ):
            state = runtime._agents.get(agent)
            if state is None:
                continue
            history = list(state.get("history", []))
            if len(history) <= HOT_HISTORY_KEEP:
                continue
            rows.extend(
                (subsystem, agent, deepcopy(record))
                for record in history[:-HOT_HISTORY_KEEP]
            )
            plans.append((state, deepcopy(history[-HOT_HISTORY_KEEP:])))
        try:
            self._pending_history.stage(rows)
        except EpisodeIntegrityError:
            if strict:
                raise
            return False
        for state, keep in plans:
            state["history"] = keep
        return self.flush_history(strict=True) if strict else True

    def flush_history(self, *, strict: bool = False) -> bool:
        if self.history is None or not self._pending_history._rows:
            return True
        rows = self._pending_history.rows()
        try:
            self.history.store_batch(rows)
        except (sqlite3.Error, EpisodeIntegrityError):
            if strict:
                raise
            return False
        self._pending_history = PendingContinuityHistory()
        return True

    def compact_all(self, *, strict: bool = False) -> bool:
        complete = all(self.compact(agent) for agent in self.continuity.agents())
        if strict and not complete:
            raise EpisodeIntegrityError("continuity-history staging failure")
        return self.flush_history(strict=True) if strict else complete

    def expanded_history(
        self,
        subsystem: str,
        agent: str,
        hot_history: list[dict[str, Any]],
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        if self.history is None:
            return deepcopy(hot_history)
        rows = (
            self.history.records(subsystem, str(agent))
            + self._pending_history.records(subsystem, str(agent))
            + deepcopy(hot_history)
        )
        by_sequence = {int(row["sequence"]): row for row in rows}
        return [
            deepcopy(by_sequence[key])
            for key in sorted(by_sequence)[-int(limit) :]
        ]

    def history_manifest(self) -> dict[str, Any] | None:
        if self._pending_history._rows:
            raise RuntimeError("continuity-history manifest requires a strict flush")
        return None if self.history is None else self.history.manifest()

    def _projection_score(
        self,
        subsystem: str,
        agent: str,
        tokens: list[str],
    ) -> float:
        continuity = self.continuity.get_state(agent) or {"activation": {}}
        activation = continuity["activation"]
        emotion = self.emotions.get_state(agent) or {"levels": {}}
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

    def working_projections(self, agent: str) -> list[dict[str, Any]]:
        if self.history is None:
            return []
        agent = str(agent)
        active = self._projection_active.setdefault(agent, set())
        candidates: list[tuple[float, str, str, int]] = []
        for subsystem in ("interpretation", "emotion", "attention"):
            rows = self.history.projection_rows(subsystem, agent) + self._pending_history.projection_rows(subsystem, agent)
            for sequence, tokens in rows:
                key = f"{subsystem}:{sequence}"
                score = self._projection_score(subsystem, agent, tokens)
                threshold = PROJECTION_EXIT if key in active else PROJECTION_ENTER
                if score >= threshold:
                    candidates.append((score, key, subsystem, sequence))
        candidates.sort(key=lambda row: (-row[0], row[1]))
        out = []
        next_active: set[str] = set()
        for score, key, subsystem, sequence in candidates[:PROJECTION_BUDGET]:
            next_active.add(key)
            out.append(
                {
                    "key": key,
                    "subsystem": subsystem,
                    "sequence": sequence,
                    "relevance": score,
                }
            )
        self._projection_active[agent] = next_active
        return out

    def hot_history_counts(self) -> dict[str, int]:
        return {
            "interpretation": sum(
                len(state["history"]) for state in self.interpretations._agents.values()
            ),
            "emotion": sum(
                len(state["history"]) for state in self.emotions._agents.values()
            ),
            "attention": sum(
                len(state["history"]) for state in self.attention._agents.values()
            ),
        }

    def optimization_packet(self) -> dict[str, Any]:
        if any(self._pending_steps.values()):
            raise RuntimeError("continuity optimization snapshot requires materialized time")
        if self._pending_history._rows:
            raise RuntimeError("continuity optimization snapshot requires flushed history")
        return {
            "schema": CONTINUITY_OPTIMIZATION_SCHEMA,
            "compression_level": COMPRESSION_LEVEL,
            "hot_history_keep": HOT_HISTORY_KEEP,
            "projection_budget": PROJECTION_BUDGET,
            "projection_enter": PROJECTION_ENTER,
            "projection_exit": PROJECTION_EXIT,
        }

    @staticmethod
    def verify_optimization_packet(packet: Any) -> None:
        expected = {
            "schema": CONTINUITY_OPTIMIZATION_SCHEMA,
            "compression_level": COMPRESSION_LEVEL,
            "hot_history_keep": HOT_HISTORY_KEEP,
            "projection_budget": PROJECTION_BUDGET,
            "projection_enter": PROJECTION_ENTER,
            "projection_exit": PROJECTION_EXIT,
        }
        if packet != expected:
            raise EpisodeIntegrityError("unsupported continuity optimization packet")
