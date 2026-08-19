import copy
import math
from dataclasses import asdict
from ghost.step import GhostStep
from ghost.agents import AgentRegistry
from ghost.relationships import RelationshipGraph
from ghost.events import normalize_event
from ghost.validation import (
    validate_non_negative_finite,
    validate_unit_interval,
)
from ghost.ids import normalize_id

# Package/release metadata. GHOST_VERSION remains as the public
# compatibility name used by existing integrations.
GHOST_PACKAGE_VERSION = "1.10.0"
GHOST_VERSION = GHOST_PACKAGE_VERSION

# Persisted-format metadata. This changes only when the snapshot
# contract changes, not whenever the package is released.
GHOST_SNAPSHOT_SCHEMA_VERSION = "1.0"
GHOST_LEGACY_SNAPSHOT_SCHEMA_VERSIONS = frozenset(
    {
        "1.7.5",
    }
)
GHOST_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS = (
    frozenset(
        {
            GHOST_SNAPSHOT_SCHEMA_VERSION,
        }
    )
    | GHOST_LEGACY_SNAPSHOT_SCHEMA_VERSIONS
)

def _json_safe(x):

    if isinstance(x, dict):
        return {str(k): _json_safe(v) for k, v in x.items()}

    if isinstance(x, list):
        return [_json_safe(v) for v in x]

    if isinstance(x, tuple):
        return [_json_safe(v) for v in x]

    if isinstance(x, set):
        return sorted(
            (_json_safe(v) for v in x),
            key=lambda value: repr(value),
        )

    if isinstance(x, float) and not math.isfinite(x):
        raise ValueError("Snapshot contains non-finite float")

    return x

def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


_ENGINE_SNAPSHOT_REQUIRED_KEYS = {
    "agents",
    "cycles",
    "ghost_version",
    "input",
    "last_step",
    "neighbors",
    "npc",
    "relationships",
    "schema_version",
    "social_propagation",
}


_ENGINE_RELATIONSHIP_NUMERIC_KEYS = {
    "attachment",
    "betrayal_shock_maturity_threshold",
    "betrayal_shock_positive_threshold",
    "betrayal_stability_breach_fraction",
    "high_severity_shock_bonus",
    "high_severity_threshold",
    "maturity",
    "maturity_cap",
    "maturity_gain",
    "neg",
    "neg_decay",
    "neg_gain",
    "negative_volatility",
    "pos",
    "pos_decay",
    "pos_gain",
    "positive_reservoir_cap",
    "positive_volatility",
    "recent_event_decay",
    "recent_event_magnitude",
    "relative_shock_bonus",
    "relative_shock_ratio",
    "severe_negative_maturity_floor",
    "stability_shock_maturity_threshold",
    "stability_shock_positive_threshold",
    "trust",
    "volatility",
}


_ENGINE_RELATIONSHIP_NON_NEGATIVE_KEYS = {
    "pos",
    "neg",
    "maturity",
    "maturity_cap",
    "maturity_gain",
    "volatility",
    "positive_volatility",
    "negative_volatility",
    "recent_event_magnitude",
    "positive_reservoir_cap",
}


def _engine_snapshot_json_value(
    value,
    label: str,
):
    if value is None:
        return

    if isinstance(
        value,
        (
            str,
            bool,
            int,
        ),
    ):
        return

    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(
                f"{label} must contain only finite numbers"
            )

        return

    if isinstance(value, list):
        for index, item in enumerate(value):
            _engine_snapshot_json_value(
                item,
                f"{label}[{index}]",
            )

        return

    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(
                    f"{label} keys must be strings"
                )

            _engine_snapshot_json_value(
                item,
                f"{label}.{key}",
            )

        return

    raise ValueError(
        f"{label} must be JSON-safe"
    )


def _engine_snapshot_text(
    value,
    label: str,
) -> str:
    if not isinstance(value, str):
        raise ValueError(
            f"{label} must be a string"
        )

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{label} cannot be empty"
        )

    return normalized


def _engine_snapshot_number(
    value,
    label: str,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(
            value,
            (
                int,
                float,
            ),
        )
    ):
        raise ValueError(
            f"{label} must be a finite number"
        )

    number = float(value)

    if not math.isfinite(number):
        raise ValueError(
            f"{label} must be a finite number"
        )

    return number


def _engine_snapshot_non_negative_int(
    value,
    label: str,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
    ):
        raise ValueError(
            f"{label} must be a non-negative integer"
        )

    return value


