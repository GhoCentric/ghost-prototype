import copy
import json
import math
from types import ModuleType

import pytest
from hypothesis import given, settings, strategies as st

from ghost.api import GhostAPI
from ghost.engine import GhostEngine
from ghost.events import RelationshipEvent


VALID_AGENT_IDS = st.text(
    alphabet=st.characters(
        blacklist_characters="|",
        blacklist_categories=("Cs",),
    ),
    min_size=1,
    max_size=8,
).filter(lambda value: value.strip() != "")


RELATIONSHIP_EVENTS = st.sampled_from(
    [
        "greet",
        "help",
        "gift",
        "apologize",
        "insult",
        "threat",
        "attack",
        "betrayal",
    ]
)


STEP_INTENTS = st.sampled_from(
    [
        "greet",
        "help",
        "threat",
        "attack",
        "observe",
        "wait",
    ]
)


def assert_no_internal_objects(value):
    if isinstance(value, dict):
        for key, item in value.items():
            assert isinstance(key, str)
            assert_no_internal_objects(item)
        return

    if isinstance(value, (list, tuple)):
        for item in value:
            assert_no_internal_objects(item)
        return

    if isinstance(value, set):
        raise AssertionError("public state must not contain sets")

    if isinstance(value, ModuleType):
        raise AssertionError("public state must not contain modules")

    if callable(value):
        raise AssertionError("public state must not contain callables")

    assert isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
            type(None),
        ),
    )


def assert_strict_json_safe(packet):
    assert_no_internal_objects(packet)
    json.dumps(packet, allow_nan=False)


def pair_from_key(pair_key):
    parts = str(pair_key).split("|")

    if len(parts) != 2:
        raise AssertionError(f"Invalid relationship key shape: {pair_key!r}")

    return parts[0], parts[1]


def assert_public_relationship_invariants(relationship):
    assert_strict_json_safe(relationship)

    pos = relationship.get("pos")
    neg = relationship.get("neg")

    if "trust" in relationship:
        trust = relationship["trust"]
    elif pos is not None and neg is not None:
        trust = pos - neg
    else:
        trust = 0.0

    assert math.isfinite(trust)
    assert -5.0 <= trust <= 5.0

    if pos is not None:
        assert math.isfinite(pos)
        assert 0.0 <= pos <= relationship.get("max_reservoir", 5.0)

    if neg is not None:
        assert math.isfinite(neg)
        assert 0.0 <= neg <= relationship.get("max_reservoir", 5.0)

    if "state" in relationship:
        assert relationship["state"] in {
            "hostile",
            "neutral",
            "friendly",
        }


def assert_raw_relationship_invariants(raw_relationship):
    assert_strict_json_safe(raw_relationship)

    max_reservoir = raw_relationship.get("max_reservoir", 5.0)
    pos = raw_relationship.get("pos", 0.0)
    neg = raw_relationship.get("neg", 0.0)

    assert math.isfinite(max_reservoir)
    assert math.isfinite(pos)
    assert math.isfinite(neg)

    assert max_reservoir > 0.0
    assert 0.0 <= pos <= max_reservoir
    assert 0.0 <= neg <= max_reservoir


def assert_snapshot_invariants(snapshot):
    assert_strict_json_safe(snapshot)

    assert isinstance(snapshot["cycles"], int)
    assert snapshot["cycles"] >= 0

    assert snapshot["ghost_version"] == "1.7.0"
    assert snapshot["schema_version"] == "1.7.0"

    npc = snapshot["npc"]

    assert math.isfinite(npc["threat_level"])
    assert npc["threat_level"] >= 0.0

    for agent in snapshot["agents"].values():
        assert math.isfinite(agent["mood"])
        assert math.isfinite(agent["tension"])

        assert 0.0 <= agent["mood"] <= 1.0
        assert 0.0 <= agent["tension"] <= 1.0


def assert_engine_invariants(engine):
    snapshot = engine.snapshot()
    assert_snapshot_invariants(snapshot)

    for pair_key, raw_relationship in engine.relationships.all().items():
        assert_raw_relationship_invariants(raw_relationship)

        actor, target = pair_from_key(pair_key)
        public_relationship = engine.relationships.get(actor, target)

        assert_public_relationship_invariants(public_relationship)

    return snapshot


