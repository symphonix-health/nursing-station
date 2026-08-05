"""Risk-ranked ward work queue (FR-NS-090, FR-NS-091, FR-NS-092).

A due-time-ordered task list is not a nursing work queue. Two tasks due in the
same minute are not equally urgent when one belongs to a patient whose warning
score just crossed the escalation threshold and the other is a routine weight.

The ranking here is deterministic, explainable and repo-owned:

* every contributing factor is returned beside the rank, so a nurse (or an
  assurance agent reading the same surface) can see WHY a row is at the top;
* nothing is hidden or auto-actioned by the ranking -- it orders work, it never
  completes, reassigns or closes it;
* the weights are an operational weighting, not a national rule, and are
  declared here rather than in the country pack for exactly that reason.

Skill gating (FR-NS-091) and interruption resurfacing (FR-NS-092) are part of
the same surface: a task the viewing nurse is not competent to perform is
returned with ``delegable: false`` and the missing competency named, and a task
interrupted and not yet resumed carries an explicit uplift so suspended work
cannot quietly sink below newer work.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

PRIORITY_WEIGHT = {"stat": 60, "high": 30, "normal": 10}
ESCALATION_WEIGHT = {"critical": 50, "urgent": 30, "review": 12, "routine": 0}
RISK_WEIGHT = {"critical": 40, "high": 20, "moderate": 8, "low": 0}
OVERDUE_WEIGHT_PER_MINUTE = 0.5
OVERDUE_WEIGHT_CAP = 60.0
UNRESUMED_INTERRUPTION_WEIGHT = 25
DUE_SOON_WEIGHT = 8
DUE_SOON_MINUTES = 30

INTERRUPTION_CATEGORIES = (
    "clinical-emergency",
    "patient-request",
    "medication-round",
    "staffing-reallocation",
    "equipment-unavailable",
    "communication",
)


@dataclass(frozen=True)
class QueueEntry:
    task: dict[str, Any]
    rank_score: float
    factors: dict[str, float]
    delegable: bool
    missing_competency: str | None
    overdue_minutes: float
    unresumed_interruptions: int

    def as_dict(self) -> dict[str, Any]:
        row = dict(self.task)
        row["rank_score"] = self.rank_score
        row["rank_factors"] = dict(self.factors)
        row["delegable"] = self.delegable
        row["missing_competency"] = self.missing_competency
        row["overdue_minutes"] = self.overdue_minutes
        row["unresumed_interruptions"] = self.unresumed_interruptions
        return row


def _minutes_overdue(due_at: str, moment: datetime) -> float:
    try:
        due = datetime.fromisoformat(due_at)
    except ValueError:
        return 0.0
    if due.tzinfo is None:
        due = due.replace(tzinfo=UTC)
    return round((moment - due).total_seconds() / 60.0, 2)


def rank_tasks(
    tasks: list[dict[str, Any]],
    *,
    patient_context: dict[str, dict[str, Any]],
    interruptions: dict[str, int],
    viewer_competencies: set[str],
    moment: datetime | None = None,
) -> list[QueueEntry]:
    """Order open nursing work by clinical risk, then by how late it already is."""
    current = moment or datetime.now(UTC)
    entries: list[QueueEntry] = []
    for task in tasks:
        context = patient_context.get(str(task.get("patient_id")), {})
        overdue = _minutes_overdue(str(task.get("due_at") or ""), current)
        unresumed = int(interruptions.get(str(task.get("id")), 0))
        factors: dict[str, float] = {
            "priority": float(PRIORITY_WEIGHT.get(str(task.get("priority")), 0)),
            "escalation_level": float(
                ESCALATION_WEIGHT.get(str(context.get("escalation_level") or "routine"), 0)
            ),
            "assessment_risk": float(
                RISK_WEIGHT.get(str(context.get("highest_risk_level") or "low"), 0)
            ),
            "overdue": (
                min(overdue * OVERDUE_WEIGHT_PER_MINUTE, OVERDUE_WEIGHT_CAP)
                if overdue > 0
                else 0.0
            ),
            "due_soon": float(DUE_SOON_WEIGHT) if -DUE_SOON_MINUTES <= overdue <= 0 else 0.0,
            "interrupted": float(UNRESUMED_INTERRUPTION_WEIGHT * min(unresumed, 2)),
        }
        required = task.get("required_competency")
        missing = (
            str(required)
            if required and str(required) not in viewer_competencies
            else None
        )
        entries.append(
            QueueEntry(
                task=task,
                rank_score=round(sum(factors.values()), 2),
                factors=factors,
                delegable=missing is None,
                missing_competency=missing,
                overdue_minutes=overdue,
                unresumed_interruptions=unresumed,
            )
        )
    entries.sort(key=lambda entry: (-entry.rank_score, str(entry.task.get("due_at") or "")))
    return entries


def competency_gap(required: str | None, held: set[str]) -> str | None:
    if not required:
        return None
    return None if str(required) in held else str(required)
