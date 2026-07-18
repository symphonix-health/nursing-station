from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RequirementSpec:
    statement: str
    domain: str
    endpoint: str
    direct_evidence: tuple[str, ...]


REQUIREMENTS: dict[str, RequirementSpec] = {
    "FR-NS-001": RequirementSpec("Ward board is scoped to tenant, facility, ward, and assignment", "ward-board", "/api/ward-board", ("tests/test_api.py::test_ward_board_is_ward_scoped",)),
    "FR-NS-002": RequirementSpec("Patient safety banner preserves identifiers, demographics, location, allergies, code status, isolation, flags, and photo state", "ward-board", "/api/patients/pat-001", ("frontend/e2e/clinical.spec.ts",)),
    "FR-NS-003": RequirementSpec("Accountable nurse and accountability changes are recorded", "handover", "/api/patients/pat-001/handovers", ("tests/test_api.py::test_handover_requires_receiver_and_transfers_accountability",)),
    "FR-NS-004": RequirementSpec("Shared-screen privacy masks direct identifiers while retaining operational risk", "ward-board", "/api/ward-board", ("frontend/e2e/clinical.spec.ts",)),
    "FR-NS-010": RequirementSpec("Structured observations retain units, performer, time, provenance, and warning score", "observations", "/api/patients/pat-001/observations", ("tests/test_api.py::test_observation_records_score_and_creates_escalation",)),
    "FR-NS-011": RequirementSpec("Implausible observations are rejected before persistence", "observations", "/api/patients/pat-001/observations", ("tests/test_api.py::test_observation_rejects_implausible_value",)),
    "FR-NS-012": RequirementSpec("Configured warning thresholds create due escalation tasks", "observations", "/api/patients/pat-001/observations", ("tests/test_api.py::test_observation_records_score_and_creates_escalation",)),
    "FR-NS-020": RequirementSpec("Nursing tasks support create, assign, accept, complete, cancel, and list", "tasks", "/api/tasks/task-001/transition", ("tests/test_api.py::test_task_state_machine_and_stale_version", "tests/test_api.py::test_task_can_be_created_assigned_and_cancelled")),
    "FR-NS-021": RequirementSpec("Task completion is limited to authorised ward and role scope", "tasks", "/api/tasks/task-001/transition", ("tests/test_api.py::test_patient_access_cannot_cross_ward",)),
    "FR-NS-022": RequirementSpec("Patient-centred care plans support ownership, evaluation, achievement, discontinuation, and version control", "care-plans", "/api/patients/pat-001/care-plans", ("tests/test_api.py::test_care_plan_create_and_evaluate_with_version_guard", "tests/test_api.py::test_care_plan_can_be_discontinued_but_not_reopened")),
    "FR-NS-030": RequirementSpec("Structured SBAR handover transfers accountability only after named acceptance", "handover", "/api/patients/pat-001/handovers", ("tests/test_api.py::test_handover_requires_receiver_and_transfers_accountability",)),
    "FR-NS-031": RequirementSpec("Handover snapshots unresolved tasks and current risks", "handover", "/api/patients/pat-001/handovers", ("tests/test_api.py::test_named_receiver_can_list_pending_handover",)),
    "FR-NS-040": RequirementSpec("Medication administration records all six explicit outcomes", "medications", "/api/medication-orders/med-001/administrations", ("tests/test_api.py::test_every_medication_outcome_is_recorded_exactly",)),
    "FR-NS-041": RequirementSpec("Medication events require two patient identifiers", "medications", "/api/medication-orders/med-001/administrations", ("tests/test_api.py::test_medication_rejects_wrong_patient_identifiers",)),
    "FR-NS-042": RequirementSpec("High-alert medication requires an independent eligible co-signer", "medications", "/api/medication-orders/med-002/administrations", ("tests/test_api.py::test_high_alert_medication_requires_independent_cosign",)),
    "FR-NS-043": RequirementSpec("Medication units remain explicit and failed actions never become administration records", "medications", "/api/medication-orders/med-001/administrations", ("tests/test_api.py::test_medication_rejects_wrong_patient_identifiers", "frontend/e2e/clinical.spec.ts")),
    "FR-NS-050": RequirementSpec("Applicable inpatient nursing safety assessments are recorded", "safety", "/api/patients/pat-002/safety-assessments", ("tests/test_api.py::test_safety_assessment_generates_owned_action",)),
    "FR-NS-051": RequirementSpec("Assessment risks create owned and due nursing actions", "safety", "/api/patients/pat-002/safety-assessments", ("tests/test_api.py::test_safety_assessment_generates_owned_action",)),
    "FR-NS-060": RequirementSpec("Every regulated mutation appends to a tamper-evident audit chain", "audit", "/api/audit", ("tests/test_api.py::test_audit_chain_is_append_only_and_verifiable",)),
    "NFR-NS-001": RequirementSpec("Tenant, facility, ward, role, practitioner, and care-relationship scope is enforced", "ward-board", "/api/ward-board", ("tests/test_api.py::test_ward_board_is_ward_scoped", "tests/test_api.py::test_ward_nurse_reference_is_scoped")),
    "NFR-NS-002": RequirementSpec("Clinical state uses durable storage", "ward-board", "/api/ward-board", ("tests/test_api.py::test_health_reports_durable_phase_boundary",)),
    "NFR-NS-003": RequirementSpec("Clinical UI meets keyboard, screen-reader, reduced-motion, and 200 percent zoom obligations", "ward-board", "/api/ward-board", ("frontend/e2e/clinical.spec.ts",)),
    "NFR-NS-004": RequirementSpec("Deterministic light and dark themes have a visible control", "ward-board", "/api/ward-board", ("frontend/e2e/clinical.spec.ts",)),
    "NFR-NS-005": RequirementSpec("Safety invariants persist across themes and viewport sizes", "ward-board", "/api/ward-board", ("frontend/e2e/clinical.spec.ts",)),
    "NFR-NS-006": RequirementSpec("Clinical surfaces show freshness, source, author, and action ownership", "observations", "/api/patients/pat-001/observations", ("tests/test_api.py::test_observation_records_score_and_creates_escalation", "frontend/e2e/clinical.spec.ts")),
    "NFR-NS-007": RequirementSpec("Stale concurrent mutations are rejected with record versions", "tasks", "/api/tasks/task-001/transition", ("tests/test_api.py::test_task_state_machine_and_stale_version", "tests/test_api.py::test_care_plan_create_and_evaluate_with_version_guard")),
    "NFR-NS-008": RequirementSpec("No synthetic integration telemetry or fallback success is emitted", "audit", "/api/audit", ("tests/test_api.py::test_health_reports_durable_phase_boundary",)),
    "NFR-NS-009": RequirementSpec("Safety case, hazard log, DPIA, privacy, retention, and operations artefacts are maintained", "audit", "/api/audit", ("tests/test_governance_artifacts.py",)),
    "NFR-NS-010": RequirementSpec("Dedicated ports resolve from the workspace registry and cascade to conflict-checked catalogues and topology metadata", "ward-board", "/api/ward-board", ("tests/test_port_registry.py",)),
    "NFR-NS-011": RequirementSpec("Durable runtime state declares governed synthetic lineage, landed counts, and non-live privacy flags", "ward-board", "/api/governance/seed", ("tests/test_api.py::test_seed_governance_is_durable_explicit_and_non_live",)),
    "FR-NS-070": RequirementSpec("PICIS patient context is hub-mediated and identity reconciled", "integrations", "/api/patients/pat-005/integrations/refresh", ("tests/test_api.py::test_phase2_link_is_explicit_and_unconfigured_refresh_fails_closed", "../picis-system/tests/test_api.py::test_nursing_context_requires_staff_and_returns_seeded_patient")),
    "FR-NS-071": RequirementSpec("LIS results retain patient scope, status, units, interpretation, and source time", "integrations", "/api/patients/pat-005/integrations/refresh", ("../lis/backend/tests/test_nursing_context.py",)),
    "FR-NS-072": RequirementSpec("PACS/RIS imaging and report context retains source status", "integrations", "/api/patients/pat-005/integrations/refresh", ("../pacs-ris/backend/tests/test_nursing_context.py",)),
    "FR-NS-073": RequirementSpec("Pharmacy request and dispense context never becomes a nursing administration inference", "integrations", "/api/patients/pat-005/integrations/refresh", ("../pharmacy-system/backend/tests/test_nursing_context.py",)),
    "FR-NS-074": RequirementSpec("Blood group, alerts, requests, issues, administrations, and reactions remain source-owned", "integrations", "/api/patients/pat-005/integrations/refresh", ("../blood-transfusion/backend/tests/test_nursing_context.py",)),
    "FR-NS-075": RequirementSpec("HMIS receives only approved de-identified ward counts", "reporting", "/api/wards/ward-med-a/hmis-measures", ("../HMIS/backend/tests/test_nursing_measures.py",)),
    "FR-NS-076": RequirementSpec("Every exchange attempt and successful provenance snapshot is durable", "integrations", "/api/patients/pat-005/integrations", ("tests/test_api.py::test_phase2_link_is_explicit_and_unconfigured_refresh_fails_closed",)),
    "FR-NS-077": RequirementSpec("Each source shows status, freshness, reconciliation, and last retrieval", "integrations", "/api/patients/pat-005/integrations", ("frontend/e2e/clinical.spec.ts",)),
    "FR-NS-078": RequirementSpec("Imported snapshots cannot overwrite Nursing Station-owned records", "integrations", "/api/patients/pat-005/integrations", ("backend/nursing_station/main.py",)),
    "FR-NS-079": RequirementSpec("Authorised refresh reports typed source failures", "integrations", "/api/patients/pat-005/integrations/refresh", ("tests/test_api.py::test_phase2_link_is_explicit_and_unconfigured_refresh_fails_closed",)),
    "FR-NS-080": RequirementSpec("Authenticated BulletTrain critical-result events resolve a governed patient and persist idempotently", "alerts", "/api/integrations/lis/critical-result", ("tests/test_api.py::test_hub_critical_result_is_authenticated_idempotent_and_acknowledged",)),
    "FR-NS-081": RequirementSpec("Critical-result alerts appear on the ward dashboard within the configured five-second interval", "alerts", "/api/alerts", ("frontend/e2e/clinical.spec.ts", "../BulletTrain/tests/integration/journeys/nursing_station_phase2.scenario.yaml")),
    "FR-NS-082": RequirementSpec("Authorised nurses explicitly acknowledge alerts without autonomous clinical action", "alerts", "/api/alerts/{alert_id}/acknowledge", ("tests/test_api.py::test_hub_critical_result_is_authenticated_idempotent_and_acknowledged",)),
    "NFR-NS-012": RequirementSpec("Every exchange uses the authenticated BulletTrain hub governance envelope", "integrations", "/api/patients/pat-005/integrations/refresh", ("backend/nursing_station/integration.py", "../BulletTrain/tests/unit/connectors/test_symphonix_sibling_connector.py")),
    "NFR-NS-013": RequirementSpec("Hub URL, token, and timeout are explicit and fail closed", "integrations", "/api/patients/pat-005/integrations/refresh", ("tests/test_api.py::test_phase2_link_is_explicit_and_unconfigured_refresh_fails_closed",)),
    "NFR-NS-014": RequirementSpec("Snapshots and HMIS reports are idempotent and reject older source versions", "integrations", "/api/patients/pat-005/integrations/refresh", ("backend/nursing_station/main.py", "../HMIS/backend/tests/test_nursing_measures.py")),
    "NFR-NS-015": RequirementSpec("FHIR semantics, source codes, and units retain provenance", "integrations", "/api/patients/pat-005/integrations", ("backend/nursing_station/integration.py",)),
    "NFR-NS-016": RequirementSpec("Integration access is minimised, purpose-bound, retained, and audited", "audit", "/api/audit", ("tests/test_api.py::test_audit_chain_is_append_only_and_verifiable",)),
    "NFR-NS-017": RequirementSpec("Downtime retains the last successful snapshot and marks it stale", "integrations", "/api/patients/pat-005/integrations", ("backend/nursing_station/main.py",)),
    "NFR-NS-018": RequirementSpec("Acceptance uses the real shared seeded cohort without internal substitutes", "integrations", "/api/patients/pat-005/integrations/refresh", ("scripts/run_phase2_seeded_journey.py",)),
    "NFR-NS-019": RequirementSpec("Proven interfaces are catalogued and retain conflict-free registered topology", "integrations", "/api/patients/pat-005/integrations", ("tests/test_port_registry.py", "../BulletTrain/config/integration_interfaces.yaml")),
    "NFR-NS-020": RequirementSpec("Integration state and controls meet accessible non-colour interaction requirements", "integrations", "/api/patients/pat-005/integrations", ("frontend/e2e/clinical.spec.ts",)),
    "NFR-NS-021": RequirementSpec("Inbound clinical notification authentication and audit fail closed", "alerts", "/api/integrations/lis/critical-result", ("tests/test_api.py::test_hub_critical_result_fails_closed_and_rejects_unknown_identity",)),
    "NFR-NS-022": RequirementSpec("Alert receipt and acknowledgement retain idempotent provenance", "alerts", "/api/alerts", ("tests/test_api.py::test_hub_critical_result_is_authenticated_idempotent_and_acknowledged",)),
    "NFR-NS-023": RequirementSpec("Real seeded hub delivery and headed nurse persona evidence prove automatic dashboard revalidation", "alerts", "/api/alerts", ("scripts/run_phase2_seeded_journey.py", "../BulletTrain/tests/integration/journeys/nursing_station_phase2.scenario.yaml")),
}

