from copy import deepcopy
from types import SimpleNamespace

import pytest

from ghost.examples.ghost_revolution.demo import GhostRevolutionRun
from ghost.examples.ghost_revolution.raid import RaidOutcome


def _packet(*, detain=False, fail=False):
    return {
        "law": {"action": "detain" if detain else "none"},
        "win_fail": {"is_fail": fail},
    }


def test_demo_foundation_snapshot_copy_setters_and_raid_errors():
    with pytest.raises(ValueError, match="must be JSON-safe"):
        GhostRevolutionRun._snapshot_copy({"bad": object()}, "value")

    game = GhostRevolutionRun()
    game.raid_plan = None
    game.active_raid = None

    context = game._raid_context("missing")
    assert context.valid_target is False

    game.weapon_stock["sword"] = 0
    with pytest.raises(RuntimeError, match="weapon stock negative"):
        game._apply_raid_outcome(
            RaidOutcome("", False, weapon_stock_deltas={"sword": -1})
        )

    game.shield_stock["light"] = 0
    with pytest.raises(RuntimeError, match="shield stock negative"):
        game._apply_raid_outcome(
            RaidOutcome("", False, shield_stock_deltas={"light": -1})
        )

    game.food = 0
    with pytest.raises(RuntimeError, match="food negative"):
        game._apply_raid_outcome(RaidOutcome("", False, food_delta=-1))

    game.last_action_note = "preserved"
    assert game._apply_raid_outcome(RaidOutcome("", True)) is True
    assert game.last_action_note == "preserved"


def test_demo_snapshot_validation_closes_remaining_state_shapes():
    base = GhostRevolutionRun().snapshot()

    cases = []

    damaged = deepcopy(base)
    damaged["state"] = []
    cases.append((damaged, "snapshot state is invalid"))

    damaged = deepcopy(base)
    damaged["state"]["phase"] = 1
    cases.append((damaged, "text state is invalid"))

    damaged = deepcopy(base)
    damaged["state"]["alive"] = 1
    cases.append((damaged, "boolean state is invalid"))

    damaged = deepcopy(base)
    damaged["state"]["weapon_stock"] = []
    cases.append((damaged, "mapping state is invalid"))

    damaged = deepcopy(base)
    damaged["state"]["last_king_response"] = {}
    cases.append((damaged, "record state is invalid"))

    damaged = deepcopy(base)
    damaged["state"]["public_event_state"] = {}
    cases.append((damaged, "public event state is invalid"))

    for snapshot, message in cases:
        with pytest.raises(ValueError, match=message):
            GhostRevolutionRun.from_snapshot(snapshot)


def test_demo_action_spending_and_packet_terminal_outcomes():
    game = GhostRevolutionRun()

    assert game._spend_action(0) is False
    game.actions = 0
    assert game._spend_action(1) is False

    detained = GhostRevolutionRun()
    assert detained._save_packet(_packet(detain=True))['law']['action'] == 'detain'
    assert detained.captured is True
    assert detained.alive is False

    failed = GhostRevolutionRun()
    assert failed._save_packet(_packet(fail=True))["win_fail"]["is_fail"] is True
    assert failed.alive is False


def test_demo_guard_roster_edge_paths_and_totals():
    game = GhostRevolutionRun()

    assert game.guard_count("missing") == 0
    assert game.active_guard("ashfield") is None
    assert game.active_guard_label("ashfield") == "No royal guard"

    with pytest.raises(ValueError, match="unknown town id"):
        game._add_guard("missing", "watchman")

    with pytest.raises(RuntimeError, match="unknown town for guard removal"):
        game._remove_guard("missing", "x")

    with pytest.raises(RuntimeError, match="missing active guard"):
        game._remove_guard("millcross", "not-present")

    game.towns["ashfield"]["recruited"] = 2
    game.towns["millcross"]["recruited"] = 3
    assert game.total_recruited() == 5


def test_demo_role_assignment_inventory_and_raid_lookup_edges():
    game = GhostRevolutionRun()

    assert game.set_combat_role("unknown", 1) is False
    assert game.set_combat_role("scouts", -1) is False

    game.followers = 1
    game.role_assignments["warriors"] = 1
    assert game.set_combat_role("scouts", 1) is False

    game = GhostRevolutionRun()
    game.followers = 3
    game.assignments["farmers"] = 3
    assert game.set_combat_role("scouts", 1) is False

    game.shield_stock.update({"light": 1, "medium": 2, "heavy": 3})
    assert game.shield_stock_total() == 6

    game.followers = 10
    assert game.set_combat_role("warriors", 5) is True
    assert game.plan_raid("ashfield") is not None
    assert game.set_raid_force(2) is True
    assert game.set_raid_shield_issue("light", 0) is True
    assert game.army_shields_issued() == 0
    game._release_raid_reservations()
    assert game.raid_plan is None

    with pytest.raises(ValueError, match="Unknown military camp"):
        game.military_camp("missing")
    with pytest.raises(ValueError, match="Unknown raid target"):
        game.raid_requirement("missing")
    with pytest.raises(ValueError, match="Unknown raid target"):
        game.raid_readiness("missing")


