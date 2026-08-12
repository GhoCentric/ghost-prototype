"""Coverage closure for Ghost Revolution entry point and epistemic benchmarks."""

from __future__ import annotations

from copy import deepcopy
import importlib
import runpy
import sys

import pytest

from ghost.examples.ghost_revolution import demo
from ghost.examples.ghost_revolution.benchmarks import (
    epistemic_decision_benchmark as decision,
)
from ghost.examples.ghost_revolution.benchmarks import (
    epistemic_fair_fork_benchmark as fair,
)
from ghost.examples.ghost_revolution.benchmarks import (
    epistemic_scenario_matrix_benchmark as matrix,
)


class _ActionGame:
    def __init__(self, *, actions=2):
        self.actions = actions
        self.last_action_note = ""
        self.packet = {"ok": True}

    def seize_royal_supplies(self):
        self.actions -= 1
        self.last_action_note = "Royal cache seized: test"

    def question_guard(self):
        self.actions -= 1
        self.last_action_note = "Guard read: knight's patrols"

    def earn_honest_gold(self):
        self.actions -= 1
        return self.packet


class _SnapshotGame:
    def __init__(self, snapshot, *, exact=True, actions=2):
        self._snapshot = deepcopy(snapshot)
        self._exact = exact
        self.location = "millcross"
        self.phase = "rebellion"
        self.phase_number = 1
        self.phase_day = 1
        self.actions = actions
        self.followers = 0
        self.gold = 0
        self.food = 0
        self.heat = 0
        self.royal_alert = 0
        self.towns = {"millcross": {"fear": 0}}
        self.knight_town = "millcross"
        self.alive = True
        self.captured = False
        self.last_action_note = ""

    def snapshot(self):
        if self._exact:
            return deepcopy(self._snapshot)
        return {"different": True}

    def weapon_stock_total(self):
        return 0

    def town_trust(self, _town):
        return 0.0

    def guard_count(self, _town):
        return 2


class _FakeGhost:
    def snapshot(self):
        return {"ghost": True}

    def get_belief(self, _holder, _subject):
        return {"id": "revised"}


class _FakeGhostAPI:
    @classmethod
    def from_snapshot(cls, _snapshot):
        return _FakeGhost()


def test_package_main_executes_demo_main_v180(monkeypatch):
    imported = importlib.import_module(
        "ghost.examples.ghost_revolution.__main__"
    )
    assert imported.main is demo.main

    sys.modules.pop(
        "ghost.examples.ghost_revolution.__main__",
        None,
    )

    calls = []
    monkeypatch.setattr(demo, "main", lambda: calls.append("main"))
    runpy.run_module(
        "ghost.examples.ghost_revolution",
        run_name="__main__",
    )
    assert calls == ["main"]


def test_decision_policy_and_setup_boundaries_v180(monkeypatch):
    class NoTravel:
        def __init__(self, seed):
            self.knight_town = None

        def travel(self, _town):
            return False

    monkeypatch.setattr(decision, "GhostRevolutionRun", NoTravel)
    with pytest.raises(RuntimeError, match="could not travel"):
        decision._prepare_game(1)

    assert decision.provenance_initial_policy({
        "report_quality": {
            "direct_observation": .9,
            "deception_likely": .1,
        },
        "dimensions": {
            "royal_presence": {
                "dominant_candidate": "unknown",
            },
        },
    }) == "secure_work"

    assert decision.provenance_revised_policy({
        "dimensions": {
            "royal_presence": {
                "dominant_candidate": "knight_absent",
                "confidence": .9,
            },
        },
    }) == "seize_royal_supplies"

    assert decision.oracle_diagnostic_policy({
        "knight_present": False,
    }) == "seize_royal_supplies"


