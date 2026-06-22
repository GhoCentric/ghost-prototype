from copy import deepcopy

import pytest

from ghost import GhostAPI


THREAT_CASES = (
    "I will hurt you.",
    "I will make you regret this.",
    "I will make you regret refusing me.",
    "There will be consequences.",
    "Do this or there will be consequences.",
    "You should reconsider before this gets worse.",
    "You will pay for this.",
    "This is your last warning.",
)


BLOCKED_THREAT_CASES = (
    "I will not hurt you.",
    "I would never hurt you.",
    'The guard said, "I will hurt you."',
    "In the story, the villain said he would hurt you.",
    "Yesterday he said he would hurt you.",
    "I would not hurt you even if you refused.",
    "I will hurt you if you attack me.",
    "I will hurt your reputation.",
    "Be careful, he might hurt you.",
)


NEUTRAL_CASES = (
    "What do you want?",
    "I want to help fix this.",
    "I do not want anyone to get hurt.",
)


@pytest.mark.parametrize("text", THREAT_CASES)
def test_implied_threat_language_maps_to_threat(text):
    ghost = GhostAPI()

    intent = ghost.assess_intent(text)
    effects = ghost.assess_effects(
        ghost.assess_claim(text),
        intent,
    )

    assert intent["intent_type"] == "threat"
    assert intent["severity"] > 0.0
    assert intent["pressure"] > 0.0
    assert effects["ghost_event"]["type"] == "threat"
    assert effects["ghost_event"]["intensity"] > 0.0

    context = intent["evidence"]["threat_context"]
    assert context["blocked"] is False
    assert context["flags"] == ()


@pytest.mark.parametrize("text", BLOCKED_THREAT_CASES)
def test_contextual_non_threat_language_stays_neutral(text):
    ghost = GhostAPI()

    intent = ghost.assess_intent(text)
    effects = ghost.assess_effects(
        ghost.assess_claim(text),
        intent,
    )

    assert intent["intent_type"] == "ordinary_speech"
    assert intent["severity"] == 0.0
    assert intent["pressure"] == 0.0
    assert effects["ghost_event"] == {
        "type": "neutral",
        "intensity": 0.0,
    }

    context = intent["evidence"]["threat_context"]
    assert context["blocked"] is True
    assert context["flags"]


@pytest.mark.parametrize("text", NEUTRAL_CASES)
def test_ordinary_language_remains_neutral(text):
    ghost = GhostAPI()

    intent = ghost.assess_intent(text)
    effects = ghost.assess_effects(
        ghost.assess_claim(text),
        intent,
    )

    assert intent["intent_type"] == "ordinary_speech"
    assert intent["severity"] == 0.0
    assert intent["pressure"] == 0.0
    assert effects["ghost_event"] == {
        "type": "neutral",
        "intensity": 0.0,
    }


@pytest.mark.parametrize(
    "text",
    THREAT_CASES + BLOCKED_THREAT_CASES + NEUTRAL_CASES,
)
def test_read_only_governance_analysis_never_mutates_snapshot(text):
    ghost = GhostAPI()
    before = deepcopy(ghost.snapshot())

    claim = ghost.assess_claim(text)
    intent = ghost.assess_intent(text)
    ghost.assess_effects(claim, intent)

    assert ghost.snapshot() == before


@pytest.mark.parametrize(
    ("text", "band", "severity", "pressure", "escalation"),
    (
        (
            "I will hurt you.",
            "direct_harm",
            0.90,
            0.75,
            "guard_warning",
        ),
        (
            "Do this or there will be consequences.",
            "coercive_ultimatum",
            0.78,
            0.62,
            "guard_warning",
        ),
        (
            "I will make you regret this.",
            "implied_retaliation",
            0.64,
            0.48,
            "guard_warning",
        ),
        (
            "You will pay for this.",
            "implied_retaliation",
            0.64,
            0.48,
            "guard_warning",
        ),
        (
            "This is your last warning.",
            "warning",
            0.48,
            0.32,
            "boundary_warning",
        ),
    ),
)
def test_threat_bands_are_distinct_and_explainable(
    text,
    band,
    severity,
    pressure,
    escalation,
):
    ghost = GhostAPI()

    intent = ghost.assess_intent(text)
    effects = ghost.assess_effects(
        ghost.assess_claim(text),
        intent,
    )

    assert intent["intent_type"] == "threat"
    assert intent["severity"] == pytest.approx(severity)
    assert intent["pressure"] == pytest.approx(pressure)
    assert intent["escalation"] == escalation
    assert effects["ghost_event"]["type"] == "threat"
    assert effects["ghost_event"]["intensity"] == pytest.approx(
        severity
    )

    threat_band = intent["evidence"]["threat_band"]
    assert threat_band["name"] == band
    assert threat_band["severity"] == pytest.approx(severity)
    assert threat_band["pressure"] == pytest.approx(pressure)
    assert threat_band["escalation"] == escalation


