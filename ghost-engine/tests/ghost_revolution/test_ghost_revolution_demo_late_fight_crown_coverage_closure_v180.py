"""Coverage closure for late king-fight dispatch and crown-loop branches."""

from __future__ import annotations

from ghost.examples.ghost_revolution import opponent_ai as oa
from ghost.examples.ghost_revolution.demo import GhostRevolutionRun
from ghost.examples.ghost_revolution.dev_shortcuts import (
    create_fight_stage_shortcut,
)


def _elite_knight():
    game, _packet = create_fight_stage_shortcut(
        "elite_knight"
    )
    game.king_fight["parry_opening"] = None
    game.king_fight["intent"] = "open_recovery"
    game._consume_king_fight_opponent_reaction_plan = (
        lambda _intent: None
    )
    game._precommitted_opponent_reaction = (
        lambda *_args, **_kwargs: None
    )
    return game


def _crown_game() -> GhostRevolutionRun:
    game = GhostRevolutionRun(seed=191)
    game.phase = "crown"
    game.king_fight = {
        "stage": "crown_loop",
        "king_fate": "jail_king",
    }
    return game


def test_base_elite_normal_exchange_returns_collapse_after_defeat_and_survival_v180(
    monkeypatch,
):
    collapse = {
        "outcome": "castle_collapse_legend",
    }

    defeated = _elite_knight()
    defeated.king_fight["elite_knight_health"] = 4
    monkeypatch.setattr(
        defeated,
        "_advance_castle_timer",
        lambda: collapse,
    )

    packet = oa._GHOST_ORIGINAL_RESOLVE_ELITE_KNIGHT_MOVE(
        defeated,
        "heavy",
    )

    assert packet is collapse
    assert defeated.king_fight["stage"] == "king_phase_two"

    surviving = _elite_knight()
    surviving.king_fight["elite_knight_health"] = 20
    monkeypatch.setattr(
        surviving,
        "_advance_castle_timer",
        lambda: collapse,
    )

    packet = oa._GHOST_ORIGINAL_RESOLVE_ELITE_KNIGHT_MOVE(
        surviving,
        "light",
    )

    assert packet is collapse
    assert surviving.king_fight["stage"] == "elite_knight"


def test_king_fight_dispatch_rejects_inactive_invalid_and_terminal_stages_v180():
    game = GhostRevolutionRun(seed=192)

    assert oa._GHOST_ORIGINAL_RESOLVE_KING_FIGHT_MOVE(game, "heavy") is None
    assert "no active" in game.last_action_note.lower()

    game.king_fight = {
        "stage": "king_phase_one",
        "parry_opening": None,
    }
    game.ending = "already over"
    assert oa._GHOST_ORIGINAL_RESOLVE_KING_FIGHT_MOVE(game, "heavy") is None
    assert "already resolved" in game.last_action_note.lower()

    game.ending = ""
    assert oa._GHOST_ORIGINAL_RESOLVE_KING_FIGHT_MOVE(game, "") is None
    assert "choose a king-fight move" in game.last_action_note.lower()

    assert oa._GHOST_ORIGINAL_RESOLVE_KING_FIGHT_MOVE(game, "sing") is None
    assert "choose heavy" in game.last_action_note.lower()

    game.king_fight["stage"] = "fate_choice"
    assert oa._GHOST_ORIGINAL_RESOLVE_KING_FIGHT_MOVE(game, "heavy") is None
    assert "execute_king" in game.last_action_note

    game.king_fight["stage"] = "crown_loop"
    assert oa._GHOST_ORIGINAL_RESOLVE_KING_FIGHT_MOVE(game, "heavy") is None
    assert "hold the crown" in game.last_action_note.lower()

    game.king_fight["stage"] = "unknown"
    assert oa._GHOST_ORIGINAL_RESOLVE_KING_FIGHT_MOVE(game, "heavy") is None
    assert "already resolved" in game.last_action_note.lower()


def test_choose_fate_rejects_invalid_state_and_invalid_choice_v180():
    game = GhostRevolutionRun(seed=193)

    assert game.choose_king_fate("execute_king") is None
    assert "mercy" in game.last_action_note.lower()

    game.king_fight = {
        "stage": "fate_choice",
    }

    assert game.choose_king_fate("release_king") is None
    assert "choose execute_king or jail_king" in game.last_action_note.lower()


def test_royal_visit_covers_rejections_and_all_public_views_v180(
    monkeypatch,
):
    denied = GhostRevolutionRun(seed=194)
    assert denied.royal_visit("millcross") is None
    assert "do not hold the crown" in denied.last_action_note.lower()

    game = _crown_game()
    assert game.royal_visit("unknown") is None
    assert "unknown town" in game.last_action_note.lower()

    town_id = next(iter(game.towns))

    monkeypatch.setattr(
        game,
        "town_trust",
        lambda _town_id: 0.70,
    )
    game.towns[town_id]["fear"] = 1
    assert game.royal_visit(town_id)["view"] == "beloved"

    monkeypatch.setattr(
        game,
        "town_trust",
        lambda _town_id: 0.30,
    )
    game.towns[town_id]["fear"] = 1
    assert game.royal_visit(town_id)["view"] == "hopeful"

    monkeypatch.setattr(
        game,
        "town_trust",
        lambda _town_id: 0.10,
    )
    game.towns[town_id]["fear"] = 5
    assert game.royal_visit(town_id)["view"] == "afraid"


def test_retire_crown_rejects_invalid_state_and_covers_legacy_bands_v180(
    monkeypatch,
):
    denied = GhostRevolutionRun(seed=195)
    assert denied.retire_crown() is None
    assert "cannot retire" in denied.last_action_note.lower()

    cases = (
        (
            {
                "a": {"trust": 0.70, "fear": 1},
                "b": {"trust": 0.60, "fear": 1},
            },
            "beloved",
        ),
        (
            {
                "a": {"trust": 0.30, "fear": 4},
                "b": {"trust": 0.30, "fear": 4},
            },
            "respected",
        ),
        (
            {
                "a": {"trust": 0.10, "fear": 6},
                "b": {"trust": 0.10, "fear": 6},
            },
            "feared",
        ),
    )

    for index, (towns, expected) in enumerate(cases):
        game = _crown_game()

        monkeypatch.setattr(
            game,
            "_final_kingdom_stats",
            lambda towns=towns: {
                "towns": towns,
            },
        )

        packet = game.retire_crown()

        assert packet["outcome"] == "retired_crown"
        assert packet["legacy"] == expected
        assert game.king_fight["retired_legacy"] == expected
