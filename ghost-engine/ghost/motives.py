"""Deterministic motive-field runtime for Ghost v1.11 development.

A motive field is *not* an action selector. It converts persistent Ghost-owned
agent state into auditable behavioral pressures using developer-configured,
engine-neutral motive channels. The runtime never invents game facts, does not
mutate source cognition, does not execute behavior, and does not call an LLM.

Profiles are explicit linear pressure maps::

    score = clamp01(baseline + sum(signal_value * signed_weight))

Signal names are namespaced and built from copied agent state:

    trait:cautious
    value:protect_town
    goal:maintain_post:priority_remaining
    persistent:emotion:anger
    persistent:interpretation:betrayal
    attended:emotion:anger
    attention:flow_pressure

Missing configured signals contribute zero and are reported in diagnostics.
"""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any

from .ids import normalize_id
from .validation import validate_finite_number


MOTIVE_SNAPSHOT_SCHEMA_VERSION = "1.0"
MOTIVE_SIGNAL_PACKET_VERSION = "1.0"
DEFAULT_MOTIVE_HISTORY_LIMIT = 64
GOAL_STATUSES = ("inactive", "active", "blocked", "satisfied", "abandoned")

_SNAPSHOT_KEYS = {
    "schema_version", "history_limit", "sequence", "profiles", "history",
}
_PROFILE_KEYS = {"motive_id", "baseline", "weights"}
_SIGNAL_PACKET_KEYS = {"packet_version", "agent", "signals", "sources"}
_SOURCE_KEYS = {"traits", "values", "goals", "persistent_salience", "attention"}
_RECORD_KEYS = {
    "sequence", "agent", "signal_packet_version", "sources", "signals",
    "motives", "ranking", "dominant_motive", "dominant_score",
}
_MOTIVE_RESULT_KEYS = {
    "motive_id", "score", "raw_score", "baseline", "support", "opposition",
    "missing_signals", "contributions",
}
_CONTRIBUTION_KEYS = {"signal", "signal_value", "weight", "contribution"}


