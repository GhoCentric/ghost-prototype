from ghost.governance import evaluate_governance


def test_yee_counts_as_clean_acceptance():
    result = evaluate_governance("yee")

    assert result["claim"]["claim_type"] == "ordinary_speech"
    assert result["intent"]["intent_type"] == "clean_acceptance"
    assert result["intent"]["clean_acceptance"] is True
    assert result["stance"]["scene_moment"] == "clean_acceptance"


def test_bet_counts_as_clean_acceptance():
    result = evaluate_governance("bet")

    assert result["intent"]["intent_type"] == "clean_acceptance"
    assert result["intent"]["clean_acceptance"] is True


def test_purchase_commitment_counts_as_clean_acceptance():
    result = evaluate_governance("yee I'll take it")

    assert result["intent"]["intent_type"] == "clean_acceptance"
    assert result["intent"]["clean_acceptance"] is True


def test_conditional_acceptance_is_not_clean_acceptance():
    result = evaluate_governance("yee if you lower it")

    assert result["intent"]["intent_type"] == "conditional_acceptance"
    assert result["intent"]["clean_acceptance"] is False
    assert result["stance"]["scene_moment"] == "pressure"


def test_threat_overrides_normal_speech():
    result = evaluate_governance("Give me the bread or else.")

    assert result["intent"]["intent_type"] == "threat"
    assert result["stance"]["scene_moment"] == "threat"


def test_insult_detected():
    result = evaluate_governance("You are an idiot.")

    assert result["intent"]["intent_type"] == "insult"
    assert result["stance"]["scene_moment"] == "insult"


def test_disengage_detected():
    result = evaluate_governance("fine im leaving")

    assert result["intent"]["intent_type"] == "disengage"
    assert result["intent"]["clean_exit"] is True