from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from nursing_station import main
from nursing_station.database import Database

MATRIX = Path(__file__).parent / "json_matrices" / "nursing_station_phase2_canonical.json"
ALL_SCENARIOS = json.loads(MATRIX.read_text(encoding="utf-8"))["scenarios"]
SHARD_TOTAL = max(1, int(os.getenv("BT_MATRIX_APP_HARNESS_SHARD_TOTAL", "1")))
SHARD_INDEX = int(os.getenv("BT_MATRIX_APP_HARNESS_SHARD_INDEX", "0"))
SCENARIOS = [row for index, row in enumerate(ALL_SCENARIOS) if index % SHARD_TOTAL == SHARD_INDEX]
TOKENS: dict[str, str] = {}


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    main.db = Database(tmp_path_factory.mktemp("matrix-harness") / "test.db")
    with TestClient(main.app) as test_client:
        yield test_client


def _login(client, email: str = "amina.okafor@nursing.test") -> dict[str, str]:
    if email in TOKENS:
        return {"Authorization": f"Bearer {TOKENS[email]}"}
    response = client.post(
        "/api/auth/login", json={"email": email, "password": "Nursing2026!"}
    )
    assert response.status_code == 200
    TOKENS[email] = response.json()["access_token"]
    return {"Authorization": f"Bearer {TOKENS[email]}"}


def _request(client, domain: str, headers: dict[str, str], category: str):
    unauthenticated = category == "negative"
    active_headers = {} if unauthenticated else headers
    edge = category == "edge"
    if domain == "ward-board":
        suffix = "?ward_id=ward-surg-b" if edge else ""
        return client.get(f"/api/ward-board{suffix}", headers=active_headers)
    if domain == "observations":
        payload = {
            "respiratory_rate": 0 if edge else 18,
            "oxygen_saturation": 98,
            "supplemental_oxygen": False,
            "systolic_bp": 122,
            "pulse": 78,
            "temperature": 36.8,
            "consciousness": "alert",
            "source": "CAID matrix harness",
        }
        return client.post("/api/patients/pat-001/observations", headers=active_headers, json=payload)
    if domain == "tasks":
        if not unauthenticated and not edge:
            main.db.execute("UPDATE tasks SET status='open',version=1 WHERE id='task-001'")
        payload = {"action": "invalid" if edge else "accept", "version": 1, "note": ""}
        return client.post("/api/tasks/task-001/transition", headers=active_headers, json=payload)
    if domain == "care-plans":
        payload = {
            "problem": "Impaired comfort",
            "goal": "Comfort improves during the shift",
            "interventions": [] if edge else ["Reassess comfort after intervention"],
            "owner_id": "usr-amina",
        }
        return client.post("/api/patients/pat-001/care-plans", headers=active_headers, json=payload)
    if domain == "handover":
        payload = {
            "receiver_id": "usr-amina" if edge else "usr-grace",
            "situation": "Current nursing priorities require review",
            "background": "Admitted with pneumonia",
            "assessment": "Repeat observations remain due",
            "recommendation": "Review observations and outstanding actions",
        }
        return client.post("/api/patients/pat-001/handovers", headers=active_headers, json=payload)
    if domain == "medications":
        if not unauthenticated and not edge:
            main.db.execute("DELETE FROM medication_administrations WHERE order_id='med-002'")
            main.db.execute("UPDATE medication_orders SET status='active' WHERE id='med-002'")
        payload = {
            "outcome": "administered",
            "reason": None,
            "mrn_verified": "wrong" if edge else "MRN-104329",
            "date_of_birth_verified": "1981-11-22",
            "cosigner_id": "usr-grace",
        }
        return client.post("/api/medication-orders/med-002/administrations", headers=active_headers, json=payload)
    if domain == "safety":
        payload = {
            "assessment_type": "falls",
            "risk_level": "high",
            "score": 12,
            "findings": "Requires supervised transfer",
            "actions": [] if edge else ["Supervise transfers"],
        }
        return client.post("/api/patients/pat-002/safety-assessments", headers=active_headers, json=payload)
    if domain == "audit":
        audit_headers = {} if unauthenticated else _login(client, "grace.mensah@nursing.test")
        if edge:
            audit_headers = headers
        return client.get("/api/audit", headers=audit_headers)
    if domain == "integrations":
        patient_id = "pat-004" if edge else "pat-005"
        return client.get(f"/api/patients/{patient_id}/integrations", headers=active_headers)
    if domain == "reporting":
        report_headers = {} if unauthenticated else _login(client, "grace.mensah@nursing.test")
        if edge:
            report_headers = headers
        return client.post("/api/wards/ward-med-a/hmis-measures", headers=report_headers)
    if domain == "alerts":
        if edge:
            return client.post("/api/alerts/missing/acknowledge", headers=headers)
        return client.get("/api/alerts", headers={} if unauthenticated else headers)
    if domain == "governance":
        return client.get("/api/governance/seed", headers=active_headers)
    raise AssertionError(f"Unhandled matrix domain: {domain}")


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda row: row["use_case_id"])
def test_matrix_scenario(client, scenario):
    headers = _login(client)
    category = scenario["scenario_category"].lower()
    domain = next(tag for tag in scenario["tags"] if tag in {
        "ward-board", "observations", "tasks", "care-plans", "handover",
        "medications", "safety", "audit", "integrations", "reporting", "alerts",
        "governance",
    })
    response = _request(client, domain, headers, category)
    expected = 503 if domain == "reporting" else 200 if domain in {"ward-board", "audit", "tasks", "integrations", "alerts", "governance"} else 201
    if category == "positive":
        assert response.status_code == expected
    elif category == "negative":
        assert response.status_code == 401
    else:
        assert response.status_code in {403, 404, 422}