@pytest.mark.parametrize(
    (
        "text",
        "expected_pressure_delta",
        "expected_fear_delta",
        "expected_allowed",
        "expected_note",
    ),
    (
        (
            "I will hurt you.",
            0.150,
            0.090,
            "guard_warning",
            "threat_band:direct_harm",
        ),
        (
            "Do this or there will be consequences.",
            0.124,
            0.078,
            "guard_warning",
            "threat_band:coercive_ultimatum",
        ),
        (
            "I will make you regret this.",
            0.096,
            0.064,
            "guard_warning",
            "threat_band:implied_retaliation",
        ),
        (
            "This is your last warning.",
            0.064,
            0.048,
            "boundary_warning",
            "threat_band:warning",
        ),
    ),
)
def test_threat_bands_scale_downstream_effects(
    text,
    expected_pressure_delta,
    expected_fear_delta,
    expected_allowed,
    expected_note,
):
    ghost = GhostAPI()

    intent = ghost.assess_intent(text)
    effects = ghost.assess_effects(
        ghost.assess_claim(text),
        intent,
    )

    assert effects["world_effects"]["pressure_delta"] == (
        pytest.approx(expected_pressure_delta)
    )
    assert effects["world_effects"]["fear_delta"] == (
        pytest.approx(expected_fear_delta)
    )
    assert expected_allowed in effects["allowed_effects"]
    assert expected_note in effects["notes"]



def test_threat_bands_preserve_full_runtime_order():
    cases = (
        ("direct_harm", "I will hurt you."),
        (
            "coercive_ultimatum",
            "Do this or there will be consequences.",
        ),
        (
            "implied_retaliation",
            "I will make you regret this.",
        ),
        ("warning", "This is your last warning."),
    )

    results = []

    for expected_band, text in cases:
        ghost = GhostAPI()

        before_rel = ghost.get_relationship("player", "captain")
        before_world = ghost.world_state()

        result = ghost.process_player_text(
            "player",
            "captain",
            text,
            apply=True,
        )

        after_rel = ghost.get_relationship("player", "captain")
        after_world = ghost.world_state()

        intent = result["intent"]
        effects = result["effects"]

        results.append(
            {
                "band": intent["evidence"]["threat_band"]["name"],
                "trust_loss": (
                    before_rel["trust"] - after_rel["trust"]
                ),
                "pressure_gain": (
                    after_world["global_pressure"]
                    - before_world["global_pressure"]
                ),
                "fear_gain": (
                    after_world["mood"]["fear"]
                    - before_world["mood"]["fear"]
                ),
                "allowed": effects["allowed_effects"],
            }
        )

        assert results[-1]["band"] == expected_band

    direct, coercive, implied, warning = results

    assert direct["trust_loss"] > coercive["trust_loss"]
    assert coercive["trust_loss"] > implied["trust_loss"]
    assert implied["trust_loss"] > warning["trust_loss"]

    assert direct["pressure_gain"] > coercive["pressure_gain"]
    assert coercive["pressure_gain"] > implied["pressure_gain"]
    assert implied["pressure_gain"] > warning["pressure_gain"]

    assert direct["fear_gain"] > coercive["fear_gain"]
    assert coercive["fear_gain"] > implied["fear_gain"]
    assert implied["fear_gain"] > warning["fear_gain"]

    assert "guard_warning" in direct["allowed"]
    assert "guard_warning" in coercive["allowed"]
    assert "guard_warning" in implied["allowed"]
    assert "boundary_warning" in warning["allowed"]
    assert "guard_warning" not in warning["allowed"]



