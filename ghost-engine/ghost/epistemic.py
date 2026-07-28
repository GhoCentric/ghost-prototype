"""
Deterministic epistemic state for Ghost.

Ghost stores objective facts separately from observations, beliefs,
reports, and evidence. It never turns speech into truth automatically
and never hardcodes game consequences.
"""

from __future__ import annotations

from copy import deepcopy
import json
import math
from typing import Any


EPISTEMIC_SNAPSHOT_SCHEMA_VERSION = "1.0"

_EPISTEMIC_SNAPSHOT_KEYS = {
    "schema_version",
    "tick",
    "sequence",
    "records",
}

_EPISTEMIC_RECORD_KINDS = {
    "fact",
    "observation",
    "report",
    "evidence",
    "belief",
    "tick",
}


def _copy_json(value: Any, label: str) -> Any:
    try:
        return json.loads(
            json.dumps(
                value,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be JSON-safe") from exc


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")

    return value.strip()


def _probability(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise ValueError(f"{label} must be a number")

    value = float(value)

    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{label} must be between 0.0 and 1.0")

    return value


def _weight(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise ValueError(f"{label} must be a number")

    value = float(value)

    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{label} must be non-negative")

    return value


def _snapshot_non_negative_int(
    value: Any,
    label: str,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
    ):
        raise ValueError(
            f"{label} must be a non-negative integer"
        )

    return value



def _actors(value: Any, label: str) -> list[str]:
    if value is None:
        return []

    if isinstance(value, str):
        values = [value]
    elif isinstance(value, set):
        values = sorted(value)
    elif isinstance(value, (list, tuple)):
        values = list(value)
    else:
        raise ValueError(
            f"{label} must be a string, list, tuple, set, or None"
        )

    out = []

    for item in values:
        item = _text(item, label)

        if item not in out:
            out.append(item)

    return out


def _ids(value: Any, label: str) -> list[str]:
    if value is None:
        return []

    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{label} must be a list or tuple")

    out = []

    for item in value:
        item = _text(item, label)

        if item not in out:
            out.append(item)

    return out


def _dimensions(
    value: dict,
    label: str,
    allow_empty: bool = False,
) -> dict[str, dict[str, float]]:
    """
    Normalize exclusive candidate dimensions.

    Flat candidate maps become the "default" dimension:

        {"royal_confiscation": 0.60, "unknown": 0.40}

    Nested maps keep independent candidate spaces:

        {
            "cause": {
                "royal_confiscation": 0.60,
                "unknown": 0.40,
            },
            "quantity": {
                "all_taken": 0.20,
                "some_taken": 0.80,
            },
        }

    Every dimension is normalized independently in a belief packet.
    """
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a dict")

    if not value:
        if allow_empty:
            return {}

        raise ValueError(f"{label} must not be empty")

    flat = all(
        not isinstance(item, bool)
        and isinstance(item, (int, float))
        for item in value.values()
    )
    raw = {"default": value} if flat else value
    out = {}

    for dimension, candidates in raw.items():
        dimension = _text(dimension, f"{label} dimension")

        if dimension == "report_quality":
            raise ValueError(
                "report_quality is independent. Pass it through "
                "the report_quality argument instead."
            )

        if not isinstance(candidates, dict) or not candidates:
            raise ValueError(
                f"{label} dimension {dimension!r} "
                "must be a non-empty dict"
            )

        parsed = {}

        for candidate, strength in candidates.items():
            candidate = _text(candidate, f"{label} candidate")
            parsed[candidate] = _weight(
                strength,
                f"{label} strength",
            )

        if sum(parsed.values()) <= 0.0:
            raise ValueError(
                f"{label} dimension {dimension!r} "
                "must have positive total weight"
            )

        out[dimension] = parsed

    return out


def _report_quality(
    value: dict | None,
    label: str,
) -> dict[str, float]:
    """
    Normalize independent report-quality values.

    These are intentionally not normalized against each other. A report
    can be directly observed and exaggerated at the same time.
    """
    if value is None:
        return {}

    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a dict or None")

    out = {}

    for name, confidence in value.items():
        out[_text(name, f"{label} key")] = _probability(
            confidence,
            f"{label} value",
        )

    return out


def _evidence_adjustments(
    value: dict | None,
    label: str,
) -> dict[str, dict]:
    """
    Normalize evidence strengths.

    `report_quality` is reserved for independent quality signals:

        {
            "cause": {"royal_confiscation": 0.30},
            "quantity": {"some_taken": 0.50},
            "report_quality": {
                "exaggeration_likely": 0.20,
            },
        }
    """
    if value is None:
        return {
            "dimensions": {},
            "report_quality": {},
        }

    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a dict or None")

    raw = dict(value)
    quality = raw.pop("report_quality", None)

    return {
        "dimensions": _dimensions(
            raw,
            label,
            allow_empty=True,
        ),
        "report_quality": _report_quality(
            quality,
            f"{label} report quality",
        ),
    }


_EPISTEMIC_COMMON_RECORD_KEYS = {
    "id",
    "kind",
    "sequence",
    "tick",
}


_EPISTEMIC_RECORD_FIELDS = {
    "fact": {
        "attributes",
        "fact_id",
        "object",
        "predicate",
        "source",
        "subject",
    },
    "observation": {
        "observation_kind",
        "observer",
        "provenance",
        "reliability",
        "subject",
        "visible_features",
    },
    "report": {
        "audience",
        "claim",
        "confidence",
        "provenance",
        "source_belief_id",
        "speaker",
    },
    "evidence": {
        "available_to",
        "contradicts",
        "evidence_type",
        "provenance",
        "source",
        "subject",
        "supports",
    },
    "belief": {
        "base_dimensions",
        "base_report_quality",
        "dimensions",
        "evidence_ids",
        "holder",
        "previous_belief_id",
        "provenance",
        "report_quality",
        "subject",
    },
    "tick": set(),
}


def _epistemic_snapshot_mapping(
    value,
    label: str,
) -> dict:
    if not isinstance(value, dict):
        raise ValueError(
            f"{label} must be a dict"
        )

    return value


def _epistemic_snapshot_optional_text(
    value,
    label: str,
):
    if value is None:
        return None

    return _text(
        value,
        label,
    )


def _epistemic_snapshot_text_list(
    value,
    label: str,
    *,
    allow_empty: bool,
) -> list[str]:
    values = _ids(
        value,
        label,
    )

    if not allow_empty and not values:
        raise ValueError(
            f"{label} must not be empty"
        )

    return values


def _validate_epistemic_probability_map(
    value,
    label: str,
) -> dict[str, float]:
    value = _epistemic_snapshot_mapping(
        value,
        label,
    )

    normalized = {}

    for name, confidence in value.items():
        name = _text(
            name,
            f"{label} key",
        )

        normalized[name] = _probability(
            confidence,
            f"{label} value",
        )

    return normalized


def _validate_epistemic_weight_dimensions(
    value,
    label: str,
    *,
    allow_empty: bool,
) -> dict[str, dict[str, float]]:
    value = _epistemic_snapshot_mapping(
        value,
        label,
    )

    if not allow_empty and not value:
        raise ValueError(
            f"{label} must not be empty"
        )

    normalized = {}

    for dimension, candidates in value.items():
        dimension = _text(
            dimension,
            f"{label} dimension",
        )

        candidates = _epistemic_snapshot_mapping(
            candidates,
            (
                f"{label} dimension "
                f"{dimension}"
            ),
        )

        if not candidates:
            raise ValueError(
                f"{label} dimension "
                f"{dimension!r} must not be empty"
            )

        normalized_candidates = {}

        for candidate, weight in candidates.items():
            candidate = _text(
                candidate,
                f"{label} candidate",
            )

            normalized_candidates[candidate] = _weight(
                weight,
                f"{label} weight",
            )

        if sum(normalized_candidates.values()) <= 0.0:
            raise ValueError(
                f"{label} dimension "
                f"{dimension!r} must have positive weight"
            )

        normalized[dimension] = (
            normalized_candidates
        )

    return normalized


def _validate_epistemic_adjustments(
    value,
    label: str,
):
    value = _epistemic_snapshot_mapping(
        value,
        label,
    )

    if set(value) != {
        "dimensions",
        "report_quality",
    }:
        raise ValueError(
            f"{label} has unsupported keys"
        )

    _validate_epistemic_weight_dimensions(
        value["dimensions"],
        f"{label} dimensions",
        allow_empty=True,
    )

    _validate_epistemic_probability_map(
        value["report_quality"],
        f"{label} report_quality",
    )


def _validate_epistemic_packet_dimensions(
    value,
):
    value = _epistemic_snapshot_mapping(
        value,
        "epistemic snapshot belief dimensions",
    )

    if not value:
        raise ValueError(
            "epistemic snapshot belief "
            "dimensions must not be empty"
        )

    for dimension_name, data in value.items():
        dimension_name = _text(
            dimension_name,
            (
                "epistemic snapshot belief "
                "dimension name"
            ),
        )

        data = _epistemic_snapshot_mapping(
            data,
            (
                "epistemic snapshot belief "
                f"dimension {dimension_name}"
            ),
        )

        required = {
            "candidates",
            "confidence",
            "dominant_candidate",
            "uncertainty",
        }

        if set(data) != required:
            raise ValueError(
                "epistemic snapshot belief "
                f"dimension {dimension_name!r} "
                "has unsupported fields"
            )

        candidates = _epistemic_snapshot_mapping(
            data["candidates"],
            (
                "epistemic snapshot belief "
                f"dimension {dimension_name} candidates"
            ),
        )

        if not candidates:
            raise ValueError(
                "epistemic snapshot belief "
                f"dimension {dimension_name!r} "
                "candidates must not be empty"
            )

        normalized_candidates = {}

        for candidate, probability in (
            candidates.items()
        ):
            candidate = _text(
                candidate,
                (
                    "epistemic snapshot belief "
                    f"dimension {dimension_name} candidate"
                ),
            )

            normalized_candidates[candidate] = (
                _probability(
                    probability,
                    (
                        "epistemic snapshot belief "
                        f"dimension {dimension_name} "
                        f"candidate {candidate}"
                    ),
                )
            )

        total = sum(
            normalized_candidates.values()
        )

        if not math.isclose(
            total,
            1.0,
            rel_tol=1e-9,
            abs_tol=1e-9,
        ):
            raise ValueError(
                "epistemic snapshot belief "
                f"dimension {dimension_name!r} "
                "candidate probabilities must total 1.0"
            )

        dominant = _text(
            data["dominant_candidate"],
            (
                "epistemic snapshot belief "
                f"dimension {dimension_name} "
                "dominant_candidate"
            ),
        )

        if dominant not in normalized_candidates:
            raise ValueError(
                "epistemic snapshot belief "
                f"dimension {dimension_name!r} "
                "dominant candidate is absent"
            )

        expected_dominant, expected_confidence = (
            sorted(
                normalized_candidates.items(),
                key=lambda item: (
                    -item[1],
                    item[0],
                ),
            )[0]
        )

        if dominant != expected_dominant:
            raise ValueError(
                "epistemic snapshot belief "
                f"dimension {dimension_name!r} "
                "dominant candidate is inconsistent"
            )

        confidence = _probability(
            data["confidence"],
            (
                "epistemic snapshot belief "
                f"dimension {dimension_name} confidence"
            ),
        )

        uncertainty = _probability(
            data["uncertainty"],
            (
                "epistemic snapshot belief "
                f"dimension {dimension_name} uncertainty"
            ),
        )

        if not math.isclose(
            confidence,
            expected_confidence,
            rel_tol=1e-9,
            abs_tol=1e-9,
        ):
            raise ValueError(
                "epistemic snapshot belief "
                f"dimension {dimension_name!r} "
                "confidence is inconsistent"
            )

        if not math.isclose(
            confidence + uncertainty,
            1.0,
            rel_tol=1e-9,
            abs_tol=1e-9,
        ):
            raise ValueError(
                "epistemic snapshot belief "
                f"dimension {dimension_name!r} "
                "confidence and uncertainty "
                "must total 1.0"
            )


def _epistemic_record_accessible_to(
    record: dict,
    holder: str,
) -> bool:
    kind = record["kind"]

    if kind == "observation":
        return record["observer"] == holder

    if kind == "report":
        return holder in record["audience"]

    if kind == "evidence":
        return holder in record["available_to"]

    return False


def _validate_epistemic_record_semantics(
    record: dict,
    prior_by_id: dict[str, dict],
    prior_beliefs: dict[str, dict],
):
    record_kind = record["kind"]

    expected_fields = (
        _EPISTEMIC_COMMON_RECORD_KEYS
        | _EPISTEMIC_RECORD_FIELDS[
            record_kind
        ]
    )

    missing = expected_fields - set(record)

    if missing:
        raise ValueError(
            "epistemic snapshot "
            f"{record_kind} record is missing fields: "
            + ", ".join(sorted(missing))
        )

    unknown = set(record) - expected_fields

    if unknown:
        raise ValueError(
            "epistemic snapshot "
            f"{record_kind} record has unsupported fields: "
            + ", ".join(sorted(unknown))
        )

    if record_kind == "tick":
        return

    if record_kind == "fact":
        for field_name in (
            "fact_id",
            "source",
            "subject",
            "predicate",
            "object",
        ):
            _text(
                record[field_name],
                (
                    "epistemic snapshot fact "
                    f"{field_name.replace('_', ' ')}"
                ),
            )

        _epistemic_snapshot_mapping(
            record["attributes"],
            "epistemic snapshot fact attributes",
        )

        return

    provenance = _epistemic_snapshot_mapping(
        record["provenance"],
        "epistemic snapshot record provenance",
    )

    if record_kind == "observation":
        _text(
            record["observer"],
            (
                "epistemic snapshot "
                "observation observer"
            ),
        )

        _text(
            record["observation_kind"],
            (
                "epistemic snapshot "
                "observation kind"
            ),
        )

        _epistemic_snapshot_optional_text(
            record["subject"],
            (
                "epistemic snapshot "
                "observation subject"
            ),
        )

        _epistemic_snapshot_text_list(
            record["visible_features"],
            (
                "epistemic snapshot "
                "observation visible features"
            ),
            allow_empty=False,
        )

        _probability(
            record["reliability"],
            (
                "epistemic snapshot "
                "observation reliability"
            ),
        )

        return

    if record_kind == "report":
        speaker = _text(
            record["speaker"],
            (
                "epistemic snapshot "
                "report speaker"
            ),
        )

        _epistemic_snapshot_text_list(
            record["audience"],
            (
                "epistemic snapshot "
                "report audience"
            ),
            allow_empty=False,
        )

        _epistemic_snapshot_mapping(
            record["claim"],
            "epistemic snapshot report claim",
        )

        _probability(
            record["confidence"],
            (
                "epistemic snapshot "
                "report confidence"
            ),
        )

        source_belief_id = record[
            "source_belief_id"
        ]

        if source_belief_id is not None:
            source_belief_id = _text(
                source_belief_id,
                (
                    "epistemic snapshot "
                    "source belief id"
                ),
            )

            source_belief = (
                prior_beliefs.get(
                    source_belief_id
                )
            )

            if source_belief is None:
                raise ValueError(
                    "epistemic snapshot report "
                    "source belief does not exist"
                )

            if (
                source_belief["holder"]
                != speaker
            ):
                raise ValueError(
                    "epistemic snapshot report "
                    "speaker must own source belief"
                )

        return

    if record_kind == "evidence":
        _text(
            record["evidence_type"],
            (
                "epistemic snapshot "
                "evidence type"
            ),
        )

        _text(
            record["source"],
            (
                "epistemic snapshot "
                "evidence source"
            ),
        )

        _epistemic_snapshot_optional_text(
            record["subject"],
            (
                "epistemic snapshot "
                "evidence subject"
            ),
        )

        _epistemic_snapshot_text_list(
            record["available_to"],
            (
                "epistemic snapshot "
                "evidence availability"
            ),
            allow_empty=True,
        )

        _validate_epistemic_adjustments(
            record["supports"],
            "epistemic snapshot evidence supports",
        )

        _validate_epistemic_adjustments(
            record["contradicts"],
            "epistemic snapshot evidence contradicts",
        )

        return

    holder = _text(
        record["holder"],
        (
            "epistemic snapshot "
            "belief holder"
        ),
    )

    subject = _text(
        record["subject"],
        (
            "epistemic snapshot "
            "belief subject"
        ),
    )

    _validate_epistemic_weight_dimensions(
        record["base_dimensions"],
        (
            "epistemic snapshot belief "
            "base_dimensions"
        ),
        allow_empty=False,
    )

    _validate_epistemic_probability_map(
        record["base_report_quality"],
        (
            "epistemic snapshot belief "
            "base_report_quality"
        ),
    )

    _validate_epistemic_packet_dimensions(
        record["dimensions"]
    )

    _validate_epistemic_probability_map(
        record["report_quality"],
        (
            "epistemic snapshot belief "
            "report_quality"
        ),
    )

    evidence_ids = (
        _epistemic_snapshot_text_list(
            record["evidence_ids"],
            (
                "epistemic snapshot "
                "belief evidence ids"
            ),
            allow_empty=True,
        )
    )

    for evidence_id in evidence_ids:
        evidence_record = (
            prior_by_id.get(
                evidence_id
            )
        )

        if evidence_record is None:
            raise ValueError(
                "epistemic snapshot belief "
                "references a future or unknown record"
            )

        if evidence_record["kind"] not in {
            "observation",
            "report",
            "evidence",
        }:
            raise ValueError(
                "epistemic snapshot belief "
                "evidence ids must reference "
                "observations, reports, or evidence"
            )

        if not _epistemic_record_accessible_to(
            evidence_record,
            holder,
        ):
            raise ValueError(
                "epistemic snapshot belief "
                f"holder cannot access {evidence_id!r}"
            )

        evidence_subject = evidence_record.get(
            "subject"
        )

        if (
            evidence_record["kind"]
            == "evidence"
            and evidence_subject is not None
            and evidence_subject != subject
        ):
            raise ValueError(
                "epistemic snapshot belief "
                "evidence subject does not match"
            )

    previous_belief_id = record[
        "previous_belief_id"
    ]

    if previous_belief_id is not None:
        previous_belief_id = _text(
            previous_belief_id,
            (
                "epistemic snapshot "
                "previous belief id"
            ),
        )

        previous = prior_beliefs.get(
            previous_belief_id
        )

        if previous is None:
            raise ValueError(
                "epistemic snapshot previous "
                "belief does not exist"
            )

        if previous["holder"] != holder:
            raise ValueError(
                "epistemic snapshot previous "
                "belief holder does not match"
            )

        if previous["subject"] != subject:
            raise ValueError(
                "epistemic snapshot previous "
                "belief subject does not match"
            )

    if set(provenance) != {
        "evidence_ids",
        "metadata",
    }:
        raise ValueError(
            "epistemic snapshot belief provenance "
            "has unsupported keys"
        )

    provenance_ids = (
        _epistemic_snapshot_text_list(
            provenance["evidence_ids"],
            (
                "epistemic snapshot belief "
                "provenance evidence ids"
            ),
            allow_empty=True,
        )
    )

    if provenance_ids != evidence_ids:
        raise ValueError(
            "epistemic snapshot belief provenance "
            "evidence ids do not match"
        )

    _epistemic_snapshot_mapping(
        provenance["metadata"],
        (
            "epistemic snapshot belief "
            "provenance metadata"
        ),
    )


class EpistemicRuntime:
    """
    First-order deterministic belief runtime.

    Facts are objective state.
    Observations, reports, and evidence are actor-limited inputs.
    Beliefs are explicit evaluations with append-only provenance.

    The runtime does not decide prices, fear, recruitment, patrols,
    dialogue, or any other game-specific consequence.
    """

    def __init__(self):
        self._tick = 0
        self._sequence = 0
        self._records: list[dict] = []
        self._by_id: dict[str, dict] = {}
        self._facts: dict[str, dict] = {}
        self._beliefs: dict[str, dict] = {}
        self._latest: dict[tuple[str, str], str] = {}

    def _append(self, kind: str, **fields) -> dict:
        self._sequence += 1

        record = {
            "id": f"epistemic_{self._sequence:06d}",
            "kind": kind,
            "sequence": self._sequence,
            "tick": self._tick,
        }
        record.update(_copy_json(fields, "epistemic record"))

        self._records.append(record)
        self._by_id[record["id"]] = record

        return record

    def record_fact(
        self,
        fact_id: str,
        source: str,
        subject: str,
        predicate: str,
        object: str,
        attributes: dict | None = None,
    ) -> dict:
        """
        Record objective truth.

        No actor learns this fact merely because it exists.
        """
        if attributes is not None and not isinstance(
            attributes,
            dict,
        ):
            raise ValueError("fact attributes must be a dict or None")

        record = self._append(
            "fact",
            fact_id=_text(fact_id, "fact id"),
            source=_text(source, "fact source"),
            subject=_text(subject, "fact subject"),
            predicate=_text(predicate, "fact predicate"),
            object=_text(object, "fact object"),
            attributes=_copy_json(
                attributes or {},
                "fact attributes",
            ),
        )
        self._facts[record["fact_id"]] = record

        return deepcopy(record)

    def get_fact(self, fact_id: str) -> dict | None:
        """
        Developer/runtime access to objective truth.

        This does not imply an in-world actor knows the fact.
        """
        fact = self._facts.get(_text(fact_id, "fact id"))

        return deepcopy(fact) if fact is not None else None

    def observe(
        self,
        observer: str,
        kind: str,
        visible_features: list[str] | tuple[str, ...],
        reliability: float,
        provenance: dict | None = None,
        subject: str | None = None,
    ) -> dict:
        """
        Record what one actor saw, heard, or otherwise received.

        Ghost intentionally does not infer a cause from raw features.
        """
        if not isinstance(visible_features, (list, tuple)):
            raise ValueError(
                "visible features must be a list or tuple"
            )

        if provenance is not None and not isinstance(
            provenance,
            dict,
        ):
            raise ValueError(
                "observation provenance must be a dict or None"
            )

        features = [
            _text(feature, "visible feature")
            for feature in visible_features
        ]

        if not features:
            raise ValueError("visible features must not be empty")

        record = self._append(
            "observation",
            observer=_text(observer, "observer"),
            observation_kind=_text(kind, "observation kind"),
            subject=(
                _text(subject, "observation subject")
                if subject is not None
                else None
            ),
            visible_features=features,
            reliability=_probability(
                reliability,
                "observation reliability",
            ),
            provenance=_copy_json(
                provenance or {},
                "observation provenance",
            ),
        )

        return deepcopy(record)

    def report(
        self,
        speaker: str,
        audience: str | list[str] | tuple[str, ...] | set[str],
        claim: dict,
        confidence: float,
        source_belief_id: str | None = None,
        provenance: dict | None = None,
    ) -> dict:
        """
        Record a claim communicated to an audience.

        The report is not objective truth and does not automatically make
        any listener believe the claim.
        """
        speaker = _text(speaker, "report speaker")
        audience = _actors(audience, "report audience")

        if not audience:
            raise ValueError("report audience must not be empty")

        if not isinstance(claim, dict):
            raise ValueError("report claim must be a dict")

        if provenance is not None and not isinstance(
            provenance,
            dict,
        ):
            raise ValueError(
                "report provenance must be a dict or None"
            )

        if source_belief_id is not None:
            source_belief_id = _text(
                source_belief_id,
                "source belief id",
            )
            belief = self._beliefs.get(source_belief_id)

            if belief is None:
                raise ValueError("source belief id does not exist")

            if belief["holder"] != speaker:
                raise ValueError(
                    "report speaker must own source belief"
                )

        record = self._append(
            "report",
            speaker=speaker,
            audience=audience,
            claim=_copy_json(claim, "report claim"),
            confidence=_probability(
                confidence,
                "report confidence",
            ),
            source_belief_id=source_belief_id,
            provenance=_copy_json(
                provenance or {},
                "report provenance",
            ),
        )

        return deepcopy(record)

    def add_evidence(
        self,
        evidence_type: str,
        source: str,
        supports: dict | None = None,
        contradicts: dict | None = None,
        subject: str | None = None,
        available_to: (
            str
            | list[str]
            | tuple[str, ...]
            | set[str]
            | None
        ) = None,
        provenance: dict | None = None,
    ) -> dict:
        """
        Append structured evidence.

        Evidence can exist while hidden. `available_to` is the explicit
        knowledge boundary for an actor using it in a belief revision.
        """
        if provenance is not None and not isinstance(
            provenance,
            dict,
        ):
            raise ValueError(
                "evidence provenance must be a dict or None"
            )

        record = self._append(
            "evidence",
            evidence_type=_text(
                evidence_type,
                "evidence type",
            ),
            source=_text(source, "evidence source"),
            subject=(
                _text(subject, "evidence subject")
                if subject is not None
                else None
            ),
            supports=_evidence_adjustments(
                supports,
                "evidence supports",
            ),
            contradicts=_evidence_adjustments(
                contradicts,
                "evidence contradicts",
            ),
            available_to=_actors(
                available_to,
                "evidence availability",
            ),
            provenance=_copy_json(
                provenance or {},
                "evidence provenance",
            ),
        )

        return deepcopy(record)

    def _available_to(self, record: dict, holder: str) -> bool:
        if record["kind"] == "observation":
            return record["observer"] == holder

        if record["kind"] == "report":
            return holder in record["audience"]

        if record["kind"] == "evidence":
            return holder in record["available_to"]

        return False

    def _evidence_records(
        self,
        holder: str,
        subject: str,
        evidence_ids: list[str],
    ) -> list[dict]:
        records = []

        for evidence_id in evidence_ids:
            record = self._by_id.get(evidence_id)

            if record is None:
                raise ValueError(
                    f"unknown epistemic record id: {evidence_id}"
                )

            if record["kind"] not in {
                "observation",
                "report",
                "evidence",
            }:
                raise ValueError(
                    "belief evidence ids must reference observations, "
                    "reports, or evidence"
                )

            if not self._available_to(record, holder):
                raise ValueError(
                    f"{holder!r} cannot access {evidence_id!r}"
                )

            if (
                record["kind"] == "evidence"
                and record["subject"] is not None
                and record["subject"] != subject
            ):
                raise ValueError(
                    "evidence subject does not match belief subject"
                )

            records.append(record)

        return records

    def _apply(
        self,
        base_dimensions: dict[str, dict[str, float]],
        base_quality: dict[str, float],
        records: list[dict],
    ) -> tuple[dict[str, dict[str, float]], dict[str, float]]:
        scores = deepcopy(base_dimensions)
        quality = deepcopy(base_quality)

        for record in records:
            if record["kind"] != "evidence":
                continue

            for direction, multiplier in (
                ("supports", 1.0),
                ("contradicts", -1.0),
            ):
                adjustments = record[direction]

                for dimension, changes in adjustments[
                    "dimensions"
                ].items():
                    if dimension not in scores:
                        raise ValueError(
                            "evidence dimension is absent from "
                            "belief candidates"
                        )

                    for candidate, strength in changes.items():
                        if candidate not in scores[dimension]:
                            raise ValueError(
                                "evidence candidate is absent from "
                                "belief candidates"
                            )

                        scores[dimension][candidate] = max(
                            0.0,
                            scores[dimension][candidate]
                            + (strength * multiplier),
                        )

                for signal, strength in adjustments[
                    "report_quality"
                ].items():
                    if signal not in quality:
                        raise ValueError(
                            "evidence report quality signal is absent "
                            "from belief report_quality"
                        )

                    quality[signal] = min(
                        1.0,
                        max(
                            0.0,
                            quality[signal]
                            + (strength * multiplier),
                        ),
                    )

        return scores, quality

    def _packet_dimensions(
        self,
        scores: dict[str, dict[str, float]],
    ) -> dict[str, dict]:
        out = {}

        for dimension, candidates in scores.items():
            total = sum(candidates.values())

            if total <= 0.0:
                raise ValueError(
                    "evidence removed all candidate weight for "
                    f"{dimension!r}"
                )

            distribution = {
                candidate: strength / total
                for candidate, strength in candidates.items()
            }
            dominant, confidence = sorted(
                distribution.items(),
                key=lambda item: (-item[1], item[0]),
            )[0]

            out[dimension] = {
                "candidates": distribution,
                "dominant_candidate": dominant,
                "confidence": confidence,
                "uncertainty": 1.0 - confidence,
            }

        return out

    def evaluate_beliefs(
        self,
        holder: str,
        subject: str,
        candidates: dict | None = None,
        evidence_ids: list[str] | tuple[str, ...] | None = None,
        report_quality: dict | None = None,
        previous_belief_id: str | None = None,
        provenance: dict | None = None,
    ) -> dict:
        """
        Create one actor-owned belief packet.

        candidates are exclusive hypotheses such as cause and quantity.
        report_quality contains independent signals, so direct observation
        and exaggeration can both be likely at the same time.

        Observations and reports carry provenance only. Ghost does not
        invent semantic meaning from generic raw input.
        """
        holder = _text(holder, "belief holder")
        subject = _text(subject, "belief subject")
        new_ids = _ids(evidence_ids, "belief evidence ids")

        if provenance is not None and not isinstance(
            provenance,
            dict,
        ):
            raise ValueError(
                "belief provenance must be a dict or None"
            )

        if previous_belief_id is None:
            if candidates is None:
                raise ValueError(
                    "new beliefs require candidate weights"
                )

            base_dimensions = _dimensions(
                candidates,
                "belief candidates",
            )
            base_quality = _report_quality(
                report_quality,
                "belief report_quality",
            )
            previous_ids = []
        else:
            if candidates is not None or report_quality is not None:
                raise ValueError(
                    "belief revisions use previous_belief_id only"
                )

            previous_belief_id = _text(
                previous_belief_id,
                "previous belief id",
            )
            previous = self._beliefs.get(previous_belief_id)

            if previous is None:
                raise ValueError("previous belief id does not exist")

            if previous["holder"] != holder:
                raise ValueError(
                    "previous belief holder does not match"
                )

            if previous["subject"] != subject:
                raise ValueError(
                    "previous belief subject does not match"
                )

            base_dimensions = deepcopy(
                previous["base_dimensions"]
            )
            base_quality = deepcopy(
                previous["base_report_quality"]
            )
            previous_ids = list(previous["evidence_ids"])

        all_ids = _ids(
            previous_ids + new_ids,
            "belief evidence ids",
        )
        records = self._evidence_records(
            holder,
            subject,
            all_ids,
        )
        scores, quality = self._apply(
            base_dimensions,
            base_quality,
            records,
        )
        record = self._append(
            "belief",
            holder=holder,
            subject=subject,
            base_dimensions=base_dimensions,
            base_report_quality=base_quality,
            dimensions=self._packet_dimensions(scores),
            report_quality=quality,
            evidence_ids=all_ids,
            previous_belief_id=previous_belief_id,
            provenance={
                "evidence_ids": all_ids,
                "metadata": _copy_json(
                    provenance or {},
                    "belief provenance",
                ),
            },
        )

        self._beliefs[record["id"]] = record
        self._latest[(holder, subject)] = record["id"]

        return deepcopy(record)

    def get_belief(
        self,
        holder: str,
        subject: str,
    ) -> dict | None:
        """Return one holder's latest belief for one subject."""
        holder = _text(holder, "belief holder")
        subject = _text(subject, "belief subject")
        belief_id = self._latest.get((holder, subject))

        if belief_id is None:
            return None

        return deepcopy(self._beliefs[belief_id])

    def propagate_belief(
        self,
        speaker: str,
        audience: str | list[str] | tuple[str, ...] | set[str],
        belief_id: str,
        confidence: float | None = None,
        provenance: dict | None = None,
    ) -> dict:
        """
        Convert a belief into a report.

        Recipients receive a report record, not an automatic belief.
        """
        speaker = _text(speaker, "propagation speaker")
        belief_id = _text(belief_id, "belief id")
        belief = self._beliefs.get(belief_id)

        if belief is None:
            raise ValueError("belief id does not exist")

        if belief["holder"] != speaker:
            raise ValueError(
                "propagation speaker must own belief"
            )

        if confidence is None:
            confidence = max(
                data["confidence"]
                for data in belief["dimensions"].values()
            )

        claim = {
            "subject": belief["subject"],
            "dimensions": {
                name: {
                    "dominant_candidate": data[
                        "dominant_candidate"
                    ],
                    "confidence": data["confidence"],
                    "uncertainty": data["uncertainty"],
                }
                for name, data in belief["dimensions"].items()
            },
            "report_quality": belief["report_quality"],
        }

        return self.report(
            speaker=speaker,
            audience=audience,
            claim=claim,
            confidence=confidence,
            source_belief_id=belief_id,
            provenance=provenance,
        )

    def tick(self) -> dict:
        """
        Advance epistemic time without invented confidence decay.

        A generic decay rule would be game policy, so v1 only records
        that time passed.
        """
        self._tick += 1

        return deepcopy(self._append("tick"))

    def snapshot(self) -> dict:
        """
        Return a JSON-safe immutable epistemic snapshot.

        Derived indexes are rebuilt by from_snapshot().
        The append-only record ledger is the persistence source of truth.
        """
        return _copy_json(
            {
                "schema_version": (
                    EPISTEMIC_SNAPSHOT_SCHEMA_VERSION
                ),
                "tick": self._tick,
                "sequence": self._sequence,
                "records": self._records,
            },
            "epistemic snapshot",
        )

    @classmethod
    def from_snapshot(
        cls,
        snapshot: dict,
    ) -> "EpistemicRuntime":
        """
        Restore a deterministic epistemic runtime from validated
        append-only ledger data.

        Record schemas, probability fields, ownership, accessibility,
        evidence references, belief revisions, sequence order, and
        temporal order are validated before the runtime is returned.
        """
        if not isinstance(snapshot, dict):
            raise ValueError(
                "epistemic snapshot must be a dict"
            )

        snapshot = _copy_json(
            snapshot,
            "epistemic snapshot",
        )

        if (
            set(snapshot)
            != _EPISTEMIC_SNAPSHOT_KEYS
        ):
            raise ValueError(
                "epistemic snapshot "
                "has unsupported keys"
            )

        if (
            snapshot["schema_version"]
            != EPISTEMIC_SNAPSHOT_SCHEMA_VERSION
        ):
            raise ValueError(
                "unsupported epistemic "
                "snapshot schema version"
            )

        tick = _snapshot_non_negative_int(
            snapshot["tick"],
            "epistemic snapshot tick",
        )

        sequence = (
            _snapshot_non_negative_int(
                snapshot["sequence"],
                (
                    "epistemic snapshot "
                    "sequence"
                ),
            )
        )

        records = snapshot["records"]

        if not isinstance(records, list):
            raise ValueError(
                "epistemic snapshot records "
                "must be a list"
            )

        if sequence != len(records):
            raise ValueError(
                "epistemic snapshot sequence "
                "must match records"
            )

        runtime = cls()
        previous_tick = 0

        for expected_sequence, record in (
            enumerate(
                records,
                start=1,
            )
        ):
            if not isinstance(record, dict):
                raise ValueError(
                    "epistemic snapshot record "
                    "must be a dict"
                )

            missing_common = (
                _EPISTEMIC_COMMON_RECORD_KEYS
                - set(record)
            )

            if missing_common:
                raise ValueError(
                    "epistemic snapshot record "
                    "is missing common fields: "
                    + ", ".join(
                        sorted(missing_common)
                    )
                )

            expected_id = (
                f"epistemic_"
                f"{expected_sequence:06d}"
            )

            if record["id"] != expected_id:
                raise ValueError(
                    "epistemic snapshot "
                    "record id is invalid"
                )

            record_sequence = (
                _snapshot_non_negative_int(
                    record["sequence"],
                    (
                        "epistemic snapshot "
                        "record sequence"
                    ),
                )
            )

            if (
                record_sequence
                != expected_sequence
            ):
                raise ValueError(
                    "epistemic snapshot "
                    "record sequence is invalid"
                )

            record_kind = record["kind"]

            if (
                record_kind
                not in _EPISTEMIC_RECORD_KINDS
            ):
                raise ValueError(
                    "epistemic snapshot "
                    "record kind is invalid"
                )

            record_tick = (
                _snapshot_non_negative_int(
                    record["tick"],
                    (
                        "epistemic snapshot "
                        "record tick"
                    ),
                )
            )

            if (
                record_tick < previous_tick
                or record_tick > tick
            ):
                raise ValueError(
                    "epistemic snapshot "
                    "record tick is invalid"
                )

            _validate_epistemic_record_semantics(
                record,
                runtime._by_id,
                runtime._beliefs,
            )

            if record_kind == "fact":
                runtime._facts[
                    record["fact_id"]
                ] = record

            elif record_kind == "belief":
                holder = record["holder"]
                subject = record["subject"]

                runtime._beliefs[
                    expected_id
                ] = record

                runtime._latest[
                    (
                        holder,
                        subject,
                    )
                ] = expected_id

            runtime._records.append(
                record
            )

            runtime._by_id[
                expected_id
            ] = record

            previous_tick = record_tick

        if records and previous_tick != tick:
            raise ValueError(
                "epistemic snapshot tick "
                "does not match records"
            )

        runtime._tick = tick
        runtime._sequence = sequence

        return runtime

    def records(self) -> list[dict]:
        """Return copied append-only epistemic history."""
        return deepcopy(self._records)

