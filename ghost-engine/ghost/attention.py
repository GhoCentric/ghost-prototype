"""Deterministic persistent attention / flow runtime.

This layer models *access* to persistent internal state rather than mutating the
underlying emotion or interpretation itself. The host supplies current cognitive
signals and optional salience values. Ghost evolves a per-agent flow pressure,
applies hysteresis, exposes transient attention gain, and allows strong novelty,
threat, contradiction, or interpretation impulses to break through flow.

There is no timer pulse, no RNG, no action selection, and no dialogue generation.
Flow emerges from the agent's signal trajectory. Underlying salience values are
copied into diagnostics and are never rewritten by this runtime.
"""

from __future__ import annotations

from copy import deepcopy
import math

from .ids import normalize_id


ATTENTION_SNAPSHOT_SCHEMA_VERSION = "1.0"
DEFAULT_ATTENTION_HISTORY_LIMIT = 64

DEFAULT_FLOW_ENTRY_THRESHOLD = 0.72
DEFAULT_FLOW_EXIT_THRESHOLD = 0.44
DEFAULT_FLOW_BUILD_RATE = 0.26
DEFAULT_FLOW_RELEASE_RATE = 0.48
DEFAULT_INTERRUPT_THRESHOLD = 0.72
DEFAULT_INTERRUPT_RELEASE = 0.82
DEFAULT_MAX_SUPPRESSION = 0.96

_SIGNAL_NAMES = (
    "task_focus",
    "repetition",
    "stability",
    "novelty",
    "threat",
    "contradiction",
    "interpretation_impulse",
)

_DEFAULT_SIGNALS = {name: 0.0 for name in _SIGNAL_NAMES}


def _agent_id(value, label: str = "attention agent") -> str:
    return normalize_id(value, label)


