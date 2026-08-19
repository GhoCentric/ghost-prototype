"""Deterministic NPC-specific interpretation pressure runtime.

This layer separates an objective action from what that action means to a
particular NPC. The host supplies observable action features. Each NPC owns a
rule map, sensitivity, baseline, and activation/release thresholds for arbitrary
interpretation dimensions such as ``betrayal``, ``cooperation``, or ``threat``.

Ghost does not infer hidden facts, choose an action, or generate dialogue here.
"""

from __future__ import annotations

from copy import deepcopy
import math
import sys

from .ids import normalize_id


INTERPRETATION_SNAPSHOT_SCHEMA_VERSION = "1.0"
DEFAULT_INTERPRETATION_THRESHOLD = 0.65
DEFAULT_INTERPRETATION_RELEASE_MARGIN = 0.15
DEFAULT_INTERPRETATION_HISTORY_LIMIT = 64
_MAX_FINITE_FLOAT = sys.float_info.max


def _agent_id(value, label: str = "interpretation agent") -> str:
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


def _non_negative(value, label: str) -> float:
    value = _finite(value, label)
    if value < 0.0:
        raise ValueError(f"{label} must be non-negative")
    return value


def _signed_unit(value, label: str) -> float:
    value = _finite(value, label)
    if not -1.0 <= value <= 1.0:
        raise ValueError(f"{label} must be in [-1, 1]")
    return value


def _saturating_product(weight: float, *factors: float) -> float:
    """Multiply finite factors without allowing diagnostic overflow."""
    if weight == 0.0:
        return 0.0
    sign = -1.0 if weight < 0.0 else 1.0
    magnitude = abs(weight)
    for factor in factors:
        if factor == 0.0:
            return 0.0
        if magnitude > _MAX_FINITE_FLOAT / factor:
            return sign * _MAX_FINITE_FLOAT
        magnitude *= factor
    return sign * magnitude


def _saturating_add(left: float, right: float) -> float:
    """Add finite diagnostics while preserving a finite saturation bound."""
    total = left + right
    if math.isfinite(total):
        return total
    return _MAX_FINITE_FLOAT if right >= 0.0 else -_MAX_FINITE_FLOAT


def _json_safe(value, label: str = "value"):
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


def _validate_number_map(value, label: str, validator) -> dict[str, float]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a dict or None")
    result = {}
    for raw_name, raw_value in value.items():
        name = _token(raw_name, f"{label} name")
        if name in result:
            raise ValueError(f"{label} contains duplicate normalized name: {name}")
        result[name] = validator(raw_value, f"{label}.{name}")
    return result


