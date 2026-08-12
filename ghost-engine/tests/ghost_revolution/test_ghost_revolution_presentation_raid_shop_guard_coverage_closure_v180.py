"""Coverage closure candidate for presentation.py raid/shop/guard section."""

from __future__ import annotations

from collections import deque

import ghost.examples.ghost_revolution.presentation as p


class BaseGame:
    complete = False
    phase = "rebellion"
    actions = 6
    last_action_note = ""


def _inputs(monkeypatch, values):
    it = iter(values)
    monkeypatch.setattr("builtins.input", lambda _="": next(it))


def _quiet(monkeypatch):
    monkeypatch.setattr(p, "panel", lambda title, lines: title)
    monkeypatch.setattr(p, "action_summary", lambda game: "actions")
    monkeypatch.setattr(p, "print_ghost_packet", lambda packet: None)


def test_raid_preparation_all_choices_and_loop_boundaries(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(p, "raid_plan_panel", lambda game, target: None)

    class Game(BaseGame):
        location = "base"
        raid_plan = {"target": "ashfield"}
        last_action_note = "raid note"

        def raid_readiness(self, target):
            return {
                "town": target,
                "recommended_warriors": 25,
                "warriors": 10,
                "available_warriors": 20,
                "weapon_stock": {"sword": 2},
                "shield_stock": {"light": 1},
            }

        def set_raid_force(self, amount):
            return False

        def set_raid_weapon_issue(self, weapon, amount):
            return True

        def set_raid_shield_issue(self, shield, amount):
            return True

        def cancel_raid_plan(self):
            return True

        def commit_raid(self):
            return True

    game = Game()
    events = deque(maxlen=6)
    _inputs(
        monkeypatch,
        [
            "1", "bad",
            "1", "3",
            "2", "bad",
            "2", "2",
            "6", "bad",
            "6", "1",
            "9",
            "10",
            "11",
            "wat",
            "0",
        ],
    )
    p.raid_preparation_menu(game, events, "ashfield")
    assert events

    done = Game()
    done.complete = True
    p.raid_preparation_menu(done, deque(), "ashfield")


def test_raid_town_menu_all_paths(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(p, "active_raid_panel", lambda game: None)
    prep_calls = []
    monkeypatch.setattr(
        p,
        "raid_preparation_menu",
        lambda game, events, target: prep_calls.append(target),
    )

    class Game(BaseGame):
        location = "base"
        active_raid = None
        food = 10
        weapon_stock = {"sword": 1}
        shield_stock = {"light": 1}
        last_action_note = "planned"

        def role_summary(self):
            return {"warriors": 8, "deployed_warriors": 0}

        def leader_weapon_label(self):
            return "Sword"

        def plan_raid(self, target):
            if target == "millcross":
                return None
            return {"town": target}

    active = Game()
    active.active_raid = {"town": "ashfield"}
    p.raid_town_menu(active, deque())

    game = Game()
    _inputs(monkeypatch, ["wat", "2", "1", "0"])
    p.raid_town_menu(game, deque())
    assert prep_calls == ["ashfield"]

    done = Game()
    done.complete = True
    p.raid_town_menu(done, deque())


def test_shop_menus_cover_invalid_success_failure_and_exit(monkeypatch):
    _quiet(monkeypatch)

    class ShopGame(BaseGame):
        def __init__(self):
            self.complete = False
            self.phase = "rebellion"
            self.actions = 6
            self.last_action_note = "merchant note"
            self.black_calls = 0
            self.food_calls = 0
            self.goods_calls = 0

        def blacksmith_buy(self, item):
            self.black_calls += 1
            if self.black_calls == 2:
                self.last_action_note = ""
            return self.black_calls >= 3

        def buy_food(self, item):
            self.food_calls += 1
            if self.food_calls == 2:
                self.last_action_note = ""
            return self.food_calls >= 3

        def buy_common_goods(self, item):
            self.goods_calls += 1
            if self.goods_calls == 2:
                self.last_action_note = ""
            return self.goods_calls >= 3

    game = ShopGame()
    _inputs(monkeypatch, ["wat", "1", "2", "3", "0"])
    p.blacksmith_menu(game, deque())
    assert game.black_calls == 3

    game = ShopGame()
    _inputs(monkeypatch, ["wat", "1", "2", "3", "0"])
    p.food_menu(game, deque())
    assert game.food_calls == 3

    game = ShopGame()
    _inputs(monkeypatch, ["wat", "1", "2", "1", "0"])
    p.goods_menu(game, deque())
    assert game.goods_calls == 3

    complete = ShopGame()
    complete.complete = True
    p.blacksmith_menu(complete, deque())
    p.food_menu(complete, deque())
    p.goods_menu(complete, deque())


def _down_status(conduct=2, witnesses=3):
    return {
        "stage": "down",
        "conduct": conduct,
        "witnesses": witnesses,
    }


def test_guard_down_menu_all_status_conduct_and_outcomes(monkeypatch):
    _quiet(monkeypatch)

    class DownGame(BaseGame):
        def __init__(self, status, packet=None, note="down note"):
            self._status = status
            self.guard_combat = object()
            self.complete = False
            self.last_action_note = note
            self.packet = packet

        def guard_combat_status(self):
            return self._status

        def resolve_guard_down(self, choice):
            return self.packet

    p.guard_down_menu(DownGame(None), deque())
    p.guard_down_menu(DownGame({"stage": "active"}), deque())

    _inputs(monkeypatch, ["bad", "1"])
    events = deque()
    p.guard_down_menu(
        DownGame(_down_status(2, 9), packet={"ok": True}),
        events,
    )
    assert list(events) == ["down note"]

    _inputs(monkeypatch, ["2"])
    p.guard_down_menu(
        DownGame(_down_status(0, 0), packet=None, note=""),
        deque(),
    )

    _inputs(monkeypatch, ["1"])
    p.guard_down_menu(
        DownGame(_down_status(-1, 3), packet=None),
        deque(),
    )

    game = DownGame(_down_status(2))
    game.complete = True
    p.guard_down_menu(game, deque())


class CombatGame(BaseGame):
    def __init__(self, free_attack=False, start=True):
        self.complete = False
        self.phase = "rebellion"
        self.actions = 6
        self.guard_combat = object() if start else None
        self.last_action_note = ""
        self.free_attack = free_attack
        self.moves = []

    def fight_guard(self):
        self.guard_combat = object()
        return {"started": True}

    def guard_combat_status(self):
        return {
            "stage": "active",
            "guard_label": "Guard",
            "guards_remaining": 1,
            "player_health": 10,
            "player_max_health": 10,
            "guard_health": 8,
            "guard_max_health": 8,
            "exchange_count": 1,
            "combat_noise": 0,
            "guard_tell": "steady",
            "free_attack": self.free_attack,
        }

    def resolve_guard_combat_move(self, move):
        self.moves.append(move)
        self.last_action_note = "move note" if len(self.moves) % 2 else ""
        return {"move": move} if len(self.moves) % 2 else None

    def retreat_guard_combat(self):
        self.guard_combat = None
        return {"retreat": True}


def test_guard_combat_menu_entry_status_moves_and_free_attack(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(p, "guard_down_menu", lambda game, events: None)

    class NoStart(CombatGame):
        def fight_guard(self):
            self.last_action_note = ""
            return None

    no_start = NoStart(start=False)
    p.guard_combat_menu(no_start, deque())

    start = CombatGame(start=False)
    _inputs(monkeypatch, ["0"])
    p.guard_combat_menu(start, deque())

    status_none = CombatGame()
    status_none.guard_combat_status = lambda: None
    p.guard_combat_menu(status_none, deque())

    down = CombatGame()
    down.guard_combat_status = lambda: _down_status()
    p.guard_combat_menu(down, deque())

    game = CombatGame(free_attack=False)
    _inputs(
        monkeypatch,
        [
            "3", "0",
            "3", "bad",
            "3", "1",
            "3", "2",
            "4",
            "5",
            "6",
            "1",
            "2",
            "bad",
            "0",
        ],
    )
    p.guard_combat_menu(game, deque())
    assert set(game.moves) >= {
        "feint_heavy", "feint_light", "parry", "deflect",
        "dodge", "heavy", "light",
    }

    free = CombatGame(free_attack=True)
    _inputs(monkeypatch, ["4", "1", "0"])
    p.guard_combat_menu(free, deque())

    complete = CombatGame()
    complete.complete = True
    p.guard_combat_menu(complete, deque())


def _guard_game(active=True, passage=False):
    class GuardGame(BaseGame):
        location = "millcross"
        towns = {"millcross": {"name": "Millcross", "fear": 1}}
        royal_alert = 1
        actions = 6
        last_action_note = "guard note"
        complete = False

        def __init__(self):
            self.active = active

        def has_active_guard(self, town):
            return self.active

        def guard_passage_active(self, town):
            return passage

        def town_trust(self, town):
            return 0.0

        def town_memory_label(self, town):
            return "quiet"

        def guard_count(self, town):
            return 1

        def active_guard_label(self, town):
            return "Guard"

        def question_guard(self):
            return {"question": True}

        def bribe_guard(self):
            return None

        def recruit_guard(self):
            self.active = False
            return {"recruit": True}

    return GuardGame()


def test_guard_encounter_menu_all_paths(monkeypatch):
    _quiet(monkeypatch)

    outside = _guard_game()
    outside.location = "base"
    p.guard_encounter_menu(outside, deque())

    p.guard_encounter_menu(_guard_game(active=False), deque())

    _inputs(monkeypatch, ["0"])
    p.guard_encounter_menu(_guard_game(), deque())

    passage = _guard_game(passage=True)
    _inputs(monkeypatch, ["4", "0"])
    p.guard_encounter_menu(passage, deque())

    game = _guard_game()
    _inputs(monkeypatch, ["bad", "1", "2", "3"])
    p.guard_encounter_menu(game, deque())

    calls = []
    def combat_leave(game, events):
        calls.append("combat")
        game.active = False
    monkeypatch.setattr(p, "guard_combat_menu", combat_leave)
    game = _guard_game()
    _inputs(monkeypatch, ["4"])
    p.guard_encounter_menu(game, deque())

    def combat_keep(game, events):
        calls.append("combat-keep")
    monkeypatch.setattr(p, "guard_combat_menu", combat_keep)
    game = _guard_game()
    _inputs(monkeypatch, ["4", "0"])
    p.guard_encounter_menu(game, deque())

    done = _guard_game()
    done.complete = True
    p.guard_encounter_menu(done, deque())
    assert calls == ["combat", "combat-keep"]


def _middle_game(active_guard=False):
    class MiddleGame(BaseGame):
        location = "ashfield"
        towns = {"ashfield": {"name": "Ashfield"}}
        royal_alert = 1
        actions = 6
        last_action_note = ""
        complete = False

        def has_active_guard(self, town):
            return active_guard

        def town_memory_label(self, town):
            return "quiet"

        def recruit_quietly(self):
            return {"recruit": True}

        def seize_royal_supplies(self):
            self.last_action_note = "seized"
            return {"seize": True}

        def bribe_network(self):
            return None

        def earn_honest_gold(self):
            self.last_action_note = "worked"
            return {"work": True}

    return MiddleGame()


def test_middle_of_town_and_resolve_packet_paths(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(p, "scout_intel_menu", lambda game, events: None)
    monkeypatch.setattr(p, "guard_encounter_menu", lambda game, events: None)

    outside = _middle_game()
    outside.location = "base"
    p.middle_of_town_menu(outside, deque())

    _inputs(monkeypatch, ["0"])
    p.middle_of_town_menu(_middle_game(), deque())

    no_guard = _middle_game(active_guard=False)
    _inputs(monkeypatch, ["3", "bad", "1", "2", "4", "5", "6", "0"])
    p.middle_of_town_menu(no_guard, deque())

    with_guard = _middle_game(active_guard=True)
    _inputs(monkeypatch, ["3", "0"])
    p.middle_of_town_menu(with_guard, deque())

    game = _middle_game()
    game.last_action_note = "explicit"
    p.resolve_town_packet(game, deque(), None, "a", "e")

    game.last_action_note = ""
    game.actions = 0
    p.resolve_town_packet(game, deque(), None, "a", "e")

    game.actions = 2
    p.resolve_town_packet(game, deque(), None, "a", "e")

    events = deque()
    p.resolve_town_packet(game, events, {"ok": True}, "action", "event")
    assert list(events) == ["event"]

    done = _middle_game()
    done.complete = True
    p.middle_of_town_menu(done, deque())
