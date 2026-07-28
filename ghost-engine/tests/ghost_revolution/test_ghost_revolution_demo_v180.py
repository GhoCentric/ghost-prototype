import json

from ghost.examples.ghost_revolution.demo import (
    CAMP_DAYS,
    GhostRevolutionRun,
    REBELLION_DAYS,
    build_revolution_scenario,
)


def test_demo_starts_in_first_rebellion_phase():
    game = GhostRevolutionRun()

    assert game.runtime.config == build_revolution_scenario()
    assert game.phase == "rebellion"
    assert game.phase_number == 1
    assert game.phase_day == 1
    assert game.location == "base"


def test_all_location_travel_uses_distance_action_cost():
    game = GhostRevolutionRun()

    assert game.travel("crownmarket")
    assert game.location == "crownmarket"
    assert game.actions == 3


def test_town_recruitment_routes_through_ghost_packet():
    game = GhostRevolutionRun()

    assert game.travel("ashfield")

    packet = game.recruit_quietly()

    assert packet["action"]["type"] == "help"
    assert packet["action"]["target"] == "ashfield"
    assert packet["propagation"]["propagated"]
    assert game.followers > 0

    json.dumps(packet, sort_keys=True)


def test_raid_supplies_routes_to_contextual_seizure():
    game = GhostRevolutionRun(seed=7)

    assert game.travel("ashfield") is True

    actions_before = game.actions
    gold_before = game.gold
    food_before = game.food
    weapons_before = game.weapon_stock_total()
    heat_before = game.heat
    trust_before = game.town_trust("ashfield")

    packet = game.raid_supplies()

    assert packet is None
    assert game.actions == actions_before - 1
    assert game.heat == min(10, heat_before + 2)
    assert game.town_trust("ashfield") == trust_before

    gained_something = (
        game.gold > gold_before
        or game.food > food_before
        or game.weapon_stock_total() > weapons_before
    )

    assert gained_something is True
    assert "Royal cache seized:" in game.last_action_note
    assert "theft" not in game.last_action_note.lower()

def test_rebellion_phase_transitions_to_camp_after_seven_days():
    game = GhostRevolutionRun()
    game.food = REBELLION_DAYS + 1

    for _ in range(REBELLION_DAYS):
        result = game.end_day()

    assert result["phase_change"] == "camp"
    assert game.phase == "camp"
    assert game.phase_day == 1


def test_camp_assignments_create_passive_output():
    game = GhostRevolutionRun()

    game.followers = 4
    game.food = REBELLION_DAYS + 1

    for _ in range(REBELLION_DAYS):
        game.end_day()

    assert game.phase == "camp"
    assert game.set_assignment("farmers", 2)
    assert game.set_assignment("foragers", 2)

    food_before = game.food
    gold_before = game.gold

    result = game.end_day()

    assert result["camp_output"]["food_gain"] >= 2
    assert game.food > food_before
    assert game.gold > gold_before


def test_two_camp_days_trigger_king_response_and_new_phase():
    game = GhostRevolutionRun()
    game.food = REBELLION_DAYS + 1

    for _ in range(REBELLION_DAYS):
        game.end_day()

    game.end_day()
    result = game.end_day()

    assert result["phase_change"] == "rebellion"
    assert result["king_response"]
    assert game.phase == "rebellion"
    assert game.phase_number == 2
    assert game.phase_day == 1


def test_siege_warning_is_visible_even_when_weak():
    game = GhostRevolutionRun()

    warning = game.siege_warning()

    assert warning["likely_success"] is False
    assert "strength" in warning


def test_failed_siege_before_king_executes_only_player_with_zero_followers():
    game = GhostRevolutionRun()

    result = game.siege_castle()

    assert result["outcome"] == "failed_siege_before_king"
    assert result["ending_type"] == "failure"
    assert result["followers_executed"] == 0
    assert result["player_alive"] is False
    assert result["player_captured"] is True
    assert result["king_status"] == "enthroned"
    assert result["rebellion_status"] == "destroyed"
    assert game.alive is False
    assert game.captured is True
    assert game.complete is True
    assert game.king_fight is None
    assert (
        game.ending
        == "The siege fails before you ever reach the king. "
        "You are publicly executed for conspiracy against the crown."
    )


