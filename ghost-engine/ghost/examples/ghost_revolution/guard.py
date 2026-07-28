"""Deterministic guard-domain rules for Ghost Revolution."""

from __future__ import annotations

from types import MappingProxyType


class GuardSystem:
    """
    Own pure guard-policy calculations.

    GhostRevolutionRun owns live world mutation and presentation.
    GuardSystem owns deterministic guard-rule math.
    """

    _TACTICAL_MOVE_ALIASES = MappingProxyType(
        {
            "heavy": "heavy",
            "light": "light",
            "feint_heavy": "feint_heavy",
            "feint_light": "feint_light",
            "parry": "parry",
            "deflect": "deflect",
            "dodge": "dodge",
        }
    )

    _COMBAT_INTENTS = MappingProxyType(
        {
            "tight_defense": MappingProxyType(
                {
                    "label": "Tight Defense",
                    "tell": (
                        "The guard closes his stance behind a tight "
                        "defense, blade centered and elbows tucked."
                    ),
                }
            ),
            "open_line": MappingProxyType(
                {
                    "label": "Open Line",
                    "tell": (
                        "The guard's blade drifts wide of center, "
                        "leaving a direct line through his guard."
                    ),
                }
            ),
            "recovering": MappingProxyType(
                {
                    "label": "Recovering Guard",
                    "tell": (
                        "The guard resets his footing late, with his "
                        "weapon still low from the last movement."
                    ),
                }
            ),
            "committed_heavy": MappingProxyType(
                {
                    "label": "Committed Heavy",
                    "tell": (
                        "The guard raises his sword behind his shoulder. "
                        "His lead shoulder drops as his hips begin to "
                        "turn. The strike is gathering his full weight."
                    ),
                }
            ),
            "wide_cut": MappingProxyType(
                {
                    "label": "Wide Cut",
                    "tell": (
                        "The guard's elbow extends fully as his blade "
                        "gathers speed through a wide looping line, "
                        "exposing the flat of the weapon."
                    ),
                }
            ),
            "driving_lunge": MappingProxyType(
                {
                    "label": "Driving Lunge",
                    "tell": (
                        "The guard settles just beyond your blade's "
                        "reach. His footing locks as his eyes drop "
                        "toward your legs, your armor gap, then your head."
                    ),
                }
            ),
        }
    )

    _RANK_PROFILES = MappingProxyType(
        {
            "watchman": MappingProxyType(
                {
                    "label": "Royal Watchman",
                    "max_health": 10,
                    "light_damage": 2,
                    "heavy_damage": 3,
                    "feint_read_chance": 25,
                    "parry_success_chance": 75,
                    "deflect_success_chance": 70,
                    "escape_chance": 22,
                    "death_chance": 2,
                }
            ),
            "crown_guard": MappingProxyType(
                {
                    "label": "Crown Guard",
                    "max_health": 14,
                    "light_damage": 3,
                    "heavy_damage": 4,
                    "feint_read_chance": 40,
                    "parry_success_chance": 65,
                    "deflect_success_chance": 60,
                    "escape_chance": 12,
                    "death_chance": 5,
                }
            ),
        }
    )

    @classmethod
    def guard_profile(cls, rank) -> dict:
        """
        Return a fresh rank profile for one named guard.

        Rank mechanics are intentionally not applied yet. This creates
        a validated identity boundary for the later health-and-tactics
        combat system.
        """
        if not isinstance(rank, str):
            raise ValueError(
                "guard rank must be a string"
            )

        normalized = rank.strip().lower()

        profile = cls._RANK_PROFILES.get(normalized)

        if profile is None:
            raise ValueError(
                f"unknown guard rank: {normalized}"
            )

        return {
            "rank": normalized,
            "label": str(profile["label"]),
            "max_health": int(profile["max_health"]),
            "light_damage": int(profile["light_damage"]),
            "heavy_damage": int(profile["heavy_damage"]),
            "feint_read_chance": int(
                profile["feint_read_chance"]
            ),
            "parry_success_chance": int(
                profile["parry_success_chance"]
            ),
            "deflect_success_chance": int(
                profile["deflect_success_chance"]
            ),
            "escape_chance": int(
                profile["escape_chance"]
            ),
            "death_chance": int(profile["death_chance"]),
        }

    @classmethod
    def new_guard(
        cls,
        *,
        guard_id,
        rank,
    ) -> dict:
        """
        Build one fresh, validated guard roster entry.

        The facade owns roster mutation. This method returns no shared
        mutable profile state.
        """
        if not isinstance(guard_id, str):
            raise ValueError(
                "guard id must be a string"
            )

        normalized_id = guard_id.strip()

        if not normalized_id:
            raise ValueError(
                "guard id must not be empty"
            )

        profile = cls.guard_profile(rank)

        return {
            "id": normalized_id,
            "rank": profile["rank"],
            "label": profile["label"],
        }

    def defection_chance(
        self,
        *,
        trust: float,
        fear: int,
        royal_alert: int,
        execution_memory: int,
        knight_occupied: bool,
    ) -> int:
        """
        Return the bounded chance that a local guard defects.

        This preserves the original game-loop formula exactly.
        """
        chance = 20
        chance += max(0, round(trust * 60))
        chance += max(0, 3 - fear) * 8
        chance -= royal_alert * 7
        chance -= execution_memory * 8

        if knight_occupied:
            chance -= 20

        return max(5, min(75, chance))

    @classmethod
    def combat_intents(cls) -> tuple[str, ...]:
        """Return the valid guard intent identifiers in stable order."""
        return tuple(cls._COMBAT_INTENTS)

    @classmethod
    def combat_intent(cls, intent) -> dict:
        """Return a copy-safe physical tell for one guard intent."""
        if not isinstance(intent, str):
            raise ValueError(
                "invalid internal guard combat intent"
            )

        normalized = intent.strip().lower()
        profile = cls._COMBAT_INTENTS.get(normalized)

        if profile is None:
            raise ValueError(
                "invalid internal guard combat intent"
            )

        return {
            "intent": normalized,
            "label": str(profile["label"]),
            "tell": str(profile["tell"]),
        }

    @classmethod
    def _normalize_tactical_move(cls, move) -> str:
        if not isinstance(move, str):
            raise ValueError(
                "Choose heavy, light, feint_heavy, feint_light, "
                "parry, deflect, or dodge."
            )

        normalized = move.strip().lower()
        result = cls._TACTICAL_MOVE_ALIASES.get(normalized)

        if result is None:
            raise ValueError(
                "Choose heavy, light, feint_heavy, feint_light, "
                "parry, deflect, or dodge."
            )

        return result

    @staticmethod
    def _percent_roll(value, label: str) -> int:
        if not isinstance(value, int) or not 1 <= value <= 100:
            raise ValueError(
                f"{label} must be an integer from 1 to 100"
            )

        return value

    @staticmethod
    def _packet(
        *,
        move: str,
        intent: str,
        result: str,
        guard_damage: int = 0,
        player_damage: int = 0,
        conduct_delta: int = 0,
        correct_reads_delta: int = 0,
        wrong_reads_delta: int = 0,
        free_attack: bool = False,
        message: str,
    ) -> dict:
        return {
            "move": move,
            "intent": intent,
            "result": result,
            "guard_damage": guard_damage,
            "player_damage": player_damage,
            "conduct_delta": conduct_delta,
            "correct_reads_delta": correct_reads_delta,
            "wrong_reads_delta": wrong_reads_delta,
            "free_attack": free_attack,
            "message": message,
        }

    def resolve_tactical_exchange(
        self,
        *,
        rank,
        intent,
        player_move,
        free_attack: bool = False,
        feint_read_roll: int | None = None,
        counter_roll: int | None = None,
        technique_roll: int | None = None,
    ) -> dict:
        """
        Resolve one pure tactical exchange.

        The caller supplies all seeded rolls. This method owns only
        deterministic combat math; it does not mutate campaign state.
        """
        profile = self.guard_profile(rank)
        intent_packet = self.combat_intent(intent)
        move = self._normalize_tactical_move(player_move)

        light_damage = profile["light_damage"]
        heavy_damage = profile["heavy_damage"]

        if free_attack:
            if move not in ("heavy", "light"):
                raise ValueError(
                    "Your parry opened the guard. Choose heavy or light."
                )

            damage = (
                heavy_damage
                if move == "heavy"
                else light_damage
            )

            return self._packet(
                move=move,
                intent=intent_packet["intent"],
                result="free_attack",
                guard_damage=damage,
                conduct_delta=1,
                correct_reads_delta=1,
                message=(
                    "The guard is still out of form. Your "
                    f"{move} strike lands cleanly."
                ),
            )

        if intent_packet["intent"] == "tight_defense":
            if move not in ("feint_heavy", "feint_light"):
                return self._packet(
                    move=move,
                    intent=intent_packet["intent"],
                    result="blocked",
                    wrong_reads_delta=1,
                    conduct_delta=-1,
                    message=(
                        "The guard's tight defense absorbs the attack. "
                        "You needed to draw the block first."
                    ),
                )

            read_roll = self._percent_roll(
                feint_read_roll,
                "feint_read_roll",
            )
            counter = self._percent_roll(
                counter_roll,
                "counter_roll",
            )

            main_move = move.removeprefix("feint_")
            main_damage = (
                heavy_damage
                if main_move == "heavy"
                else light_damage
            )

            if read_roll <= profile["feint_read_chance"]:
                counter_damage = (
                    light_damage
                    if counter <= 20
                    else 0
                )

                message = (
                    "The guard reads the feint and blocks the "
                    "real attack."
                )

                if counter_damage:
                    message += (
                        " He snaps a light counter through the opening."
                    )

                return self._packet(
                    move=move,
                    intent=intent_packet["intent"],
                    result="feint_read",
                    player_damage=counter_damage,
                    conduct_delta=-1,
                    wrong_reads_delta=1,
                    message=message,
                )

            return self._packet(
                move=move,
                intent=intent_packet["intent"],
                result="feint_lands",
                guard_damage=main_damage,
                conduct_delta=1,
                correct_reads_delta=1,
                message=(
                    "The guard commits to the false opening. Your "
                    f"{main_move} attack lands behind the feint."
                ),
            )

        if intent_packet["intent"] == "open_line":
            if move == "heavy":
                return self._packet(
                    move=move,
                    intent=intent_packet["intent"],
                    result="heavy_lands",
                    guard_damage=heavy_damage,
                    conduct_delta=1,
                    correct_reads_delta=1,
                    message=(
                        "You drive a heavy attack through the open line."
                    ),
                )

            if move == "light":
                return self._packet(
                    move=move,
                    intent=intent_packet["intent"],
                    result="partial_light",
                    guard_damage=1,
                    message=(
                        "Your light strike clips the guard, but the "
                        "larger opening passes before you can punish it."
                    ),
                )

            if move in ("feint_heavy", "feint_light"):
                main_move = move.removeprefix("feint_")
                damage = (
                    heavy_damage
                    if main_move == "heavy"
                    else light_damage
                )

                return self._packet(
                    move=move,
                    intent=intent_packet["intent"],
                    result="feint_through_opening",
                    guard_damage=damage,
                    message=(
                        "The guard gives ground before the feint. Your "
                        f"{main_move} attack still finds the open line."
                    ),
                )

            if move == "dodge":
                return self._packet(
                    move=move,
                    intent=intent_packet["intent"],
                    result="dodge_no_progress",
                    message=(
                        "You give ground from an opening that did not "
                        "require it. The guard recovers his structure."
                    ),
                )

            return self._packet(
                move=move,
                intent=intent_packet["intent"],
                result="bad_defense",
                player_damage=light_damage,
                conduct_delta=-1,
                wrong_reads_delta=1,
                message=(
                    "You prepare a defense instead of taking the line. "
                    "The guard clips you with a light cut."
                ),
            )

        if intent_packet["intent"] == "recovering":
            if move == "light":
                return self._packet(
                    move=move,
                    intent=intent_packet["intent"],
                    result="light_lands",
                    guard_damage=light_damage,
                    conduct_delta=1,
                    correct_reads_delta=1,
                    message=(
                        "You catch the guard before his recovery "
                        "can close."
                    ),
                )

            if move == "heavy":
                return self._packet(
                    move=move,
                    intent=intent_packet["intent"],
                    result="partial_heavy",
                    guard_damage=1,
                    message=(
                        "Your heavy attack lands late as the guard "
                        "regains his feet."
                    ),
                )

            if move in ("feint_heavy", "feint_light"):
                main_move = move.removeprefix("feint_")
                damage = (
                    heavy_damage
                    if main_move == "heavy"
                    else light_damage
                )

                return self._packet(
                    move=move,
                    intent=intent_packet["intent"],
                    result="feint_on_recovery",
                    guard_damage=damage,
                    message=(
                        "The guard is too busy recovering to bite on "
                        "the feint. Your "
                        f"{main_move} attack lands anyway."
                    ),
                )

            if move == "dodge":
                return self._packet(
                    move=move,
                    intent=intent_packet["intent"],
                    result="dodge_no_progress",
                    message=(
                        "You step away while the guard recovers. "
                        "Neither side gains ground."
                    ),
                )

            return self._packet(
                move=move,
                intent=intent_packet["intent"],
                result="bad_defense",
                player_damage=light_damage,
                conduct_delta=-1,
                wrong_reads_delta=1,
                message=(
                    "You wait for a blow that never comes. The guard "
                    "recovers and cuts you lightly."
                ),
            )

        if intent_packet["intent"] == "committed_heavy":
            if move == "dodge":
                return self._packet(
                    move=move,
                    intent=intent_packet["intent"],
                    result="dodge_success",
                    correct_reads_delta=1,
                    message=(
                        "You clear the heavy line before the blade "
                        "can carry through you."
                    ),
                )

            if move == "parry":
                roll = self._percent_roll(
                    technique_roll,
                    "technique_roll",
                )

                if roll <= profile["parry_success_chance"]:
                    return self._packet(
                        move=move,
                        intent=intent_packet["intent"],
                        result="parry_success",
                        conduct_delta=1,
                        correct_reads_delta=1,
                        free_attack=True,
                        message=(
                            "You catch the heavy strike on time. The "
                            "guard loses form, and you have a free attack."
                        ),
                    )

                return self._packet(
                    move=move,
                    intent=intent_packet["intent"],
                    result="parry_fail",
                    player_damage=heavy_damage,
                    conduct_delta=-1,
                    wrong_reads_delta=1,
                    message=(
                        "Your parry misses the leverage point. The "
                        "guard's heavy strike lands."
                    ),
                )

            return self._packet(
                move=move,
                intent=intent_packet["intent"],
                result="heavy_punish",
                player_damage=heavy_damage,
                conduct_delta=-1,
                wrong_reads_delta=1,
                message=(
                    "You do not clear the committed heavy attack. "
                    "The guard's full weight crashes through."
                ),
            )

        if intent_packet["intent"] == "wide_cut":
            if move == "dodge":
                return self._packet(
                    move=move,
                    intent=intent_packet["intent"],
                    result="dodge_success",
                    correct_reads_delta=1,
                    message=(
                        "You step outside the looping cut and let "
                        "the blade pass."
                    ),
                )

            if move == "deflect":
                roll = self._percent_roll(
                    technique_roll,
                    "technique_roll",
                )

                if roll <= profile["deflect_success_chance"]:
                    return self._packet(
                        move=move,
                        intent=intent_packet["intent"],
                        result="deflect_success",
                        guard_damage=1,
                        conduct_delta=1,
                        correct_reads_delta=1,
                        message=(
                            "You beat the flat of the blade aside and "
                            "land an immediate light riposte."
                        ),
                    )

                return self._packet(
                    move=move,
                    intent=intent_packet["intent"],
                    result="deflect_fail",
                    player_damage=light_damage,
                    conduct_delta=-1,
                    wrong_reads_delta=1,
                    message=(
                        "Your deflection misses the flat. The wide cut "
                        "catches you with a light strike."
                    ),
                )

            return self._packet(
                move=move,
                intent=intent_packet["intent"],
                result="wide_punish",
                player_damage=light_damage,
                conduct_delta=-1,
                wrong_reads_delta=1,
                message=(
                    "You stay inside the looping line. The guard's "
                    "wide cut catches you."
                ),
            )

        if intent_packet["intent"] == "driving_lunge":
            if move == "dodge":
                return self._packet(
                    move=move,
                    intent=intent_packet["intent"],
                    result="dodge_success",
                    correct_reads_delta=1,
                    message=(
                        "You move off the lunge line before the guard "
                        "can drive through your center."
                    ),
                )

            return self._packet(
                move=move,
                intent=intent_packet["intent"],
                result="lunge_punish",
                player_damage=heavy_damage,
                conduct_delta=-1,
                wrong_reads_delta=1,
                message=(
                    "You do not leave the lunge line. The guard drives "
                    "a heavy attack into you."
                ),
            )

        raise RuntimeError(
            "unhandled guard combat intent"
        )

    def resolve_player_loss_outcome(
        self,
        *,
        rank,
        roll: int,
        trust: float,
        fear: int,
        witnesses: int,
        royal_alert: int,
        execution_memory: int,
    ) -> dict:
        """
        Classify a player defeat as escape, detention, or rare death.

        Social context is explicit input. It affects aftermath only,
        never direct sword-hit math.
        """
        profile = self.guard_profile(rank)
        roll = self._percent_roll(roll, "loss_roll")

        if not isinstance(witnesses, int) or witnesses < 1:
            raise ValueError(
                "witnesses must be a positive integer"
            )

        if not isinstance(fear, int) or fear < 0:
            raise ValueError(
                "fear must be a non-negative integer"
            )

        if (
            not isinstance(royal_alert, int)
            or royal_alert < 0
        ):
            raise ValueError(
                "royal_alert must be a non-negative integer"
            )

        if (
            not isinstance(execution_memory, int)
            or execution_memory < 0
        ):
            raise ValueError(
                "execution_memory must be a non-negative integer"
            )

        escape = profile["escape_chance"]
        death = profile["death_chance"]

        if trust >= 0.25 and witnesses >= 3:
            escape += 8

        if trust <= -0.25:
            escape -= 4

        if fear >= 3:
            escape -= 4
            death += 1

        if royal_alert >= 3:
            escape -= 4
            death += 1

        if execution_memory > 0:
            escape -= 3
            death += 1

        escape = max(0, min(60, escape))
        death = max(1, min(10, death))
        detention = 100 - escape - death

        if roll <= death:
            outcome = "death"
        elif roll <= death + escape:
            outcome = "escape"
        else:
            outcome = "detention"

        return {
            "outcome": outcome,
            "escape_chance": escape,
            "detention_chance": detention,
            "death_chance": death,
        }


    def resolve_guard_down_outcome(
        self,
        *,
        choice,
        conduct: int,
        trust: float,
        fear: int,
        witnesses: int,
    ) -> dict:
        """
        Return the pure social outcome of a defeated guard decision.

        The facade owns world mutation, Ghost calls, TownMemory writes,
        weapon spending, and player-facing presentation.
        """
        if not isinstance(choice, str):
            raise ValueError(
                "Choose leave or execute."
            )

        normalized = choice.lower().strip()

        if normalized in (
            "leave",
            "loot",
            "spare",
            "take",
        ):
            resolution = "leave"
        elif normalized == "execute":
            resolution = "execute"
        else:
            raise ValueError(
                "Choose leave or execute."
            )

        if resolution == "leave":
            earns_support = (
                conduct >= 1
                and trust >= 0.12
                and fear <= 2
                and witnesses >= 3
            )

            return {
                "resolution": "leave",
                "outcome": (
                    "leave_support"
                    if earns_support
                    else "leave_neutral"
                ),
                "gold_delta": 6,
                "heat_delta": 1,
                "royal_alert_delta": 1,
                "fear_delta": -1 if earns_support else 0,
                "ghost_event": (
                    "help"
                    if earns_support
                    else None
                ),
                "execution_memory_response": None,
            }

        execution_is_accepted = (
            conduct >= 2
            and trust >= 0.35
            and fear <= 1
            and witnesses >= 3
        )

        execution_is_rejected = (
            trust <= 0.10
            or fear >= 3
            or witnesses >= 4
        )

        if execution_is_accepted:
            outcome = "execution_accepted"
            fear_delta = -1
            ghost_event = "help"
            memory_response = None
        elif execution_is_rejected:
            outcome = "execution_rejected"
            fear_delta = 1
            ghost_event = "insult"
            memory_response = "rejected"
        else:
            outcome = "execution_uncertain"
            fear_delta = 1
            ghost_event = None
            memory_response = "uncertain"

        return {
            "resolution": "execute",
            "outcome": outcome,
            "gold_delta": 0,
            "heat_delta": 2,
            "royal_alert_delta": 2,
            "fear_delta": fear_delta,
            "ghost_event": ghost_event,
            "execution_memory_response": memory_response,
        }
