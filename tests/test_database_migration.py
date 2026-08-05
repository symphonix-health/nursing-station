"""Upgrade path from a pre-national-capability database.

Every other test in this repository starts from an empty file, so the whole
suite exercises the CREATE-from-scratch path and none of it exercises the
upgrade path a deployed ward would actually take. That blind spot hid a real
defect: an index in ``SCHEMA`` named a column that ``_migrate`` had not added
yet, and because ``CREATE TABLE IF NOT EXISTS`` is a no-op against an existing
table, ``initialise()`` aborted with ``no such column: source_order_id`` on
every already-seeded database.

The legacy DDL below is the pre-wave shape of the tables that gained columns.
It is deliberately written out rather than derived from the current schema, so
this test keeps describing the shape that exists in the field.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

import pytest
from nursing_station.database import Database

LEGACY_SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE wards (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, facility_id TEXT NOT NULL,
 code TEXT NOT NULL, name TEXT NOT NULL, specialty TEXT NOT NULL,
 UNIQUE(tenant_id, facility_id, code)
);
CREATE TABLE users (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
 name TEXT NOT NULL, role TEXT NOT NULL, ward_id TEXT, password_hash BLOB NOT NULL,
 active INTEGER NOT NULL DEFAULT 1, FOREIGN KEY(ward_id) REFERENCES wards(id)
);
CREATE TABLE patients (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, ward_id TEXT NOT NULL,
 mrn TEXT NOT NULL, national_id_last4 TEXT NOT NULL, name TEXT NOT NULL,
 date_of_birth TEXT NOT NULL, sex TEXT NOT NULL, bed TEXT NOT NULL,
 admission_reason TEXT NOT NULL, admitted_at TEXT NOT NULL,
 allergies_json TEXT NOT NULL, code_status TEXT NOT NULL,
 isolation_status TEXT NOT NULL, flags_json TEXT NOT NULL,
 photo_status TEXT NOT NULL DEFAULT 'unavailable', accountable_nurse_id TEXT,
 version INTEGER NOT NULL DEFAULT 1, data_class TEXT NOT NULL DEFAULT 'seeded_synthetic',
 seed_manifest_id TEXT NOT NULL DEFAULT 'seed.uk.nursing_station.phase2_v1',
 external_nhs_number TEXT, source_patient_id TEXT,
 UNIQUE(tenant_id, mrn), FOREIGN KEY(ward_id) REFERENCES wards(id)
);
CREATE TABLE observations (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, ward_id TEXT NOT NULL, patient_id TEXT NOT NULL,
 recorded_by TEXT NOT NULL, recorded_at TEXT NOT NULL, source TEXT NOT NULL,
 units_json TEXT NOT NULL, warning_profile_version TEXT NOT NULL,
 respiratory_rate REAL NOT NULL, oxygen_saturation REAL NOT NULL,
 supplemental_oxygen INTEGER NOT NULL, systolic_bp REAL NOT NULL,
 pulse REAL NOT NULL, temperature REAL NOT NULL, consciousness TEXT NOT NULL,
 score INTEGER NOT NULL, escalation_level TEXT NOT NULL
);
CREATE TABLE tasks (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, ward_id TEXT NOT NULL, patient_id TEXT NOT NULL,
 title TEXT NOT NULL, description TEXT NOT NULL, priority TEXT NOT NULL,
 status TEXT NOT NULL, due_at TEXT NOT NULL, assigned_to TEXT,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, completed_by TEXT,
 completed_at TEXT, completion_note TEXT, version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE medication_orders (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, ward_id TEXT NOT NULL, patient_id TEXT NOT NULL,
 medication_name TEXT NOT NULL, dose_value REAL NOT NULL, dose_unit TEXT NOT NULL,
 route TEXT NOT NULL, schedule TEXT NOT NULL, due_at TEXT NOT NULL,
 high_alert INTEGER NOT NULL, status TEXT NOT NULL, source TEXT NOT NULL
);
CREATE TABLE medication_administrations (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, ward_id TEXT NOT NULL, patient_id TEXT NOT NULL,
 order_id TEXT NOT NULL, outcome TEXT NOT NULL, reason TEXT,
 administered_by TEXT NOT NULL, cosigned_by TEXT, administered_at TEXT NOT NULL,
 mrn_verified TEXT NOT NULL, dob_verified TEXT NOT NULL
);
"""

NEW_TABLES = (
    "nurse_competencies", "task_interruptions", "escalation_responses",
    "outbound_publications", "staffing_snapshots", "staffing_declarations",
    "harm_incidents", "incident_reviews", "discharge_readiness",
    "discharge_criteria", "quality_measure_results", "country_pack_adoptions",
)
NEW_COLUMNS = {
    "patients": ("oxygen_target_scale", "acuity_dependency"),
    "tasks": ("required_competency", "origin_kind", "origin_id"),
    "medication_orders": ("source_system", "source_order_id"),
    "medication_administrations": ("publication_id",),
    "observations": ("oxygen_scale", "jurisdiction", "pack_version", "response_due_at"),
}


