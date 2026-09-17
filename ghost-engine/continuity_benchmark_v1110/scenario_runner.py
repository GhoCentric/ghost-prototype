"""Frozen scenario runner shared by Stage-1 baseline and later Ghost adapter."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .contract import ArchiveMismatchError, CapacityBackpressureError, scenario_manifest


EPS = 1e-12


def _digest(value) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _max_affect(state: dict) -> float:
    return max(state["emotion"].values(), default=0.0)


def _tick(system, agent: str, count: int) -> None:
    system.tick(agent, count)


def _scenario_moving(factory, root: Path, label: str) -> dict:
    s = factory(root, label)
    try:
        s.event("npc", source="betrayal-1", dimension="betrayal", meaning_delta=0.9,
                relevance=0.9, emotion_profile={"anger": 0.75, "grief": 0.65, "fear": 0.35}, consequence=-1.0)
        fresh = s.observe("npc")
        _tick(s, "npc", 32)
        moved = s.observe("npc")
        return {
            "checks": {
                "meaning_persists": moved["meaning"]["betrayal"] >= fresh["meaning"]["betrayal"] - EPS,
                "relevance_releases": moved["activation"]["betrayal"] < fresh["activation"]["betrayal"] * 1e-6,
                "old_concern_not_foreground": moved["foreground"] != "betrayal",
                "associated_affect_relaxes": _max_affect(moved) < _max_affect(fresh) * 0.20,
            },
            "measures": {
                "fresh_relevance": fresh["activation"]["betrayal"],
                "moved_relevance": moved["activation"]["betrayal"],
            },
        }
    finally:
        s.close()


def _scenario_recall(factory, root: Path, label: str) -> dict:
    s = factory(root, label)
    try:
        row = s.event("npc", source="betrayal-1", dimension="betrayal", meaning_delta=0.9,
                      relevance=0.9, emotion_profile={"anger": 0.8}, consequence=-1.0)
        _tick(s, "npc", 32)
        before = s.observe("npc")
        recalled = s.recall_episode(row["episode_id"], 0.7)
        after = s.observe("npc")
        return {
            "checks": {
                "meaning_unchanged": recalled["meaning_unchanged"] and after["meaning"] == before["meaning"],
                "consequence_unchanged": abs(after["trust"] - before["trust"]) <= EPS,
                "target_relevance_rises": after["activation"]["betrayal"] > before["activation"]["betrayal"] + 0.5,
                "target_becomes_current_again": after["foreground"] == "betrayal",
                "episode_affect_reexpresses": after["emotion"]["anger"] > before["emotion"]["anger"] + EPS,
            },
            "measures": {"relevance_gain": after["activation"]["betrayal"] - before["activation"]["betrayal"]},
        }
    finally:
        s.close()


def _scenario_identity(factory, root: Path, label: str) -> dict:
    s = factory(root, label)
    try:
        first = s.event("npc", source="betrayal-a", dimension="betrayal", meaning_delta=0.45,
                        relevance=0.8, emotion_profile={"anger": 0.8}, consequence=-0.5)
        second = s.event("npc", source="betrayal-b", dimension="betrayal", meaning_delta=0.45,
                         relevance=0.8, emotion_profile={"fear": 0.6}, consequence=-0.5)
        before = s.observe("npc")
        ambiguous = s.recall_dimension("npc", "betrayal", 0.5)
        after = s.observe("npc")
        exact = s.recall_episode(second["episode_id"], 0.5)
        return {
            "checks": {
                "episode_ids_are_distinct": first["episode_id"] != second["episode_id"],
                "dimension_lookup_is_ambiguous": ambiguous["status"] == "ambiguous" and ambiguous["candidate_count"] == 2,
                "ambiguous_dimension_recall_does_not_mutate_hot_state": after == before,
                "exact_second_recall_uses_second_episode_affect": exact["record"]["emotion_profile"] == {"fear": 0.6},
            },
            "measures": {"candidate_count": ambiguous["candidate_count"]},
        }
    finally:
        s.close()


def _scenario_revision(factory, root: Path, label: str) -> dict:
    s = factory(root, label)
    try:
        row = s.event("npc", source="betrayal-1", dimension="betrayal", meaning_delta=0.9,
                      relevance=0.9, emotion_profile={"anger": 0.8}, consequence=-1.0)
        _tick(s, "npc", 12)
        before = s.observe("npc")
        s.revise("npc", "betrayal", -0.85)
        revised = s.observe("npc")
        meaning_after_revision = revised["meaning"]["betrayal"]
        trust_after_revision = revised["trust"]
        affect_after_revision = deepcopy(revised["emotion"])
        s.recall_episode(row["episode_id"], 0.8)
        recalled = s.observe("npc")
        return {
            "checks": {
                "meaning_revises_down": meaning_after_revision < before["meaning"]["betrayal"] * 0.10,
                "consequence_does_not_rewind": abs(trust_after_revision - before["trust"]) <= EPS,
                "affect_does_not_rewind_instantly": affect_after_revision == before["emotion"],
                "old_episode_recall_does_not_restore_old_meaning": abs(recalled["meaning"]["betrayal"] - meaning_after_revision) <= EPS,
            },
            "measures": {"meaning_after_revision": meaning_after_revision},
        }
    finally:
        s.close()


def _scenario_snapshot(factory, root: Path, label: str) -> dict:
    s = factory(root, label)
    row = s.event("npc", source="betrayal-1", dimension="betrayal", meaning_delta=0.9,
                  relevance=0.9, emotion_profile={"anger": 0.8}, consequence=-1.0)
    snap = s.snapshot()
    before = s.observe("npc")
    s.close()
    restored = factory(root, label, snapshot=snap)
    wrong_rejected = False
    try:
        restored_state = restored.observe("npc")
        recalled = restored.recall_episode(row["episode_id"], 0.6)
        wrong = factory(root, label + "-wrong")
        try:
            try:
                factory(root, label + "-wrong", snapshot=snap)
            except ArchiveMismatchError:
                wrong_rejected = True
        finally:
            wrong.close()
        encoded = json.dumps(snap, sort_keys=True)
        return {
            "checks": {
                "hot_snapshot_excludes_episode_payloads": "emotion_profile" not in encoded and "source" not in encoded,
                "snapshot_contains_archive_manifest": snap["episode_archive"]["record_count"] == 1,
                "matching_archive_restores_exact_hot_state": restored_state == before,
                "wrong_archive_is_rejected": wrong_rejected,
                "exact_recall_works_after_restart": recalled["episode_id"] == row["episode_id"],
            },
            "measures": {"snapshot_bytes": len(_canonical_bytes(snap))},
        }
    finally:
        restored.close()


def _canonical_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _scenario_capacity(factory, root: Path, label: str) -> dict:
    s = factory(root, label, max_records=1)
    try:
        first = s.event("npc", source="one", dimension="betrayal", meaning_delta=0.5,
                        relevance=0.5, emotion_profile={"anger": 0.5}, consequence=-0.5)
        before = s.observe("npc")
        failed = False
        try:
            s.event("npc", source="two", dimension="respect", meaning_delta=0.6,
                    relevance=0.6, emotion_profile={"hope": 0.5}, consequence=0.5)
        except CapacityBackpressureError:
            failed = True
        after = s.observe("npc")
        return {
            "checks": {
                "capacity_failure_is_explicit": failed,
                "existing_episode_survives": s.get_episode(first["episode_id"]) is not None,
                "archive_count_does_not_change": after["episode_count"] == 1,
                "failed_event_does_not_partially_mutate_hot_state": after == before,
            },
            "measures": {"archive_count": after["episode_count"]},
        }
    finally:
        s.close()


def _scenario_near_tie(factory, root: Path, label: str) -> dict:
    first_system = factory(root, label + "-first")
    second_system = factory(root, label + "-second")
    try:
        first = first_system.near_tie_trace(100)
        second = second_system.near_tie_trace(100)
        flips = sum(a != b for a, b in zip(first, first[1:]))
        return {
            "checks": {
                "alternating_near_tie_does_not_flip": flips == 0,
                "trace_is_deterministic": first == second,
            },
            "measures": {"flips": flips},
        }
    finally:
        first_system.close()
        second_system.close()


def _scenario_isolation(factory, root: Path, label: str) -> dict:
    s = factory(root, label)
    try:
        s.event("other", source="respect-other", dimension="respect", meaning_delta=0.6,
                relevance=0.5, emotion_profile={"hope": 0.4}, consequence=0.4)
        other_before = s.observe("other")
        s.event("npc", source="betrayal-npc", dimension="betrayal", meaning_delta=0.9,
                relevance=0.9, emotion_profile={"anger": 0.8}, consequence=-1.0)
        _tick(s, "npc", 8)
        s.recall_episode(s.episodes_for_dimension("npc", "betrayal")[0]["episode_id"], 0.7)
        other_after = s.observe("other")
        return {
            "checks": {
                "other_agent_meaning_unchanged": other_after["meaning"] == other_before["meaning"],
                "other_agent_relevance_unchanged": other_after["activation"] == other_before["activation"],
                "other_agent_affect_unchanged": other_after["emotion"] == other_before["emotion"],
                "other_agent_consequence_unchanged": abs(other_after["trust"] - other_before["trust"]) <= EPS,
            },
            "measures": {},
        }
    finally:
        s.close()


def _scenario_long_history(factory, root: Path, label: str) -> dict:
    s = factory(root, label)
    try:
        old = s.event("npc", source="old-betrayal", dimension="betrayal", meaning_delta=0.2,
                      relevance=0.8, emotion_profile={"anger": 0.9}, consequence=-0.2)
        for index in range(200):
            dimension = "respect" if index % 2 == 0 else "threat"
            profile = {"hope": 0.2} if dimension == "respect" else {"fear": 0.2}
            s.event("npc", source=f"noise-{index}", dimension=dimension, meaning_delta=0.001,
                    relevance=0.2, emotion_profile=profile, consequence=0.0)
            s.tick("npc", 1)
        before = s.observe("npc")
        old_record = s.get_episode(old["episode_id"])
        result = s.recall_episode(old["episode_id"], 0.9)
        after = s.observe("npc")
        other_changes = [
            dim for dim in before["activation"]
            if dim != "betrayal" and abs(after["activation"].get(dim, 0.0) - before["activation"].get(dim, 0.0)) > EPS
        ]
        return {
            "checks": {
                "old_episode_still_exists": old_record is not None,
                "old_episode_profile_is_exact": old_record["emotion_profile"] == {"anger": 0.9},
                "old_exact_recall_does_not_change_meaning": result["meaning_unchanged"],
                "old_exact_recall_raises_only_target_dimension": after["activation"]["betrayal"] > before["activation"]["betrayal"] and not other_changes,
                "all_history_remains_counted": after["episode_count"] == 201,
            },
            "measures": {"history_count": after["episode_count"]},
        }
    finally:
        s.close()


def _scenario_episode_affect(factory, root: Path, label: str) -> dict:
    s = factory(root, label)
    try:
        old = s.event("npc", source="old", dimension="betrayal", meaning_delta=0.3,
                      relevance=0.7, emotion_profile={"anger": 0.9}, consequence=-0.2)
        s.tick("npc", 40)
        new = s.event("npc", source="new", dimension="betrayal", meaning_delta=0.3,
                      relevance=0.7, emotion_profile={"fear": 0.9}, consequence=-0.2)
        s.tick("npc", 40)
        meaning_before = deepcopy(s.observe("npc")["meaning"])
        old_before = s.observe("npc")
        s.recall_episode(old["episode_id"], 0.9)
        old_after = s.observe("npc")
        old_anger_gain = old_after["emotion"]["anger"] - old_before["emotion"]["anger"]
        old_fear_gain = old_after["emotion"]["fear"] - old_before["emotion"]["fear"]
        s.tick("npc", 40)
        new_before = s.observe("npc")
        s.recall_episode(new["episode_id"], 0.9)
        new_after = s.observe("npc")
        new_fear_gain = new_after["emotion"]["fear"] - new_before["emotion"]["fear"]
        new_anger_gain = new_after["emotion"]["anger"] - new_before["emotion"]["anger"]
        return {
            "checks": {
                "older_exact_recall_prefers_older_affect": old_anger_gain > old_fear_gain + EPS,
                "newer_exact_recall_prefers_newer_affect": new_fear_gain > new_anger_gain + EPS,
                "older_and_newer_ids_remain_distinct": old["episode_id"] != new["episode_id"],
                "meaning_is_unchanged_by_both_recalls": new_after["meaning"] == meaning_before,
            },
            "measures": {"old_specificity": old_anger_gain - old_fear_gain, "new_specificity": new_fear_gain - new_anger_gain},
        }
    finally:
        s.close()


def _recall_load(factory, root: Path, label: str, repeated: bool) -> dict:
    s = factory(root, label)
    try:
        row = s.event("npc", source="betrayal", dimension="betrayal", meaning_delta=0.9,
                      relevance=0.9, emotion_profile={"anger": 0.75, "grief": 0.65}, consequence=-1.0)
        s.tick("npc", 32)
        relevance = 0.0
        affect = 0.0
        for tick in range(24):
            if tick == 0 or (repeated and tick % 4 == 0):
                s.recall_episode(row["episode_id"], 0.7)
            state = s.observe("npc")
            relevance += state["activation"]["betrayal"]
            affect += _max_affect(state)
            s.tick("npc", 1)
        return {"relevance": relevance, "affect": affect}
    finally:
        s.close()


def _scenario_recall_load(factory, root: Path, label: str) -> dict:
    single = _recall_load(factory, root, label + "-single", False)
    repeated = _recall_load(factory, root, label + "-repeated", True)
    return {
        "checks": {
            "repeated_recall_increases_relevance_load": repeated["relevance"] > single["relevance"] + EPS,
            "repeated_recall_increases_affect_load": repeated["affect"] > single["affect"] + EPS,
        },
        "measures": {"single": single, "repeated": repeated},
    }


def _scenario_stale(factory, root: Path, label: str) -> dict:
    s = factory(root, label)
    try:
        old = s.event("npc", source="betrayal-old", dimension="betrayal", meaning_delta=0.9,
                      relevance=1.0, emotion_profile={"anger": 1.0}, consequence=-1.0)
        s.tick("npc", 24)
        for index in range(30):
            s.event("npc", source=f"respect-{index}", dimension="respect", meaning_delta=0.002,
                    relevance=0.25, emotion_profile={"hope": 0.1}, consequence=0.02)
            s.tick("npc", 1)
        before = s.observe("npc")
        s.recall_episode(old["episode_id"], 0.95)
        after = s.observe("npc")
        return {
            "checks": {
                "recent_concern_can_displace_old_concern": before["foreground"] == "respect",
                "old_meaning_is_not_erased": before["meaning"]["betrayal"] > 0.8,
                "old_relevance_becomes_small": before["activation"]["betrayal"] < 1e-6,
                "exact_old_recall_can_restore_old_relevance": after["activation"]["betrayal"] > 0.9,
            },
            "measures": {"old_relevance_before_recall": before["activation"]["betrayal"]},
        }
    finally:
        s.close()


def _scenario_restart(factory, root: Path, label: str) -> dict:
    s = factory(root, label)
    first = s.event("npc", source="one", dimension="betrayal", meaning_delta=0.6,
                    relevance=0.8, emotion_profile={"anger": 0.6}, consequence=-0.5)
    second = s.event("npc", source="two", dimension="respect", meaning_delta=0.6,
                     relevance=0.8, emotion_profile={"hope": 0.6}, consequence=0.5)
    initial_state = s.observe("npc")
    initial_manifest = s.archive_manifest()
    ids = [first["episode_id"], second["episode_id"]]
    for _ in range(20):
        snap = s.snapshot()
        s.close()
        s = factory(root, label, snapshot=snap)
    try:
        final_state = s.observe("npc")
        final_manifest = s.archive_manifest()
        final_ids = [row["episode_id"] for dim in ("betrayal", "respect") for row in s.episodes_for_dimension("npc", dim)]
        return {
            "checks": {
                "hot_state_survives_twenty_restarts": final_state == initial_state,
                "archive_manifest_survives_twenty_restarts": final_manifest == initial_manifest,
                "episode_ids_survive_twenty_restarts": sorted(final_ids) == sorted(ids),
                "restart_cycles_do_not_duplicate_episodes": final_state["episode_count"] == 2,
            },
            "measures": {"restart_count": 20},
        }
    finally:
        s.close()


def _scenario_duplication(factory, root: Path, label: str) -> dict:
    s = factory(root, label)
    try:
        row = s.event("npc", source="betrayal", dimension="betrayal", meaning_delta=0.9,
                      relevance=0.9, emotion_profile={"anger": 0.8}, consequence=-1.0)
        before = s.observe("npc")
        for _ in range(100):
            s.recall_episode(row["episode_id"], 0.2)
            s.tick("npc", 1)
        after = s.observe("npc")
        return {
            "checks": {
                "one_hundred_recalls_do_not_change_consequence": abs(after["trust"] - before["trust"]) <= EPS,
                "one_hundred_recalls_do_not_duplicate_episode": after["episode_count"] == before["episode_count"] == 1,
                "one_hundred_recalls_do_not_rewrite_meaning": after["meaning"] == before["meaning"],
            },
            "measures": {},
        }
    finally:
        s.close()


def _scenario_revision_recall(factory, root: Path, label: str) -> dict:
    s = factory(root, label)
    try:
        row = s.event("npc", source="betrayal", dimension="betrayal", meaning_delta=0.9,
                      relevance=0.9, emotion_profile={"grief": 0.9}, consequence=-1.0)
        s.tick("npc", 20)
        s.revise("npc", "betrayal", -0.85)
        revised = s.observe("npc")
        s.tick("npc", 20)
        before = s.observe("npc")
        s.recall_episode(row["episode_id"], 0.9)
        after = s.observe("npc")
        return {
            "checks": {
                "revised_meaning_stays_revised": abs(after["meaning"]["betrayal"] - revised["meaning"]["betrayal"]) <= EPS,
                "old_episode_can_become_relevant_again": after["activation"]["betrayal"] > before["activation"]["betrayal"] + 0.8,
                "old_recall_does_not_rewind_consequence": abs(after["trust"] - before["trust"]) <= EPS,
                "old_recall_uses_historical_episode_affect": after["emotion"]["grief"] > before["emotion"]["grief"] + EPS,
            },
            "measures": {},
        }
    finally:
        s.close()


def _scenario_large_ambiguity(factory, root: Path, label: str) -> dict:
    s = factory(root, label)
    try:
        for index in range(50):
            s.event("npc", source=f"betrayal-{index}", dimension="betrayal", meaning_delta=0.01,
                    relevance=0.1, emotion_profile={"anger": 0.01}, consequence=0.0)
            s.tick("npc", 1)
        before = s.observe("npc")
        result = s.recall_dimension("npc", "betrayal", 1.0)
        after = s.observe("npc")
        return {
            "checks": {
                "fifty_same_dimension_episodes_are_reported_ambiguous": result["status"] == "ambiguous" and result["candidate_count"] == 50,
                "ambiguous_recall_leaves_meaning_unchanged": after["meaning"] == before["meaning"],
                "ambiguous_recall_leaves_relevance_unchanged": after["activation"] == before["activation"],
                "ambiguous_recall_leaves_affect_unchanged": after["emotion"] == before["emotion"],
            },
            "measures": {"candidate_count": result["candidate_count"]},
        }
    finally:
        s.close()


_SCENARIO_FUNCS = {
    "moving_on_without_erasure": _scenario_moving,
    "exact_recall_without_replay": _scenario_recall,
    "same_dimension_identity_and_ambiguity": _scenario_identity,
    "revision_without_rewind": _scenario_revision,
    "snapshot_archive_pairing": _scenario_snapshot,
    "capacity_no_silent_eviction": _scenario_capacity,
    "near_tie_hysteresis": _scenario_near_tie,
    "multi_agent_isolation": _scenario_isolation,
    "long_history_selective_old_recall": _scenario_long_history,
    "same_dimension_episode_specific_affect": _scenario_episode_affect,
    "repeated_recall_load": _scenario_recall_load,
    "stale_dominance_resistance": _scenario_stale,
    "repeated_restart_stability": _scenario_restart,
    "causal_duplication_torture": _scenario_duplication,
    "revision_then_old_recall": _scenario_revision_recall,
    "large_ambiguity_safety": _scenario_large_ambiguity,
}


def run_frozen_suite(factory, root: Path, run_label: str) -> dict:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    scenarios = {}
    classes = {}
    categories: dict[str, dict[str, int]] = {}
    for spec in scenario_manifest():
        scenario_id = spec["id"]
        result = _SCENARIO_FUNCS[scenario_id](factory, root, f"{run_label}-{scenario_id}")
        if tuple(result["checks"]) != tuple(spec["checks"]):
            raise AssertionError(f"scenario check contract drifted: {scenario_id}")
        scenarios[scenario_id] = deepcopy(result)
        classes[scenario_id] = spec["class"]
        for category in spec["categories"]:
            bucket = categories.setdefault(category, {"passes": 0, "total": 0})
            for passed in result["checks"].values():
                bucket["total"] += 1
                bucket["passes"] += int(bool(passed))

    competence_checks = [
        passed
        for scenario_id, result in scenarios.items()
        if classes[scenario_id] == "competence"
        for passed in result["checks"].values()
    ]
    discriminator_checks = [
        passed
        for scenario_id, result in scenarios.items()
        if classes[scenario_id] == "discriminator"
        for passed in result["checks"].values()
    ]
    deterministic_payload = {
        "scenarios": scenarios,
        "classes": classes,
        "categories": categories,
    }
    return {
        "scenario_count": len(scenarios),
        "competence": {"passes": sum(map(bool, competence_checks)), "total": len(competence_checks)},
        "discriminators": {"passes": sum(map(bool, discriminator_checks)), "total": len(discriminator_checks)},
        "all_checks": {
            "passes": sum(bool(v) for result in scenarios.values() for v in result["checks"].values()),
            "total": sum(len(result["checks"]) for result in scenarios.values()),
        },
        "categories": categories,
        "scenarios": scenarios,
        "deterministic_digest": _digest(deterministic_payload),
    }
