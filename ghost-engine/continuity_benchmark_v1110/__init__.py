"""Frozen NPC continuity comparison experiment for Ghost v1.11 development."""

from .contract import CONTRACT_VERSION, contract_digest, scenario_manifest
from .purpose_built import PurposeBuiltContinuity
from .scenario_runner import run_frozen_suite

__all__ = [
    "CONTRACT_VERSION",
    "PurposeBuiltContinuity",
    "contract_digest",
    "run_frozen_suite",
    "scenario_manifest",
]
