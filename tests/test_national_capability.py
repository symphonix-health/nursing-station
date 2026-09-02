"""Direct executable evidence for the national-capability requirements.

Every test here drives the real FastAPI application against the real durable
seeded database. Nothing is mocked: where a BulletTrain route does not exist the
test asserts the fail-closed behaviour rather than substituting a fake hub.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from nursing_station import main, publications, workforce
from nursing_station.country_packs import CountryPackError, load_pack

CRITICAL_VITALS = {
    "respiratory_rate": 28,
    "oxygen_saturation": 89,
    "supplemental_oxygen": True,
    "systolic_bp": 88,
    "pulse": 134,
    "temperature": 39.4,
    "consciousness": "new-confusion",
    "source": "manual bedside observation",
}


def login(client, email: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": email, "password": "Nursing2026!"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def charge(client):
    return login(client, "grace.mensah@nursing.test")


@pytest.fixture()
def safety_officer(client):
    return login(client, "clinical.safety@nursing.test")


def _future(minutes: int = 60) -> str:
    return (datetime.now(UTC) + timedelta(minutes=minutes)).isoformat()


# ---------------------------------------------------------------------------
# FR-NS-170 / NFR-NS-027 -- country policy as versioned data
# ---------------------------------------------------------------------------
def test_country_pack_is_served_with_sources_and_is_not_adopted_by_default(client, headers):
    response = client.get("/api/country-pack", headers=headers)
    assert response.status_code == 200
    body = response.json()
    active = body["active"]
    assert active["jurisdiction"] == "IE"
    assert active["adoption_status"] == "candidate"
    assert body["locally_adopted"] is False
    assert body["local_adoption"] is None
    assert set(body["available_jurisdictions"]) == {"GB", "IE", "KE", "US"}
    # Every clinically meaningful entry must be traceable to a dated publisher.
    assert active["sources"]
    # FR-NS-101: the UI reads its deterioration thresholds from here.
    early = body["early_warning"]
    assert early["profile_id"] == active["early_warning_profile_id"]
    assert early["thresholds"] == {"review": 3, "escalate": 5, "critical": 7}
    assert early["response_minutes"]["critical"] > 0
    assert early["responder_minimum_role"]["escalate"] == "nurse_in_charge"
    for source in active["sources"]:
        assert source["publisher"] and source["title"] and source["effective_from"]


def test_country_pack_adoption_is_role_gated_and_pinned_to_the_reviewed_version(
    client, headers, safety_officer
):
    decision = {
        "jurisdiction": "IE",
        "pack_version": "2026.08.0",
        "decision": "adopted",
        "scope": "synthetic clinical simulation on ward MED-A",
        "note": "Reviewed against the ward's local escalation protocol.",
    }
    assert client.post("/api/country-pack/adoptions", headers=headers, json=decision).status_code == 403

    stale = {**decision, "pack_version": "2025.01.0"}
    conflict = client.post("/api/country-pack/adoptions", headers=safety_officer, json=stale)
    assert conflict.status_code == 409
    assert "2026.08.0" in conflict.json()["detail"]

    accepted = client.post("/api/country-pack/adoptions", headers=safety_officer, json=decision)
    assert accepted.status_code == 201
    assert accepted.json()["decision"] == "adopted"
    assert client.post(
        "/api/country-pack/adoptions", headers=safety_officer, json=decision
    ).status_code == 409
    assert client.get("/api/country-pack", headers=headers).json()["locally_adopted"] is True


def test_every_shipped_pack_validates_and_resolves_its_own_citations():
    for jurisdiction in ("IE", "GB", "KE", "US"):
        pack = load_pack(jurisdiction)
        assert pack.pack_version
        for measure in pack.quality_measures:
            assert pack.source(measure["source_id"])["publisher"]
        assert pack.source(pack.early_warning["source_id"])["title"]
        assert pack.source(pack.safe_staffing["source_id"])["title"]
        for criterion in pack.discharge_criteria:
            assert criterion["evidence_source"]
    with pytest.raises(CountryPackError):
        load_pack("ZZ")


# ---------------------------------------------------------------------------
# FR-NS-090 / FR-NS-091 / FR-NS-092 -- ward work orchestration
# ---------------------------------------------------------------------------
def test_work_queue_ranks_by_clinical_risk_and_explains_every_rank(client, headers):
    client.post("/api/patients/pat-001/observations", headers=headers, json=CRITICAL_VITALS)
    response = client.get("/api/ward-board/work-queue", headers=headers)
    assert response.status_code == 200
    body = response.json()
    entries = body["entries"]
    assert entries
    # Deterioration work for the critical patient outranks routine ward work.
    assert entries[0]["patient_id"] == "pat-001"
    assert entries[0]["rank_factors"]["escalation_level"] > 0
    assert entries[0]["rank_score"] == pytest.approx(
        sum(entries[0]["rank_factors"].values()), abs=0.01
    )
    scores = [entry["rank_score"] for entry in entries]
    assert scores == sorted(scores, reverse=True)
    daily_weight = next(e for e in entries if e["id"] == "task-002")["rank_score"]
    assert entries[0]["rank_score"] > daily_weight


def test_work_queue_marks_work_the_viewer_is_not_competent_to_perform(client, headers, charge):
    amina = client.get("/api/ward-board/work-queue", headers=headers).json()["entries"]
    blocked = next(entry for entry in amina if entry["id"] == "task-004")
    assert blocked["delegable"] is False
    assert blocked["missing_competency"] == "deteriorating-patient-response"

    grace = client.get("/api/ward-board/work-queue", headers=charge).json()["entries"]
    allowed = next(entry for entry in grace if entry["id"] == "task-004")
    assert allowed["delegable"] is True
    assert allowed["missing_competency"] is None


def test_delegation_requires_the_verified_competency(client, headers, charge):
    payload = {
        "title": "Coordinate discharge medicines",
        "description": "Reconcile the discharge supply with the ward list",
        "priority": "high",
        "due_at": _future(),
        "assigned_to": "usr-amina",
        "required_competency": "discharge-coordination",
    }
    refused = client.post("/api/patients/pat-001/tasks", headers=headers, json=payload)
    assert refused.status_code == 422
    assert refused.json()["detail"]["code"] == "competency_not_verified"
    assert refused.json()["detail"]["required_competency"] == "discharge-coordination"

    accepted = client.post(
        "/api/patients/pat-001/tasks", headers=headers,
        json={**payload, "assigned_to": "usr-grace"},
    )
    assert accepted.status_code == 201
    task_id = accepted.json()["id"]
    # The gate holds on transition too, not only on assignment.
    blocked = client.post(
        f"/api/tasks/{task_id}/transition", headers=headers,
        json={"action": "accept", "version": 1, "note": ""},
    )
    assert blocked.status_code == 422
    assert client.post(
        f"/api/tasks/{task_id}/transition", headers=charge,
        json={"action": "accept", "version": 1, "note": ""},
    ).status_code == 200


def test_interrupted_work_resurfaces_until_it_is_resumed(client, headers):
    before = client.get("/api/ward-board/work-queue", headers=headers).json()["entries"]
    baseline = next(entry for entry in before if entry["id"] == "task-002")["rank_score"]

    interruption = client.post(
        "/api/tasks/task-002/interruptions", headers=headers,
        json={"reason": "Called to a deteriorating patient in bay 3",
              "reason_category": "clinical-emergency"},
    )
    assert interruption.status_code == 201
    interruption_id = interruption.json()["id"]

    during = client.get("/api/ward-board/work-queue", headers=headers).json()["entries"]
    raised = next(entry for entry in during if entry["id"] == "task-002")
    assert raised["unresumed_interruptions"] == 1
    assert raised["rank_score"] > baseline

    resumed = client.post(f"/api/task-interruptions/{interruption_id}/resume", headers=headers)
    assert resumed.status_code == 200
    assert client.post(
        f"/api/task-interruptions/{interruption_id}/resume", headers=headers
    ).status_code == 409

    after = client.get("/api/ward-board/work-queue", headers=headers).json()["entries"]
    settled = next(entry for entry in after if entry["id"] == "task-002")
    assert settled["unresumed_interruptions"] == 0
    assert settled["rank_score"] == pytest.approx(baseline, abs=0.01)


# ---------------------------------------------------------------------------
# FR-NS-100 / FR-NS-101 -- deterioration scoring and response
# ---------------------------------------------------------------------------
def test_prescribed_oxygen_target_scale_changes_the_warning_score(client, headers):
    vitals = {
        "respiratory_rate": 18,
        "oxygen_saturation": 90,
        "supplemental_oxygen": False,
        "systolic_bp": 122,
        "pulse": 78,
        "temperature": 36.8,
        "consciousness": "alert",
        "source": "manual bedside observation",
    }
    scale_one = client.post("/api/patients/pat-001/observations", headers=headers, json=vitals)
    scale_two = client.post("/api/patients/pat-007/observations", headers=headers, json=vitals)
    assert scale_one.status_code == 201 and scale_two.status_code == 201
    assert scale_one.json()["oxygen_scale"] == "1"
    assert scale_two.json()["oxygen_scale"] == "2"
    # 90% is hypoxic against a 94-98% target and on-target against 88-92%.
    assert scale_one.json()["parameter_scores"]["oxygen_saturation"] == 3
    assert scale_two.json()["parameter_scores"]["oxygen_saturation"] == 0
    assert scale_one.json()["score"] - scale_two.json()["score"] == 3


def test_escalation_carries_the_jurisdiction_response_interval_and_responder_role(
    client, headers
):
    recorded = client.post(
        "/api/patients/pat-001/observations", headers=headers, json=CRITICAL_VITALS
    ).json()
    assert recorded["escalation_level"] == "critical"
    assert recorded["response_minutes"] == 5
    assert recorded["responder_minimum_role"] == "nurse_in_charge"
    assert recorded["response_due_at"]

    feed = client.get("/api/wards/ward-med-a/escalations", headers=headers)
    assert feed.status_code == 200
    row = next(r for r in feed.json()["escalations"] if r["id"] == recorded["id"])
    assert row["answered"] is False
    assert feed.json()["profile_id"] == "IE-INEWS-CANDIDATE-v1"


def test_escalation_response_names_a_human_and_never_self_resolves(client, headers, charge):
    recorded = client.post(
        "/api/patients/pat-001/observations", headers=headers, json=CRITICAL_VITALS
    ).json()
    observation_id = recorded["id"]
    body = {"clinical_response": "Reviewed at the bedside; oxygen titrated and medical team called",
            "outcome": "escalated-to-medical-team"}

    refused = client.post(
        f"/api/observations/{observation_id}/escalation-response", headers=headers, json=body
    )
    assert refused.status_code == 403
    assert "nurse_in_charge" in refused.json()["detail"]

    answered = client.post(
        f"/api/observations/{observation_id}/escalation-response", headers=charge, json=body
    )
    assert answered.status_code == 201
    payload = answered.json()
    assert payload["responder_id"] == "usr-grace"
    assert payload["responder_role"] == "nurse_in_charge"
    assert payload["within_required_interval"] is True
    assert payload["escalation_task_id"] == recorded["escalation_task_id"]

    # Recording a response must not close the escalation task by itself.
    detail = client.get("/api/patients/pat-001", headers=headers).json()
    task = next(t for t in detail["tasks"] if t["id"] == recorded["escalation_task_id"])
    assert task["status"] == "open"

    assert client.post(
        f"/api/observations/{observation_id}/escalation-response", headers=charge, json=body
    ).status_code == 409

    feed = client.get("/api/wards/ward-med-a/escalations", headers=charge).json()
    assert next(r for r in feed["escalations"] if r["id"] == observation_id)["answered"] is True


def test_routine_observation_cannot_carry_an_escalation_response(client, charge):
    routine = client.post(
        "/api/patients/pat-002/observations", headers=charge,
        json={"respiratory_rate": 16, "oxygen_saturation": 98, "supplemental_oxygen": False,
              "systolic_bp": 122, "pulse": 78, "temperature": 36.8, "consciousness": "alert",
              "source": "manual bedside observation"},
    ).json()
    response = client.post(
        f"/api/observations/{routine['id']}/escalation-response", headers=charge,
        json={"clinical_response": "No action needed", "outcome": "reviewed-no-change"},
    )
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# FR-NS-120 -- handover transfers the unresolved actions too
# ---------------------------------------------------------------------------
def _handover(client, headers, receiver_id: str, patient_id: str = "pat-001") -> str:
    created = client.post(
        f"/api/patients/{patient_id}/handovers", headers=headers,
        json={"receiver_id": receiver_id, "situation": "Oxygen requirement improving",
              "background": "Admitted with pneumonia",
              "assessment": "Observation frequency remains increased",
              "recommendation": "Review oxygen and repeat observations"},
    )
    assert created.status_code == 201
    return created.json()["id"]


def test_accepting_a_handover_moves_the_unresolved_actions_with_the_patient(
    client, headers, charge
):
    handover_id = _handover(client, headers, "usr-grace")
    accepted = client.post(
        f"/api/handovers/{handover_id}/accept", headers=charge, json={"version": 1}
    )
    assert accepted.status_code == 200
    accepted_ids = {row["task_id"] for row in accepted.json()["accepted_actions"]}
    assert "task-001" in accepted_ids
    assert accepted.json()["declined_actions"] == []
    detail = client.get("/api/patients/pat-001", headers=charge).json()
    assert next(t for t in detail["tasks"] if t["id"] == "task-001")["assigned_to"] == "usr-grace"


def test_a_declined_action_stays_with_the_sender_and_needs_a_reason(client, headers, charge):
    handover_id = _handover(client, headers, "usr-grace")
    without_reason = client.post(
        f"/api/handovers/{handover_id}/accept", headers=charge,
        json={"version": 1,
              "action_decisions": [{"task_id": "task-001", "decision": "decline", "reason": " "}]},
    )
    assert without_reason.status_code == 422
    assert without_reason.json()["detail"]["code"] == "decline_requires_reason"

    unknown = client.post(
        f"/api/handovers/{handover_id}/accept", headers=charge,
        json={"version": 1,
              "action_decisions": [{"task_id": "task-999", "decision": "accept", "reason": ""}]},
    )
    assert unknown.status_code == 422
    assert unknown.json()["detail"]["code"] == "unknown_unresolved_action"

    declined = client.post(
        f"/api/handovers/{handover_id}/accept", headers=charge,
        json={"version": 1,
              "action_decisions": [{"task_id": "task-001", "decision": "decline",
                                    "reason": "Assigned to the twilight nurse already on the bay"}]},
    )
    assert declined.status_code == 200
    assert [row["task_id"] for row in declined.json()["declined_actions"]] == ["task-001"]
    assert declined.json()["declined_actions"][0]["retained_by"] == "usr-amina"
    detail = client.get("/api/patients/pat-001", headers=charge).json()
    assert next(t for t in detail["tasks"] if t["id"] == "task-001")["assigned_to"] == "usr-amina"


def test_an_action_the_receiver_is_not_competent_for_is_never_silently_transferred(
    client, headers, charge
):
    created = client.post(
        "/api/patients/pat-002/tasks", headers=charge,
        json={"title": "Coordinate discharge medicines",
              "description": "Reconcile the discharge supply with the ward list",
              "priority": "high", "due_at": _future(), "assigned_to": "usr-grace",
              "required_competency": "discharge-coordination"},
    )
    assert created.status_code == 201
    task_id = created.json()["id"]
    handover_id = _handover(client, charge, "usr-amina", patient_id="pat-002")
    accepted = client.post(
        f"/api/handovers/{handover_id}/accept", headers=headers, json={"version": 1}
    )
    assert accepted.status_code == 200
    declined = {row["task_id"]: row for row in accepted.json()["declined_actions"]}
    assert task_id in declined
    assert "discharge-coordination" in declined[task_id]["reason"]
    assert declined[task_id]["retained_by"] == "usr-grace"


# ---------------------------------------------------------------------------
# FR-NS-110 / FR-NS-111 -- eMAR loop
# ---------------------------------------------------------------------------
PHARMACY_CONTEXT = {
    "patient_id": "pat-ava",
    "medication_requests": [
        {"id": "rx-ava-0001", "medication_name": "Enoxaparin", "dose_value": 40,
         "dose_unit": "mg", "route": "subcutaneous", "schedule": "once daily",
         "due_at": "2026-08-05T20:00:00+00:00", "high_alert": False},
        {"id": "rx-ava-0002", "medication_name": "Paracetamol", "dose_value": 1,
         "route": "oral", "schedule": "four times daily",
         "due_at": "2026-08-05T18:00:00+00:00"},
    ],
}


def _reconcile(patient_id: str = "pat-005") -> dict:
    with main.db.connect() as conn:
        patient = dict(conn.execute(
            "SELECT * FROM patients WHERE id=?", (patient_id,)
        ).fetchone())
        return main.reconcile_medication_orders(
            conn, patient=patient, tenant_id=patient["tenant_id"], body=PHARMACY_CONTEXT
        )


def test_hub_sourced_requests_reconcile_into_the_emar_and_refuse_incomplete_ones(client, headers):
    result = _reconcile()
    # The second request has no dose unit. FR-NS-043 forbids inferring one, so
    # it must never become an administrable order.
    assert len(result["created"]) == 1
    assert result["unmappable"] == ["rx-ava-0002"]
    orders = client.get("/api/patients/pat-005/medications", headers=headers).json()
    assert [o["medication_name"] for o in orders] == ["Enoxaparin"]
    assert orders[0]["source_system"] == "pharmacy-system"
    assert orders[0]["source_order_id"] == "rx-ava-0001"

    repeated = _reconcile()
    assert repeated["created"] == []
    assert len(repeated["updated"]) == 1
    assert len(client.get("/api/patients/pat-005/medications", headers=headers).json()) == 1


def test_an_administered_order_is_never_overwritten_by_a_later_snapshot(client, charge):
    order_id = _reconcile()["created"][0]
    recorded = client.post(
        f"/api/medication-orders/{order_id}/administrations", headers=charge,
        json={"outcome": "administered", "reason": None, "mrn_verified": "MRN-104401",
              "date_of_birth_verified": "1964-12-30", "cosigner_id": None},
    )
    assert recorded.status_code == 201
    assert _reconcile()["protected"] == [order_id]


def test_a_hub_sourced_outcome_is_queued_and_never_reported_as_delivered(client, charge):
    """Administration writes the obligation; it does not deliver it.

    pharmacy_system now publishes the NursingMedicationOutcome write route, so
    this outcome CAN be delivered -- but recording an administration still only
    queues it. Delivery is a separate, explicit dispatch that must hear a
    receipt, so a pharmacy outage can never be hidden inside a nurse's
    administration succeeding.
    """
    order_id = _reconcile()["created"][0]
    recorded = client.post(
        f"/api/medication-orders/{order_id}/administrations", headers=charge,
        json={"outcome": "omitted", "reason": "Dose unavailable before the occurrence closed",
              "mrn_verified": "MRN-104401", "date_of_birth_verified": "1964-12-30",
              "cosigner_id": None},
    ).json()
    assert recorded["publication_status"] == publications.STATUS_PENDING
    assert recorded["publication_id"]

    queue = client.get("/api/publications", headers=charge).json()
    entry = next(p for p in queue["publications"] if p["id"] == recorded["publication_id"])
    assert entry["kind"] == publications.KIND_MEDICATION_OUTCOME
    assert entry["connector"] == "pharmacy_system"
    assert entry["status"] == publications.STATUS_PENDING
    assert entry["completed_at"] is None
    assert entry["correlation_id"].startswith("ns-medadmin-")
    assert entry["receipt_json"] is None if "receipt_json" in entry else True


def test_dispatching_without_a_configured_hub_fails_loudly_and_keeps_the_obligation(
    client, charge
):
    """No hub, no delivery, and the row still says pending -- not delivered.

    The test environment configures no BulletTrain hub, so this is the honest
    unavailable path: the dispatch refuses with 503 and the publication is left
    exactly where it was for a retry.
    """
    order_id = _reconcile()["created"][0]
    recorded = client.post(
        f"/api/medication-orders/{order_id}/administrations", headers=charge,
        json={"outcome": "withheld", "reason": "Systolic below the hold parameter",
              "mrn_verified": "MRN-104401", "date_of_birth_verified": "1964-12-30",
              "cosigner_id": None},
    ).json()
    publication_id = recorded["publication_id"]
    response = client.post(f"/api/publications/{publication_id}/dispatch", headers=charge)
    assert response.status_code == 503, response.text
    assert response.json()["detail"]["code"] == "integration_not_configured"
    queue = client.get("/api/publications", headers=charge).json()
    entry = next(p for p in queue["publications"] if p["id"] == publication_id)
    assert entry["status"] == publications.STATUS_PENDING
    assert entry["completed_at"] is None


def test_dispatch_is_role_gated_and_skips_kinds_with_no_route(client, headers, charge):
    assert client.post("/api/publications/dispatch", headers=headers).status_code == 403
    # A staffing declaration has no BulletTrain destination; draining the queue
    # reports it as skipped with its named gap rather than attempting a delivery
    # that cannot land.
    client.post(
        "/api/wards/ward-med-a/staffing-declarations", headers=charge,
        json={"reason": "Two registered nurses off sick on a high-acuity ward tonight."},
    )
    drained = client.post("/api/publications/dispatch?kind=staffing.shortage.declaration",
                          headers=charge)
    assert drained.status_code == 200, drained.text
    body = drained.json()
    assert body["attempted"] == 0
    assert body["skipped_unregistered"]
    assert all(item["gap"] for item in body["skipped_unregistered"])


def test_a_locally_authored_order_creates_no_external_obligation(client, headers):
    recorded = client.post(
        "/api/medication-orders/med-001/administrations", headers=headers,
        json={"outcome": "administered", "reason": None, "mrn_verified": "MRN-104287",
              "date_of_birth_verified": "1957-09-14", "cosigner_id": None},
    ).json()
    assert recorded["publication_id"] is None
    assert recorded["publication_status"] == "not-applicable"


# ---------------------------------------------------------------------------
# FR-NS-140 / FR-NS-141 -- harm incident and review
# ---------------------------------------------------------------------------
def _incident(client, headers, **overrides) -> dict:
    payload = {
        "incident_type": "fall",
        "occurred_at": datetime.now(UTC).isoformat(),
        "discovered_at": datetime.now(UTC).isoformat(),
        "harm_level": "moderate",
        "description": "Unwitnessed fall from the bedside chair; no loss of consciousness",
    }
    payload.update(overrides)
    response = client.post("/api/patients/pat-001/harm-incidents", headers=headers, json=payload)
    return response


def test_reportability_comes_from_the_country_pack_not_from_code(client, headers):
    reportable = _incident(client, headers, harm_level="severe")
    assert reportable.status_code == 201
    assert reportable.json()["externally_reportable"] is True
    assert reportable.json()["review_required"] is True
    assert reportable.json()["external_report_state"] == publications.STATUS_PENDING

    minor = _incident(client, headers, harm_level="low")
    assert minor.status_code == 201
    assert minor.json()["externally_reportable"] is False
    assert minor.json()["review_required"] is False
    assert minor.json()["publication_id"] is None


def test_a_pressure_injury_present_on_admission_is_not_this_wards_harm(client, headers):
    acquired = _incident(
        client, headers, incident_type="pressure-injury", classification="category-3",
        body_site="sacrum", harm_level="moderate", present_on_admission=False,
    )
    assert acquired.json()["externally_reportable"] is True

    on_admission = _incident(
        client, headers, incident_type="pressure-injury", classification="category-3",
        body_site="left heel", harm_level="moderate", present_on_admission=True,
    )
    assert on_admission.json()["externally_reportable"] is False


def test_an_incident_discovered_before_it_occurred_is_rejected(client, headers):
    response = _incident(
        client, headers,
        occurred_at=datetime.now(UTC).isoformat(),
        discovered_at=(datetime.now(UTC) - timedelta(hours=2)).isoformat(),
    )
    assert response.status_code == 422


def test_incident_review_needs_a_second_person_and_produces_owned_learning(
    client, headers, charge
):
    incident_id = _incident(client, headers, harm_level="severe").json()["id"]
    review = {
        "avoidability": "avoidable",
        "contributory_factors": ["Call bell out of reach", "Sedating medication not reviewed"],
        "learning_actions": ["Re-audit call-bell placement on every bay"],
        "conclusion": "Preventable with the existing falls bundle applied at handover.",
    }
    assert client.post(
        f"/api/harm-incidents/{incident_id}/review", headers=headers, json=review
    ).status_code == 403

    own_incident = _incident(client, charge, harm_level="severe").json()["id"]
    self_review = client.post(
        f"/api/harm-incidents/{own_incident}/review", headers=charge, json=review
    )
    assert self_review.status_code == 422

    reviewed = client.post(
        f"/api/harm-incidents/{incident_id}/review", headers=charge, json=review
    )
    assert reviewed.status_code == 201
    assert reviewed.json()["reviewed_by"] == "usr-grace"
    assert len(reviewed.json()["generated_task_ids"]) == 1
    assert client.post(
        f"/api/harm-incidents/{incident_id}/review", headers=charge, json=review
    ).status_code == 409

    listing = client.get("/api/wards/ward-med-a/harm-incidents", headers=charge).json()
    row = next(i for i in listing["incidents"] if i["id"] == incident_id)
    assert row["status"] == "reviewed"
    assert row["avoidability"] == "avoidable"


# ---------------------------------------------------------------------------
# FR-NS-150 / FR-NS-151 -- discharge readiness
# ---------------------------------------------------------------------------
def _readiness(client, headers, patient_id: str = "pat-002") -> dict:
    response = client.post(
        f"/api/patients/{patient_id}/discharge-readiness", headers=headers, json={}
    )
    assert response.status_code == 201
    return response.json()


def test_readiness_opens_from_the_pack_criteria_and_blocks_early_completion(client, headers):
    opened = _readiness(client, headers)
    assert opened["criteria"] == 6
    assert opened["jurisdiction"] == "IE"
    view = client.get("/api/patients/pat-002/discharge-readiness", headers=headers).json()
    assert view["ready_for_discharge"] is False
    assert set(view["outstanding_mandatory"]) == {
        "medicines-supply-and-education", "equipment-and-aids",
        "community-nursing-referral", "patient-and-carer-education",
    }
    blocked = client.post(
        f"/api/discharge-readiness/{opened['id']}/complete", headers=headers
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "mandatory_criteria_outstanding"
    assert client.post(
        "/api/patients/pat-002/discharge-readiness", headers=headers, json={}
    ).status_code == 409


def test_a_criterion_owned_by_a_sibling_cannot_be_met_by_local_assertion(client, headers):
    opened = _readiness(client, headers)
    refused = client.post(
        f"/api/discharge-readiness/{opened['id']}/criteria/medicines-supply-and-education/confirm",
        headers=headers, json={"note": "Pharmacy said it was fine on the phone"},
    )
    assert refused.status_code == 409
    assert "pharmacy-system" in refused.json()["detail"]

    owned = client.post(
        f"/api/discharge-readiness/{opened['id']}/criteria/patient-and-carer-education/confirm",
        headers=headers, json={"note": "Warning signs and escalation route explained; teach-back done"},
    )
    assert owned.status_code == 200
    criterion = next(
        c for c in owned.json()["criteria"] if c["criterion_id"] == "patient-and-carer-education"
    )
    assert criterion["status"] == "met"
    assert criterion["confirmed_by"] == "usr-amina"
    assert "patient-and-carer-education" not in owned.json()["outstanding_mandatory"]


def test_discharge_coordination_fails_closed_without_a_configured_hub(client, headers):
    opened = _readiness(client, headers)
    response = client.post(f"/api/discharge-readiness/{opened['id']}/coordinate", headers=headers)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "integration_not_configured"


# ---------------------------------------------------------------------------
# FR-NS-130 / FR-NS-131 / FR-NS-132 -- safe staffing
# ---------------------------------------------------------------------------
def test_staffing_position_computes_the_requirement_and_reports_the_missing_roster(
    client, charge
):
    response = client.get("/api/wards/ward-med-a/staffing-position", headers=charge)
    assert response.status_code == 200
    position = response.json()["position"]
    assert position["occupied_beds"] == 6
    assert position["policy_status"] == workforce.POLICY_SUFFICIENT
    assert position["required_nursing_hours"] == pytest.approx(13.2)
    assert position["required_registered_hours"] == pytest.approx(10.56)
    assert position["roster_state"] == workforce.ROSTER_STATE_NOT_REFRESHED
    # No roster means no actual staffing, not zero actual staffing.
    assert position["actual_registered_hours"] is None
    assert position["actual_skill_mix_percent"] is None
    assert position["triggers_fired"] == []
    assert response.json()["roster_contract"]["owner"] == "unassigned"


def test_roster_refresh_fails_closed_without_a_configured_hub(client, charge):
    response = client.post("/api/wards/ward-med-a/staffing-roster/refresh", headers=charge)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "integration_not_configured"


def test_a_shortage_declaration_emits_exactly_the_governed_field_set(client, headers, charge):
    body = {"reason": "Two registered nurses absent at short notice; escalation cover unfilled"}
    assert client.post(
        "/api/wards/ward-med-a/staffing-declarations", headers=headers, json=body
    ).status_code == 403

    declared = client.post(
        "/api/wards/ward-med-a/staffing-declarations", headers=charge, json=body
    )
    assert declared.status_code == 201
    payload = declared.json()
    governed = payload["governed_declaration"]
    assert set(governed) == {
        "declaration_id", "scope_unit", "declared_by", "reason", "starts_at", "expires_at",
    }
    assert governed["scope_unit"] == "ward-med-a"
    assert governed["declared_by"] == "usr-grace"
    # The tier belongs to BulletTrain's policy evaluation, never to this repo.
    assert payload["effective_tier"] is None
    assert payload["publication_status"] == publications.STATUS_PENDING
    assert payload["position"]["roster_state"] == workforce.ROSTER_STATE_NOT_REFRESHED

    listing = client.get("/api/wards/ward-med-a/staffing-declarations", headers=charge).json()
    row = next(d for d in listing["declarations"] if d["declaration_id"] == governed["declaration_id"])
    assert row["active"] is True
    assert row["revoked"] == 0

    revoked = client.post(
        f"/api/staffing-declarations/{governed['declaration_id']}/revoke", headers=charge,
        json={"reason": "Bank nurse arrived and cover is restored"},
    )
    assert revoked.status_code == 200
    assert client.post(
        f"/api/staffing-declarations/{governed['declaration_id']}/revoke", headers=charge,
        json={"reason": "duplicate"},
    ).status_code == 409
    listing = client.get("/api/wards/ward-med-a/staffing-declarations", headers=charge).json()
    assert next(
        d for d in listing["declarations"] if d["declaration_id"] == governed["declaration_id"]
    )["active"] is False


def test_the_declaration_builder_refuses_to_extend_the_governed_contract():
    pack = load_pack("IE")
    starts = datetime.now(UTC)
    _, expires = workforce.declaration_window(pack, starts)
    governed = workforce.build_declaration(
        pack, declaration_id="ns-staffing-1", scope_unit="ward-med-a", declared_by="usr-grace",
        reason="cover unfilled", starts_at=starts, expires_at=expires,
    )
    assert (expires - starts) == timedelta(minutes=480)
    assert list(governed) == [
        "declaration_id", "scope_unit", "declared_by", "reason", "starts_at", "expires_at",
    ]


def test_position_computation_reads_a_published_roster_and_fires_pack_triggers():
    pack = load_pack("IE")
    roster = {
        "ward_id": "ward-med-a", "shift_date": "2026-08-05", "shift": "day",
        "assignments": [
            {"staff_id": "s1", "role": "registered_nurse", "registered": True, "hours": 12},
            {"staff_id": "s2", "role": "healthcare_assistant", "registered": False, "hours": 12},
            {"staff_id": "s3", "role": "healthcare_assistant", "registered": False, "hours": 12},
        ],
    }
    workforce.validate_roster_payload(
        roster, ward_id="ward-med-a", shift_date="2026-08-05", shift="day"
    )
    position = workforce.compute_position(
        pack,
        ward={"id": "ward-med-a", "specialty": "adult-medical"},
        patients=[{"acuity_dependency": "level-2", "latest_score": 2} for _ in range(10)],
        escalate_threshold=5,
        roster=roster,
        roster_state=workforce.ROSTER_STATE_CURRENT,
        roster_source="workforce",
        shift="day",
        shift_date="2026-08-05",
    )
    fired = {trigger["trigger_id"] for trigger in position.triggers_fired}
    assert "registered-hours-below-norm" in fired
    assert "skill-mix-below-minimum" in fired
    assert "patients-per-registered-nurse-exceeded" in fired
    assert position.actual_skill_mix_percent == pytest.approx(33.3, abs=0.1)
    assert position.shortage_indicated is True


def test_an_empty_roster_is_rejected_rather_than_read_as_nobody_on_duty():
    with pytest.raises(workforce.RosterContractError):
        workforce.validate_roster_payload(
            {"ward_id": "ward-med-a", "shift_date": "2026-08-05", "shift": "day",
             "assignments": []},
            ward_id="ward-med-a", shift_date="2026-08-05", shift="day",
        )
    with pytest.raises(workforce.RosterContractError):
        workforce.validate_roster_payload(
            {"ward_id": "ward-surg-b", "shift_date": "2026-08-05", "shift": "day",
             "assignments": [{"staff_id": "s1", "role": "registered_nurse",
                              "registered": True, "hours": 12}]},
            ward_id="ward-med-a", shift_date="2026-08-05", shift="day",
        )


# ---------------------------------------------------------------------------
# FR-NS-160 / FR-NS-161 -- nursing quality dataset
# ---------------------------------------------------------------------------
def test_quality_measures_apply_the_pack_definitions_to_this_wards_records(
    client, headers, charge
):
    _incident(client, headers, harm_level="severe")
    _incident(client, headers, incident_type="pressure-injury", classification="category-3",
              body_site="sacrum", harm_level="moderate")
    response = client.get("/api/wards/ward-med-a/quality-measures", headers=charge)
    assert response.status_code == 200
    body = response.json()
    measures = {row["measure_id"]: row for row in body["measures"]}
    assert set(measures) == {
        "NSQ-STAFF-01", "NSQ-STAFF-02", "NSQ-CARE-01", "NSQ-SAFE-01", "NSQ-SAFE-02",
        "NSQ-DETER-01", "NSQ-MED-01",
    }
    # Roster-dependent measures are absent, not zero.
    assert measures["NSQ-STAFF-01"]["status"] == "source-unavailable"
    assert measures["NSQ-STAFF-02"]["status"] == "source-unavailable"
    assert measures["NSQ-STAFF-01"]["value"] is None
    assert body["unavailable"] == ["NSQ-STAFF-01", "NSQ-STAFF-02"]
    assert measures["NSQ-SAFE-01"]["numerator"] == 1
    assert measures["NSQ-SAFE-02"]["numerator"] == 1
    assert measures["NSQ-SAFE-01"]["status"] == "computed"
    assert measures["NSQ-CARE-01"]["status"] == "computed"
    # Nothing happened is distinguished from a perfect score.
    assert measures["NSQ-MED-01"]["status"] == "no-denominator"
    for row in body["measures"]:
        assert row["source_id"]


def test_quality_measures_are_role_gated(client, headers):
    assert client.get(
        "/api/wards/ward-med-a/quality-measures", headers=headers
    ).status_code == 403


def test_the_measure_payload_carries_no_patient_identifiers(client, headers, charge):
    _incident(client, headers, harm_level="severe")
    body = client.get("/api/wards/ward-med-a/quality-measures", headers=charge).json()
    serialised = json.dumps(body["measures"])
    for identifier in ("pat-001", "MRN-104287", "Margaret", "1957-09-14"):
        assert identifier not in serialised


# ---------------------------------------------------------------------------
# NFR-NS-029 -- the durable queue is visible and honest about its gaps
# ---------------------------------------------------------------------------
def test_the_publication_surface_names_every_open_bullettrain_gap(client, charge):
    body = client.get("/api/publications", headers=charge).json()
    contracts = {row["kind"]: row for row in body["contracts"]}
    # Registered destinations: HMIS measures, and pharmacy's administration
    # outcome since BT-PHARMACY-SYSTEM-HUB-001 gained NursingMedicationOutcome.
    for kind in (
        publications.KIND_QUALITY_DATASET,
        publications.KIND_MEDICATION_OUTCOME,
    ):
        assert contracts[kind]["route_status"] == "registered"
        assert not contracts[kind]["gap"]
    # Still owned by nobody, and said so rather than faked.
    for kind in (
        publications.KIND_STAFFING_DECLARATION,
        publications.KIND_HARM_INCIDENT,
    ):
        assert contracts[kind]["route_status"] == "unregistered"
        assert contracts[kind]["gap"]


def test_the_publication_surface_is_role_gated(client, headers):
    assert client.get("/api/publications", headers=headers).status_code == 403


# ---------------------------------------------------------------------------
# FR-NS-092 -- the queue names the open interruption so it can be resumed from the ward UI
# ---------------------------------------------------------------------------
def test_work_queue_carries_open_interruption_ids_until_resumed(client, headers):
    recorded = client.post(
        "/api/tasks/task-002/interruptions",
        headers=headers,
        json={"reason": "Called to a deteriorating patient in bay 3", "reason_category": "clinical-emergency"},
    )
    assert recorded.status_code == 201, recorded.text
    interruption_id = recorded.json()["id"]
    queue = client.get("/api/ward-board/work-queue", headers=headers).json()
    entry = next(row for row in queue["entries"] if row["id"] == "task-002")
    assert [item["id"] for item in entry["open_interruptions"]] == [interruption_id]
    assert entry["open_interruptions"][0]["reason_category"] == "clinical-emergency"
    assert entry["unresumed_interruptions"] == 1
    assert client.post(f"/api/task-interruptions/{interruption_id}/resume", headers=headers).status_code == 200
    queue = client.get("/api/ward-board/work-queue", headers=headers).json()
    entry = next(row for row in queue["entries"] if row["id"] == "task-002")
    assert entry["open_interruptions"] == []


# ---------------------------------------------------------------------------
# FR-NS-110 / NFR-NS-015 -- every sibling read is keyed on the SHARED identifier
# ---------------------------------------------------------------------------
def test_every_sibling_read_is_keyed_on_the_shared_cross_system_identifier():
    """picis's local encounter id means nothing to pharmacy or pacs-ris.

    Sending it produced an empty 200 from both -- a context the ward rendered
    as "no reportable items" rather than "asked with the wrong key". The value
    is now always the shared identifier; only the parameter NAME differs,
    because the connector routes name it differently.
    """
    from nursing_station.main import _integration_payload

    patient = {"external_nhs_number": "9991000003", "source_patient_id": "pat-ava"}
    for source in ("picis-system", "lis", "blood-transfusion", "pharmacy-system", "pacs-ris"):
        payload = _integration_payload(patient, source)
        assert list(payload.values()) == ["9991000003"], (source, payload)
        assert "pat-ava" not in payload.values()
    assert set(_integration_payload(patient, "pharmacy-system")) == {"patient_id"}
    assert set(_integration_payload(patient, "lis")) == {"external_nhs_number"}
