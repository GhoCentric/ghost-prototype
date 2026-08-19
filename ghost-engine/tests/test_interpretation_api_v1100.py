from __future__ import annotations

from copy import deepcopy
import inspect
import json

import pytest

from ghost import GhostAPI
from ghost.interpretation import INTERPRETATION_SNAPSHOT_SCHEMA_VERSION


def _configure_case(api: GhostAPI) -> None:
    api.register_interpretation_agent(
        "sera",
        thresholds={
            "betrayal": {"enter": 0.60, "exit": 0.40},
            "cooperation": 0.70,
        },
        rules={
            "action:report_evidence_to_guards": {
                "betrayal": 0.15,
                "cooperation": 0.05,
            },
            "confidential_evidence_shared": {"betrayal": 0.70},
            "authority_involved": {"betrayal": 0.10},
        },
    )
    api.register_interpretation_agent(
        "rowan",
        thresholds={
            "betrayal": 0.75,
            "cooperation": 0.55,
        },
        rules={
            "action:report_evidence_to_guards": {"cooperation": 0.65},
            "confidential_evidence_shared": {"betrayal": 0.05},
        },
    )


def test_v110_development_api_signatures_are_explicit():
    expected = {
        "register_interpretation_agent": (
            "self",
            "agent",
            "initial",
            "baseline",
            "thresholds",
            "sensitivities",
            "rules",
        ),
        "configure_interpretation_rule": (
            "self",
            "agent",
            "feature",
            "pressures",
        ),
        "interpretation_state": (
            "self",
            "agent",
        ),
        "evaluate_action_meaning": (
            "self",
            "agent",
            "action",
            "features",
            "intensity",
            "context_modifiers",
            "source",
            "provenance",
        ),
    }
    for method_name, names in expected.items():
        signature = inspect.signature(getattr(GhostAPI, method_name))
        assert tuple(signature.parameters) == names


def test_v110_same_objective_action_can_cross_different_npc_meaning_thresholds():
    api = GhostAPI()
    _configure_case(api)
    features = {
        "confidential_evidence_shared": 1.0,
        "authority_involved": 1.0,
    }
    sera = api.evaluate_action_meaning(
        "sera",
        "report_evidence_to_guards",
        features,
        source="player",
    )
    rowan = api.evaluate_action_meaning(
        "rowan",
        "report_evidence_to_guards",
        features,
        source="player",
    )

    assert sera["objective_action"] == rowan["objective_action"]
    assert sera["active_interpretations"] == ["betrayal"]
    assert rowan["active_interpretations"] == ["cooperation"]


def test_v110_api_snapshot_round_trip_persists_interpretation_runtime():
    api = GhostAPI()
    _configure_case(api)
    api.evaluate_action_meaning(
        "sera",
        "report_evidence_to_guards",
        {"confidential_evidence_shared": 1.0},
        provenance={"evidence_id": "ledger-1"},
    )
    snapshot = api.snapshot()

    assert snapshot["interpretations"]["schema_version"] == (
        INTERPRETATION_SNAPSHOT_SCHEMA_VERSION
    )
    json.dumps(snapshot, sort_keys=True, allow_nan=False)

    restored = GhostAPI.from_snapshot(deepcopy(snapshot))
    assert restored.snapshot() == snapshot
    assert restored.interpretation_state("sera") == api.interpretation_state("sera")


def test_v110_old_snapshot_without_interpretations_restores_without_shape_change():
    api = GhostAPI()
    legacy = api.snapshot()
    assert "interpretations" not in legacy

    restored = GhostAPI.from_snapshot(deepcopy(legacy))
    assert restored.snapshot() == legacy
    assert restored.interpretation_state("sera") is None


def test_v110_invalid_interpretation_snapshot_is_rejected_without_mutating_existing_api():
    source = GhostAPI()
    _configure_case(source)
    packet = source.snapshot()
    packet["interpretations"]["schema_version"] = "999"

    target = GhostAPI()
    before = target.snapshot()
    with pytest.raises(ValueError):
        target.restore_snapshot(packet)
    assert target.snapshot() == before
