from copy import deepcopy

import pytest

import ghost
from ghost import GhostAPI
from ghost.engine import (
    GHOST_LEGACY_SNAPSHOT_SCHEMA_VERSIONS,
    GHOST_PACKAGE_VERSION,
    GHOST_SNAPSHOT_SCHEMA_VERSION,
    GHOST_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS,
    GHOST_VERSION,
    GhostEngine,
)


PACKAGE_VERSION = "1.10.0"
SNAPSHOT_SCHEMA_VERSION = "1.0"
LEGACY_RELEASE_NAMED_SCHEMA_VERSION = "1.7.5"


def test_package_and_snapshot_versions_are_independent_v180():
    assert ghost.__version__ == PACKAGE_VERSION
    assert GHOST_PACKAGE_VERSION == PACKAGE_VERSION
    assert GHOST_VERSION == PACKAGE_VERSION
    assert (
        GHOST_SNAPSHOT_SCHEMA_VERSION
        == SNAPSHOT_SCHEMA_VERSION
    )
    assert GHOST_VERSION != GHOST_SNAPSHOT_SCHEMA_VERSION


def test_supported_schema_versions_are_explicit_v180():
    assert (
        SNAPSHOT_SCHEMA_VERSION
        in GHOST_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS
    )
    assert (
        LEGACY_RELEASE_NAMED_SCHEMA_VERSION
        in GHOST_LEGACY_SNAPSHOT_SCHEMA_VERSIONS
    )
    assert (
        LEGACY_RELEASE_NAMED_SCHEMA_VERSION
        in GHOST_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS
    )


def test_engine_snapshot_emits_current_package_and_schema_v180():
    snapshot = GhostEngine().snapshot()

    assert snapshot["ghost_version"] == PACKAGE_VERSION
    assert (
        snapshot["schema_version"]
        == SNAPSHOT_SCHEMA_VERSION
    )


def test_engine_snapshot_metadata_cannot_be_overridden_v180():
    engine = GhostEngine(
        {
            "ghost_version": "caller-controlled",
            "schema_version": "caller-controlled",
        }
    )

    snapshot = engine.snapshot()

    assert snapshot["ghost_version"] == PACKAGE_VERSION
    assert (
        snapshot["schema_version"]
        == SNAPSHOT_SCHEMA_VERSION
    )


def test_engine_restore_accepts_prior_package_metadata_v180():
    snapshot = GhostEngine().snapshot()
    snapshot["ghost_version"] = "1.7.5"

    restored = GhostEngine.from_snapshot(
        deepcopy(snapshot)
    )

    restored_snapshot = restored.snapshot()

    assert restored_snapshot["ghost_version"] == PACKAGE_VERSION
    assert (
        restored_snapshot["schema_version"]
        == SNAPSHOT_SCHEMA_VERSION
    )


def test_engine_restore_migrates_legacy_schema_metadata_v180():
    snapshot = GhostEngine().snapshot()
    snapshot["ghost_version"] = "1.7.5"
    snapshot["schema_version"] = (
        LEGACY_RELEASE_NAMED_SCHEMA_VERSION
    )

    restored = GhostEngine.from_snapshot(
        deepcopy(snapshot)
    )

    restored_snapshot = restored.snapshot()

    assert restored_snapshot["ghost_version"] == PACKAGE_VERSION
    assert (
        restored_snapshot["schema_version"]
        == SNAPSHOT_SCHEMA_VERSION
    )


def test_api_restore_uses_schema_not_producer_version_v180():
    snapshot = GhostAPI().snapshot()
    snapshot["ghost_version"] = "1.7.5"
    snapshot["schema_version"] = (
        LEGACY_RELEASE_NAMED_SCHEMA_VERSION
    )
    snapshot["engine"]["ghost_version"] = "1.7.5"
    snapshot["engine"]["schema_version"] = (
        LEGACY_RELEASE_NAMED_SCHEMA_VERSION
    )

    restored = GhostAPI.from_snapshot(
        deepcopy(snapshot)
    )

    restored_snapshot = restored.snapshot()

    assert restored_snapshot["ghost_version"] == PACKAGE_VERSION
    assert (
        restored_snapshot["schema_version"]
        == SNAPSHOT_SCHEMA_VERSION
    )
    assert (
        restored_snapshot["engine"]["ghost_version"]
        == PACKAGE_VERSION
    )
    assert (
        restored_snapshot["engine"]["schema_version"]
        == SNAPSHOT_SCHEMA_VERSION
    )


def test_api_restore_rejects_malformed_producer_version_v180():
    snapshot = GhostAPI().snapshot()
    snapshot["ghost_version"] = []

    with pytest.raises(
        ValueError,
        match="ghost_version must be a non-empty string",
    ):
        GhostAPI.from_snapshot(
            snapshot
        )


def test_unknown_snapshot_schema_remains_rejected_v180():
    engine_snapshot = GhostEngine().snapshot()
    engine_snapshot["schema_version"] = "999.0"

    with pytest.raises(
        ValueError,
        match="unsupported engine snapshot schema",
    ):
        GhostEngine.from_snapshot(
            engine_snapshot
        )

    api_snapshot = GhostAPI().snapshot()
    api_snapshot["schema_version"] = "999.0"

    with pytest.raises(
        ValueError,
        match="unsupported GhostAPI snapshot schema",
    ):
        GhostAPI.from_snapshot(
            api_snapshot
        )