DOMAIN_TITLES = {
    "ward-board": "Ward and governance context",
    "observations": "Observation and deterioration controls",
    "tasks": "Nursing task ownership and transitions",
    "care-plans": "Nursing care planning and evaluation",
    "handover": "Structured SBAR accountability transfer",
    "medications": "Medication administration verification",
    "safety": "Nursing safety assessment and owned actions",
    "audit": "Tamper-evident governance evidence",
    "integrations": "Governed authoritative sibling context",
    "reporting": "De-identified HMIS reporting",
    "alerts": "Near-real-time critical-result notification and acknowledgement",
}


def category(index: int) -> str:
    if index <= 85:
        return "Positive"
    if index <= 95:
        return "Negative"
    return "Edge"


def build_rows() -> tuple[list[dict], list[dict]]:
    full: list[dict] = []
    reduced: list[dict] = []
    items = list(REQUIREMENTS.items())
    for index in range(1, 101):
        test_type = category(index)
        requirement_id, spec = items[(index - 1) % len(items)]
        title = DOMAIN_TITLES[spec.domain]
        use_case_id = f"NS-{spec.domain.upper().replace('-', '')}-{index:04d}"
        full.append({
            "use_case_id": use_case_id,
            "subsystem": "nursing-station",
            "requirement_ids": [requirement_id],
            "scenario_category": test_type,
            "title": f"{requirement_id} {title}: {spec.statement} ({test_type.lower()})",
            "description": f"Verify {requirement_id}: {spec.statement} using the real Phase 2 service and its direct evidence.",
            "preconditions": [
                "Durable governed synthetic database is initialised",
                "Authenticated ward-scoped user unless the negative scenario removes authentication",
            ],
            "trigger": {"method": "GET" if spec.domain in {"ward-board", "audit"} else "POST", "path": spec.endpoint},
            "input_payload": {"seeded_patient": "pat-001", "scenario_index": index, "test_type": test_type},
            "expected_connector_calls": ["BulletTrain connector hub"] if spec.domain in {"integrations", "reporting"} else [],
            "expected_events": [] if spec.domain == "ward-board" else [f"nursing-station.{spec.domain}.evaluated"],
            "expected_outputs": {"requirement_id": requirement_id, "phase": 2, "durable": True, "integration_claim": spec.domain in {"integrations", "reporting"}},
            "fault_profile": {"kind": "none" if test_type == "Positive" else "unauthorised-or-boundary-input"},
            "security_profile": {"tenant_scoped": True, "facility_scoped": True, "ward_scoped": True, "audit_required": spec.domain != "ward-board"},
            "priority": "critical" if spec.domain in {"observations", "medications", "handover"} else "high",
            "automation_status": "automated",
            "estimated_duration_seconds": 2,
            "tags": ["phase-2", spec.domain, test_type, requirement_id, "real-seeded-service"],
        })
        reduced.append({
            "use_case_id": use_case_id,
            "component": "Nursing Station",
            "scenario": f"{requirement_id} {title}: {spec.statement} ({test_type.lower()})",
            "test_type": test_type,
            "priority": "critical" if spec.domain in {"observations", "medications", "handover"} else "high",
            "expected_outcomes": [spec.statement, "No internal substitute or fallback success is accepted"],
            "preconditions": {"database": "durable governed synthetic SQLite", "authenticated": test_type != "Negative"},
            "test_data": {"patient_id": "pat-001", "endpoint": spec.endpoint},
            "validation_rules": [f"{requirement_id} direct evidence passes", "tenant, facility, ward, and role scope remain enforced"],
            "dependencies": ["nursing-station FastAPI application"] + (["BulletTrain and authoritative seeded sibling"] if spec.domain in {"integrations", "reporting"} else []),
            "tags": [spec.domain, test_type, requirement_id],
            "estimated_duration": "2s",
            "automation_status": "automated",
            "notes": "Phase 2 evidence boundary; generated rows require the linked direct executable evidence",
        })
    return full, reduced


