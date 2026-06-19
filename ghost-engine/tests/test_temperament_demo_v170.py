from ghost.examples.temperament_demo import main


def test_temperament_demo_runs(capsys):
    main()

    output = capsys.readouterr().out

    assert "GHOST TEMPERAMENT DEMO" in output
    assert "Step 1: Create a relationship break" in output
    assert "Step 2: Interpret same state through different temperaments" in output
    assert "calm_guard" in output
    assert "anxious_guard" in output
    assert "confident_guard" in output
    assert "suspicious_guard" in output
    assert "resentful_guard" in output
    assert "loyal_guard" in output
    assert "volatile_guard" in output
    assert "Ghost did not pick an action." in output
    assert "Ghost temperament demo complete" in output
