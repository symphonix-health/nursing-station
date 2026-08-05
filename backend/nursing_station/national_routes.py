"""National-capability API surface (FR-NS-090..FR-NS-170).

Registered onto the application by :mod:`nursing_station.main`, which supplies
the shared authentication, scoping and persistence helpers through
:class:`RouteContext`. The context resolves ``db`` and ``settings`` through
callables rather than capturing them, because both are rebound per test.

Everything here obeys the same four rules the rest of the service does:

* No sibling is ever called directly. The only egress is the BulletTrain hub
  client, and a publication with no BulletTrain-side route stops at the durable
  queue rather than pretending to have been delivered.
* No safety decision resolves itself. Escalation responses, incident reviews,
  staffing declarations, discharge readiness and country-pack adoption all name
  the human who made the call.
* Every regulated mutation appends to the tamper-evident audit chain.
* Jurisdictional policy is read from the country pack, never hard-coded.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from . import publications, quality, work_queue, workforce
from .country_packs import CountryPack, CountryPackError, available_jurisdictions, load_pack
from .identity import CurrentUser
from .integration import HubClient, IntegrationError

HARM_LEVELS = ("none", "low", "moderate", "severe", "death")
_HARM_ORDER = {level: index for index, level in enumerate(HARM_LEVELS)}
INCIDENT_TYPES = ("fall", "pressure-injury", "healthcare-associated-infection")


def _externally_reportable(harm: dict[str, Any], body: Any) -> bool:
    """Map an incident onto the jurisdiction's own reportable-type list.

    A pressure injury is judged on its category and on whether it was present
    on admission -- an injury the patient arrived with is not this ward's
    hospital-acquired harm and must not inflate the national return. A fall or
    an infection is judged on recorded harm.
    """
    reportable_types = set(harm.get("reportable_types", []))
    if body.incident_type == "pressure-injury":
        if body.present_on_admission or not body.classification:
            return False
        key = f"pressure-injury-{str(body.classification).strip().lower().replace(' ', '-')}"
        return key in reportable_types
    key = {
        "fall": "fall-with-moderate-or-greater-harm",
        "healthcare-associated-infection": "healthcare-associated-infection-outbreak",
    }.get(body.incident_type)
    return bool(
        key in reportable_types
        and _HARM_ORDER[body.harm_level] >= _HARM_ORDER["moderate"]
    )


@dataclass(frozen=True)
class RouteContext:
    get_db: Callable[[], Any]
    get_settings: Callable[[], Any]
    current_user: Callable[..., Any]
    scoped_patient: Callable[[str, Any], dict]
    require_roles: Callable[..., None]
    new_id: Callable[[str], str]
    now: Callable[[], str]


# --------------------------------------------------------------------------
# Request models
# --------------------------------------------------------------------------
class AdoptionDecision(BaseModel):
    jurisdiction: str = Field(min_length=2, max_length=2)
    pack_version: str = Field(min_length=1, max_length=40)
    decision: Literal["adopted", "rejected"]
    scope: str = Field(min_length=3, max_length=200)
    note: str = Field(min_length=3, max_length=1000)


class InterruptionCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=300)
    reason_category: Literal[
        "clinical-emergency",
        "patient-request",
        "medication-round",
        "staffing-reallocation",
        "equipment-unavailable",
        "communication",
    ]


class EscalationResponseCreate(BaseModel):
    clinical_response: str = Field(min_length=5, max_length=1000)
    outcome: Literal["reviewed-no-change", "treatment-changed", "escalated-to-medical-team", "transferred"]


class HarmIncidentCreate(BaseModel):
    incident_type: Literal["fall", "pressure-injury", "healthcare-associated-infection"]
    occurred_at: datetime
    discovered_at: datetime
    harm_level: Literal["none", "low", "moderate", "severe", "death"]
    description: str = Field(min_length=5, max_length=2000)
    classification: str | None = Field(default=None, max_length=80)
    body_site: str | None = Field(default=None, max_length=80)
    present_on_admission: bool = False
    linked_assessment_id: str | None = None


class IncidentReviewCreate(BaseModel):
    avoidability: Literal["avoidable", "unavoidable", "not-determined"]
    contributory_factors: list[str] = Field(min_length=1, max_length=10)
    learning_actions: list[str] = Field(min_length=1, max_length=10)
    conclusion: str = Field(min_length=5, max_length=2000)


class DischargeReadinessCreate(BaseModel):
    target_date: datetime | None = None


class CriterionConfirm(BaseModel):
    note: str = Field(min_length=3, max_length=500)


class StaffingDeclarationCreate(BaseModel):
    reason: str = Field(min_length=10, max_length=500)
    window_minutes: int | None = Field(default=None, ge=15, le=1440)


class StaffingRevoke(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


# --------------------------------------------------------------------------
def build_router(ctx: RouteContext) -> APIRouter:  # noqa: C901 - route table
    router = APIRouter()
    # The dependency is declared as a DEFAULT VALUE, and it has to be.
    # This module uses `from __future__ import annotations`, so every annotation
    # is a STRING that FastAPI resolves against module globals. `ctx` is a local
    # of this factory, so `Annotated[CurrentUser, Depends(ctx.current_user)]`
    # never resolves, FastAPI falls back to treating the parameter as a query
    # field, and every route here returns 422. Two runs of
    # tests/test_national_capability.py caught exactly that. A default value is
    # evaluated eagerly at definition time and is therefore immune.
    # ruff B008 is configured to allow fastapi.Depends for this reason.

    def db() -> Any:
        return ctx.get_db()

    def settings() -> Any:
        return ctx.get_settings()

    def pack() -> CountryPack:
        try:
            return load_pack(settings().jurisdiction)
        except CountryPackError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    def adoption_for(tenant_id: str, active: CountryPack) -> dict | None:
        return db().fetchone(
            "SELECT * FROM country_pack_adoptions WHERE tenant_id=? AND jurisdiction=? "
            "AND pack_version=?",
            (tenant_id, active.jurisdiction, active.pack_version),
        )

    def scoped_ward(ward_id: str, user: Any) -> dict:
        ward = db().fetchone(
            "SELECT * FROM wards WHERE id=? AND tenant_id=?", (ward_id, user.tenant_id)
        )
        if not ward:
            raise HTTPException(status_code=404, detail="Ward not found")
        if user.ward_id and user.ward_id != ward_id:
            raise HTTPException(status_code=403, detail="Ward is outside assigned scope")
        return ward

    def competencies_of(user_id: str) -> set[str]:
        return {
            row["competency"]
            for row in db().fetchall(
                "SELECT competency FROM nurse_competencies WHERE user_id=?", (user_id,)
            )
        }

    def queue_publication(
        conn: Any,
        *,
        kind: str,
        resource_id: str,
        payload: dict,
        tenant_id: str,
        actor_id: str,
        correlation_id: str,
    ) -> str:
        """Persist an outbound publication before any transport is attempted.

        The row is written first and only moved to ``published`` by a hub
        receipt, so a crash between build and dispatch leaves a replayable
        record rather than a lost obligation.
        """
        contract = publications.contract(kind)
        missing = publications.missing_fields(kind, payload)
        if missing:
            raise HTTPException(
                status_code=500,
                detail=f"{kind} payload is missing contract fields: {missing}",
            )
        publication_id = ctx.new_id("publication")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        conn.execute(
            """INSERT INTO outbound_publications
            (id,tenant_id,kind,connector,resource_type,operation,resource_id,correlation_id,
             content_hash,payload_json,status,error_code,error_detail,receipt_json,
             hub_audit_event_id,attempts,created_by,created_at,completed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,NULL,?,NULL,NULL,0,?,?,NULL)""",
            (
                publication_id, tenant_id, kind, contract.connector, contract.resource_type,
                contract.operation, resource_id, correlation_id,
                hashlib.sha256(canonical.encode()).hexdigest(), canonical,
                publications.STATUS_PENDING,
                None if contract.deliverable else contract.gap_note,
                actor_id, ctx.now(),
            ),
        )
        return publication_id

    # ------------------------------------------------------------------
    # Country pack -- FR-NS-170 / NFR-NS-027
    # ------------------------------------------------------------------
    @router.get("/api/country-pack")
    def country_pack(user: CurrentUser = Depends(ctx.current_user)) -> dict:
        active = pack()
        adoption = adoption_for(user.tenant_id, active)
        return {
            "active": active.summary(),
            "available_jurisdictions": list(available_jurisdictions()),
            "local_adoption": adoption,
            "locally_adopted": bool(adoption and adoption["decision"] == "adopted"),
            "publication_gaps": publications.open_gaps(),
        }

    @router.post("/api/country-pack/adoptions", status_code=201)
    def record_adoption(body: AdoptionDecision, user: CurrentUser = Depends(ctx.current_user)) -> dict:
        ctx.require_roles(user, "clinical_safety_officer")
        try:
            target = load_pack(body.jurisdiction)
        except CountryPackError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if target.pack_version != body.pack_version:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{target.jurisdiction} pack on disk is version {target.pack_version}; "
                    f"an adoption decision is pinned to the exact version it reviewed"
                ),
            )
        adoption_id = ctx.new_id("adoption")
        adopted_at = ctx.now()
        with db().connect() as conn:
            existing = conn.execute(
                "SELECT id FROM country_pack_adoptions WHERE tenant_id=? AND jurisdiction=? "
                "AND pack_version=?",
                (user.tenant_id, target.jurisdiction, target.pack_version),
            ).fetchone()
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail="A decision already exists for this jurisdiction and pack version",
                )
            conn.execute(
                """INSERT INTO country_pack_adoptions
                (id,tenant_id,jurisdiction,pack_version,decision,scope,adopted_by,adopted_at,note)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (adoption_id, user.tenant_id, target.jurisdiction, target.pack_version,
                 body.decision, body.scope, user.id, adopted_at, body.note),
            )
            db().audit(
                conn, event_id=ctx.new_id("audit"), tenant_id=user.tenant_id, actor_id=user.id,
                action=f"country-pack.{body.decision}", resource_type="CountryPack",
                resource_id=f"{target.jurisdiction}:{target.pack_version}", patient_id=None,
                details={"scope": body.scope, "note": body.note},
            )
        return {"id": adoption_id, "jurisdiction": target.jurisdiction,
                "pack_version": target.pack_version, "decision": body.decision,
                "adopted_by": user.id, "adopted_at": adopted_at}

    # ------------------------------------------------------------------
    # Ward work orchestration -- FR-NS-090 / FR-NS-091 / FR-NS-092
    # ------------------------------------------------------------------
    @router.get("/api/ward-board/work-queue")
    def work_queue_view(user: CurrentUser = Depends(ctx.current_user), ward_id: str | None = Query(default=None)) -> dict:
        ctx.require_roles(user, "registered_nurse", "nurse_in_charge", "clinical_safety_officer")
        selected = ward_id or user.ward_id
        if not selected:
            raise HTTPException(status_code=422, detail="ward_id is required for cross-ward roles")
        scoped_ward(selected, user)
        active = pack()
        tasks = db().fetchall(
            """SELECT t.*,p.name AS patient_name,p.bed,assignee.name AS assigned_to_name
            FROM tasks t JOIN patients p ON p.id=t.patient_id
            LEFT JOIN users assignee ON assignee.id=t.assigned_to
            WHERE t.tenant_id=? AND t.ward_id=? AND t.status IN ('open','accepted')""",
            (user.tenant_id, selected),
        )
        context: dict[str, dict[str, Any]] = {}
        for row in db().fetchall(
            """SELECT p.id,
            (SELECT escalation_level FROM observations o WHERE o.patient_id=p.id
             ORDER BY recorded_at DESC LIMIT 1) AS escalation_level,
            (SELECT risk_level FROM safety_assessments s WHERE s.patient_id=p.id
             ORDER BY CASE s.risk_level WHEN 'critical' THEN 0 WHEN 'high' THEN 1
             WHEN 'moderate' THEN 2 ELSE 3 END LIMIT 1) AS highest_risk_level
            FROM patients p WHERE p.tenant_id=? AND p.ward_id=?""",
            (user.tenant_id, selected),
        ):
            context[row["id"]] = row
        interruptions = {
            row["task_id"]: row["open_count"]
            for row in db().fetchall(
                """SELECT task_id,COUNT(*) AS open_count FROM task_interruptions
                WHERE tenant_id=? AND ward_id=? AND resumed_at IS NULL GROUP BY task_id""",
                (user.tenant_id, selected),
            )
        }
        entries = work_queue.rank_tasks(
            tasks,
            patient_context=context,
            interruptions=interruptions,
            viewer_competencies=competencies_of(user.id),
        )
        return {
            "ward_id": selected,
            "generated_at": ctx.now(),
            "jurisdiction": active.jurisdiction,
            "ranking_weights": {
                "priority": work_queue.PRIORITY_WEIGHT,
                "escalation_level": work_queue.ESCALATION_WEIGHT,
                "assessment_risk": work_queue.RISK_WEIGHT,
                "overdue_per_minute": work_queue.OVERDUE_WEIGHT_PER_MINUTE,
                "unresumed_interruption": work_queue.UNRESUMED_INTERRUPTION_WEIGHT,
            },
            "ranking_note": (
                "Ranking orders work and explains itself. It never completes, reassigns or "
                "closes a task, and it never hides one: a task the viewer is not competent "
                "to perform is returned with delegable=false and the missing competency named."
            ),
            "entries": [entry.as_dict() for entry in entries],
        }

    @router.get("/api/wards/{ward_id}/competencies")
    def ward_competencies(ward_id: str, user: CurrentUser = Depends(ctx.current_user)) -> dict:
        ctx.require_roles(user, "registered_nurse", "nurse_in_charge", "clinical_safety_officer")
        scoped_ward(ward_id, user)
        rows = db().fetchall(
            """SELECT u.id,u.name,u.role,c.competency,c.verified_at,c.verified_by
            FROM users u LEFT JOIN nurse_competencies c ON c.user_id=u.id
            WHERE u.tenant_id=? AND u.ward_id=? AND u.active=1 ORDER BY u.name""",
            (user.tenant_id, ward_id),
        )
        nurses: dict[str, dict[str, Any]] = {}
        for row in rows:
            entry = nurses.setdefault(
                row["id"], {"id": row["id"], "name": row["name"], "role": row["role"],
                            "competencies": []}
            )
            if row["competency"]:
                entry["competencies"].append(
                    {"competency": row["competency"], "verified_at": row["verified_at"],
                     "verified_by": row["verified_by"]}
                )
        return {"ward_id": ward_id, "nurses": list(nurses.values())}

    @router.post("/api/tasks/{task_id}/interruptions", status_code=201)
    def record_interruption(task_id: str, body: InterruptionCreate, user: CurrentUser = Depends(ctx.current_user)) -> dict:
        ctx.require_roles(user, "registered_nurse", "nurse_in_charge")
        task = db().fetchone(
            "SELECT * FROM tasks WHERE id=? AND tenant_id=?", (task_id, user.tenant_id)
        )
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        if user.ward_id and task["ward_id"] != user.ward_id:
            raise HTTPException(status_code=403, detail="Task is outside assigned ward")
        if task["status"] not in {"open", "accepted"}:
            raise HTTPException(
                status_code=409, detail="Only open or accepted work can be interrupted"
            )
        interruption_id = ctx.new_id("interruption")
        interrupted_at = ctx.now()
        with db().connect() as conn:
            conn.execute(
                """INSERT INTO task_interruptions
                (id,tenant_id,ward_id,task_id,interrupted_at,reason,reason_category,
                 recorded_by,resumed_at,resumed_by)
                VALUES (?,?,?,?,?,?,?,?,NULL,NULL)""",
                (interruption_id, user.tenant_id, task["ward_id"], task_id, interrupted_at,
                 body.reason, body.reason_category, user.id),
            )
            db().audit(
                conn, event_id=ctx.new_id("audit"), tenant_id=user.tenant_id, actor_id=user.id,
                action="task.interrupted", resource_type="Task", resource_id=task_id,
                patient_id=task["patient_id"],
                details={"reason_category": body.reason_category, "reason": body.reason},
            )
        return {"id": interruption_id, "task_id": task_id, "interrupted_at": interrupted_at,
                "reason_category": body.reason_category}

    @router.post("/api/task-interruptions/{interruption_id}/resume")
    def resume_interruption(interruption_id: str, user: CurrentUser = Depends(ctx.current_user)) -> dict:
        ctx.require_roles(user, "registered_nurse", "nurse_in_charge")
        row = db().fetchone(
            "SELECT * FROM task_interruptions WHERE id=? AND tenant_id=?",
            (interruption_id, user.tenant_id),
        )
        if not row:
            raise HTTPException(status_code=404, detail="Interruption not found")
        if user.ward_id and row["ward_id"] != user.ward_id:
            raise HTTPException(status_code=403, detail="Interruption is outside assigned ward")
        if row["resumed_at"]:
            raise HTTPException(status_code=409, detail="Interruption is already resumed")
        resumed_at = ctx.now()
        with db().connect() as conn:
            conn.execute(
                "UPDATE task_interruptions SET resumed_at=?,resumed_by=? WHERE id=?",
                (resumed_at, user.id, interruption_id),
            )
            db().audit(
                conn, event_id=ctx.new_id("audit"), tenant_id=user.tenant_id, actor_id=user.id,
                action="task.resumed", resource_type="Task", resource_id=row["task_id"],
                patient_id=None, details={"interruption_id": interruption_id},
            )
        return {"id": interruption_id, "task_id": row["task_id"], "resumed_at": resumed_at}

    # ------------------------------------------------------------------
    # Deterioration response -- FR-NS-100 / FR-NS-101
    # ------------------------------------------------------------------
    @router.get("/api/wards/{ward_id}/escalations")
    def escalations(ward_id: str, user: CurrentUser = Depends(ctx.current_user)) -> dict:
        ctx.require_roles(user, "registered_nurse", "nurse_in_charge", "clinical_safety_officer")
        scoped_ward(ward_id, user)
        active = pack()
        threshold = int(active.early_warning["thresholds"]["escalate"])
        rows = db().fetchall(
            """SELECT o.id,o.patient_id,o.recorded_at,o.score,o.escalation_level,
            o.oxygen_scale,o.response_due_at,o.warning_profile_version,o.jurisdiction,
            p.name AS patient_name,p.bed,
            r.id AS response_id,r.responded_at,r.responder_id,r.within_required_interval
            FROM observations o
            JOIN patients p ON p.id=o.patient_id
            LEFT JOIN escalation_responses r ON r.observation_id=o.id
            WHERE o.tenant_id=? AND o.ward_id=? AND o.score>=?
            ORDER BY o.recorded_at DESC LIMIT 100""",
            (user.tenant_id, ward_id, threshold),
        )
        current = datetime.now(UTC)
        for row in rows:
            row["answered"] = row["response_id"] is not None
            due = row["response_due_at"]
            row["overdue"] = bool(
                not row["answered"] and due and datetime.fromisoformat(due) < current
            )
        return {
            "ward_id": ward_id,
            "profile_id": active.early_warning["profile_id"],
            "jurisdiction": active.jurisdiction,
            "pack_version": active.pack_version,
            "response_minutes": active.early_warning["response_minutes"],
            "responder_minimum_role": active.early_warning["responder_minimum_role"],
            "escalations": rows,
        }

    @router.post("/api/observations/{observation_id}/escalation-response", status_code=201)
    def record_escalation_response(
        observation_id: str, body: EscalationResponseCreate, user: CurrentUser = Depends(ctx.current_user)
    ) -> dict:
        ctx.require_roles(user, "registered_nurse", "nurse_in_charge")
        observation = db().fetchone(
            "SELECT * FROM observations WHERE id=? AND tenant_id=?",
            (observation_id, user.tenant_id),
        )
        if not observation:
            raise HTTPException(status_code=404, detail="Observation not found")
        ctx.scoped_patient(observation["patient_id"], user)
        active = pack()
        threshold = int(active.early_warning["thresholds"]["escalate"])
        if observation["score"] < threshold:
            raise HTTPException(
                status_code=409,
                detail="This observation did not reach the configured escalation threshold",
            )
        level = observation["escalation_level"]
        minimum_role = active.early_warning["responder_minimum_role"].get(
            {"critical": "critical", "urgent": "escalate", "review": "review"}.get(level, "review")
        )
        if minimum_role == "nurse_in_charge" and user.role != "nurse_in_charge":
            raise HTTPException(
                status_code=403,
                detail=(
                    f"A {level} escalation requires a {minimum_role} response under the "
                    f"{active.jurisdiction} profile"
                ),
            )
        existing = db().fetchone(
            "SELECT * FROM escalation_responses WHERE observation_id=?", (observation_id,)
        )
        if existing:
            raise HTTPException(
                status_code=409, detail="This escalation already has a recorded response"
            )
        responded_at = datetime.now(UTC)
        required_by = observation["response_due_at"] or (
            datetime.fromisoformat(observation["recorded_at"])
            + timedelta(minutes=int(active.early_warning["response_minutes"]["escalate"]))
        ).isoformat()
        within = responded_at <= datetime.fromisoformat(required_by)
        response_id = ctx.new_id("escalation-response")
        task = db().fetchone(
            "SELECT id FROM tasks WHERE origin_kind='observation' AND origin_id=?",
            (observation_id,),
        )
        with db().connect() as conn:
            conn.execute(
                """INSERT INTO escalation_responses
                (id,tenant_id,ward_id,patient_id,observation_id,task_id,escalation_level,
                 warning_score,profile_id,pack_version,responder_id,responder_role,responded_at,
                 required_by,within_required_interval,clinical_response,outcome)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (response_id, user.tenant_id, observation["ward_id"], observation["patient_id"],
                 observation_id, task["id"] if task else None, level, observation["score"],
                 str(active.early_warning["profile_id"]), active.pack_version, user.id, user.role,
                 responded_at.isoformat(), required_by, int(within), body.clinical_response,
                 body.outcome),
            )
            db().audit(
                conn, event_id=ctx.new_id("audit"), tenant_id=user.tenant_id, actor_id=user.id,
                action="escalation.answered", resource_type="Observation",
                resource_id=observation_id, patient_id=observation["patient_id"],
                details={"outcome": body.outcome, "within_required_interval": within,
                         "escalation_level": level, "responder_role": user.role},
            )
        return {
            "id": response_id, "observation_id": observation_id, "escalation_level": level,
            "responded_at": responded_at.isoformat(), "required_by": required_by,
            "within_required_interval": within, "responder_id": user.id,
            "responder_role": user.role, "outcome": body.outcome,
            "escalation_task_id": task["id"] if task else None,
            "note": "Recording a response never completes the escalation task; that remains a "
                    "separate, explicit nursing action.",
        }

    # ------------------------------------------------------------------
    # Harm incidents -- FR-NS-140 / FR-NS-141
    # ------------------------------------------------------------------
    @router.post("/api/patients/{patient_id}/harm-incidents", status_code=201)
    def report_harm_incident(
        patient_id: str, body: HarmIncidentCreate, user: CurrentUser = Depends(ctx.current_user)
    ) -> dict:
        ctx.require_roles(user, "registered_nurse", "nurse_in_charge")
        patient = ctx.scoped_patient(patient_id, user)
        active = pack()
        if body.discovered_at < body.occurred_at:
            raise HTTPException(
                status_code=422, detail="An incident cannot be discovered before it occurred"
            )
        harm = active.harm_incident
        reportable = _externally_reportable(harm, body)
        review_required = (
            _HARM_ORDER[body.harm_level]
            >= _HARM_ORDER[str(harm.get("review_required_from_harm_level", "moderate"))]
        )
        incident_id = ctx.new_id("incident")
        reported_at = ctx.now()
        publication_id = None
        with db().connect() as conn:
            if reportable:
                publication_id = queue_publication(
                    conn,
                    kind=publications.KIND_HARM_INCIDENT,
                    resource_id=incident_id,
                    payload={
                        "tenant_id": user.tenant_id,
                        "facility_id": patient["facility_id"],
                        "ward_id": patient["ward_id"],
                        "incident_type": body.incident_type,
                        "harm_level": body.harm_level,
                        "occurred_at": body.occurred_at.isoformat(),
                        "classification": body.classification,
                        "present_on_admission": body.present_on_admission,
                        "correlation_id": f"ns-incident-{incident_id}",
                    },
                    tenant_id=user.tenant_id,
                    actor_id=user.id,
                    correlation_id=f"ns-incident-{incident_id}",
                )
            conn.execute(
                """INSERT INTO harm_incidents
                (id,tenant_id,ward_id,patient_id,incident_type,occurred_at,discovered_at,
                 reported_by,reported_at,classification,body_site,present_on_admission,
                 harm_level,description,linked_assessment_id,externally_reportable,
                 review_required,status,jurisdiction,pack_version,publication_id,version)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                (incident_id, user.tenant_id, patient["ward_id"], patient_id, body.incident_type,
                 body.occurred_at.isoformat(), body.discovered_at.isoformat(), user.id,
                 reported_at, body.classification, body.body_site,
                 int(body.present_on_admission), body.harm_level, body.description,
                 body.linked_assessment_id, int(reportable), int(review_required),
                 "awaiting-review" if review_required else "open", active.jurisdiction,
                 active.pack_version, publication_id),
            )
            db().audit(
                conn, event_id=ctx.new_id("audit"), tenant_id=user.tenant_id, actor_id=user.id,
                action="harm-incident.reported", resource_type="AdverseEvent",
                resource_id=incident_id, patient_id=patient_id,
                details={"incident_type": body.incident_type, "harm_level": body.harm_level,
                         "externally_reportable": reportable, "review_required": review_required,
                         "publication_id": publication_id},
            )
        return {
            "id": incident_id,
            "status": "awaiting-review" if review_required else "open",
            "externally_reportable": reportable,
            "review_required": review_required,
            "publication_id": publication_id,
            "external_report_state": (
                publications.STATUS_PENDING if publication_id else "not-required"
            ),
            "external_report_note": (
                publications.contract(publications.KIND_HARM_INCIDENT).gap_note
                if publication_id else None
            ),
        }

    @router.get("/api/wards/{ward_id}/harm-incidents")
    def list_harm_incidents(ward_id: str, user: CurrentUser = Depends(ctx.current_user)) -> dict:
        ctx.require_roles(user, "registered_nurse", "nurse_in_charge", "clinical_safety_officer")
        scoped_ward(ward_id, user)
        rows = db().fetchall(
            """SELECT i.*,p.name AS patient_name,p.bed,u.name AS reported_by_name,
            r.id AS review_id,r.avoidability,r.reviewed_at,r.reviewed_by
            FROM harm_incidents i JOIN patients p ON p.id=i.patient_id
            JOIN users u ON u.id=i.reported_by
            LEFT JOIN incident_reviews r ON r.incident_id=i.id
            WHERE i.tenant_id=? AND i.ward_id=? ORDER BY i.occurred_at DESC""",
            (user.tenant_id, ward_id),
        )
        return {"ward_id": ward_id, "incidents": rows}

    @router.post("/api/harm-incidents/{incident_id}/review", status_code=201)
    def review_harm_incident(
        incident_id: str, body: IncidentReviewCreate, user: CurrentUser = Depends(ctx.current_user)
    ) -> dict:
        ctx.require_roles(user, "nurse_in_charge", "clinical_safety_officer")
        incident = db().fetchone(
            "SELECT * FROM harm_incidents WHERE id=? AND tenant_id=?",
            (incident_id, user.tenant_id),
        )
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        if user.ward_id and incident["ward_id"] != user.ward_id:
            raise HTTPException(status_code=403, detail="Incident is outside assigned ward")
        if incident["reported_by"] == user.id:
            raise HTTPException(
                status_code=422,
                detail="An incident review must be carried out by someone other than the reporter",
            )
        if db().fetchone(
            "SELECT id FROM incident_reviews WHERE incident_id=?", (incident_id,)
        ):
            raise HTTPException(status_code=409, detail="Incident is already reviewed")
        review_id = ctx.new_id("review")
        reviewed_at = ctx.now()
        created_tasks: list[str] = []
        with db().connect() as conn:
            for action in body.learning_actions:
                task_id = ctx.new_id("task")
                created_tasks.append(task_id)
                conn.execute(
                    """INSERT INTO tasks
                    (id,tenant_id,ward_id,patient_id,title,description,priority,status,due_at,
                     assigned_to,created_by,created_at,completed_by,completed_at,completion_note,
                     version,required_competency,origin_kind,origin_id)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,NULL,NULL,NULL,1,NULL,'incident-review',?)""",
                    (task_id, user.tenant_id, incident["ward_id"], incident["patient_id"], action,
                     f"Learning action from {incident['incident_type']} review {review_id}",
                     "high", "open",
                     (datetime.now(UTC) + timedelta(days=1)).isoformat(), None, user.id,
                     reviewed_at, incident_id),
                )
            conn.execute(
                """INSERT INTO incident_reviews
                (id,tenant_id,incident_id,reviewed_by,reviewed_at,avoidability,
                 contributory_factors_json,learning_actions_json,conclusion,
                 generated_task_ids_json)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (review_id, user.tenant_id, incident_id, user.id, reviewed_at, body.avoidability,
                 json.dumps(body.contributory_factors), json.dumps(body.learning_actions),
                 body.conclusion, json.dumps(created_tasks)),
            )
            conn.execute(
                "UPDATE harm_incidents SET status='reviewed',version=version+1 WHERE id=?",
                (incident_id,),
            )
            db().audit(
                conn, event_id=ctx.new_id("audit"), tenant_id=user.tenant_id, actor_id=user.id,
                action="harm-incident.reviewed", resource_type="AdverseEvent",
                resource_id=incident_id, patient_id=incident["patient_id"],
                details={"avoidability": body.avoidability, "learning_task_ids": created_tasks},
            )
        return {"id": review_id, "incident_id": incident_id, "reviewed_by": user.id,
                "reviewed_at": reviewed_at, "avoidability": body.avoidability,
                "generated_task_ids": created_tasks}

    # ------------------------------------------------------------------
    # Discharge readiness -- FR-NS-150 / FR-NS-151
    # ------------------------------------------------------------------
    @router.post("/api/patients/{patient_id}/discharge-readiness", status_code=201)
    def open_discharge_readiness(
        patient_id: str, body: DischargeReadinessCreate, user: CurrentUser = Depends(ctx.current_user)
    ) -> dict:
        ctx.require_roles(user, "registered_nurse", "nurse_in_charge")
        patient = ctx.scoped_patient(patient_id, user)
        active = pack()
        if db().fetchone(
            "SELECT id FROM discharge_readiness WHERE patient_id=? AND status='in-progress'",
            (patient_id,),
        ):
            raise HTTPException(
                status_code=409, detail="This patient already has an open discharge readiness record"
            )
        readiness_id = ctx.new_id("discharge")
        created_at = ctx.now()
        criteria = active.discharge_criteria
        with db().connect() as conn:
            conn.execute(
                """INSERT INTO discharge_readiness
                (id,tenant_id,ward_id,patient_id,status,jurisdiction,pack_version,target_date,
                 created_by,created_at,updated_at,completed_by,completed_at,version)
                VALUES (?,?,?,?,'in-progress',?,?,?,?,?,?,NULL,NULL,1)""",
                (readiness_id, user.tenant_id, patient["ward_id"], patient_id,
                 active.jurisdiction, active.pack_version,
                 body.target_date.isoformat() if body.target_date else None,
                 user.id, created_at, created_at),
            )
            for criterion in criteria:
                conn.execute(
                    """INSERT INTO discharge_criteria
                    (id,readiness_id,criterion_id,title,owner_role,evidence_source,mandatory,
                     status,evidence_reference,evidence_hash,correlation_id,confirmed_by,
                     confirmed_at,note)
                    VALUES (?,?,?,?,?,?,?,'pending',NULL,NULL,NULL,NULL,NULL,NULL)""",
                    (ctx.new_id("criterion"), readiness_id, criterion["criterion_id"],
                     criterion["title"], criterion["owner_role"], criterion["evidence_source"],
                     int(bool(criterion.get("mandatory")))),
                )
            db().audit(
                conn, event_id=ctx.new_id("audit"), tenant_id=user.tenant_id, actor_id=user.id,
                action="discharge-readiness.opened", resource_type="CarePlan",
                resource_id=readiness_id, patient_id=patient_id,
                details={"jurisdiction": active.jurisdiction, "pack_version": active.pack_version,
                         "criterion_count": len(criteria)},
            )
        return {"id": readiness_id, "status": "in-progress", "criteria": len(criteria),
                "jurisdiction": active.jurisdiction, "pack_version": active.pack_version}

    def _readiness_view(readiness: dict) -> dict:
        criteria = db().fetchall(
            "SELECT * FROM discharge_criteria WHERE readiness_id=? ORDER BY mandatory DESC,"
            " criterion_id",
            (readiness["id"],),
        )
        outstanding = [
            row["criterion_id"] for row in criteria
            if row["mandatory"] and row["status"] != "met"
        ]
        return {
            **readiness,
            "criteria": criteria,
            "outstanding_mandatory": outstanding,
            "ready_for_discharge": not outstanding,
        }

    @router.get("/api/patients/{patient_id}/discharge-readiness")
    def get_discharge_readiness(patient_id: str, user: CurrentUser = Depends(ctx.current_user)) -> dict:
        ctx.scoped_patient(patient_id, user)
        readiness = db().fetchone(
            "SELECT * FROM discharge_readiness WHERE patient_id=? AND tenant_id=?"
            " ORDER BY created_at DESC LIMIT 1",
            (patient_id, user.tenant_id),
        )
        if not readiness:
            raise HTTPException(status_code=404, detail="No discharge readiness record")
        return _readiness_view(readiness)

    @router.post("/api/discharge-readiness/{readiness_id}/criteria/{criterion_id}/confirm")
    def confirm_criterion(
        readiness_id: str, criterion_id: str, body: CriterionConfirm, user: CurrentUser = Depends(ctx.current_user)
    ) -> dict:
        ctx.require_roles(user, "registered_nurse", "nurse_in_charge")
        readiness = db().fetchone(
            "SELECT * FROM discharge_readiness WHERE id=? AND tenant_id=?",
            (readiness_id, user.tenant_id),
        )
        if not readiness:
            raise HTTPException(status_code=404, detail="Discharge readiness record not found")
        ctx.scoped_patient(readiness["patient_id"], user)
        criterion = db().fetchone(
            "SELECT * FROM discharge_criteria WHERE readiness_id=? AND criterion_id=?",
            (readiness_id, criterion_id),
        )
        if not criterion:
            raise HTTPException(status_code=404, detail="Criterion not found")
        if criterion["evidence_source"] != "nursing-station":
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{criterion_id} is owned by {criterion['evidence_source']}; it can only be "
                    "met by a receipt from that source through the hub, never by local assertion"
                ),
            )
        if criterion["status"] == "met":
            raise HTTPException(status_code=409, detail="Criterion is already met")
        confirmed_at = ctx.now()
        with db().connect() as conn:
            conn.execute(
                """UPDATE discharge_criteria SET status='met',confirmed_by=?,confirmed_at=?,
                note=?,evidence_reference='nursing-station-direct-confirmation' WHERE id=?""",
                (user.id, confirmed_at, body.note, criterion["id"]),
            )
            conn.execute(
                "UPDATE discharge_readiness SET updated_at=?,version=version+1 WHERE id=?",
                (confirmed_at, readiness_id),
            )
            db().audit(
                conn, event_id=ctx.new_id("audit"), tenant_id=user.tenant_id, actor_id=user.id,
                action="discharge-criterion.confirmed", resource_type="CarePlan",
                resource_id=f"{readiness_id}:{criterion_id}",
                patient_id=readiness["patient_id"], details={"note": body.note},
            )
        return _readiness_view(
            db().fetchone("SELECT * FROM discharge_readiness WHERE id=?", (readiness_id,))
        )

    @router.post("/api/discharge-readiness/{readiness_id}/coordinate")
    async def coordinate_discharge(readiness_id: str, user: CurrentUser = Depends(ctx.current_user)) -> dict:
        """Ask each owning sibling, through the hub, to confirm its criterion.

        A criterion becomes ``met`` only when the source's own response carries
        the evidence. A dispatch, a 2xx with nothing in it, or a missing hub
        route all leave the criterion ``pending`` with a typed reason.
        """
        ctx.require_roles(user, "registered_nurse", "nurse_in_charge")
        readiness = db().fetchone(
            "SELECT * FROM discharge_readiness WHERE id=? AND tenant_id=?",
            (readiness_id, user.tenant_id),
        )
        if not readiness:
            raise HTTPException(status_code=404, detail="Discharge readiness record not found")
        patient = ctx.scoped_patient(readiness["patient_id"], user)
        try:
            hub = HubClient(settings())
        except IntegrationError as exc:
            raise HTTPException(
                status_code=503, detail={"code": exc.code, "message": exc.detail}
            ) from exc
        results: list[dict[str, Any]] = []
        for criterion in db().fetchall(
            "SELECT * FROM discharge_criteria WHERE readiness_id=? AND status<>'met'",
            (readiness_id,),
        ):
            source = criterion["evidence_source"]
            if source == "nursing-station":
                continue
            contract = DISCHARGE_CONFIRMATIONS.get(source)
            correlation_id = ctx.new_id(f"ns-discharge-{source}")
            if contract is None:
                results.append({
                    "criterion_id": criterion["criterion_id"], "status": "pending",
                    "error_code": "hub_route_unregistered",
                    "message": f"No BulletTrain exchange route confirms {source} discharge readiness",
                    "correlation_id": correlation_id,
                })
                continue
            if not patient["source_patient_id"] and not patient["external_nhs_number"]:
                results.append({
                    "criterion_id": criterion["criterion_id"], "status": "pending",
                    "error_code": "identity_link_missing",
                    "message": "Patient has no governed cross-system identity link",
                    "correlation_id": correlation_id,
                })
                continue
            try:
                exchanged = await hub.exchange(
                    connector=contract["connector"], resource_type=contract["resource_type"],
                    operation="read", payload={"patient_id": patient["source_patient_id"]},
                    tenant_id=user.tenant_id, actor_id=user.id, role=user.role,
                    correlation_id=correlation_id,
                )
            except IntegrationError as exc:
                results.append({
                    "criterion_id": criterion["criterion_id"], "status": "pending",
                    "error_code": exc.code, "message": exc.detail,
                    "correlation_id": correlation_id,
                })
                continue
            evidence = contract["evidence"](exchanged["body"])
            if not evidence:
                results.append({
                    "criterion_id": criterion["criterion_id"], "status": "pending",
                    "error_code": "evidence_absent",
                    "message": f"{source} responded without the evidence this criterion requires",
                    "correlation_id": correlation_id,
                })
                continue
            confirmed_at = ctx.now()
            with db().connect() as conn:
                conn.execute(
                    """UPDATE discharge_criteria SET status='met',evidence_reference=?,
                    evidence_hash=?,correlation_id=?,confirmed_at=?,confirmed_by=? WHERE id=?""",
                    (evidence, hashlib.sha256(evidence.encode()).hexdigest(), correlation_id,
                     confirmed_at, user.id, criterion["id"]),
                )
                db().audit(
                    conn, event_id=ctx.new_id("audit"), tenant_id=user.tenant_id, actor_id=user.id,
                    action="discharge-criterion.received", resource_type="CarePlan",
                    resource_id=f"{readiness_id}:{criterion['criterion_id']}",
                    patient_id=readiness["patient_id"],
                    details={"source_system": source, "correlation_id": correlation_id,
                             "evidence_reference": evidence},
                )
            results.append({
                "criterion_id": criterion["criterion_id"], "status": "met",
                "evidence_reference": evidence, "correlation_id": correlation_id,
            })
        with db().connect() as conn:
            conn.execute(
                "UPDATE discharge_readiness SET updated_at=?,version=version+1 WHERE id=?",
                (ctx.now(), readiness_id),
            )
        return {
            "readiness": _readiness_view(
                db().fetchone("SELECT * FROM discharge_readiness WHERE id=?", (readiness_id,))
            ),
            "results": results,
        }

    @router.post("/api/discharge-readiness/{readiness_id}/complete")
    def complete_discharge_readiness(readiness_id: str, user: CurrentUser = Depends(ctx.current_user)) -> dict:
        ctx.require_roles(user, "registered_nurse", "nurse_in_charge")
        readiness = db().fetchone(
            "SELECT * FROM discharge_readiness WHERE id=? AND tenant_id=?",
            (readiness_id, user.tenant_id),
        )
        if not readiness:
            raise HTTPException(status_code=404, detail="Discharge readiness record not found")
        ctx.scoped_patient(readiness["patient_id"], user)
        if readiness["status"] != "in-progress":
            raise HTTPException(status_code=409, detail="Discharge readiness is not in progress")
        view = _readiness_view(readiness)
        if view["outstanding_mandatory"]:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "mandatory_criteria_outstanding",
                    "outstanding": view["outstanding_mandatory"],
                },
            )
        completed_at = ctx.now()
        with db().connect() as conn:
            conn.execute(
                """UPDATE discharge_readiness SET status='ready',completed_by=?,completed_at=?,
                updated_at=?,version=version+1 WHERE id=? AND status='in-progress'""",
                (user.id, completed_at, completed_at, readiness_id),
            )
            db().audit(
                conn, event_id=ctx.new_id("audit"), tenant_id=user.tenant_id, actor_id=user.id,
                action="discharge-readiness.completed", resource_type="CarePlan",
                resource_id=readiness_id, patient_id=readiness["patient_id"],
                details={"completed_by": user.id},
            )
        return _readiness_view(
            db().fetchone("SELECT * FROM discharge_readiness WHERE id=?", (readiness_id,))
        )

    # ------------------------------------------------------------------
    # Safe staffing -- FR-NS-130 / FR-NS-131 / FR-NS-132
    # ------------------------------------------------------------------
    def _current_position(ward: dict, user: Any, active: CountryPack) -> workforce.StaffingPosition:
        shift = workforce.resolve_shift()
        shift_date = datetime.now(UTC).date().isoformat()
        snapshot = db().fetchone(
            "SELECT * FROM staffing_snapshots WHERE tenant_id=? AND ward_id=? AND shift_date=?"
            " AND shift=?",
            (user.tenant_id, ward["id"], shift_date, shift),
        )
        roster = json.loads(snapshot["data_json"]) if snapshot else None
        patients = db().fetchall(
            """SELECT p.id,p.acuity_dependency,
            (SELECT score FROM observations o WHERE o.patient_id=p.id
             ORDER BY recorded_at DESC LIMIT 1) AS latest_score
            FROM patients p WHERE p.tenant_id=? AND p.ward_id=?""",
            (user.tenant_id, ward["id"]),
        )
        return workforce.compute_position(
            active,
            ward=ward,
            patients=patients,
            escalate_threshold=int(active.early_warning["thresholds"]["escalate"]),
            roster=roster,
            roster_state=(
                snapshot["status"] if snapshot else workforce.ROSTER_STATE_NOT_REFRESHED
            ),
            roster_source=snapshot["source_system"] if snapshot else None,
            shift=shift,
            shift_date=shift_date,
        )

    @router.get("/api/wards/{ward_id}/staffing-position")
    def staffing_position(ward_id: str, user: CurrentUser = Depends(ctx.current_user)) -> dict:
        ctx.require_roles(user, "registered_nurse", "nurse_in_charge", "clinical_safety_officer")
        ward = scoped_ward(ward_id, user)
        active = pack()
        position = _current_position(ward, user, active)
        return {
            "position": position.as_dict(),
            "roster_contract": {
                "connector": workforce.ROSTER_CONNECTOR,
                "resource_type": workforce.ROSTER_RESOURCE_TYPE,
                "owner": "unassigned",
                "note": (
                    "No estate service currently publishes a nursing roster and no BulletTrain "
                    "exchange route exists for one. Nursing Station consumes a roster when one "
                    "is published and never authors it."
                ),
            },
            "declaration_policy": active.safe_staffing.get("declaration_policy", {}),
        }

    @router.post("/api/wards/{ward_id}/staffing-roster/refresh")
    async def refresh_staffing_roster(ward_id: str, user: CurrentUser = Depends(ctx.current_user)) -> dict:
        ctx.require_roles(user, "nurse_in_charge", "clinical_safety_officer")
        ward = scoped_ward(ward_id, user)
        try:
            hub = HubClient(settings())
        except IntegrationError as exc:
            raise HTTPException(
                status_code=503, detail={"code": exc.code, "message": exc.detail}
            ) from exc
        shift = workforce.resolve_shift()
        shift_date = datetime.now(UTC).date().isoformat()
        correlation_id = ctx.new_id("ns-roster")
        try:
            exchanged = await hub.exchange(
                connector=workforce.ROSTER_CONNECTOR,
                resource_type=workforce.ROSTER_RESOURCE_TYPE, operation="read",
                payload={"ward_id": ward_id, "shift_date": shift_date, "shift": shift},
                tenant_id=user.tenant_id, actor_id=user.id, role=user.role,
                correlation_id=correlation_id, purpose_of_use="operations",
            )
        except IntegrationError as exc:
            with db().connect() as conn:
                db().audit(
                    conn, event_id=ctx.new_id("audit"), tenant_id=user.tenant_id, actor_id=user.id,
                    action="staffing.roster.failed", resource_type="PractitionerRole",
                    resource_id=ward_id, patient_id=None,
                    details={"error_code": exc.code, "correlation_id": correlation_id},
                )
            raise HTTPException(
                status_code=502, detail={"code": exc.code, "message": exc.detail}
            ) from exc
        try:
            roster = workforce.validate_roster_payload(
                exchanged["body"], ward_id=ward_id, shift_date=shift_date, shift=shift
            )
        except workforce.RosterContractError as exc:
            raise HTTPException(
                status_code=502, detail={"code": "invalid_roster", "message": str(exc)}
            ) from exc
        canonical = json.dumps(roster, sort_keys=True, separators=(",", ":"), default=str)
        content_hash = hashlib.sha256(canonical.encode()).hexdigest()
        fetched_at = ctx.now()
        with db().connect() as conn:
            conn.execute(
                """INSERT INTO staffing_snapshots
                (id,tenant_id,ward_id,shift_date,shift,source_system,content_hash,correlation_id,
                 fetched_at,source_updated_at,status,data_json,version)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)
                ON CONFLICT(tenant_id,ward_id,shift_date,shift) DO UPDATE SET
                 content_hash=excluded.content_hash,correlation_id=excluded.correlation_id,
                 fetched_at=excluded.fetched_at,status=excluded.status,
                 data_json=excluded.data_json,version=staffing_snapshots.version+1""",
                (ctx.new_id("roster"), user.tenant_id, ward_id, shift_date, shift,
                 workforce.ROSTER_CONNECTOR, content_hash, correlation_id, fetched_at,
                 roster.get("source_updated_at"), workforce.ROSTER_STATE_CURRENT, canonical),
            )
            db().audit(
                conn, event_id=ctx.new_id("audit"), tenant_id=user.tenant_id, actor_id=user.id,
                action="staffing.roster.refreshed", resource_type="PractitionerRole",
                resource_id=ward_id, patient_id=None,
                details={"correlation_id": correlation_id, "content_hash": content_hash,
                         "shift": shift, "shift_date": shift_date, "purpose_of_use": "operations"},
            )
        active = pack()
        return {"ward_id": ward_id, "shift": shift, "shift_date": shift_date,
                "correlation_id": correlation_id,
                "position": _current_position(ward, user, active).as_dict()}

    @router.post("/api/wards/{ward_id}/staffing-declarations", status_code=201)
    def declare_staffing_shortage(
        ward_id: str, body: StaffingDeclarationCreate, user: CurrentUser = Depends(ctx.current_user)
    ) -> dict:
        ctx.require_roles(user, "nurse_in_charge")
        ward = scoped_ward(ward_id, user)
        active = pack()
        position = _current_position(ward, user, active)
        starts_at, expires_at = workforce.declaration_window(
            active, datetime.now(UTC), body.window_minutes
        )
        declaration_id = ctx.new_id("ns-staffing")
        governed = workforce.build_declaration(
            active, declaration_id=declaration_id, scope_unit=ward_id, declared_by=user.id,
            reason=body.reason, starts_at=starts_at, expires_at=expires_at,
        )
        record_id = ctx.new_id("declaration")
        with db().connect() as conn:
            publication_id = queue_publication(
                conn, kind=publications.KIND_STAFFING_DECLARATION, resource_id=record_id,
                payload=governed, tenant_id=user.tenant_id, actor_id=user.id,
                correlation_id=declaration_id,
            )
            conn.execute(
                """INSERT INTO staffing_declarations
                (id,tenant_id,ward_id,declaration_id,scope_unit,declared_by,reason,starts_at,
                 expires_at,revoked,revoked_by,revoked_at,jurisdiction,pack_version,triggers_json,
                 position_json,publication_id,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,0,NULL,NULL,?,?,?,?,?,?)""",
                (record_id, user.tenant_id, ward_id, declaration_id, ward_id, user.id,
                 body.reason, governed["starts_at"], governed["expires_at"],
                 active.jurisdiction, active.pack_version,
                 json.dumps(position.triggers_fired), json.dumps(position.as_dict()),
                 publication_id, ctx.now()),
            )
            db().audit(
                conn, event_id=ctx.new_id("audit"), tenant_id=user.tenant_id, actor_id=user.id,
                action="staffing.shortage.declared", resource_type="PractitionerRole",
                resource_id=declaration_id, patient_id=None,
                details={"scope_unit": ward_id, "reason": body.reason,
                         "triggers_fired": [t["trigger_id"] for t in position.triggers_fired],
                         "publication_id": publication_id},
            )
        return {
            "id": record_id,
            "governed_declaration": governed,
            "triggers_fired": position.triggers_fired,
            "position": position.as_dict(),
            "publication_id": publication_id,
            "publication_status": publications.STATUS_PENDING,
            "publication_note": publications.contract(
                publications.KIND_STAFFING_DECLARATION
            ).gap_note,
            "effective_tier": None,
            "effective_tier_note": (
                "The effective policy tier is decided by BulletTrain's governed role assumption "
                "from this declaration; Nursing Station never computes or asserts one."
            ),
        }

    @router.post("/api/staffing-declarations/{declaration_id}/revoke")
    def revoke_staffing_declaration(
        declaration_id: str, body: StaffingRevoke, user: CurrentUser = Depends(ctx.current_user)
    ) -> dict:
        ctx.require_roles(user, "nurse_in_charge")
        record = db().fetchone(
            "SELECT * FROM staffing_declarations WHERE declaration_id=? AND tenant_id=?",
            (declaration_id, user.tenant_id),
        )
        if not record:
            raise HTTPException(status_code=404, detail="Declaration not found")
        if user.ward_id and record["ward_id"] != user.ward_id:
            raise HTTPException(status_code=403, detail="Declaration is outside assigned ward")
        if record["revoked"]:
            raise HTTPException(status_code=409, detail="Declaration is already revoked")
        revoked_at = ctx.now()
        with db().connect() as conn:
            conn.execute(
                "UPDATE staffing_declarations SET revoked=1,revoked_by=?,revoked_at=? WHERE id=?",
                (user.id, revoked_at, record["id"]),
            )
            db().audit(
                conn, event_id=ctx.new_id("audit"), tenant_id=user.tenant_id, actor_id=user.id,
                action="staffing.shortage.revoked", resource_type="PractitionerRole",
                resource_id=declaration_id, patient_id=None, details={"reason": body.reason},
            )
        return {"declaration_id": declaration_id, "revoked": True, "revoked_by": user.id,
                "revoked_at": revoked_at}

    @router.get("/api/wards/{ward_id}/staffing-declarations")
    def list_staffing_declarations(ward_id: str, user: CurrentUser = Depends(ctx.current_user)) -> dict:
        ctx.require_roles(user, "nurse_in_charge", "clinical_safety_officer")
        scoped_ward(ward_id, user)
        rows = db().fetchall(
            "SELECT * FROM staffing_declarations WHERE tenant_id=? AND ward_id=?"
            " ORDER BY created_at DESC",
            (user.tenant_id, ward_id),
        )
        current = datetime.now(UTC)
        for row in rows:
            row["active"] = bool(
                not row["revoked"]
                and datetime.fromisoformat(row["starts_at"]) <= current
                < datetime.fromisoformat(row["expires_at"])
            )
        return {"ward_id": ward_id, "declarations": rows}

    # ------------------------------------------------------------------
    # Nursing quality dataset -- FR-NS-160 / FR-NS-161
    # ------------------------------------------------------------------
    @router.get("/api/wards/{ward_id}/quality-measures")
    def quality_measures(ward_id: str, user: CurrentUser = Depends(ctx.current_user), days: int = Query(default=1, ge=1, le=90)) -> dict:
        ctx.require_roles(user, "nurse_in_charge", "clinical_safety_officer")
        ward = scoped_ward(ward_id, user)
        active = pack()
        results, inputs, period = compute_ward_measures(
            db(), ward=ward, tenant_id=user.tenant_id, pack=active, days=days
        )
        return {
            "ward_id": ward_id,
            "period_start": period[0],
            "period_end": period[1],
            "jurisdiction": active.jurisdiction,
            "pack_version": active.pack_version,
            "definitions_source": "country pack",
            "inputs": asdict(inputs),
            "measures": [row.as_dict() for row in results],
            "unavailable": quality.unavailable_measures(results),
        }

    # ------------------------------------------------------------------
    # Durable outbound queue -- NFR-NS-029
    # ------------------------------------------------------------------
    @router.get("/api/publications")
    def list_publications(user: CurrentUser = Depends(ctx.current_user), kind: str | None = Query(default=None)) -> dict:
        ctx.require_roles(user, "nurse_in_charge", "clinical_safety_officer")
        clauses = ["tenant_id=?"]
        params: list[Any] = [user.tenant_id]
        if kind:
            clauses.append("kind=?")
            params.append(kind)
        rows = db().fetchall(
            f"SELECT id,tenant_id,kind,connector,resource_type,operation,resource_id,"
            f"correlation_id,content_hash,status,error_code,error_detail,attempts,created_by,"
            f"created_at,completed_at FROM outbound_publications WHERE {' AND '.join(clauses)}"
            f" ORDER BY created_at DESC LIMIT 200",
            tuple(params),
        )
        return {
            "publications": rows,
            "contracts": [
                {
                    "kind": contract.kind, "connector": contract.connector,
                    "resource_type": contract.resource_type, "operation": contract.operation,
                    "route_status": contract.route_status, "gap": contract.gap_note or None,
                }
                for contract in publications.PUBLICATION_CONTRACTS.values()
            ],
        }

    return router


def compute_ward_measures(
    db: Any, *, ward: dict, tenant_id: str, pack: CountryPack, days: int
) -> tuple[list[quality.MeasureResult], quality.MeasureInputs, tuple[str, str]]:
    """Gather the measure inputs this ward owns and apply the pack definitions.

    Module-level rather than a closure so the HMIS submission route in
    :mod:`nursing_station.main` publishes the SAME numbers the read surface
    shows, instead of a second implementation that can drift from it.
    """
    end = datetime.now(UTC)
    start = (end - timedelta(days=days)).replace(microsecond=0)
    ward_id = ward["id"]
    params = (tenant_id, ward_id, start.isoformat(), end.isoformat())
    occupied = db.fetchone(
        "SELECT COUNT(*) c FROM patients WHERE tenant_id=? AND ward_id=?", (tenant_id, ward_id)
    )["c"]
    tasks = db.fetchone(
        """SELECT COUNT(*) due,
        SUM(CASE WHEN status IN ('open','accepted') OR
            (status='completed' AND completed_at>due_at) THEN 1 ELSE 0 END) missed
        FROM tasks WHERE tenant_id=? AND ward_id=? AND due_at>=? AND due_at<=?""",
        params,
    )
    falls = db.fetchone(
        """SELECT COUNT(*) c FROM harm_incidents WHERE tenant_id=? AND ward_id=?
        AND incident_type='fall' AND harm_level IN ('moderate','severe','death')
        AND present_on_admission=0 AND occurred_at>=? AND occurred_at<=?""",
        params,
    )["c"]
    hapi = db.fetchone(
        """SELECT COUNT(*) c FROM harm_incidents WHERE tenant_id=? AND ward_id=?
        AND incident_type='pressure-injury' AND present_on_admission=0
        AND occurred_at>=? AND occurred_at<=?""",
        params,
    )["c"]
    escalations_raised = db.fetchone(
        """SELECT COUNT(*) c FROM observations WHERE tenant_id=? AND ward_id=?
        AND score>=? AND recorded_at>=? AND recorded_at<=?""",
        (tenant_id, ward_id, int(pack.early_warning["thresholds"]["escalate"]),
         start.isoformat(), end.isoformat()),
    )["c"]
    answered = db.fetchone(
        """SELECT COUNT(*) c FROM escalation_responses WHERE tenant_id=? AND ward_id=?
        AND within_required_interval=1 AND responded_at>=? AND responded_at<=?""",
        params,
    )["c"]
    medication = db.fetchone(
        """SELECT COUNT(*) total, SUM(CASE WHEN outcome='omitted' THEN 1 ELSE 0 END) omitted
        FROM medication_administrations WHERE tenant_id=? AND ward_id=?
        AND administered_at>=? AND administered_at<=?""",
        params,
    )
    snapshot = db.fetchone(
        "SELECT data_json FROM staffing_snapshots WHERE tenant_id=? AND ward_id=?"
        " ORDER BY fetched_at DESC LIMIT 1",
        (tenant_id, ward_id),
    )
    registered_hours = total_hours = None
    if snapshot:
        assignments = json.loads(snapshot["data_json"])["assignments"]
        registered_hours = round(
            sum(float(a["hours"]) for a in assignments if a["registered"]), 2
        )
        total_hours = round(sum(float(a["hours"]) for a in assignments), 2)
    inputs = quality.MeasureInputs(
        occupied_bed_days=float(occupied) * days,
        registered_nursing_hours=registered_hours,
        total_nursing_hours=total_hours,
        tasks_due=int(tasks["due"] or 0),
        tasks_missed=int(tasks["missed"] or 0),
        falls_with_harm=int(falls),
        hospital_acquired_pressure_injuries=int(hapi),
        escalations_raised=int(escalations_raised),
        escalations_within_interval=int(answered),
        medication_outcomes=int(medication["total"] or 0),
        medication_omissions=int(medication["omitted"] or 0),
    )
    return (
        quality.compute_measures(pack, inputs),
        inputs,
        (start.isoformat(), end.isoformat()),
    )


def _pharmacy_discharge_evidence(body: dict) -> str | None:
    """A discharge-medicines confirmation must be visible in pharmacy's own answer."""
    for key in ("dispenses", "medication_dispenses", "dispensed"):
        entries = body.get(key)
        if isinstance(entries, list):
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                purpose = str(entry.get("purpose") or entry.get("supply_type") or "").lower()
                status = str(entry.get("status") or "").lower()
                if "discharge" in purpose and status in {"completed", "dispensed", "issued"}:
                    return str(entry.get("id") or entry.get("dispense_id") or purpose)
    return None


DISCHARGE_CONFIRMATIONS: dict[str, dict[str, Any]] = {
    "pharmacy-system": {
        "connector": "pharmacy_system",
        "resource_type": "NursingMedicationContext",
        "evidence": _pharmacy_discharge_evidence,
    },
}
