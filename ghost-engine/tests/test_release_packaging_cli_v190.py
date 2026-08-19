from __future__ import annotations

import importlib
from pathlib import Path
import tomllib

import ghost
from ghost.api import GhostAPI
from ghost.engine import (
    GHOST_PACKAGE_VERSION,
    GHOST_SNAPSHOT_SCHEMA_VERSION,
    GHOST_VERSION,
)


ROOT = Path(__file__).resolve().parents[1]


EXPECTED_SCRIPTS = {
    "ghost-demo": "ghost.examples.relationship_proof_demo:main",
    "ghost-npc-demo": "ghost.examples.simple_npc_demo:main",
    "ghost-shopkeeper-demo": "ghost.examples.shopkeeper_mini_game:main",
    "ghost-math-demo": "ghost.examples.ghost_math_helper:main",
    "ghost-diagnostics-demo":
        "ghost.examples.relationship_diagnostics_demo:main",
    "ghost-social-demo": "ghost.examples.social_propagation_demo:main",
    "ghost-temperament-demo": "ghost.examples.temperament_demo:main",
    "ghost-threat-response-demo":
        "ghost.examples.threat_response_demo:main",
    "ghost-epistemic-demo":
        "ghost.examples.epistemic_api_smoke_demo:main",
    "ghost-revolution-demo":
        "ghost.examples.ghost_revolution.demo:main",
    "ghost-revolution-dev":
        "ghost.examples.ghost_revolution.dev_shortcuts:main",
    "ghost-revolution-llm-dev":
        "ghost.examples.ghost_revolution.live_llm_dev:main",
    "ghost-order-coordination-demo":
        "ghost.examples.order_coordination_demo:main",
}


def _pyproject() -> dict:
    return tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )


def test_v190_package_and_runtime_versions():
    assert _pyproject()["project"]["version"] == "1.10.0"
    assert ghost.__version__ == "1.10.0"
    assert GHOST_PACKAGE_VERSION == "1.10.0"
    assert GHOST_VERSION == "1.10.0"


def test_v190_snapshot_schema_intentionally_remains_v1():
    assert GHOST_SNAPSHOT_SCHEMA_VERSION == "1.0"

    api = GhostAPI()
    snapshot = api.snapshot()

    assert snapshot["ghost_version"] == "1.10.0"
    assert snapshot["schema_version"] == "1.0"
    assert snapshot["engine"]["ghost_version"] == "1.10.0"
    assert snapshot["engine"]["schema_version"] == "1.0"


def test_v190_v180_producer_snapshot_remains_restoreable():
    api = GhostAPI()
    snapshot = api.snapshot()

    snapshot["ghost_version"] = "1.8.0"
    snapshot["engine"]["ghost_version"] = "1.8.0"

    restored = GhostAPI.from_snapshot(snapshot)
    current = restored.snapshot()

    assert current["ghost_version"] == "1.10.0"
    assert current["schema_version"] == "1.0"
    assert current["engine"]["ghost_version"] == "1.10.0"
    assert current["engine"]["schema_version"] == "1.0"


def test_v190_declared_cli_contract_is_exact():
    scripts = _pyproject()["project"]["scripts"]
    assert scripts == EXPECTED_SCRIPTS


def test_v190_all_declared_cli_targets_resolve_to_callables():
    for target in EXPECTED_SCRIPTS.values():
        module_name, attr_name = target.split(":", 1)
        value = importlib.import_module(module_name)

        for part in attr_name.split("."):
            value = getattr(value, part)

        assert callable(value)


def test_v190_order_coordination_console_wrapper_returns_none(
    monkeypatch,
):
    module = importlib.import_module(
        "ghost.examples.order_coordination_demo"
    )
    calls = []

    monkeypatch.setattr(
        module,
        "run_demo",
        lambda: calls.append("run"),
    )

    assert module.main() is None
    assert calls == ["run"]


def test_v190_readme_lists_version_validation_and_new_cli_commands():
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Version:    1.10.0" in text
    assert "Validation: 2,390 passed, 1 skipped" in text

    for command in (
        "ghost-epistemic-demo",
        "ghost-revolution-demo",
        "ghost-revolution-dev",
        "ghost-revolution-llm-dev",
        "ghost-order-coordination-demo",
    ):
        assert command in text