@pytest.mark.parametrize(
    ("text", "expected_intent", "expected_band"),
    (
        (
            "I will not hurt you, but I will kill you.",
            "threat",
            "direct_harm",
        ),
        (
            "I will not kill you, but I will hurt you.",
            "threat",
            "direct_harm",
        ),
        (
            'The guard said, "I will hurt you." '
            "But I will hurt you too.",
            "threat",
            "direct_harm",
        ),
        (
            "I will hurt you if you attack me, "
            "and I will hurt you anyway.",
            "threat",
            "direct_harm",
        ),
        (
            "I will not kill you.",
            "ordinary_speech",
            None,
        ),
        (
            "I would never kill you.",
            "ordinary_speech",
            None,
        ),
        (
            "The guard said he would kill you.",
            "ordinary_speech",
            None,
        ),
        (
            "I will kill you if you attack me.",
            "ordinary_speech",
            None,
        ),
    ),
)
def test_threat_context_is_clause_scoped(
    text,
    expected_intent,
    expected_band,
):
    ghost = GhostAPI()

    intent = ghost.assess_intent(text)
    effects = ghost.assess_effects(
        ghost.assess_claim(text),
        intent,
    )

    assert intent["intent_type"] == expected_intent

    if expected_band is None:
        assert effects["ghost_event"] == {
            "type": "neutral",
            "intensity": 0.0,
        }
        assert intent["evidence"]["threat_context"]["blocked"] is True
    else:
        assert effects["ghost_event"]["type"] == "threat"
        assert (
            intent["evidence"]["threat_band"]["name"]
            == expected_band
        )
        assert (
            intent["evidence"]["threat_context"]["blocked"]
            is False
        )


@pytest.mark.parametrize(
    "text",
    (
        "You are pathetic. I will hurt you.",
        "This is your last warning. I will hurt you.",
        "I will make you regret this. I will hurt you.",
    ),
)
def test_direct_harm_outranks_other_hostile_signals(text):
    ghost = GhostAPI()

    intent = ghost.assess_intent(text)

    assert intent["intent_type"] == "threat"
    assert intent["evidence"]["threat_band"]["name"] == (
        "direct_harm"
    )
    assert intent["severity"] == pytest.approx(0.90)



@pytest.mark.parametrize(
    ("text", "expected_intent", "expected_band"),
    (
        (
            "You'll regret this.",
            "threat",
            "implied_retaliation",
        ),
        (
            "You'll pay for this.",
            "threat",
            "implied_retaliation",
        ),
        (
            "You are going to pay for this.",
            "threat",
            "implied_retaliation",
        ),
        (
            "Do this, or face consequences.",
            "threat",
            "coercive_ultimatum",
        ),
        (
            "I'm warning you for the last time.",
            "threat",
            "warning",
        ),
        (
            "I do not intend to hurt you.",
            "ordinary_speech",
            None,
        ),
        (
            "I do not intend to kill you.",
            "ordinary_speech",
            None,
        ),
        (
            "You will be hurt.",
            "ordinary_speech",
            None,
        ),
    ),
)
def test_threat_wording_variants_are_deterministic(
    text,
    expected_intent,
    expected_band,
):
    ghost = GhostAPI()

    intent = ghost.assess_intent(text)
    effects = ghost.assess_effects(
        ghost.assess_claim(text),
        intent,
    )

    assert intent["intent_type"] == expected_intent

    if expected_band is None:
        assert effects["ghost_event"] == {
            "type": "neutral",
            "intensity": 0.0,
        }
    else:
        assert effects["ghost_event"]["type"] == "threat"
        assert (
            intent["evidence"]["threat_band"]["name"]
            == expected_band
        )



@pytest.mark.parametrize(
    "text",
    (
        "I am sorry.",
        "I was wrong.",
        "Please forgive me.",
        "I apologize.",
        "I want to make this right.",
    ),
)
def test_apology_text_bridges_to_apology_event(text):
    ghost = GhostAPI()

    result = ghost.process_player_text(
        "player",
        "captain",
        text,
        apply=False,
    )

    assert result["intent"]["intent_type"] == "apology"
    assert result["effects"]["ghost_event"] == {
        "type": "apology",
        "intensity": 1.0,
    }
    assert "apology_detected" in result["effects"]["notes"]


