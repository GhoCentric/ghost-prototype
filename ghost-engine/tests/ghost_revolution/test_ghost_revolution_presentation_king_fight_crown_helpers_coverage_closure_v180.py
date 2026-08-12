from __future__ import annotations

from collections import deque

from ghost.examples.ghost_revolution import presentation as p


def _status(stage="king_phase_one", **updates):
    value = {
        "stage": stage,
        "castle_timer": 5,
        "player_health": 10,
        "player_max_health": 10,
        "king_health": 20,
        "king_max_health": 20,
        "tell": "A guarded tell.",
    }
    value.update(updates)
    return value


class FightGame:
    def __init__(self, statuses, packet=None):
        self.complete = False
        self.king_fight = {"stage": "king_phase_one"}
        self._statuses = list(statuses)
        self.packet = packet or {"outcome": "king_exchange"}
        self.moves = []
        self.last_action_note = "fight note"
        self.fates = []
        self.public_tell = None

    def king_fight_status(self):
        if not self._statuses:
            return None
        if len(self._statuses) == 1:
            return self._statuses[0]
        return self._statuses.pop(0)

    def king_fight_opponent_public_tell(self):
        return self.public_tell

    def resolve_king_fight_move(self, move):
        self.moves.append(move)
        self.complete = True
        return self.packet

    def choose_king_fate(self, choice):
        self.fates.append(choice)
        self.last_action_note = ""
        return {"outcome": choice}

    def final_ending_packet(self):
        return {"outcome": "already_final"}


def _set_inputs(monkeypatch, values):
    iterator = iter(values)
    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt="": next(iterator),
    )


def test_king_fight_menu_early_dispatch_and_llm_public_tell_paths(
    monkeypatch,
    capsys,
):
    p.king_fight_menu(FightGame([None]), deque())

    calls = []
    monkeypatch.setattr(
        p,
        "_king_fight_llm_opponent_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        p,
        "_select_king_fight_llm_opponent_intent",
        lambda game: calls.append(game),
    )

    after_select_none = FightGame([_status(), None])
    p.king_fight_menu(after_select_none, deque())

    for public_tell in ({"tell": "Public tell."}, None):
        game = FightGame([_status(), _status()])
        game.public_tell = public_tell
        _set_inputs(monkeypatch, ["q"])
        p.king_fight_menu(game, deque())

    output = capsys.readouterr().out
    assert len(calls) == 3
    assert "Observed tell: Public tell." in output
    assert "Opponent control:" in output
    assert "LLM strategy / Ghost" in output


def test_king_fight_menu_stage_dispatch_and_fate_edges(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        p,
        "_king_fight_llm_opponent_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        p,
        "_king_fight_llm_enabled",
        lambda: False,
    )

    crown_calls = []
    monkeypatch.setattr(
        p,
        "crown_loop_menu",
        lambda game, events: crown_calls.append((game, events)),
    )
    p.king_fight_menu(FightGame([_status("crown_loop")]), deque())

    fate_hold = FightGame([_status("fate_choice")])
    _set_inputs(monkeypatch, ["bad", "0"])
    p.king_fight_menu(fate_hold, deque())

    fate_execute = FightGame([_status("fate_choice")])
    _set_inputs(monkeypatch, ["1"])
    events = deque()
    p.king_fight_menu(fate_execute, events)

    final_game = FightGame([_status("finished")])
    p.king_fight_menu(final_game, deque())

    output = capsys.readouterr().out
    assert len(crown_calls) == 1
    assert fate_execute.fates == ["execute_king"]
    assert list(events) == ["The crown changes hands."]
    assert "Unknown king-fate choice." in output
    assert "already_final" in output


