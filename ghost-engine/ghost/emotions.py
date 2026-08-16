"""
Deterministic multi-emotion state for Ghost.

This module intentionally separates four concepts that are easy to blur:

- level: current bounded emotional state in [0, 1]
- impulse: signed event effect in [-1, 1]
- sensitivity: per-agent gain applied to an impulse
- salience: current attention pressure derived from level * salience_bias
- spotlight: stateful dominant attention using a deterministic switch margin

No random numbers are used. Default event impulse profiles are explicit starter
semantics, not claims about human psychology. Applications may configure them.

Relationship state remains separate. A character can be friendly while angry,
or hostile while afraid. Ghost exposes both layers; a host game, agent, or LLM
still owns the final action and presentation.
"""

from copy import deepcopy

from .ids import normalize_id
from .validation import (
    validate_finite_number,
    validate_non_negative_finite,
    validate_unit_interval,
)


EMOTION_SNAPSHOT_SCHEMA_VERSION = "1.1"
EMOTION_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS = ("1.0", "1.1")
DEFAULT_SPOTLIGHT_SWITCH_MARGIN = 0.05
_SPOTLIGHT_EPSILON = 1e-12
DEFAULT_EMOTIONS = (
    "anger",
    "fear",
    "grief",
    "hope",
    "joy",
)
DEFAULT_GENERIC_INERTIA = 0.85
DEFAULT_INERTIA = {
    "anger": 0.82,
    "fear": 0.78,
    "grief": 0.93,
    "hope": 0.88,
    "joy": 0.72,
}
DEFAULT_EVENT_IMPULSES = {
    "neutral": {},
    "greet": {
        "anger": -0.05,
        "fear": -0.05,
        "hope": 0.08,
        "joy": 0.10,
    },
    "help": {
        "anger": -0.10,
        "fear": -0.15,
        "grief": -0.05,
        "hope": 0.35,
        "joy": 0.25,
    },
    "cooperate": {
        "anger": -0.05,
        "fear": -0.08,
        "hope": 0.20,
        "joy": 0.15,
    },
    "gift": {
        "anger": -0.08,
        "fear": -0.08,
        "grief": -0.05,
        "hope": 0.25,
        "joy": 0.40,
    },
    "apology": {
        "anger": -0.25,
        "fear": -0.05,
        "grief": -0.10,
        "hope": 0.20,
        "joy": 0.05,
    },
    "apologize": {
        "anger": -0.25,
        "fear": -0.05,
        "grief": -0.10,
        "hope": 0.20,
        "joy": 0.05,
    },
    "disengage": {
        "anger": -0.05,
        "fear": -0.05,
        "grief": 0.08,
    },
    "pressure": {
        "anger": 0.15,
        "fear": 0.25,
        "hope": -0.10,
        "joy": -0.08,
    },
    "manipulate": {
        "anger": 0.20,
        "fear": 0.10,
        "grief": 0.08,
        "hope": -0.15,
    },
    "deceive": {
        "anger": 0.30,
        "fear": 0.10,
        "grief": 0.15,
        "hope": -0.25,
        "joy": -0.10,
    },
    "insult": {
        "anger": 0.35,
        "fear": 0.08,
        "grief": 0.12,
        "hope": -0.08,
        "joy": -0.15,
    },
    "threat": {
        "anger": 0.25,
        "fear": 0.65,
        "grief": 0.10,
        "hope": -0.15,
        "joy": -0.20,
    },
    "theft": {
        "anger": 0.55,
        "fear": 0.30,
        "grief": 0.30,
        "hope": -0.20,
        "joy": -0.25,
    },
    "attack": {
        "anger": 0.55,
        "fear": 0.70,
        "grief": 0.35,
        "hope": -0.30,
        "joy": -0.35,
    },
    "betrayal": {
        "anger": 0.75,
        "fear": 0.20,
        "grief": 0.65,
        "hope": -0.55,
        "joy": -0.60,
    },
}

_EVENT_ALIASES = {
    "betray": "betrayal",
    "steal": "theft",
}

