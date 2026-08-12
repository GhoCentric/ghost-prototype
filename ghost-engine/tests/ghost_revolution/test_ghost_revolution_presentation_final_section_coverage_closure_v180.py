from collections import deque
from types import SimpleNamespace

import ghost.examples.ghost_revolution.presentation as p


def _inputs(monkeypatch, values):
    it = iter(values)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(it))


class CrownGame:
    def __init__(self, *, king_fight=None, complete=False):
        self.king_fight = {"stage": "crown_loop"} if king_fight is None else king_fight
        self.complete = complete
        self.retired = False

    def crown_towns(self):
        return ["Ashfield", "Millcross", "Crownmarket"]

    def retire_crown(self):
        self.retired = True
        return {"ending": "retired"}


def test_final_crown_loop_all_choices_and_loop_guards(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(p, "_crown_town_menu", lambda game, events, town: calls.append(("town", town)))
    monkeypatch.setattr(p, "_print_crown_kingdom_stats", lambda game: calls.append(("stats", None)))
    monkeypatch.setattr(p, "print_endgame_packet", lambda packet: calls.append(("end", packet["ending"])))

    game = CrownGame()
    events = deque()
    _inputs(monkeypatch, ["1", "5", "x", "4"])
    p.crown_loop_menu(game, events)
    assert calls == [("town", "Ashfield"), ("stats", None), ("end", "retired")]
    assert list(events) == ["retired"]

    for guard_game in (
        CrownGame(king_fight=None),
        CrownGame(king_fight={"stage": "other"}),
        CrownGame(complete=True),
    ):
        if guard_game.king_fight == {"stage": "crown_loop"}:
            guard_game.king_fight = None
        p.crown_loop_menu(guard_game, deque())

    game = CrownGame()
    _inputs(monkeypatch, ["0"])
    p.crown_loop_menu(game, deque())
    assert "Unknown crown-loop choice." in capsys.readouterr().out


class SiegeGame:
    def __init__(
        self,
        *,
        label="Siege the Castle",
        armed=False,
        warning=None,
        followers=0,
        result=None,
        complete=False,
    ):
        self._label = label
        self.siege_armed = armed
        self._warning = warning or {
            "strength": 10,
            "minimum_required": 5,
            "strong_threshold": 8,
            "reaches_king": True,
            "wounded_start": False,
            "prepared_assault": False,
        }
        self.followers = followers
        self._result = result or {"outcome": "failed", "score": 1, "ending": "failed"}
        self.complete = complete
        self.last_action_note = "siege note"

    def endgame_action_label(self):
        return self._label

    def siege_warning(self):
        return dict(self._warning)

    def siege_castle(self):
        return dict(self._result)


def test_final_siege_menu_all_warning_and_resolution_paths(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(p, "crown_loop_menu", lambda game, events: calls.append("crown"))
    monkeypatch.setattr(p, "siege_animation", lambda game: calls.append("animation"))
    monkeypatch.setattr(p, "king_fight_menu", lambda game, events: calls.append("fight"))

    p.siege_menu(SiegeGame(label="Retire the Crown"), deque())

    p.siege_menu(
        SiegeGame(
            warning={
                "strength": 3,
                "minimum_required": 5,
                "strong_threshold": 8,
                "reaches_king": False,
                "wounded_start": True,
                "prepared_assault": False,
            },
            followers=2,
        ),
        deque(),
    )

    p.siege_menu(
        SiegeGame(
            warning={
                "strength": 9,
                "minimum_required": 5,
                "strong_threshold": 8,
                "reaches_king": True,
                "wounded_start": False,
                "prepared_assault": True,
            },
            followers=0,
        ),
        deque(),
    )

    p.siege_menu(
        SiegeGame(
            warning={
                "strength": 6,
                "minimum_required": 5,
                "strong_threshold": 8,
                "reaches_king": True,
                "wounded_start": False,
                "prepared_assault": False,
            },
            followers=0,
        ),
        deque(),
    )

    fight_result = {
        "outcome": "king_confrontation_started",
        "score": 9,
        "player_health": 10,
        "player_max_health": 12,
        "castle_timer": 7,
        "tell": "tell",
    }
    events = deque()
    p.siege_menu(SiegeGame(armed=True, result=fight_result, complete=False), events)
    assert calls.count("fight") == 1
    assert "The rebellion launched the final siege." in events

    p.siege_menu(SiegeGame(armed=True, result=fight_result, complete=True), deque())
    p.siege_menu(
        SiegeGame(
            armed=True,
            result={"outcome": "failed", "score": 1, "ending": "over"},
        ),
        deque(),
    )

    out = capsys.readouterr().out
    assert "SIEGE RESULT" in out and "KING FIGHT STARTED" in out


def test_final_intro_day_report_and_final_result_all_branches(capsys):
    p.print_intro()

    game = SimpleNamespace(food=5, phase_day=2)
    p.print_day_report(game, {})
    p.print_day_report(
        game,
        {
            "day_report": {
                "starved": True,
                "food_used": 4,
                "food_before": 1,
                "followers_fed": 0,
            }
        },
    )
    p.print_day_report(
        game,
        {
            "phase_change": "camp",
            "day_report": {
                "starved": False,
                "food_used": 2,
                "followers_fed": 3,
            },
        },
    )
    p.print_day_report(
        game,
        {
            "phase_change": None,
            "day_report": {
                "starved": False,
                "food_used": 1,
                "leader_fed": 1,
                "followers_fed": 2,
            },
        },
    )

    base = dict(
        followers=3,
        food=4,
        gold=5,
        weapons=6,
        armor=7,
        king_control=8,
        guards_defeated=9,
    )
    p.print_final_result(SimpleNamespace(**base, ending="victory", quit_game=False))
    p.print_final_result(SimpleNamespace(**base, ending=None, quit_game=True))
    p.print_final_result(SimpleNamespace(**base, ending=None, quit_game=False))

    out = capsys.readouterr().out
    assert "REBELLION STARVES" in out
    assert "Camp phase begins." in out
    assert "Campaign paused by player." in out
    assert "Campaign remains unresolved." in out


class RunGame:
    instances = []

    def __init__(self):
        type(self).instances.append(self)
        self.phase = "rebellion"
        self.king_fight = None
        self.quit_game = False
        self.siege_armed = True
        self.gold = 1
        self.followers = 2
        self.alive = True
        self.phase_day = 1
        self.end_day_calls = 0

    @property
    def complete(self):
        return self.quit_game

    def available_warriors(self):
        return 1

    def endgame_action_label(self):
        return "Siege the Castle"

    def end_day(self):
        self.end_day_calls += 1
        if self.end_day_calls == 1:
            self.phase = "camp"
            return {
                "phase_change": "camp",
                "day_report": {
                    "starved": False,
                    "food_used": 1,
                    "followers_fed": 2,
                    "scout_reports": ["scout one"],
                },
            }
        if self.end_day_calls == 2:
            self.alive = True
            return {
                "phase_change": None,
                "day_report": {
                    "starved": False,
                    "food_used": 2,
                    "followers_fed": 1,
                    "scout_reports": [],
                },
            }
        self.alive = False
        return {
            "phase_change": None,
            "day_report": {
                "starved": False,
                "food_used": 3,
                "followers_fed": 0,
                "scout_reports": [],
            },
        }


def test_final_run_presentation_main_dispatch_and_day_end_paths(monkeypatch):
    calls = []
    RunGame.instances.clear()
    monkeypatch.setattr(p, "GhostRevolutionRun", RunGame)
    monkeypatch.setattr(p, "print_intro", lambda: calls.append("intro"))
    monkeypatch.setattr(p, "render_status", lambda game: "status")
    monkeypatch.setattr(p, "print_recent_events", lambda events: calls.append("recent"))
    monkeypatch.setattr(p, "action_summary", lambda game: "actions")
    monkeypatch.setattr(p, "kingdom_map_menu", lambda game, events: calls.append("map"))
    monkeypatch.setattr(p, "enter_current_location", lambda game, events: calls.append("enter"))
    monkeypatch.setattr(p, "scout_intel_menu", lambda game, events: calls.append("scout"))
    monkeypatch.setattr(p, "siege_menu", lambda game, events: calls.append("siege"))
    monkeypatch.setattr(p, "print_day_report", lambda game, result: calls.append(("day", result.get("phase_change"))))
    monkeypatch.setattr(p, "print_legend", lambda: calls.append("legend"))
    monkeypatch.setattr(p, "print_final_result", lambda game: calls.append("final"))

    def camp_menu(game, events):
        calls.append("camp")
        game.phase = "rebellion"

    monkeypatch.setattr(p, "camp_menu", camp_menu)

    _inputs(monkeypatch, ["1", "@", "3", "4", "5", "5", "5", "6", "bad", "0"])
    p.run_presentation()

    game = RunGame.instances[-1]
    assert game.end_day_calls == 3
    assert calls.count("map") == 1
    assert calls.count("enter") == 1
    assert calls.count("scout") == 1
    assert calls.count("siege") == 1
    assert calls.count("camp") == 1
    assert calls.count("legend") == 1
    assert calls[-1] == "final"


class SpecialRunGame(RunGame):
    mode = "camp"

    def __init__(self):
        super().__init__()
        if type(self).mode == "camp":
            self.phase = "camp"
        elif type(self).mode == "fight":
            self.king_fight = {"stage": "king_phase_one"}


def test_final_run_presentation_camp_fight_and_initial_complete_paths(monkeypatch):
    calls = []

    monkeypatch.setattr(p, "print_intro", lambda: calls.append("intro"))
    monkeypatch.setattr(p, "print_final_result", lambda game: calls.append("final"))

    SpecialRunGame.mode = "camp"
    monkeypatch.setattr(p, "GhostRevolutionRun", SpecialRunGame)
    def camp_exit(game, events):
        calls.append("camp")
        game.quit_game = True
    monkeypatch.setattr(p, "camp_menu", camp_exit)
    p.run_presentation()

    SpecialRunGame.mode = "fight"
    monkeypatch.setattr(p, "GhostRevolutionRun", SpecialRunGame)
    def fight_exit(game, events):
        calls.append("fight")
        game.quit_game = True
    monkeypatch.setattr(p, "king_fight_menu", fight_exit)
    p.run_presentation()

    class CompleteGame(SpecialRunGame):
        def __init__(self):
            super().__init__()
            self.quit_game = True
            self.phase = "rebellion"
            self.king_fight = None

    monkeypatch.setattr(p, "GhostRevolutionRun", CompleteGame)
    p.run_presentation()

    assert calls.count("camp") == 1
    assert calls.count("fight") == 1
    assert calls.count("final") == 3
