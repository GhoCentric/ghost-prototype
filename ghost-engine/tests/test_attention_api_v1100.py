from __future__ import annotations

from copy import deepcopy
import inspect
import json

import pytest

from ghost import GhostAPI
from ghost.attention import ATTENTION_SNAPSHOT_SCHEMA_VERSION


def _focus():
    return {
        "task_focus": 1.0,
        "repetition": 1.0,
        "stability": 1.0,
        "novelty": 0.0,
        "threat": 0.0,
        "contradiction": 0.0,
        "interpretation_impulse": 0.0,
    }


def test_v110_attention_api_signatures_are_explicit():
    expected = {
        "register_attention_agent": (
            "self",
            "agent",
            "initial_flow_pressure",
            "flow_active",
            "config",
        ),
        "attention_state": (
            "self",
            "agent",
        ),
        "advance_attention": (
            "self",
            "agent",
            "signals",
            "salience",
            "source",
            "provenance",
        ),
    }
    for method_name, names in expected.items():
        signature = inspect.signature(getattr(GhostAPI, method_name))
        assert tuple(signature.parameters) == names


def test_v110_attention_api_preserves_underlying_salience_and_suppresses_access():
    api = GhostAPI()
    api.register_attention_agent("sera")
    salience = {"betrayal": 0.85, "anger": 0.70}
    packet = None
    for _ in range(8):
        packet = api.advance_attention("sera", _focus(), salience)
    assert packet["flow_active_after"] is True
    assert packet["underlying_salience"] == salience
    assert packet["attended_salience"]["betrayal"] < salience["betrayal"]
    assert salience == {"betrayal": 0.85, "anger": 0.70}


def test_v110_attention_api_strong_threat_breaks_through_flow():
    api = GhostAPI()
    for _ in range(9):
        api.advance_attention("sera", _focus(), {"betrayal": 0.8})
    packet = api.advance_attention(
        "sera",
        {**_focus(), "threat": 1.0},
        {"betrayal": 0.8},
        source="world",
        provenance={"event": "castle_fire"},
    )
    assert packet["breakthrough"] is True
    assert packet["resurfaced"] is True
    assert packet["attention_gain"] == 1.0
    assert packet["attended_salience"] == {"betrayal": 0.8}


def test_v110_api_snapshot_round_trip_persists_attention_runtime():
    api = GhostAPI()
    for _ in range(7):
        api.advance_attention("sera", _focus(), {"anger": 0.9})
    snapshot = api.snapshot()
    assert snapshot["attention"]["schema_version"] == ATTENTION_SNAPSHOT_SCHEMA_VERSION
    json.dumps(snapshot, sort_keys=True, allow_nan=False)

    restored = GhostAPI.from_snapshot(deepcopy(snapshot))
    assert restored.snapshot() == snapshot
    assert restored.attention_state("sera") == api.attention_state("sera")


def test_v110_old_snapshot_without_attention_restores_without_shape_change():
    api = GhostAPI()
    legacy = api.snapshot()
    assert "attention" not in legacy

    restored = GhostAPI.from_snapshot(deepcopy(legacy))
    assert restored.snapshot() == legacy
    assert restored.attention_state("sera") is None


def test_v110_invalid_attention_snapshot_is_rejected_without_mutating_existing_api():
    source = GhostAPI()
    source.advance_attention("sera", _focus())
    packet = source.snapshot()
    packet["attention"]["schema_version"] = "999"

    target = GhostAPI()
    before = target.snapshot()
    with pytest.raises(ValueError):
        target.restore_snapshot(packet)
    assert target.snapshot() == before


def test_v110_attention_and_interpretation_snapshot_layers_coexist():
    api = GhostAPI()
    api.register_interpretation_agent(
        "sera",
        rules={"confidential_evidence_shared": {"betrayal": 0.8}},
    )
    meaning = api.evaluate_action_meaning(
        "sera",
        "report_evidence_to_guards",
        {"confidential_evidence_shared": 1.0},
    )
    api.advance_attention(
        "sera",
        _focus(),
        {"betrayal": meaning["state"]["levels"]["betrayal"]},
    )
    snapshot = api.snapshot()
    assert "interpretations" in snapshot
    assert "attention" in snapshot
    restored = GhostAPI.from_snapshot(deepcopy(snapshot))
    assert restored.snapshot() == snapshot