def test_decision_action_validation_boundaries_v180():
    game = _ActionGame()
    game.seize_royal_supplies = lambda: None
    with pytest.raises(RuntimeError, match="spend one action"):
        decision._execute_seizure(game)

    game = _ActionGame()
    def bad_seizure():
        game.actions -= 1
        game.last_action_note = "wrong"
    game.seize_royal_supplies = bad_seizure
    with pytest.raises(RuntimeError, match="consequence text"):
        decision._execute_seizure(game)

    game = _ActionGame()
    game.question_guard = lambda: None
    with pytest.raises(RuntimeError, match="spend one action"):
        decision._execute_guard_investigation(game)

    game = _ActionGame()
    def bad_guard():
        game.actions -= 1
        game.last_action_note = "Guard read without cue"
    game.question_guard = bad_guard
    with pytest.raises(RuntimeError, match="knight-presence"):
        decision._execute_guard_investigation(game)

    game = _ActionGame()
    game.packet = None
    with pytest.raises(RuntimeError, match="work action to resolve"):
        decision._execute_secure_work(game)

    game = _ActionGame()
    game.earn_honest_gold = lambda: {"ok": True}
    with pytest.raises(RuntimeError, match="spend one action"):
        decision._execute_secure_work(game)


def test_decision_runner_alternate_and_failure_paths_v180(monkeypatch):
    game = _ActionGame(actions=3)
    monkeypatch.setattr(decision, "_prepare_game", lambda _seed: game)
    monkeypatch.setattr(decision, "_state_fingerprint", lambda _game: {"actions": 3})
    monkeypatch.setattr(decision, "naive_report_truth_policy", lambda _report: "secure_work")
    monkeypatch.setattr(decision, "_execute_secure_work", lambda _game: None)
    monkeypatch.setattr(decision, "_outcome", lambda _before, _game: {"ok": True})
    assert decision._run_naive_policy(1, {})["decision_path"] == ["secure_work"]

    monkeypatch.setattr(
        decision,
        "_build_epistemic_case",
        lambda _report: (_FakeGhost(), {
            "fact_id": "fact",
            "fact_record_id": "fact-record",
            "report_id": "report",
            "initial_belief": {"id": "initial"},
        }),
    )
    monkeypatch.setattr(decision, "provenance_initial_policy", lambda _belief: "secure_work")
    with pytest.raises(RuntimeError, match="trigger guard investigation"):
        decision._run_provenance_policy(1, {})

    monkeypatch.setattr(decision, "provenance_initial_policy", lambda _belief: "investigate_guard")
    monkeypatch.setattr(decision, "_execute_guard_investigation", lambda _game: None)
    monkeypatch.setattr(
        decision,
        "_revise_from_guard_investigation",
        lambda _ghost, _belief: {
            "observation_id": "o",
            "evidence_id": "e",
            "revised_belief": {"id": "revised"},
        },
    )
    monkeypatch.setattr(decision, "provenance_revised_policy", lambda _belief: "seize_royal_supplies")
    monkeypatch.setattr(decision, "_execute_seizure", lambda _game: None)
    monkeypatch.setattr(decision, "_belief_summary", lambda belief: {"id": belief["id"]})
    monkeypatch.setattr(decision, "GhostAPI", _FakeGhostAPI)
    result = decision._run_provenance_policy(1, {})
    assert result["decision_path"] == ["investigate_guard", "seize_royal_supplies"]

    monkeypatch.setattr(decision, "oracle_diagnostic_policy", lambda _objective: "seize_royal_supplies")
    result = decision._run_oracle_diagnostic(1, {})
    assert result["decision_path"] == ["seize_royal_supplies"]