def test_king_fight_menu_all_remaining_move_choice_edges(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        p,
        "_king_fight_llm_opponent_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        p,
        "_king_fight_llm_enabled",
        lambda: False,
    )

    resolved = []
    cases = [
        (_status(parry_opening={"open": True}), ["1"], "heavy"),
        (_status(parry_opening={"open": True}), ["2"], "light"),
        (_status(forced_response={"allowed_moves": ("light", "dodge")}), ["2"], "light"),
        (_status(forced_response={"allowed_moves": ("light", "dodge")}), ["6"], "dodge"),
        (_status(bait_response={"open": True}), ["1"], "light"),
        (_status(bait_response={"open": True}), ["2"], "parry"),
        (_status(bait_response={"open": True}), ["3"], "pass"),
        (_status(), ["3", "2"], "feint_light"),
        (_status(), ["3", "3"], "feint_bait"),
    ]

    for status, inputs, expected in cases:
        game = FightGame([status])
        _set_inputs(monkeypatch, inputs)
        p.king_fight_menu(game, deque())
        resolved.append(game.moves[0])
        assert game.moves == [expected]

    nonresolving = [
        (_status(bait_response={"open": True}), ["9", "q"]),
        (_status(), ["3", "4", "q"]),
        (_status(), ["3", "wat", "q"]),
        (_status(), ["9", "q"]),
        (_status(), ["0", "q"]),
        (_status(), ["7", "q"]),
    ]

    for status, inputs in nonresolving:
        game = FightGame([status])
        _set_inputs(monkeypatch, inputs)
        p.king_fight_menu(game, deque())
        assert game.moves == []

    output = capsys.readouterr().out
    assert resolved == [
        "heavy",
        "light",
        "light",
        "dodge",
        "light",
        "parry",
        "pass",
        "feint_light",
        "feint_bait",
    ]
    assert "During a bait opening" in output
    assert "Unknown feint choice." in output
    assert "Unknown king-fight move." in output
    assert "There is no retreat." in output


def test_king_fight_menu_llm_resolution_outcome_dispatch(
    monkeypatch,
):
    monkeypatch.setattr(
        p,
        "_king_fight_llm_opponent_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        p,
        "_king_fight_llm_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        p,
        "_king_fight_scene_seen",
        lambda game, reason: True,
    )

    calls = []
    monkeypatch.setattr(
        p,
        "_king_fight_mark_transition_scene_seen",
        lambda game, packet: calls.append(("mark", packet["outcome"])),
    )
    monkeypatch.setattr(
        p,
        "_print_king_fight_transition_receipt",
        lambda packet: calls.append(("receipt", packet["outcome"])),
    )
    monkeypatch.setattr(
        p,
        "_print_king_fight_scene_beat",
        lambda packet, reason: calls.append(("scene", reason)),
    )
    monkeypatch.setattr(
        p,
        "_print_king_fight_mocking_lines",
        lambda packet: calls.append(("mock", packet["outcome"])),
    )
    monkeypatch.setattr(
        p,
        "_print_king_fight_llm_narration",
        lambda packet: calls.append(("narration", packet["outcome"])),
    )

    for outcome in (
        "elite_knight_called",
        "elite_knight_defeated",
        "player_death",
        "king_exchange",
    ):
        game = FightGame([_status()], {"outcome": outcome})
        _set_inputs(monkeypatch, ["1"])
        p.king_fight_menu(game, deque())

    assert ("receipt", "elite_knight_called") in calls
    assert ("scene", "elite_knight_start") in calls
    assert ("scene", "phase_two_start") in calls
    assert ("scene", "fight_end") in calls
    assert ("mock", "player_death") in calls
    assert ("narration", "king_exchange") in calls


def test_crown_helpers_cover_false_profiles_and_invalid_menu_choices(
    monkeypatch,
    capsys,
):
    class StatsGame:
        followers = 1
        food = 2
        gold = 3
        weapons = 4
        armor = 5
        king_control = 6
        guards_defeated = 7

        def _final_kingdom_stats(self):
            return "not-a-dict"

    p._print_crown_kingdom_stats(StatsGame())
    p._print_crown_packet({"outcome": "quiet"})

    class CrownGame:
        def crown_town_locations(self, town):
            return [{"id": "square", "label": "Square"}]

        def crown_visit_location(self, town, location):
            return {
                "outcome": "visit",
                "town": town,
                "location": location,
                "narrative": "visited",
                "npcs": [],
            }

        def crown_npc_interaction(self, town, location, npc_id, action):
            return {"outcome": "npc", "narrative": "npc"}

    game = CrownGame()

    _set_inputs(monkeypatch, ["word", "0"])
    p._crown_town_menu(game, deque(), "Ashfield")

    _set_inputs(monkeypatch, ["2", "0"])
    p._crown_town_menu(game, deque(), "Ashfield")

    _set_inputs(monkeypatch, ["1", "0"])
    p._crown_location_menu(
        game,
        deque(),
        {
            "town": "Ashfield",
            "location": "square",
            "location_label": "Square",
            "npcs": [],
        },
    )

    output = capsys.readouterr().out
    assert "FINAL KINGDOM STATS" in output
    assert output.count("Unknown crown-loop location.") == 2
    assert "Unknown crown-loop NPC option." in output
