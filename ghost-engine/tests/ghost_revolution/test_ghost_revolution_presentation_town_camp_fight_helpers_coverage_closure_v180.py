"""Coverage closure candidate for presentation.py town/camp/fight-helper section."""

from __future__ import annotations

from collections import deque

import ghost.examples.ghost_revolution.presentation as p
import ghost.examples.ghost_revolution.llm_bridge as llm


class BaseGame:
    complete = False
    phase = "rebellion"
    actions = 6
    gold = 20
    followers = 5
    last_action_note = "note"


def _inputs(monkeypatch, values):
    it = iter(values)
    monkeypatch.setattr("builtins.input", lambda _="": next(it))


def _quiet(monkeypatch):
    monkeypatch.setattr(p, "panel", lambda title, lines: title + ":" + "|".join(map(str, lines)))
    monkeypatch.setattr(p, "action_summary", lambda game: "actions")
    monkeypatch.setattr(p, "print_ghost_packet", lambda packet: None)


def test_bar_public_event_town_arrival_and_enter_paths(monkeypatch):
    _quiet(monkeypatch)
    resolved = []
    monkeypatch.setattr(
        p,
        "resolve_town_packet",
        lambda game, events, packet, action, event: resolved.append((packet, event)),
    )

    class BarGame(BaseGame):
        location = "ashfield"
        towns = {"ashfield": {"name": "Ashfield"}}

        def bar_rumor(self):
            return {"kind": "rumor"}

        def bar_recruit_quietly(self):
            return {"kind": "recruit"}

        def bar_local_work(self):
            self.last_action_note = "work note"
            return {"kind": "work"}

    game = BarGame()
    _inputs(monkeypatch, ["1", "2", "3", "4", "bad", "0"])
    p.bar_menu(game, deque())
    assert [item[0]["kind"] for item in resolved] == ["rumor", "recruit", "rumor", "work"]

    done = BarGame()
    done.complete = True
    p.bar_menu(done, deque())

    class EventGame(BarGame):
        def __init__(self, begin=True):
            self.begin = begin
            self.leave_calls = 0
            self.used = {"speech"}

        def begin_public_event(self):
            if not self.begin:
                self.last_action_note = "event blocked"
            return self.begin

        def public_event_summary(self):
            return {"used_actions": self.used}

        def leave_public_event(self):
            self.leave_calls += 1
            self.last_action_note = "left event"

        def speak_publicly(self):
            return {"kind": "speech"}

        def recruit_openly(self):
            return {"kind": "open-recruit"}

        def rally_people(self):
            return {"kind": "rally"}

    blocked = EventGame(False)
    blocked_events = deque()
    p.public_event_menu(blocked, blocked_events)
    assert list(blocked_events) == ["event blocked"]

    event = EventGame(True)
    _inputs(monkeypatch, ["1", "2", "3", "bad", "0"])
    p.public_event_menu(event, deque())
    assert event.leave_calls == 1

    done_event = EventGame(True)
    done_event.complete = True
    p.public_event_menu(done_event, deque())

    calls = []
    for name in (
        "blacksmith_menu", "food_menu", "goods_menu", "middle_of_town_menu",
        "bar_menu", "public_event_menu", "hidden_base_menu",
    ):
        monkeypatch.setattr(p, name, lambda game, events, name=name: calls.append(name))
    monkeypatch.setattr(p, "town_status_label", lambda game, town_id: "stable")
    monkeypatch.setattr(p, "town_role_icon", lambda town_id: "[X]")

    class TownGame(BaseGame):
        location = "ashfield"
        towns = {"ashfield": {"name": "Ashfield"}}

        def recruitment_available_today(self, town_id):
            return 2

    town = TownGame()
    _inputs(monkeypatch, ["1", "2", "3", "4", "5", "6", "bad", "0"])
    p.town_arrival_menu(town, deque())
    assert calls[:6] == [
        "blacksmith_menu", "food_menu", "goods_menu", "middle_of_town_menu",
        "bar_menu", "public_event_menu",
    ]

    town.complete = True
    p.town_arrival_menu(town, deque())

    monkeypatch.setattr(p, "town_arrival_menu", lambda game, events: calls.append("town_arrival"))

    base = TownGame()
    base.location = "base"
    p.enter_current_location(base, deque())

    town2 = TownGame()
    p.enter_current_location(town2, deque())

    other = TownGame()
    other.location = "castle"
    events = deque()
    p.enter_current_location(other, events)
    assert list(events) == ["Current location has no enterable menu."]


