from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from ghost.api import GhostAPI
from ghost.continuity import PairwiseForeground
from ghost.episode_store import SQLiteEpisodeArchive


EPS = 1e-12


def _digest(value):
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ProductionContinuityFixture:
    def __init__(self, api: GhostAPI, store: SQLiteEpisodeArchive, belief: dict):
        self.api = api
        self.store = store
        self.belief = belief

    def close(self) -> None:
        self.store.close()

    def betrayal(self) -> dict:
        self.api.apply_event("a", "b", {"type": "betrayal", "intensity": 1.0})
        return self.api.continuity_event(
            "b",
            "observe",
            features={"betrayal_cue": 1.0},
            source="production_m3_betrayal",
            emotion_event="production_m3_betrayal",
            emotion_impulses={"anger": 0.75, "grief": 0.65, "fear": 0.35},
            signals={"interpretation_impulse": 0.90, "threat": 0.70},
        )

    def respect(self) -> dict:
        return self.api.continuity_event(
            "b",
            "observe",
            features={"respect_cue": 1.0},
            source="production_m3_respect",
            signals={"interpretation_impulse": 0.85},
        )

    def threat(self) -> dict:
        return self.api.continuity_event(
            "b",
            "observe",
            features={"threat_cue": 1.0},
            source="production_m3_threat",
            signals={"interpretation_impulse": 0.70, "threat": 0.70},
        )

    def exonerate(self) -> dict:
        return self.api.continuity_event(
            "b",
            "observe",
            features={"exoneration": 1.0},
            source="production_m3_exoneration",
            signals={"interpretation_impulse": 0.95, "contradiction": 0.95},
        )

    def recall(self, dimension: str, strength: float) -> dict:
        return self.api.recall_dimension("b", dimension, strength)

    def help(self, count: int = 1) -> None:
        for _ in range(count):
            self.api.apply_event("a", "b", {"type": "help", "intensity": 1.0})
        self.api.advance_attention_from_state("b", signals={})

    def empty_tick(self) -> None:
        self.api.continuity_tick("b")

    def observe(self) -> dict:
        continuity = self.api.continuity_state("b") or {
            "activation": {},
            "current_leader": None,
        }
        belief_dim = self.belief["dimensions"]["default"]
        return {
            "focus": continuity["current_leader"],
            "meaning": copy.deepcopy(self.api.interpretation_state("b")["levels"]),
            "activation": copy.deepcopy(continuity["activation"]),
            "emotion": copy.deepcopy(self.api.emotional_state("b")["levels"]),
            "relationship_trust": self.api.get_relationship("a", "b")["trust"],
            "belief_conflict": belief_dim["dominant_candidate"] == "true",
        }


def _factory(tmp_path: Path, label: str) -> ProductionContinuityFixture:
    store = SQLiteEpisodeArchive(tmp_path / f"{label}.sqlite")
    api = GhostAPI(episode_store=store)
    for _ in range(24):
        api.apply_event("a", "b", {"type": "help", "intensity": 1.0})
    api.register_emotional_agent(
        "b",
        initial={"anger": 0.05, "grief": 0.05, "fear": 0.02, "hope": 0.15},
        baseline={"anger": 0.05, "grief": 0.05, "fear": 0.02, "hope": 0.15},
        inertia={"anger": 0.88, "grief": 0.94, "fear": 0.86, "hope": 0.92},
    )
    api.register_interpretation_agent(
        "b",
        initial={"betrayal": 0.0, "respect": 0.0, "threat": 0.0},
    )
    for feature, impulses in (
        ("betrayal_cue", {"betrayal": 0.90}),
        ("respect_cue", {"respect": 0.85}),
        ("threat_cue", {"threat": 0.70}),
        ("exoneration", {"betrayal": -0.95}),
    ):
        api.configure_interpretation_rule("b", feature, impulses)
    api.register_attention_agent("b", initial_flow_pressure=0.0, flow_active=False)
    api.record_fact(
        fact_id="door_locked_fact",
        source="world",
        subject="door",
        predicate="locked",
        object="false",
    )
    belief = api.evaluate_beliefs(
        holder="b",
        subject="door",
        candidates={"true": 3.0, "false": 1.0},
        provenance={"fixture": "production_m3"},
    )
    return ProductionContinuityFixture(api, store, belief)


def _ticks(system: ProductionContinuityFixture, count: int) -> None:
    for _ in range(count):
        system.empty_tick()


