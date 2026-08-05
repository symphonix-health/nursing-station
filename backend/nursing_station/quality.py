"""Nursing quality dataset computation (FR-NS-160, FR-NS-161).

The measure DEFINITIONS -- title, type, numerator, denominator, exclusions, unit
and citation -- live in the country pack, because they are jurisdictional policy
and change on their own schedule. This module only applies them to the ward's
own records.

Three states, kept distinct on purpose:

* ``computed`` -- both sides came from repo-owned records.
* ``source-unavailable`` -- the measure needs an input this repository does not
  own and has not received. The registered-nursing-hours measures need the
  roster, which no estate service currently publishes. Reporting them as zero
  would read downstream as "no nurses on duty"; reporting them as absent is the
  only honest option.
* ``no-denominator`` -- nothing happened to measure. Distinguished from a zero
  numerator so an empty period cannot be mistaken for a perfect one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .country_packs import CountryPack

STATUS_COMPUTED = "computed"
STATUS_SOURCE_UNAVAILABLE = "source-unavailable"
STATUS_NO_DENOMINATOR = "no-denominator"

PER_1000_BED_DAYS = 1000.0


@dataclass(frozen=True)
class MeasureInputs:
    occupied_bed_days: float
    registered_nursing_hours: float | None
    total_nursing_hours: float | None
    tasks_due: int
    tasks_missed: int
    falls_with_harm: int
    hospital_acquired_pressure_injuries: int
    escalations_raised: int
    escalations_within_interval: int
    medication_outcomes: int
    medication_omissions: int


@dataclass(frozen=True)
class MeasureResult:
    measure_id: str
    title: str
    measure_type: str
    numerator: float | None
    denominator: float | None
    value: float | None
    unit: str
    status: str
    source_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "measure_id": self.measure_id,
            "title": self.title,
            "measure_type": self.measure_type,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "value": self.value,
            "unit": self.unit,
            "status": self.status,
            "source_id": self.source_id,
        }


def _ratio(numerator: float | None, denominator: float | None, factor: float) -> tuple[
    float | None, str
]:
    if numerator is None or denominator is None:
        return None, STATUS_SOURCE_UNAVAILABLE
    if denominator <= 0:
        return None, STATUS_NO_DENOMINATOR
    return round(numerator / denominator * factor, 3), STATUS_COMPUTED


def compute_measures(pack: CountryPack, inputs: MeasureInputs) -> list[MeasureResult]:
    """Apply every measure definition the pack declares, in pack order."""
    bed_days = inputs.occupied_bed_days
    pairs: dict[str, tuple[float | None, float | None, float]] = {
        "NSQ-STAFF-01": (inputs.registered_nursing_hours, bed_days, 1.0),
        "NSQ-STAFF-02": (inputs.registered_nursing_hours, inputs.total_nursing_hours, 100.0),
        "NSQ-CARE-01": (float(inputs.tasks_missed), float(inputs.tasks_due), 100.0),
        "NSQ-SAFE-01": (float(inputs.falls_with_harm), bed_days, PER_1000_BED_DAYS),
        "NSQ-SAFE-02": (
            float(inputs.hospital_acquired_pressure_injuries), bed_days, PER_1000_BED_DAYS
        ),
        "NSQ-DETER-01": (
            float(inputs.escalations_within_interval), float(inputs.escalations_raised), 100.0
        ),
        "NSQ-MED-01": (
            float(inputs.medication_omissions), float(inputs.medication_outcomes), 100.0
        ),
    }
    results: list[MeasureResult] = []
    for definition in pack.quality_measures:
        measure_id = str(definition["measure_id"])
        numerator, denominator, factor = pairs.get(measure_id, (None, None, 1.0))
        value, status = _ratio(numerator, denominator, factor)
        results.append(
            MeasureResult(
                measure_id=measure_id,
                title=str(definition["title"]),
                measure_type=str(definition["measure_type"]),
                numerator=numerator,
                denominator=denominator,
                value=value,
                unit=str(definition["unit"]),
                status=status,
                source_id=str(definition["source_id"]),
            )
        )
    return results


def dataset_payload(results: list[MeasureResult]) -> list[dict[str, Any]]:
    """De-identified measure block for the HMIS submission.

    Aggregate numerators and denominators only. No patient identifier, no name,
    no birth date, no free text and no patient-level event ever enters this
    payload (FR-NS-075).
    """
    return [result.as_dict() for result in results]


def unavailable_measures(results: list[MeasureResult]) -> list[str]:
    return [r.measure_id for r in results if r.status == STATUS_SOURCE_UNAVAILABLE]