def _validate_thresholds(value) -> dict[str, dict[str, float]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("thresholds must be a dict or None")
    result = {}
    for raw_name, raw_spec in value.items():
        name = _token(raw_name, "threshold name")
        if name in result:
            raise ValueError(f"thresholds contains duplicate normalized name: {name}")
        if isinstance(raw_spec, dict):
            unknown = set(raw_spec) - {"enter", "exit"}
            if unknown:
                raise ValueError(
                    f"thresholds.{name} has unsupported keys: "
                    + ", ".join(sorted(unknown))
                )
            if "enter" not in raw_spec:
                raise ValueError(f"thresholds.{name}.enter is required")
            enter = _unit(raw_spec["enter"], f"thresholds.{name}.enter")
            exit_value = raw_spec.get(
                "exit",
                max(0.0, enter - DEFAULT_INTERPRETATION_RELEASE_MARGIN),
            )
            exit_level = _unit(exit_value, f"thresholds.{name}.exit")
        else:
            enter = _unit(raw_spec, f"thresholds.{name}")
            exit_level = max(
                0.0,
                enter - DEFAULT_INTERPRETATION_RELEASE_MARGIN,
            )
        if exit_level > enter:
            raise ValueError(f"thresholds.{name}.exit cannot exceed enter")
        result[name] = {"enter": enter, "exit": exit_level}
    return result


def _validate_rules(value) -> dict[str, dict[str, float]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("rules must be a dict or None")
    result = {}
    for raw_feature, raw_pressures in value.items():
        feature = _token(raw_feature, "rule feature")
        if feature in result:
            raise ValueError(f"rules contains duplicate normalized feature: {feature}")
        if not isinstance(raw_pressures, dict):
            raise ValueError(f"rules.{feature} must be a dict")
        pressures = {}
        for raw_dimension, raw_weight in raw_pressures.items():
            dimension = _token(raw_dimension, f"rules.{feature} dimension")
            if dimension in pressures:
                raise ValueError(
                    f"rules.{feature} contains duplicate normalized dimension: {dimension}"
                )
            pressures[dimension] = _signed_unit(
                raw_weight,
                f"rules.{feature}.{dimension}",
            )
        result[feature] = pressures
    return result


def _default_threshold() -> dict[str, float]:
    return {
        "enter": DEFAULT_INTERPRETATION_THRESHOLD,
        "exit": max(
            0.0,
            DEFAULT_INTERPRETATION_THRESHOLD
            - DEFAULT_INTERPRETATION_RELEASE_MARGIN,
        ),
    }


def _resolve_active(previous: bool, level: float, threshold: dict[str, float]) -> bool:
    if previous:
        return level > threshold["exit"]
    return level >= threshold["enter"]


def _transition(previous: bool, current: bool) -> str:
    if not previous and current:
        return "entered"
    if previous and not current:
        return "released"
    return "retained_active" if current else "inactive"


class InterpretationRuntime:
    """Persistent deterministic action-to-meaning state for individual agents."""

    def __init__(self, history_limit: int = DEFAULT_INTERPRETATION_HISTORY_LIMIT):
        if isinstance(history_limit, bool) or not isinstance(history_limit, int):
            raise ValueError("history_limit must be a positive integer")
        if history_limit <= 0:
            raise ValueError("history_limit must be a positive integer")
        self.history_limit = history_limit
        self._sequence = 0
        self._agents: dict[str, dict] = {}

    def has_state(self) -> bool:
        return bool(self._agents)

    def register_agent(
        self,
        agent: str,
        initial: dict | None = None,
        baseline: dict | None = None,
        thresholds: dict | None = None,
        sensitivities: dict | None = None,
        rules: dict | None = None,
    ) -> dict:
        agent = _agent_id(agent)
        initial_map = _validate_number_map(initial, "initial", _unit)
        baseline_map = _validate_number_map(baseline, "baseline", _unit)
        threshold_map = _validate_thresholds(thresholds)
        sensitivity_map = _validate_number_map(
            sensitivities,
            "sensitivities",
            _non_negative,
        )
        rule_map = _validate_rules(rules)

        current = deepcopy(self._agents.get(agent))
        if current is None:
            current = {
                "levels": {},
                "baseline": {},
                "thresholds": {},
                "sensitivities": {},
                "rules": {},
                "active": {},
                "history": [],
            }

        dimensions = set(current["levels"])
        dimensions.update(initial_map)
        dimensions.update(baseline_map)
        dimensions.update(threshold_map)
        dimensions.update(sensitivity_map)
        for pressures in rule_map.values():
            dimensions.update(pressures)

        for dimension in sorted(dimensions):
            if dimension not in current["levels"]:
                current["levels"][dimension] = baseline_map.get(dimension, 0.0)
            if dimension not in current["baseline"]:
                current["baseline"][dimension] = 0.0
            if dimension not in current["thresholds"]:
                current["thresholds"][dimension] = _default_threshold()
            if dimension not in current["sensitivities"]:
                current["sensitivities"][dimension] = 1.0
            if dimension not in current["active"]:
                current["active"][dimension] = False

        for dimension, value in baseline_map.items():
            current["baseline"][dimension] = value
        for dimension, value in initial_map.items():
            current["levels"][dimension] = value
        for dimension, value in threshold_map.items():
            current["thresholds"][dimension] = deepcopy(value)
        for dimension, value in sensitivity_map.items():
            current["sensitivities"][dimension] = value
        for feature, pressures in rule_map.items():
            current["rules"][feature] = deepcopy(pressures)

        for dimension in sorted(dimensions):
            current["active"][dimension] = _resolve_active(
                bool(current["active"].get(dimension, False)),
                current["levels"][dimension],
                current["thresholds"][dimension],
            )

        self._agents[agent] = current
        return self.get_state(agent)

    def configure_rule(
        self,
        agent: str,
        feature: str,
        pressures: dict,
    ) -> dict:
        agent = _agent_id(agent)
        feature = _token(feature, "feature")
        pressure_map = _validate_rules({feature: pressures})[feature]
        if agent not in self._agents:
            self.register_agent(agent)
        self.register_agent(agent, rules={feature: pressure_map})
        return {
            "agent": agent,
            "feature": feature,
            "pressures": deepcopy(pressure_map),
        }

    def get_state(self, agent: str) -> dict | None:
        agent = _agent_id(agent)
        state = self._agents.get(agent)
        if state is None:
            return None
        packet = deepcopy(state)
        active = [
            dimension
            for dimension in sorted(packet["active"])
            if packet["active"][dimension]
        ]
        strongest = None
        strongest_level = 0.0
        if packet["levels"]:
            strongest = min(
                packet["levels"],
                key=lambda name: (-packet["levels"][name], name),
            )
            strongest_level = packet["levels"][strongest]
            if strongest_level <= 0.0:
                strongest = None
        packet["agent"] = agent
        packet["active_interpretations"] = active
        packet["strongest_interpretation"] = strongest
        packet["strongest_level"] = strongest_level
        return packet

    def evaluate_action(
        self,
        agent: str,
        action: str,
        features: dict | None = None,
        intensity: float = 1.0,
        context_modifiers: dict | None = None,
        source: str | None = None,
        provenance: dict | None = None,
    ) -> dict:
        agent = _agent_id(agent)
        action = _token(action, "action")
        intensity = _unit(intensity, "action intensity")
        feature_map = _validate_number_map(features, "features", _unit)
        reserved = [
            feature
            for feature in feature_map
            if feature.startswith("action:")
        ]
        if reserved:
            raise ValueError(
                "features cannot use reserved action: keys: "
                + ", ".join(sorted(reserved))
            )
        context_map = _validate_number_map(
            context_modifiers,
            "context_modifiers",
            _non_negative,
        )
        if source is not None:
            source = _agent_id(source, "interpretation source")
        if provenance is not None:
            if not isinstance(provenance, dict):
                raise ValueError("provenance must be a dict or None")
            _json_safe(provenance, "provenance")
            provenance = deepcopy(provenance)

        if agent not in self._agents:
            raise ValueError(f"interpretation agent is not registered: {agent}")

        objective_features = {f"action:{action}": 1.0}
        objective_features.update(feature_map)
        before = self.get_state(agent)
        working = deepcopy(self._agents[agent])

        contributions = []
        aggregate: dict[str, float] = {}
        for feature in sorted(objective_features):
            strength = objective_features[feature]
            pressures = working["rules"].get(feature, {})
            for dimension in sorted(pressures):
                weight = pressures[dimension]
                sensitivity = working["sensitivities"].get(dimension, 1.0)
                context = context_map.get(dimension, 1.0)
                value = _saturating_product(
                    weight,
                    strength,
                    intensity,
                    sensitivity,
                    context,
                )
                aggregate[dimension] = _saturating_add(
                    aggregate.get(dimension, 0.0),
                    value,
                )
                contributions.append(
                    {
                        "feature": feature,
                        "feature_strength": strength,
                        "interpretation": dimension,
                        "rule_weight": weight,
                        "sensitivity": sensitivity,
                        "context_modifier": context,
                        "contribution": value,
                    }
                )

        transitions = {}
        for dimension in sorted(aggregate):
            raw_impulse = aggregate[dimension]
            effective_impulse = max(-1.0, min(1.0, raw_impulse))
            level_before = working["levels"][dimension]
            if effective_impulse >= 0.0:
                level_after = level_before + (1.0 - level_before) * effective_impulse
            else:
                level_after = level_before * (1.0 + effective_impulse)
            level_after = max(0.0, min(1.0, level_after))

            active_before = bool(working["active"].get(dimension, False))
            active_after = _resolve_active(
                active_before,
                level_after,
                working["thresholds"][dimension],
            )
            working["levels"][dimension] = level_after
            working["active"][dimension] = active_after
            transitions[dimension] = {
                "level_before": level_before,
                "level_after": level_after,
                "raw_impulse": raw_impulse,
                "effective_impulse": effective_impulse,
                "active_before": active_before,
                "active_after": active_after,
                "transition": _transition(active_before, active_after),
                "threshold": deepcopy(working["thresholds"][dimension]),
            }

        self._sequence += 1
        history_entry = {
            "sequence": self._sequence,
            "action": action,
            "source": source,
            "features": deepcopy(objective_features),
            "transitions": deepcopy(transitions),
            "provenance": deepcopy(provenance),
        }
        working["history"].append(history_entry)
        working["history"] = working["history"][-self.history_limit :]
        self._agents[agent] = working
        after = self.get_state(agent)

        return {
            "sequence": self._sequence,
            "agent": agent,
            "objective_action": {
                "type": action,
                "intensity": intensity,
                "features": deepcopy(objective_features),
                "source": source,
                "provenance": deepcopy(provenance),
            },
            "contributions": contributions,
            "transitions": transitions,
            "state_before": before,
            "state": after,
            "active_interpretations": deepcopy(after["active_interpretations"]),
            "strongest_interpretation": after["strongest_interpretation"],
            "strongest_level": after["strongest_level"],
        }

    def snapshot(self) -> dict:
        packet = {
            "schema_version": INTERPRETATION_SNAPSHOT_SCHEMA_VERSION,
            "history_limit": self.history_limit,
            "sequence": self._sequence,
            "agents": deepcopy(self._agents),
        }
        _json_safe(packet, "interpretation snapshot")
        return packet

    @classmethod
    def from_snapshot(cls, snapshot: dict) -> "InterpretationRuntime":
        if not isinstance(snapshot, dict):
            raise ValueError("interpretation snapshot must be a dict")
        if set(snapshot) != {"schema_version", "history_limit", "sequence", "agents"}:
            raise ValueError("interpretation snapshot has unsupported or missing keys")
        if snapshot["schema_version"] != INTERPRETATION_SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(
                "unsupported interpretation snapshot schema version: "
                f"{snapshot['schema_version']!r}"
            )
        _json_safe(snapshot, "interpretation snapshot")
        history_limit = snapshot["history_limit"]
        runtime = cls(history_limit=history_limit)
        sequence = snapshot["sequence"]
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            raise ValueError("interpretation snapshot sequence must be a non-negative integer")
        agents = snapshot["agents"]
        if not isinstance(agents, dict):
            raise ValueError("interpretation snapshot agents must be a dict")

        restored_agents = {}
        seen_history_sequences: set[int] = set()
        for raw_agent, raw_state in agents.items():
            agent = _agent_id(raw_agent, "interpretation snapshot agent")
            if agent in restored_agents:
                raise ValueError(
                    "interpretation snapshot contains duplicate normalized agent: "
                    + agent
                )
            if not isinstance(raw_state, dict):
                raise ValueError(f"interpretation snapshot agent {agent} must be a dict")
            expected = {
                "levels",
                "baseline",
                "thresholds",
                "sensitivities",
                "rules",
                "active",
                "history",
            }
            if set(raw_state) != expected:
                raise ValueError(f"interpretation snapshot agent {agent} has invalid keys")

            levels = _validate_number_map(raw_state["levels"], f"agents.{agent}.levels", _unit)
            baseline = _validate_number_map(raw_state["baseline"], f"agents.{agent}.baseline", _unit)
            thresholds = _validate_thresholds(raw_state["thresholds"])
            sensitivities = _validate_number_map(
                raw_state["sensitivities"],
                f"agents.{agent}.sensitivities",
                _non_negative,
            )
            rules = _validate_rules(raw_state["rules"])
            rule_dimensions = {
                dimension
                for pressures in rules.values()
                for dimension in pressures
            }
            unknown_rule_dimensions = rule_dimensions - set(levels)
            if unknown_rule_dimensions:
                raise ValueError(
                    f"interpretation snapshot agent {agent} rules name unknown "
                    "dimensions: " + ", ".join(sorted(unknown_rule_dimensions))
                )
            active = raw_state["active"]
            if not isinstance(active, dict):
                raise ValueError(f"agents.{agent}.active must be a dict")
            validated_active = {}
            for raw_dimension, raw_value in active.items():
                dimension = _token(raw_dimension, f"agents.{agent}.active dimension")
                if dimension in validated_active:
                    raise ValueError(
                        f"agents.{agent}.active contains duplicate normalized dimension: "
                        + dimension
                    )
                if not isinstance(raw_value, bool):
                    raise ValueError(f"agents.{agent}.active.{dimension} must be bool")
                expected_active = _resolve_active(
                    raw_value,
                    levels[dimension],
                    thresholds[dimension],
                )
                if expected_active != raw_value:
                    raise ValueError(f"agents.{agent}.active.{dimension} is inconsistent with level/threshold")
                validated_active[dimension] = raw_value

            if (
                set(levels) != set(baseline)
                or set(levels) != set(thresholds)
                or set(levels) != set(sensitivities)
                or set(levels) != set(validated_active)
            ):
                raise ValueError(
                    f"interpretation snapshot agent {agent} dimensions do not align"
                )

            history = raw_state["history"]
            if not isinstance(history, list):
                raise ValueError(f"agents.{agent}.history must be a list")
            if len(history) > history_limit:
                raise ValueError(f"agents.{agent}.history exceeds history_limit")
            previous_history_sequence = -1
            expected_history_keys = {
                "sequence",
                "action",
                "source",
                "features",
                "transitions",
                "provenance",
            }
            for index, entry in enumerate(history):
                if not isinstance(entry, dict):
                    raise ValueError(f"agents.{agent}.history[{index}] must be a dict")
                if set(entry) != expected_history_keys:
                    raise ValueError(
                        f"agents.{agent}.history[{index}] has invalid keys"
                    )
                entry_sequence = entry["sequence"]
                if (
                    isinstance(entry_sequence, bool)
                    or not isinstance(entry_sequence, int)
                    or entry_sequence < 1
                    or entry_sequence > sequence
                    or entry_sequence <= previous_history_sequence
                ):
                    raise ValueError(
                        f"agents.{agent}.history[{index}].sequence is invalid"
                    )
                if entry_sequence in seen_history_sequences:
                    raise ValueError(
                        "interpretation snapshot history sequence is duplicated: "
                        f"{entry_sequence}"
                    )
                seen_history_sequences.add(entry_sequence)
                previous_history_sequence = entry_sequence
                _token(entry["action"], f"agents.{agent}.history[{index}].action")
                entry_source = entry["source"]
                if entry_source is not None:
                    _agent_id(
                        entry_source,
                        f"agents.{agent}.history[{index}].source",
                    )
                entry_features = _validate_number_map(
                    entry["features"],
                    f"agents.{agent}.history[{index}].features",
                    _unit,
                )
                action_keys = [
                    feature
                    for feature in entry_features
                    if feature.startswith("action:")
                ]
                if len(action_keys) != 1:
                    raise ValueError(
                        f"agents.{agent}.history[{index}] must contain exactly "
                        "one action: feature"
                    )
                if action_keys[0] != f"action:{entry['action']}":
                    raise ValueError(
                        f"agents.{agent}.history[{index}] action feature mismatch"
                    )
                if entry_features[action_keys[0]] != 1.0:
                    raise ValueError(
                        f"agents.{agent}.history[{index}] action feature must equal 1.0"
                    )
                if not isinstance(entry["transitions"], dict):
                    raise ValueError(
                        f"agents.{agent}.history[{index}].transitions must be a dict"
                    )
                for transition_dimension, transition_packet in entry["transitions"].items():
                    dimension = _token(
                        transition_dimension,
                        f"agents.{agent}.history[{index}] transition dimension",
                    )
                    if dimension not in levels:
                        raise ValueError(
                            f"agents.{agent}.history[{index}] transition names "
                            "an unknown interpretation dimension"
                        )
                    if not isinstance(transition_packet, dict):
                        raise ValueError(
                            f"agents.{agent}.history[{index}].transitions.{dimension} "
                            "must be a dict"
                        )
                    expected_transition_keys = {
                        "level_before",
                        "level_after",
                        "raw_impulse",
                        "effective_impulse",
                        "active_before",
                        "active_after",
                        "transition",
                        "threshold",
                    }
                    if set(transition_packet) != expected_transition_keys:
                        raise ValueError(
                            f"agents.{agent}.history[{index}].transitions.{dimension} "
                            "has invalid keys"
                        )
                    level_before = _unit(
                        transition_packet["level_before"],
                        f"agents.{agent}.history[{index}] level_before",
                    )
                    level_after = _unit(
                        transition_packet["level_after"],
                        f"agents.{agent}.history[{index}] level_after",
                    )
                    raw_impulse = _finite(
                        transition_packet["raw_impulse"],
                        f"agents.{agent}.history[{index}] raw_impulse",
                    )
                    effective_impulse = _signed_unit(
                        transition_packet["effective_impulse"],
                        f"agents.{agent}.history[{index}] effective_impulse",
                    )
                    if not isinstance(transition_packet["active_before"], bool):
                        raise ValueError(
                            f"agents.{agent}.history[{index}] active_before must be bool"
                        )
                    if not isinstance(transition_packet["active_after"], bool):
                        raise ValueError(
                            f"agents.{agent}.history[{index}] active_after must be bool"
                        )
                    if transition_packet["transition"] not in {
                        "entered",
                        "released",
                        "retained_active",
                        "inactive",
                    }:
                        raise ValueError(
                            f"agents.{agent}.history[{index}] transition value is invalid"
                        )
                    history_threshold = _validate_thresholds(
                        {dimension: transition_packet["threshold"]}
                    )[dimension]
                    expected_effective = max(-1.0, min(1.0, raw_impulse))
                    if effective_impulse != expected_effective:
                        raise ValueError(
                            f"agents.{agent}.history[{index}] effective impulse is inconsistent"
                        )
                    if effective_impulse >= 0.0:
                        expected_level_after = (
                            level_before
                            + (1.0 - level_before) * effective_impulse
                        )
                    else:
                        expected_level_after = level_before * (1.0 + effective_impulse)
                    expected_level_after = max(0.0, min(1.0, expected_level_after))
                    if not math.isclose(
                        level_after,
                        expected_level_after,
                        rel_tol=0.0,
                        abs_tol=1e-15,
                    ):
                        raise ValueError(
                            f"agents.{agent}.history[{index}] level transition is inconsistent"
                        )
                    active_before = transition_packet["active_before"]
                    active_after = transition_packet["active_after"]
                    expected_active_after = _resolve_active(
                        active_before,
                        level_after,
                        history_threshold,
                    )
                    if active_after != expected_active_after:
                        raise ValueError(
                            f"agents.{agent}.history[{index}] active transition is inconsistent"
                        )
                    if transition_packet["transition"] != _transition(
                        active_before, active_after
                    ):
                        raise ValueError(
                            f"agents.{agent}.history[{index}] transition label is inconsistent"
                        )
                provenance = entry["provenance"]
                if provenance is not None and not isinstance(provenance, dict):
                    raise ValueError(
                        f"agents.{agent}.history[{index}].provenance must be a dict or None"
                    )
                _json_safe(entry, f"agents.{agent}.history[{index}]")

            restored_agents[agent] = {
                "levels": levels,
                "baseline": baseline,
                "thresholds": thresholds,
                "sensitivities": sensitivities,
                "rules": rules,
                "active": validated_active,
                "history": deepcopy(history),
            }

        if sequence > 0 and (
            not seen_history_sequences or max(seen_history_sequences) != sequence
        ):
            raise ValueError(
                "interpretation snapshot latest history sequence must equal sequence"
            )

        runtime._sequence = sequence
        runtime._agents = restored_agents
        return runtime