def test_failed_siege_before_king_executes_player_and_followers():
    game = GhostRevolutionRun()
    game.followers = 3

    result = game.siege_castle()

    assert result["outcome"] == "failed_siege_before_king"
    assert result["ending_type"] == "failure"
    assert result["followers_executed"] == 3
    assert result["player_alive"] is False
    assert result["player_captured"] is True
    assert result["king_status"] == "enthroned"
    assert result["rebellion_status"] == "destroyed"
    assert game.alive is False
    assert game.captured is True
    assert game.complete is True
    assert game.king_fight is None
    assert (
        game.ending
        == "The siege fails before you ever reach the king. "
        "You and the rebels who followed you are publicly "
        "executed for conspiracy against the crown."
    )


def test_strong_siege_starts_king_confrontation():
    game = GhostRevolutionRun()

    game.followers = 40
    game.weapons = 8
    game.armor = 4
    game.guards_defeated = 4
    game.king_control = 5

    result = game.siege_castle()

    assert result["outcome"] == "king_confrontation_started"
    assert result["prepared_assault"] is True
    assert result["wounded_start"] is False
    assert result["player_health"] == 10
    assert result["player_max_health"] == 10
    assert result["damage_bonus_percent"] == 0
    assert result["stage"] == "king_phase_one"
    assert game.king_fight is not None
    assert game.king_fight["stage"] == "king_phase_one"
    assert game.king_fight["armor_broken"] is False
    assert game.king_fight["clean_king_victory_possible"] is True
    assert game.ending == ""
    assert game.complete is False


def test_targeted_scouting_adds_persistent_raid_intel():
    game = GhostRevolutionRun()
    game.followers = 30
    game.food = 10

    assert game.set_combat_role("warriors", 25) is True
    assert game.set_combat_role("scouts", 1) is True
    assert game.plan_raid("ashfield") is not None
    assert game.set_raid_force(25) is True

    before = game.raid_readiness("ashfield")

    result = game.end_day()

    after = game.raid_readiness("ashfield")
    reports = result["day_report"]["scout_reports"]

    assert len(reports) == 1
    assert "Ashfield report 1/3" in reports[0]
    assert game.scout_intel["ashfield"] == 1
    assert after["intel_bonus"] == 2
    assert after["readiness"] == before["readiness"] + 2
    assert game.actions == 6

def test_public_actions_have_distinct_fear_and_heat_effects():
    speech_game = GhostRevolutionRun()
    speech_game.location = "ashfield"
    speech_game.towns["ashfield"]["fear"] = 3

    assert speech_game.begin_public_event() is True

    speech_packet = speech_game.speak_publicly()

    assert speech_packet is not None
    assert speech_game.towns["ashfield"]["fear"] == 2
    assert speech_game.heat == 1

    rally_game = GhostRevolutionRun()
    rally_game.location = "ashfield"
    rally_game.towns["ashfield"]["fear"] = 3

    assert rally_game.begin_public_event() is True

    rally_packet = rally_game.rally_people()

    assert rally_packet is not None
    assert rally_game.towns["ashfield"]["fear"] == 1
    assert rally_game.heat == 0

def test_open_recruitment_adds_attention_after_real_recruitment():
    game = GhostRevolutionRun()
    game.location = "ashfield"

    assert game.begin_public_event() is True

    followers_before = game.followers

    packet = game.recruit_openly()

    assert packet is not None
    assert game.followers > followers_before
    assert game.heat == 1

def test_day_report_tracks_leader_food_separately():
    game = GhostRevolutionRun()
    game.followers = 0

    result = game.end_day()
    report = result["day_report"]

    assert report["leader_fed"] == 1
    assert report["followers_fed"] == 0


def test_scout_intel_reports_are_distinct_and_stop_at_maximum():
    game = GhostRevolutionRun()
    game.followers = 1
    game.food = 10

    game.scout_intel["millcross"] = 3
    game.scout_intel["crownmarket"] = 3

    assert game.set_combat_role("scouts", 1) is True

    first = game.end_day()
    first_report = first["day_report"]["scout_reports"][0]

    second = game.end_day()
    second_report = second["day_report"]["scout_reports"][0]

    third = game.end_day()
    third_report = third["day_report"]["scout_reports"][0]

    fourth = game.end_day()
    final_reports = fourth["day_report"]["scout_reports"]

    assert "Ashfield report 1/3" in first_report
    assert "royal troops" in first_report

    assert "Ashfield report 2/3" in second_report
    assert "royal troops" in second_report

    assert "Ashfield report 3/3" in third_report
    assert "royal troops" in third_report

    assert game.scout_intel["ashfield"] == 3
    assert final_reports == []

def test_rebellion_day_starts_with_six_actions():
    game = GhostRevolutionRun()

    assert game.actions == 6

    assert game.travel("ashfield") is True
    assert game.actions == 5