@pytest.fixture()
def legacy_db(tmp_path):
    path = tmp_path / "legacy.db"
    now = datetime.now(UTC).isoformat()
    with sqlite3.connect(path) as conn:
        conn.executescript(LEGACY_SCHEMA)
        conn.execute(
            "INSERT INTO wards VALUES ('ward-med-a','tenant-st-brigids','facility-st-brigids',"
            "'MED-A','Medical Ward A','adult-medical')"
        )
        conn.execute(
            "INSERT INTO users VALUES ('usr-amina','tenant-st-brigids','amina.okafor@nursing.test',"
            "'Amina Okafor','registered_nurse','ward-med-a',X'00',1)"
        )
        conn.execute(
            "INSERT INTO patients (id,tenant_id,ward_id,mrn,national_id_last4,name,date_of_birth,"
            "sex,bed,admission_reason,admitted_at,allergies_json,code_status,isolation_status,"
            "flags_json,accountable_nurse_id) VALUES ('pat-legacy','tenant-st-brigids','ward-med-a',"
            "'MRN-LEGACY','0001','Legacy Patient','1950-01-01','female','A-01','Pre-upgrade admission',"
            f"'{now}','[]','Full escalation','None','[]','usr-amina')"
        )
        conn.execute(
            "INSERT INTO medication_orders VALUES ('med-legacy','tenant-st-brigids','ward-med-a',"
            f"'pat-legacy','Amoxicillin',500,'mg','oral','three times daily','{now}',0,'active',"
            "'pre-upgrade order')"
        )
        conn.execute(
            "INSERT INTO tasks VALUES ('task-legacy','tenant-st-brigids','ward-med-a','pat-legacy',"
            f"'Pre-upgrade task','Carried across the upgrade','normal','open','{now}','usr-amina',"
            f"'usr-amina','{now}',NULL,NULL,NULL,1)"
        )
    return path


def _columns(path, table: str) -> set[str]:
    with sqlite3.connect(path) as conn:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _tables(path) -> set[str]:
    with sqlite3.connect(path) as conn:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_an_existing_database_upgrades_without_losing_clinical_records(legacy_db):
    for table, columns in NEW_COLUMNS.items():
        assert not (_columns(legacy_db, table) & set(columns)), "fixture is not a legacy database"

    Database(legacy_db).initialise()

    for table, columns in NEW_COLUMNS.items():
        present = _columns(legacy_db, table)
        missing = sorted(set(columns) - present)
        assert not missing, f"{table} did not gain {missing}"
    assert not sorted(set(NEW_TABLES) - _tables(legacy_db))

    with sqlite3.connect(legacy_db) as conn:
        conn.row_factory = sqlite3.Row
        patient = conn.execute("SELECT * FROM patients WHERE id='pat-legacy'").fetchone()
        assert patient["name"] == "Legacy Patient"
        # New columns take their declared defaults on pre-existing rows.
        assert patient["oxygen_target_scale"] == "1"
        assert patient["acuity_dependency"] == "level-1"
        order = conn.execute("SELECT * FROM medication_orders WHERE id='med-legacy'").fetchone()
        assert order["source_system"] == "nursing-station"
        assert order["source_order_id"] is None
        task = conn.execute("SELECT * FROM tasks WHERE id='task-legacy'").fetchone()
        assert task["required_competency"] is None
        assert task["status"] == "open"


def test_the_upgrade_creates_the_source_reference_index_after_its_column(legacy_db):
    Database(legacy_db).initialise()
    with sqlite3.connect(legacy_db) as conn:
        indexes = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='medication_orders'"
            )
        }
    assert "one_order_per_source_reference" in indexes


def test_the_upgrade_is_repeatable(legacy_db):
    db = Database(legacy_db)
    db.initialise()
    first = db.fetchall("SELECT id FROM patients ORDER BY id")
    db.initialise()
    db.initialise()
    assert db.fetchall("SELECT id FROM patients ORDER BY id") == first
    assert db.fetchone("SELECT COUNT(*) c FROM seed_runs")["c"] == 1


def test_a_new_database_gets_the_same_shape_as_an_upgraded_one(tmp_path, legacy_db):
    fresh = tmp_path / "fresh.db"
    Database(fresh).initialise()
    Database(legacy_db).initialise()
    for table in (*NEW_TABLES, *NEW_COLUMNS):
        assert _columns(fresh, table) == _columns(legacy_db, table), (
            f"{table} differs between a created and an upgraded database"
        )
    assert json.dumps(sorted(_tables(fresh))) == json.dumps(sorted(_tables(legacy_db)))
