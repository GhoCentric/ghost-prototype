"""Architecture-neutral continuity-to-behavior scenarios for Stage 6."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from .ghost_adapter import GhostContinuityAdapter
from .purpose_built import PurposeBuiltContinuity
from .stage6_behavior_policy import (
    behavior_distance,
    behavior_scores,
    behavior_signature,
    robust,
    seeded_float,
    seeded_int,
)

EPS = 1e-12


def factory(kind: str, root: Path, label: str, *, snapshot: dict | None = None):
    root.mkdir(parents=True, exist_ok=True)
    if kind == "baseline":
        return PurposeBuiltContinuity(root / f"{label}.sqlite", snapshot=snapshot)
    if kind == "ghost":
        return GhostContinuityAdapter(root / f"{label}.sqlite", snapshot=snapshot)
    raise ValueError(f"unknown contestant: {kind}")


def event(system, source: str, dimension: str, delta: float, emotion=None, consequence: float = 0.0):
    return system.event(
        "npc",
        source=source,
        dimension=dimension,
        meaning_delta=delta,
        relevance=abs(delta),
        emotion_profile={} if emotion is None else emotion,
        consequence=consequence,
    )


def relevant_history_retention(kind: str, root: Path) -> dict:
    left = factory(kind, root, f"{kind}-relevant-left")
    right = factory(kind, root, f"{kind}-relevant-right")
    try:
        betrayal = seeded_float("relevant:betrayal", .55, .78)
        positive_history = seeded_float("relevant:positive_history", .20, .32)
        respect = seeded_float("relevant:respect", .018, .032)
        old_ticks = seeded_int("relevant:old_ticks", 28, 42)
        support_count = seeded_int("relevant:support_count", 10, 16)
        event(left, "old-betrayal", "betrayal", betrayal, {"anger": .75}, -.7)
        event(right, "old-respect", "respect", positive_history, {"hope": .65}, .7)
        left.tick("npc", old_ticks); right.tick("npc", old_ticks)
        for index in range(support_count):
            event(left, f"support-{index}", "respect", respect, {"hope": .05}, .025)
            event(right, f"support-{index}", "respect", respect, {"hope": .05}, .025)
            left.tick("npc", 1); right.tick("npc", 1)
        left_state = left.observe("npc"); right_state = right.observe("npc")
        left_behavior = behavior_signature(left_state); right_behavior = behavior_signature(right_state)
        history = robust(lambda i: (
            behavior_scores(right_state, i)["cooperate"] > behavior_scores(left_state, i)["cooperate"] + .02
            and behavior_scores(left_state, i)["confront"] > behavior_scores(right_state, i)["confront"] + .02
        ))
        return {
            "checks": {
                "relevant_old_history_still_changes_behavior": history["passed"],
                "old_transient_activation_is_stale": left_state["activation"].get("betrayal", 0.0) < 1e-6,
            },
            "robust": history,
            "measures": {"behavior_distance": behavior_distance(left_behavior, right_behavior)},
        }
    finally:
        left.close(); right.close()


def irrelevant_history_convergence(kind: str, root: Path) -> dict:
    noisy = factory(kind, root, f"{kind}-irrelevant-noisy")
    clean = factory(kind, root, f"{kind}-irrelevant-clean")
    try:
        for index in range(seeded_int("irrelevant:count", 40, 70)):
            event(noisy, f"weather-{index}", "weather", .003); noisy.tick("npc", 1)
        for system in (noisy, clean):
            for index in range(8):
                event(system, f"support-{index}", "respect", .045, {"hope": .06}, .03)
                system.tick("npc", 1)
        noisy_behavior = behavior_signature(noisy.observe("npc")); clean_behavior = behavior_signature(clean.observe("npc"))
        distance = behavior_distance(noisy_behavior, clean_behavior)
        return {"checks": {"irrelevant_history_does_not_change_behavior": distance < .015},
                "measures": {"behavior_distance": distance}}
    finally:
        noisy.close(); clean.close()


def threat_override_and_recovery(kind: str, root: Path) -> dict:
    system = factory(kind, root, f"{kind}-threat")
    try:
        for index in range(seeded_int("threat:support_count", 6, 10)):
            event(system, f"support-{index}", "respect", .06, {"hope": .08}, .05); system.tick("npc", 1)
        before = behavior_signature(system.observe("npc"))
        event(system, "credible-threat", "threat", seeded_float("threat:delta", .65, .82), {"fear": .85}, -.05)
        hot = behavior_signature(system.observe("npc"))
        system.tick("npc", seeded_int("threat:decay", 28, 38))
        recovered = behavior_signature(system.observe("npc"))
        override = robust(lambda i: hot["states"][i]["guard"] > hot["states"][i]["cooperate"] + .03)
        rise = robust(lambda i: hot["states"][i]["guard"] > before["states"][i]["guard"] + .08)
        recovery = robust(lambda i: recovered["states"][i]["cooperate"] > recovered["states"][i]["guard"] + .01)
        return {"checks": {
                    "active_threat_overrides_cooperation": override["passed"],
                    "defensive_response_rises_on_threat": rise["passed"],
                    "cooperation_recovers_after_threat_decays": recovery["passed"],
                }, "robust": {"override": override, "rise": rise, "recovery": recovery}, "measures": {}}
    finally:
        system.close()


def revision_without_consequence_rewind(kind: str, root: Path) -> dict:
    system = factory(kind, root, f"{kind}-revision")
    clean = factory(kind, root, f"{kind}-revision-clean")
    try:
        event(system, "false-betrayal", "betrayal", .75, {"anger": .75}, -.65)
        system.tick("npc", 18)
        before = behavior_signature(system.observe("npc"))
        system.revise("npc", "betrayal", -.65); system.tick("npc", 18)
        after_state = system.observe("npc"); after = behavior_signature(after_state)
        clean.tick("npc", 36); clean_behavior = behavior_signature(clean.observe("npc"))
        drop = robust(lambda i: after["states"][i]["confront"] < before["states"][i]["confront"] - .02)
        residue = robust(lambda i: max(after["states"][i][x] for x in ("guard", "withdraw", "confront")) >
                                   max(clean_behavior["states"][i][x] for x in ("guard", "withdraw", "confront")) + .025)
        return {"checks": {
                    "semantic_revision_reduces_hostility": drop["passed"],
                    "historical_consequence_still_affects_behavior": residue["passed"],
                    "revision_does_not_rewind_trust": after_state["trust"] < -.5,
                }, "robust": {"drop": drop, "residue": residue}, "measures": {}}
    finally:
        system.close(); clean.close()


def episode_specific_affect(kind: str, root: Path) -> dict:
    system = factory(kind, root, f"{kind}-episode-affect")
    try:
        angry = event(system, "angry-betrayal", "betrayal", .2, {"anger": .9}, -.1); system.tick("npc", 36)
        fearful = event(system, "fearful-betrayal", "betrayal", .2, {"fear": .9}, -.1); system.tick("npc", 36)
        base_state = system.observe("npc"); base = behavior_signature(base_state)
        system.recall_episode(angry["episode_id"], .9)
        angry_state = system.observe("npc"); angry_behavior = behavior_signature(angry_state)
        system.tick("npc", 36)
        pre_fear_state = system.observe("npc"); pre_fear = behavior_signature(pre_fear_state)
        system.recall_episode(fearful["episode_id"], .9)
        fear_state = system.observe("npc"); fear_behavior = behavior_signature(fear_state)
        angry_check = robust(lambda i: (
            angry_behavior["states"][i]["confront"] - base["states"][i]["confront"]
            > angry_behavior["states"][i]["guard"] - base["states"][i]["guard"] + .01
        ))
        fear_check = robust(lambda i: (
            max(fear_behavior["states"][i][x] for x in ("guard", "withdraw"))
            - max(pre_fear["states"][i][x] for x in ("guard", "withdraw"))
            > fear_behavior["states"][i]["confront"] - pre_fear["states"][i]["confront"] + .01
        ))
        no_fg_fear = robust(lambda i: (
            max(behavior_scores(fear_state, i, use_foreground=False)[x] for x in ("guard", "withdraw"))
            - max(behavior_scores(pre_fear_state, i, use_foreground=False)[x] for x in ("guard", "withdraw"))
            > behavior_scores(fear_state, i, use_foreground=False)["confront"]
            - behavior_scores(pre_fear_state, i, use_foreground=False)["confront"] + .01
        ))
        return {"checks": {
                    "angry_episode_recall_is_behaviorally_angrier": angry_check["passed"],
                    "fearful_episode_recall_is_behaviorally_more_defensive": fear_check["passed"],
                },
                "robust": {"angry": angry_check, "fear": fear_check},
                "ablation": {"fear_without_foreground": no_fg_fear},
                "measures": {"fear_foreground": fear_state["foreground"]}}
    finally:
        system.close()


def betrayal_affect_mode_resolution(kind: str, root: Path) -> dict:
    outputs = {}; systems = []
    try:
        for emotion_name in ("anger", "fear", "grief"):
            system = factory(kind, root, f"{kind}-betrayal-mode-{emotion_name}"); systems.append(system)
            row = event(
                system, f"betrayal-{emotion_name}", "betrayal",
                seeded_float(f"betrayal-mode:{emotion_name}:meaning", .10, .16),
                {emotion_name: seeded_float(f"betrayal-mode:{emotion_name}:emotion", .84, .94)}, -.08,
            )
            system.tick("npc", seeded_int(f"betrayal-mode:{emotion_name}:decay", 34, 42))
            system.recall_episode(row["episode_id"], seeded_float(f"betrayal-mode:{emotion_name}:recall", .86, .94))
            outputs[emotion_name] = system.observe("npc")
        full = {name: behavior_signature(state) for name, state in outputs.items()}
        anger = robust(lambda i: full["anger"]["states"][i]["confront"] >
                                 max(full["anger"]["states"][i][x] for x in ("guard", "withdraw")) + .01)
        fear = robust(lambda i: max(full["fear"]["states"][i][x] for x in ("guard", "withdraw")) >
                                full["fear"]["states"][i]["confront"] + .01)
        grief = robust(lambda i: full["grief"]["states"][i]["withdraw"] > full["grief"]["states"][i]["confront"] + .01)
        ablated = {
            name: behavior_signature(state, use_foreground=False) for name, state in outputs.items()
        }
        no_fg_fear = robust(lambda i: max(ablated["fear"]["states"][i][x] for x in ("guard", "withdraw")) >
                                      ablated["fear"]["states"][i]["confront"] + .01)
        no_fg_grief = robust(lambda i: ablated["grief"]["states"][i]["withdraw"] >
                                       ablated["grief"]["states"][i]["confront"] + .01)
        return {"checks": {
                    "anger_tagged_betrayal_recall_prefers_confrontation": anger["passed"],
                    "fear_tagged_betrayal_recall_prefers_defense": fear["passed"],
                    "grief_tagged_betrayal_recall_prefers_withdrawal": grief["passed"],
                },
                "robust": {"anger": anger, "fear": fear, "grief": grief},
                "ablation": {"fear_without_foreground": no_fg_fear, "grief_without_foreground": no_fg_grief},
                "measures": {name: {"foreground": state["foreground"]} for name, state in outputs.items()}}
    finally:
        for system in systems:
            system.close()


def ambiguous_recall_inertness(kind: str, root: Path) -> dict:
    system = factory(kind, root, f"{kind}-ambiguous")
    try:
        for index in range(seeded_int("ambiguous:count", 4, 8)):
            event(system, f"betrayal-{index}", "betrayal", .08,
                  {"anger": .15 if index % 2 == 0 else 0.0, "fear": .15 if index % 2 else 0.0}, -.01)
            system.tick("npc", 2)
        before_state = deepcopy(system.observe("npc")); before = behavior_signature(before_state)
        result = system.recall_dimension("npc", "betrayal", .95)
        after_state = deepcopy(system.observe("npc")); after = behavior_signature(after_state)
        return {"checks": {
                    "ambiguous_recall_reports_ambiguity": result["status"] == "ambiguous",
                    "ambiguous_recall_does_not_change_behavior": before == after,
                    "ambiguous_recall_does_not_change_hot_observation": before_state == after_state,
                }, "measures": {"candidate_count": result.get("candidate_count")}}
    finally:
        system.close()


def reactivation_is_transient_not_replay(kind: str, root: Path) -> dict:
    system = factory(kind, root, f"{kind}-reactivation")
    try:
        row = event(system, "old-betrayal", "betrayal", .55, {"fear": .7, "anger": .3}, -.45)
        system.tick("npc", 48)
        before_state = system.observe("npc"); before = behavior_signature(before_state); trust = before_state["trust"]
        system.recall_episode(row["episode_id"], .9)
        hot_state = system.observe("npc"); hot = behavior_signature(hot_state)
        system.tick("npc", 42); cooled = behavior_signature(system.observe("npc"))
        rise = robust(lambda i: max(hot["states"][i][x] for x in ("guard", "confront", "withdraw")) >
                                max(before["states"][i][x] for x in ("guard", "confront", "withdraw")) + .04)
        cool = robust(lambda i: abs(cooled["states"][i]["guard"] - before["states"][i]["guard"]) < .06
                               and abs(cooled["states"][i]["confront"] - before["states"][i]["confront"]) < .06)
        return {"checks": {
                    "exact_recall_temporarily_changes_behavior": rise["passed"],
                    "recall_does_not_duplicate_consequence": abs(hot_state["trust"] - trust) < EPS,
                    "reactivated_behavior_cools_again": cool["passed"],
                }, "robust": {"rise": rise, "cool": cool}, "measures": {}}
    finally:
        system.close()


def restart_behavior_identity(kind: str, root: Path) -> dict:
    system = factory(kind, root, f"{kind}-restart"); restored = None
    try:
        event(system, "betrayal", "betrayal", .4, {"anger": .5}, -.3); system.tick("npc", 7)
        event(system, "respect", "respect", .3, {"hope": .45}, .2); system.tick("npc", 5)
        before_state = system.observe("npc"); before = behavior_signature(before_state); snapshot = system.snapshot()
        system.close(); system = None
        restored = factory(kind, root, f"{kind}-restart", snapshot=snapshot)
        after_state = restored.observe("npc"); after = behavior_signature(after_state)
        return {"checks": {
                    "restart_preserves_behavior_exactly": before == after,
                    "restart_preserves_common_observation": before_state == after_state,
                }, "measures": {}}
    finally:
        if system is not None:
            system.close()
        if restored is not None:
            restored.close()


def cross_layer_recent_affect_sensitivity(kind: str, root: Path) -> dict:
    hope_system = factory(kind, root, f"{kind}-cross-hope")
    fear_system = factory(kind, root, f"{kind}-cross-fear")
    try:
        for index in range(seeded_int("cross:count", 8, 12)):
            event(hope_system, f"same-{index}", "respect", .035, {"hope": .11}, .01); hope_system.tick("npc", 1)
            event(fear_system, f"same-{index}", "respect", .035, {"fear": .11}, .01); fear_system.tick("npc", 1)
        hope = behavior_signature(hope_system.observe("npc")); fear = behavior_signature(fear_system.observe("npc"))
        cooperation = robust(lambda i: hope["states"][i]["cooperate"] > fear["states"][i]["cooperate"] + .03)
        defense = robust(lambda i: max(fear["states"][i][x] for x in ("guard", "withdraw")) >
                                   max(hope["states"][i][x] for x in ("guard", "withdraw")) + .03)
        return {"checks": {
                    "same_semantics_different_recent_affect_changes_cooperation": cooperation["passed"],
                    "same_semantics_different_recent_affect_changes_defense": defense["passed"],
                }, "robust": {"cooperation": cooperation, "defense": defense}, "measures": {}}
    finally:
        hope_system.close(); fear_system.close()


def long_history_selective_reactivation(kind: str, root: Path) -> dict:
    system = factory(kind, root, f"{kind}-long-selective")
    try:
        target = event(system, "target", "betrayal", .12, {"fear": .85}, -.05)
        for index in range(seeded_int("long:noise_count", 100, 140)):
            dimension = "respect" if index % 2 == 0 else "weather"
            emotion = {"hope": .03} if dimension == "respect" else {}
            event(system, f"noise-{index}", dimension, .004, emotion); system.tick("npc", 1)
        before = behavior_signature(system.observe("npc"))
        system.recall_episode(target["episode_id"], .9); after = behavior_signature(system.observe("npc"))
        specific = robust(lambda i: max(after["states"][i][x] for x in ("guard", "withdraw")) >
                                    max(before["states"][i][x] for x in ("guard", "withdraw")) + .04)
        return {"checks": {
                    "long_history_exact_recall_remains_behaviorally_specific": specific["passed"],
                    "long_history_retains_target_episode": system.get_episode(target["episode_id"]) is not None,
                }, "robust": specific, "measures": {"episode_count": system.observe("npc")["episode_count"]}}
    finally:
        system.close()


SCENARIOS = (
    ("relevant_history_retention", relevant_history_retention),
    ("irrelevant_history_convergence", irrelevant_history_convergence),
    ("threat_override_and_recovery", threat_override_and_recovery),
    ("revision_without_consequence_rewind", revision_without_consequence_rewind),
    ("episode_specific_affect", episode_specific_affect),
    ("betrayal_affect_mode_resolution", betrayal_affect_mode_resolution),
    ("ambiguous_recall_inertness", ambiguous_recall_inertness),
    ("reactivation_is_transient_not_replay", reactivation_is_transient_not_replay),
    ("restart_behavior_identity", restart_behavior_identity),
    ("cross_layer_recent_affect_sensitivity", cross_layer_recent_affect_sensitivity),
    ("long_history_selective_reactivation", long_history_selective_reactivation),
)


def run_quality(kind: str, root: Path) -> dict:
    results = {}; passed = total = 0
    for name, scenario in SCENARIOS:
        packet = scenario(kind, root / name); results[name] = packet
        for value in packet["checks"].values():
            total += 1; passed += bool(value)
    return {"kind": kind, "passed": passed, "total": total, "scenarios": results}