def test_demo_danger_travel_and_town_condition_matrix(monkeypatch):
    game = GhostRevolutionRun()
    game.location = "crownmarket"
    game.knight_town = "crownmarket"
    game.towns["crownmarket"]["locked"] = True
    assert game.danger_level() >= 6

    game.location = "castle"
    assert game.danger_level() >= 8

    game = GhostRevolutionRun()
    assert game.travel("missing") is False
    game.phase = "camp"
    assert game.travel("ashfield") is False
    game.phase = "rebellion"
    game.actions = 0
    assert game.travel("ashfield") is False

    castle = GhostRevolutionRun()
    castle.actions = 20
    assert castle.travel("castle") is True
    assert castle.heat == 2

    matrix = GhostRevolutionRun()
    trust = {"ashfield": 0.0, "millcross": 0.0, "crownmarket": 0.0}
    monkeypatch.setattr(matrix, "town_trust", lambda town_id: trust[town_id])

    matrix.towns["ashfield"]["locked"] = True
    assert matrix.town_condition("ashfield") == "LOCKED DOWN"
    matrix.towns["ashfield"]["locked"] = False

    matrix.knight_town = "ashfield"
    assert matrix.town_condition("ashfield") == "KNIGHT OCCUPIED"
    matrix.knight_town = "crownmarket"

    trust["millcross"] = -0.3
    assert matrix.town_condition("millcross") == "HOSTILE"

    trust["ashfield"] = 0.6
    assert matrix.town_condition("ashfield") == "SUPPORTIVE"
    trust["ashfield"] = 0.3
    assert matrix.town_condition("ashfield") == "FRIENDLY"
    trust["ashfield"] = -0.3
    assert matrix.town_condition("ashfield") == "WARY"


def test_demo_recruitment_limit_and_daily_cap_messages(monkeypatch):
    game = GhostRevolutionRun()
    monkeypatch.setattr(game, "town_trust", lambda _town_id: 0.6)
    game.towns["crownmarket"]["fear"] = 4
    game.knight_town = "crownmarket"

    assert game.recruitment_limit_today("crownmarket") == 1

    for category, fragment in (
        ("work", "already worked"),
        ("bar", "all it knows"),
        ("public_event", "another public event"),
    ):
        game.daily_activity["ashfield"][category] = True
        assert game._daily_cap_available("ashfield", category) is False
        assert fragment in game.last_action_note


def test_demo_scout_capture_and_crownmarket_risk_branches(monkeypatch):
    game = GhostRevolutionRun()
    game.towns["crownmarket"]["guard_roster"].clear()
    game.knight_town = "ashfield"
    game.towns["crownmarket"]["locked"] = True
    assert game._crownmarket_capture_risk() >= 30

    game = GhostRevolutionRun()
    game.scout_intel.update({"ashfield": 3, "millcross": 3, "crownmarket": 0})
    game.role_assignments["scouts"] = 1
    game.followers = 1
    monkeypatch.setattr(game.rng, "randint", lambda _a, _b: 1)

    reports = game._run_scout_reports()
    assert len(reports) == 1
    assert game.scouts_captured == 1
    assert game.role_assignments["scouts"] == 0
    assert game.followers == 0


def test_demo_public_event_denial_and_summary_paths():
    game = GhostRevolutionRun()
    game.phase = "camp"
    assert game.begin_public_event() is False

    game.phase = "rebellion"
    game.location = "base"
    assert game.begin_public_event() is False
    game.leave_public_event()
    assert game.public_event_action_available("speech") is False
    assert game.public_event_summary()["open"] is False

    game.location = "ashfield"
    game.towns["ashfield"]["locked"] = True
    assert game.begin_public_event() is False
    game.towns["ashfield"]["locked"] = False

    game.public_event_state["ashfield"]["completed"] = True
    assert game.begin_public_event() is False
    game.public_event_state["ashfield"]["completed"] = False

    game.leave_public_event()
    assert game.public_event_action_available("speech") is False

    assert game.begin_public_event() is True
    game.public_event_state["ashfield"]["used_actions"].add("speech")
    assert game.public_event_action_available("speech") is False


def test_demo_crownmarket_scout_can_return_without_capture(monkeypatch):
    game = GhostRevolutionRun()
    game.scout_intel.update({"ashfield": 3, "millcross": 3, "crownmarket": 0})
    game.role_assignments["scouts"] = 1
    game.followers = 1
    monkeypatch.setattr(game.rng, "randint", lambda _a, _b: 100)

    reports = game._run_scout_reports()

    assert len(reports) == 1
    assert game.scouts_captured == 0
    assert game.scout_intel["crownmarket"] == 1