@given(
    events=st.lists(
        st.tuples(
            VALID_AGENT_IDS,
            VALID_AGENT_IDS,
            RELATIONSHIP_EVENTS,
            st.floats(
                min_value=0.0,
                max_value=1.0,
                allow_nan=False,
                allow_infinity=False,
            ),
        ),
        min_size=1,
        max_size=40,
    )
)
@settings(max_examples=75)
def test_relationship_event_sequences_preserve_invariants(events):
    engine = GhostEngine()

    previous_cycles = engine.snapshot()["cycles"]

    for actor, target, event_type, intensity in events:
        if actor.strip() == target.strip():
            target = target.strip() + "_target"

        packet = engine.apply_event(
            actor,
            target,
            event_type,
            intensity=intensity,
        )

        assert_strict_json_safe(packet)

        snapshot = assert_engine_invariants(engine)

        assert snapshot["cycles"] >= previous_cycles
        previous_cycles = snapshot["cycles"]


@given(
    steps=st.lists(
        st.fixed_dictionaries(
            {
                "source": st.just("property_test"),
                "intent": STEP_INTENTS,
                "actor": VALID_AGENT_IDS,
                "target": VALID_AGENT_IDS,
                "intensity": st.floats(
                    min_value=0.0,
                    max_value=10.0,
                    allow_nan=False,
                    allow_infinity=False,
                ),
            }
        ),
        min_size=1,
        max_size=40,
    )
)
@settings(max_examples=75)
def test_step_sequences_preserve_engine_invariants(steps):
    engine = GhostEngine()

    previous_cycles = engine.snapshot()["cycles"]

    for step in steps:
        if step["actor"].strip() == step["target"].strip():
            step = dict(step)
            step["target"] = step["target"].strip() + "_target"

        engine.step(step)

        snapshot = assert_engine_invariants(engine)

        assert snapshot["cycles"] == previous_cycles + 1
        previous_cycles = snapshot["cycles"]


def test_bad_step_input_is_atomic():
    bad_steps = [
        {
            "source": "test",
            "intent": "threat",
            "actor": "A",
            "target": "B",
            "intensity": -0.1,
        },
        {
            "source": "test",
            "intent": "threat",
            "actor": "A",
            "target": "B",
            "intensity": float("nan"),
        },
        {
            "source": "test",
            "intent": "threat",
            "actor": "A",
            "target": "B",
            "intensity": float("inf"),
        },
        {
            "source": "test",
            "intent": "threat",
            "actor": "A",
            "target": "B",
            "intensity": float("-inf"),
        },
        {
            "source": "test",
            "intent": "threat",
            "actor": "",
            "target": "B",
            "intensity": 1.0,
        },
        {
            "source": "test",
            "intent": "threat",
            "actor": "bad|id",
            "target": "B",
            "intensity": 1.0,
        },
    ]

    for bad_step in bad_steps:
        engine = GhostEngine()
        before = copy.deepcopy(engine.state())

        with pytest.raises((ValueError, TypeError)):
            engine.step(bad_step)

        after = engine.state()

        assert after == before
        assert_engine_invariants(engine)


def test_bad_api_relationship_input_is_atomic():
    bad_events = [
        {
            "type": "help",
            "intensity": -0.1,
        },
        {
            "type": "help",
            "intensity": 1.1,
        },
        {
            "type": "help",
            "intensity": float("nan"),
        },
        {
            "type": "help",
            "intensity": float("inf"),
        },
        {
            "type": "help",
            "intensity": float("-inf"),
        },
    ]

    for bad_event in bad_events:
        api = GhostAPI()
        before_engine = copy.deepcopy(api.engine.state())
        before_world = copy.deepcopy(api.world.to_dict())

        with pytest.raises(ValueError):
            api.apply_event("A", "B", bad_event)

        assert api.engine.state() == before_engine
        assert api.world.to_dict() == before_world

        assert_engine_invariants(api.engine)
        assert_strict_json_safe(api.world.to_dict())


def test_determinism_same_initial_state_same_sequence():
    sequence = [
        ("A", "B", "help", 1.0),
        ("A", "B", "insult", 0.5),
        ("B", "C", "gift", 0.75),
        ("A", "B", "betrayal", 1.0),
        ("C", "A", "apologize", 0.25),
    ]

    engine_a = GhostEngine()
    engine_b = GhostEngine()

    for actor, target, event_type, intensity in sequence:
        engine_a.apply_event(
            actor,
            target,
            event_type,
            intensity=intensity,
        )
        engine_b.apply_event(
            actor,
            target,
            event_type,
            intensity=intensity,
        )

    assert engine_a.snapshot() == engine_b.snapshot()
    assert_engine_invariants(engine_a)
    assert_engine_invariants(engine_b)