def test_scout_intel_empty_and_populated(monkeypatch, capsys):
    _quiet(monkeypatch)

    class Game:
        def __init__(self, reports, beliefs):
            self.reports = reports
            self.beliefs = beliefs

        def scout_report_summary(self):
            return {
                "last_reports": self.reports,
                "information": {"latest_scout_beliefs": self.beliefs},
                "assigned_scouts": 2,
                "reports_today": 1,
                "scouts_captured": 0,
                "intel": {"ashfield": 1, "millcross": 2, "crownmarket": 3},
                "crownmarket_capture_risk": 25,
            }

    p.scout_intel_menu(Game([], {}), deque())
    p.scout_intel_menu(
        Game(
            ["report"],
            {"millcross": {"dominant_candidate": "royal_weak", "confidence": 0.75}},
        ),
        deque(),
    )
    out = capsys.readouterr().out
    assert "SCOUT REPORTS" in out


def test_kingdom_map_cancel_invalid_success_and_failure(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(p, "render_map", lambda game: "map")
    travels = []
    entries = []
    monkeypatch.setattr(p, "travel_animation", lambda origin, destination, cost: travels.append((origin, destination, cost)))
    monkeypatch.setattr(p, "town_arrival_menu", lambda game, events: entries.append("town"))
    monkeypatch.setattr(p, "hidden_base_menu", lambda game, events: entries.append("base"))

    class Game(BaseGame):
        def __init__(self, location="ashfield", succeeds=True):
            self.location = location
            self.towns = {"ashfield": {}, "millcross": {}, "crownmarket": {}}
            self.succeeds = succeeds

        def travel_cost(self, destination):
            return 1 if destination == "millcross" else 2

        def travel(self, destination):
            if self.succeeds:
                self.location = destination
                return True
            return False

    monkeypatch.setattr(p, "LOCATIONS", ("base", "ashfield", "millcross", "castle"))

    _inputs(monkeypatch, ["0"])
    p.kingdom_map_menu(Game(), deque())

    events = deque()
    _inputs(monkeypatch, ["bad"])
    p.kingdom_map_menu(Game(), events)
    assert list(events) == ["Invalid kingdom-map choice."]

    _inputs(monkeypatch, ["99"])
    p.kingdom_map_menu(Game(), deque())

    _inputs(monkeypatch, ["2"])
    p.kingdom_map_menu(Game("ashfield"), deque())

    _inputs(monkeypatch, ["1"])
    p.kingdom_map_menu(Game("ashfield"), deque())

    _inputs(monkeypatch, ["3"])
    p.kingdom_map_menu(Game("ashfield"), deque())

    failed = Game("ashfield", succeeds=False)
    events = deque()
    _inputs(monkeypatch, ["2"])
    p.kingdom_map_menu(failed, events)
    assert list(events) == ["Travel attempt failed."]
    assert travels and "town" in entries and "base" in entries


def test_camp_menu_all_actions_and_boundaries(monkeypatch):
    _quiet(monkeypatch)
    legend_calls = []
    response_calls = []
    monkeypatch.setattr(p, "camp_phase_card", lambda game: None)
    monkeypatch.setattr(p, "print_legend", lambda: legend_calls.append(True))
    monkeypatch.setattr(p, "king_response_card", lambda events: response_calls.append(tuple(events)))

    class Game(BaseGame):
        phase = "camp"
        actions = 3

        def __init__(self):
            self.complete = False
            self._quit_game = False
            self.assignments = {"farmers": 0, "foragers": 0, "trainers": 0, "smiths": 0, "scouts": 0}
            self.assign_calls = 0
            self.train_calls = 0
            self.end_calls = 0

        @property
        def quit_game(self):
            return self._quit_game

        @quit_game.setter
        def quit_game(self, value):
            self._quit_game = value
            if value:
                self.complete = True

        def available_workers(self):
            return 5

        def set_assignment(self, role, amount):
            self.assign_calls += 1
            self.assignments[role] = amount
            return self.assign_calls % 2 == 1

        def train_rebels(self):
            self.train_calls += 1
            return self.train_calls == 1

        def end_day(self):
            self.end_calls += 1
            if self.end_calls == 1:
                return {
                    "camp_output": {"food_gain": 1, "gold_gain": 2, "weapon_gain": 3},
                    "king_response": ["king acts"],
                }
            return {"camp_output": None, "king_response": []}

    game = Game()
    events = deque()
    _inputs(monkeypatch, [
        "1", "bad",
        "1", "2",
        "2", "3",
        "6", "6",
        "7", "7",
        "8", "bad", "0",
    ])
    p.camp_menu(game, events)
    assert game.quit_game is True
    assert legend_calls == [True]
    assert response_calls == [("king acts",)]
    assert "king acts" in events

    done = Game()
    done.complete = True
    p.camp_menu(done, deque())


def test_endgame_labels_moves_env_and_mocking(monkeypatch, capsys):
    _quiet(monkeypatch)
    p.print_endgame_packet(None)
    p.print_endgame_packet({})
    p.print_endgame_packet({
        "outcome": "fight",
        "stage": "king_phase_one",
        "castle_timer": 8,
        "player_health": 9,
        "king_health": 7,
        "elite_knight_health": 6,
        "exchange": {"result": "hit", "message": "message"},
        "choices": ("execute", "jail"),
        "tell": "tell",
        "note": "note",
        "ending": "ending",
        "wounded_start_explanation": ["w1", 2],
        "developer_cause": ["d1", 3],
    })
    assert p.king_fight_stage_label("king_phase_one") == "King Fight — Phase One"
    assert p.king_fight_stage_label("custom_stage") == "Custom Stage"
    assert p._king_fight_move_from_choice("1") == "heavy"
    assert p._king_fight_move_from_choice("x") is None

    monkeypatch.delenv("GHOST_REAL_LLM", raising=False)
    monkeypatch.delenv("GHOST_DEV_LLM_NARRATION", raising=False)
    assert p._king_fight_llm_enabled() is False
    monkeypatch.setenv("GHOST_DEV_LLM_NARRATION", "1")
    assert p._king_fight_llm_enabled() is True
    monkeypatch.setenv("GHOST_REAL_LLM", "1")
    assert p._king_fight_llm_enabled() is True

    p._print_king_fight_mocking_lines(None)
    p._print_king_fight_mocking_lines({})
    p._print_king_fight_mocking_lines({"king_mocking_lines": "bad"})
    p._print_king_fight_mocking_lines({"king_mocking_lines": ["", "   "]})
    p._print_king_fight_mocking_lines({"king_mocking_lines": [" one ", "", 2]})
    assert "THE KING'S FINAL WORD" in capsys.readouterr().out


def test_king_fight_llm_narration_real_dev_debug_and_failure(monkeypatch, capsys):
    _quiet(monkeypatch)
    monkeypatch.setattr(p, "_record_llm_measured_cost", lambda role, result: None)
    monkeypatch.setattr(p, "_measured_cost_lines", lambda result, role: ["cost"])
    monkeypatch.setattr(llm, "OpenAIResponsesClient", lambda: object())
    monkeypatch.setattr(llm, "config_for_role", lambda role: {"role": role})
    monkeypatch.setattr(
        llm,
        "generate_king_fight_adapter_fallback_narration",
        lambda packet: {"text": "fallback", "provider_called": False, "provider": "fallback"},
    )

    class Bridge:
        fail = False

        def __init__(self, client, config):
            pass

        def generate_king_fight_narration(self, packet):
            if type(self).fail:
                raise RuntimeError("boom")
            return {
                "text": "real",
                "cost_estimate": {"model": "estimate-model"},
                "provider_called": True,
                "response_model": None,
            }

    monkeypatch.setattr(llm, "GhostRevolutionLLMBridge", Bridge)

    monkeypatch.setenv("GHOST_REAL_LLM", "1")
    monkeypatch.delenv("GHOST_DEV_LLM_NARRATION", raising=False)
    monkeypatch.delenv("GHOST_LLM_DEBUG", raising=False)
    p._print_king_fight_llm_narration({"outcome": "x"})

    monkeypatch.setenv("GHOST_LLM_DEBUG", "1")
    p._print_king_fight_llm_narration({"outcome": "x"})

    Bridge.fail = True
    monkeypatch.delenv("GHOST_LLM_DEBUG", raising=False)
    p._print_king_fight_llm_narration({"outcome": "x"})
    monkeypatch.setenv("GHOST_LLM_DEBUG", "1")
    p._print_king_fight_llm_narration({"outcome": "x"})

    Bridge.fail = False
    monkeypatch.delenv("GHOST_REAL_LLM", raising=False)
    monkeypatch.setenv("GHOST_DEV_LLM_NARRATION", "1")
    monkeypatch.delenv("GHOST_LLM_DEBUG", raising=False)
    p._print_king_fight_llm_narration({"outcome": "x"})
    monkeypatch.setenv("GHOST_LLM_DEBUG", "1")
    p._print_king_fight_llm_narration({"outcome": "x"})

    monkeypatch.delenv("GHOST_DEV_LLM_NARRATION", raising=False)
    p._print_king_fight_llm_narration({"outcome": "x"})
    assert "REAL LLM FIGHT BEAT" in capsys.readouterr().out


def test_scene_helpers_stats_profiles_packets_and_final_detection():
    assert p._king_fight_scene_reason_for_stage("king_phase_one") == "phase_one_start"
    assert p._king_fight_scene_reason_for_stage("elite_knight") == "elite_knight_start"
    assert p._king_fight_scene_reason_for_stage("king_phase_two") == "phase_two_start"
    assert p._king_fight_scene_reason_for_stage("other") is None

    class Seen:
        pass

    seen = Seen()
    assert p._king_fight_scene_seen(seen, "a") is False
    assert p._king_fight_scene_seen(seen, "a") is True

    class StatsGood:
        def _final_kingdom_stats(self):
            return {"followers": 8}

    class StatsBad:
        def _final_kingdom_stats(self):
            raise RuntimeError("bad")

    class StatsWrong:
        def _final_kingdom_stats(self):
            return []

    class NoStats:
        _final_kingdom_stats = None

    assert p._king_fight_kingdom_stats(StatsGood()) == {"followers": 8}
    assert p._king_fight_kingdom_stats(StatsBad()) == {}
    assert p._king_fight_kingdom_stats(StatsWrong()) == {}
    assert p._king_fight_kingdom_stats(NoStats()) == {}

    class ProfileStats:
        followers = 99

        def _final_kingdom_stats(self):
            return {
                "followers": 10,
                "weapon_caches": 2,
                "armor": 3,
                "guards_defeated": 4,
                "heat": 5,
                "king_control": 6,
                "prepared_assault": True,
                "wounded_start": False,
                "likely_success": True,
                "strength": 42,
                "estimated_arms": 11,
            }

    profile = p._king_fight_player_profile(ProfileStats())
    assert profile["strength"] == 42 and profile["estimated_arms"] == 11

    class MethodProfile:
        followers = 5
        weapon_caches = 1
        armor = 1
        guards_defeated = 1
        heat = 2
        king_control = 4
        prepared_assault = "yes"
        wounded_start = "no"
        likely_success = None
        estimated_arms = None

        def _final_kingdom_stats(self):
            return {"followers": True, "prepared_assault": None}

        def siege_strength(self):
            raise TypeError("signature")

        _siege_strength = "not callable"

        def calculate_siege_strength(self):
            return "bad"

        def _calculate_siege_strength(self):
            return 33

    profile = p._king_fight_player_profile(MethodProfile())
    assert profile["strength"] == 33 and profile["followers"] == 5

    class FallbackProfile:
        followers = 5
        weapon_caches = 2
        armor = 1
        guards_defeated = 3
        heat = True
        king_control = 8
        prepared_assault = None
        wounded_start = None
        likely_success = None

    fallback = p._king_fight_player_profile(FallbackProfile())
    assert fallback["strength"] == 19
    assert "heat" not in fallback and "estimated_arms" not in fallback

    class LowControlProfile:
        followers = 1
        weapon_caches = 0
        armor = 0
        guards_defeated = 0
        king_control = 4

    low = p._king_fight_player_profile(LowControlProfile())
    assert low["strength"] == 1

    status = {"stage": "elite_knight", "tell": "watch", "player_health": 8}
    packet = p._king_fight_scene_packet_from_status(ProfileStats(), status, "elite_knight_start")
    assert packet["upcoming_tell"] == "watch" and packet["tell"] is None

    for outcome in (
        "player_death", "player_killed_by_king", "clean_king_victory",
        "last_breath_king_victory", "uncertain_king_fall", "castle_collapse",
    ):
        assert p._king_fight_packet_is_final_scene({"outcome": outcome}) is True
    assert p._king_fight_packet_is_final_scene({"outcome": "other", "ending": "done"}) is True
    assert p._king_fight_packet_is_final_scene({"outcome": "other"}) is False