def _token(value, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _finite(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return value


def _unit(value, label: str) -> float:
    value = _finite(value, label)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{label} must be in [0, 1]")
    return value


def _json_safe(value, label: str = "value") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        _finite(value, label)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _json_safe(item, f"{label}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{label} keys must be strings")
            _json_safe(item, f"{label}.{key}")
        return
    raise ValueError(f"{label} must be JSON-safe")


def _validate_history_limit(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("history_limit must be a positive integer")
    return value


def _validate_config(value: dict | None) -> dict[str, float]:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError("attention config must be a dict or None")

    allowed = {
        "entry_threshold",
        "exit_threshold",
        "build_rate",
        "release_rate",
        "interrupt_threshold",
        "interrupt_release",
        "max_suppression",
    }
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(
            "attention config has unsupported keys: " + ", ".join(sorted(unknown))
        )

    config = {
        "entry_threshold": _unit(
            value.get("entry_threshold", DEFAULT_FLOW_ENTRY_THRESHOLD),
            "attention config.entry_threshold",
        ),
        "exit_threshold": _unit(
            value.get("exit_threshold", DEFAULT_FLOW_EXIT_THRESHOLD),
            "attention config.exit_threshold",
        ),
        "build_rate": _unit(
            value.get("build_rate", DEFAULT_FLOW_BUILD_RATE),
            "attention config.build_rate",
        ),
        "release_rate": _unit(
            value.get("release_rate", DEFAULT_FLOW_RELEASE_RATE),
            "attention config.release_rate",
        ),
        "interrupt_threshold": _unit(
            value.get("interrupt_threshold", DEFAULT_INTERRUPT_THRESHOLD),
            "attention config.interrupt_threshold",
        ),
        "interrupt_release": _unit(
            value.get("interrupt_release", DEFAULT_INTERRUPT_RELEASE),
            "attention config.interrupt_release",
        ),
        "max_suppression": _unit(
            value.get("max_suppression", DEFAULT_MAX_SUPPRESSION),
            "attention config.max_suppression",
        ),
    }
    if config["exit_threshold"] > config["entry_threshold"]:
        raise ValueError("attention config.exit_threshold cannot exceed entry_threshold")
    return config


def _validate_signals(value: dict | None) -> dict[str, float]:
    if value is None:
        return deepcopy(_DEFAULT_SIGNALS)
    if not isinstance(value, dict):
        raise ValueError("signals must be a dict or None")
    unknown = set(value) - set(_SIGNAL_NAMES)
    if unknown:
        raise ValueError("signals has unsupported keys: " + ", ".join(sorted(unknown)))
    result = deepcopy(_DEFAULT_SIGNALS)
    for name, raw in value.items():
        result[name] = _unit(raw, f"signals.{name}")
    return result


def _validate_salience(value: dict | None) -> dict[str, float]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("salience must be a dict or None")
    result: dict[str, float] = {}
    for raw_name, raw_value in value.items():
        name = _token(raw_name, "salience name")
        if name in result:
            raise ValueError(f"salience contains duplicate normalized name: {name}")
        result[name] = _unit(raw_value, f"salience.{name}")
    return result


def _support(signals: dict[str, float]) -> float:
    """Return deterministic flow support in [0, 1]."""
    return (
        0.34 * signals["task_focus"]
        + 0.24 * signals["repetition"]
        + 0.18 * signals["stability"]
        + 0.14 * (1.0 - signals["novelty"])
        + 0.10 * (1.0 - signals["threat"])
    )


def _interrupt_strength(signals: dict[str, float]) -> float:
    return max(
        signals["novelty"],
        signals["threat"],
        signals["contradiction"],
        signals["interpretation_impulse"],
    )


def _resolve_flow(previous: bool, pressure: float, config: dict[str, float]) -> bool:
    if previous:
        return pressure > config["exit_threshold"]
    return pressure >= config["entry_threshold"]


def _transition(previous: bool, current: bool) -> str:
    if not previous and current:
        return "entered"
    if previous and not current:
        return "released"
    return "retained_active" if current else "inactive"


def _flow_depth(active: bool, pressure: float, config: dict[str, float]) -> float:
    if not active:
        return 0.0
    entry = config["entry_threshold"]
    if entry >= 1.0:
        return 1.0
    return min(1.0, max(0.0, (pressure - entry) / (1.0 - entry)))


def _attention_gain(
    active: bool,
    pressure: float,
    config: dict[str, float],
    breakthrough: bool,
) -> float:
    if breakthrough or not active:
        return 1.0
    depth = _flow_depth(True, pressure, config)
    suppression = config["max_suppression"] * (0.35 + 0.65 * depth)
    return max(0.0, 1.0 - suppression)


class AttentionRuntime:
    """Persistent deterministic attention / flow state for individual agents."""

    def __init__(self, history_limit: int = DEFAULT_ATTENTION_HISTORY_LIMIT):
        self.history_limit = _validate_history_limit(history_limit)
        self._sequence = 0
        self._agents: dict[str, dict] = {}

    def has_state(self) -> bool:
        return bool(self._agents)

    def register_agent(
        self,
        agent: str,
        *,
        initial_flow_pressure: float | None = None,
        flow_active: bool | None = None,
        config: dict | None = None,
    ) -> dict:
        agent = _agent_id(agent)
        pressure = (
            None
            if initial_flow_pressure is None
            else _unit(initial_flow_pressure, "initial_flow_pressure")
        )
        validated_config = _validate_config(config)
        if flow_active is not None and not isinstance(flow_active, bool):
            raise ValueError("flow_active must be a bool or None")

        current = deepcopy(self._agents.get(agent))
        if current is None:
            current = {
                "flow_pressure": 0.0 if pressure is None else pressure,
                "flow_active": False,
                "config": validated_config,
                "history": [],
            }
        else:
            if pressure is not None:
                current["flow_pressure"] = pressure
            if config is not None:
                current["config"] = validated_config

        if flow_active is None:
            current["flow_active"] = _resolve_flow(
                bool(current["flow_active"]),
                current["flow_pressure"],
                current["config"],
            )
        else:
            current["flow_active"] = flow_active
            expected = _resolve_flow(
                False if not flow_active else True,
                current["flow_pressure"],
                current["config"],
            )
            if expected != flow_active:
                raise ValueError("flow_active is inconsistent with pressure/config hysteresis")

        self._agents[agent] = current
        return self.get_state(agent)

    def get_state(self, agent: str) -> dict | None:
        agent = _agent_id(agent)
        state = self._agents.get(agent)
        if state is None:
            return None
        packet = deepcopy(state)
        packet["agent"] = agent
        packet["flow_depth"] = _flow_depth(
            bool(state["flow_active"]),
            state["flow_pressure"],
            state["config"],
        )
        packet["attention_gain"] = _attention_gain(
            bool(state["flow_active"]),
            state["flow_pressure"],
            state["config"],
            False,
        )
        return packet

    def step(
        self,
        agent: str,
        *,
        signals: dict | None = None,
        salience: dict | None = None,
        source: str | None = None,
        provenance: dict | None = None,
    ) -> dict:
        agent = _agent_id(agent)
        signal_map = _validate_signals(signals)
        salience_map = _validate_salience(salience)
        if source is not None:
            source = _token(source, "source")
        if provenance is not None:
            if not isinstance(provenance, dict):
                raise ValueError("provenance must be a dict or None")
            _json_safe(provenance, "provenance")

        # Validation is complete before implicit registration so a rejected
        # step cannot create or otherwise mutate attention state.
        if agent not in self._agents:
            self.register_agent(agent)

        state = self._agents[agent]
        config = state["config"]
        before_pressure = state["flow_pressure"]
        before_active = bool(state["flow_active"])

        support = _support(signal_map)
        interrupt = _interrupt_strength(signal_map)
        target_pressure = support * (1.0 - 0.85 * interrupt)

        if target_pressure >= before_pressure:
            rate = config["build_rate"]
        else:
            rate = config["release_rate"]
        pressure = before_pressure + (target_pressure - before_pressure) * rate

        breakthrough = interrupt >= config["interrupt_threshold"]
        if breakthrough:
            pressure *= max(0.0, 1.0 - config["interrupt_release"] * interrupt)
        pressure = min(1.0, max(0.0, pressure))

        active = _resolve_flow(before_active, pressure, config)
        transition = _transition(before_active, active)
        depth = _flow_depth(active, pressure, config)
        gain = _attention_gain(active, pressure, config, breakthrough)
        attended = {
            name: min(1.0, max(0.0, value * gain))
            for name, value in salience_map.items()
        }
        resurfaced = before_active and (not active or breakthrough)

        self._sequence += 1
        record = {
            "sequence": self._sequence,
            "agent": agent,
            "source": source,
            "config": deepcopy(config),
            "signals": deepcopy(signal_map),
            "support": support,
            "interrupt_strength": interrupt,
            "breakthrough": breakthrough,
            "target_flow_pressure": target_pressure,
            "flow_pressure_before": before_pressure,
            "flow_pressure_after": pressure,
            "flow_active_before": before_active,
            "flow_active_after": active,
            "transition": transition,
            "flow_depth": depth,
            "attention_gain": gain,
            "resurfaced": resurfaced,
            "underlying_salience": deepcopy(salience_map),
            "attended_salience": deepcopy(attended),
            "provenance": deepcopy(provenance),
        }
        state["flow_pressure"] = pressure
        state["flow_active"] = active
        state["history"].append(deepcopy(record))
        if len(state["history"]) > self.history_limit:
            del state["history"][: len(state["history"]) - self.history_limit]
        return deepcopy(record)

    def _advance_idle_time(self, agent: str, calls: int) -> dict | None:
        """Advance no-signal attention time without allocating history records."""
        if isinstance(calls, bool) or not isinstance(calls, int) or calls < 1:
            raise ValueError("calls must be a positive integer")
        agent = _token(agent, "agent")
        state = self._agents.get(agent)
        if state is None:
            return None
        config = state["config"]
        pressure = state["flow_pressure"] * ((1.0 - config["release_rate"]) ** calls)
        pressure = min(1.0, max(0.0, pressure))
        state["flow_pressure"] = pressure
        state["flow_active"] = _resolve_flow(
            bool(state["flow_active"]),
            pressure,
            config,
        )
        return self.get_state(agent)

    def snapshot(self) -> dict:
        return {
            "schema_version": ATTENTION_SNAPSHOT_SCHEMA_VERSION,
            "history_limit": self.history_limit,
            "sequence": self._sequence,
            "agents": deepcopy(self._agents),
        }

    @classmethod
    def from_snapshot(cls, snapshot: dict) -> "AttentionRuntime":
        if not isinstance(snapshot, dict):
            raise ValueError("attention snapshot must be a dict")
        allowed = {"schema_version", "history_limit", "sequence", "agents"}
        unknown = set(snapshot) - allowed
        if unknown:
            raise ValueError(
                "attention snapshot has unsupported keys: " + ", ".join(sorted(unknown))
            )
        missing = allowed - set(snapshot)
        if missing:
            raise ValueError(
                "attention snapshot is missing required keys: " + ", ".join(sorted(missing))
            )
        _json_safe(snapshot, "attention snapshot")
        if snapshot["schema_version"] != ATTENTION_SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(
                "unsupported attention snapshot schema version: "
                f"{snapshot['schema_version']!r}"
            )

        runtime = cls(history_limit=_validate_history_limit(snapshot["history_limit"]))
        sequence = snapshot["sequence"]
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            raise ValueError("attention snapshot sequence must be a non-negative integer")
        agents = snapshot["agents"]
        if not isinstance(agents, dict):
            raise ValueError("attention snapshot agents must be a dict")

        restored: dict[str, dict] = {}
        seen_history_sequences: set[int] = set()
        max_history_sequence = 0
        record_keys = {
            "sequence",
            "agent",
            "source",
            "signals",
            "support",
            "interrupt_strength",
            "breakthrough",
            "target_flow_pressure",
            "flow_pressure_before",
            "flow_pressure_after",
            "flow_active_before",
            "flow_active_after",
            "transition",
            "flow_depth",
            "attention_gain",
            "resurfaced",
            "underlying_salience",
            "attended_salience",
            "provenance",
        }
        record_keys_with_config = record_keys | {"config"}

        for raw_agent, raw_state in agents.items():
            agent = _agent_id(raw_agent, "attention snapshot agent")
            if agent in restored:
                raise ValueError(
                    f"attention snapshot contains duplicate normalized agent: {agent}"
                )
            if not isinstance(raw_state, dict):
                raise ValueError(f"attention snapshot agent {agent} must be a dict")
            expected_keys = {"flow_pressure", "flow_active", "config", "history"}
            if set(raw_state) != expected_keys:
                raise ValueError(
                    f"attention snapshot agent {agent} keys must be exactly: "
                    + ", ".join(sorted(expected_keys))
                )
            pressure = _unit(
                raw_state["flow_pressure"],
                f"attention snapshot agent {agent}.flow_pressure",
            )
            active = raw_state["flow_active"]
            if not isinstance(active, bool):
                raise ValueError(
                    f"attention snapshot agent {agent}.flow_active must be a bool"
                )
            config = _validate_config(raw_state["config"])
            if config != raw_state["config"]:
                raise ValueError(
                    f"attention snapshot agent {agent}.config must be canonical and complete"
                )
            if _resolve_flow(active, pressure, config) != active:
                raise ValueError(
                    f"attention snapshot agent {agent} flow state is inconsistent"
                )
            history = raw_state["history"]
            if not isinstance(history, list):
                raise ValueError(
                    f"attention snapshot agent {agent}.history must be a list"
                )
            if len(history) > runtime.history_limit:
                raise ValueError(
                    f"attention snapshot agent {agent}.history exceeds history_limit"
                )

            previous_sequence = 0
            validated_history = []
            for index, raw_record in enumerate(history):
                label = f"attention snapshot agent {agent}.history[{index}]"
                if not isinstance(raw_record, dict):
                    raise ValueError(f"{label} must be a dict")
                raw_record_keys = set(raw_record)
                if (
                    raw_record_keys != record_keys
                    and raw_record_keys != record_keys_with_config
                ):
                    raise ValueError(f"{label} has invalid keys")
                _json_safe(raw_record, label)
                record = deepcopy(raw_record)
                record_sequence = record["sequence"]
                if (
                    isinstance(record_sequence, bool)
                    or not isinstance(record_sequence, int)
                    or record_sequence <= previous_sequence
                    or record_sequence < 1
                    or record_sequence > sequence
                ):
                    raise ValueError(f"{label}.sequence is invalid")
                if record_sequence in seen_history_sequences:
                    raise ValueError(
                        f"attention snapshot history sequence is duplicated: {record_sequence}"
                    )
                seen_history_sequences.add(record_sequence)
                if record["agent"] != agent:
                    raise ValueError(f"{label}.agent is inconsistent")
                source = record["source"]
                if source is not None:
                    canonical_source = _token(source, f"{label}.source")
                    if canonical_source != source:
                        raise ValueError(f"{label}.source must be canonical")

                signals = _validate_signals(record["signals"])
                if signals != record["signals"]:
                    raise ValueError(f"{label}.signals must be canonical and complete")
                support = _unit(record["support"], f"{label}.support")
                expected_support = _support(signals)
                if not math.isclose(support, expected_support, rel_tol=0.0, abs_tol=1e-15):
                    raise ValueError(f"{label}.support is inconsistent")
                interrupt = _unit(
                    record["interrupt_strength"],
                    f"{label}.interrupt_strength",
                )
                expected_interrupt = _interrupt_strength(signals)
                if not math.isclose(
                    interrupt, expected_interrupt, rel_tol=0.0, abs_tol=1e-15
                ):
                    raise ValueError(f"{label}.interrupt_strength is inconsistent")
                breakthrough = record["breakthrough"]
                if not isinstance(breakthrough, bool):
                    raise ValueError(f"{label}.breakthrough must be bool")
                target_pressure = _unit(
                    record["target_flow_pressure"],
                    f"{label}.target_flow_pressure",
                )
                expected_target = support * (1.0 - 0.85 * interrupt)
                if not math.isclose(
                    target_pressure, expected_target, rel_tol=0.0, abs_tol=1e-15
                ):
                    raise ValueError(f"{label}.target_flow_pressure is inconsistent")

                before_pressure = _unit(
                    record["flow_pressure_before"],
                    f"{label}.flow_pressure_before",
                )
                after_pressure = _unit(
                    record["flow_pressure_after"],
                    f"{label}.flow_pressure_after",
                )
                before_active = record["flow_active_before"]
                after_active = record["flow_active_after"]
                if not isinstance(before_active, bool):
                    raise ValueError(f"{label}.flow_active_before must be bool")
                if not isinstance(after_active, bool):
                    raise ValueError(f"{label}.flow_active_after must be bool")
                transition = record["transition"]
                expected_transition = _transition(before_active, after_active)
                if transition != expected_transition:
                    raise ValueError(f"{label}.transition is inconsistent")

                record_config = None
                if "config" in record:
                    record_config = _validate_config(record["config"])
                    if record_config != record["config"]:
                        raise ValueError(f"{label}.config must be canonical and complete")
                    expected_breakthrough = (
                        interrupt >= record_config["interrupt_threshold"]
                    )
                    if breakthrough != expected_breakthrough:
                        raise ValueError(f"{label}.breakthrough is inconsistent")
                    rate = (
                        record_config["build_rate"]
                        if target_pressure >= before_pressure
                        else record_config["release_rate"]
                    )
                    expected_pressure = before_pressure + (
                        target_pressure - before_pressure
                    ) * rate
                    if breakthrough:
                        expected_pressure *= max(
                            0.0,
                            1.0
                            - record_config["interrupt_release"] * interrupt,
                        )
                    expected_pressure = min(1.0, max(0.0, expected_pressure))
                    if not math.isclose(
                        after_pressure,
                        expected_pressure,
                        rel_tol=0.0,
                        abs_tol=1e-15,
                    ):
                        raise ValueError(f"{label}.flow pressure math is inconsistent")
                    expected_active = _resolve_flow(
                        before_active, after_pressure, record_config
                    )
                    if after_active != expected_active:
                        raise ValueError(f"{label}.flow active math is inconsistent")

                depth = _unit(record["flow_depth"], f"{label}.flow_depth")
                gain = _unit(record["attention_gain"], f"{label}.attention_gain")
                if record_config is not None:
                    expected_depth = _flow_depth(
                        after_active, after_pressure, record_config
                    )
                    expected_gain = _attention_gain(
                        after_active,
                        after_pressure,
                        record_config,
                        breakthrough,
                    )
                    if not math.isclose(
                        depth, expected_depth, rel_tol=0.0, abs_tol=1e-15
                    ):
                        raise ValueError(f"{label}.flow_depth is inconsistent")
                    if not math.isclose(
                        gain, expected_gain, rel_tol=0.0, abs_tol=1e-15
                    ):
                        raise ValueError(f"{label}.attention_gain is inconsistent")

                resurfaced = record["resurfaced"]
                if not isinstance(resurfaced, bool):
                    raise ValueError(f"{label}.resurfaced must be bool")
                expected_resurfaced = before_active and (
                    not after_active or breakthrough
                )
                if resurfaced != expected_resurfaced:
                    raise ValueError(f"{label}.resurfaced is inconsistent")

                underlying = _validate_salience(record["underlying_salience"])
                attended = _validate_salience(record["attended_salience"])
                if underlying != record["underlying_salience"]:
                    raise ValueError(
                        f"{label}.underlying_salience must be canonical"
                    )
                if attended != record["attended_salience"]:
                    raise ValueError(f"{label}.attended_salience must be canonical")
                if set(attended) != set(underlying):
                    raise ValueError(f"{label}.attended_salience dimensions mismatch")
                for name, value in underlying.items():
                    expected_attended = min(1.0, max(0.0, value * gain))
                    if not math.isclose(
                        attended[name],
                        expected_attended,
                        rel_tol=0.0,
                        abs_tol=1e-15,
                    ):
                        raise ValueError(
                            f"{label}.attended_salience.{name} is inconsistent"
                        )

                provenance = record["provenance"]
                if provenance is not None and not isinstance(provenance, dict):
                    raise ValueError(f"{label}.provenance must be a dict or None")

                previous_sequence = record_sequence
                max_history_sequence = max(max_history_sequence, record_sequence)
                validated_history.append(record)

            restored[agent] = {
                "flow_pressure": pressure,
                "flow_active": active,
                "config": config,
                "history": validated_history,
            }

        if restored and max_history_sequence != sequence:
            raise ValueError("latest attention history sequence must equal sequence")
        if not restored and sequence != 0:
            raise ValueError("attention snapshot sequence must be zero when agents are empty")

        runtime._sequence = sequence
        runtime._agents = restored
        return runtime
