from __future__ import annotations

from copy import deepcopy

import pytest

from ghost import GhostAPI


def test_release_legacy_optional_restore_fallbacks_and_direct_attention_v1100():
    api = GhostAPI()
    snapshot = api.snapshot()

    # Current snapshots include optional public runtime layers only when they
    # carry state. A supported legacy packet may omit them; restoring such a
    # packet must construct fresh empty runtimes without changing the top-level
    # schema contract.
    legacy = deepcopy(snapshot)
    for key in (
        "event_map",
        "epistemic",
        "emotions",
        "interpretations",
        "attention",
        "ghost_version",
        "transitions",
    ):
        legacy.pop(key, None)

    restored = GhostAPI.from_snapshot(legacy)
    restored_snapshot = restored.snapshot()

    assert restored_snapshot["schema_version"] == "1.0"
    assert restored_snapshot["ghost_version"] == "1.11.0"
    assert restored_snapshot["world"] == snapshot["world"]
    assert restored_snapshot["event_map"]
    # Epistemic state is always serialized by GhostAPI.snapshot(), even when
    # the restored legacy packet omitted it; the fallback creates a fresh
    # empty epistemic runtime.
    assert "epistemic" in restored_snapshot
    assert restored_snapshot["epistemic"] == GhostAPI().snapshot()["epistemic"]
    assert "emotions" not in restored_snapshot
    assert "interpretations" not in restored_snapshot
    assert "attention" not in restored_snapshot

    # Release coverage must also prove the fail-closed validation branches for
    # both optional v1.10 runtime snapshots. These are public persistence
    # contract checks, not unreachable/dead branches.
    bad_interpretations = deepcopy(snapshot)
    bad_interpretations["interpretations"] = []
    with pytest.raises(
        ValueError,
        match="snapshot interpretations must be a dict",
    ):
        GhostAPI.from_snapshot(bad_interpretations)

    bad_attention = deepcopy(snapshot)
    bad_attention["attention"] = []
    with pytest.raises(
        ValueError,
        match="snapshot attention must be a dict",
    ):
        GhostAPI.from_snapshot(bad_attention)

    # Exercise the thin public interpretation-rule wrapper directly. Runtime
    # behavior is already covered elsewhere; this closes the public API line
    # without changing production code merely to satisfy coverage.
    rule = restored.configure_interpretation_rule(
        "sera",
        "action:release_coverage_probe",
        {"cooperation": 0.25},
    )
    assert rule == {
        "agent": "sera",
        "feature": "action:release_coverage_probe",
        "pressures": {"cooperation": 0.25},
    }
    assert restored.interpretation_state("sera")["rules"][
        "action:release_coverage_probe"
    ] == {"cooperation": 0.25}

    # Also exercise the successful direct attention API rather than only the
    # read-only bridge path. The caller-owned salience packet remains untouched.
    salience = {"host:priority": 0.5}
    packet = restored.advance_attention(
        "sera",
        signals={"task_focus": 0.5, "stability": 0.5},
        salience=salience,
        source="release-coverage-closure",
        provenance={"gate": "v1.11.0"},
    )

    assert packet["agent"] == "sera"
    assert packet["underlying_salience"] == salience
    assert salience == {"host:priority": 0.5}
    assert restored.attention_state("sera") is not None
