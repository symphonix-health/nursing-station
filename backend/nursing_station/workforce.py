"""Ward staffing position and governed shortage declaration (FR-NS-130..132).

Nursing Station does not own the roster. No estate service currently does: the
registered nursing roster, professional registration status and temporary
staffing bookings have no canonical owner and no BulletTrain connector route.
This module therefore does three separate things and keeps them separate.

1. **Consume.** :func:`validate_roster_payload` states the contract Nursing
   Station expects from a roster owner over the hub. Nothing here authors a
   roster, and an absent roster is reported as absent -- never inferred from
   who happens to be logged in.
2. **Compute.** The acuity side is genuinely repo-owned: this ward knows its
   occupied beds, its dependency levels and its warning scores.
   :func:`compute_position` turns that plus the country pack's staffing norm
   into a required-versus-actual position. When the pack carries no numeric norm
   for the jurisdiction (the United States sets ratios by state, not federally)
   the position reports ``insufficient-policy`` rather than manufacturing a
   compliance verdict from a zero.
3. **Declare.** A shortage declaration is a named human act by the nurse in
   charge. :func:`build_declaration` emits exactly the six fields BulletTrain's
   governed role-assumption model requires and nothing else -- no severity, no
   role enum, no approval field, because that model has none. The effective
   policy tier belongs to BulletTrain and is never computed here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from .country_packs import CountryPack

SHIFTS = ("day", "night")
DEFAULT_SHIFT_HOURS = 12.0
ACUITY_LEVELS = ("level-1", "level-2", "level-3", "level-4")

ROSTER_RESOURCE_TYPE = "NursingRosterContext"
ROSTER_CONNECTOR = "workforce"

ROSTER_STATE_NOT_REFRESHED = "not-refreshed"
ROSTER_STATE_CURRENT = "current"
ROSTER_STATE_STALE = "stale"

POLICY_SUFFICIENT = "sufficient"
POLICY_INSUFFICIENT = "insufficient-policy"


class RosterContractError(ValueError):
    """A roster payload did not satisfy the declared consumption contract."""


@dataclass(frozen=True)
class StaffingPosition:
    ward_id: str
    shift_date: str
    shift: str
    shift_hours: float
    jurisdiction: str
    pack_version: str
    framework_id: str
    policy_status: str
    occupied_beds: int
    acuity_distribution: dict[str, int]
    high_acuity_patients: int
    required_nursing_hours: float | None
    required_registered_hours: float | None
    required_registered_nurses: int | None
    max_patients_per_registered_nurse: int | None
    roster_state: str
    roster_source: str | None
    actual_registered_hours: float | None
    actual_total_hours: float | None
    actual_registered_headcount: int | None
    actual_skill_mix_percent: float | None
    patients_per_registered_nurse: float | None
    unregistered_practitioners: list[str] = field(default_factory=list)
    triggers_fired: list[dict[str, Any]] = field(default_factory=list)

    @property
    def shortage_indicated(self) -> bool:
        return bool(self.triggers_fired)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ward_id": self.ward_id,
            "shift_date": self.shift_date,
            "shift": self.shift,
            "shift_hours": self.shift_hours,
            "jurisdiction": self.jurisdiction,
            "pack_version": self.pack_version,
            "framework_id": self.framework_id,
            "policy_status": self.policy_status,
            "occupied_beds": self.occupied_beds,
            "acuity_distribution": dict(self.acuity_distribution),
            "high_acuity_patients": self.high_acuity_patients,
            "required_nursing_hours": self.required_nursing_hours,
            "required_registered_hours": self.required_registered_hours,
            "required_registered_nurses": self.required_registered_nurses,
            "max_patients_per_registered_nurse": self.max_patients_per_registered_nurse,
            "roster_state": self.roster_state,
            "roster_source": self.roster_source,
            "actual_registered_hours": self.actual_registered_hours,
            "actual_total_hours": self.actual_total_hours,
            "actual_registered_headcount": self.actual_registered_headcount,
            "actual_skill_mix_percent": self.actual_skill_mix_percent,
            "patients_per_registered_nurse": self.patients_per_registered_nurse,
            "unregistered_practitioners": list(self.unregistered_practitioners),
            "triggers_fired": [dict(t) for t in self.triggers_fired],
            "shortage_indicated": self.shortage_indicated,
        }


def validate_roster_payload(payload: Any, *, ward_id: str, shift_date: str, shift: str) -> dict:
    """The roster contract Nursing Station consumes over the hub.

    Rejecting a malformed roster matters more than accepting a partial one: a
    silently-empty ``assignments`` list would read downstream as "nobody on
    duty", which is a shortage the ward never had.
    """
    if not isinstance(payload, dict):
        raise RosterContractError("roster payload is not an object")
    for key in ("ward_id", "shift_date", "shift", "assignments"):
        if key not in payload:
            raise RosterContractError(f"roster payload is missing {key}")
    if payload["ward_id"] != ward_id:
        raise RosterContractError("roster payload is for a different ward")
    if payload["shift_date"] != shift_date or payload["shift"] != shift:
        raise RosterContractError("roster payload is for a different shift")
    assignments = payload["assignments"]
    if not isinstance(assignments, list) or not assignments:
        raise RosterContractError("roster payload carries no assignments")
    for entry in assignments:
        if not isinstance(entry, dict):
            raise RosterContractError("roster assignment is not an object")
        for key in ("staff_id", "role", "registered", "hours"):
            if key not in entry:
                raise RosterContractError(f"roster assignment is missing {key}")
        if not isinstance(entry["registered"], bool):
            raise RosterContractError("roster assignment 'registered' must be a boolean")
        try:
            float(entry["hours"])
        except (TypeError, ValueError) as exc:
            raise RosterContractError("roster assignment 'hours' must be numeric") from exc
    return payload


def resolve_shift(moment: datetime | None = None) -> str:
    current = moment or datetime.now(UTC)
    return "day" if 7 <= current.hour < 19 else "night"


def _norm_value(norm: dict[str, Any] | None, key: str, shift: str) -> float | None:
    if not norm:
        return None
    value = norm.get(key)
    if isinstance(value, dict):
        value = value.get(shift)
    if value in (None, 0, 0.0):
        return None
    return float(value)


def compute_position(
    pack: CountryPack,
    *,
    ward: dict[str, Any],
    patients: list[dict[str, Any]],
    escalate_threshold: int,
    roster: dict[str, Any] | None,
    roster_state: str,
    roster_source: str | None,
    shift: str,
    shift_date: str,
    shift_hours: float = DEFAULT_SHIFT_HOURS,
) -> StaffingPosition:
    staffing = pack.safe_staffing
    norm = pack.ward_norm(str(ward.get("specialty", "")))
    nhppd = _norm_value(norm, "nursing_hours_per_patient_day", shift)
    max_per_rn = _norm_value(norm, "max_patients_per_registered_nurse", shift)
    skill_mix_minimum = float(staffing.get("registered_nurse_skill_mix_minimum_percent") or 0)

    occupied = len(patients)
    distribution = {level: 0 for level in ACUITY_LEVELS}
    high_acuity = 0
    for patient in patients:
        level = str(patient.get("acuity_dependency") or "level-1")
        distribution[level] = distribution.get(level, 0) + 1
        score = patient.get("latest_score")
        if level in {"level-3", "level-4"} or (score is not None and int(score) >= escalate_threshold):
            high_acuity += 1

    required_nursing_hours = (
        round(occupied * nhppd * (shift_hours / 24.0), 2) if nhppd else None
    )
    required_registered_hours = (
        round(required_nursing_hours * skill_mix_minimum / 100.0, 2)
        if required_nursing_hours is not None and skill_mix_minimum
        else None
    )
    required_registered_nurses = (
        math.ceil(occupied / max_per_rn) if max_per_rn and occupied else None
    )
    policy_status = POLICY_SUFFICIENT if (nhppd or max_per_rn) else POLICY_INSUFFICIENT

    registered_hours = total_hours = None
    registered_headcount = None
    skill_mix_percent = None
    patients_per_rn = None
    unregistered: list[str] = []
    if roster:
        assignments = roster["assignments"]
        registered_hours = round(
            sum(float(a["hours"]) for a in assignments if a["registered"]), 2
        )
        total_hours = round(sum(float(a["hours"]) for a in assignments), 2)
        registered_headcount = sum(1 for a in assignments if a["registered"])
        skill_mix_percent = (
            round(registered_hours / total_hours * 100.0, 1) if total_hours else 0.0
        )
        patients_per_rn = (
            round(occupied / registered_headcount, 2) if registered_headcount else None
        )
        unregistered = [
            str(a["staff_id"])
            for a in assignments
            if a["registered"] and str(a.get("registration_status", "active")) != "active"
        ]

    triggers: list[dict[str, Any]] = []
    declared_triggers = {
        entry["trigger_id"]: entry
        for entry in staffing.get("declaration_policy", {}).get("triggers", [])
    }
    if "registered-hours-below-norm" in declared_triggers and None not in (
        required_registered_hours,
        registered_hours,
    ) and registered_hours < required_registered_hours:
        triggers.append({
            "trigger_id": "registered-hours-below-norm",
            "rule": declared_triggers["registered-hours-below-norm"]["rule"],
            "observed": registered_hours,
            "required": required_registered_hours,
        })
    if "skill-mix-below-minimum" in declared_triggers and skill_mix_percent is not None \
            and skill_mix_minimum and skill_mix_percent < skill_mix_minimum:
        triggers.append({
            "trigger_id": "skill-mix-below-minimum",
            "rule": declared_triggers["skill-mix-below-minimum"]["rule"],
            "observed": skill_mix_percent,
            "required": skill_mix_minimum,
        })
    ratio_trigger = declared_triggers.get("patients-per-registered-nurse-exceeded") \
        or declared_triggers.get("state-ratio-exceeded")
    if ratio_trigger and patients_per_rn is not None and max_per_rn and patients_per_rn > max_per_rn:
        triggers.append({
            "trigger_id": ratio_trigger["trigger_id"],
            "rule": ratio_trigger["rule"],
            "observed": patients_per_rn,
            "required": max_per_rn,
        })
    if unregistered:
        triggers.append({
            "trigger_id": "registration-not-active",
            "rule": "every practitioner counted as registered holds an active registration",
            "observed": unregistered,
            "required": "active",
        })

    return StaffingPosition(
        ward_id=str(ward["id"]),
        shift_date=shift_date,
        shift=shift,
        shift_hours=shift_hours,
        jurisdiction=pack.jurisdiction,
        pack_version=pack.pack_version,
        framework_id=str(staffing["framework_id"]),
        policy_status=policy_status,
        occupied_beds=occupied,
        acuity_distribution=distribution,
        high_acuity_patients=high_acuity,
        required_nursing_hours=required_nursing_hours,
        required_registered_hours=required_registered_hours,
        required_registered_nurses=required_registered_nurses,
        max_patients_per_registered_nurse=int(max_per_rn) if max_per_rn else None,
        roster_state=roster_state,
        roster_source=roster_source,
        actual_registered_hours=registered_hours,
        actual_total_hours=total_hours,
        actual_registered_headcount=registered_headcount,
        actual_skill_mix_percent=skill_mix_percent,
        patients_per_registered_nurse=patients_per_rn,
        unregistered_practitioners=unregistered,
        triggers_fired=triggers,
    )


def declaration_window(
    pack: CountryPack, starts_at: datetime, minutes: int | None = None
) -> tuple[datetime, datetime]:
    policy = pack.safe_staffing.get("declaration_policy", {}).get("declaration_contract", {})
    window = int(minutes or policy.get("default_window_minutes") or 480)
    return starts_at, starts_at + timedelta(minutes=window)


def build_declaration(
    pack: CountryPack,
    *,
    declaration_id: str,
    scope_unit: str,
    declared_by: str,
    reason: str,
    starts_at: datetime,
    expires_at: datetime,
) -> dict[str, Any]:
    """Exactly the governed declaration field set -- nothing added, nothing renamed."""
    required = tuple(
        pack.safe_staffing["declaration_policy"]["declaration_contract"]["required_fields"]
    )
    payload = {
        "declaration_id": declaration_id,
        "scope_unit": scope_unit,
        "declared_by": declared_by,
        "reason": reason,
        "starts_at": starts_at.isoformat(),
        "expires_at": expires_at.isoformat(),
    }
    missing = [name for name in required if name not in payload]
    if missing:
        raise RosterContractError(f"declaration is missing governed fields: {missing}")
    extra = [name for name in payload if name not in required]
    if extra:
        raise RosterContractError(
            f"declaration carries fields the governed model does not define: {extra}"
        )
    return payload
