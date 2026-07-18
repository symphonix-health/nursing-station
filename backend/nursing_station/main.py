from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

import bcrypt
import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

from .config import get_settings
from .database import Database

settings = get_settings()
db = Database(settings.database_path)


def now() -> str:
    return datetime.now(UTC).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.initialise()
    yield


app = FastAPI(
    title="Symphonix Health Nursing Station",
    version="0.1.0",
    description="Phase 1 standalone inpatient nursing workflow",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Login(BaseModel):
    email: str
    password: str


class CurrentUser(BaseModel):
    id: str
    tenant_id: str
    email: str
    name: str
    role: str
    ward_id: str | None


def issue_token(user: dict) -> str:
    payload = {
        "sub": user["id"],
        "tenant": user["tenant_id"],
        "role": user["role"],
        "exp": datetime.now(UTC) + timedelta(minutes=settings.token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def current_user(authorization: Annotated[str | None, Header()] = None) -> CurrentUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    try:
        payload = jwt.decode(authorization[7:], settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
    user = db.fetchone("SELECT * FROM users WHERE id=? AND active=1", (payload["sub"],))
    if not user:
        raise HTTPException(status_code=401, detail="User is not active")
    return CurrentUser(**{key: user[key] for key in CurrentUser.model_fields})


UserDep = Annotated[CurrentUser, Depends(current_user)]


def require_roles(user: CurrentUser, *roles: str) -> None:
    if user.role not in roles:
        raise HTTPException(status_code=403, detail="Role is not authorised for this action")


def scoped_patient(patient_id: str, user: CurrentUser) -> dict:
    patient = db.fetchone("SELECT * FROM patients WHERE id=? AND tenant_id=?", (patient_id, user.tenant_id))
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if user.ward_id and patient["ward_id"] != user.ward_id:
        raise HTTPException(status_code=403, detail="Patient is outside assigned ward")
    return patient


def decode(row: dict, *fields: str) -> dict:
    for field in fields:
        row[field] = json.loads(row[field])
    return row


@app.get("/health")
def health() -> dict:
    audit_ok, audit_count = db.verify_audit()
    return {
        "status": "ok" if audit_ok else "degraded",
        "service": "nursing-station",
        "phase": 1,
        "database": "durable-sqlite",
        "audit_chain_valid": audit_ok,
        "audit_events": audit_count,
        "integrations": "not-implemented-phase-2",
    }


@app.post("/api/auth/login")
def login(body: Login) -> dict:
    user = db.fetchone("SELECT * FROM users WHERE lower(email)=lower(?) AND active=1", (body.email,))
    if not user or not bcrypt.checkpw(body.password.encode(), user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"access_token": issue_token(user), "token_type": "bearer"}


@app.get("/api/auth/me")
def me(user: UserDep) -> CurrentUser:
    return user


@app.get("/api/reference/{name}")
def reference(name: str, _: UserDep) -> dict:
    values = {
        "task-priorities": ["normal", "high", "stat"],
        "task-statuses": ["open", "accepted", "completed", "cancelled"],
        "consciousness": ["alert", "voice", "pain", "unresponsive", "new-confusion"],
        "medication-outcomes": ["administered", "withheld", "refused", "delayed", "omitted", "partial"],
        "assessment-types": ["falls", "pressure-injury", "infection", "nutrition", "hydration", "pain", "delirium"],
        "risk-levels": ["low", "moderate", "high", "critical"],
    }
    if name not in values:
        raise HTTPException(status_code=404, detail="Reference set not found")
    return {"name": name, "values": values[name]}


@app.get("/api/wards")
def wards(user: UserDep) -> list[dict]:
    if user.ward_id:
        return db.fetchall("SELECT * FROM wards WHERE id=? AND tenant_id=?", (user.ward_id, user.tenant_id))
    return db.fetchall("SELECT * FROM wards WHERE tenant_id=? ORDER BY name", (user.tenant_id,))


@app.get("/api/wards/{ward_id}/nurses")
def ward_nurses(ward_id: str, user: UserDep) -> list[dict]:
    if user.ward_id and ward_id != user.ward_id:
        raise HTTPException(status_code=403, detail="Ward is outside assignment")
    return db.fetchall(
        """SELECT id,name,role FROM users WHERE tenant_id=? AND ward_id=? AND active=1
        AND role IN ('registered_nurse','nurse_in_charge') ORDER BY name""",
        (user.tenant_id, ward_id),
    )


@app.get("/api/ward-board")
def ward_board(user: UserDep, ward_id: str | None = Query(default=None)) -> dict:
    selected = ward_id or user.ward_id
    if not selected:
        raise HTTPException(status_code=422, detail="ward_id is required for cross-ward roles")
    if user.ward_id and selected != user.ward_id:
        raise HTTPException(status_code=403, detail="Ward is outside assignment")
    ward = db.fetchone("SELECT * FROM wards WHERE id=? AND tenant_id=?", (selected, user.tenant_id))
    if not ward:
        raise HTTPException(status_code=404, detail="Ward not found")
    patients = db.fetchall(
        """SELECT p.*,u.name AS accountable_nurse_name,
        (SELECT score FROM observations o WHERE o.patient_id=p.id ORDER BY recorded_at DESC LIMIT 1) AS latest_score,
        (SELECT recorded_at FROM observations o WHERE o.patient_id=p.id ORDER BY recorded_at DESC LIMIT 1) AS observation_time,
        (SELECT COUNT(*) FROM tasks t WHERE t.patient_id=p.id AND t.status IN ('open','accepted')) AS open_tasks,
        (SELECT COUNT(*) FROM tasks t WHERE t.patient_id=p.id AND t.status IN ('open','accepted') AND t.due_at < ?) AS overdue_tasks
        FROM patients p LEFT JOIN users u ON u.id=p.accountable_nurse_id
        WHERE p.tenant_id=? AND p.ward_id=? ORDER BY p.bed""",
        (now(), user.tenant_id, selected),
    )
    for patient in patients:
        decode(patient, "allergies_json", "flags_json")
    return {"ward": ward, "patients": patients, "generated_at": now(), "source": "Phase 1 Nursing Station database"}


@app.get("/api/patients/{patient_id}")
def patient_detail(patient_id: str, user: UserDep) -> dict:
    patient = decode(scoped_patient(patient_id, user), "allergies_json", "flags_json")
    patient["observations"] = db.fetchall(
        "SELECT * FROM observations WHERE patient_id=? ORDER BY recorded_at DESC LIMIT 20", (patient_id,)
    )
    patient["tasks"] = db.fetchall(
        "SELECT * FROM tasks WHERE patient_id=? ORDER BY due_at", (patient_id,)
    )
    patient["medications"] = db.fetchall(
        "SELECT * FROM medication_orders WHERE patient_id=? AND status='active' ORDER BY due_at", (patient_id,)
    )
    patient["assessments"] = db.fetchall(
        "SELECT * FROM safety_assessments WHERE patient_id=? ORDER BY assessed_at DESC", (patient_id,)
    )
    for assessment in patient["assessments"]:
        decode(assessment, "actions_json")
    patient["care_plans"] = db.fetchall(
        "SELECT * FROM care_plans WHERE patient_id=? ORDER BY updated_at DESC", (patient_id,)
    )
    for plan in patient["care_plans"]:
        decode(plan, "interventions_json")
    return patient


class ObservationCreate(BaseModel):
    respiratory_rate: float = Field(ge=4, le=80)
    oxygen_saturation: float = Field(ge=50, le=100)
    supplemental_oxygen: bool
    systolic_bp: float = Field(ge=40, le=300)
    pulse: float = Field(ge=20, le=250)
    temperature: float = Field(ge=30, le=45)
    consciousness: Literal["alert", "voice", "pain", "unresponsive", "new-confusion"]
    source: str = Field(default="manual", min_length=2, max_length=80)


def news_score(value: ObservationCreate) -> int:
    score = 0
    score += 3 if value.respiratory_rate <= 8 or value.respiratory_rate >= 25 else 1 if value.respiratory_rate <= 11 else 2 if value.respiratory_rate >= 21 else 0
    score += 3 if value.oxygen_saturation <= 91 else 2 if value.oxygen_saturation <= 93 else 1 if value.oxygen_saturation <= 95 else 0
    score += 2 if value.supplemental_oxygen else 0
    score += 3 if value.systolic_bp <= 90 or value.systolic_bp >= 220 else 2 if value.systolic_bp <= 100 else 1 if value.systolic_bp <= 110 else 0
    score += 3 if value.pulse <= 40 or value.pulse >= 131 else 1 if value.pulse <= 50 or 91 <= value.pulse <= 110 else 2 if 111 <= value.pulse <= 130 else 0
    score += 3 if value.temperature <= 35 else 2 if value.temperature >= 39.1 else 1 if value.temperature <= 36 or value.temperature >= 38.1 else 0
    score += 0 if value.consciousness == "alert" else 3
    return int(score)


@app.post("/api/patients/{patient_id}/observations", status_code=201)
def add_observation(patient_id: str, body: ObservationCreate, user: UserDep) -> dict:
    require_roles(user, "registered_nurse", "nurse_in_charge")
    patient = scoped_patient(patient_id, user)
    observation_id = new_id("obs")
    score = news_score(body)
    escalation = "critical" if score >= 7 else "urgent" if score >= 5 else "review" if score >= 3 else "routine"
    recorded_at = now()
    with db.connect() as conn:
        conn.execute(
            """INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (observation_id,user.tenant_id,patient["ward_id"],patient_id,user.id,recorded_at,body.source,
             body.respiratory_rate,body.oxygen_saturation,int(body.supplemental_oxygen),body.systolic_bp,
             body.pulse,body.temperature,body.consciousness,score,escalation),
        )
        escalation_task = None
        if score >= 5:
            escalation_task = new_id("task")
            conn.execute(
                """INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (escalation_task,user.tenant_id,patient["ward_id"],patient_id,
                 f"{escalation.title()} deterioration review",f"Warning score {score}; assess and escalate per local policy",
                 "stat" if score >= 7 else "high","open",(datetime.now(UTC)+timedelta(minutes=5)).isoformat(),
                 patient["accountable_nurse_id"],user.id,recorded_at,None,None,None,1),
            )
        db.audit(conn,event_id=new_id("audit"),tenant_id=user.tenant_id,actor_id=user.id,
                 action="observation.recorded",resource_type="Observation",resource_id=observation_id,
                 patient_id=patient_id,details={"score":score,"escalation":escalation,"task_id":escalation_task})
    return {"id": observation_id, "score": score, "escalation_level": escalation, "escalation_task_id": escalation_task}


class TaskCreate(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=3, max_length=500)
    priority: Literal["normal", "high", "stat"]
    due_at: datetime
    assigned_to: str | None = None


@app.get("/api/tasks")
def tasks(user: UserDep, status_filter: str | None = Query(default=None, alias="status")) -> list[dict]:
    clauses = ["t.tenant_id=?"]
    params: list = [user.tenant_id]
    if user.ward_id:
        clauses.append("t.ward_id=?")
        params.append(user.ward_id)
    if status_filter:
        clauses.append("t.status=?")
        params.append(status_filter)
    return db.fetchall(
        f"""SELECT t.*,p.name AS patient_name,p.bed FROM tasks t JOIN patients p ON p.id=t.patient_id
        WHERE {' AND '.join(clauses)} ORDER BY CASE t.priority WHEN 'stat' THEN 0 WHEN 'high' THEN 1 ELSE 2 END,t.due_at""",
        tuple(params),
    )


@app.post("/api/patients/{patient_id}/tasks", status_code=201)
def create_task(patient_id: str, body: TaskCreate, user: UserDep) -> dict:
    require_roles(user, "registered_nurse", "nurse_in_charge")
    patient = scoped_patient(patient_id, user)
    if body.assigned_to:
        assignee = db.fetchone("SELECT * FROM users WHERE id=? AND tenant_id=?", (body.assigned_to, user.tenant_id))
        if not assignee or assignee["ward_id"] != patient["ward_id"]:
            raise HTTPException(status_code=422, detail="Assignee is not active in the patient's ward")
    task_id = new_id("task")
    with db.connect() as conn:
        conn.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (task_id,user.tenant_id,patient["ward_id"],patient_id,body.title,body.description,
             body.priority,"open",body.due_at.astimezone(UTC).isoformat(),body.assigned_to,user.id,now(),None,None,None,1))
        db.audit(conn,event_id=new_id("audit"),tenant_id=user.tenant_id,actor_id=user.id,
                 action="task.created",resource_type="Task",resource_id=task_id,patient_id=patient_id,
                 details={"priority":body.priority,"assigned_to":body.assigned_to})
    return {"id": task_id, "status": "open"}


class TaskTransition(BaseModel):
    action: Literal["accept", "complete", "cancel"]
    version: int
    note: str = Field(default="", max_length=500)


@app.post("/api/tasks/{task_id}/transition")
def transition_task(task_id: str, body: TaskTransition, user: UserDep) -> dict:
    require_roles(user, "registered_nurse", "nurse_in_charge")
    task = db.fetchone("SELECT * FROM tasks WHERE id=? AND tenant_id=?", (task_id, user.tenant_id))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if user.ward_id != task["ward_id"]:
        raise HTTPException(status_code=403, detail="Task is outside assigned ward")
    if body.version != task["version"]:
        raise HTTPException(status_code=409, detail="Task changed; refresh before updating")
    allowed = {"accept": ("open", "accepted"), "complete": ("accepted", "completed"), "cancel": ("open", "cancelled")}
    required, target = allowed[body.action]
    if task["status"] != required:
        raise HTTPException(status_code=409, detail=f"Task must be {required} before {body.action}")
    completed_by = user.id if target == "completed" else None
    completed_at = now() if target == "completed" else None
    assigned_to = user.id if target == "accepted" else task["assigned_to"]
    with db.connect() as conn:
        conn.execute(
            "UPDATE tasks SET status=?,assigned_to=?,completed_by=?,completed_at=?,completion_note=?,version=version+1 WHERE id=?",
            (target,assigned_to,completed_by,completed_at,body.note or None,task_id),
        )
        db.audit(conn,event_id=new_id("audit"),tenant_id=user.tenant_id,actor_id=user.id,
                 action=f"task.{target}",resource_type="Task",resource_id=task_id,
                 patient_id=task["patient_id"],details={"note":body.note})
    return {"id": task_id, "status": target, "version": body.version + 1}


class HandoverCreate(BaseModel):
    receiver_id: str
    situation: str = Field(min_length=5, max_length=2000)
    background: str = Field(min_length=5, max_length=2000)
    assessment: str = Field(min_length=5, max_length=2000)
    recommendation: str = Field(min_length=5, max_length=2000)


@app.get("/api/handovers")
def handovers(user: UserDep, status_filter: str | None = Query(default=None, alias="status")) -> list[dict]:
    clauses = ["h.tenant_id=?", "(h.sender_id=? OR h.receiver_id=?)"]
    params: list[str] = [user.tenant_id, user.id, user.id]
    if status_filter:
        clauses.append("h.status=?")
        params.append(status_filter)
    rows = db.fetchall(
        f"""SELECT h.*,p.name AS patient_name,p.bed,s.name AS sender_name,r.name AS receiver_name
        FROM handovers h JOIN patients p ON p.id=h.patient_id
        JOIN users s ON s.id=h.sender_id JOIN users r ON r.id=h.receiver_id
        WHERE {' AND '.join(clauses)} ORDER BY h.created_at DESC""",
        tuple(params),
    )
    for row in rows:
        decode(row, "unresolved_tasks_json")
    return rows


@app.post("/api/patients/{patient_id}/handovers", status_code=201)
def create_handover(patient_id: str, body: HandoverCreate, user: UserDep) -> dict:
    require_roles(user, "registered_nurse", "nurse_in_charge")
    patient = scoped_patient(patient_id, user)
    receiver = db.fetchone("SELECT * FROM users WHERE id=? AND active=1", (body.receiver_id,))
    if not receiver or receiver["tenant_id"] != user.tenant_id or receiver["ward_id"] != patient["ward_id"] or receiver["id"] == user.id:
        raise HTTPException(status_code=422, detail="Receiver must be a different active nurse in this ward")
    unresolved = db.fetchall("SELECT id,title,priority,due_at,status FROM tasks WHERE patient_id=? AND status IN ('open','accepted')", (patient_id,))
    handover_id = new_id("handover")
    with db.connect() as conn:
        conn.execute("INSERT INTO handovers VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (handover_id,user.tenant_id,patient["ward_id"],patient_id,user.id,body.receiver_id,now(),None,
             body.situation,body.background,body.assessment,body.recommendation,json.dumps(unresolved),"pending"))
        db.audit(conn,event_id=new_id("audit"),tenant_id=user.tenant_id,actor_id=user.id,
                 action="handover.created",resource_type="Communication",resource_id=handover_id,
                 patient_id=patient_id,details={"receiver_id":body.receiver_id,"unresolved_task_count":len(unresolved)})
    return {"id": handover_id, "status": "pending", "unresolved_tasks": unresolved}


@app.post("/api/handovers/{handover_id}/accept")
def accept_handover(handover_id: str, user: UserDep) -> dict:
    handover = db.fetchone("SELECT * FROM handovers WHERE id=? AND tenant_id=?", (handover_id, user.tenant_id))
    if not handover:
        raise HTTPException(status_code=404, detail="Handover not found")
    if handover["receiver_id"] != user.id:
        raise HTTPException(status_code=403, detail="Only the named receiver may accept")
    if handover["status"] != "pending":
        raise HTTPException(status_code=409, detail="Handover is not pending")
    accepted_at = now()
    with db.connect() as conn:
        conn.execute("UPDATE handovers SET status='accepted',accepted_at=? WHERE id=?", (accepted_at,handover_id))
        conn.execute("UPDATE patients SET accountable_nurse_id=?,version=version+1 WHERE id=?", (user.id,handover["patient_id"]))
        db.audit(conn,event_id=new_id("audit"),tenant_id=user.tenant_id,actor_id=user.id,
                 action="handover.accepted",resource_type="Communication",resource_id=handover_id,
                 patient_id=handover["patient_id"],details={"accountability_transferred":True})
    return {"id": handover_id, "status": "accepted", "accepted_at": accepted_at}


class CarePlanCreate(BaseModel):
    problem: str = Field(min_length=3, max_length=500)
    goal: str = Field(min_length=3, max_length=1000)
    interventions: list[str] = Field(min_length=1, max_length=20)
    owner_id: str


class CarePlanUpdate(BaseModel):
    status: Literal["active", "achieved", "discontinued"]
    evaluation: str = Field(min_length=3, max_length=2000)
    version: int = Field(ge=1)


@app.post("/api/patients/{patient_id}/care-plans", status_code=201)
def create_care_plan(patient_id: str, body: CarePlanCreate, user: UserDep) -> dict:
    require_roles(user, "registered_nurse", "nurse_in_charge")
    patient = scoped_patient(patient_id, user)
    owner = db.fetchone("SELECT * FROM users WHERE id=? AND active=1", (body.owner_id,))
    if not owner or owner["tenant_id"] != user.tenant_id or owner["ward_id"] != patient["ward_id"]:
        raise HTTPException(status_code=422, detail="Care plan owner must be an active nurse in this ward")
    plan_id = new_id("care")
    created_at = now()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO care_plans VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (plan_id,user.tenant_id,patient["ward_id"],patient_id,body.problem,body.goal,
             json.dumps(body.interventions),"active",body.owner_id,user.id,created_at,created_at,None,1),
        )
        db.audit(conn,event_id=new_id("audit"),tenant_id=user.tenant_id,actor_id=user.id,
                 action="care-plan.created",resource_type="CarePlan",resource_id=plan_id,
                 patient_id=patient_id,details={"owner_id":body.owner_id})
    return {"id": plan_id, "status": "active", "version": 1}


@app.post("/api/care-plans/{plan_id}/evaluate")
def evaluate_care_plan(plan_id: str, body: CarePlanUpdate, user: UserDep) -> dict:
    require_roles(user, "registered_nurse", "nurse_in_charge")
    plan = db.fetchone("SELECT * FROM care_plans WHERE id=? AND tenant_id=?", (plan_id, user.tenant_id))
    if not plan:
        raise HTTPException(status_code=404, detail="Care plan not found")
    scoped_patient(plan["patient_id"], user)
    with db.connect() as conn:
        changed = conn.execute(
            """UPDATE care_plans SET status=?,evaluation=?,updated_at=?,version=version+1
            WHERE id=? AND version=?""",
            (body.status,body.evaluation,now(),plan_id,body.version),
        )
        if changed.rowcount != 1:
            raise HTTPException(status_code=409, detail="Care plan changed; refresh before evaluating")
        db.audit(conn,event_id=new_id("audit"),tenant_id=user.tenant_id,actor_id=user.id,
                 action="care-plan.evaluated",resource_type="CarePlan",resource_id=plan_id,
                 patient_id=plan["patient_id"],details={"status":body.status,"evaluation":body.evaluation})
    return {"id": plan_id, "status": body.status, "version": body.version + 1}


@app.get("/api/patients/{patient_id}/medications")
def medications(patient_id: str, user: UserDep) -> list[dict]:
    scoped_patient(patient_id, user)
    return db.fetchall("SELECT * FROM medication_orders WHERE patient_id=? ORDER BY due_at", (patient_id,))


class AdministrationCreate(BaseModel):
    outcome: Literal["administered", "withheld", "refused", "delayed", "omitted", "partial"]
    reason: str | None = Field(default=None, max_length=500)
    mrn_verified: str
    date_of_birth_verified: str
    cosigner_id: str | None = None

    @model_validator(mode="after")
    def reason_for_non_administered(self):
        if self.outcome != "administered" and not self.reason:
            raise ValueError("A reason is required when outcome is not administered")
        return self


@app.post("/api/medication-orders/{order_id}/administrations", status_code=201)
def administer(order_id: str, body: AdministrationCreate, user: UserDep) -> dict:
    require_roles(user, "registered_nurse", "nurse_in_charge")
    order = db.fetchone("SELECT * FROM medication_orders WHERE id=? AND tenant_id=?", (order_id,user.tenant_id))
    if not order:
        raise HTTPException(status_code=404, detail="Medication order not found")
    patient = scoped_patient(order["patient_id"], user)
    if body.mrn_verified != patient["mrn"] or body.date_of_birth_verified != patient["date_of_birth"]:
        raise HTTPException(status_code=422, detail="Two-identifier patient verification failed")
    cosigner = None
    if order["high_alert"]:
        if not body.cosigner_id or body.cosigner_id == user.id:
            raise HTTPException(status_code=422, detail="Independent co-signer required for high-alert medication")
        cosigner = db.fetchone("SELECT * FROM users WHERE id=? AND active=1", (body.cosigner_id,))
        if not cosigner or cosigner["ward_id"] != patient["ward_id"] or cosigner["role"] not in {"registered_nurse","nurse_in_charge"}:
            raise HTTPException(status_code=422, detail="Co-signer is not an eligible nurse in this ward")
    administration_id = new_id("admin")
    with db.connect() as conn:
        existing = conn.execute(
            "SELECT id FROM medication_administrations WHERE order_id=? AND outcome <> 'delayed'",
            (order_id,),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Medication occurrence already has a terminal administration record")
        try:
            conn.execute("INSERT INTO medication_administrations VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (administration_id,user.tenant_id,patient["ward_id"],patient["id"],order_id,body.outcome,
                 body.reason,user.id,cosigner["id"] if cosigner else None,now(),body.mrn_verified,body.date_of_birth_verified))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(
                status_code=409,
                detail="Medication occurrence already has a terminal administration record",
            ) from exc
        if body.outcome != "delayed":
            conn.execute("UPDATE medication_orders SET status=? WHERE id=?", (body.outcome, order_id))
        db.audit(conn,event_id=new_id("audit"),tenant_id=user.tenant_id,actor_id=user.id,
                 action="medication.administration-recorded",resource_type="MedicationAdministration",
                 resource_id=administration_id,patient_id=patient["id"],
                 details={"order_id":order_id,"outcome":body.outcome,"cosigner_id":body.cosigner_id})
    return {"id": administration_id, "outcome": body.outcome, "server_confirmed": True}


class AssessmentCreate(BaseModel):
    assessment_type: Literal["falls", "pressure-injury", "infection", "nutrition", "hydration", "pain", "delirium"]
    risk_level: Literal["low", "moderate", "high", "critical"]
    score: float | None = None
    findings: str = Field(min_length=3, max_length=1000)
    actions: list[str] = Field(min_length=1, max_length=10)


@app.post("/api/patients/{patient_id}/safety-assessments", status_code=201)
def assess(patient_id: str, body: AssessmentCreate, user: UserDep) -> dict:
    require_roles(user, "registered_nurse", "nurse_in_charge")
    patient = scoped_patient(patient_id, user)
    assessment_id = new_id("assessment")
    created_tasks: list[str] = []
    with db.connect() as conn:
        conn.execute("INSERT INTO safety_assessments VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (assessment_id,user.tenant_id,patient["ward_id"],patient_id,body.assessment_type,
             body.risk_level,body.score,body.findings,json.dumps(body.actions),user.id,now()))
        for action in body.actions:
            task_id = new_id("task")
            created_tasks.append(task_id)
            priority = "stat" if body.risk_level == "critical" else "high" if body.risk_level == "high" else "normal"
            conn.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (task_id,user.tenant_id,patient["ward_id"],patient_id,action,
                 f"Generated from {body.assessment_type} assessment",priority,"open",
                 (datetime.now(UTC)+timedelta(hours=1)).isoformat(),patient["accountable_nurse_id"],
                 user.id,now(),None,None,None,1))
        db.audit(conn,event_id=new_id("audit"),tenant_id=user.tenant_id,actor_id=user.id,
                 action="safety-assessment.recorded",resource_type="RiskAssessment",
                 resource_id=assessment_id,patient_id=patient_id,
                 details={"type":body.assessment_type,"risk":body.risk_level,"task_ids":created_tasks})
    return {"id": assessment_id, "generated_task_ids": created_tasks}


@app.get("/api/audit")
def audit_log(user: UserDep, limit: int = Query(default=100, ge=1, le=500)) -> dict:
    require_roles(user, "nurse_in_charge", "clinical_safety_officer")
    clauses = ["tenant_id=?"]
    params: list = [user.tenant_id]
    if user.ward_id:
        patient_ids = [row["id"] for row in db.fetchall("SELECT id FROM patients WHERE ward_id=?", (user.ward_id,))]
        if patient_ids:
            clauses.append(f"(patient_id IN ({','.join('?' for _ in patient_ids)}) OR patient_id IS NULL)")
            params.extend(patient_ids)
    params.append(limit)
    events = db.fetchall(f"SELECT * FROM audit_events WHERE {' AND '.join(clauses)} ORDER BY sequence DESC LIMIT ?", tuple(params))
    valid, count = db.verify_audit()
    return {"chain_valid": valid, "total_events": count, "events": events}


@app.exception_handler(sqlite3.IntegrityError)
async def integrity_error(_, exc: sqlite3.IntegrityError):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


def run() -> None:
    import uvicorn
    uvicorn.run("nursing_station.main:app", host="127.0.0.1", port=8781, reload=False)


if __name__ == "__main__":
    run()
