import inspect

import ghost.api as api_module
from ghost import GhostAPI


def test_api_module_docstring_is_current_v171_cleanup():
    doc = inspect.getdoc(api_module)

    assert "v1.7.1 public API cleanup focus" in doc
    assert "GhostAPI is the high-level integration surface" in doc
    assert "snapshot() returns a JSON-safe copied public snapshot" in doc
    assert "Temperament interpretation is stateless and read-only" in doc

    assert "v1.1.0 adds Governance Core" not in doc


def test_ghostapi_class_docstring_clarifies_api_vs_engine():
    doc = inspect.getdoc(GhostAPI)

    assert "High-level public integration surface" in doc
    assert "Use GhostAPI for normal external integrations" in doc
    assert "Use GhostEngine directly only" in doc