_AGENT_KEYS_V1_0 = {
    "baseline",
    "history",
    "inertia",
    "levels",
    "salience_bias",
    "sensitivities",
}
_AGENT_KEYS = _AGENT_KEYS_V1_0 | {
    "spotlight_emotion",
    "spotlight_switch_margin",
}
_SNAPSHOT_KEYS = {
    "agents",
    "customized_profiles",
    "event_profiles",
    "history_limit",
    "schema_version",
    "sequence",
}


def _clamp01(value):
    return max(0.0, min(1.0, float(value)))


def _normalize_emotion(value):
    return normalize_id(value, "emotion name").lower()


def _normalize_event(value):
    name = normalize_id(value, "emotional event").lower()
    return _EVENT_ALIASES.get(name, name)


def _validate_signed_unit(value, label):
    number = validate_finite_number(value, label)
    if not -1.0 <= number <= 1.0:
        raise ValueError(f"{label} must be between -1.0 and 1.0")
    return number


def _validate_steps(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("emotion tick steps must be a positive integer")
    return value


def _validate_history_limit(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("emotion history_limit must be a positive integer")
    return value


def _json_safe(value, label="value"):
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        validate_finite_number(value, label)
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


def _validated_unit_map(value, label):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a dict or None")
    out = {}
    for raw_name, raw_value in value.items():
        name = _normalize_emotion(raw_name)
        out[name] = validate_unit_interval(raw_value, f"{label} {name}")
    return out


def _validated_non_negative_map(value, label):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a dict or None")
    out = {}
    for raw_name, raw_value in value.items():
        name = _normalize_emotion(raw_name)
        out[name] = validate_non_negative_finite(raw_value, f"{label} {name}")
    return out


def _validated_impulses(value, label="emotion impulses"):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a dict")
    out = {}
    for raw_name, raw_value in value.items():
        name = _normalize_emotion(raw_name)
        out[name] = _validate_signed_unit(raw_value, f"{label} {name}")
    return out


class EmotionRuntime:
    """Persistent, deterministic, independently bounded emotional channels."""

    def __init__(self, history_limit=64):
        self.history_limit = _validate_history_limit(history_limit)
        self._agents = {}
        self._sequence = 0
        self._event_profiles = {
            name: _validated_impulses(profile, f"default event profile {name}")
            for name, profile in DEFAULT_EVENT_IMPULSES.items()
        }
        self._customized_profiles = set()

    def has_state(self):
        return bool(self._agents or self._customized_profiles)

    def event_profiles(self):
        return deepcopy(self._event_profiles)

    def get_event_profile(self, event):
        event_name = _normalize_event(event)
        profile = self._event_profiles.get(event_name)
        return deepcopy(profile) if profile is not None else None

    def configure_event_profile(self, event, impulses):
        event_name = _normalize_event(event)
        validated = _validated_impulses(impulses, f"event profile {event_name}")
        self._event_profiles[event_name] = validated
        self._customized_profiles.add(event_name)
        return {
            "event": event_name,
            "impulses": deepcopy(validated),
        }

    def _default_inertia(self, emotion):
        return DEFAULT_INERTIA.get(emotion, DEFAULT_GENERIC_INERTIA)

    def _all_emotions(self, *maps):
        names = set(DEFAULT_EMOTIONS)
        for mapping in maps:
            if mapping:
                names.update(mapping)
        return sorted(names)

    def register_agent(
        self,
        agent,
        initial=None,
        baseline=None,
        sensitivities=None,
        inertia=None,
        salience_bias=None,
        spotlight_switch_margin=None,
    ):
        agent_id = normalize_id(agent, "emotional agent id")
        initial = _validated_unit_map(initial, "initial emotion level")
        baseline = _validated_unit_map(baseline, "emotion baseline")
        sensitivities = _validated_non_negative_map(
            sensitivities,
            "emotion sensitivity",
        )
        inertia = _validated_unit_map(inertia, "emotion inertia")
        salience_bias = _validated_non_negative_map(
            salience_bias,
            "emotion salience bias",
        )
        if spotlight_switch_margin is not None:
            spotlight_switch_margin = validate_unit_interval(
                spotlight_switch_margin,
                "emotion spotlight switch margin",
            )

        existing = self._agents.get(agent_id)
        if existing is None:
            names = self._all_emotions(
                initial,
                baseline,
                sensitivities,
                inertia,
                salience_bias,
            )
            state = {
                "levels": {name: 0.0 for name in names},
                "baseline": {name: 0.0 for name in names},
                "sensitivities": {name: 1.0 for name in names},
                "inertia": {
                    name: self._default_inertia(name)
                    for name in names
                },
                "salience_bias": {name: 1.0 for name in names},
                "spotlight_emotion": None,
                "spotlight_switch_margin": (
                    DEFAULT_SPOTLIGHT_SWITCH_MARGIN
                    if spotlight_switch_margin is None
                    else spotlight_switch_margin
                ),
                "history": [],
            }
            self._agents[agent_id] = state
        else:
            state = existing
            names = self._all_emotions(
                state["levels"],
                initial,
                baseline,
                sensitivities,
                inertia,
                salience_bias,
            )
            self._ensure_channels(state, names)

        state["levels"].update(initial)
        state["baseline"].update(baseline)
        state["sensitivities"].update(sensitivities)
        state["inertia"].update(inertia)
        state["salience_bias"].update(salience_bias)
        if spotlight_switch_margin is not None:
            state["spotlight_switch_margin"] = spotlight_switch_margin
        self._resolve_spotlight(state)
        return self.get_state(agent_id)

    def _ensure_channels(self, state, names):
        for name in sorted(set(names)):
            state["levels"].setdefault(name, 0.0)
            state["baseline"].setdefault(name, 0.0)
            state["sensitivities"].setdefault(name, 1.0)
            state["inertia"].setdefault(name, self._default_inertia(name))
            state["salience_bias"].setdefault(name, 1.0)

    def _ensure_agent(self, agent):
        agent_id = normalize_id(agent, "emotional agent id")
        if agent_id not in self._agents:
            self.register_agent(agent_id)
        return agent_id, self._agents[agent_id]

    def _salience_rows(self, state):
        rows = []
        for name in sorted(state["levels"]):
            level = state["levels"][name]
            bias = state["salience_bias"].get(name, 1.0)
            rows.append((name, _clamp01(level * bias)))
        return sorted(rows, key=lambda item: (-item[1], item[0]))

    def _resolve_spotlight(self, state):
        rows = self._salience_rows(state)
        by_name = dict(rows)
        raw_leader = None
        raw_leader_salience = 0.0
        if rows and rows[0][1] > 0.0:
            raw_leader = rows[0][0]
            raw_leader_salience = rows[0][1]

        previous = state.get("spotlight_emotion")
        margin = state.get(
            "spotlight_switch_margin",
            DEFAULT_SPOTLIGHT_SWITCH_MARGIN,
        )
        reason = "leader_holds"

        if raw_leader is None:
            resolved = None
            reason = "zero_vector"
        elif previous is None or previous not in by_name:
            resolved = raw_leader
            reason = "acquired"
        else:
            previous_salience = by_name.get(previous, 0.0)
            if previous_salience <= 0.0:
                resolved = raw_leader
                reason = "incumbent_inactive"
            elif raw_leader == previous:
                resolved = previous
                reason = "leader_holds"
            else:
                advantage = raw_leader_salience - previous_salience
                if advantage + _SPOTLIGHT_EPSILON >= margin:
                    resolved = raw_leader
                    reason = "margin_crossed"
                else:
                    resolved = previous
                    reason = "hysteresis_retained"

        state["spotlight_emotion"] = resolved
        return {
            "previous_spotlight": previous,
            "resolved_spotlight": resolved,
            "spotlight_changed": resolved != previous,
            "switch_reason": reason,
            "raw_leader_emotion": raw_leader,
            "raw_leader_salience": raw_leader_salience,
            "spotlight_switch_margin": margin,
        }

    def _salience_packet(self, state):
        rows = self._salience_rows(state)
        total = sum(value for _, value in rows)
        dominant = state.get("spotlight_emotion")
        by_name = dict(rows)
        dominant_salience = by_name.get(dominant, 0.0) if dominant else 0.0
        raw_leader = None
        raw_leader_salience = 0.0
        if rows and rows[0][1] > 0.0:
            raw_leader = rows[0][0]
            raw_leader_salience = rows[0][1]

        spotlight = [
            {
                "emotion": name,
                "salience": value,
                "share": (value / total if total > 0.0 else 0.0),
                "active": name == dominant,
            }
            for name, value in rows
        ]

        return {
            "dominant_emotion": dominant,
            "dominant_salience": dominant_salience,
            "raw_leader_emotion": raw_leader,
            "raw_leader_salience": raw_leader_salience,
            "spotlight_switch_margin": state.get(
                "spotlight_switch_margin",
                DEFAULT_SPOTLIGHT_SWITCH_MARGIN,
            ),
            "spotlight": spotlight,
        }

    def get_state(self, agent):
        agent_id = normalize_id(agent, "emotional agent id")
        state = self._agents.get(agent_id)
        if state is None:
            return None
        salience = self._salience_packet(state)
        return {
            "agent": agent_id,
            "levels": deepcopy(state["levels"]),
            "baseline": deepcopy(state["baseline"]),
            "sensitivities": deepcopy(state["sensitivities"]),
            "inertia": deepcopy(state["inertia"]),
            "salience_bias": deepcopy(state["salience_bias"]),
            "dominant_emotion": salience["dominant_emotion"],
            "dominant_salience": salience["dominant_salience"],
            "raw_leader_emotion": salience["raw_leader_emotion"],
            "raw_leader_salience": salience["raw_leader_salience"],
            "spotlight_switch_margin": salience["spotlight_switch_margin"],
            "spotlight": deepcopy(salience["spotlight"]),
            "history": deepcopy(state["history"]),
        }

    def apply_event(
        self,
        agent,
        event,
        intensity=1.0,
        source=None,
        context_modifiers=None,
        impulse_overrides=None,
    ):
        event_name = _normalize_event(event)
        intensity = validate_unit_interval(intensity, "emotional event intensity")
        if source is not None:
            source = normalize_id(source, "emotional event source")

        base_profile = self._event_profiles.get(event_name)
        if base_profile is None and impulse_overrides is None:
            raise ValueError(f"Unknown emotional event profile: {event_name}")

        profile = deepcopy(base_profile or {})
        if impulse_overrides is not None:
            profile.update(
                _validated_impulses(
                    impulse_overrides,
                    f"emotional event override {event_name}",
                )
            )

        context = _validated_non_negative_map(
            context_modifiers,
            "emotion context modifier",
        )
        agent_id, state = self._ensure_agent(agent)
        names = self._all_emotions(state["levels"], profile, context)
        self._ensure_channels(state, names)

        before = deepcopy(state["levels"])
        previous_spotlight = state.get("spotlight_emotion")
        deltas = {}
        effective_impulses = {}
        applied_profile = {}

        for name in names:
            base_impulse = profile.get(name, 0.0)
            sensitivity = state["sensitivities"].get(name, 1.0)
            context_multiplier = context.get(name, 1.0)
            effective = base_impulse * intensity * sensitivity * context_multiplier
            old = state["levels"][name]

            if effective >= 0.0:
                delta = effective * (1.0 - old)
            else:
                delta = effective * old

            new_value = _clamp01(old + delta)
            state["levels"][name] = new_value
            deltas[name] = new_value - old
            effective_impulses[name] = effective
            applied_profile[name] = base_impulse

        self._sequence += 1
        after = deepcopy(state["levels"])
        resolution = self._resolve_spotlight(state)
        salience = self._salience_packet(state)
        record = {
            "sequence": self._sequence,
            "source": source,
            "event": event_name,
            "intensity": intensity,
            "profile": deepcopy(applied_profile),
            "effective_impulses": deepcopy(effective_impulses),
            "deltas": deepcopy(deltas),
            "before": before,
            "after": after,
            "previous_spotlight": previous_spotlight,
            "dominant_emotion": salience["dominant_emotion"],
            "dominant_salience": salience["dominant_salience"],
            "raw_leader_emotion": salience["raw_leader_emotion"],
            "raw_leader_salience": salience["raw_leader_salience"],
            "spotlight_changed": resolution["spotlight_changed"],
            "spotlight_switch_margin": salience["spotlight_switch_margin"],
            "spotlight_switch_reason": resolution["switch_reason"],
        }
        state["history"].append(record)
        if len(state["history"]) > self.history_limit:
            del state["history"][:-self.history_limit]

        return {
            "agent": agent_id,
            "source": source,
            "event": event_name,
            "intensity": intensity,
            "base_impulses": deepcopy(applied_profile),
            "effective_impulses": deepcopy(effective_impulses),
            "deltas": deepcopy(deltas),
            "before": before,
            "after": after,
            "spotlight_transition": deepcopy(resolution),
            "state": self.get_state(agent_id),
        }

    def tick(self, agent=None, steps=1):
        steps = _validate_steps(steps)
        if agent is None:
            agent_ids = sorted(self._agents)
        else:
            agent_id = normalize_id(agent, "emotional agent id")
            if agent_id not in self._agents:
                return {
                    "event": "emotion_tick",
                    "steps": steps,
                    "agents": [],
                }
            agent_ids = [agent_id]

        packets = []
        for agent_id in agent_ids:
            state = self._agents[agent_id]
            before = deepcopy(state["levels"])
            previous_spotlight = state.get("spotlight_emotion")
            for name in sorted(state["levels"]):
                baseline = state["baseline"].get(name, 0.0)
                inertia = state["inertia"].get(
                    name,
                    self._default_inertia(name),
                )
                state["levels"][name] = _clamp01(
                    baseline
                    + (state["levels"][name] - baseline)
                    * (inertia ** steps)
                )
            resolution = self._resolve_spotlight(state)
            packets.append(
                {
                    "agent": agent_id,
                    "before": before,
                    "after": deepcopy(state["levels"]),
                    "previous_spotlight": previous_spotlight,
                    "spotlight_transition": deepcopy(resolution),
                    "state": self.get_state(agent_id),
                }
            )

        return {
            "event": "emotion_tick",
            "steps": steps,
            "agents": packets,
        }

    def snapshot(self):
        return {
            "schema_version": EMOTION_SNAPSHOT_SCHEMA_VERSION,
            "history_limit": self.history_limit,
            "sequence": self._sequence,
            "event_profiles": deepcopy(self._event_profiles),
            "customized_profiles": sorted(self._customized_profiles),
            "agents": deepcopy(self._agents),
        }

    @classmethod
    def from_snapshot(cls, snapshot):
        if not isinstance(snapshot, dict):
            raise ValueError("emotion snapshot must be a dict")
        unknown = set(snapshot) - _SNAPSHOT_KEYS
        missing = _SNAPSHOT_KEYS - set(snapshot)
        if unknown:
            raise ValueError(
                "emotion snapshot has unsupported keys: "
                + ", ".join(sorted(unknown))
            )
        if missing:
            raise ValueError(
                "emotion snapshot is missing required keys: "
                + ", ".join(sorted(missing))
            )
        _json_safe(snapshot, "emotion snapshot")
        schema_version = snapshot["schema_version"]
        if schema_version not in EMOTION_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS:
            raise ValueError(
                "unsupported emotion snapshot schema version: "
                + repr(schema_version)
            )

        history_limit = _validate_history_limit(snapshot["history_limit"])
        sequence = snapshot["sequence"]
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            raise ValueError("emotion snapshot sequence must be a non-negative integer")

        profiles_raw = snapshot["event_profiles"]
        if not isinstance(profiles_raw, dict):
            raise ValueError("emotion snapshot event_profiles must be a dict")
        profiles = {}
        for raw_event, raw_profile in profiles_raw.items():
            event_name = _normalize_event(raw_event)
            profiles[event_name] = _validated_impulses(
                raw_profile,
                f"emotion snapshot event profile {event_name}",
            )

        customized_raw = snapshot["customized_profiles"]
        if not isinstance(customized_raw, list):
            raise ValueError("emotion snapshot customized_profiles must be a list")
        customized = set()
        for raw_event in customized_raw:
            event_name = _normalize_event(raw_event)
            if event_name not in profiles:
                raise ValueError(
                    "emotion snapshot customized profile is missing from event_profiles: "
                    + event_name
                )
            customized.add(event_name)

        agents_raw = snapshot["agents"]
        if not isinstance(agents_raw, dict):
            raise ValueError("emotion snapshot agents must be a dict")
        agents = {}
        for raw_agent, raw_state in agents_raw.items():
            agent_id = normalize_id(raw_agent, "emotion snapshot agent id")
            if not isinstance(raw_state, dict):
                raise ValueError(f"emotion snapshot agent {agent_id} must be a dict")
            expected_agent_keys = (
                _AGENT_KEYS_V1_0
                if schema_version == "1.0"
                else _AGENT_KEYS
            )
            if set(raw_state) != expected_agent_keys:
                raise ValueError(
                    f"emotion snapshot agent {agent_id} has invalid keys"
                )
            levels = _validated_unit_map(raw_state["levels"], "emotion snapshot level")
            baseline = _validated_unit_map(raw_state["baseline"], "emotion snapshot baseline")
            sensitivities = _validated_non_negative_map(
                raw_state["sensitivities"],
                "emotion snapshot sensitivity",
            )
            inertia = _validated_unit_map(raw_state["inertia"], "emotion snapshot inertia")
            salience_bias = _validated_non_negative_map(
                raw_state["salience_bias"],
                "emotion snapshot salience bias",
            )
            names = set(levels)
            if not (
                names == set(baseline)
                == set(sensitivities)
                == set(inertia)
                == set(salience_bias)
            ):
                raise ValueError(
                    f"emotion snapshot agent {agent_id} channel sets must match"
                )
            history = raw_state["history"]
            if not isinstance(history, list):
                raise ValueError(f"emotion snapshot agent {agent_id} history must be a list")
            if len(history) > history_limit:
                raise ValueError(
                    f"emotion snapshot agent {agent_id} history exceeds history_limit"
                )
            for index, record in enumerate(history):
                if not isinstance(record, dict):
                    raise ValueError(
                        f"emotion snapshot agent {agent_id} history[{index}] must be a dict"
                    )
                _json_safe(
                    record,
                    f"emotion snapshot agent {agent_id} history[{index}]",
                )
            if schema_version == "1.0":
                spotlight_emotion = None
                spotlight_switch_margin = DEFAULT_SPOTLIGHT_SWITCH_MARGIN
            else:
                raw_spotlight = raw_state["spotlight_emotion"]
                if raw_spotlight is None:
                    spotlight_emotion = None
                else:
                    spotlight_emotion = _normalize_emotion(raw_spotlight)
                    if spotlight_emotion not in names:
                        raise ValueError(
                            f"emotion snapshot agent {agent_id} spotlight emotion "
                            "must name an existing channel"
                        )
                spotlight_switch_margin = validate_unit_interval(
                    raw_state["spotlight_switch_margin"],
                    f"emotion snapshot agent {agent_id} spotlight switch margin",
                )

            agents[agent_id] = {
                "levels": levels,
                "baseline": baseline,
                "sensitivities": sensitivities,
                "inertia": inertia,
                "salience_bias": salience_bias,
                "spotlight_emotion": spotlight_emotion,
                "spotlight_switch_margin": spotlight_switch_margin,
                "history": deepcopy(history),
            }

        runtime = cls(history_limit=history_limit)
        runtime._event_profiles = profiles
        runtime._customized_profiles = customized
        runtime._agents = agents
        runtime._sequence = sequence
        if schema_version == "1.0":
            for state in runtime._agents.values():
                runtime._resolve_spotlight(state)
        return runtime
