from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import bcrypt

from .synthetic_seed import DATA_CLASS, SEED_MANIFEST_ID, manifest

SEED_PASSWORD_HASH = bcrypt.hashpw(b"Nursing2026!", bcrypt.gensalt(rounds=12))

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS wards (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, facility_id TEXT NOT NULL,
 code TEXT NOT NULL, name TEXT NOT NULL, specialty TEXT NOT NULL,
 UNIQUE(tenant_id, facility_id, code)
);
CREATE TABLE IF NOT EXISTS users (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
 name TEXT NOT NULL, role TEXT NOT NULL, ward_id TEXT, password_hash BLOB NOT NULL,
 active INTEGER NOT NULL DEFAULT 1, FOREIGN KEY(ward_id) REFERENCES wards(id)
);
CREATE TABLE IF NOT EXISTS patients (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, ward_id TEXT NOT NULL,
 mrn TEXT NOT NULL, national_id_last4 TEXT NOT NULL, name TEXT NOT NULL,
 date_of_birth TEXT NOT NULL, sex TEXT NOT NULL, bed TEXT NOT NULL,
 admission_reason TEXT NOT NULL, admitted_at TEXT NOT NULL,
 allergies_json TEXT NOT NULL, code_status TEXT NOT NULL,
 isolation_status TEXT NOT NULL, flags_json TEXT NOT NULL,
 photo_status TEXT NOT NULL DEFAULT 'unavailable', accountable_nurse_id TEXT,
 version INTEGER NOT NULL DEFAULT 1, data_class TEXT NOT NULL DEFAULT 'seeded_synthetic',
 seed_manifest_id TEXT NOT NULL DEFAULT 'seed.uk.nursing_station.phase1_v1',
 UNIQUE(tenant_id, mrn), FOREIGN KEY(ward_id) REFERENCES wards(id),
 FOREIGN KEY(accountable_nurse_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS observations (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, ward_id TEXT NOT NULL, patient_id TEXT NOT NULL,
 recorded_by TEXT NOT NULL, recorded_at TEXT NOT NULL, source TEXT NOT NULL,
 units_json TEXT NOT NULL, warning_profile_version TEXT NOT NULL,
 respiratory_rate REAL NOT NULL, oxygen_saturation REAL NOT NULL,
 supplemental_oxygen INTEGER NOT NULL, systolic_bp REAL NOT NULL,
 pulse REAL NOT NULL, temperature REAL NOT NULL, consciousness TEXT NOT NULL,
 score INTEGER NOT NULL, escalation_level TEXT NOT NULL,
 FOREIGN KEY(patient_id) REFERENCES patients(id), FOREIGN KEY(recorded_by) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS tasks (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, ward_id TEXT NOT NULL, patient_id TEXT NOT NULL,
 title TEXT NOT NULL, description TEXT NOT NULL, priority TEXT NOT NULL,
 status TEXT NOT NULL, due_at TEXT NOT NULL, assigned_to TEXT,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, completed_by TEXT,
 completed_at TEXT, completion_note TEXT, version INTEGER NOT NULL DEFAULT 1,
 FOREIGN KEY(patient_id) REFERENCES patients(id), FOREIGN KEY(assigned_to) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS handovers (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, ward_id TEXT NOT NULL, patient_id TEXT NOT NULL,
 sender_id TEXT NOT NULL, receiver_id TEXT NOT NULL, created_at TEXT NOT NULL,
 accepted_at TEXT, situation TEXT NOT NULL, background TEXT NOT NULL,
 assessment TEXT NOT NULL, recommendation TEXT NOT NULL,
 unresolved_tasks_json TEXT NOT NULL, current_risks_json TEXT NOT NULL, status TEXT NOT NULL,
 version INTEGER NOT NULL DEFAULT 1,
 FOREIGN KEY(patient_id) REFERENCES patients(id)
);
CREATE TABLE IF NOT EXISTS medication_orders (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, ward_id TEXT NOT NULL, patient_id TEXT NOT NULL,
 medication_name TEXT NOT NULL, dose_value REAL NOT NULL, dose_unit TEXT NOT NULL,
 route TEXT NOT NULL, schedule TEXT NOT NULL, due_at TEXT NOT NULL,
 high_alert INTEGER NOT NULL, status TEXT NOT NULL, source TEXT NOT NULL,
 FOREIGN KEY(patient_id) REFERENCES patients(id)
);
CREATE TABLE IF NOT EXISTS medication_administrations (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, ward_id TEXT NOT NULL, patient_id TEXT NOT NULL,
 order_id TEXT NOT NULL, outcome TEXT NOT NULL, reason TEXT,
 administered_by TEXT NOT NULL, cosigned_by TEXT, administered_at TEXT NOT NULL,
 mrn_verified TEXT NOT NULL, dob_verified TEXT NOT NULL,
 FOREIGN KEY(order_id) REFERENCES medication_orders(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_terminal_administration_per_order
 ON medication_administrations(order_id) WHERE outcome <> 'delayed';
CREATE TABLE IF NOT EXISTS safety_assessments (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, ward_id TEXT NOT NULL, patient_id TEXT NOT NULL,
 assessment_type TEXT NOT NULL, risk_level TEXT NOT NULL, score REAL,
 findings TEXT NOT NULL, actions_json TEXT NOT NULL, assessed_by TEXT NOT NULL,
 assessed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS care_plans (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, ward_id TEXT NOT NULL, patient_id TEXT NOT NULL,
 problem TEXT NOT NULL, goal TEXT NOT NULL, interventions_json TEXT NOT NULL,
 status TEXT NOT NULL, owner_id TEXT NOT NULL, created_by TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, evaluation TEXT,
 version INTEGER NOT NULL DEFAULT 1,
 FOREIGN KEY(patient_id) REFERENCES patients(id), FOREIGN KEY(owner_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS audit_events (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
 occurred_at TEXT NOT NULL, tenant_id TEXT NOT NULL, actor_id TEXT NOT NULL,
 action TEXT NOT NULL, resource_type TEXT NOT NULL, resource_id TEXT NOT NULL,
 patient_id TEXT, details_json TEXT NOT NULL, previous_hash TEXT NOT NULL,
 event_hash TEXT UNIQUE NOT NULL
);
CREATE TABLE IF NOT EXISTS seed_runs (
 id TEXT PRIMARY KEY, seed_manifest_id TEXT UNIQUE NOT NULL,
 seeder_name TEXT NOT NULL, metadata_pack_id TEXT NOT NULL,
 generated_at TEXT NOT NULL, data_class TEXT NOT NULL,
 record_counts_json TEXT NOT NULL, declaration_json TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_events
BEGIN SELECT RAISE(ABORT, 'audit events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_events
BEGIN SELECT RAISE(ABORT, 'audit events are append-only'); END;
"""


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=20)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialise(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            self._migrate(conn)
            if not conn.execute("SELECT 1 FROM wards LIMIT 1").fetchone():
                self._seed(conn)
            elif not conn.execute("SELECT 1 FROM seed_runs LIMIT 1").fetchone():
                self._record_seed_run(conn, self._now())

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        observation_columns = {row[1] for row in conn.execute("PRAGMA table_info(observations)")}
        if "units_json" not in observation_columns:
            conn.execute("ALTER TABLE observations ADD COLUMN units_json TEXT NOT NULL DEFAULT '{}' ")
        if "warning_profile_version" not in observation_columns:
            conn.execute("ALTER TABLE observations ADD COLUMN warning_profile_version TEXT NOT NULL DEFAULT 'legacy' ")
        handover_columns = {row[1] for row in conn.execute("PRAGMA table_info(handovers)")}
        if "current_risks_json" not in handover_columns:
            conn.execute("ALTER TABLE handovers ADD COLUMN current_risks_json TEXT NOT NULL DEFAULT '[]' ")
        if "version" not in handover_columns:
            conn.execute("ALTER TABLE handovers ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
        patient_columns = {row[1] for row in conn.execute("PRAGMA table_info(patients)")}
        if "data_class" not in patient_columns:
            conn.execute(
                "ALTER TABLE patients ADD COLUMN data_class TEXT NOT NULL "
                "DEFAULT 'seeded_synthetic'"
            )
        if "seed_manifest_id" not in patient_columns:
            conn.execute(
                "ALTER TABLE patients ADD COLUMN seed_manifest_id TEXT NOT NULL "
                "DEFAULT 'seed.uk.nursing_station.phase1_v1'"
            )

    def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with self.connect() as conn:
            conn.execute(sql, params)

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def audit(
        self,
        conn: sqlite3.Connection,
        *,
        event_id: str,
        tenant_id: str,
        actor_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        patient_id: str | None,
        details: dict[str, Any],
    ) -> None:
        previous = conn.execute(
            "SELECT event_hash FROM audit_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous_hash = previous[0] if previous else "GENESIS"
        content = {
            "id": event_id,
            "occurred_at": self._now(),
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "patient_id": patient_id,
            "details": details,
            "previous_hash": previous_hash,
        }
        event_hash = hashlib.sha256(
            json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        conn.execute(
            """INSERT INTO audit_events
            (id,occurred_at,tenant_id,actor_id,action,resource_type,resource_id,patient_id,
             details_json,previous_hash,event_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                content["id"], content["occurred_at"], tenant_id, actor_id, action,
                resource_type, resource_id, patient_id, json.dumps(details, sort_keys=True),
                previous_hash, event_hash,
            ),
        )

    def verify_audit(self) -> tuple[bool, int]:
        events = self.fetchall("SELECT * FROM audit_events ORDER BY sequence")
        previous = "GENESIS"
        for event in events:
            details = json.loads(event["details_json"])
            content = {
                "id": event["id"], "occurred_at": event["occurred_at"],
                "tenant_id": event["tenant_id"], "actor_id": event["actor_id"],
                "action": event["action"], "resource_type": event["resource_type"],
                "resource_id": event["resource_id"], "patient_id": event["patient_id"],
                "details": details, "previous_hash": previous,
            }
            expected = hashlib.sha256(
                json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            if event["previous_hash"] != previous or event["event_hash"] != expected:
                return False, len(events)
            previous = event["event_hash"]
        return True, len(events)

    def _seed(self, conn: sqlite3.Connection) -> None:
        tenant = "tenant-st-brigids"
        wards = [
            ("ward-med-a", tenant, "facility-st-brigids", "MED-A", "Medical Ward A", "adult-medical"),
            ("ward-surg-b", tenant, "facility-st-brigids", "SURG-B", "Surgical Ward B", "adult-surgical"),
        ]
        conn.executemany("INSERT INTO wards VALUES (?,?,?,?,?,?)", wards)
        password = SEED_PASSWORD_HASH
        users = [
            ("usr-amina", tenant, "amina.okafor@nursing.test", "Amina Okafor", "registered_nurse", "ward-med-a", password, 1),
            ("usr-grace", tenant, "grace.mensah@nursing.test", "Grace Mensah", "nurse_in_charge", "ward-med-a", password, 1),
            ("usr-samuel", tenant, "samuel.osei@nursing.test", "Samuel Osei", "registered_nurse", "ward-surg-b", password, 1),
            ("usr-cso", tenant, "clinical.safety@nursing.test", "Clinical Safety Officer", "clinical_safety_officer", None, password, 1),
        ]
        conn.executemany("INSERT INTO users VALUES (?,?,?,?,?,?,?,?)", users)
        now = datetime.now(UTC)
        patients = [
            ("pat-001", tenant, "ward-med-a", "MRN-104287", "4812", "Margaret Holloway", "1957-09-14", "female", "A-12", "Pneumonia with hypoxia", (now-timedelta(days=3)).isoformat(), json.dumps([{"substance":"Penicillin","reaction":"Anaphylaxis","severity":"severe"}]), "Full escalation", "Droplet", json.dumps(["Falls risk","Oxygen therapy"]), "unavailable", "usr-amina", 1),
            ("pat-002", tenant, "ward-med-a", "MRN-104311", "2059", "Kwame Boateng", "1968-02-03", "male", "A-14", "Decompensated heart failure", (now-timedelta(days=2)).isoformat(), json.dumps([]), "Full escalation", "None", json.dumps(["Fluid restriction"]), "unavailable", "usr-grace", 1),
            ("pat-003", tenant, "ward-med-a", "MRN-104329", "7740", "Nkiru Adeyemi", "1981-11-22", "female", "A-16", "Diabetic foot infection", (now-timedelta(days=1)).isoformat(), json.dumps([{"substance":"Latex","reaction":"Contact dermatitis","severity":"moderate"}]), "Full escalation", "Contact", json.dumps(["High-alert medication","Pressure injury risk"]), "unavailable", "usr-amina", 1),
            ("pat-004", tenant, "ward-surg-b", "MRN-104350", "9014", "Liam O'Connor", "1974-06-18", "male", "B-03", "Post-operative bowel resection", (now-timedelta(hours=18)).isoformat(), json.dumps([]), "Full escalation", "None", json.dumps(["Falls risk"]), "unavailable", "usr-samuel", 1),
        ]
        patients = [row + (DATA_CLASS, SEED_MANIFEST_ID) for row in patients]
        conn.executemany(
            "INSERT INTO patients VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            patients,
        )
        tasks = [
            ("task-001",tenant,"ward-med-a","pat-001","Repeat observations","NEWS2 reassessment after oxygen titration","stat","open",(now-timedelta(minutes=12)).isoformat(),"usr-amina","usr-grace",now.isoformat(),None,None,None,1),
            ("task-002",tenant,"ward-med-a","pat-002","Daily weight","Record weight before breakfast","normal","open",(now+timedelta(minutes=35)).isoformat(),"usr-grace","usr-grace",now.isoformat(),None,None,None,1),
            ("task-003",tenant,"ward-med-a","pat-003","Pressure-area care","Reposition and inspect heels","high","open",(now+timedelta(minutes=10)).isoformat(),"usr-amina","usr-grace",now.isoformat(),None,None,None,1),
        ]
        conn.executemany("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", tasks)
        meds = [
            ("med-001",tenant,"ward-med-a","pat-001","Ceftriaxone",2,"g","IV","once daily",(now+timedelta(minutes=20)).isoformat(),0,"active","Phase 1 seeded order"),
            ("med-002",tenant,"ward-med-a","pat-003","Insulin aspart",4,"units","subcutaneous","with meals",(now+timedelta(minutes=5)).isoformat(),1,"active","Phase 1 seeded order"),
            ("med-003",tenant,"ward-med-a","pat-002","Furosemide",40,"mg","oral","twice daily",(now-timedelta(minutes=25)).isoformat(),0,"active","Phase 1 seeded order"),
        ]
        conn.executemany("INSERT INTO medication_orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", meds)
        observations = [
            ("obs-seed-001",tenant,"ward-med-a","pat-001","usr-amina",(now-timedelta(minutes=18)).isoformat(),"seeded bedside observation",json.dumps({"respiratory_rate":"/min","oxygen_saturation":"%","systolic_bp":"mmHg","pulse":"/min","temperature":"Cel"}),"NS-NEWS2-PHASE1-v1",22,94,1,112,96,38.2,"alert",5,"urgent"),
            ("obs-seed-002",tenant,"ward-med-a","pat-002","usr-grace",(now-timedelta(minutes=42)).isoformat(),"seeded bedside observation",json.dumps({"respiratory_rate":"/min","oxygen_saturation":"%","systolic_bp":"mmHg","pulse":"/min","temperature":"Cel"}),"NS-NEWS2-PHASE1-v1",18,97,0,118,84,36.7,"alert",0,"routine"),
            ("obs-seed-003",tenant,"ward-med-a","pat-003","usr-amina",(now-timedelta(minutes=25)).isoformat(),"seeded bedside observation",json.dumps({"respiratory_rate":"/min","oxygen_saturation":"%","systolic_bp":"mmHg","pulse":"/min","temperature":"Cel"}),"NS-NEWS2-PHASE1-v1",19,98,0,126,88,37.1,"alert",0,"routine"),
        ]
        conn.executemany("INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", observations)
        care_plans = [
            ("care-001",tenant,"ward-med-a","pat-001","Impaired gas exchange","Maintain oxygen saturation within prescribed target and reduce work of breathing",json.dumps(["Monitor respiratory observations at prescribed frequency","Position upright and support prescribed oxygen therapy"]),"active","usr-amina","usr-grace",now.isoformat(),now.isoformat(),None,1),
            ("care-002",tenant,"ward-med-a","pat-003","Risk of pressure injury","Skin remains intact during admission",json.dumps(["Reposition to assessed schedule","Inspect pressure areas each shift"]),"active","usr-amina","usr-grace",now.isoformat(),now.isoformat(),None,1),
        ]
        conn.executemany("INSERT INTO care_plans VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", care_plans)
        self._record_seed_run(conn, now.isoformat())

    @staticmethod
    def _record_seed_run(conn: sqlite3.Connection, generated_at: str) -> None:
        tables = (
            "wards",
            "users",
            "patients",
            "tasks",
            "medication_orders",
            "observations",
            "care_plans",
        )
        counts = {
            table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in tables
        }
        declaration = manifest(counts, generated_at)
        conn.execute(
            """INSERT INTO seed_runs
            (id,seed_manifest_id,seeder_name,metadata_pack_id,generated_at,data_class,
             record_counts_json,declaration_json) VALUES (?,?,?,?,?,?,?,?)""",
            (
                "seed-run-phase1-v1",
                declaration["seed_manifest_id"],
                declaration["seeder_name"],
                declaration["metadata_pack_id"],
                declaration["generation_completed_at"],
                DATA_CLASS,
                json.dumps(counts, sort_keys=True),
                json.dumps(declaration, sort_keys=True),
            ),
        )