def _max_memory_emotion(state: dict) -> float:
    return max(state["emotion"].get(name, 0.0) for name in ("anger", "grief", "fear"))


def _grudge_trace(tmp_path: Path, label: str, repeated: bool) -> dict:
    system = _factory(tmp_path, label)
    try:
        system.betrayal()
        _ticks(system, 32)
        relevance_sum = 0.0
        emotion_sum = 0.0
        for tick in range(24):
            if tick == 0 or (repeated and tick % 4 == 0):
                system.recall("betrayal", 0.70)
            state = system.observe()
            relevance_sum += state["activation"].get("betrayal", 0.0)
            emotion_sum += _max_memory_emotion(state)
            system.empty_tick()
        return {"relevance_sum": relevance_sum, "emotion_sum": emotion_sum}
    finally:
        system.close()


def _run_suite(tmp_path: Path, run_label: str) -> dict:
    scenarios = {}

    s = _factory(tmp_path, f"{run_label}_moving")
    try:
        s.betrayal()
        fresh = s.observe()
        _ticks(s, 12)
        moved = s.observe()
        checks = {
            "fresh_focus_is_betrayal": fresh["focus"] == "interpretation:betrayal",
            "betrayal_meaning_persists": moved["meaning"]["betrayal"] >= fresh["meaning"]["betrayal"] - EPS,
            "current_betrayal_relevance_falls": moved["activation"].get("betrayal", 0.0) < fresh["activation"].get("betrayal", 0.0) * 0.01,
            "foreground_moves_off_betrayal": moved["focus"] != "interpretation:betrayal",
            "associated_emotion_relaxes": _max_memory_emotion(moved) < _max_memory_emotion(fresh),
        }
        scenarios["moving_on"] = checks
    finally:
        s.close()

    s = _factory(tmp_path, f"{run_label}_recall")
    try:
        s.betrayal()
        _ticks(s, 32)
        before = s.observe()
        s.recall("betrayal", 0.70)
        after = s.observe()
        complex_names = {
            "interpretation:betrayal", "emotion:anger", "emotion:grief", "emotion:fear"
        }
        scenarios["recall"] = {
            "was_moved_off_before_recall": before["focus"] != "interpretation:betrayal",
            "recall_does_not_change_meaning": abs(after["meaning"]["betrayal"] - before["meaning"]["betrayal"]) <= EPS,
            "recall_raises_current_relevance": after["activation"].get("betrayal", 0.0) > before["activation"].get("betrayal", 0.0) + 0.50,
            "recall_changes_observable_foreground_to_betrayal_complex": after["focus"] in complex_names and after["focus"] != before["focus"],
            "recall_reactivates_associated_emotion": any(after["emotion"].get(name, 0.0) > before["emotion"].get(name, 0.0) + EPS for name in ("anger", "grief", "fear")),
        }
    finally:
        s.close()

    s = _factory(tmp_path, f"{run_label}_reappraisal")
    try:
        s.betrayal(); _ticks(s, 12); s.recall("betrayal", 0.70)
        before = s.observe(); s.exonerate(); after = s.observe()
        scenarios["reappraisal"] = {
            "meaning_revised_down": after["meaning"]["betrayal"] < before["meaning"]["betrayal"] * 0.10,
            "situation_can_remain_currently_active": after["activation"].get("betrayal", 0.0) > 0.90,
            "relationship_not_rewound_instantly": abs(after["relationship_trust"] - before["relationship_trust"]) <= EPS,
            "emotion_not_rewound_instantly": all(abs(after["emotion"].get(name, 0.0) - before["emotion"].get(name, 0.0)) <= EPS for name in before["emotion"]),
        }
    finally:
        s.close()

    s = _factory(tmp_path, f"{run_label}_forgive")
    try:
        s.betrayal(); post = s.observe(); _ticks(s, 12); s.help(40); after = s.observe()
        scenarios["forgive_not_forget"] = {
            "relationship_can_improve": after["relationship_trust"] > post["relationship_trust"],
            "betrayal_meaning_not_erased_by_help": after["meaning"]["betrayal"] >= post["meaning"]["betrayal"] - EPS,
            "betrayal_need_not_dominate_current_foreground": after["focus"] != "interpretation:betrayal",
        }
    finally:
        s.close()

    single = _grudge_trace(tmp_path, f"{run_label}_grudge_single", False)
    repeated = _grudge_trace(tmp_path, f"{run_label}_grudge_repeated", True)
    scenarios["grudge"] = {
        "repeated_recall_increases_betrayal_relevance_load": repeated["relevance_sum"] > single["relevance_sum"] + EPS,
        "repeated_recall_increases_associated_emotional_load": repeated["emotion_sum"] > single["emotion_sum"] + EPS,
    }

    s = _factory(tmp_path, f"{run_label}_competing")
    try:
        s.betrayal(); _ticks(s, 12); s.respect(); respect = s.observe(); _ticks(s, 2); s.recall("betrayal", 1.0); recalled = s.observe()
        scenarios["competing_concerns"] = {
            "new_respect_concern_can_take_foreground": respect["focus"] == "interpretation:respect",
            "old_betrayal_can_return_on_selective_recall": recalled["focus"] == "interpretation:betrayal",
            "both_meanings_remain_available": recalled["meaning"].get("betrayal", 0.0) > 0.0 and recalled["meaning"].get("respect", 0.0) > 0.0,
        }
    finally:
        s.close()

    s = _factory(tmp_path, f"{run_label}_silence")
    try:
        s.betrayal(); fresh = s.observe(); _ticks(s, 64); final = s.observe()
        scenarios["long_silence"] = {
            "meaning_survives_long_silence": final["meaning"]["betrayal"] >= fresh["meaning"]["betrayal"] - EPS,
            "current_relevance_nearly_gone": final["activation"].get("betrayal", 0.0) < 1e-8,
            "foreground_not_stale_betrayal": final["focus"] != "interpretation:betrayal",
            "emotion_returns_near_baseline": _max_memory_emotion(final) < 0.08,
        }
    finally:
        s.close()

    s = _factory(tmp_path, f"{run_label}_threat")
    try:
        s.threat(); fresh = s.observe(); _ticks(s, 12); quiet = s.observe(); s.recall("threat", 0.90); recalled = s.observe()
        scenarios["threat_generalization"] = {
            "fresh_threat_is_foreground": fresh["focus"] == "interpretation:threat",
            "threat_meaning_persists": quiet["meaning"]["threat"] >= fresh["meaning"]["threat"] - EPS,
            "threat_can_move_out_of_current_foreground": quiet["focus"] != "interpretation:threat",
            "threat_recall_restores_current_focus": recalled["focus"] == "interpretation:threat",
            "threat_recall_does_not_change_meaning": abs(recalled["meaning"]["threat"] - quiet["meaning"]["threat"]) <= EPS,
        }
    finally:
        s.close()

    s = _factory(tmp_path, f"{run_label}_conflict")
    try:
        before = s.observe(); s.betrayal(); _ticks(s, 12); s.recall("betrayal", 0.70); after = s.observe()
        scenarios["conflict_preservation"] = {
            "truth_belief_conflict_present_initially": before["belief_conflict"],
            "truth_belief_conflict_survives_unrelated_continuity_events": after["belief_conflict"],
        }
    finally:
        s.close()

    switch = PairwiseForeground(0.05)
    leaders = []
    for tick in range(100):
        values = (
            {"emotion:anger": 0.5001, "interpretation:threat": 0.4999}
            if tick % 2 == 0
            else {"emotion:anger": 0.4999, "interpretation:threat": 0.5001}
        )
        leaders.append(switch.step(tick, values)["resolved_leader"])
    flips = sum(left != right for left, right in zip(leaders, leaders[1:]))
    scenarios["near_tie"] = {"pass": flips == 0}

    failed = [f"{scenario}.{name}" for scenario, checks in scenarios.items() for name, passed in checks.items() if not passed]
    return {
        "scenario_passes": sum(all(checks.values()) for checks in scenarios.values()),
        "scenario_total": len(scenarios),
        "check_passes": sum(bool(passed) for checks in scenarios.values() for passed in checks.values()),
        "check_total": sum(len(checks) for checks in scenarios.values()),
        "failed_checks": failed,
        "scenarios": scenarios,
    }


def test_production_m3q_value_gate_is_10_of_10_34_of_34_and_deterministic(tmp_path):
    first = _run_suite(tmp_path, "run1")
    second = _run_suite(tmp_path, "run2")
    assert first["scenario_total"] == 10
    assert first["scenario_passes"] == 10
    assert first["check_total"] == 34
    assert first["check_passes"] == 34
    assert first["failed_checks"] == []
    assert _digest(first["scenarios"]) == _digest(second["scenarios"])