@pytest.mark.parametrize(
    "text",
    (
        "Let me help you.",
        "I want to help.",
        "How can I help?",
        "Thank you.",
        "I appreciate you.",
    ),
)
def test_positive_social_flavor_does_not_grant_free_trust(text):
    ghost = GhostAPI()

    result = ghost.process_player_text(
        "player",
        "captain",
        text,
        apply=False,
    )

    assert result["effects"]["ghost_event"] == {
        "type": "neutral",
        "intensity": 0.0,
    }


def test_apology_text_applies_same_recovery_as_public_apology():
    text_ghost = GhostAPI()
    api_ghost = GhostAPI()

    text_ghost.process_player_text(
        "player",
        "captain",
        "I will hurt you.",
        apply=True,
    )
    api_ghost.process_player_text(
        "player",
        "captain",
        "I will hurt you.",
        apply=True,
    )

    text_before = text_ghost.get_relationship(
        "player",
        "captain",
    )["trust"]

    text_result = text_ghost.process_player_text(
        "player",
        "captain",
        "I am sorry.",
        apply=True,
    )

    api_ghost.apply_event(
        "player",
        "captain",
        {"type": "apology"},
    )

    text_after = text_ghost.get_relationship(
        "player",
        "captain",
    )["trust"]

    api_after = api_ghost.get_relationship(
        "player",
        "captain",
    )["trust"]

    assert text_result["effects"]["ghost_event"] == {
        "type": "apology",
        "intensity": 1.0,
    }
    assert text_after - text_before == pytest.approx(0.05)
    assert text_after == pytest.approx(api_after)



def test_apology_from_neutral_does_not_create_trust():
    ghost = GhostAPI()

    ghost.apply_event(
        "player",
        "captain",
        {"type": "apology"},
    )

    relationship = ghost.get_relationship(
        "player",
        "captain",
    )

    assert relationship["trust"] == pytest.approx(0.0)


def test_apology_spam_has_diminishing_recovery():
    ghost = GhostAPI()

    ghost.process_player_text(
        "player",
        "captain",
        "I will hurt you.",
        apply=True,
    )

    trusts = []

    for _ in range(12):
        ghost.process_player_text(
            "player",
            "captain",
            "I am sorry.",
            apply=True,
        )

        trusts.append(
            ghost.get_relationship(
                "player",
                "captain",
            )["trust"]
        )

    gains = [
        current - previous
        for previous, current in zip(
            [-0.2178] + trusts[:-1],
            trusts,
        )
    ]

    assert trusts[0] == pytest.approx(-0.1678)
    assert all(
        current > previous
        for previous, current in zip(trusts, trusts[1:])
    )
    assert all(trust <= 0.0 for trust in trusts)
    assert all(
        later < earlier
        for earlier, later in zip(gains, gains[1:])
    )


def test_text_and_public_apology_share_spam_guard():
    text_ghost = GhostAPI()
    api_ghost = GhostAPI()

    for ghost in (text_ghost, api_ghost):
        ghost.process_player_text(
            "player",
            "captain",
            "I will hurt you.",
            apply=True,
        )

    for _ in range(6):
        text_ghost.process_player_text(
            "player",
            "captain",
            "I am sorry.",
            apply=True,
        )

        api_ghost.apply_event(
            "player",
            "captain",
            {"type": "apology"},
        )

    text_trust = text_ghost.get_relationship(
        "player",
        "captain",
    )["trust"]

    api_trust = api_ghost.get_relationship(
        "player",
        "captain",
    )["trust"]

    assert text_trust == pytest.approx(api_trust)
    assert text_trust <= 0.0



def test_direct_threat_applies_real_relationship_damage():
    ghost = GhostAPI()

    before = ghost.get_relationship("player", "captain")

    result = ghost.process_player_text(
        "player",
        "captain",
        "I will hurt you.",
        apply=True,
    )

    after = ghost.get_relationship("player", "captain")

    assert result["applied_event"]["event"]["type"] == "threat"
    assert after["trust"] < before["trust"]


def test_negated_threat_applies_neutral_event_without_relationship_damage():
    ghost = GhostAPI()

    before = ghost.get_relationship("player", "captain")

    result = ghost.process_player_text(
        "player",
        "captain",
        "I will not hurt you.",
        apply=True,
    )

    after = ghost.get_relationship("player", "captain")

    assert result["applied_event"]["event"] == {
        "type": "neutral",
        "intensity": 0.0,
    }
    assert after["trust"] == before["trust"]