def _finite(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    try:
        return validate_finite_number(value, label)
    except ValueError as exc:
        raise ValueError(f"{label} must be a finite number") from exc


def _unit(value, label: str) -> float:
    number = _finite(value, label)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{label} must be in [0, 1]")
    return number


def _signed_unit(value, label: str) -> float:
    number = _finite(value, label)
    if not -1.0 <= number <= 1.0:
        raise ValueError(f"{label} must be in [-1, 1]")
    return number


def _positive_int(value, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _non_negative_int(value, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _json_safe(value: Any, label: str) -> None:
    stack = [(value, label)]
    while stack:
        current, current_label = stack.pop()
        if current is None or isinstance(current, (str, bool, int)):
            continue
        if isinstance(current, float):
            _finite(current, current_label)
            continue
        if isinstance(current, list):
            stack.extend(
                (item, f"{current_label}[{index}]")
                for index, item in reversed(list(enumerate(current)))
            )
            continue
        if isinstance(current, dict):
            pending = []
            for key, item in current.items():
                if not isinstance(key, str):
                    raise ValueError(f"{current_label} keys must be strings")
                pending.append((item, f"{current_label}.{key}"))
            stack.extend(reversed(pending))
            continue
        raise ValueError(f"{current_label} must be JSON-safe")


def _signal_name(value, label: str = "signal name") -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _normalize_signal_map(value, label: str = "signals") -> dict[str, float]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a dict")
    out: dict[str, float] = {}
    for raw_name, raw_value in value.items():
        name = _signal_name(raw_name, f"{label} name")
        if name in out:
            raise ValueError(f"{label} contains duplicate normalized signal: {name!r}")
        out[name] = _unit(raw_value, f"{label}.{name}")
    return {name: out[name] for name in sorted(out)}


def _normalize_weights(value) -> dict[str, float]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("motive weights must be a dict or None")
    out: dict[str, float] = {}
    for raw_name, raw_weight in value.items():
        name = _signal_name(raw_name, "motive weight signal")
        if name in out:
            raise ValueError(f"motive weights contains duplicate normalized signal: {name!r}")
        out[name] = _signed_unit(raw_weight, f"motive weight {name}")
    return {name: out[name] for name in sorted(out)}


def _profile(motive_id, *, baseline=0.0, weights=None) -> dict:
    motive_id = normalize_id(motive_id, "motive id")
    return {
        "motive_id": motive_id,
        "baseline": _unit(baseline, f"motive {motive_id} baseline"),
        "weights": _normalize_weights(weights),
    }


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))


def _agent_record(value, agent: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError("agent state must be a dict")
    record_id = normalize_id(value.get("agent_id"), "agent state agent_id")
    if record_id != agent:
        raise ValueError(f"agent state id mismatch: expected {agent!r}, got {record_id!r}")
    for key in ("traits", "values", "goal_states"):
        if key not in value:
            raise ValueError(f"agent state is missing {key}")
    if not isinstance(value["traits"], dict) or not isinstance(value["values"], dict):
        raise ValueError("agent traits and values must be dicts")
    if not isinstance(value["goal_states"], dict):
        raise ValueError("agent goal_states must be a dict")
    return value


def _add_channels(signals: dict[str, float], prefix: str, channels: dict, label: str) -> int:
    count = 0
    for raw_name, raw_value in channels.items():
        name = normalize_id(raw_name, f"{label} name")
        signal = f"{prefix}{name}"
        if signal in signals:
            raise ValueError(f"duplicate motive signal: {signal}")
        signals[signal] = _unit(raw_value, f"{label}.{name}")
        count += 1
    return count


def _goal_signals(signals: dict[str, float], goal_states: dict) -> int:
    count = 0
    for raw_goal_id in sorted(goal_states):
        goal_id = normalize_id(raw_goal_id, "goal state id")
        state = goal_states[raw_goal_id]
        if not isinstance(state, dict):
            raise ValueError(f"goal state {goal_id!r} must be a dict")
        if normalize_id(state.get("goal_id"), "goal state goal_id") != goal_id:
            raise ValueError(f"goal state key/id mismatch: {goal_id!r}")
        status = state.get("status")
        if status not in GOAL_STATUSES:
            raise ValueError(f"goal state {goal_id!r} has unsupported status: {status!r}")
        priority = _unit(state.get("priority"), f"goal {goal_id} priority")
        progress = _unit(state.get("progress"), f"goal {goal_id} progress")
        unresolved = priority * (1.0 - progress) if status in {"active", "blocked"} else 0.0
        base = f"goal:{goal_id}:"
        signals[base + "priority"] = priority
        signals[base + "progress"] = progress
        signals[base + "priority_remaining"] = unresolved
        count += 3
        for possible in GOAL_STATUSES:
            signals[base + "status:" + possible] = 1.0 if status == possible else 0.0
            count += 1
    return count


def _persistent_signals(signals: dict[str, float], packet: dict | None, agent: str) -> dict:
    if packet is None:
        return {"present": False, "count": 0, "source_count": 0}
    if not isinstance(packet, dict):
        raise ValueError("persistent salience packet must be a dict or None")
    if normalize_id(packet.get("agent"), "persistent salience agent") != agent:
        raise ValueError("persistent salience agent mismatch")
    if not isinstance(packet.get("salience"), dict):
        raise ValueError("persistent salience packet is missing salience")
    salience = _normalize_signal_map(packet["salience"], "persistent salience")
    for name, value in salience.items():
        signal = "persistent:" + name
        signals[signal] = value
    source_count = packet.get("source_count", 0)
    source_count = _non_negative_int(source_count, "persistent salience source_count")
    return {"present": True, "count": len(salience), "source_count": source_count}


def _attention_signals(signals: dict[str, float], packet: dict | None, agent: str) -> dict:
    if packet is None:
        return {"present": False, "count": 0, "attended_count": 0, "revision": None}
    if not isinstance(packet, dict):
        raise ValueError("attention state must be a dict or None")
    if normalize_id(packet.get("agent"), "attention state agent") != agent:
        raise ValueError("attention state agent mismatch")
    pressure = _unit(packet.get("flow_pressure"), "attention flow_pressure")
    depth = _unit(packet.get("flow_depth"), "attention flow_depth")
    gain = _unit(packet.get("attention_gain"), "attention attention_gain")
    active = packet.get("flow_active")
    if not isinstance(active, bool):
        raise ValueError("attention flow_active must be a bool")
    signals["attention:flow_pressure"] = pressure
    signals["attention:flow_depth"] = depth
    signals["attention:gain"] = gain
    signals["attention:flow_active"] = 1.0 if active else 0.0

    history = packet.get("history")
    if not isinstance(history, list):
        raise ValueError("attention history must be a list")
    attended_count = 0
    revision = None
    if history:
        latest = history[-1]
        if not isinstance(latest, dict):
            raise ValueError("latest attention history record must be a dict")
        revision = _non_negative_int(latest.get("sequence"), "attention history sequence")
        if revision <= 0:
            raise ValueError("attention history sequence must be positive")
        attended = latest.get("attended_salience")
        if not isinstance(attended, dict):
            raise ValueError("latest attention history is missing attended_salience")
        attended_map = _normalize_signal_map(attended, "attended salience")
        for name, value in attended_map.items():
            signal = "attended:" + name
            signals[signal] = value
        attended_count = len(attended_map)
    return {
        "present": True,
        "count": 4 + attended_count,
        "attended_count": attended_count,
        "revision": revision,
    }


def build_motive_signal_packet(
    agent,
    *,
    agent_state: dict,
    persistent_salience: dict | None = None,
    attention_state: dict | None = None,
) -> dict:
    """Build one copied, deterministic signal packet from Ghost-owned state."""
    agent = normalize_id(agent, "motive signal agent")
    state = _agent_record(deepcopy(agent_state), agent)
    signals: dict[str, float] = {}
    trait_count = _add_channels(signals, "trait:", state["traits"], "agent traits")
    value_count = _add_channels(signals, "value:", state["values"], "agent values")
    goal_count = _goal_signals(signals, state["goal_states"])
    persistent_meta = _persistent_signals(signals, deepcopy(persistent_salience), agent)
    attention_meta = _attention_signals(signals, deepcopy(attention_state), agent)
    return {
        "packet_version": MOTIVE_SIGNAL_PACKET_VERSION,
        "agent": agent,
        "signals": {name: signals[name] for name in sorted(signals)},
        "sources": {
            "traits": {"count": trait_count},
            "values": {"count": value_count},
            "goals": {"count": goal_count},
            "persistent_salience": persistent_meta,
            "attention": attention_meta,
        },
    }


def _validate_signal_packet(packet: dict, agent: str) -> dict:
    if not isinstance(packet, dict):
        raise ValueError("motive signal packet must be a dict")
    unknown = set(packet) - _SIGNAL_PACKET_KEYS
    if unknown:
        raise ValueError("motive signal packet has unsupported keys: " + ", ".join(sorted(unknown)))
    missing = _SIGNAL_PACKET_KEYS - set(packet)
    if missing:
        raise ValueError("motive signal packet is missing required keys: " + ", ".join(sorted(missing)))
    if packet["packet_version"] != MOTIVE_SIGNAL_PACKET_VERSION:
        raise ValueError(f"unsupported motive signal packet version: {packet['packet_version']!r}")
    packet_agent = normalize_id(packet["agent"], "motive signal packet agent")
    if packet_agent != agent:
        raise ValueError("motive signal packet agent mismatch")
    signals = _normalize_signal_map(packet["signals"], "motive signal packet signals")
    sources = packet["sources"]
    if not isinstance(sources, dict) or set(sources) != _SOURCE_KEYS:
        raise ValueError("motive signal packet sources must contain the exact canonical source keys")
    _json_safe(sources, "motive signal packet sources")
    return {
        "packet_version": MOTIVE_SIGNAL_PACKET_VERSION,
        "agent": packet_agent,
        "signals": signals,
        "sources": deepcopy(sources),
    }


def _validate_contributions(
    item: dict,
    *,
    packet: dict,
    label: str,
    motive_id: str,
) -> tuple[list[dict], list[str], list[float], list[float], list[float]]:
    contributions = item["contributions"]
    missing = item["missing_signals"]
    if not isinstance(contributions, list) or not isinstance(missing, list):
        raise ValueError(f"{label} motive contributions/missing_signals are invalid")
    contribution_terms: list[float] = []
    support_terms: list[float] = []
    opposition_terms: list[float] = []
    expected_missing: list[str] = []
    seen_signals: set[str] = set()
    validated: list[dict] = []
    for index, raw in enumerate(contributions):
        c_label = f"{label} motive {motive_id}.contributions[{index}]"
        if not isinstance(raw, dict) or set(raw) != _CONTRIBUTION_KEYS:
            raise ValueError(f"{c_label} has invalid keys")
        signal = _signal_name(raw["signal"], f"{c_label}.signal")
        if signal in seen_signals:
            raise ValueError(
                f"{label} motive {motive_id} repeats contribution signal: {signal}"
            )
        seen_signals.add(signal)
        signal_value = _unit(raw["signal_value"], f"{c_label}.signal_value")
        weight = _signed_unit(raw["weight"], f"{c_label}.weight")
        contribution = _finite(raw["contribution"], f"{c_label}.contribution")
        expected_value = packet["signals"].get(signal, 0.0)
        if signal not in packet["signals"]:
            expected_missing.append(signal)
        if signal_value != expected_value or contribution != signal_value * weight:
            raise ValueError(f"{c_label} is inconsistent with signal/weight")
        contribution_terms.append(contribution)
        (support_terms if contribution >= 0.0 else opposition_terms).append(
            contribution if contribution >= 0.0 else -contribution
        )
        validated.append({
            "signal": signal,
            "signal_value": signal_value,
            "weight": weight,
            "contribution": contribution,
        })
    if missing != expected_missing:
        raise ValueError(
            f"{label} motive {motive_id}.missing_signals is inconsistent"
        )
    return validated, list(missing), contribution_terms, support_terms, opposition_terms


def _validate_motive_result(item: dict, *, motive_id: str, packet: dict, label: str) -> dict:
    if not isinstance(item, dict) or set(item) != _MOTIVE_RESULT_KEYS:
        raise ValueError(f"{label} motive {motive_id!r} has invalid keys")
    if normalize_id(item["motive_id"], f"{label} motive_id") != motive_id:
        raise ValueError(f"{label} motive key/id mismatch: {motive_id!r}")
    baseline = _unit(item["baseline"], f"{label} motive baseline")
    score = _unit(item["score"], f"{label} motive score")
    raw_score = _finite(item["raw_score"], f"{label} motive raw_score")
    support = _finite(item["support"], f"{label} motive support")
    opposition = _finite(item["opposition"], f"{label} motive opposition")
    if support < 0.0 or opposition < 0.0:
        raise ValueError(f"{label} motive support/opposition must be non-negative")
    validated, missing, terms, support_terms, opposition_terms = _validate_contributions(
        item, packet=packet, label=label, motive_id=motive_id,
    )
    expected_raw = math.fsum([baseline, *terms])
    if raw_score != expected_raw or score != _clamp01(expected_raw):
        raise ValueError(f"{label} motive {motive_id} score is inconsistent")
    if support != math.fsum(support_terms) or opposition != math.fsum(opposition_terms):
        raise ValueError(
            f"{label} motive {motive_id} support/opposition is inconsistent"
        )
    return {
        "motive_id": motive_id,
        "score": score,
        "raw_score": raw_score,
        "baseline": baseline,
        "support": support,
        "opposition": opposition,
        "missing_signals": missing,
        "contributions": validated,
    }


def _validate_history_record(raw_record: dict, *, agent: str, sequence: int, label: str) -> dict:
    if not isinstance(raw_record, dict):
        raise ValueError(f"{label} must be a dict")
    if set(raw_record) != _RECORD_KEYS:
        raise ValueError(f"{label} has invalid keys")
    _json_safe(raw_record, label)
    record = deepcopy(raw_record)
    record_sequence = _non_negative_int(record["sequence"], f"{label}.sequence")
    if record_sequence <= 0 or record_sequence > sequence:
        raise ValueError(f"{label}.sequence is invalid")
    if normalize_id(record["agent"], f"{label}.agent") != agent:
        raise ValueError(f"{label}.agent is inconsistent")
    packet = _validate_signal_packet({
        "packet_version": record["signal_packet_version"],
        "agent": agent,
        "signals": record["signals"],
        "sources": record["sources"],
    }, agent)
    motives = record["motives"]
    ranking = record["ranking"]
    if not isinstance(motives, dict) or not isinstance(ranking, list):
        raise ValueError(f"{label} motives/ranking are invalid")
    validated_motives: dict[str, dict] = {}
    seen_motive_ids: set[str] = set()
    for raw_motive_id in sorted(motives):
        motive_id = normalize_id(raw_motive_id, f"{label} motive id")
        if motive_id in seen_motive_ids:
            raise ValueError(
                f"{label} contains duplicate normalized motive id: {motive_id}"
            )
        seen_motive_ids.add(motive_id)
        validated_motives[motive_id] = _validate_motive_result(
            motives[raw_motive_id], motive_id=motive_id, packet=packet, label=label,
        )
    expected_ranking = sorted(
        validated_motives,
        key=lambda name: (-validated_motives[name]["score"], name),
    )
    if ranking != expected_ranking:
        raise ValueError(f"{label}.ranking is inconsistent")
    expected_dom = ranking[0] if ranking else None
    if record["dominant_motive"] != expected_dom:
        raise ValueError(f"{label}.dominant_motive is inconsistent")
    expected_score = (
        validated_motives[expected_dom]["score"] if expected_dom is not None else None
    )
    if record["dominant_score"] != expected_score:
        raise ValueError(f"{label}.dominant_score is inconsistent")
    return {
        "sequence": record_sequence,
        "agent": agent,
        "signal_packet_version": packet["packet_version"],
        "sources": packet["sources"],
        "signals": packet["signals"],
        "motives": validated_motives,
        "ranking": ranking,
        "dominant_motive": expected_dom,
        "dominant_score": expected_score,
    }




def _restore_motive_profiles(raw_profiles: dict) -> dict[str, dict[str, dict]]:
    profiles: dict[str, dict[str, dict]] = {}
    seen_agents: set[str] = set()
    for raw_agent in sorted(raw_profiles):
        agent = normalize_id(raw_agent, "motive snapshot profile agent")
        if agent in seen_agents:
            raise ValueError(
                f"motive snapshot profiles contains duplicate normalized agent: {agent}"
            )
        seen_agents.add(agent)
        items = raw_profiles[raw_agent]
        if not isinstance(items, dict):
            raise ValueError(f"motive snapshot profiles for {agent} must be a dict")
        validated: dict[str, dict] = {}
        seen_ids: set[str] = set()
        for raw_motive_id in sorted(items):
            motive_id = normalize_id(raw_motive_id, "motive snapshot profile id")
            if motive_id in seen_ids:
                raise ValueError(
                    f"motive snapshot profiles for {agent} contains duplicate normalized "
                    f"motive id: {motive_id}"
                )
            seen_ids.add(motive_id)
            item = items[raw_motive_id]
            if not isinstance(item, dict) or set(item) != _PROFILE_KEYS:
                raise ValueError(f"motive snapshot profile {motive_id!r} has invalid keys")
            built = _profile(motive_id, baseline=item["baseline"], weights=item["weights"])
            if normalize_id(item["motive_id"], "motive snapshot motive_id") != motive_id:
                raise ValueError(f"motive snapshot profile key/id mismatch: {motive_id!r}")
            validated[motive_id] = built
        if not validated:
            raise ValueError(f"motive snapshot profiles for {agent} must not be empty")
        profiles[agent] = validated
    return profiles


def _restore_motive_history(
    raw_history: dict,
    *,
    history_limit: int,
    sequence: int,
) -> dict[str, list[dict]]:
    history: dict[str, list[dict]] = {}
    seen_agents: set[str] = set()
    seen_sequences: set[int] = set()
    max_sequence = 0
    for raw_agent in sorted(raw_history):
        agent = normalize_id(raw_agent, "motive snapshot history agent")
        if agent in seen_agents:
            raise ValueError(
                f"motive snapshot history contains duplicate normalized agent: {agent}"
            )
        seen_agents.add(agent)
        records = raw_history[raw_agent]
        if not isinstance(records, list):
            raise ValueError(f"motive snapshot history for {agent} must be a list")
        if not records:
            raise ValueError(f"motive snapshot history for {agent} must not be empty")
        if len(records) > history_limit:
            raise ValueError(f"motive snapshot history for {agent} exceeds history_limit")
        validated_records: list[dict] = []
        previous = 0
        for index, raw_record in enumerate(records):
            label = f"motive snapshot history {agent}[{index}]"
            record = _validate_history_record(
                raw_record, agent=agent, sequence=sequence, label=label,
            )
            record_sequence = record["sequence"]
            if record_sequence <= previous:
                raise ValueError(f"{label}.sequence is invalid")
            if record_sequence in seen_sequences:
                raise ValueError(f"{label}.sequence is duplicated globally")
            previous = record_sequence
            seen_sequences.add(record_sequence)
            max_sequence = max(max_sequence, record_sequence)
            validated_records.append(record)
        history[agent] = validated_records
    if seen_sequences and max_sequence != sequence:
        raise ValueError(
            "latest motive history sequence must equal motive snapshot sequence"
        )
    if not seen_sequences and sequence != 0:
        raise ValueError("motive snapshot sequence must be zero when history is empty")
    return history


class MotiveRuntime:
    """Persistent configuration and audit history for deterministic motive fields."""

    def __init__(self, history_limit: int = DEFAULT_MOTIVE_HISTORY_LIMIT) -> None:
        self.history_limit = _positive_int(history_limit, "motive history_limit")
        self._sequence = 0
        self._profiles: dict[str, dict[str, dict]] = {}
        self._history: dict[str, list[dict]] = {}

    def has_state(self) -> bool:
        return bool(self._profiles or self._history)

    def agent_ids(self) -> list[str]:
        return sorted(set(self._profiles) | set(self._history))

    def configure(self, agent, motive_id, *, baseline=0.0, weights=None) -> dict:
        agent = normalize_id(agent, "motive agent")
        profile = _profile(motive_id, baseline=baseline, weights=weights)
        profiles = self._profiles.setdefault(agent, {})
        profiles[profile["motive_id"]] = profile
        self._profiles[agent] = {key: profiles[key] for key in sorted(profiles)}
        return deepcopy(profile)

    def remove(self, agent, motive_id) -> bool:
        agent = normalize_id(agent, "motive agent")
        motive_id = normalize_id(motive_id, "motive id")
        profiles = self._profiles.get(agent)
        if not profiles or motive_id not in profiles:
            return False
        del profiles[motive_id]
        if not profiles:
            del self._profiles[agent]
        return True

    def profiles(self, agent) -> dict[str, dict]:
        agent = normalize_id(agent, "motive agent")
        return deepcopy(self._profiles.get(agent, {}))

    def history(self, agent, *, limit: int | None = None) -> list[dict]:
        agent = normalize_id(agent, "motive agent")
        records = self._history.get(agent, [])
        if limit is None:
            return deepcopy(records)
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError("motive history limit must be a non-negative integer or None")
        if limit == 0:
            return []
        return deepcopy(records[-limit:])

    def current(self, agent) -> dict | None:
        records = self.history(agent, limit=1)
        return records[0] if records else None

    def evaluate(self, agent, signal_packet: dict) -> dict:
        agent = normalize_id(agent, "motive agent")
        packet = _validate_signal_packet(deepcopy(signal_packet), agent)
        profiles = self._profiles.get(agent, {})
        signals = packet["signals"]
        motives: dict[str, dict] = {}

        for motive_id in sorted(profiles):
            profile = profiles[motive_id]
            contribution_terms: list[float] = []
            support_terms: list[float] = []
            opposition_terms: list[float] = []
            missing: list[str] = []
            contributions: list[dict] = []
            for signal_name, weight in profile["weights"].items():
                if signal_name in signals:
                    signal_value = signals[signal_name]
                else:
                    signal_value = 0.0
                    missing.append(signal_name)
                contribution = signal_value * weight
                contribution_terms.append(contribution)
                if contribution >= 0.0:
                    support_terms.append(contribution)
                else:
                    opposition_terms.append(-contribution)
                contributions.append({
                    "signal": signal_name,
                    "signal_value": signal_value,
                    "weight": weight,
                    "contribution": contribution,
                })
            raw = math.fsum([profile["baseline"], *contribution_terms])
            support = math.fsum(support_terms)
            opposition = math.fsum(opposition_terms)
            motives[motive_id] = {
                "motive_id": motive_id,
                "score": _clamp01(raw),
                "raw_score": raw,
                "baseline": profile["baseline"],
                "support": support,
                "opposition": opposition,
                "missing_signals": missing,
                "contributions": contributions,
            }

        ranking = sorted(motives, key=lambda name: (-motives[name]["score"], name))
        self._sequence += 1
        record = {
            "sequence": self._sequence,
            "agent": agent,
            "signal_packet_version": packet["packet_version"],
            "sources": deepcopy(packet["sources"]),
            "signals": deepcopy(signals),
            "motives": motives,
            "ranking": ranking,
            "dominant_motive": ranking[0] if ranking else None,
            "dominant_score": motives[ranking[0]]["score"] if ranking else None,
        }
        records = self._history.setdefault(agent, [])
        records.append(deepcopy(record))
        if len(records) > self.history_limit:
            del records[: len(records) - self.history_limit]
        return deepcopy(record)

    def snapshot(self) -> dict:
        return {
            "schema_version": MOTIVE_SNAPSHOT_SCHEMA_VERSION,
            "history_limit": self.history_limit,
            "sequence": self._sequence,
            "profiles": deepcopy(self._profiles),
            "history": deepcopy(self._history),
        }

    @classmethod
    def from_snapshot(cls, snapshot: dict) -> "MotiveRuntime":
        if not isinstance(snapshot, dict):
            raise ValueError("motive snapshot must be a dict")
        unknown = set(snapshot) - _SNAPSHOT_KEYS
        if unknown:
            raise ValueError(
                "motive snapshot has unsupported keys: " + ", ".join(sorted(unknown))
            )
        missing = _SNAPSHOT_KEYS - set(snapshot)
        if missing:
            raise ValueError(
                "motive snapshot is missing required keys: " + ", ".join(sorted(missing))
            )
        _json_safe(snapshot, "motive snapshot")
        if snapshot["schema_version"] != MOTIVE_SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(
                "unsupported motive snapshot schema version: "
                f"{snapshot['schema_version']!r}"
            )
        history_limit = _positive_int(
            snapshot["history_limit"], "motive snapshot history_limit"
        )
        sequence = _non_negative_int(snapshot["sequence"], "motive snapshot sequence")
        raw_profiles = snapshot["profiles"]
        raw_history = snapshot["history"]
        if not isinstance(raw_profiles, dict):
            raise ValueError("motive snapshot profiles must be a dict")
        if not isinstance(raw_history, dict):
            raise ValueError("motive snapshot history must be a dict")
        runtime = cls(history_limit=history_limit)
        runtime._profiles = _restore_motive_profiles(raw_profiles)
        runtime._history = _restore_motive_history(
            raw_history, history_limit=history_limit, sequence=sequence,
        )
        runtime._sequence = sequence
        return runtime