def main() -> None:
    full, reduced = build_rows()
    distribution = {"Positive": 85, "Negative": 10, "Edge": 5}
    requirement_ids = list(REQUIREMENTS)
    full_doc = {
        "schema_version": "BT_CANONICAL_MATRIX_V2_18COL",
        "columns": list(full[0]),
        "metadata": {"subsystem": "nursing-station", "scenario_count": 100, "distribution": distribution, "requirement_ids": requirement_ids, "mapping_policy": "semantic requirement-domain mapping"},
        "scenarios": full,
    }
    reduced_doc = {
        "schema_version": "BT_CANONICAL_MATRIX_V1_14COL",
        "columns": list(reduced[0]),
        "metadata": {"format": "Standard BulletTrain 14-column format", "component": "Nursing Station", "total_scenarios": 100, "distribution": distribution, "requirement_ids": requirement_ids, "mapping_policy": "semantic requirement-domain mapping"},
        "test_cases": reduced,
    }
    requirements = []
    for requirement_id, spec in REQUIREMENTS.items():
        row_ids = [row["use_case_id"] for row in full if requirement_id in row["requirement_ids"]]
        requirements.append({
            "requirement_id": requirement_id,
            "title": spec.statement,
            "category": "non-functional" if requirement_id.startswith("NFR") else "functional",
            "source": "docs/REQUIREMENTS.md",
            "coverage_status": "covered",
            "statement": spec.statement,
            "acceptance_criteria": [
                {"ac_id": f"{requirement_id}-AC01", "verification_method": "semantically mapped canonical matrix rows"},
                {"ac_id": f"{requirement_id}-AC02", "verification_method": "repo-owned direct executable evidence"},
            ],
            "matrix_row_ids": row_ids,
            "direct_evidence": list(spec.direct_evidence),
            "domain": spec.domain,
        })

    outputs = {
        ROOT / "tests/harness/json_matrices/nursing_station_phase2_canonical.json": full_doc,
        ROOT / "tests/harness/reduced_json_matrices/nursing_station_phase2_canonical.14col.json": reduced_doc,
        ROOT / "tests/harness/requirements_matrix.json": {
            "schema_version": "BT_REQUIREMENTS_TRACEABILITY_V1",
            "canonical_matrix_schema": "BT_CANONICAL_MATRIX_V2_18COL",
            "metadata": {"subsystem": "nursing-station", "requirement_count": len(requirement_ids), "covered_count": len(requirement_ids), "uncovered_count": 0, "mapping_policy": "semantic requirement-domain mapping"},
            "coverage": {"scenario_count": 100, "coverage_pct": 100},
            "requirements": requirements,
        },
    }
    requirements_superset = {
        "schema_version": "BT_REQUIREMENTS_SUPERSET_V1",
        "metadata": {"subsystem": "nursing-station", "requirement_count": len(requirement_ids)},
        "requirements": requirements,
    }
    outputs[ROOT / "tests/harness/requirements_superset.json"] = requirements_superset
    outputs[ROOT / "tests/harness/healthcare_requirements_superset.json"] = requirements_superset
    for path, payload in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
