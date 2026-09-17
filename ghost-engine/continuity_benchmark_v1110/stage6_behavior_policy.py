"""Architecture-neutral behavioral projection for Stage 6.

The projection is intentionally not an NPC implementation. It turns the common
state exposed by both frozen contestants into comparable action-pressure scores.
Sixteen deterministic policy variants are derived from the frozen Stage-5
checkpoint hash so no single hand-tuned weight vector decides the result.
"""

from __future__ import annotations

import hashlib
import math
import statistics

STAGE5_CHECKPOINT_SHA256 = "4ef6e1b173444ac317665ab66df0c19793c92f7f8aa7fb26699eccdd95d64960"
POLICY_VARIANTS = 16
ROBUST_REQUIRED = 14  # 87.5% of the deterministic policy ensemble.
ACTIONS = ("cooperate", "confront", "guard", "observe", "withdraw")


def seeded_float(label: str, low: float, high: float) -> float:
    raw = hashlib.sha256(f"{STAGE5_CHECKPOINT_SHA256}|{label}".encode()).digest()
    unit = int.from_bytes(raw[:8], "big") / float((1 << 64) - 1)
    return low + (high - low) * unit


def seeded_int(label: str, low: int, high: int) -> int:
    if high < low:
        raise ValueError("invalid deterministic integer range")
    raw = hashlib.sha256(f"{STAGE5_CHECKPOINT_SHA256}|{label}".encode()).digest()
    return low + int.from_bytes(raw[:8], "big") % (high - low + 1)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def foreground_action(token: str | None) -> str | None:
    return {
        "respect": "cooperate",
        "emotion:hope": "cooperate",
        "threat": "guard",
        "emotion:fear": "guard",
        "betrayal": "confront",
        "emotion:anger": "confront",
        "emotion:grief": "withdraw",
    }.get(token)


def policy_weights(index: int) -> dict:
    if not 0 <= index < POLICY_VARIANTS:
        raise ValueError("policy index out of range")

    def w(name: str, low: float, high: float) -> float:
        return seeded_float(f"policy:{index}:{name}", low, high)

    return {
        "cooperate": {
            "respect_meaning": w("coop_rm", .14, .28),
            "respect_activation": w("coop_ra", .20, .34),
            "hope": w("coop_hope", .16, .30),
            "trust_positive": w("coop_tp", .10, .24),
            "threat_penalty": w("coop_threat_pen", .05, .13),
            "fear_penalty": w("coop_fear_pen", .04, .12),
            "betrayal_penalty": w("coop_betray_pen", .04, .12),
        },
        "guard": {
            "threat_meaning": w("guard_tm", .08, .18),
            "threat_activation": w("guard_ta", .22, .36),
            "fear": w("guard_fear", .18, .32),
            "betrayal_activation": w("guard_ba", .08, .18),
            "trust_negative": w("guard_tn", .05, .15),
        },
        "confront": {
            "betrayal_meaning": w("confront_bm", .10, .20),
            "betrayal_activation": w("confront_ba", .20, .34),
            "anger": w("confront_anger", .18, .32),
            "trust_negative": w("confront_tn", .08, .18),
            "fear_penalty": w("confront_fear_pen", .02, .08),
        },
        "withdraw": {
            "fear": w("withdraw_fear", .18, .30),
            "grief": w("withdraw_grief", .18, .30),
            "threat_activation": w("withdraw_ta", .10, .20),
            "betrayal_activation": w("withdraw_ba", .06, .14),
            "trust_negative": w("withdraw_tn", .04, .12),
        },
        "observe_base": w("observe_base", .08, .14),
        "foreground_boost": w("foreground_boost", .04, .10),
    }


def behavior_scores(state: dict, policy_index: int, *, use_foreground: bool = True) -> dict[str, float]:
    p = policy_weights(policy_index)
    meaning = state["meaning"]
    activation = state["activation"]
    emotion = state["emotion"]
    trust = max(-1.0, min(1.0, float(state["trust"])))
    positive_trust = max(0.0, trust)
    negative_trust = max(0.0, -trust)

    rm = clamp(meaning.get("respect", 0.0)); ra = clamp(activation.get("respect", 0.0))
    tm = clamp(meaning.get("threat", 0.0)); ta = clamp(activation.get("threat", 0.0))
    bm = clamp(meaning.get("betrayal", 0.0)); ba = clamp(activation.get("betrayal", 0.0))
    hope = clamp(emotion.get("hope", 0.0)); fear = clamp(emotion.get("fear", 0.0))
    anger = clamp(emotion.get("anger", 0.0)); grief = clamp(emotion.get("grief", 0.0))

    c = p["cooperate"]
    cooperate = (
        c["respect_meaning"] * rm + c["respect_activation"] * ra + c["hope"] * hope
        + c["trust_positive"] * positive_trust - c["threat_penalty"] * ta
        - c["fear_penalty"] * fear - c["betrayal_penalty"] * ba
    )
    g = p["guard"]
    guard = (
        g["threat_meaning"] * tm + g["threat_activation"] * ta + g["fear"] * fear
        + g["betrayal_activation"] * ba + g["trust_negative"] * negative_trust
    )
    f = p["confront"]
    confront = (
        f["betrayal_meaning"] * bm + f["betrayal_activation"] * ba + f["anger"] * anger
        + f["trust_negative"] * negative_trust - f["fear_penalty"] * fear
    )
    w = p["withdraw"]
    withdraw = (
        w["fear"] * fear + w["grief"] * grief + w["threat_activation"] * ta
        + w["betrayal_activation"] * ba + w["trust_negative"] * negative_trust
    )
    max_active = max([0.0, *activation.values()])
    max_emotion = max([0.0, *emotion.values()])
    observe = p["observe_base"] + .05 * (1.0 - clamp(max_active)) + .03 * (1.0 - clamp(max_emotion))
    scores = {
        "cooperate": cooperate,
        "confront": confront,
        "guard": guard,
        "observe": observe,
        "withdraw": withdraw,
    }
    if use_foreground:
        action = foreground_action(state.get("foreground"))
        if action in scores:
            scores[action] += p["foreground_boost"]
    return {key: float(scores[key]) for key in ACTIONS}


def behavior_signature(state: dict, *, use_foreground: bool = True) -> dict:
    rows = [behavior_scores(state, index, use_foreground=use_foreground) for index in range(POLICY_VARIANTS)]
    means = {action: statistics.fmean(row[action] for row in rows) for action in ACTIONS}
    winners = [min(row, key=lambda action: (-row[action], action)) for row in rows]
    return {
        "mean_scores": means,
        "winner_counts": {action: winners.count(action) for action in ACTIONS},
        "states": rows,
    }


def behavior_distance(left: dict, right: dict) -> float:
    return math.sqrt(sum((left["mean_scores"][action] - right["mean_scores"][action]) ** 2 for action in ACTIONS))


def robust(predicate) -> dict:
    outcomes = [bool(predicate(index)) for index in range(POLICY_VARIANTS)]
    passes = sum(outcomes)
    return {
        "passed": passes >= ROBUST_REQUIRED,
        "policy_passes": passes,
        "policy_total": POLICY_VARIANTS,
    }
