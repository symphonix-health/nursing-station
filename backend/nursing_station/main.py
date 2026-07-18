from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

import bcrypt
import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

from .config import get_settings
from .database import Database
from .integration import SOURCE_CONTRACTS, HubClient, IntegrationError
from .port_registry import resolve_frontend_port

settings = get_settings()
db = Database(settings.database_path)
OBSERVATION_UNITS = {
    "respiratory_rate": "/min",
    "oxygen_saturation": "%",
    "systolic_bp": "mmHg",
    "pulse": "/min",
    "temperature": "Cel",
}


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
    version="0.2.0",
    description="Phase 2 hub-integrated inpatient nursing workflow",
    lifespan=lifespan,
)
frontend_port = resolve_frontend_port()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://127.0.0.1:{frontend_port}",
        f"http://localhost:{frontend_port}",
    ],
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
    facility_id: str | None


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
    user = db.fetchone(
        """SELECT u.*,w.facility_id FROM users u LEFT JOIN wards w ON w.id=u.ward_id
        WHERE u.id=? AND u.active=1""",
        (payload["sub"],),
    )
    if not user:
        raise HTTPException(status_code=401, detail="User is not active")
    return CurrentUser(**{key: user[key] for key in CurrentUser.model_fields})


UserDep = Annotated[CurrentUser, Depends(current_user)]


def require_roles(user: CurrentUser, *roles: str) -> None:
    if user.role not in roles:
        raise HTTPException(status_code=403, detail="Role is not authorised for this action")