def test_snapshot_isolation_after_agent_and_relationship_activity():
    engine = GhostEngine()

    engine.step(
        {
            "source": "test",
            "intent": "observe",
            "actor": "A",
            "target": "B",
            "intensity": 0.0,
        }
    )

    engine.apply_event(
        "A",
        "B",
        RelationshipEvent.BETRAYAL,
        intensity=1.0,
    )

    snapshot = engine.snapshot()
    snapshot["cycles"] = 999
    snapshot["agents"]["A"]["mood"] = 999.0
    snapshot["relationships"] = {
        "corrupt": {
            "pos": 999.0,
            "neg": 999.0,
        }
    }

    fresh = engine.snapshot()

    assert fresh["cycles"] != 999
    assert fresh["agents"]["A"]["mood"] != 999.0
    assert "corrupt" not in fresh.get("relationships", {})

    assert_engine_invariants(engine)


def test_public_reads_are_copy_safe_after_agent_and_relationship_activity():
    engine = GhostEngine()

    engine.step(
        {
            "source": "test",
            "intent": "observe",
            "actor": "A",
            "target": "B",
            "intensity": 0.0,
        }
    )

    engine.apply_event(
        "A",
        "B",
        "betrayal",
        intensity=1.0,
    )

    agent_read = engine.agents.get("A")
    agent_read["mood"] = 999.0

    relationship_read = engine.relationships.get("A", "B")
    relationship_read["trust"] = 999.0

    all_relationships = engine.relationships.all()
    first_key = next(iter(all_relationships))
    all_relationships[first_key]["pos"] = 999.0

    neighbors = engine.relationships.neighbors("A")
    neighbors.append("corruption")

    assert engine.agents.get("A")["mood"] != 999.0
    assert engine.relationships.get("A", "B")["trust"] != 999.0
    assert "corruption" not in engine.relationships.neighbors("A")

    assert_engine_invariants(engine)


def test_tick_decay_does_not_explode_state():
    api = GhostAPI()

    api.apply_event(
        "A",
        "B",
        {
            "type": "betrayal",
            "intensity": 1.0,
        },
    )
    api.apply_world_effects(
        {
            "pressure_delta": 1.0,
            "fear_delta": 1.0,
            "resentment_delta": 1.0,
        }
    )

    previous_pressure = api.world.to_dict()["global_pressure"]

    for _ in range(25):
        packet = api.tick()

        world = api.world.to_dict()
        relationship = api.get_relationship("A", "B")

        assert_strict_json_safe(packet)
        assert_strict_json_safe(world)
        assert_public_relationship_invariants(relationship)

        assert 0.0 <= world["global_pressure"] <= 5.0
        assert world["global_pressure"] <= previous_pressure

        previous_pressure = world["global_pressure"]

    assert_engine_invariants(api.engine)


def test_help_after_betrayal_does_not_instantly_erase_betrayal_history():
    api = GhostAPI()

    betrayal_packet = api.apply_event(
        "Player",
        "Villager",
        {
            "type": "betrayal",
            "intensity": 1.0,
        },
    )

    after_betrayal = api.get_relationship("Player", "Villager")
    raw_after_betrayal = api.engine.relationships.all()[
        "Player|Villager"
    ]

    help_packet = api.apply_event(
        "Player",
        "Villager",
        {
            "type": "help",
            "intensity": 1.0,
        },
    )

    after_help = api.get_relationship("Player", "Villager")
    raw_after_help = api.engine.relationships.all()[
        "Player|Villager"
    ]

    assert_strict_json_safe(betrayal_packet)
    assert_strict_json_safe(help_packet)

    assert_public_relationship_invariants(after_betrayal)
    assert_public_relationship_invariants(after_help)
    assert_raw_relationship_invariants(raw_after_betrayal)
    assert_raw_relationship_invariants(raw_after_help)

    assert raw_after_betrayal["neg"] > 0.0
    assert raw_after_help["neg"] > 0.0
    assert after_help["trust"] > after_betrayal["trust"]

    assert (
        after_help["trust"] < 0.0
        or raw_after_help["neg"] >= raw_after_betrayal["neg"] * 0.5
    )