def _validate_engine_relationship(
    pair_key: str,
    relationship,
):
    if not isinstance(relationship, dict):
        raise ValueError(
            "engine snapshot relationship "
            f"{pair_key!r} must be a dict"
        )

    _engine_snapshot_json_value(
        relationship,
        (
            "engine snapshot relationship "
            f"{pair_key!r}"
        ),
    )

    for key in _ENGINE_RELATIONSHIP_NUMERIC_KEYS:
        if key not in relationship:
            continue

        value = _engine_snapshot_number(
            relationship[key],
            (
                "engine snapshot relationship "
                f"{pair_key!r} field {key}"
            ),
        )

        if (
            key
            in _ENGINE_RELATIONSHIP_NON_NEGATIVE_KEYS
            and value < 0.0
        ):
            raise ValueError(
                "engine snapshot relationship "
                f"{pair_key!r} field {key} "
                "cannot be negative"
            )

    if all(
        key in relationship
        for key in (
            "pos",
            "neg",
            "trust",
        )
    ):
        expected_trust = (
            float(relationship["pos"])
            - float(relationship["neg"])
        )

        actual_trust = float(
            relationship["trust"]
        )

        if not math.isclose(
            actual_trust,
            expected_trust,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError(
                "engine snapshot relationship "
                f"{pair_key!r} trust must equal pos - neg"
            )

    state = relationship.get("state")

    if state is not None:
        _engine_snapshot_text(
            state,
            (
                "engine snapshot relationship "
                f"{pair_key!r} state"
            ),
        )

    last_event = relationship.get(
        "last_event"
    )

    if last_event is not None:
        _engine_snapshot_text(
            last_event,
            (
                "engine snapshot relationship "
                f"{pair_key!r} last_event"
            ),
        )

    diagnostics = relationship.get(
        "diagnostics"
    )

    if (
        diagnostics is not None
        and not isinstance(
            diagnostics,
            dict,
        )
    ):
        raise ValueError(
            "engine snapshot relationship "
            f"{pair_key!r} diagnostics "
            "must be a dict or None"
        )

    transition = relationship.get(
        "transition"
    )

    if transition is not None:
        if (
            not isinstance(
                transition,
                (
                    list,
                    tuple,
                ),
            )
            or len(transition) != 2
            or not all(
                isinstance(item, str)
                and item.strip()
                for item in transition
            )
        ):
            raise ValueError(
                "engine snapshot relationship "
                f"{pair_key!r} transition "
                "must contain two state strings"
            )

    trigger = relationship.get(
        "trigger"
    )

    if (
        trigger is not None
        and not isinstance(trigger, dict)
    ):
        raise ValueError(
            "engine snapshot relationship "
            f"{pair_key!r} trigger "
            "must be a dict or None"
        )


def _validate_engine_snapshot(
    snapshot,
) -> dict:
    if not isinstance(snapshot, dict):
        raise ValueError(
            "engine snapshot must be a dict"
        )

    missing = (
        _ENGINE_SNAPSHOT_REQUIRED_KEYS
        - set(snapshot)
    )

    if missing:
        raise ValueError(
            "engine snapshot is missing required keys: "
            + ", ".join(sorted(missing))
        )

    _engine_snapshot_json_value(
        snapshot,
        "engine snapshot",
    )

    schema_version = _engine_snapshot_text(
        snapshot["schema_version"],
        "engine snapshot schema version",
    )

    if (
        schema_version
        not in GHOST_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS
    ):
        raise ValueError(
            "unsupported engine snapshot schema version: "
            f"{schema_version!r}"
        )

    _engine_snapshot_text(
        snapshot["ghost_version"],
        "engine snapshot ghost version",
    )

    _engine_snapshot_non_negative_int(
        snapshot["cycles"],
        "engine snapshot cycles",
    )

    agents = snapshot["agents"]

    if not isinstance(agents, dict):
        raise ValueError(
            "engine snapshot agents must be a dict"
        )

    npc = snapshot["npc"]

    if not isinstance(npc, dict):
        raise ValueError(
            "engine snapshot npc must be a dict"
        )

    if "threat_level" not in npc:
        raise ValueError(
            "engine snapshot npc is missing threat_level"
        )

    threat_level = _engine_snapshot_number(
        npc["threat_level"],
        "engine snapshot npc threat_level",
    )

    if threat_level < 0.0:
        raise ValueError(
            "engine snapshot npc threat_level "
            "cannot be negative"
        )

    if "last_intent" not in npc:
        raise ValueError(
            "engine snapshot npc is missing last_intent"
        )

    relationships = snapshot[
        "relationships"
    ]

    if not isinstance(
        relationships,
        dict,
    ):
        raise ValueError(
            "engine snapshot relationships must be a dict"
        )

    relationship_pairs = set()

    for pair_key, relationship in (
        relationships.items()
    ):
        if not isinstance(pair_key, str):
            raise ValueError(
                "engine snapshot relationship keys "
                "must be strings"
            )

        parts = pair_key.split("|")

        if (
            len(parts) != 2
            or not parts[0]
            or not parts[1]
            or parts[0] == parts[1]
        ):
            raise ValueError(
                "engine snapshot relationship key "
                f"{pair_key!r} is invalid"
            )

        actor_a, actor_b = parts

        canonical = tuple(
            sorted(
                (
                    actor_a,
                    actor_b,
                )
            )
        )

        if canonical in relationship_pairs:
            raise ValueError(
                "engine snapshot contains a duplicate "
                "relationship pair"
            )

        relationship_pairs.add(
            canonical
        )

        _validate_engine_relationship(
            pair_key,
            relationship,
        )

    neighbors = snapshot["neighbors"]

    if not isinstance(neighbors, dict):
        raise ValueError(
            "engine snapshot neighbors must be a dict"
        )

    normalized_neighbors = {}

    for actor, actor_neighbors in (
        neighbors.items()
    ):
        actor = _engine_snapshot_text(
            actor,
            "engine snapshot neighbor actor",
        )

        if not isinstance(
            actor_neighbors,
            list,
        ):
            raise ValueError(
                "engine snapshot neighbor lists "
                "must be lists"
            )

        normalized = []

        for neighbor in actor_neighbors:
            neighbor = _engine_snapshot_text(
                neighbor,
                (
                    "engine snapshot neighbor "
                    f"for {actor}"
                ),
            )

            if neighbor == actor:
                raise ValueError(
                    "engine snapshot actor cannot "
                    "neighbor itself"
                )

            if neighbor in normalized:
                raise ValueError(
                    "engine snapshot neighbor list "
                    f"for {actor!r} contains duplicates"
                )

            normalized.append(
                neighbor
            )

        normalized_neighbors[actor] = (
            normalized
        )

    for actor, actor_neighbors in (
        normalized_neighbors.items()
    ):
        for neighbor in actor_neighbors:
            reverse = normalized_neighbors.get(
                neighbor,
                [],
            )

            if actor not in reverse:
                raise ValueError(
                    "engine snapshot neighbor graph "
                    "must be symmetric"
                )

    for actor_a, actor_b in relationship_pairs:
        if (
            actor_b
            not in normalized_neighbors.get(
                actor_a,
                [],
            )
            or actor_a
            not in normalized_neighbors.get(
                actor_b,
                [],
            )
        ):
            raise ValueError(
                "engine snapshot relationship pairs "
                "must exist in the neighbor graph"
            )

    propagation = snapshot[
        "social_propagation"
    ]

    if not isinstance(
        propagation,
        list,
    ):
        raise ValueError(
            "engine snapshot social_propagation "
            "must be a list"
        )

    if len(propagation) > 25:
        raise ValueError(
            "engine snapshot social_propagation "
            "cannot contain more than 25 packets"
        )

    if not all(
        isinstance(packet, dict)
        for packet in propagation
    ):
        raise ValueError(
            "engine snapshot social_propagation "
            "must contain only dict packets"
        )

    validated = copy.deepcopy(
        snapshot
    )

    # The restored runtime is now owned by the installed package.
    # Preserve compatibility through the schema version, then emit
    # current producer metadata on its next snapshot.
    validated["ghost_version"] = GHOST_VERSION
    validated["schema_version"] = (
        GHOST_SNAPSHOT_SCHEMA_VERSION
    )

    return validated


class GhostEngine:
    """
    Core Ghost engine.

    - Public API: dict-based, serialization-safe
    - Internal logic may use typed objects (GhostStep)
    - All state mutation occurs via step()
    """

    def __init__(
        self,
        context: dict | None = None,
    ):
        """
        Construct a fresh engine from optional runtime configuration.

        Snapshot restoration is intentionally separate and must use
        GhostEngine.from_snapshot().
        """
        if context is None:
            context = {}

        self._initialize_context(
            context
        )

    @classmethod
    def from_snapshot(
        cls,
        snapshot: dict,
    ) -> "GhostEngine":
        """
        Restore a GhostEngine only after validating the complete
        persisted engine contract.

        Restoration bypasses __init__ so construction configuration and
        persisted runtime state remain separate public boundaries.
        """
        validated = _validate_engine_snapshot(
            snapshot
        )

        engine = cls.__new__(
            cls
        )

        engine._initialize_context(
            validated
        )

        return engine

    def _initialize_context(
        self,
        context: dict,
    ) -> None:
        """
        Bind copied context state and initialize engine subsystems.

        Public callers enter through __init__() for construction or
        from_snapshot() for restoration.
        """
        self._ctx = copy.deepcopy(
            context
        )

        self.agents = AgentRegistry(
            self._ctx
        )

        self.relationships = (
            RelationshipGraph(
                self._ctx
            )
        )

        self._ctx.setdefault(
            "cycles",
            0,
        )

        self._ctx.setdefault(
            "input",
            None,
        )

        self._ctx.setdefault(
            "last_step",
            None,
        )

        npc = self._ctx.setdefault(
            "npc",
            {},
        )

        npc.setdefault(
            "threat_level",
            0.0,
        )

        npc.setdefault(
            "last_intent",
            None,
        )

    def step(self, step_data=None):
        """
        Advance the Ghost engine by one cycle.

        Accepts:
        - dict (public / legacy input)
        - GhostStep (internal / typed input)

        Internal types MUST NOT leak into public state.
        """

        ctx = self._ctx
        npc = ctx["npc"]
        
        # passive decay (only if no threat this step)
        if step_data is None:
            ctx["cycles"] += 1
            npc["threat_level"] = clamp(npc["threat_level"] - 0.02, 0.0, 999999.0)

        step: GhostStep | None = None
        public_input: dict | None = None
        
        

        # ---- Normalize input at boundary ----
        if step_data is not None:
            if isinstance(step_data, dict):
                step = GhostStep(**step_data)
                public_input = dict(step_data)

            elif isinstance(step_data, GhostStep):
                step = step_data
                public_input = asdict(step)

            else:
                raise TypeError("step_data must be dict or GhostStep")

            validated_intensity = validate_non_negative_finite(
                step.intensity,
                "step intensity",
            )

            safe_actor = normalize_id(step.actor, "agent id")
            safe_target = None

            if step.target:
                safe_target = normalize_id(step.target, "agent id")

            safe_step = dict(public_input)
            safe_step["actor"] = safe_actor
            safe_step["target"] = safe_target
            safe_step["intensity"] = validated_intensity

            ctx["cycles"] += 1

            # Public-facing state (DICT ONLY)
            ctx["input"] = safe_step
            ctx["last_step"] = safe_step

            step.actor = safe_actor
            step.target = safe_target

        # If no step, just return current state
        if step is None:
            return ctx

        npc["last_intent"] = step.intent

        # Ensure actor exists
        actor_state = self.agents.ensure(step.actor)
        actor_state["last_intent"] = step.intent

        # Optional target
        target_state = None
        if step.target:
            target_state = self.agents.ensure(step.target)
            target_state["last_intent"] = step.intent

        intensity = clamp(
            validated_intensity,
            0.0,
            1.0,
        )

        # ---- Intent handling ----
        if step.intent == "greet":
            actor_state["mood"] = clamp(actor_state["mood"] + (0.02 * intensity), 0.0, 1.0)
            actor_state["tension"] = clamp(actor_state["tension"] - (0.01 * intensity), 0.0, 1.0)

            if target_state is not None:
                target_state["mood"] = clamp(target_state["mood"] + (0.03 * intensity), 0.0, 1.0)
                target_state["tension"] = clamp(target_state["tension"] - (0.01 * intensity), 0.0, 1.0)

                self.relationships.apply_delta(
                    step.actor,
                    step.target,
                    {"trust": 0.02, "attachment": 0.01},
                )

            npc["threat_level"] = clamp(npc["threat_level"] - (0.02 * intensity), 0.0, 999999.0)

        elif step.intent == "help":
            actor_state["mood"] = clamp(actor_state["mood"] + (0.04 * intensity), 0.0, 1.0)
            actor_state["tension"] = clamp(actor_state["tension"] - (0.02 * intensity), 0.0, 1.0)

            if target_state is not None:
                target_state["mood"] = clamp(target_state["mood"] + (0.08 * intensity), 0.0, 1.0)
                target_state["tension"] = clamp(target_state["tension"] - (0.04 * intensity), 0.0, 1.0)

                self.relationships.apply_delta(
                    step.actor,
                    step.target,
                    {"trust": 0.05, "attachment": 0.02},
                )

            npc["threat_level"] = clamp(npc["threat_level"] - (0.05 * intensity), 0.0, 999999.0)

        elif step.intent == "threat":
            actor_state["mood"] = clamp(actor_state["mood"] - (0.05 * intensity), 0.0, 1.0)
            
            # actor memory invariant (public-facing)
            actors_mem = npc.setdefault("actors", {})
            entry = actors_mem.setdefault(step.actor, {})
            entry["threat_count"] = entry.get("threat_count", 0) + 1
            
            actor_state["tension"] = clamp(actor_state["tension"] + (0.06 * intensity), 0.0, 1.0)

            if target_state is not None:
                target_state["mood"] = clamp(target_state["mood"] - (0.12 * intensity), 0.0, 1.0)
                target_state["tension"] = clamp(target_state["tension"] + (0.18 * intensity), 0.0, 1.0)

                self.relationships.apply_delta(
                    step.actor,
                    step.target,
                    {"trust": -0.08},
                )

                # ---- bounded propagation to target neighbors ----
                neighbors = self.relationships.neighbors(step.target)
                spread = 0.25 * intensity

                for neighbor_id in neighbors:
                    if neighbor_id == step.actor or neighbor_id == step.target:
                        continue

                    neighbor_state = self.agents.ensure(neighbor_id)
                    neighbor_state["mood"] = clamp(neighbor_state["mood"] - (0.03 * spread), 0.0, 1.0)
                    neighbor_state["tension"] = clamp(neighbor_state["tension"] + (0.08 * spread), 0.0, 1.0)

            # emotional modulation (public invariant)
            mood = ctx.get("state", {}).get("mood", 0.5)

            gain = 0.50 * intensity * (0.5 + mood)

            npc["threat_level"] = clamp(npc["threat_level"] + gain, 0.0, 999999.0)

        else:
            # Unknown or neutral intent -> mild decay only
            npc["threat_level"] = clamp(npc["threat_level"] - 0.01, 0.0, 999999.0)

        return ctx

    def apply_event(
        self,
        a,
        b,
        event,
        intensity: float = 1.0,
        event_spec: dict | None = None,
    ):
        """
        Apply one relationship event through RelationshipGraph.
        """
        return self.relationships.apply_event(
            a,
            b,
            normalize_event(event),
            intensity=validate_unit_interval(
                intensity,
                "relationship event intensity",
            ),
            event_spec=event_spec,
        )

    def propagate_social_event(
        self,
        source,
        target,
        event,
        observers=None,
        weights=None,
        intensity: float = 1.0,
    ):
        """
        Apply a direct relationship event and propagate bounded
        secondary effects to observers.
        """
        propagate = getattr(
            self.relationships,
            "propagate_social_event",
        )

        return propagate(
            source=source,
            target=target,
            event=event,
            observers=observers,
            weights=weights,
            intensity=validate_unit_interval(
                intensity,
                "social event intensity",
            ),
        )

    def tick(self):
        """
        Advance relationship time decay by one tick.

        Public wrapper around the relationship runtime.
        """
        return self.relationships.tick()

    def get_relationship(self, a, b):
        """
        Return the public relationship state between two actors.

        Public wrapper around the relationship runtime.
        """
        return self.relationships.get_relationship(a, b)

    def state(self):
        """
        Return the live engine state (mutable).

        Intended for internal or controlled external use.
        """
        return self._ctx

    def snapshot(self):
        """
        Return an immutable JSON-safe snapshot of engine state.

        Snapshot metadata is included for save/load and adapter contracts.
        Existing engine state keys remain at the top level for backward
        compatibility.
        """
        snapshot = _json_safe(copy.deepcopy(self._ctx))

        snapshot["ghost_version"] = GHOST_VERSION
        snapshot["schema_version"] = (
            GHOST_SNAPSHOT_SCHEMA_VERSION
        )

        return snapshot
