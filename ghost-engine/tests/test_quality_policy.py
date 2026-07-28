"""Contracts for Ghost's separated quality lanes."""

from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_ini(name: str) -> ConfigParser:
    parser = ConfigParser()
    loaded = parser.read(ROOT / name)

    assert loaded

    return parser


def test_performance_marker_is_registered_and_applied():
    pyproject = (ROOT / "pyproject.toml").read_text()

    assert (
        "performance: local throughput regression checks "
        "that must run without coverage tracing"
    ) in pyproject

    performance_source = (
        ROOT
        / "tests"
        / "performance"
        / "test_ips_floor.py"
    ).read_text()

    assert "@pytest.mark.performance" in performance_source


def test_coverage_lanes_keep_scopes_separate():
    core = read_ini("coverage.core.ini")
    revolution = read_ini("coverage.revolution.ini")

    assert core["run"]["branch"].lower() == "true"
    assert core["run"]["source"].strip() == "ghost"
    assert "ghost/examples/*" in core["run"]["omit"]

    assert revolution["run"]["branch"].lower() == "true"
    assert "source" not in revolution["run"]

    quality_doc = (ROOT / "QUALITY.md").read_text()

    assert "pytest -q -m performance" in quality_doc
    assert "coverage.core.ini" in quality_doc
    assert "coverage.revolution.ini" in quality_doc
