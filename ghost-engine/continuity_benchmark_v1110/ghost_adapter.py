"""Thin Stage-2 adapter from the frozen continuity contract to production Ghost.

The benchmark contract was frozen in Stage 1.  This module is the only system
adapter added for Stage 2.  It does not modify Ghost production code and it does
not alter the frozen runner, purpose-built baseline, metrics, contract, or Stage-1
result.

Translation policy:

* benchmark meaning deltas are translated onto Ghost's saturating interpretation
  update so the requested additive contract delta reaches the same target level;
* benchmark affect uses the frozen shared emotion-retention constants;
* benchmark consequence state is stored in Ghost's real relationship graph;
* durable identity / recall / persistence use GhostAPI + SQLiteEpisodeArchive;
* ambiguous dimension recall is passed through GhostAPI exactly as implemented;
* foreground reports the production cross-layer leader, with only
  ``interpretation:<dimension>`` unwrapped to the contract's dimension token;
* the near-tie probe exercises production PairwiseForeground directly.

No benchmark oracle values are read here.
"""

from __future__ import annotations

from copy import deepcopy
import math
from pathlib import Path

from ghost import GhostAPI
from ghost.continuity import PairwiseForeground
from ghost.episode_store import (
    EpisodeCapacityError,
    EpisodeIntegrityError,
    SQLiteEpisodeArchive,
)

from .contract import (
    BASELINE_EMOTION_RETENTION,
    BASELINE_RELEASE_RATE,
    BASELINE_SWITCH_THRESHOLD,
    ArchiveMismatchError,
    CapacityBackpressureError,
)


ADAPTER_SCHEMA = "1.0"
_CONSEQUENCE_SOURCE = "continuity-benchmark"
_EPS = 1e-12


class GhostCapacityError(CapacityBackpressureError):
    """Frozen-contract capacity signal translated from production Ghost."""


class GhostArchiveMismatchError(ArchiveMismatchError):
    """Frozen-contract archive mismatch translated from production Ghost."""


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _effective_impulse_for_additive_delta(current: float, delta: float) -> float:
    """Translate contract additive meaning semantics to Ghost saturation math."""
    current = _clamp(current)
    desired = _clamp(current + float(delta))
    if math.isclose(desired, current, rel_tol=0.0, abs_tol=_EPS):
        return 0.0
    if desired > current:
        return _clamp((desired - current) / (1.0 - current))
    return max(-1.0, min(0.0, desired / current - 1.0))


def _foreground_token(current_leader: str | None) -> str | None:
    if current_leader is None:
        return None
    prefix = "interpretation:"
    if current_leader.startswith(prefix):
        return current_leader[len(prefix):]
    return current_leader


