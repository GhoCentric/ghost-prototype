from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ghost.examples.ghost_revolution import dev_shortcuts as ds
from ghost.examples.ghost_revolution.demo import GhostRevolutionRun


def test_normalizer_and_assertion_boundaries_v180(monkeypatch):
    with pytest.raises(ValueError):
        ds.normalize_developer_preset("")

    with pytest.raises(ValueError):
        ds.normalize_developer_preset("not-a-preset")

    game = GhostRevolutionRun(seed=701)
    monkeypatch.setattr(
        ds,
        "normalize_developer_preset",
        lambda _preset: "impossible",
    )
    with pytest.raises(AssertionError):
        ds.apply_developer_preset(game, "anything")

    with pytest.raises(ValueError):
        ds.normalize_endgame_shortcut("")

    with pytest.raises(ValueError):
        ds.normalize_endgame_shortcut("not-an-endgame")

    with pytest.raises(ValueError):
        ds.create_fight_stage_shortcut("not-a-stage")

    monkeypatch.setattr(
        ds,
        "normalize_endgame_shortcut",
        lambda _shortcut: "impossible",
    )
    with pytest.raises(AssertionError):
        ds.create_endgame_shortcut("anything")


def test_print_helpers_cover_optional_sections_v180(capsys):
    game, basic = ds.create_developer_preset_run("prepared_siege")
    ds._print_summary(basic)

    _instant_game, instant = ds.create_developer_preset_run(
        "instant_king_fight"
    )
    ds._print_summary(instant)

    ds._print_siege_result(
        {
            "result": {
                "outcome": "x",
                "stage": "y",
                "ending_type": "z",
            }
        }
    )
    ds._print_siege_result(
        {
            "result": {
                "outcome": "x",
                "ending": "done",
                "tell": "look",
            }
        }
    )

    assert "DEVELOPER SHORTCUT LOADED" in capsys.readouterr().out

    empty = GhostRevolutionRun(seed=702)
    assert ds._open_king_fight_menu(empty) is None


def test_start_preset_and_packet_boundary_helpers_v180():
    game, loaded, started = ds._start_preset_siege(
        "instant_king_fight",
        seed=703,
    )
    assert game.king_fight is not None
    assert isinstance(loaded["started"], dict)
    assert started == loaded["started"]

    assert ds.wounded_start_explanation(game, None) == []
    assert ds.attach_developer_cause(game, None) is None

    no_fight_game, no_fight_packet = ds.create_developer_preset_run(
        "prepared_siege",
        seed=704,
    )
    lines = ds.developer_cause_lines(
        no_fight_game,
        no_fight_packet,
        "prepared_siege",
    )
    assert not any(line.startswith("Fight:") for line in lines)


def test_remaining_endgame_shortcut_paths_v180():
    for shortcut, expected in (
        ("weak_failure", "failed_siege_before_king"),
        ("champion_death", "player_killed_by_champion"),
        ("castle_legend", "castle_collapse_legend"),
        ("crown_execute", "execute_king"),
        ("retire_jail", "retired_crown"),
    ):
        _game, packet = ds.create_endgame_shortcut(shortcut, seed=705)
        assert packet["outcome"] == expected


def test_castle_legend_none_guard_v180(monkeypatch):
    class DummyGame:
        def __init__(self):
            self.king_fight = {"castle_timer": 5}

        def _advance_castle_timer(self):
            return None

    monkeypatch.setattr(
        ds,
        "create_fight_stage_shortcut",
        lambda *_args, **_kwargs: (DummyGame(), {}),
    )

    with pytest.raises(RuntimeError):
        ds.create_endgame_shortcut("castle_legend")


def test_direct_packet_output_and_llm_suppression_v180(
    monkeypatch,
    capsys,
):
    from ghost.examples.ghost_revolution import presentation

    seen = []
    monkeypatch.setattr(
        presentation,
        "print_endgame_packet",
        lambda packet: seen.append(packet),
    )

    monkeypatch.delenv("GHOST_REAL_LLM", raising=False)
    monkeypatch.delenv("GHOST_DEV_LLM_NARRATION", raising=False)
    monkeypatch.delenv("GHOST_LLM_DEBUG", raising=False)
    packet = {"stage": "king_phase_one", "outcome": "x"}
    ds._print_direct_packet(packet)
    assert seen == [packet]

    seen.clear()
    monkeypatch.setenv("GHOST_REAL_LLM", "1")
    ds._print_direct_packet(packet)
    assert seen == []

    monkeypatch.setenv("GHOST_LLM_DEBUG", "1")
    ds._print_direct_packet(packet)
    assert seen == [packet]
    capsys.readouterr()