def test_fair_json_setup_policy_and_action_boundaries_v180(monkeypatch):
    assert fair._json_copy({"a": [1]}, "value") == {"a": [1]}
    with pytest.raises(ValueError, match="JSON-safe"):
        fair._json_copy({"bad": object()}, "value")

    class NoTravel:
        def __init__(self, seed):
            self.knight_town = None
        def travel(self, _town):
            return False

    monkeypatch.setattr(fair, "GhostRevolutionRun", NoTravel)
    with pytest.raises(RuntimeError, match="could not travel"):
        fair._create_decision_fork(1)

    class BadBudget:
        def __init__(self, seed):
            self.knight_town = None
            self.actions = 0
        def travel(self, _town):
            return True
        def snapshot(self):
            return {"state": {"actions": 999}}

    monkeypatch.setattr(fair, "GhostRevolutionRun", BadBudget)
    with pytest.raises(RuntimeError, match="action budget"):
        fair._create_decision_fork(1)

    assert fair.provenance_initial_policy({
        "report_quality": {"direct_observation": .9, "deception_likely": .1},
        "dimensions": {"royal_presence": {"dominant_candidate": "unknown", "confidence": .9}},
    }) == "secure_work"
    assert fair.provenance_revised_policy({
        "dimensions": {"royal_presence": {"dominant_candidate": "knight_absent", "confidence": .9}},
    }) == "seize_royal_supplies"
    assert fair.oracle_budget_matched_policy({"knight_present": False}) == (
        "seize_royal_supplies", "secure_work"
    )

    game = _ActionGame()
    def bad_seizure():
        game.actions -= 1
        game.last_action_note = "wrong"
    game.seize_royal_supplies = bad_seizure
    with pytest.raises(RuntimeError, match="supply-seizure"):
        fair._execute_action(game, "seize_royal_supplies")

    game = _ActionGame()
    def bad_guard():
        game.actions -= 1
        game.last_action_note = "wrong"
    game.question_guard = bad_guard
    with pytest.raises(RuntimeError, match="guard-investigation"):
        fair._execute_action(game, "investigate_guard")

    game = _ActionGame()
    game.packet = None
    with pytest.raises(RuntimeError, match="work action"):
        fair._execute_action(game, "secure_work")

    with pytest.raises(ValueError, match="Unsupported benchmark action"):
        fair._execute_action(_ActionGame(), "unknown")

    game = _ActionGame()
    game.earn_honest_gold = lambda: {"ok": True}
    with pytest.raises(RuntimeError, match="spend exactly one action"):
        fair._execute_action(game, "secure_work")


def test_fair_branch_validation_and_ghost_alternates_v180(monkeypatch):
    snapshot = {"state": {"actions": 2}}

    class Factory:
        exact = True
        actions = 2
        @classmethod
        def from_snapshot(cls, snap):
            return _SnapshotGame(snap, exact=cls.exact, actions=cls.actions)

    monkeypatch.setattr(fair, "GhostRevolutionRun", Factory)
    monkeypatch.setattr(fair, "_state_view", lambda game: {"actions": game.actions})
    monkeypatch.setattr(fair, "_execute_action", lambda game, action: setattr(game, "actions", game.actions - 1))
    monkeypatch.setattr(
        fair,
        "_raw_outcome",
        lambda before, game: {
            "actions_spent": before["actions"] - game.actions,
            "actions_remaining": game.actions,
        },
    )

    Factory.exact = False
    with pytest.raises(RuntimeError, match="restore exact"):
        fair._run_action_path(snapshot, ("a", "b"))

    Factory.exact = True
    Factory.actions = 1
    with pytest.raises(RuntimeError, match="action budget"):
        fair._run_action_path(snapshot, ("a", "b"))

    Factory.actions = 2
    monkeypatch.setattr(fair, "_raw_outcome", lambda _before, _game: {
        "actions_spent": 1,
        "actions_remaining": 1,
    })
    with pytest.raises(RuntimeError, match="exhaust fixed"):
        fair._run_action_path(snapshot, ("a", "b"))

    monkeypatch.setattr(
        fair,
        "_build_epistemic_case",
        lambda _report: (_FakeGhost(), {"initial_belief": {"id": "initial"}}),
    )
    monkeypatch.setattr(fair, "provenance_initial_policy", lambda _belief: "secure_work")
    with pytest.raises(RuntimeError, match="expected low-provenance"):
        fair._run_ghost_branch(snapshot, {})

    monkeypatch.setattr(fair, "provenance_initial_policy", lambda _belief: "investigate_guard")
    Factory.exact = False
    with pytest.raises(RuntimeError, match="restore exact"):
        fair._run_ghost_branch(snapshot, {})

    Factory.exact = True
    Factory.actions = 2
    monkeypatch.setattr(fair, "_state_view", lambda game: {"actions": game.actions})
    monkeypatch.setattr(fair, "_execute_action", lambda game, action: setattr(game, "actions", game.actions - 1))
    monkeypatch.setattr(
        fair,
        "_revise_from_guard_read",
        lambda *_args: {
            "observation_id": "o",
            "evidence_id": "e",
            "revised_belief": {"id": "revised"},
        },
    )
    monkeypatch.setattr(fair, "provenance_revised_policy", lambda _belief: "secure_work")
    monkeypatch.setattr(fair, "_raw_outcome", lambda _before, _game: {
        "actions_spent": 1,
        "actions_remaining": 1,
    })
    with pytest.raises(RuntimeError, match="exhaust fixed"):
        fair._run_ghost_branch(snapshot, {})