class GhostContinuityAdapter:
    """Frozen-contract façade over the real M3 production implementation."""

    def __init__(
        self,
        archive_path: str | Path,
        *,
        max_records: int | None = None,
        snapshot: dict | None = None,
    ) -> None:
        self.archive = SQLiteEpisodeArchive(
            archive_path,
            max_records=max_records,
        )
        self.api: GhostAPI | None = None
        self._ticks: dict[str, int] = {}
        try:
            if snapshot is None:
                self.api = GhostAPI(episode_store=self.archive)
            else:
                self._restore(snapshot)
        except Exception:
            self.archive.close()
            raise

    @property
    def _ghost(self) -> GhostAPI:
        if self.api is None:
            raise RuntimeError("Ghost adapter is closed")
        return self.api

    def _ensure_agent(self, agent: str) -> None:
        agent = str(agent)
        if self._ghost.interpretation_state(agent) is None:
            self._ghost.register_interpretation_agent(agent)
        if self._ghost.attention_state(agent) is None:
            self._ghost.register_attention_agent(
                agent,
                config={"release_rate": BASELINE_RELEASE_RATE},
            )
        if self._ghost.emotional_state(agent) is None:
            self._ghost.register_emotional_agent(
                agent,
                inertia=BASELINE_EMOTION_RETENTION,
                spotlight_switch_margin=BASELINE_SWITCH_THRESHOLD,
            )
        self._ticks.setdefault(agent, 0)

    def _meaning_level(self, agent: str, dimension: str) -> float:
        state = self._ghost.interpretation_state(agent)
        if state is None:
            return 0.0
        return float(state["levels"].get(str(dimension), 0.0))

    def _configure_impulse_action(
        self,
        agent: str,
        dimension: str,
        impulse: float,
        *,
        kind: str,
    ) -> tuple[str, float]:
        sign = "positive" if impulse >= 0.0 else "negative"
        action = f"benchmark_{kind}_{sign}_{dimension}"
        self._ghost.configure_interpretation_rule(
            agent,
            f"action:{action}",
            {str(dimension): 1.0 if impulse >= 0.0 else -1.0},
        )
        return action, abs(float(impulse))

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
        del relevance  # Ghost's M3 activation is intentionally interpretation-cause driven.
        agent = str(agent)
        dimension = str(dimension)
        checkpoint = self._ghost.snapshot()
        self._ensure_agent(agent)
        current = self._meaning_level(agent, dimension)
        impulse = _effective_impulse_for_additive_delta(current, meaning_delta)
        profile = {} if emotion_profile is None else dict(emotion_profile)
        try:
            action, intensity = self._configure_impulse_action(
                agent,
                dimension,
                impulse,
                kind="event",
            )
            packet = self._ghost.continuity_event(
                agent,
                action,
                intensity=intensity,
                source=str(source),
                provenance={"benchmark_dimension": dimension},
                emotion_event="benchmark_episode",
                emotion_intensity=1.0,
                emotion_impulses=profile,
            )
            episodes = packet["episodes"]
            if len(episodes) != 1:
                raise RuntimeError(
                    "frozen benchmark event expected exactly one durable Ghost episode"
                )
        except EpisodeCapacityError as exc:
            self._ghost.restore_snapshot(checkpoint)
            raise GhostCapacityError(str(exc)) from exc
        except Exception:
            self._ghost.restore_snapshot(checkpoint)
            raise
        if consequence:
            self._ghost.engine.relationships.apply_delta(
                _CONSEQUENCE_SOURCE,
                agent,
                {"trust": float(consequence)},
            )
        return deepcopy(episodes[0])

    def revise(self, agent: str, dimension: str, meaning_delta: float) -> None:
        agent = str(agent)
        dimension = str(dimension)
        self._ensure_agent(agent)
        current = self._meaning_level(agent, dimension)
        impulse = _effective_impulse_for_additive_delta(current, meaning_delta)
        action, intensity = self._configure_impulse_action(
            agent,
            dimension,
            impulse,
            kind="revision",
        )
        self._ghost.continuity_event(
            agent,
            action,
            intensity=intensity,
            source="continuity-benchmark-revision",
            provenance={"benchmark_revision": True, "benchmark_dimension": dimension},
        )

    def tick(self, agent: str, steps: int = 1) -> None:
        agent = str(agent)
        self._ensure_agent(agent)
        self._ghost.continuity_tick(agent, steps=int(steps))
        self._ticks[agent] = self._ticks.get(agent, 0) + int(steps)

    def recall_episode(self, episode_id: str, strength: float) -> dict:
        packet = self._ghost.recall_episode(str(episode_id), float(strength))
        lookup = packet["lookup"]
        return {
            "status": "explicit_episode",
            "episode_id": packet["episode_id"],
            "record": deepcopy(lookup["record"]),
            "meaning_unchanged": bool(packet["meaning_unchanged"]),
        }

    def recall_dimension(self, agent: str, dimension: str, strength: float) -> dict:
        packet = self._ghost.recall_dimension(
            str(agent),
            str(dimension),
            float(strength),
        )
        lookup = deepcopy(packet["lookup"])
        if lookup["status"] != "unique":
            return lookup
        return {
            "status": "unique",
            "candidate_count": 1,
            "record": deepcopy(lookup["record"]),
            "recall": {
                "status": "explicit_episode",
                "episode_id": packet["episode_id"],
                "record": deepcopy(lookup["record"]),
                "meaning_unchanged": bool(packet["meaning_unchanged"]),
            },
        }

    def episodes_for_dimension(self, agent: str, dimension: str) -> list[dict]:
        return self.archive.for_dimension(str(agent), str(dimension))

    def get_episode(self, episode_id: str) -> dict | None:
        return self.archive.get(str(episode_id))

    def archive_manifest(self) -> dict:
        return self.archive.manifest()

    def near_tie_trace(self, steps: int = 100) -> list[str | None]:
        foreground = PairwiseForeground(BASELINE_SWITCH_THRESHOLD)
        trace = []
        for tick in range(int(steps)):
            values = (
                {"anger": 0.5001, "threat": 0.4999}
                if tick % 2 == 0
                else {"anger": 0.4999, "threat": 0.5001}
            )
            packet = foreground.step(tick, values)
            trace.append(packet["resolved_leader"])
        return trace

    def observe(self, agent: str) -> dict:
        agent = str(agent)
        self._ensure_agent(agent)
        meaning_state = self._ghost.interpretation_state(agent)
        continuity_state = self._ghost.continuity_state(agent)
        emotion_state = self._ghost.emotional_state(agent)
        relationship = self._ghost.get_relationship(_CONSEQUENCE_SOURCE, agent)
        assert meaning_state is not None
        assert continuity_state is not None
        assert emotion_state is not None
        return {
            "meaning": deepcopy(dict(sorted(meaning_state["levels"].items()))),
            "activation": deepcopy(dict(sorted(continuity_state["activation"].items()))),
            "emotion": {
                name: float(emotion_state["levels"].get(name, 0.0))
                for name in sorted(BASELINE_EMOTION_RETENTION)
            },
            "trust": float(relationship.get("trust", 0.0)),
            "foreground": _foreground_token(continuity_state["current_leader"]),
            "tick": int(self._ticks.get(agent, 0)),
            "episode_count": self.archive.count(),
        }

    def snapshot(self) -> dict:
        return {
            "schema": ADAPTER_SCHEMA,
            "ghost": self._ghost.snapshot(),
            "ticks": deepcopy(dict(sorted(self._ticks.items()))),
            "episode_archive": self.archive.manifest(),
        }

    def _restore(self, snapshot: dict) -> None:
        if not isinstance(snapshot, dict) or set(snapshot) != {
            "schema",
            "ghost",
            "ticks",
            "episode_archive",
        }:
            raise GhostArchiveMismatchError("invalid Ghost adapter snapshot")
        if snapshot["schema"] != ADAPTER_SCHEMA:
            raise GhostArchiveMismatchError("unsupported Ghost adapter snapshot schema")
        try:
            self.archive.verify_manifest(snapshot["episode_archive"])
            self.api = GhostAPI.from_snapshot(
                snapshot["ghost"],
                episode_store=self.archive,
            )
        except EpisodeIntegrityError as exc:
            raise GhostArchiveMismatchError(str(exc)) from exc
        self._ticks = {
            str(agent): int(value)
            for agent, value in snapshot["ticks"].items()
        }

    def close(self) -> None:
        if self.api is None:
            return
        self.archive.close()
        self.api = None


def ghost_factory(
    root: str | Path,
    label: str,
    *,
    max_records: int | None = None,
    snapshot: dict | None = None,
) -> GhostContinuityAdapter:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    return GhostContinuityAdapter(
        root / f"{label}.ghost.sqlite",
        max_records=max_records,
        snapshot=snapshot,
    )
