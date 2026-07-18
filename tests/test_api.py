from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest


def login(client, email: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": email, "password": "Nursing2026!"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_health_reports_durable_phase_boundary(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "nursing-station",
        "phase": 1,
        "database": "durable-sqlite",
        "audit_chain_valid": True,
        "audit_events": 0,
        "integrations": "not-implemented-phase-2",
        "warning_profile": "NS-NEWS2-PHASE1-v1",
        "synthetic_seed": {
            "seed_manifest_id": "seed.uk.nursing_station.phase1_v1",
            "data_class": "seeded_synthetic",
        },
    }


def test_seed_governance_is_durable_explicit_and_non_live(client, headers):
    response = client.get("/api/governance/seed", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["seed_manifest_id"] == "seed.uk.nursing_station.phase1_v1"
    assert body["record_counts"]["patients"] == 4
    assert body["record_counts"]["observations"] == 3
    declaration = body["declaration"]
    assert declaration["record_counts_landed"] == declaration["record_counts_expected"]
    assert declaration["contains_real_patient_data"] is False
    assert declaration["contains_real_person_data"] is False
    assert declaration["contains_pseudonymised_real_data"] is False
    assert declaration["source_is_live_clinical_system"] is False

    patient = client.get("/api/patients/pat-001", headers=headers).json()
    assert patient["data_class"] == "seeded_synthetic"
    assert patient["seed_manifest_id"] == body["seed_manifest_id"]


def test_authentication_rejects_wrong_password(client):
    response = client.post("/api/auth/login", json={"email": "amina.okafor@nursing.test", "password": "wrong"})
    assert response.status_code == 401


def test_ward_board_is_ward_scoped(client, headers):
    response = client.get("/api/ward-board", headers=headers)
    assert response.status_code == 200
    assert response.json()["ward"]["id"] == "ward-med-a"
    assert {patient["id"] for patient in response.json()["patients"]} == {"pat-001", "pat-002", "pat-003"}
    forbidden = client.get("/api/ward-board?ward_id=ward-surg-b", headers=headers)
    assert forbidden.status_code == 403


def test_patient_access_cannot_cross_ward(client, headers):
    assert client.get("/api/patients/pat-001", headers=headers).status_code == 200
    assert client.get("/api/patients/pat-004", headers=headers).status_code == 403


def test_observation_records_score_and_creates_escalation(client, headers):
    response = client.post(
        "/api/patients/pat-001/observations",
        headers=headers,
        json={
            "respiratory_rate": 28,
            "oxygen_saturation": 89,
            "supplemental_oxygen": True,
            "systolic_bp": 88,
            "pulse": 134,
            "temperature": 39.4,
            "consciousness": "new-confusion",
            "source": "manual bedside observation",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["score"] >= 7
    assert body["escalation_level"] == "critical"
    assert body["escalation_task_id"].startswith("task-")
    detail = client.get("/api/patients/pat-001", headers=headers).json()
    assert detail["observations"][0]["score"] == body["score"]
    assert detail["observations"][0]["units_json"]["temperature"] == "Cel"
    assert detail["observations"][0]["recorded_by_name"] == "Amina Okafor"
    assert detail["observations"][0]["warning_profile_version"] == "NS-NEWS2-PHASE1-v1"
    assert any(task["title"] == "Critical deterioration review" for task in detail["tasks"])


def test_observation_normal_values_score_zero(client, headers):
    response = client.post(
        "/api/patients/pat-002/observations",
        headers=headers,
        json={"respiratory_rate": 16, "oxygen_saturation": 98, "supplemental_oxygen": False,
              "systolic_bp": 122, "pulse": 78, "temperature": 36.8,
              "consciousness": "alert", "source": "manual bedside observation"},
    )
    assert response.status_code == 201
    assert response.json()["score"] == 0
    assert response.json()["escalation_level"] == "routine"


def test_observation_rejects_implausible_value(client, headers):
    response = client.post(
        "/api/patients/pat-001/observations",
        headers=headers,
        json={"respiratory_rate": 0, "oxygen_saturation": 110, "supplemental_oxygen": False,
              "systolic_bp": 10, "pulse": 500, "temperature": 20, "consciousness": "alert", "source": "manual"},
    )
    assert response.status_code == 422


def test_task_state_machine_and_stale_version(client, headers):
    created = client.post(
        "/api/patients/pat-001/tasks",
        headers=headers,
        json={"title": "Review fluid balance", "description": "Calculate six-hour total", "priority": "high",
              "due_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(), "assigned_to": "usr-amina"},
    )
    assert created.status_code == 201
    task_id = created.json()["id"]
    accepted = client.post(f"/api/tasks/{task_id}/transition", headers=headers, json={"action": "accept", "version": 1, "note": ""})
    assert accepted.status_code == 200
    stale = client.post(f"/api/tasks/{task_id}/transition", headers=headers, json={"action": "complete", "version": 1, "note": "done"})
    assert stale.status_code == 409
    completed = client.post(f"/api/tasks/{task_id}/transition", headers=headers, json={"action": "complete", "version": 2, "note": "Documented total"})
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"


def test_task_can_be_created_assigned_and_cancelled(client, headers):
    created = client.post(
        "/api/patients/pat-002/tasks",
        headers=headers,
        json={
            "title": "Review discharge teaching",
            "description": "Confirm understanding and document outstanding questions",
            "priority": "normal",
            "due_at": (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
            "assigned_to": "usr-grace",
        },
    )
    assert created.status_code == 201
    task_id = created.json()["id"]
    cancelled = client.post(
        f"/api/tasks/{task_id}/transition",
        headers=headers,
        json={"action": "cancel", "version": 1, "note": "Plan changed after review"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json() == {"id": task_id, "status": "cancelled", "version": 2}


def test_high_alert_medication_requires_independent_cosign(client, headers):
    missing = client.post(
        "/api/medication-orders/med-002/administrations", headers=headers,
        json={"outcome": "administered", "reason": None, "mrn_verified": "MRN-104329", "date_of_birth_verified": "1981-11-22", "cosigner_id": None},
    )
    assert missing.status_code == 422
    self_cosign = client.post(
        "/api/medication-orders/med-002/administrations", headers=headers,
        json={"outcome": "administered", "reason": None, "mrn_verified": "MRN-104329", "date_of_birth_verified": "1981-11-22", "cosigner_id": "usr-amina"},
    )
    assert self_cosign.status_code == 422
    confirmed = client.post(
        "/api/medication-orders/med-002/administrations", headers=headers,
        json={"outcome": "administered", "reason": None, "mrn_verified": "MRN-104329", "date_of_birth_verified": "1981-11-22", "cosigner_id": "usr-grace"},
    )
    assert confirmed.status_code == 201
    assert confirmed.json()["server_confirmed"] is True
    repeated = client.post(
        "/api/medication-orders/med-002/administrations", headers=headers,
        json={"outcome": "administered", "reason": None, "mrn_verified": "MRN-104329", "date_of_birth_verified": "1981-11-22", "cosigner_id": "usr-grace"},
    )
    assert repeated.status_code == 409
    detail = client.get("/api/patients/pat-003", headers=headers).json()
    assert all(order["id"] != "med-002" for order in detail["medications"])


def test_medication_rejects_wrong_patient_identifiers(client, headers):
    response = client.post(
        "/api/medication-orders/med-001/administrations", headers=headers,
        json={"outcome": "administered", "reason": None, "mrn_verified": "MRN-WRONG", "date_of_birth_verified": "1957-09-14", "cosigner_id": None},
    )
    assert response.status_code == 422
    detail = client.get("/api/patients/pat-001", headers=headers).json()
    assert any(order["id"] == "med-001" for order in detail["medications"])


def test_non_administered_medication_requires_reason(client, headers):
    response = client.post(
        "/api/medication-orders/med-001/administrations", headers=headers,
        json={"outcome": "withheld", "reason": None, "mrn_verified": "MRN-104287", "date_of_birth_verified": "1957-09-14", "cosigner_id": None},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("outcome", "reason"),
    [
        ("administered", None),
        ("withheld", "Clinical parameter outside prescribed range"),
        ("refused", "Patient declined after discussion"),
        ("delayed", "Awaiting scheduled review"),
        ("omitted", "Dose not available before occurrence closed"),
        ("partial", "Patient tolerated part of prescribed dose"),
    ],
)
def test_every_medication_outcome_is_recorded_exactly(client, headers, outcome, reason):
    response = client.post(
        "/api/medication-orders/med-001/administrations",
        headers=headers,
        json={
            "outcome": outcome,
            "reason": reason,
            "mrn_verified": "MRN-104287",
            "date_of_birth_verified": "1957-09-14",
            "cosigner_id": None,
        },
    )
    assert response.status_code == 201
    assert response.json()["outcome"] == outcome


def test_clinical_text_rejects_oversize_and_preserves_unicode(client, headers):
    rejected = client.post(
        "/api/patients/pat-001/care-plans", headers=headers,
        json={"problem": "x" * 501, "goal": "Reduce pain", "interventions": ["Reassess"], "owner_id": "usr-amina"},
    )
    assert rejected.status_code == 422
    goal = "Patient reports pain <= 3/10; reassess nausea and mobility."
    created = client.post(
        "/api/patients/pat-001/care-plans", headers=headers,
        json={"problem": "Acute pain", "goal": goal, "interventions": ["Reassess after intervention"], "owner_id": "usr-amina"},
    )
    assert created.status_code == 201
    detail = client.get("/api/patients/pat-001", headers=headers).json()
    assert any(plan["goal"] == goal for plan in detail["care_plans"])


def test_handover_requires_receiver_and_transfers_accountability(client, headers):
    created = client.post(
        "/api/patients/pat-001/handovers", headers=headers,
        json={"receiver_id": "usr-grace", "situation": "Oxygen requirement improving", "background": "Admitted with pneumonia",
              "assessment": "Observation frequency remains increased", "recommendation": "Review oxygen and repeat observations"},
    )
    assert created.status_code == 201
    handover_id = created.json()["id"]
    assert created.json()["unresolved_tasks"]
    assert client.post(
        f"/api/handovers/{handover_id}/accept", headers=headers, json={"version": 1}
    ).status_code == 403
    grace = login(client, "grace.mensah@nursing.test")
    accepted = client.post(
        f"/api/handovers/{handover_id}/accept", headers=grace, json={"version": 1}
    )
    assert accepted.status_code == 200
    detail = client.get("/api/patients/pat-001", headers=grace).json()
    assert detail["accountable_nurse_id"] == "usr-grace"


def test_named_receiver_can_list_pending_handover(client, headers):
    client.post(
        "/api/patients/pat-002/handovers", headers=headers,
        json={"receiver_id": "usr-grace", "situation": "Fluid balance review", "background": "Heart failure",
              "assessment": "Daily weight is due", "recommendation": "Review weight and diuresis"},
    )
    grace = login(client, "grace.mensah@nursing.test")
    pending = client.get("/api/handovers?status=pending", headers=grace)
    assert pending.status_code == 200
    assert pending.json()[0]["patient_id"] == "pat-002"
    assert pending.json()[0]["unresolved_tasks_json"]
    assert pending.json()[0]["current_risks_json"]["flags"] == ["Fluid restriction"]
    assert pending.json()[0]["version"] == 1


def test_care_plan_create_and_evaluate_with_version_guard(client, headers):
    created = client.post(
        "/api/patients/pat-002/care-plans", headers=headers,
        json={"problem": "Excess fluid volume", "goal": "Weight and symptoms improve",
              "interventions": ["Record daily weight", "Maintain prescribed fluid balance"],
              "owner_id": "usr-grace"},
    )
    assert created.status_code == 201
    plan_id = created.json()["id"]
    evaluated = client.post(
        f"/api/care-plans/{plan_id}/evaluate", headers=headers,
        json={"status": "active", "evaluation": "Weight pending; continue current interventions", "version": 1},
    )
    assert evaluated.status_code == 200
    assert evaluated.json()["version"] == 2
    stale = client.post(
        f"/api/care-plans/{plan_id}/evaluate", headers=headers,
        json={"status": "achieved", "evaluation": "Stale update", "version": 1},
    )
    assert stale.status_code == 409


def test_care_plan_can_be_discontinued_but_not_reopened(client, headers):
    response = client.post(
        "/api/care-plans/care-001/evaluate",
        headers=headers,
        json={"status": "discontinued", "evaluation": "Replaced by revised plan", "version": 1},
    )
    assert response.status_code == 200
    reopened = client.post(
        "/api/care-plans/care-001/evaluate",
        headers=headers,
        json={"status": "active", "evaluation": "Attempt to reopen terminal plan", "version": 2},
    )
    assert reopened.status_code == 409


def test_ward_nurse_reference_is_scoped(client, headers):
    nurses = client.get("/api/wards/ward-med-a/nurses", headers=headers)
    assert nurses.status_code == 200
    assert {nurse["id"] for nurse in nurses.json()} == {"usr-amina", "usr-grace"}
    assert client.get("/api/wards/ward-surg-b/nurses", headers=headers).status_code == 403


def test_safety_assessment_generates_owned_action(client, headers):
    response = client.post(
        "/api/patients/pat-002/safety-assessments", headers=headers,
        json={"assessment_type": "falls", "risk_level": "high", "score": 14,
              "findings": "Unsteady on standing", "actions": ["Supervise all transfers", "Place call bell within reach"]},
    )
    assert response.status_code == 201
    assert len(response.json()["generated_task_ids"]) == 2


def test_audit_chain_is_append_only_and_verifiable(client, headers):
    client.post(
        "/api/patients/pat-001/tasks", headers=headers,
        json={"title": "Record intake", "description": "Document oral intake", "priority": "normal",
              "due_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(), "assigned_to": "usr-amina"},
    )
    grace = login(client, "grace.mensah@nursing.test")
    audit = client.get("/api/audit", headers=grace)
    assert audit.status_code == 200
    assert audit.json()["chain_valid"] is True
    assert audit.json()["total_events"] == 1


def test_registered_nurse_cannot_read_audit(client, headers):
    assert client.get("/api/audit", headers=headers).status_code == 403


def test_reference_sets_cover_seeded_values(client, headers):
    priorities = client.get("/api/reference/task-priorities", headers=headers).json()["values"]
    statuses = client.get("/api/reference/task-statuses", headers=headers).json()["values"]
    tasks = client.get("/api/tasks", headers=headers).json()
    assert all(task["priority"] in priorities for task in tasks)
    assert all(task["status"] in statuses for task in tasks)