def scoped_patient(patient_id: str, user: CurrentUser) -> dict:
    require_roles(
        user,
        "registered_nurse",
        "nurse_in_charge",
        "clinical_safety_officer",
    )
    patient = db.fetchone(
        """SELECT p.*,w.facility_id,u.name AS accountable_nurse_name
        FROM patients p JOIN wards w ON w.id=p.ward_id
        LEFT JOIN users u ON u.id=p.accountable_nurse_id
        WHERE p.id=? AND p.tenant_id=?""",
        (patient_id, user.tenant_id),
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if user.ward_id and patient["ward_id"] != user.ward_id:
        raise HTTPException(status_code=403, detail="Patient is outside assigned ward")
    if user.facility_id and patient["facility_id"] != user.facility_id:
        raise HTTPException(status_code=403, detail="Patient is outside assigned facility")
    if user.role in {"registered_nurse", "nurse_in_charge"} and not user.ward_id:
        raise HTTPException(status_code=403, detail="No active ward care relationship")
    return patient


def decode(row: dict, *fields: str) -> dict:
    for field in fields:
        row[field] = json.loads(row[field])
    return row


@app.get("/health")
def health() -> dict:
    audit_ok, audit_count = db.verify_audit()
    seed = db.fetchone("SELECT seed_manifest_id,data_class FROM seed_runs LIMIT 1")
    return {
        "status": "ok" if audit_ok else "degraded",
        "service": "nursing-station",
        "phase": 2,
        "database": "durable-sqlite",
        "audit_chain_valid": audit_ok,
        "audit_events": audit_count,
        "integrations": (
            "configured-bullettrain-hub"
            if settings.integration_hub_url and settings.integration_hub_token
            else "not-configured-fail-closed"
        ),
        "warning_profile": settings.warning_profile_version,
        "alert_refresh_seconds": settings.alert_refresh_seconds,
        "synthetic_seed": seed,
    }


class CriticalResultAlert(BaseModel):
    event_id: str = Field(min_length=1, max_length=128)
    source_system: Literal["lis"]
    source_patient_id: str = Field(min_length=1, max_length=128)
    result_id: str = Field(min_length=1, max_length=128)
    test_name: str = Field(min_length=1, max_length=160)
    result_value: str = Field(min_length=1, max_length=120)
    unit: str = Field(min_length=1, max_length=40)
    interpretation: str = Field(min_length=1, max_length=160)
    observed_at: datetime
    severity: Literal["critical"]


def _verify_hub_signature(raw_body: bytes, signature: str | None) -> None:
    if not settings.inbound_hmac_secret:
        raise HTTPException(status_code=503, detail="Inbound hub authentication is not configured")
    if not signature or not signature.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Valid hub signature required")
    expected = hmac.new(
        settings.inbound_hmac_secret.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature[7:], expected):
        raise HTTPException(status_code=401, detail="Invalid hub signature")


@app.post("/api/integrations/lis/critical-result", status_code=202)
async def receive_critical_result(
    request: Request,
    x_signature: Annotated[str | None, Header()] = None,
    x_event_id: Annotated[str | None, Header()] = None,
    x_event_kind: Annotated[str | None, Header()] = None,
    x_correlation_id: Annotated[str | None, Header()] = None,
) -> dict:
    raw_body = await request.body()
    _verify_hub_signature(raw_body, x_signature)
    if x_event_kind != "critical-result":
        raise HTTPException(status_code=400, detail="Unexpected hub event kind")
    try:
        event = CriticalResultAlert.model_validate_json(raw_body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid critical-result event") from exc
    if x_event_id != event.event_id:
        raise HTTPException(status_code=400, detail="Event identity mismatch")
    patient = db.fetchone(
        "SELECT * FROM patients WHERE external_nhs_number=?", (event.source_patient_id,)
    )
    if not patient:
        raise HTTPException(status_code=404, detail="No governed patient identity link")
    canonical = json.dumps(event.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    correlation_id = x_correlation_id or event.event_id
    existing = db.fetchone(
        "SELECT * FROM clinical_alerts WHERE source_system=? AND event_id=?",
        (event.source_system, event.event_id),
    )
    if existing:
        if existing["content_hash"] != content_hash:
            raise HTTPException(status_code=409, detail="Event identifier reused with different content")
        return {"status": "duplicate", "alert_id": existing["id"], "event_id": event.event_id}
    alert_id = new_id("alert")
    received_at = now()
    with db.connect() as conn:
        conn.execute(
            """INSERT INTO clinical_alerts
            (id,tenant_id,ward_id,patient_id,event_id,source_system,source_resource_id,
             alert_type,severity,title,summary,observed_at,received_at,status,
             acknowledged_at,acknowledged_by,correlation_id,content_hash,version)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'open',NULL,NULL,?,?,1)""",
            (
                alert_id, patient["tenant_id"], patient["ward_id"], patient["id"],
                event.event_id, event.source_system, event.result_id, "critical-result",
                event.severity, f"Critical {event.test_name} result",
                f"{event.result_value} {event.unit}; {event.interpretation}",
                event.observed_at.isoformat(), received_at, correlation_id, content_hash,
            ),
        )
        db.audit(
            conn, event_id=new_id("audit"), tenant_id=patient["tenant_id"],
            actor_id="bullettrain-hub", action="clinical_alert.received",
            resource_type="CriticalResultAlert", resource_id=alert_id,
            patient_id=patient["id"],
            details={"event_id": event.event_id, "correlation_id": correlation_id,
                     "source_system": event.source_system, "content_hash": content_hash},
        )
    return {"status": "accepted", "alert_id": alert_id, "event_id": event.event_id}


@app.get("/api/alerts")
def alerts(user: UserDep, alert_status: Literal["open", "acknowledged", "all"] = "open") -> dict:
    require_roles(user, "registered_nurse", "nurse_in_charge", "clinical_safety_officer")
    clauses = ["a.tenant_id=?"]
    params: list[object] = [user.tenant_id]
    if user.ward_id:
        clauses.append("a.ward_id=?")
        params.append(user.ward_id)
    if alert_status != "all":
        clauses.append("a.status=?")
        params.append(alert_status)
    rows = db.fetchall(
        f"""SELECT a.*,p.name AS patient_name,p.bed,p.mrn FROM clinical_alerts a
        JOIN patients p ON p.id=a.patient_id WHERE {' AND '.join(clauses)}
        ORDER BY a.received_at DESC""", tuple(params)
    )
    return {"alerts": rows, "generated_at": now(), "refresh_seconds": settings.alert_refresh_seconds}


@app.post("/api/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str, user: UserDep) -> dict:
    require_roles(user, "registered_nurse", "nurse_in_charge", "clinical_safety_officer")
    alert = db.fetchone("SELECT * FROM clinical_alerts WHERE id=? AND tenant_id=?", (alert_id, user.tenant_id))
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if user.ward_id and alert["ward_id"] != user.ward_id:
        raise HTTPException(status_code=403, detail="Alert is outside assigned ward")
    if alert["status"] == "acknowledged":
        return alert
    acknowledged_at = now()
    with db.connect() as conn:
        conn.execute(
            """UPDATE clinical_alerts SET status='acknowledged',acknowledged_at=?,
            acknowledged_by=?,version=version+1 WHERE id=?""",
            (acknowledged_at, user.id, alert_id),
        )
        db.audit(
            conn, event_id=new_id("audit"), tenant_id=user.tenant_id, actor_id=user.id,
            action="clinical_alert.acknowledged", resource_type="CriticalResultAlert",
            resource_id=alert_id, patient_id=alert["patient_id"],
            details={"event_id": alert["event_id"], "correlation_id": alert["correlation_id"]},
        )
    return db.fetchone("SELECT * FROM clinical_alerts WHERE id=?", (alert_id,))


def _latest_source_timestamp(value: object) -> str | None:
    candidates: list[str] = []

    def visit(item: object) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                if key in {
                    "updated_at", "source_updated_at", "verified_at", "tested_at",
                    "last_update", "received_at", "created_at", "dispensed_at",
                } and isinstance(nested, str):
                    candidates.append(nested)
                visit(nested)
        elif isinstance(item, list):
            for nested in item:
                visit(nested)

    visit(value)
    return max(candidates) if candidates else None


def _identity_status(patient: dict, source: str, body: dict) -> str:
    if source in {"picis-system", "blood-transfusion"}:
        source_patient = body.get("patient")
        if not isinstance(source_patient, dict):
            raise IntegrationError("identity_missing", f"{source} omitted patient identity")
        external_number = source_patient.get("external_nhs_number")
        source_name = source_patient.get("name") or source_patient.get("full_name")
        source_dob = source_patient.get("date_of_birth") or source_patient.get("dob")
        if external_number != patient["external_nhs_number"]:
            raise IntegrationError("identity_mismatch", f"{source} returned a different NHS number")
        if source_name and source_name.casefold() != patient["name"].casefold():
            raise IntegrationError("identity_mismatch", f"{source} returned a different patient name")
        if source_dob and str(source_dob)[:10] != patient["date_of_birth"]:
            raise IntegrationError("identity_mismatch", f"{source} returned a different date of birth")
        return "three-identifier-match" if source_name and source_dob else "nhs-number-match"
    expected_patient_id = (
        patient["external_nhs_number"] if source == "lis" else patient["source_patient_id"]
    )
    if body.get("patient_id") != expected_patient_id:
        raise IntegrationError("identity_mismatch", f"{source} returned a different patient identifier")
    return "source-patient-id-match"


def _integration_payload(patient: dict, source: str) -> dict:
    key = "external_nhs_number" if source in {"picis-system", "lis", "blood-transfusion"} else "patient_id"
    value = patient["external_nhs_number"] if key == "external_nhs_number" else patient["source_patient_id"]
    return {key: value}


@app.get("/api/patients/{patient_id}/integrations")
def patient_integrations(patient_id: str, user: UserDep) -> dict:
    patient = scoped_patient(patient_id, user)
    snapshots = {
        row["source_system"]: row
        for row in db.fetchall(
            "SELECT * FROM integration_snapshots WHERE tenant_id=? AND patient_id=?",
            (user.tenant_id, patient_id),
        )
    }
    latest_attempts = {
        row["source_system"]: row
        for row in db.fetchall(
            """SELECT a.* FROM integration_attempts a JOIN (
            SELECT source_system,MAX(attempted_at) attempted_at FROM integration_attempts
            WHERE tenant_id=? AND patient_id=? GROUP BY source_system
            ) latest ON latest.source_system=a.source_system AND latest.attempted_at=a.attempted_at
            WHERE a.tenant_id=? AND a.patient_id=?""",
            (user.tenant_id, patient_id, user.tenant_id, patient_id),
        )
    }
    sources = []
    for source, contract in SOURCE_CONTRACTS.items():
        snapshot = snapshots.get(source)
        attempt = latest_attempts.get(source)
        if snapshot:
            snapshot["data"] = json.loads(snapshot.pop("data_json"))
        sources.append({
            "source_system": source,
            "resource_type": contract.resource_type,
            "semantics": contract.semantics,
            "state": attempt["status"] if attempt else (snapshot["status"] if snapshot else "not-refreshed"),
            "last_attempt": attempt,
            "snapshot": snapshot,
        })
    with db.connect() as conn:
        db.audit(
            conn, event_id=new_id("audit"), tenant_id=user.tenant_id, actor_id=user.id,
            action="integration.context.viewed", resource_type="IntegrationSnapshot",
            resource_id=patient_id, patient_id=patient_id,
            details={"sources": list(SOURCE_CONTRACTS), "purpose_of_use": "treatment"},
        )
    return {
        "patient_id": patient_id,
        "linked": bool(patient["external_nhs_number"] and patient["source_patient_id"]),
        "identity": {
            "external_nhs_number": patient["external_nhs_number"],
            "source_patient_id": patient["source_patient_id"],
        },
        "sources": sources,
    }


@app.post("/api/patients/{patient_id}/integrations/refresh")
async def refresh_patient_integrations(patient_id: str, user: UserDep) -> dict:
    patient = scoped_patient(patient_id, user)
    if not patient["external_nhs_number"] or not patient["source_patient_id"]:
        raise HTTPException(status_code=409, detail="Patient has no governed cross-system identity link")
    try:
        hub = HubClient(settings)
    except IntegrationError as exc:
        raise HTTPException(status_code=503, detail={"code": exc.code, "message": exc.detail}) from exc

    results = []
    for source, contract in SOURCE_CONTRACTS.items():
        correlation_id = new_id(f"ns-{source}")
        attempt_id = new_id("integration-attempt")
        attempted_at = now()
        with db.connect() as conn:
            conn.execute(
                """INSERT INTO integration_attempts
                (id,tenant_id,patient_id,source_system,resource_type,correlation_id,attempted_at,status)
                VALUES (?,?,?,?,?,?,?,?)""",
                (attempt_id, user.tenant_id, patient_id, source, contract.resource_type, correlation_id, attempted_at, "in-progress"),
            )
        try:
            exchanged = await hub.exchange(
                connector=contract.connector, resource_type=contract.resource_type,
                operation="read", payload=_integration_payload(patient, source),
                tenant_id=user.tenant_id, actor_id=user.id, role=user.role,
                correlation_id=correlation_id,
            )
            body = exchanged["body"]
            reconciliation = _identity_status(patient, source, body)
            canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
            content_hash = hashlib.sha256(canonical.encode()).hexdigest()
            source_updated_at = _latest_source_timestamp(body)
            completed_at = now()
            with db.connect() as conn:
                existing = conn.execute(
                    "SELECT id,version,content_hash,source_updated_at FROM integration_snapshots WHERE tenant_id=? AND patient_id=? AND source_system=?",
                    (user.tenant_id, patient_id, source),
                ).fetchone()
                if existing and source_updated_at and existing["source_updated_at"] and source_updated_at < existing["source_updated_at"]:
                    raise IntegrationError("stale_source", f"{source} returned an older source version")
                if existing:
                    if existing["content_hash"] == content_hash:
                        conn.execute(
                            """UPDATE integration_snapshots SET fetched_at=?,status='current',
                            reconciliation_status=?,correlation_id=? WHERE id=?""",
                            (completed_at, reconciliation, correlation_id, existing["id"]),
                        )
                    else:
                        conn.execute(
                            """UPDATE integration_snapshots SET resource_type=?,content_hash=?,source_updated_at=?,
                            fetched_at=?,status='current',reconciliation_status=?,correlation_id=?,data_json=?,version=version+1
                            WHERE id=?""",
                            (contract.resource_type, content_hash, source_updated_at, completed_at,
                             reconciliation, correlation_id, canonical, existing["id"]),
                        )
                    snapshot_id = existing["id"]
                else:
                    snapshot_id = new_id("integration-snapshot")
                    conn.execute(
                        """INSERT INTO integration_snapshots
                        (id,tenant_id,patient_id,source_system,resource_type,content_hash,source_updated_at,
                        fetched_at,status,reconciliation_status,correlation_id,data_json,version)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                        (snapshot_id, user.tenant_id, patient_id, source, contract.resource_type,
                         content_hash, source_updated_at, completed_at, "current",
                         reconciliation, correlation_id, canonical),
                    )
                conn.execute(
                    """UPDATE integration_attempts SET completed_at=?,status='success',content_hash=?,
                    hub_audit_event_id=?,duration_ms=? WHERE id=?""",
                    (completed_at, content_hash, exchanged.get("hub_audit_event_id"), exchanged.get("duration_ms"), attempt_id),
                )
                db.audit(
                    conn, event_id=new_id("audit"), tenant_id=user.tenant_id, actor_id=user.id,
                    action="integration.context.refreshed", resource_type=contract.resource_type,
                    resource_id=snapshot_id, patient_id=patient_id,
                    details={"source_system": source, "correlation_id": correlation_id,
                             "content_hash": content_hash, "reconciliation_status": reconciliation,
                             "purpose_of_use": "treatment"},
                )
            results.append({"source_system": source, "status": "success", "correlation_id": correlation_id})
        except IntegrationError as exc:
            completed_at = now()
            with db.connect() as conn:
                conn.execute(
                    """UPDATE integration_attempts SET completed_at=?,status='failed',error_code=?,
                    error_detail=?,hub_audit_event_id=? WHERE id=?""",
                    (completed_at, exc.code, exc.detail, exc.hub_audit_event_id, attempt_id),
                )
                conn.execute(
                    """UPDATE integration_snapshots SET status='stale',version=version+1
                    WHERE tenant_id=? AND patient_id=? AND source_system=?""",
                    (user.tenant_id, patient_id, source),
                )
                db.audit(
                    conn, event_id=new_id("audit"), tenant_id=user.tenant_id, actor_id=user.id,
                    action="integration.context.failed", resource_type=contract.resource_type,
                    resource_id=attempt_id, patient_id=patient_id,
                    details={"source_system": source, "correlation_id": correlation_id,
                             "error_code": exc.code, "purpose_of_use": "treatment"},
                )
            results.append({"source_system": source, "status": "failed", "error_code": exc.code,
                            "message": exc.detail, "correlation_id": correlation_id})
    return {"patient_id": patient_id, "results": results, "all_succeeded": all(row["status"] == "success" for row in results)}


@app.post("/api/wards/{ward_id}/hmis-measures")
async def submit_hmis_measures(ward_id: str, user: UserDep) -> dict:
    require_roles(user, "nurse_in_charge", "clinical_safety_officer")
    ward = db.fetchone(
        "SELECT * FROM wards WHERE id=? AND tenant_id=?", (ward_id, user.tenant_id)
    )
    if not ward:
        raise HTTPException(status_code=404, detail="Ward not found")
    if user.ward_id and user.ward_id != ward_id:
        raise HTTPException(status_code=403, detail="Ward is outside assigned scope")
    try:
        hub = HubClient(settings)
    except IntegrationError as exc:
        raise HTTPException(status_code=503, detail={"code": exc.code, "message": exc.detail}) from exc
    current = datetime.now(UTC)
    start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    measures = db.fetchone(
        """SELECT COUNT(*) occupied_beds,
        SUM((SELECT COUNT(*) FROM tasks t WHERE t.patient_id=p.id AND t.status IN ('open','accepted'))) open_tasks,
        SUM((SELECT COUNT(*) FROM tasks t WHERE t.patient_id=p.id AND t.status IN ('open','accepted') AND t.due_at<?)) overdue_tasks,
        SUM(CASE WHEN COALESCE((SELECT score FROM observations o WHERE o.patient_id=p.id ORDER BY recorded_at DESC LIMIT 1),0)>=5 THEN 1 ELSE 0 END) high_warning_score_patients,
        SUM(CASE WHEN p.isolation_status<>'None' THEN 1 ELSE 0 END) isolation_patients
        FROM patients p WHERE p.tenant_id=? AND p.ward_id=?""",
        (current.isoformat(), user.tenant_id, ward_id),
    ) or {}
    medication_count = db.fetchone(
        "SELECT COUNT(*) count FROM medication_administrations WHERE tenant_id=? AND ward_id=? AND administered_at>=?",
        (user.tenant_id, ward_id, start.isoformat()),
    )
    payload = {
        "tenant_id": user.tenant_id,
        "facility_id": ward["facility_id"],
        "ward_id": ward_id,
        "period_start": start.isoformat(),
        "period_end": current.isoformat(),
        "counts": {
            "occupied_beds": int(measures.get("occupied_beds") or 0),
            "open_tasks": int(measures.get("open_tasks") or 0),
            "overdue_tasks": int(measures.get("overdue_tasks") or 0),
            "high_warning_score_patients": int(measures.get("high_warning_score_patients") or 0),
            "isolation_patients": int(measures.get("isolation_patients") or 0),
            "medication_outcomes_recorded": int((medication_count or {}).get("count") or 0),
        },
    }
    correlation_id = new_id("ns-hmis")
    try:
        exchanged = await hub.exchange(
            connector="hmis", resource_type="NursingMeasureReport", operation="write",
            payload=payload, tenant_id=user.tenant_id, actor_id=user.id, role=user.role,
            correlation_id=correlation_id, purpose_of_use="operations",
        )
    except IntegrationError as exc:
        with db.connect() as conn:
            db.audit(
                conn, event_id=new_id("audit"), tenant_id=user.tenant_id, actor_id=user.id,
                action="hmis.measure.failed", resource_type="MeasureReport",
                resource_id=correlation_id, patient_id=None,
                details={"ward_id": ward_id, "error_code": exc.code, "correlation_id": correlation_id},
            )
        raise HTTPException(status_code=502, detail={"code": exc.code, "message": exc.detail}) from exc
    with db.connect() as conn:
        db.audit(
            conn, event_id=new_id("audit"), tenant_id=user.tenant_id, actor_id=user.id,
            action="hmis.measure.submitted", resource_type="MeasureReport",
            resource_id=correlation_id, patient_id=None,
            details={"ward_id": ward_id, "correlation_id": correlation_id,
                     "hub_audit_event_id": exchanged.get("hub_audit_event_id")},
        )
    return {"correlation_id": correlation_id, "measures": payload, "receipt": exchanged["body"]}


@app.get("/api/governance/seed")
def seed_governance(_: UserDep) -> dict:
    row = db.fetchone("SELECT * FROM seed_runs ORDER BY generated_at DESC LIMIT 1")
    if not row:
        raise HTTPException(status_code=503, detail="Synthetic seed declaration is unavailable")
    row["record_counts"] = json.loads(row.pop("record_counts_json"))
    row["declaration"] = json.loads(row.pop("declaration_json"))
    return row


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
        """SELECT o.*,u.name AS recorded_by_name FROM observations o
        JOIN users u ON u.id=o.recorded_by WHERE o.patient_id=?
        ORDER BY o.recorded_at DESC LIMIT 20""",
        (patient_id,),
    )
    for observation in patient["observations"]:
        decode(observation, "units_json")
    patient["tasks"] = db.fetchall(
        """SELECT t.*,creator.name AS created_by_name,assignee.name AS assigned_to_name
        FROM tasks t JOIN users creator ON creator.id=t.created_by
        LEFT JOIN users assignee ON assignee.id=t.assigned_to
        WHERE t.patient_id=? ORDER BY t.due_at""",
        (patient_id,),
    )
    patient["medications"] = db.fetchall(
        "SELECT * FROM medication_orders WHERE patient_id=? AND status='active' ORDER BY due_at", (patient_id,)
    )
    patient["assessments"] = db.fetchall(
        """SELECT s.*,u.name AS assessed_by_name FROM safety_assessments s
        JOIN users u ON u.id=s.assessed_by
        WHERE s.patient_id=? ORDER BY s.assessed_at DESC""",
        (patient_id,),
    )
    for assessment in patient["assessments"]:
        decode(assessment, "actions_json")
    patient["care_plans"] = db.fetchall(
        """SELECT c.*,owner.name AS owner_name,creator.name AS created_by_name
        FROM care_plans c JOIN users owner ON owner.id=c.owner_id
        JOIN users creator ON creator.id=c.created_by
        WHERE c.patient_id=? ORDER BY c.updated_at DESC""",
        (patient_id,),
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
    escalation = (
        "critical" if score >= settings.warning_critical_threshold
        else "urgent" if score >= settings.warning_escalation_threshold
        else "review" if score >= settings.warning_review_threshold
        else "routine"
    )
    recorded_at = now()
    with db.connect() as conn:
        conn.execute(
            """INSERT INTO observations
            (id,tenant_id,ward_id,patient_id,recorded_by,recorded_at,source,units_json,
             warning_profile_version,respiratory_rate,oxygen_saturation,supplemental_oxygen,
             systolic_bp,pulse,temperature,consciousness,score,escalation_level)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (observation_id,user.tenant_id,patient["ward_id"],patient_id,user.id,recorded_at,body.source,
             json.dumps(OBSERVATION_UNITS),settings.warning_profile_version,
             body.respiratory_rate,body.oxygen_saturation,int(body.supplemental_oxygen),body.systolic_bp,
             body.pulse,body.temperature,body.consciousness,score,escalation),
        )
        escalation_task = None
        if score >= settings.warning_escalation_threshold:
            escalation_task = new_id("task")
            conn.execute(
                """INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (escalation_task,user.tenant_id,patient["ward_id"],patient_id,
                 f"{escalation.title()} deterioration review",f"Warning score {score}; assess and escalate per local policy",
                  "stat" if score >= settings.warning_critical_threshold else "high","open",
                  (datetime.now(UTC)+timedelta(minutes=settings.escalation_due_minutes)).isoformat(),
                 patient["accountable_nurse_id"],user.id,recorded_at,None,None,None,1),
            )
        db.audit(conn,event_id=new_id("audit"),tenant_id=user.tenant_id,actor_id=user.id,
                 action="observation.recorded",resource_type="Observation",resource_id=observation_id,
                 patient_id=patient_id,details={"score":score,"escalation":escalation,"task_id":escalation_task,
                 "warning_profile":settings.warning_profile_version,"units":OBSERVATION_UNITS})
    return {"id": observation_id, "score": score, "escalation_level": escalation,
            "escalation_task_id": escalation_task, "warning_profile": settings.warning_profile_version,
            "units": OBSERVATION_UNITS}


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
        f"""SELECT t.*,p.name AS patient_name,p.bed,creator.name AS created_by_name,
        assignee.name AS assigned_to_name FROM tasks t JOIN patients p ON p.id=t.patient_id
        JOIN users creator ON creator.id=t.created_by
        LEFT JOIN users assignee ON assignee.id=t.assigned_to
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
        changed = conn.execute(
            """UPDATE tasks SET status=?,assigned_to=?,completed_by=?,completed_at=?,completion_note=?,version=version+1
            WHERE id=? AND version=? AND status=?""",
            (target,assigned_to,completed_by,completed_at,body.note or None,task_id,body.version,required),
        )
        if changed.rowcount != 1:
            raise HTTPException(status_code=409, detail="Task changed; refresh before updating")
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
        decode(row, "unresolved_tasks_json", "current_risks_json")
    return rows


@app.post("/api/patients/{patient_id}/handovers", status_code=201)
def create_handover(patient_id: str, body: HandoverCreate, user: UserDep) -> dict:
    require_roles(user, "registered_nurse", "nurse_in_charge")
    patient = scoped_patient(patient_id, user)
    receiver = db.fetchone("SELECT * FROM users WHERE id=? AND active=1", (body.receiver_id,))
    if not receiver or receiver["tenant_id"] != user.tenant_id or receiver["ward_id"] != patient["ward_id"] or receiver["id"] == user.id:
        raise HTTPException(status_code=422, detail="Receiver must be a different active nurse in this ward")
    unresolved = db.fetchall("SELECT id,title,priority,due_at,status FROM tasks WHERE patient_id=? AND status IN ('open','accepted')", (patient_id,))
    latest_observation = db.fetchone(
        "SELECT score,escalation_level,recorded_at FROM observations WHERE patient_id=? ORDER BY recorded_at DESC LIMIT 1",
        (patient_id,),
    )
    active_assessments = db.fetchall(
        """SELECT assessment_type,risk_level,findings,assessed_at FROM safety_assessments
        WHERE patient_id=? AND risk_level IN ('high','critical') ORDER BY assessed_at DESC""",
        (patient_id,),
    )
    current_risks = {
        "flags": json.loads(patient["flags_json"]),
        "allergies": json.loads(patient["allergies_json"]),
        "isolation_status": patient["isolation_status"],
        "code_status": patient["code_status"],
        "latest_observation": latest_observation,
        "high_risk_assessments": active_assessments,
        "captured_at": now(),
    }
    handover_id = new_id("handover")
    with db.connect() as conn:
        conn.execute(
            """INSERT INTO handovers
            (id,tenant_id,ward_id,patient_id,sender_id,receiver_id,created_at,accepted_at,
             situation,background,assessment,recommendation,unresolved_tasks_json,current_risks_json,status,version)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (handover_id,user.tenant_id,patient["ward_id"],patient_id,user.id,body.receiver_id,now(),None,
             body.situation,body.background,body.assessment,body.recommendation,json.dumps(unresolved),
             json.dumps(current_risks),"pending",1),
        )
        db.audit(conn,event_id=new_id("audit"),tenant_id=user.tenant_id,actor_id=user.id,
                 action="handover.created",resource_type="Communication",resource_id=handover_id,
                  patient_id=patient_id,details={"receiver_id":body.receiver_id,
                  "unresolved_task_count":len(unresolved),"risk_snapshot":current_risks})
    return {"id": handover_id, "status": "pending", "unresolved_tasks": unresolved,
            "current_risks": current_risks, "version": 1}


class HandoverAccept(BaseModel):
    version: int = Field(ge=1)


@app.post("/api/handovers/{handover_id}/accept")
def accept_handover(handover_id: str, body: HandoverAccept, user: UserDep) -> dict:
    handover = db.fetchone("SELECT * FROM handovers WHERE id=? AND tenant_id=?", (handover_id, user.tenant_id))
    if not handover:
        raise HTTPException(status_code=404, detail="Handover not found")
    if handover["receiver_id"] != user.id:
        raise HTTPException(status_code=403, detail="Only the named receiver may accept")
    if handover["status"] != "pending":
        raise HTTPException(status_code=409, detail="Handover is not pending")
    if body.version != handover["version"]:
        raise HTTPException(status_code=409, detail="Handover changed; refresh before accepting")
    accepted_at = now()
    with db.connect() as conn:
        changed = conn.execute(
            """UPDATE handovers SET status='accepted',accepted_at=?,version=version+1
            WHERE id=? AND status='pending' AND version=?""",
            (accepted_at,handover_id,body.version),
        )
        if changed.rowcount != 1:
            raise HTTPException(status_code=409, detail="Handover changed; refresh before accepting")
        conn.execute("UPDATE patients SET accountable_nurse_id=?,version=version+1 WHERE id=?", (user.id,handover["patient_id"]))
        db.audit(conn,event_id=new_id("audit"),tenant_id=user.tenant_id,actor_id=user.id,
                 action="handover.accepted",resource_type="Communication",resource_id=handover_id,
                 patient_id=handover["patient_id"],details={"accountability_transferred":True})
    return {"id": handover_id, "status": "accepted", "accepted_at": accepted_at,
            "version": handover["version"] + 1}


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
    if plan["status"] != "active":
        raise HTTPException(status_code=409, detail="Only an active care plan may be evaluated")
    with db.connect() as conn:
        changed = conn.execute(
            """UPDATE care_plans SET status=?,evaluation=?,updated_at=?,version=version+1
            WHERE id=? AND version=? AND status='active'""",
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

    from .port_registry import resolve_backend_port

    uvicorn.run(
        "nursing_station.main:app",
        host="127.0.0.1",
        port=resolve_backend_port(),
        reload=False,
    )


if __name__ == "__main__":
    run()