def test_royal_cache_loot_table_has_all_category_combinations():
    class ScriptedRNG:
        def __init__(self, values):
            self.values = list(values)

        def randint(self, low, high):
            if not self.values:
                raise AssertionError("Scripted RNG ran out of values.")

            value = self.values.pop(0)

            assert low <= value <= high

            return value

        def choice(self, options):
            return options[0]

    cases = [
        ("food", [10, 3], 3, 0, 0),
        ("gold", [30, 7], 0, 7, 0),
        ("weapons", [45, 2], 0, 0, 2),
        ("food_gold", [55, 2, 4], 2, 4, 0),
        ("food_weapons", [70, 2], 2, 0, 1),
        ("gold_weapons", [82, 5], 0, 5, 1),
        ("full_cache", [95, 3, 8, 2], 3, 8, 2),
    ]

    for composition, values, food, gold, weapon_count in cases:
        game = GhostRevolutionRun()
        food_before = game.food
        gold_before = game.gold
        weapons_before = game.weapon_stock_total()

        game.rng = ScriptedRNG(values)

        loot = game._roll_royal_cache_loot()

        assert loot["composition"] == composition
        assert loot["food"] == food
        assert loot["gold"] == gold
        assert len(loot["weapons"]) == weapon_count
        assert game.food == food_before + food
        assert game.gold == gold_before + gold
        assert (
            game.weapon_stock_total() - weapons_before
            == weapon_count
        )
        assert loot["summary"]

def test_guard_loss_escalates_without_betrayal_and_victory_is_local():
    class ScriptedRNG:
        def __init__(self, choices, rolls):
            self.choices = list(choices)
            self.rolls = list(rolls)

        def choice(self, options):
            value = self.choices.pop(0)
            assert value in options
            return value

        def randint(self, low, high):
            value = self.rolls.pop(0)
            assert low <= value <= high
            return value

    victory = GhostRevolutionRun()
    victory.location = "millcross"

    actions_before = victory.actions
    fear_before = victory.towns["millcross"]["fear"]
    gold_before = victory.gold
    weapons_before = victory.weapon_stock_total()
    trust_before = victory.town_trust("millcross")

    victory.rng = ScriptedRNG(
        (
            "tight_defense",
            "open_line",
            "open_line",
            "recovering",
        ),
        (26, 100),
    )

    assert victory.fight_guard() is None
    assert victory.actions == actions_before - 1
    assert victory.resolve_guard_combat_move(
        "feint_heavy"
    ) is None
    assert victory.resolve_guard_combat_move("heavy") is None
    assert victory.resolve_guard_combat_move("heavy") is None
    assert victory.resolve_guard_combat_move("light") is None

    status = victory.guard_combat_status()

    assert status is not None
    assert status["stage"] == "down"
    assert status["guard_health"] == 0
    assert status["player_health"] == 10
    assert status["conduct"] >= 4
    assert victory.guard_count("millcross") == 2

    packet = victory.resolve_guard_down("leave")

    assert packet is None
    assert victory.guard_combat is None
    assert victory.guard_count("millcross") == 1
    assert victory.towns["millcross"]["fear"] == fear_before
    assert victory.guards_defeated == 1
    assert victory.gold == gold_before + 6
    assert victory.weapon_stock_total() == weapons_before
    assert victory.heat == 2
    assert victory.royal_alert == 2
    assert victory.town_trust("millcross") == trust_before
    assert "do not yet know what kind of ruler" in victory.last_action_note

    loss = GhostRevolutionRun()
    loss.location = "millcross"

    fear_before = loss.towns["millcross"]["fear"]

    loss.rng = ScriptedRNG(
        (
            "driving_lunge",
            "driving_lunge",
            "driving_lunge",
            "driving_lunge",
        ),
        (100,),
    )

    assert loss.fight_guard() is None

    for _ in range(4):
        assert loss.resolve_guard_combat_move("heavy") is None

    assert loss.guard_combat is None
    assert loss.alive is False
    assert loss.captured is True
    assert loss.last_packet is None
    assert loss.guard_count("millcross") == 2
    assert loss.towns["millcross"]["fear"] == min(
        5,
        fear_before + 1,
    )
    assert loss.heat == 3
    assert loss.royal_alert == 3
    assert "detains you" in loss.ending