def test_matrix_setup_action_and_policy_boundaries_v180(monkeypatch):
    class NoTravel:
        def __init__(self, seed):
            self.knight_town = None
        def travel(self, _town):
            return False

    monkeypatch.setattr(matrix, "GhostRevolutionRun", NoTravel)
    with pytest.raises(RuntimeError, match="could not travel"):
        matrix._fork(1, "millcross", True)

    class BadBudget:
        def __init__(self, seed):
            self.knight_town = None
            self.actions = 0
        def travel(self, _town):
            return True
        def snapshot(self):
            return {"state": {"actions": 999}}

    monkeypatch.setattr(matrix, "GhostRevolutionRun", BadBudget)
    with pytest.raises(RuntimeError, match="action budget"):
        matrix._fork(1, "millcross", True)

    game = _ActionGame()
    game.packet = None
    with pytest.raises(RuntimeError, match="work action"):
        matrix._act(game, "secure_work")

    with pytest.raises(ValueError, match="Unsupported matrix action"):
        matrix._act(_ActionGame(), "unknown")

    game = _ActionGame()
    def bad_seizure():
        game.actions -= 1
        game.last_action_note = "wrong"
    game.seize_royal_supplies = bad_seizure
    with pytest.raises(RuntimeError, match="evidence text"):
        matrix._act(game, "seize_royal_supplies")

    game = _ActionGame()
    game.earn_honest_gold = lambda: {"ok": True}
    with pytest.raises(RuntimeError, match="spend exactly one action"):
        matrix._act(game, "secure_work")

    with pytest.raises(ValueError, match="requires at least one report"):
        matrix.naive_report_truth_policy([])


def test_matrix_branch_validation_boundaries_v180(monkeypatch):
    snapshot = {"state": {"actions": 2}}

    class Factory:
        exact = True
        actions = 2
        @classmethod
        def from_snapshot(cls, snap):
            return _SnapshotGame(snap, exact=cls.exact, actions=cls.actions)

    monkeypatch.setattr(matrix, "GhostRevolutionRun", Factory)
    monkeypatch.setattr(matrix, "_view", lambda game, town: {"actions": game.actions})
    monkeypatch.setattr(matrix, "_act", lambda game, action: setattr(game, "actions", game.actions - 1))
    monkeypatch.setattr(
        matrix,
        "_outcome",
        lambda before, game, town: {
            "actions_spent": before["actions"] - game.actions,
            "actions_remaining": game.actions,
        },
    )

    Factory.exact = False
    with pytest.raises(RuntimeError, match="restore exact"):
        matrix._run_actions(snapshot, "millcross", ("a", "b"))

    Factory.exact = True
    monkeypatch.setattr(matrix, "_outcome", lambda *_args: {
        "actions_spent": 1,
        "actions_remaining": 1,
    })
    with pytest.raises(RuntimeError, match="exhaust the fixed"):
        matrix._run_actions(snapshot, "millcross", ("a", "b"))

    scenario = {
        "id": "scenario",
        "knight_present": True,
    }
    reports = [{"speaker": "s", "confidence": .9, "claim": {"knight_status": "absent"}}]
    monkeypatch.setattr(
        matrix,
        "_epistemic_case",
        lambda *_args: (_FakeGhost(), {
            "subject": "royal_presence:millcross",
            "fact_id": "f",
            "fact_record_id": "fr",
            "report_ids": ["r"],
            "belief": {"id": "initial"},
        }),
    )
    monkeypatch.setattr(matrix, "provenance_initial_policy", lambda _belief: "secure_work")

    Factory.exact = False
    with pytest.raises(RuntimeError, match="restore exact"):
        matrix._ghost(snapshot, scenario, "millcross", reports)

    Factory.exact = True
    monkeypatch.setattr(matrix, "_belief_summary", lambda belief: {"id": belief["id"]})
    monkeypatch.setattr(matrix, "GhostAPI", _FakeGhostAPI)
    monkeypatch.setattr(matrix, "_outcome", lambda *_args: {
        "actions_spent": 1,
        "actions_remaining": 1,
    })
    with pytest.raises(RuntimeError, match="exhaust the fixed"):
        matrix._ghost(snapshot, scenario, "millcross", reports)