def test_crown_menu_and_show_shortcut_branches_v180(monkeypatch, capsys):
    from ghost.examples.ghost_revolution import presentation

    empty = GhostRevolutionRun(seed=706)
    assert ds._open_crown_loop_menu(empty) is None

    active, packet = ds.create_endgame_shortcut("crown_jail", seed=707)
    seen = {}

    def fake_crown_loop_menu(game, events):
        events.appendleft("ok")
        seen["game"] = game
        seen["events"] = list(events)

    monkeypatch.setattr(
        presentation,
        "crown_loop_menu",
        fake_crown_loop_menu,
    )
    ds._open_crown_loop_menu(active)
    assert seen["game"] is active
    assert seen["events"] == ["ok"]

    monkeypatch.setattr(ds, "_print_direct_packet", lambda _packet: None)
    king_calls = []
    crown_calls = []
    monkeypatch.setattr(
        ds,
        "_open_king_fight_menu",
        lambda game: king_calls.append(game),
    )
    monkeypatch.setattr(
        ds,
        "_open_crown_loop_menu",
        lambda game: crown_calls.append(game),
    )

    complete = SimpleNamespace(complete=True)
    ds._show_endgame_shortcut(complete, {"stage": "fate_choice"})
    assert not king_calls

    unfinished = SimpleNamespace(complete=False)
    ds._show_endgame_shortcut(unfinished, {"stage": "fate_choice"})
    ds._show_endgame_shortcut(unfinished, {"stage": "crown_loop"})
    ds._show_endgame_shortcut(unfinished, {"stage": "other"})
    assert king_calls == [unfinished]
    assert crown_calls == [unfinished]
    capsys.readouterr()


def test_endgame_shortcut_panel_valid_invalid_and_back_v180(
    monkeypatch,
    capsys,
):
    choices = iter(["x", "1", "0"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(choices))

    game = SimpleNamespace(complete=True)
    packet = {"outcome": "done"}
    calls = []
    monkeypatch.setattr(
        ds,
        "create_endgame_shortcut",
        lambda shortcut: (game, {**packet, "shortcut": shortcut}),
    )
    monkeypatch.setattr(
        ds,
        "_show_endgame_shortcut",
        lambda active, result: calls.append((active, result)),
    )

    ds.run_endgame_shortcut_panel()
    assert calls[0][1]["shortcut"] == "weak_failure"
    assert "Unknown shortcut." in capsys.readouterr().out


def test_developer_shortcut_panel_all_choices_v180(
    monkeypatch,
    capsys,
):
    choices = iter(
        ["1", "2", "3", "4", "5", "6", "7", "8", "x", "0"]
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(choices))

    dummy = SimpleNamespace(king_fight={"stage": "king_phase_one"})
    direct_packets = []
    fight_stages = []
    preset_starts = []
    shown = []

    monkeypatch.setattr(
        ds,
        "create_endgame_shortcut",
        lambda shortcut: (
            dummy,
            {"outcome": shortcut, "stage": "done"},
        ),
    )

    def fake_fight_stage(stage):
        fight_stages.append(stage)
        return dummy, {"outcome": stage, "stage": stage}

    monkeypatch.setattr(ds, "create_fight_stage_shortcut", fake_fight_stage)

    def fake_start(preset):
        preset_starts.append(preset)
        return (
            dummy,
            {
                "label": preset,
                "note": "note",
                "summary": {},
                "started": None,
            },
            {"outcome": preset, "stage": "king_phase_one"},
        )

    monkeypatch.setattr(ds, "_start_preset_siege", fake_start)
    monkeypatch.setattr(ds, "_print_summary", lambda packet: None)
    monkeypatch.setattr(
        ds,
        "_print_direct_packet",
        lambda packet: direct_packets.append(packet),
    )
    monkeypatch.setattr(ds, "_open_king_fight_menu", lambda game: None)
    monkeypatch.setattr(
        ds,
        "_show_endgame_shortcut",
        lambda game, packet: shown.append(packet),
    )
    monkeypatch.setattr(ds, "run_endgame_shortcut_panel", lambda: shown.append("panel"))

    ds.run_developer_shortcut_panel()

    assert fight_stages == [
        "wounded_king",
        "prepared_king",
        "elite_knight",
        "king_phase_two",
    ]
    assert preset_starts == ["brutal_takeover", "honorable_takeover"]
    assert shown[0]["outcome"] == "weak_failure"
    assert shown[-1] == "panel"
    assert len(direct_packets) == 6
    assert "Unknown shortcut." in capsys.readouterr().out


def test_main_and_module_entrypoint_v180(monkeypatch):
    calls = []
    monkeypatch.setattr(ds, "run_developer_shortcut_panel", lambda: calls.append("main"))
    ds.main()
    assert calls == ["main"]

    monkeypatch.setattr("builtins.input", lambda _prompt="": "0")
    source = Path(ds.__file__)
    namespace = {
        "__name__": "__main__",
        "__package__": "ghost.examples.ghost_revolution",
        "__file__": str(source),
    }
    exec(
        compile(source.read_text(encoding="utf-8"), str(source), "exec"),
        namespace,
    )