def test_guard_question_and_bribe_create_one_day_tactical_state():
    class ScriptedRNG:
        def __init__(self, values):
            self.values = list(values)

        def randint(self, low, high):
            if not self.values:
                raise AssertionError("Scripted RNG ran out of values.")

            value = self.values.pop(0)

            assert low <= value <= high

            return value

    question = GhostRevolutionRun()
    question.location = "millcross"

    actions_before = question.actions

    assert question.question_guard() is None
    assert question.actions == actions_before - 1
    assert question.daily_activity["millcross"]["guard_question"] is True
    assert "Guard read — Defection pressure:" in question.last_action_note

    actions_after_first_question = question.actions

    assert question.question_guard() is None
    assert question.actions == actions_after_first_question
    assert "already questioned" in question.last_action_note

    bribe = GhostRevolutionRun()
    bribe.location = "millcross"
    bribe.gold = 10

    danger_before = bribe.danger_level()
    gold_before = bribe.gold
    actions_before = bribe.actions

    assert bribe.bribe_guard() is None
    assert bribe.actions == actions_before - 1
    assert bribe.gold == gold_before - 6
    assert bribe.guard_count("millcross") == 2
    assert bribe.has_active_guard("millcross") is True
    assert bribe.guard_passage_active("millcross") is True
    assert bribe.danger_level() == danger_before - 2
    assert "Safe passage is active." in bribe.last_action_note

    fear_before = bribe.towns["millcross"]["fear"]

    bribe.rng = ScriptedRNG([30, 7])

    packet = bribe.seize_royal_supplies()

    assert packet is None
    assert bribe.heat == 2
    assert bribe.towns["millcross"]["fear"] == fear_before
    assert "No one cheers" in bribe.last_action_note

    bribe._reset_daily_limits()

    assert bribe.guard_passage_active("millcross") is False


def test_guard_recruitment_defection_and_rejection_are_local():
    class ScriptedRNG:
        def __init__(self, values):
            self.values = list(values)

        def randint(self, low, high):
            if not self.values:
                raise AssertionError("Scripted RNG ran out of values.")

            value = self.values.pop(0)

            assert low <= value <= high

            return value

    success = GhostRevolutionRun()
    success.location = "millcross"

    fear_before = success.towns["millcross"]["fear"]
    followers_before = success.followers

    success.rng = ScriptedRNG([1])

    packet = success.recruit_guard()

    assert packet is not None
    assert packet["action"]["type"] == "help"
    assert success.guard_count("millcross") == 1
    assert success.has_active_guard("millcross") is True
    assert success.towns["millcross"]["fear"] == max(
        0,
        fear_before - 1,
    )
    assert success.followers == followers_before + 1
    assert success.heat == 1
    assert success.royal_alert == 1
    assert "throws down his royal badge" in success.last_action_note

    failure = GhostRevolutionRun()
    failure.location = "millcross"

    trust_before = failure.town_trust("millcross")
    fear_before = failure.towns["millcross"]["fear"]

    failure.rng = ScriptedRNG([100])

    packet = failure.recruit_guard()

    assert packet is None
    assert failure.alive is True
    assert failure.captured is False
    assert failure.last_packet is None
    assert failure.guard_count("millcross") == 2
    assert failure.has_active_guard("millcross") is True
    assert failure.towns["millcross"]["fear"] == min(
        5,
        fear_before + 1,
    )
    assert failure.heat == 1
    assert failure.royal_alert == 1
    assert failure.town_trust("millcross") == trust_before
    assert "reaches for his signal whistle" in failure.last_action_note

def test_guard_combat_health_and_retreat_are_local():
    class ScriptedRNG:
        def __init__(self, choices):
            self.choices = list(choices)

        def choice(self, options):
            value = self.choices.pop(0)
            assert value in options
            return value

    game = GhostRevolutionRun()
    game.location = "millcross"

    fear_before = game.towns["millcross"]["fear"]
    game.rng = ScriptedRNG(("open_line", "recovering"))

    assert game.fight_guard() is None
    assert game.resolve_guard_combat_move("heavy") is None

    status = game.guard_combat_status()

    assert status is not None
    assert status["exchange_count"] == 1
    assert status["player_health"] == 10
    assert status["guard_health"] == 7
    assert status["guard_intent"] == "recovering"
    assert "open line" in game.last_action_note

    assert game.retreat_guard_combat() is None
    assert game.guard_combat is None
    assert game.guard_count("millcross") == 2
    assert game.has_active_guard("millcross") is True
    assert game.towns["millcross"]["fear"] == fear_before
    assert game.heat == 1
    assert game.royal_alert == 1
    assert game.last_packet is None
    assert "break contact" in game.last_action_note


