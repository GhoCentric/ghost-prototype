"""
Ghost-only social boundary for Ghost Revolution.

The game facade never calls ScenarioRuntime or runtime.api directly.
All social reads, semantic actions, and ticks move through this bridge.
"""

from __future__ import annotations

from copy import deepcopy
import json

from ghost import GhostAPI
from ghost.scenario_runtime import ScenarioRuntime


SOCIAL_SNAPSHOT_SCHEMA_VERSION = "1.0"

_SOCIAL_SNAPSHOT_KEYS = {
    "schema_version",
    "config",
    "actor_id",
    "api",
    "scenario_state",
    "information_sequence",
    "information_entries",
}

_SCENARIO_STATE_KEYS = {
    "warning_count",
    "arrest_count",
    "served_punishment",
    "resistance_remaining",
    "quest_completed",
    "price_records",
}


def _snapshot_copy(value, label: str):
    try:
        return json.loads(
            json.dumps(
                value,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"{label} must be JSON-safe"
        ) from error


def _snapshot_text(value, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")

    return value.strip()


def _snapshot_non_negative_int(value, label: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
    ):
        raise ValueError(
            f"{label} must be a non-negative integer"
        )

    return value


class GhostRevolutionSocialBridge:
    """
    Own the Ghost ScenarioRuntime for exactly one rebellion run.

    Feature systems should use semantic methods here rather than
    reaching into Ghost internals.
    """

    def __init__(
        self,
        config: dict,
        *,
        actor_id: str = "player",
    ) -> None:
        self._runtime = ScenarioRuntime(deepcopy(config))
        self._actor_id = actor_id
        self._information_sequence = 0
        self._information_entries = []

    @property
    def runtime(self) -> ScenarioRuntime:
        """
        Compatibility view for existing tests and diagnostics.

        New feature code must use this bridge's semantic methods.
        """

        return self._runtime

    def current_world(self) -> dict:
        return self._runtime.api.world_state()

    def relationship(self, target: str) -> dict:
        npc_id = self._runtime.config["npc_roles"][target]

        return self._runtime.api.get_relationship(
            self._actor_id,
            npc_id,
        )

    def resolve_action(
        self,
        action_type: str,
        target: str,
    ) -> dict:
        return self._runtime.resolve_action(
            {
                "type": action_type,
                "target": target,
            }
        )

    def tick(self) -> dict:
        return self._runtime.api.tick()

    def build_combat_objective(
        self,
        *,
        actor: str,
        target: str,
        actor_health: int,
        actor_max_health: int,
        target_health: int,
        target_max_health: int,
        turns_remaining: int,
        expected_damage_per_success: int,
        deadline_label: str,
    ) -> dict:
        """
        Route a fight-level strategic objective through Ghost.

        Ghost owns the objective contract. The game supplies only the
        concrete combat state from which Ghost derives the horizon packet.
        """
        return self._runtime.api.build_combat_objective(
            actor=actor,
            target=target,
            actor_health=actor_health,
            actor_max_health=(
                actor_max_health
            ),
            target_health=target_health,
            target_max_health=(
                target_max_health
            ),
            turns_remaining=turns_remaining,
            expected_damage_per_success=(
                expected_damage_per_success
            ),
            deadline_label=deadline_label,
        )

    def advance_combat_initiative(
        self,
        *,
        previous_state: str,
        event: str,
    ) -> dict:
        return self._runtime.api.advance_combat_initiative(
            previous_state=previous_state,
            event=event,
        )

    def lock_combat_recovery_read(
        self,
        *,
        selection_key: str,
        proposed_move: str | None,
        fallback_move: str,
    ) -> dict:
        return self._runtime.api.lock_combat_recovery_read(
            selection_key=selection_key,
            proposed_move=proposed_move,
            fallback_move=fallback_move,
        )

    def resolve_combat_recovery(
        self,
        *,
        read_packet: dict,
        player_move: str,
        light_damage: int,
    ) -> dict:
        return self._runtime.api.resolve_combat_recovery(
            read_packet=read_packet,
            player_move=player_move,
            light_damage=light_damage,
        )

    @staticmethod
    def _garrison_band(garrison: int) -> str:
        if garrison <= 30:
            return "light_presence"

        if garrison <= 60:
            return "moderate_presence"

        return "heavy_presence"

    @staticmethod
    def _garrison_candidates(
        band: str,
        primary_weight: float,
        unknown_weight: float,
    ) -> dict:
        candidates = {
            "light_presence": 0.10,
            "moderate_presence": 0.10,
            "heavy_presence": 0.10,
            "unknown": unknown_weight,
        }

        candidates[band] = primary_weight

        return {
            "garrison_assessment": candidates,
        }

    def _append_information_entry(
        self,
        kind: str,
        **fields,
    ) -> dict:
        self._information_sequence += 1

        entry = {
            "id": (
                "revolution_information_"
                f"{self._information_sequence:06d}"
            ),
            "kind": kind,
        }
        entry.update(deepcopy(fields))

        self._information_entries.append(entry)

        return deepcopy(entry)

    def record_scout_report(
        self,
        town_id: str,
        camp: dict,
        intel_level: int,
        phase_number: int,
        phase_day: int,
    ) -> dict:
        """
        Route one successful scout mission through Ghost's epistemic API.

        Objective camp state, scout observation, scout belief, scout report,
        player evidence, and player belief remain separate packets.
        """
        api = self._runtime.api

        town_id = str(town_id).strip()
        camp_name = str(camp["name"]).strip()
        garrison = int(camp["garrison"])

        subject = f"royal_garrison:{town_id}"
        band = self._garrison_band(garrison)
        reliability = min(
            0.90,
            0.50 + (0.10 * int(intel_level)),
        )

        entry_number = self._information_sequence + 1
        mission_id = (
            f"p{phase_number}_d{phase_day}_"
            f"{town_id}_{intel_level}_{entry_number}"
        )
        scout_id = f"scout_{mission_id}"

        fact = api.record_fact(
            fact_id=f"royal_garrison_{mission_id}",
            source="royal_camp_state",
            subject=subject,
            predicate="garrison_count",
            object=f"{garrison} troops",
            attributes={
                "town": town_id,
                "camp": camp_name,
                "garrison": garrison,
                "phase_number": phase_number,
                "phase_day": phase_day,
            },
        )

        observation = api.observe(
            observer=scout_id,
            kind="scout_visual",
            visible_features=[
                camp_name,
                "royal_tents",
                "armed_patrols",
                f"estimated_{garrison}_troops",
            ],
            reliability=reliability,
            subject=subject,
            provenance={
                "town": town_id,
                "intel_level": intel_level,
                "mission_id": mission_id,
            },
        )

        scout_belief = api.evaluate_beliefs(
            holder=scout_id,
            subject=subject,
            candidates=self._garrison_candidates(
                band=band,
                primary_weight=0.65,
                unknown_weight=0.35,
            ),
            report_quality={
                "direct_observation": reliability,
                "rumor_repetition_likely": 0.05,
            },
            evidence_ids=[observation["id"]],
            provenance={
                "basis": "scout visual observation",
                "mission_id": mission_id,
            },
        )

        report = api.report(
            speaker=scout_id,
            audience=self._actor_id,
            claim={
                "statement": (
                    f"{camp_name} appears to hold about "
                    f"{garrison} royal troops."
                ),
                "town": town_id,
                "camp": camp_name,
                "garrison_estimate": garrison,
                "garrison_band": band,
                "intel_level": intel_level,
            },
            confidence=reliability,
            source_belief_id=scout_belief["id"],
            provenance={
                "channel": "scout_dispatch",
                "mission_id": mission_id,
            },
        )

        evidence = api.add_evidence(
            evidence_type="scout_dispatch",
            source=scout_id,
            subject=subject,
            available_to=self._actor_id,
            supports={
                "garrison_assessment": {
                    band: 0.35,
                },
                "report_quality": {
                    "direct_observation": 0.20,
                },
            },
            provenance={
                "report_id": report["id"],
                "mission_id": mission_id,
            },
        )

        previous = api.get_belief(
            self._actor_id,
            subject,
        )

        if previous is None:
            player_belief = api.evaluate_beliefs(
                holder=self._actor_id,
                subject=subject,
                candidates=self._garrison_candidates(
                    band=band,
                    primary_weight=0.45,
                    unknown_weight=0.55,
                ),
                report_quality={
                    "direct_observation": 0.10,
                    "rumor_repetition_likely": 0.15,
                },
                evidence_ids=[
                    report["id"],
                    evidence["id"],
                ],
                provenance={
                    "basis": "first scout report",
                    "mission_id": mission_id,
                },
            )
        else:
            player_belief = api.evaluate_beliefs(
                holder=self._actor_id,
                subject=subject,
                previous_belief_id=previous["id"],
                evidence_ids=[
                    report["id"],
                    evidence["id"],
                ],
                provenance={
                    "basis": "additional scout report",
                    "mission_id": mission_id,
                },
            )

        belief_view = player_belief["dimensions"][
            "garrison_assessment"
        ]

        return self._append_information_entry(
            "scout_report",
            town=town_id,
            subject=subject,
            intel_level=intel_level,
            fact_id=fact["fact_id"],
            fact_record_id=fact["id"],
            observation_id=observation["id"],
            scout_belief_id=scout_belief["id"],
            report_id=report["id"],
            evidence_id=evidence["id"],
            player_belief_id=player_belief["id"],
            player_belief={
                "dominant_candidate": belief_view[
                    "dominant_candidate"
                ],
                "confidence": belief_view["confidence"],
                "uncertainty": belief_view["uncertainty"],
            },
            message=(
                f"{town_id.title()} report {intel_level}/3: "
                f"{camp_name} appears to hold about "
                f"{garrison} royal troops."
            ),
        )

    def record_scout_capture(
        self,
        town_id: str,
        risk: int,
        phase_number: int,
        phase_day: int,
    ) -> dict:
        """
        Record an objective scout capture and a player-facing report.

        The capture fact does not create a player belief automatically.
        """
        api = self._runtime.api

        town_id = str(town_id).strip()

        entry_number = self._information_sequence + 1
        mission_id = (
            f"p{phase_number}_d{phase_day}_"
            f"{town_id}_capture_{entry_number}"
        )

        fact = api.record_fact(
            fact_id=f"scout_capture_{mission_id}",
            source="royal_patrol",
            subject=f"scout_mission:{town_id}",
            predicate="captured",
            object="scout",
            attributes={
                "town": town_id,
                "capture_risk": risk,
                "phase_number": phase_number,
                "phase_day": phase_day,
            },
        )

        report = api.report(
            speaker="scout_dispatch",
            audience=self._actor_id,
            claim={
                "statement": (
                    f"{town_id.title()} scout captured by royal patrols."
                ),
                "town": town_id,
                "capture_risk": risk,
            },
            confidence=0.90,
            provenance={
                "channel": "missing_scout_notice",
                "mission_id": mission_id,
            },
        )

        return self._append_information_entry(
            "scout_capture",
            town=town_id,
            fact_id=fact["fact_id"],
            fact_record_id=fact["id"],
            report_id=report["id"],
            message=(
                f"{town_id.title()} scout captured by royal patrols. "
                f"Capture risk was {risk}%."
            ),
        )

    def information_summary(self) -> dict:
        """
        Return copy-safe player-facing information state.

        This contains reports and player beliefs, not raw objective facts.
        """
        latest_scout_beliefs = {}

        for entry in self._information_entries:
            if entry["kind"] == "scout_report":
                latest_scout_beliefs[entry["town"]] = deepcopy(
                    entry["player_belief"]
                )

        return {
            "entries": deepcopy(self._information_entries),
            "latest_scout_beliefs": latest_scout_beliefs,
        }

    def snapshot(self) -> dict:
        """
        Return a JSON-safe snapshot of Ghost and game-facing social state.
        """
        runtime = self._runtime

        return _snapshot_copy(
            {
                "schema_version": (
                    SOCIAL_SNAPSHOT_SCHEMA_VERSION
                ),
                "config": runtime.config,
                "actor_id": self._actor_id,
                "api": runtime.api.snapshot(),
                "scenario_state": {
                    "warning_count": runtime.warning_count,
                    "arrest_count": runtime.arrest_count,
                    "served_punishment": (
                        runtime.served_punishment
                    ),
                    "resistance_remaining": (
                        runtime.resistance_remaining
                    ),
                    "quest_completed": runtime.quest_completed,
                    "price_records": runtime.price_records,
                },
                "information_sequence": (
                    self._information_sequence
                ),
                "information_entries": (
                    self._information_entries
                ),
            },
            "Ghost Revolution social snapshot",
        )

    @classmethod
    def from_snapshot(
        cls,
        snapshot: dict,
    ) -> "GhostRevolutionSocialBridge":
        """
        Restore Ghost and social bookkeeping from snapshot() output.
        """
        if not isinstance(snapshot, dict):
            raise ValueError(
                "social snapshot must be a dict"
            )

        snapshot = _snapshot_copy(
            snapshot,
            "social snapshot",
        )

        if set(snapshot) != _SOCIAL_SNAPSHOT_KEYS:
            raise ValueError(
                "social snapshot has unsupported keys"
            )

        if (
            snapshot["schema_version"]
            != SOCIAL_SNAPSHOT_SCHEMA_VERSION
        ):
            raise ValueError(
                "unsupported social snapshot schema version"
            )

        config = snapshot["config"]

        if not isinstance(config, dict):
            raise ValueError(
                "social snapshot config must be a dict"
            )

        actor_id = _snapshot_text(
            snapshot["actor_id"],
            "social snapshot actor id",
        )

        scenario_state = snapshot["scenario_state"]

        if (
            not isinstance(scenario_state, dict)
            or set(scenario_state) != _SCENARIO_STATE_KEYS
        ):
            raise ValueError(
                "social snapshot scenario state is invalid"
            )

        information_sequence = _snapshot_non_negative_int(
            snapshot["information_sequence"],
            "social snapshot information sequence",
        )
        information_entries = snapshot["information_entries"]

        if not isinstance(information_entries, list):
            raise ValueError(
                "social snapshot information entries must be a list"
            )

        if information_sequence != len(information_entries):
            raise ValueError(
                "social snapshot information sequence is invalid"
            )

        warning_count = _snapshot_non_negative_int(
            scenario_state["warning_count"],
            "social snapshot warning count",
        )
        arrest_count = _snapshot_non_negative_int(
            scenario_state["arrest_count"],
            "social snapshot arrest count",
        )
        resistance_remaining = _snapshot_non_negative_int(
            scenario_state["resistance_remaining"],
            "social snapshot resistance remaining",
        )

        if (
            not isinstance(
                scenario_state["served_punishment"],
                bool,
            )
            or not isinstance(
                scenario_state["quest_completed"],
                bool,
            )
            or not isinstance(
                scenario_state["price_records"],
                dict,
            )
        ):
            raise ValueError(
                "social snapshot scenario state is invalid"
            )

        bridge = cls(
            deepcopy(config),
            actor_id=actor_id,
        )
        bridge._runtime.api = GhostAPI.from_snapshot(
            snapshot["api"]
        )
        bridge._runtime.warning_count = warning_count
        bridge._runtime.arrest_count = arrest_count
        bridge._runtime.served_punishment = (
            scenario_state["served_punishment"]
        )
        bridge._runtime.resistance_remaining = (
            resistance_remaining
        )
        bridge._runtime.quest_completed = (
            scenario_state["quest_completed"]
        )
        bridge._runtime.price_records = deepcopy(
            scenario_state["price_records"]
        )
        bridge._information_sequence = information_sequence
        bridge._information_entries = deepcopy(
            information_entries
        )

        return bridge

