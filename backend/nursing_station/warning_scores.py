"""Jurisdiction-configured aggregate early-warning scoring (FR-NS-100, FR-NS-101).

The aggregate algorithm (respiratory rate, oxygen saturation, supplemental
oxygen, systolic blood pressure, pulse, temperature, consciousness) stays in
code because it is the algorithm the pack names. What varies by jurisdiction --
and therefore lives in the country pack as versioned data -- is:

* the oxygen-saturation band table, including the Scale 2 table used when a
  prescriber has set a 88-92% target range in hypercapnic respiratory failure;
* the review / escalate / critical thresholds;
* the required response interval per escalation level;
* the minimum role that may answer an escalation at each level.

Scale 2 is not a preference. Scoring a patient on a prescribed 88-92% target
against the Scale 1 table over-scores them and manufactures escalations; scoring
them the other way round under-scores real hypoxia. The scale therefore comes
from the patient record, is only honoured when the pack marks the scale as
requiring a prescription AND the patient carries one, and falls back to Scale 1
rather than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .country_packs import CountryPack

ESCALATION_ROUTINE = "routine"
ESCALATION_REVIEW = "review"
ESCALATION_URGENT = "urgent"
ESCALATION_CRITICAL = "critical"

# Escalation level -> the pack key that carries its threshold / interval.
_LEVEL_KEYS = {
    ESCALATION_REVIEW: "review",
    ESCALATION_URGENT: "escalate",
    ESCALATION_CRITICAL: "critical",
}


class Vitals(Protocol):
    respiratory_rate: float
    oxygen_saturation: float
    supplemental_oxygen: bool
    systolic_bp: float
    pulse: float
    temperature: float
    consciousness: str


@dataclass(frozen=True)
class WarningResult:
    score: int
    escalation_level: str
    oxygen_scale: str
    profile_id: str
    pack_version: str
    jurisdiction: str
    response_minutes: int | None
    responder_minimum_role: str | None
    parameter_scores: dict[str, int]

    def as_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "escalation_level": self.escalation_level,
            "oxygen_scale": self.oxygen_scale,
            "profile_id": self.profile_id,
            "pack_version": self.pack_version,
            "jurisdiction": self.jurisdiction,
            "response_minutes": self.response_minutes,
            "responder_minimum_role": self.responder_minimum_role,
            "parameter_scores": dict(self.parameter_scores),
        }


def _band_score(bands: list[dict[str, Any]], value: float) -> int:
    """First band whose closed [min, max] window contains ``value``.

    Bands are authored ascending with open ends expressed by omitting ``min``
    or ``max``. An uncovered value is a pack defect, so the last band's score is
    NOT used as a silent default -- the caller gets a hard error instead of a
    quietly wrong clinical score.
    """
    for band in bands:
        low = band.get("min")
        high = band.get("max")
        if (low is None or value >= low) and (high is None or value <= high):
            return int(band["score"])
    raise ValueError(f"oxygen saturation {value} is not covered by the pack band table")


def _oxygen_score(pack: CountryPack, scale: str, saturation: float, on_oxygen: bool) -> int:
    scales = pack.early_warning["oxygen_scales"]
    definition = scales[scale]
    if scale == "1":
        return _band_score(definition["bands"], saturation)
    key = "bands_on_oxygen" if on_oxygen else "bands_on_air"
    return _band_score(definition[key], saturation)


def resolve_oxygen_scale(pack: CountryPack, requested: str | None) -> str:
    """Honour the patient's prescribed scale only when the pack defines it.

    ``requested`` is the scale recorded on the patient record, which is where
    the prescriber's target-range decision lives. An unknown or absent value
    falls back to Scale 1 rather than guessing at a target range.
    """
    scales = pack.early_warning["oxygen_scales"]
    if requested in scales and requested in {"1", "2"}:
        return str(requested)
    return "1"


def score_observation(
    pack: CountryPack,
    vitals: Vitals,
    *,
    oxygen_scale: str = "1",
) -> WarningResult:
    scale = resolve_oxygen_scale(pack, oxygen_scale)
    rr = vitals.respiratory_rate
    parameter_scores = {
        "respiratory_rate": 3 if rr <= 8 or rr >= 25 else 1 if rr <= 11 else 2 if rr >= 21 else 0,
        "oxygen_saturation": _oxygen_score(
            pack, scale, vitals.oxygen_saturation, bool(vitals.supplemental_oxygen)
        ),
        "supplemental_oxygen": 2 if vitals.supplemental_oxygen else 0,
        "systolic_bp": (
            3 if vitals.systolic_bp <= 90 or vitals.systolic_bp >= 220
            else 2 if vitals.systolic_bp <= 100
            else 1 if vitals.systolic_bp <= 110
            else 0
        ),
        "pulse": (
            3 if vitals.pulse <= 40 or vitals.pulse >= 131
            else 1 if vitals.pulse <= 50 or 91 <= vitals.pulse <= 110
            else 2 if 111 <= vitals.pulse <= 130
            else 0
        ),
        "temperature": (
            3 if vitals.temperature <= 35
            else 2 if vitals.temperature >= 39.1
            else 1 if vitals.temperature <= 36 or vitals.temperature >= 38.1
            else 0
        ),
        "consciousness": 0 if vitals.consciousness == "alert" else 3,
    }
    score = int(sum(parameter_scores.values()))
    level = escalation_level(pack, score)
    return WarningResult(
        score=score,
        escalation_level=level,
        oxygen_scale=scale,
        profile_id=str(pack.early_warning["profile_id"]),
        pack_version=pack.pack_version,
        jurisdiction=pack.jurisdiction,
        response_minutes=response_minutes(pack, level),
        responder_minimum_role=responder_minimum_role(pack, level),
        parameter_scores=parameter_scores,
    )


def escalation_level(pack: CountryPack, score: int) -> str:
    thresholds = pack.early_warning["thresholds"]
    if score >= int(thresholds["critical"]):
        return ESCALATION_CRITICAL
    if score >= int(thresholds["escalate"]):
        return ESCALATION_URGENT
    if score >= int(thresholds["review"]):
        return ESCALATION_REVIEW
    return ESCALATION_ROUTINE


def response_minutes(pack: CountryPack, level: str) -> int | None:
    key = _LEVEL_KEYS.get(level)
    if key is None:
        return None
    return int(pack.early_warning["response_minutes"][key])


def responder_minimum_role(pack: CountryPack, level: str) -> str | None:
    key = _LEVEL_KEYS.get(level)
    if key is None:
        return None
    return str(pack.early_warning["responder_minimum_role"][key])


def requires_escalation(pack: CountryPack, score: int) -> bool:
    return score >= int(pack.early_warning["thresholds"]["escalate"])