def test_guard_down_resolution_uses_combat_conduct_and_town_state():
    def defeated_guard(game, conduct, witnesses):
        guard = game.active_guard("millcross")
        assert guard is not None

        game.guard_combat = {
            "stage": "down",
            "town": "millcross",
            "guard_id": guard["id"],
            "guard_rank": guard["rank"],
            "guard_label": guard["label"],
            "conduct": conduct,
            "witnesses": witnesses,
        }

    supportive = GhostRevolutionRun()
    supportive.location = "millcross"
    supportive.towns["millcross"]["fear"] = 1

    supportive._resolve("help", "millcross")
    supportive._resolve("help", "millcross")

    trust_before = supportive.town_trust("millcross")
    fear_before = supportive.towns["millcross"]["fear"]

    supportive.last_packet = None
    defeated_guard(supportive, conduct=2, witnesses=3)

    packet = supportive.resolve_guard_down("leave")

    assert packet is not None
    assert packet["action"]["type"] == "help"
    assert supportive.towns["millcross"]["fear"] == max(
        0,
        fear_before - 1,
    )
    assert supportive.town_trust("millcross") > trust_before
    assert "see control instead of cruelty" in supportive.last_action_note

    execution = GhostRevolutionRun()
    execution.location = "millcross"

    trust_before = execution.town_trust("millcross")
    fear_before = execution.towns["millcross"]["fear"]
    gold_before = execution.gold
    defeated_guard(execution, conduct=0, witnesses=3)

    packet = execution.resolve_guard_down("execute")

    assert packet is not None
    assert packet["action"]["type"] == "insult"
    assert execution.gold == gold_before
    assert execution.heat == 2
    assert execution.royal_alert == 2
    assert execution.towns["millcross"]["fear"] == min(
        5,
        fear_before + 1,
    )
    assert execution.town_trust("millcross") < trust_before
    assert "people pull away from you in fear" in execution.last_action_note



def test_guard_combat_hides_counter_map_and_records_conduct():
    from pathlib import Path

    class ScriptedRNG:
        def __init__(self, choices, rolls):
            self.choices = list(choices)
            self.rolls = list(rolls)

        def choice(self, options):
            value = self.choices.pop(0)
            assert value in options
            return value

        def randint(self, low, high):
            value = self.rolls.pop(0)
            assert low <= value <= high
            return value

    game = GhostRevolutionRun()
    game.location = "millcross"
    game.rng = ScriptedRNG(
        ("tight_defense", "open_line"),
        (26, 100),
    )

    assert game.fight_guard() is None
    assert "Counter map" not in game.last_action_note
    assert "Heavy > Guard" not in game.last_action_note

    assert game.resolve_guard_combat_move(
        "feint_heavy"
    ) is None

    status = game.guard_combat_status()

    assert status is not None
    assert status["conduct"] == 1
    assert status["correct_reads"] == 1
    assert status["wrong_reads"] == 0
    assert "can punish" not in status["guard_tell"]
    assert "can catch" not in status["guard_tell"]

    presentation_text = Path(
        "ghost/examples/ghost_revolution/presentation.py"
    ).read_text()

    assert "Counter map:" not in presentation_text
    assert "Heavy > Guard" not in presentation_text
    assert "Guard > Feint" not in presentation_text
    assert "Feint > Heavy" not in presentation_text


def test_execution_memory_persists_after_ghost_trust_moves():
    game = GhostRevolutionRun()
    game.location = "millcross"

    guard = game.active_guard("millcross")
    assert guard is not None

    game.guard_combat = {
        "stage": "down",
        "town": "millcross",
        "guard_id": guard["id"],
        "guard_rank": guard["rank"],
        "guard_label": guard["label"],
        "conduct": 0,
        "witnesses": 3,
    }

    packet = game.resolve_guard_down("execute")

    assert packet is not None
    assert packet["action"]["type"] == "insult"
    assert game.town_execution_memory("millcross") == 3
    assert (
        game.town_memory_label("millcross")
        == "Execution remembered (3 days)"
    )

    trust_before = game.town_trust("millcross")

    help_packet = game._resolve(
        "help",
        "millcross",
    )

    trust_after = game.town_trust("millcross")

    assert help_packet is not None
    assert trust_after > trust_before

    assert game.town_execution_memory("millcross") == 3
    assert (
        game.town_memory_label("millcross")
        == "Execution remembered (3 days)"
    )



def test_presentation_labels_connected_observers_and_town_memory():
    from pathlib import Path

    text = Path(
        "ghost/examples/ghost_revolution/presentation.py"
    ).read_text()

    assert "Connected observers:" in text
    assert "Observers:" not in text
    assert "Town Memory:" in text
    assert "town_memory_label(game.location)" in text

