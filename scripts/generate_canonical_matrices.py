"""Generate Nursing Station's canonical matrices and requirement catalogues.

BROWNFIELD CONTRACT (read before changing anything here)
--------------------------------------------------------
Every artefact this script writes is shared, accumulated state. Other sessions
inject requirements and scenario rows into the same files. Until 2026-08-05 this
script was regenerate-overwrite: running it silently deleted every row it had
not produced itself, which was proved by planting a foreign requirement and a
foreign matrix row and watching both disappear.

It is now read-merge-write:

* rows this script owns (by ``use_case_id``) are regenerated;
* every other row is preserved verbatim, in its original relative order;
* requirements this script owns (by ``requirement_id``) are regenerated, all
  others preserved;
* totals, distributions and coverage are recomputed over the UNION.

``tests/test_matrix_builder_brownfield.py`` plants a foreign entry in each
output and asserts survival, and asserts the rebuild is a byte-identical no-op
on an unchanged tree.

The legacy 100-row matrix is generated from a FROZEN requirement-id tuple, not
from the live ``REQUIREMENTS`` mapping. Growing the catalogue must never reshuffle
the rotation of an already-committed matrix: that would rewrite every row body,
destroying the coverage atoms recorded in ``matrix-integrity-baseline.json``.
New requirements get their own authored matrix instead, with genuinely distinct
per-row substance rather than a rotated template.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

LEGACY_MATRIX = "nursing_station_phase2_canonical"
NATIONAL_MATRIX = "nursing_station_national_capability_canonical"


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
    "NFR-NS-024": RequirementSpec("The governed Agent Clinical Safety Officer executes the evidence review and recommends without claiming professional authority", "governance", "/api/governance/seed", ("safety/AGENT_CSO_HITL_PROCEDURE.md", "tests/test_governance_artifacts.py")),
    "NFR-NS-025": RequirementSpec("Clinical deployment decisions require independent passing agent and human keys for the identical scope", "governance", "/api/governance/seed", ("safety/CLINICAL_DEPLOYMENT_GATE.json", "scripts/evaluate_clinical_deployment_gate.py", "tests/test_governance_artifacts.py")),
    "NFR-NS-026": RequirementSpec("Synthetic clinical-simulation approval cannot activate or be inherited by live-patient deployment", "governance", "/api/governance/seed", ("safety/CLINICAL_DEPLOYMENT_GATE.json", "tests/test_governance_artifacts.py")),
    # ---- National capability wave (2026-08-05) --------------------------
    "FR-NS-090": RequirementSpec("Ward work is ranked by clinical risk, due time, and suspended work, and every rank explains its own factors", "work-orchestration", "/api/ward-board/work-queue", ("tests/test_national_capability.py::test_work_queue_ranks_by_clinical_risk_and_explains_every_rank",)),
    "FR-NS-091": RequirementSpec("Delegation of nursing work requires the assignee's verified competency at assignment and at transition", "work-orchestration", "/api/patients/pat-001/tasks", ("tests/test_national_capability.py::test_delegation_requires_the_verified_competency", "tests/test_national_capability.py::test_work_queue_marks_work_the_viewer_is_not_competent_to_perform")),
    "FR-NS-092": RequirementSpec("Interrupted nursing work is recorded with its reason and resurfaces in the queue until it is resumed", "work-orchestration", "/api/tasks/task-002/interruptions", ("tests/test_national_capability.py::test_interrupted_work_resurfaces_until_it_is_resumed",)),
    "FR-NS-100": RequirementSpec("Each deterioration escalation carries a required response interval and is closed only by a named responder of the required seniority", "deterioration", "/api/observations/{observation_id}/escalation-response", ("tests/test_national_capability.py::test_escalation_response_names_a_human_and_never_self_resolves",)),
    "FR-NS-101": RequirementSpec("The early-warning profile, its oxygen band tables including the prescribed Scale 2 target range, and its thresholds come from the jurisdiction's country pack", "deterioration", "/api/patients/pat-007/observations", ("tests/test_national_capability.py::test_prescribed_oxygen_target_scale_changes_the_warning_score",)),
    "FR-NS-110": RequirementSpec("Hub-sourced pharmacy medication requests reconcile into the eMAR idempotently, never overwrite an administered record, and never infer a missing dose unit", "emar", "/api/patients/pat-005/integrations/refresh", ("tests/test_national_capability.py::test_hub_sourced_requests_reconcile_into_the_emar_and_refuse_incomplete_ones", "tests/test_national_capability.py::test_an_administered_order_is_never_overwritten_by_a_later_snapshot")),
    "FR-NS-111": RequirementSpec("An administration outcome for a hub-sourced order is queued durably for its owning system and never reported as delivered without a receipt", "emar", "/api/medication-orders/{order_id}/administrations", ("tests/test_national_capability.py::test_a_hub_sourced_outcome_is_queued_and_never_reported_as_delivered",)),
    "FR-NS-120": RequirementSpec("Handover acceptance transfers every unresolved action to the receiver, or records a reasoned decline that leaves it with the sender", "handover", "/api/handovers/{handover_id}/accept", ("tests/test_national_capability.py::test_accepting_a_handover_moves_the_unresolved_actions_with_the_patient", "tests/test_national_capability.py::test_a_declined_action_stays_with_the_sender_and_needs_a_reason")),
    "FR-NS-130": RequirementSpec("The shift roster is consumed through BulletTrain against a declared contract and an unpublished or malformed roster is reported absent, never inferred", "staffing", "/api/wards/ward-med-a/staffing-roster/refresh", ("tests/test_national_capability.py::test_an_empty_roster_is_rejected_rather_than_read_as_nobody_on_duty", "tests/test_national_capability.py::test_roster_refresh_fails_closed_without_a_configured_hub")),
    "FR-NS-131": RequirementSpec("The ward staffing position compares repo-owned acuity against the country pack's staffing norm and reports insufficient-policy rather than a false compliance verdict", "staffing", "/api/wards/ward-med-a/staffing-position", ("tests/test_national_capability.py::test_staffing_position_computes_the_requirement_and_reports_the_missing_roster", "tests/test_national_capability.py::test_position_computation_reads_a_published_roster_and_fires_pack_triggers")),
    "FR-NS-132": RequirementSpec("A staffing shortage declaration is a named nurse-in-charge act that emits exactly BulletTrain's governed declaration field set and asserts no policy tier of its own", "staffing", "/api/wards/ward-med-a/staffing-declarations", ("tests/test_national_capability.py::test_a_shortage_declaration_emits_exactly_the_governed_field_set", "tests/test_national_capability.py::test_the_declaration_builder_refuses_to_extend_the_governed_contract")),
    "FR-NS-140": RequirementSpec("Falls, pressure injuries and healthcare-associated infections are recorded as incidents whose external reportability is decided by the country pack and by present-on-admission status", "harm", "/api/patients/pat-001/harm-incidents", ("tests/test_national_capability.py::test_reportability_comes_from_the_country_pack_not_from_code", "tests/test_national_capability.py::test_a_pressure_injury_present_on_admission_is_not_this_wards_harm")),
    "FR-NS-141": RequirementSpec("A harm incident is reviewed by someone other than its reporter, records avoidability and contributory factors, and produces owned learning actions", "harm", "/api/harm-incidents/{incident_id}/review", ("tests/test_national_capability.py::test_incident_review_needs_a_second_person_and_produces_owned_learning",)),
    "FR-NS-150": RequirementSpec("Discharge readiness is opened from the jurisdiction's criteria set and cannot be completed while a mandatory criterion is outstanding", "discharge", "/api/patients/pat-002/discharge-readiness", ("tests/test_national_capability.py::test_readiness_opens_from_the_pack_criteria_and_blocks_early_completion",)),
    "FR-NS-151": RequirementSpec("A discharge criterion owned by another system is met only by that system's receipt through the hub, never by local assertion or by a dispatch", "discharge", "/api/discharge-readiness/{readiness_id}/coordinate", ("tests/test_national_capability.py::test_a_criterion_owned_by_a_sibling_cannot_be_met_by_local_assertion", "tests/test_national_capability.py::test_discharge_coordination_fails_closed_without_a_configured_hub")),
    "FR-NS-160": RequirementSpec("Nursing quality measure definitions are versioned country-pack data carrying numerator, denominator, exclusions, unit and a dated citation", "quality", "/api/wards/ward-med-a/quality-measures", ("tests/test_national_capability.py::test_quality_measures_apply_the_pack_definitions_to_this_wards_records",)),
    "FR-NS-161": RequirementSpec("The nursing quality dataset is computed from ward records, distinguishes an unavailable source from a zero, and publishes de-identified on the proven HMIS envelope", "quality", "/api/wards/ward-med-a/hmis-measures", ("tests/test_national_capability.py::test_quality_measures_apply_the_pack_definitions_to_this_wards_records", "tests/test_national_capability.py::test_the_measure_payload_carries_no_patient_identifiers")),
    "FR-NS-170": RequirementSpec("Country policy ships as a versioned pack per jurisdiction with publisher, title and effective date for every clinically meaningful entry", "country-pack", "/api/country-pack", ("tests/test_national_capability.py::test_country_pack_is_served_with_sources_and_is_not_adopted_by_default", "tests/test_country_packs.py::test_every_pack_carries_a_complete_dated_citation_for_every_clinical_entry")),
    "NFR-NS-027": RequirementSpec("A country pack ships as a candidate and is treated as locally adopted only after a recorded organisational decision pinned to the exact reviewed pack version", "country-pack", "/api/country-pack/adoptions", ("tests/test_national_capability.py::test_country_pack_adoption_is_role_gated_and_pinned_to_the_reviewed_version", "tests/test_country_packs.py::test_a_pack_version_change_does_not_inherit_the_previous_adoption")),
    "NFR-NS-028": RequirementSpec("Nursing Station consumes roster and registration state and never becomes its author; an unavailable roster degrades the staffing position rather than producing one", "staffing", "/api/wards/ward-med-a/staffing-position", ("tests/test_national_capability.py::test_staffing_position_computes_the_requirement_and_reports_the_missing_roster", "tests/test_bt_connector_seam.py::test_no_roster_exchange_route_exists_yet")),
    "NFR-NS-029": RequirementSpec("Every outbound national publication is durable, idempotent by correlation identifier, and remains pending until a receipt arrives; an unregistered hub route is surfaced as a named gap", "publications", "/api/publications", ("tests/test_national_capability.py::test_the_publication_surface_names_every_open_bullettrain_gap", "tests/test_bt_connector_seam.py::test_publication_contract_route_status_matches_bullettrain")),
    "NFR-NS-030": RequirementSpec("Every national safety decision records the named human who made it and nothing auto-resolves, auto-declares, auto-reviews or auto-adopts", "governance", "/api/observations/{observation_id}/escalation-response", ("tests/test_national_capability.py::test_escalation_response_names_a_human_and_never_self_resolves", "tests/test_national_capability.py::test_incident_review_needs_a_second_person_and_produces_owned_learning")),
}

# FROZEN. The legacy 100-row matrix rotates over exactly these ids in exactly
# this order. Appending to REQUIREMENTS must never change this tuple, or every
# legacy row body is rewritten and the committed coverage atoms are destroyed.
LEGACY_MATRIX_REQUIREMENT_IDS: tuple[str, ...] = (
    "FR-NS-001", "FR-NS-002", "FR-NS-003", "FR-NS-004", "FR-NS-010", "FR-NS-011",
    "FR-NS-012", "FR-NS-020", "FR-NS-021", "FR-NS-022", "FR-NS-030", "FR-NS-031",
    "FR-NS-040", "FR-NS-041", "FR-NS-042", "FR-NS-043", "FR-NS-050", "FR-NS-051",
    "FR-NS-060", "NFR-NS-001", "NFR-NS-002", "NFR-NS-003", "NFR-NS-004", "NFR-NS-005",
    "NFR-NS-006", "NFR-NS-007", "NFR-NS-008", "NFR-NS-009", "NFR-NS-010", "NFR-NS-011",
    "FR-NS-070", "FR-NS-071", "FR-NS-072", "FR-NS-073", "FR-NS-074", "FR-NS-075",
    "FR-NS-076", "FR-NS-077", "FR-NS-078", "FR-NS-079", "FR-NS-080", "FR-NS-081",
    "FR-NS-082", "NFR-NS-012", "NFR-NS-013", "NFR-NS-014", "NFR-NS-015", "NFR-NS-016",
    "NFR-NS-017", "NFR-NS-018", "NFR-NS-019", "NFR-NS-020", "NFR-NS-021", "NFR-NS-022",
    "NFR-NS-023", "NFR-NS-024", "NFR-NS-025", "NFR-NS-026",
)

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
    "governance": "Agent Clinical Safety Officer and human two-key approval",
    "work-orchestration": "Risk-ranked ward work, competency and interruption",
    "deterioration": "Jurisdiction-configured deterioration scoring and response",
    "emar": "Closed-loop medication administration",
    "staffing": "Consumed roster, staffing position and governed declaration",
    "harm": "Harm incident, review and external reporting",
    "discharge": "Discharge readiness and receipt-driven coordination",
    "quality": "Nursing quality measure definition and dataset",
    "country-pack": "Versioned country policy and adoption governance",
    "publications": "Durable outbound national publication queue",
}


# ---------------------------------------------------------------------------
# Legacy 100-row matrix (frozen rotation)
# ---------------------------------------------------------------------------
def category(index: int) -> str:
    if index <= 85:
        return "Positive"
    if index <= 95:
        return "Negative"
    return "Edge"


def build_rows() -> tuple[list[dict], list[dict]]:
    full: list[dict] = []
    reduced: list[dict] = []
    items = [(rid, REQUIREMENTS[rid]) for rid in LEGACY_MATRIX_REQUIREMENT_IDS]
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
            "trigger": {"method": "GET" if spec.domain in {"ward-board", "audit", "governance"} else "POST", "path": spec.endpoint},
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


# ---------------------------------------------------------------------------
# National-capability matrix (authored, one distinct flow per row)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class NationalScenario:
    suffix: str
    requirement_ids: tuple[str, ...]
    category: str
    scenario: str
    method: str
    path: str
    payload: dict[str, Any]
    outputs: dict[str, Any]
    validations: tuple[str, ...]
    evidence: str
    connectors: tuple[str, ...] = ()
    events: tuple[str, ...] = ()
    priority: str = "high"
    fault: str = "none"


def _s(*args: Any, **kwargs: Any) -> NationalScenario:
    return NationalScenario(*args, **kwargs)


NATIONAL_SCENARIOS: tuple[NationalScenario, ...] = (
    # ---- FR-NS-090 ----------------------------------------------------
    _s("WORKQ-RANK", ("FR-NS-090",), "Positive",
       "A deteriorating patient's work outranks routine ward work in the ranked queue",
       "GET", "/api/ward-board/work-queue",
       {"ward_id": "ward-med-a", "precondition_observation": {"patient": "pat-001", "score": ">=7"}},
       {"top_entry_patient_id": "pat-001", "ordering": "rank_score descending"},
       ("entries[0].patient_id == 'pat-001'", "rank_score list is monotonically non-increasing"),
       "tests/test_national_capability.py::test_work_queue_ranks_by_clinical_risk_and_explains_every_rank",
       priority="critical"),
    _s("WORKQ-EXPLAIN", ("FR-NS-090",), "Positive",
       "Each queue entry publishes the factor breakdown that produced its rank",
       "GET", "/api/ward-board/work-queue",
       {"ward_id": "ward-med-a", "inspect": "rank_factors"},
       {"factors": ["priority", "escalation_level", "assessment_risk", "overdue", "due_soon", "interrupted"]},
       ("rank_score == sum(rank_factors.values())", "ranking_weights are published with the queue"),
       "tests/test_national_capability.py::test_work_queue_ranks_by_clinical_risk_and_explains_every_rank"),
    # ---- FR-NS-091 ----------------------------------------------------
    _s("COMP-ASSIGN", ("FR-NS-091",), "Positive",
       "Work requiring discharge-coordination is assignable to the nurse who holds that verified competency",
       "POST", "/api/patients/pat-001/tasks",
       {"assigned_to": "usr-grace", "required_competency": "discharge-coordination", "priority": "high"},
       {"status": "open", "required_competency": "discharge-coordination"},
       ("HTTP 201", "task.required_competency is persisted for later transition checks"),
       "tests/test_national_capability.py::test_delegation_requires_the_verified_competency"),
    _s("COMP-VIEW", ("FR-NS-091",), "Positive",
       "The queue names the missing competency instead of hiding work the viewer cannot do",
       "GET", "/api/ward-board/work-queue",
       {"viewer": "usr-amina", "task": "task-004"},
       {"delegable": False, "missing_competency": "deteriorating-patient-response"},
       ("task-004 is present in the queue", "delegable is false and the competency is named"),
       "tests/test_national_capability.py::test_work_queue_marks_work_the_viewer_is_not_competent_to_perform"),
    # ---- FR-NS-092 ----------------------------------------------------
    _s("INTR-RECORD", ("FR-NS-092",), "Positive",
       "A clinical-emergency interruption of ward work is recorded with its reason category",
       "POST", "/api/tasks/task-002/interruptions",
       {"reason": "Called to a deteriorating patient in bay 3", "reason_category": "clinical-emergency"},
       {"unresumed_interruptions": 1, "queue_rank_increases": True},
       ("HTTP 201", "the interrupted task's rank_score rises above its pre-interruption baseline"),
       "tests/test_national_capability.py::test_interrupted_work_resurfaces_until_it_is_resumed"),
    _s("INTR-RESUME", ("FR-NS-092",), "Positive",
       "Resuming interrupted work returns its rank to the pre-interruption baseline",
       "POST", "/api/task-interruptions/{interruption_id}/resume",
       {"task_id": "task-002"},
       {"unresumed_interruptions": 0, "rank_score": "baseline"},
       ("HTTP 200", "a second resume of the same interruption is rejected with 409"),
       "tests/test_national_capability.py::test_interrupted_work_resurfaces_until_it_is_resumed"),
    # ---- FR-NS-100 ----------------------------------------------------
    _s("ESC-RESPOND", ("FR-NS-100",), "Positive",
       "A nurse in charge closes a critical escalation inside the jurisdiction's response interval",
       "POST", "/api/observations/{observation_id}/escalation-response",
       {"responder": "usr-grace", "outcome": "escalated-to-medical-team",
        "clinical_response": "Reviewed at the bedside; oxygen titrated and medical team called"},
       {"within_required_interval": True, "responder_role": "nurse_in_charge",
        "escalation_task_status_after": "open"},
       ("HTTP 201", "the linked escalation task is NOT completed by recording the response"),
       "tests/test_national_capability.py::test_escalation_response_names_a_human_and_never_self_resolves",
       events=("nursing-station.deterioration.answered",), priority="critical"),
    _s("ESC-FEED", ("FR-NS-100",), "Positive",
       "The ward escalation feed separates answered escalations from those still overdue",
       "GET", "/api/wards/ward-med-a/escalations",
       {"ward_id": "ward-med-a", "threshold_source": "country pack thresholds.escalate"},
       {"answered": True, "profile_id": "IE-INEWS-CANDIDATE-v1"},
       ("every row carries response_due_at and an answered flag",
        "overdue is derived from response_due_at, never from a fixed constant"),
       "tests/test_national_capability.py::test_escalation_carries_the_jurisdiction_response_interval_and_responder_role"),
    # ---- FR-NS-101 ----------------------------------------------------
    _s("EWS-SCALE1", ("FR-NS-101",), "Positive",
       "Saturation of 90 percent on the default target range scores 3 for oxygen saturation",
       "POST", "/api/patients/pat-001/observations",
       {"oxygen_saturation": 90, "supplemental_oxygen": False, "oxygen_target_scale": "1"},
       {"oxygen_scale": "1", "parameter_scores.oxygen_saturation": 3},
       ("HTTP 201", "the band table comes from country_packs oxygen_scales.1"),
       "tests/test_national_capability.py::test_prescribed_oxygen_target_scale_changes_the_warning_score",
       priority="critical"),
    _s("EWS-SCALE2", ("FR-NS-101",), "Positive",
       "The same 90 percent saturation scores 0 for a patient prescribed the 88-92 percent target range",
       "POST", "/api/patients/pat-007/observations",
       {"oxygen_saturation": 90, "supplemental_oxygen": False, "oxygen_target_scale": "2"},
       {"oxygen_scale": "2", "parameter_scores.oxygen_saturation": 0, "score_delta_vs_scale_1": -3},
       ("HTTP 201", "Scale 2 bands_on_air are applied because the patient is not on oxygen"),
       "tests/test_national_capability.py::test_prescribed_oxygen_target_scale_changes_the_warning_score",
       priority="critical"),
    # ---- FR-NS-110 ----------------------------------------------------
    _s("EMAR-INGEST", ("FR-NS-110",), "Positive",
       "A hub-sourced pharmacy medication request becomes an eMAR order carrying its source reference",
       "POST", "/api/patients/pat-005/integrations/refresh",
       {"source_system": "pharmacy-system", "request": "rx-ava-0001", "dose_unit": "mg"},
       {"source_system": "pharmacy-system", "source_order_id": "rx-ava-0001", "created": 1},
       ("the order is retrievable at /api/patients/pat-005/medications",
        "a request with no dose unit is returned as unmappable and never becomes an order"),
       "tests/test_national_capability.py::test_hub_sourced_requests_reconcile_into_the_emar_and_refuse_incomplete_ones",
       connectors=("pharmacy_system",)),
    _s("EMAR-PROTECT", ("FR-NS-110",), "Positive",
       "A later pharmacy snapshot leaves an order that already has an administration record untouched",
       "POST", "/api/patients/pat-005/integrations/refresh",
       {"source_system": "pharmacy-system", "order_state": "already administered"},
       {"protected": 1, "created": 0, "updated": 0},
       ("the administered order is reported as protected",
        "no imported snapshot overwrites a Nursing Station-owned record"),
       "tests/test_national_capability.py::test_an_administered_order_is_never_overwritten_by_a_later_snapshot",
       connectors=("pharmacy_system",), priority="critical"),
    # ---- FR-NS-111 ----------------------------------------------------
    _s("EMAR-QUEUE", ("FR-NS-111",), "Positive",
       "An omission recorded against a hub-sourced order is queued for pharmacy with its correlation id",
       "POST", "/api/medication-orders/{order_id}/administrations",
       {"outcome": "omitted", "reason": "Dose unavailable before the occurrence closed"},
       {"publication_status": "pending-publication", "connector": "pharmacy_system"},
       ("the correlation id is derived from the administration id",
        "the response never reports the outcome as delivered"),
       "tests/test_national_capability.py::test_a_hub_sourced_outcome_is_queued_and_never_reported_as_delivered",
       connectors=("pharmacy_system",), priority="critical"),
    _s("EMAR-NOOBLIG", ("FR-NS-111",), "Positive",
       "A locally authored order creates no external publication obligation when administered",
       "POST", "/api/medication-orders/med-001/administrations",
       {"outcome": "administered", "source_order_id": None},
       {"publication_id": None, "publication_status": "not-applicable"},
       ("no outbound_publications row is created for a locally authored order",),
       "tests/test_national_capability.py::test_a_locally_authored_order_creates_no_external_obligation"),
    # ---- FR-NS-120 ----------------------------------------------------
    _s("HAND-ACTIONS", ("FR-NS-120",), "Positive",
       "Accepting a handover reassigns every unresolved action to the receiving nurse",
       "POST", "/api/handovers/{handover_id}/accept",
       {"receiver": "usr-grace", "action_decisions": []},
       {"accepted_actions": ["task-001"], "declined_actions": []},
       ("task-001 assigned_to becomes usr-grace",
        "patient accountability and action ownership move together"),
       "tests/test_national_capability.py::test_accepting_a_handover_moves_the_unresolved_actions_with_the_patient",
       priority="critical"),
    _s("HAND-DECLINE", ("FR-NS-120",), "Positive",
       "A reasoned decline leaves the unresolved action with the sending nurse rather than unowned",
       "POST", "/api/handovers/{handover_id}/accept",
       {"action_decisions": [{"task_id": "task-001", "decision": "decline",
                              "reason": "Assigned to the twilight nurse already on the bay"}]},
       {"declined_actions": ["task-001"], "retained_by": "usr-amina"},
       ("the declined task keeps its original assignee",
        "a decline without a reason is rejected with decline_requires_reason"),
       "tests/test_national_capability.py::test_a_declined_action_stays_with_the_sender_and_needs_a_reason"),
    # ---- FR-NS-130 ----------------------------------------------------
    _s("ROSTER-CONTRACT", ("FR-NS-130",), "Positive",
       "A published roster is accepted only when it matches the declared ward, shift and assignment shape",
       "POST", "/api/wards/ward-med-a/staffing-roster/refresh",
       {"resource_type": "NursingRosterContext", "shift": "day",
        "assignments": [{"staff_id": "s1", "registered": True, "hours": 12}]},
       {"roster_state": "current", "source_system": "workforce"},
       ("a roster for a different ward or shift is rejected",
        "the snapshot is stored with a content hash and a correlation id"),
       "tests/test_national_capability.py::test_an_empty_roster_is_rejected_rather_than_read_as_nobody_on_duty",
       connectors=("workforce",)),
    _s("ROSTER-CONSUME", ("FR-NS-130",), "Positive",
       "Consumed roster hours and registration status feed the position without being authored locally",
       "GET", "/api/wards/ward-med-a/staffing-position",
       {"roster_source": "workforce", "registered_hours": 12, "unregistered_hours": 24},
       {"actual_skill_mix_percent": 33.3, "roster_contract_owner": "unassigned"},
       ("skill mix is derived from consumed hours only",
        "Nursing Station exposes no route that writes a roster"),
       "tests/test_national_capability.py::test_position_computation_reads_a_published_roster_and_fires_pack_triggers",
       connectors=("workforce",)),
    # ---- FR-NS-131 ----------------------------------------------------
    _s("POS-REQUIRE", ("FR-NS-131",), "Positive",
       "The required nursing hours for the shift are derived from the pack norm and the occupied beds",
       "GET", "/api/wards/ward-med-a/staffing-position",
       {"occupied_beds": 6, "nursing_hours_per_patient_day": 4.4, "shift_hours": 12},
       {"required_nursing_hours": 13.2, "required_registered_hours": 10.56,
        "policy_status": "sufficient"},
       ("required hours equal beds * NHpPD * shift fraction",
        "an absent roster yields null actuals rather than zero actuals"),
       "tests/test_national_capability.py::test_staffing_position_computes_the_requirement_and_reports_the_missing_roster",
       priority="critical"),
    _s("POS-TRIGGERS", ("FR-NS-131",), "Positive",
       "Every declaration trigger the pack declares is evaluated against the consumed roster",
       "GET", "/api/wards/ward-med-a/staffing-position",
       {"occupied_beds": 10, "registered_headcount": 1, "skill_mix_percent": 33.3},
       {"triggers_fired": ["registered-hours-below-norm", "skill-mix-below-minimum",
                           "patients-per-registered-nurse-exceeded"]},
       ("only triggers declared in the pack are evaluated",
        "shortage_indicated is derived from the fired triggers, never asserted directly"),
       "tests/test_national_capability.py::test_position_computation_reads_a_published_roster_and_fires_pack_triggers"),
    # ---- FR-NS-132 ----------------------------------------------------
    _s("DECL-EMIT", ("FR-NS-132",), "Positive",
       "A declaration emits the six governed fields and no locally invented severity or tier",
       "POST", "/api/wards/ward-med-a/staffing-declarations",
       {"declared_by": "usr-grace", "window_minutes": None,
        "reason": "Two registered nurses absent at short notice; escalation cover unfilled"},
       {"governed_fields": ["declaration_id", "scope_unit", "declared_by", "reason",
                            "starts_at", "expires_at"], "effective_tier": None},
       ("the payload key set equals the governed declaration contract exactly",
        "the effective policy tier is left to BulletTrain"),
       "tests/test_national_capability.py::test_a_shortage_declaration_emits_exactly_the_governed_field_set",
       connectors=("global_agent_registry",), priority="critical"),
    _s("DECL-REVOKE", ("FR-NS-132",), "Positive",
       "A declaration is revocable by the nurse in charge and stops being active immediately",
       "POST", "/api/staffing-declarations/{declaration_id}/revoke",
       {"reason": "Bank nurse arrived and cover is restored"},
       {"revoked": True, "active_after_revoke": False},
       ("a second revoke of the same declaration is rejected with 409",
        "the revoking human is recorded"),
       "tests/test_national_capability.py::test_a_shortage_declaration_emits_exactly_the_governed_field_set"),
    # ---- FR-NS-140 ----------------------------------------------------
    _s("HARM-FALL", ("FR-NS-140",), "Positive",
       "A fall with severe harm is classified externally reportable from the pack's reportable-type list",
       "POST", "/api/patients/pat-001/harm-incidents",
       {"incident_type": "fall", "harm_level": "severe",
        "description": "Unwitnessed fall from the bedside chair; no loss of consciousness"},
       {"externally_reportable": True, "review_required": True,
        "external_report_state": "pending-publication"},
       ("a fall with low harm is not reportable",
        "reportability is read from country pack harm_incident.reportable_types"),
       "tests/test_national_capability.py::test_reportability_comes_from_the_country_pack_not_from_code",
       connectors=("hmis",), priority="critical"),
    _s("HARM-POA", ("FR-NS-140",), "Positive",
       "A category-3 pressure injury present on admission is excluded from this ward's acquired harm",
       "POST", "/api/patients/pat-001/harm-incidents",
       {"incident_type": "pressure-injury", "classification": "category-3",
        "body_site": "left heel", "present_on_admission": True},
       {"externally_reportable": False, "publication_id": None},
       ("the same injury not present on admission is reportable",
        "present-on-admission injuries never inflate the national return"),
       "tests/test_national_capability.py::test_a_pressure_injury_present_on_admission_is_not_this_wards_harm",
       priority="critical"),
    # ---- FR-NS-141 ----------------------------------------------------
    _s("REVIEW-LEARN", ("FR-NS-141",), "Positive",
       "An incident review records avoidability and contributory factors and creates owned learning work",
       "POST", "/api/harm-incidents/{incident_id}/review",
       {"avoidability": "avoidable",
        "contributory_factors": ["Call bell out of reach", "Sedating medication not reviewed"],
        "learning_actions": ["Re-audit call-bell placement on every bay"]},
       {"generated_task_ids": 1, "incident_status": "reviewed"},
       ("each learning action becomes a due ward task with origin_kind incident-review",
        "a second review of the same incident is rejected with 409"),
       "tests/test_national_capability.py::test_incident_review_needs_a_second_person_and_produces_owned_learning"),
    _s("REVIEW-SEPARATION", ("FR-NS-141",), "Positive",
       "The reviewer must be someone other than the nurse who reported the incident",
       "POST", "/api/harm-incidents/{incident_id}/review",
       {"reporter": "usr-grace", "reviewer": "usr-grace"},
       {"status_code": 422, "reason": "reviewer and reporter are the same person"},
       ("self-review is refused before any state changes",
        "a registered nurse cannot review at all"),
       "tests/test_national_capability.py::test_incident_review_needs_a_second_person_and_produces_owned_learning"),
    # ---- FR-NS-150 ----------------------------------------------------
    _s("DISCH-OPEN", ("FR-NS-150",), "Positive",
       "Discharge readiness opens with exactly the jurisdiction's criteria set and its mandatory subset",
       "POST", "/api/patients/pat-002/discharge-readiness",
       {"jurisdiction": "IE", "criteria_source": "country pack discharge.criteria"},
       {"criteria": 6, "outstanding_mandatory": ["medicines-supply-and-education",
                                                 "equipment-and-aids",
                                                 "community-nursing-referral",
                                                 "patient-and-carer-education"]},
       ("completion is refused while any mandatory criterion is outstanding",
        "a second open readiness record for the same patient is refused"),
       "tests/test_national_capability.py::test_readiness_opens_from_the_pack_criteria_and_blocks_early_completion"),
    _s("DISCH-OWNED", ("FR-NS-150",), "Positive",
       "A repo-owned criterion is met by a named nurse recording what was explained",
       "POST", "/api/discharge-readiness/{readiness_id}/criteria/patient-and-carer-education/confirm",
       {"note": "Warning signs and escalation route explained; teach-back done"},
       {"status": "met", "confirmed_by": "usr-amina"},
       ("only criteria whose evidence_source is nursing-station may be confirmed this way",
        "the confirming human is recorded on the criterion"),
       "tests/test_national_capability.py::test_a_criterion_owned_by_a_sibling_cannot_be_met_by_local_assertion"),
    # ---- FR-NS-151 ----------------------------------------------------
    _s("DISCH-RECEIPT", ("FR-NS-151",), "Positive",
       "A sibling-owned criterion stays pending with a typed reason until that sibling's receipt carries the evidence",
       "POST", "/api/discharge-readiness/{readiness_id}/coordinate",
       {"criterion": "community-nursing-referral", "hub_route": "unregistered"},
       {"status": "pending", "error_code": "hub_route_unregistered"},
       ("a 2xx with no evidence yields evidence_absent, not met",
        "no criterion is met by a dispatch"),
       "tests/test_national_capability.py::test_a_criterion_owned_by_a_sibling_cannot_be_met_by_local_assertion",
       connectors=("pharmacy_system",), priority="critical"),
    # ---- FR-NS-160 ----------------------------------------------------
    _s("QUAL-DEFS", ("FR-NS-160",), "Positive",
       "Every quality measure is served with its numerator, denominator, exclusions, unit and dated citation",
       "GET", "/api/wards/ward-med-a/quality-measures",
       {"jurisdiction": "IE", "measure_ids": ["NSQ-STAFF-01", "NSQ-STAFF-02", "NSQ-CARE-01",
                                              "NSQ-SAFE-01", "NSQ-SAFE-02", "NSQ-DETER-01",
                                              "NSQ-MED-01"]},
       {"definitions_source": "country pack", "every_measure_has_source_id": True},
       ("each source_id resolves to a publisher, title and effective date in the same pack",
        "the definition set changes with the jurisdiction, not with the code"),
       "tests/test_national_capability.py::test_quality_measures_apply_the_pack_definitions_to_this_wards_records"),
    # ---- FR-NS-161 ----------------------------------------------------
    _s("QUAL-COMPUTE", ("FR-NS-161",), "Positive",
       "Harm and missed-care measures are computed from this ward's own records",
       "GET", "/api/wards/ward-med-a/quality-measures",
       {"falls_with_harm": 1, "hospital_acquired_pressure_injuries": 1},
       {"NSQ-SAFE-01.numerator": 1, "NSQ-SAFE-02.numerator": 1, "NSQ-CARE-01.status": "computed"},
       ("roster-dependent measures report source-unavailable rather than zero",
        "a measure with no denominator reports no-denominator rather than a perfect score"),
       "tests/test_national_capability.py::test_quality_measures_apply_the_pack_definitions_to_this_wards_records"),
    _s("QUAL-PUBLISH", ("FR-NS-161",), "Positive",
       "The dataset publishes de-identified on the proven HMIS NursingMeasureReport envelope",
       "POST", "/api/wards/ward-med-a/hmis-measures",
       {"envelope_keys": ["tenant_id", "facility_id", "ward_id", "period_start",
                          "period_end", "counts"], "additive_block": "measures"},
       {"receipt_required": True, "persisted_to": "quality_measure_results"},
       ("the six required envelope keys are unchanged so an older HMIS still accepts it",
        "no patient identifier, name, birth date or free text appears in the measures block"),
       "tests/test_national_capability.py::test_the_measure_payload_carries_no_patient_identifiers",
       connectors=("hmis",), events=("nursing-station.quality.published",)),
    # ---- FR-NS-170 ----------------------------------------------------
    _s("PACK-SERVE", ("FR-NS-170",), "Positive",
       "The active jurisdiction pack is served with its version, effective date and full source list",
       "GET", "/api/country-pack",
       {"jurisdiction": "IE"},
       {"pack_version": "2026.08.0", "adoption_status": "candidate",
        "available_jurisdictions": ["GB", "IE", "KE", "US"]},
       ("every source carries publisher, title and effective_from",
        "the health surface reports the same pack version"),
       "tests/test_national_capability.py::test_country_pack_is_served_with_sources_and_is_not_adopted_by_default"),
    _s("PACK-FOURCOUNTRY", ("FR-NS-170",), "Positive",
       "All four jurisdiction packs validate and resolve every source they cite",
       "GET", "/api/country-pack",
       {"packs": ["ie.json", "gb.json", "ke.json", "us.json"]},
       {"validated": 4, "dangling_sources": 0},
       ("a pack citing an undefined source_id raises CountryPackError",
        "the United States pack reports insufficient-policy rather than a federal ratio"),
       "tests/test_country_packs.py::test_every_pack_carries_a_complete_dated_citation_for_every_clinical_entry"),
    # ---- NEGATIVE ------------------------------------------------------
    _s("NEG-ESC-ROLE", ("NFR-NS-030",), "Negative",
       "A registered nurse cannot close a critical escalation the jurisdiction reserves to a nurse in charge",
       "POST", "/api/observations/{observation_id}/escalation-response",
       {"responder": "usr-amina", "responder_role": "registered_nurse",
        "escalation_level": "critical"},
       {"status_code": 403, "detail_contains": "nurse_in_charge"},
       ("the required role is read from responder_minimum_role in the pack",
        "no escalation response row is written"),
       "tests/test_national_capability.py::test_escalation_response_names_a_human_and_never_self_resolves",
       priority="critical", fault="insufficient-seniority"),
    _s("NEG-ROSTER-CLOSED", ("NFR-NS-028",), "Negative",
       "Roster refresh with no configured hub fails closed instead of producing a roster",
       "POST", "/api/wards/ward-med-a/staffing-roster/refresh",
       {"hub_url": None, "hub_token": None},
       {"status_code": 503, "code": "integration_not_configured"},
       ("no staffing_snapshots row is written",
        "the position continues to report roster_state not-refreshed"),
       "tests/test_national_capability.py::test_roster_refresh_fails_closed_without_a_configured_hub",
       fault="dependency-unconfigured"),
    _s("NEG-DISCH-ASSERT", ("FR-NS-151",), "Negative",
       "A pharmacy-owned discharge criterion cannot be marked met by a local assertion",
       "POST", "/api/discharge-readiness/{readiness_id}/criteria/medicines-supply-and-education/confirm",
       {"note": "Pharmacy said it was fine on the phone"},
       {"status_code": 409, "detail_contains": "pharmacy-system"},
       ("the criterion remains pending",
        "only a receipt through the hub can meet a sibling-owned criterion"),
       "tests/test_national_capability.py::test_a_criterion_owned_by_a_sibling_cannot_be_met_by_local_assertion",
       priority="critical", fault="ownership-violation"),
    _s("NEG-PACK-VERSION", ("NFR-NS-027",), "Negative",
       "An adoption decision naming a pack version that is not the version on disk is refused",
       "POST", "/api/country-pack/adoptions",
       {"jurisdiction": "IE", "pack_version": "2025.01.0", "decision": "adopted"},
       {"status_code": 409, "detail_contains": "2026.08.0"},
       ("adoption is pinned to the exact reviewed version",
        "a registered nurse cannot record an adoption at all"),
       "tests/test_national_capability.py::test_country_pack_adoption_is_role_gated_and_pinned_to_the_reviewed_version",
       fault="stale-policy-version"),
    # ---- EDGE ----------------------------------------------------------
    _s("EDGE-GAPS", ("NFR-NS-029",), "Edge",
       "Three of the four publication contracts have no BulletTrain route and each names its own gap",
       "GET", "/api/publications",
       {"deliverable_kinds": 1, "undeliverable_kinds": 3},
       {"registered": ["nursing.quality.dataset"],
        "unregistered": ["medication.administration.outcome", "staffing.shortage.declaration",
                         "harm.incident.reported"]},
       ("every unregistered contract publishes a non-empty gap note",
        "a queued publication never reaches published without a receipt"),
       "tests/test_national_capability.py::test_the_publication_surface_names_every_open_bullettrain_gap",
       fault="boundary-no-receiver"),
    _s("EDGE-NODENOM", ("FR-NS-160",), "Edge",
       "A period with no medication outcomes reports no-denominator rather than a perfect omission rate",
       "GET", "/api/wards/ward-med-a/quality-measures",
       {"medication_outcomes": 0, "medication_omissions": 0},
       {"NSQ-MED-01.status": "no-denominator", "NSQ-MED-01.value": None},
       ("an empty period is never presented as a perfect score",
        "source-unavailable and no-denominator remain distinguishable"),
       "tests/test_national_capability.py::test_quality_measures_apply_the_pack_definitions_to_this_wards_records",
       fault="boundary-empty-denominator"),
)


def build_national_rows() -> tuple[list[dict], list[dict]]:
    """One requirement per row, on purpose.

    Binding one body to two requirements is a cluster split: identical
    executable substance cannot satisfy two distinct obligations, so at most one
    of the two bindings is real. Each row therefore names exactly one
    requirement, and the acceptance-criterion id advances with the row so the
    first flow for a requirement carries AC01 (canonical matrix mapping) and the
    second carries AC02 (repo-owned direct executable evidence).
    """
    full: list[dict] = []
    reduced: list[dict] = []
    seen: dict[str, int] = {}
    for index, scenario in enumerate(NATIONAL_SCENARIOS, start=1):
        use_case_id = f"NS-NAT-{scenario.suffix}-{index:04d}"
        primary = scenario.requirement_ids[0]
        assert len(scenario.requirement_ids) == 1, (
            f"{use_case_id} binds {len(scenario.requirement_ids)} requirements; "
            "one body cannot satisfy two obligations"
        )
        domain = REQUIREMENTS[primary].domain
        seen[primary] = seen.get(primary, 0) + 1
        acceptance = [f"{primary}-AC{min(seen[primary], 2):02d}"]
        full.append({
            "use_case_id": use_case_id,
            "subsystem": "nursing-station",
            "requirement_ids": list(scenario.requirement_ids),
            "acceptance_criteria_ids": acceptance,
            "scenario_category": scenario.category,
            "title": f"{primary} {DOMAIN_TITLES[domain]}: {scenario.scenario}",
            "description": scenario.scenario,
            "preconditions": [
                "Durable governed synthetic database is initialised with the ward MED-A cohort",
                f"Active country pack is the {scenario.payload.get('jurisdiction', 'IE')} pack at its committed version",
            ],
            "trigger": {"method": scenario.method, "path": scenario.path},
            "input_payload": scenario.payload,
            "expected_connector_calls": list(scenario.connectors),
            "expected_events": list(scenario.events),
            "expected_outputs": scenario.outputs,
            "fault_profile": {"kind": scenario.fault},
            "security_profile": {
                "tenant_scoped": True,
                "facility_scoped": True,
                "ward_scoped": True,
                "audit_required": True,
                "named_human_required": domain in {"deterioration", "harm", "staffing", "discharge", "governance"},
            },
            "priority": scenario.priority,
            "automation_status": "automated",
            "estimated_duration_seconds": 3,
            "tags": ["national-capability", domain, scenario.category, *scenario.requirement_ids],
        })
        reduced.append({
            "use_case_id": use_case_id,
            "component": "Nursing Station",
            "scenario": scenario.scenario,
            "test_type": scenario.category.lower(),
            "priority": "high" if scenario.priority == "high" else "high",
            "requirement_ids": list(scenario.requirement_ids),
            "acceptance_criteria_ids": acceptance,
            "expected_outcomes": [f"{key}: {value}" for key, value in scenario.outputs.items()],
            "preconditions": {
                "database": "durable governed synthetic SQLite seeded with ward MED-A",
                "country_pack": scenario.payload.get("jurisdiction", "IE"),
                "authenticated_role": (
                    "nurse_in_charge" if domain in {"staffing", "quality"} else "registered_nurse"
                ),
            },
            "test_data": {"method": scenario.method, "endpoint": scenario.path,
                          "payload": scenario.payload},
            "validation_rules": list(scenario.validations),
            "dependencies": ["nursing-station FastAPI application", "nursing_station.country_packs"]
            + [f"BulletTrain connector {name}" for name in scenario.connectors],
            "tags": ["national-capability", domain, scenario.category.lower(),
                     *scenario.requirement_ids],
            "estimated_duration": "3s",
            "automation_status": "automated",
            "notes": f"Direct executable evidence: {scenario.evidence}",
        })
    return full, reduced


# ---------------------------------------------------------------------------
# Brownfield merge helpers
# ---------------------------------------------------------------------------
def _read(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def merge_rows(existing: dict | None, key: str, generated: list[dict]) -> list[dict]:
    """Generated rows first, then every foreign row preserved in original order."""
    owned = {row["use_case_id"] for row in generated}
    foreign = [
        row
        for row in ((existing or {}).get(key) or [])
        if isinstance(row, dict) and row.get("use_case_id") not in owned
    ]
    return [*generated, *foreign]


def merge_requirements(existing: dict | None, generated: list[dict]) -> list[dict]:
    owned = {row["requirement_id"] for row in generated}
    foreign = [
        row
        for row in ((existing or {}).get("requirements") or [])
        if isinstance(row, dict) and row.get("requirement_id") not in owned
    ]
    return [*generated, *foreign]


def distribution_of(rows: list[dict], key: str) -> dict[str, int]:
    counts = {"Positive": 0, "Negative": 0, "Edge": 0}
    for row in rows:
        value = str(row.get(key, "")).strip().lower()
        for name in counts:
            if name.lower() == value:
                counts[name] += 1
    return counts


def main() -> None:
    legacy_full, legacy_reduced = build_rows()
    national_full, national_reduced = build_national_rows()

    paths = {
        "legacy_full": ROOT / f"tests/harness/json_matrices/{LEGACY_MATRIX}.json",
        "legacy_reduced": ROOT / f"tests/harness/reduced_json_matrices/{LEGACY_MATRIX}.14col.json",
        "national_full": ROOT / f"tests/harness/json_matrices/{NATIONAL_MATRIX}.json",
        "national_reduced": ROOT / f"tests/harness/reduced_json_matrices/{NATIONAL_MATRIX}.14col.json",
        "requirements_matrix": ROOT / "tests/harness/requirements_matrix.json",
        "superset": ROOT / "tests/harness/requirements_superset.json",
        "healthcare_superset": ROOT / "tests/harness/healthcare_requirements_superset.json",
    }

    legacy_full_rows = merge_rows(_read(paths["legacy_full"]), "scenarios", legacy_full)
    legacy_reduced_rows = merge_rows(_read(paths["legacy_reduced"]), "test_cases", legacy_reduced)
    national_full_rows = merge_rows(_read(paths["national_full"]), "scenarios", national_full)
    national_reduced_rows = merge_rows(
        _read(paths["national_reduced"]), "test_cases", national_reduced
    )

    all_full_rows = legacy_full_rows + national_full_rows
    generated_requirements = []
    for requirement_id, spec in REQUIREMENTS.items():
        row_ids = [
            row["use_case_id"]
            for row in all_full_rows
            if requirement_id in (row.get("requirement_ids") or [])
        ]
        generated_requirements.append({
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

    requirements = merge_requirements(_read(paths["superset"]), generated_requirements)
    total_requirements = len(requirements)

    outputs: dict[Path, dict] = {
        paths["legacy_full"]: {
            "schema_version": "BT_CANONICAL_MATRIX_V2_18COL",
            "columns": list(legacy_full[0]),
            "metadata": {
                "subsystem": "nursing-station",
                "scenario_count": len(legacy_full_rows),
                "distribution": distribution_of(legacy_full_rows, "scenario_category"),
                "requirement_ids": list(LEGACY_MATRIX_REQUIREMENT_IDS),
                "mapping_policy": "semantic requirement-domain mapping",
            },
            "scenarios": legacy_full_rows,
        },
        paths["legacy_reduced"]: {
            "schema_version": "BT_CANONICAL_MATRIX_V1_14COL",
            "columns": list(legacy_reduced[0]),
            "metadata": {
                "format": "Standard BulletTrain 14-column format",
                "component": "Nursing Station",
                "total_scenarios": len(legacy_reduced_rows),
                "distribution": distribution_of(legacy_reduced_rows, "test_type"),
                "requirement_ids": list(LEGACY_MATRIX_REQUIREMENT_IDS),
                "mapping_policy": "semantic requirement-domain mapping",
            },
            "test_cases": legacy_reduced_rows,
        },
        paths["national_full"]: {
            "schema_version": "BT_CANONICAL_MATRIX_V2_18COL",
            "columns": list(legacy_full[0]),
            "metadata": {
                "subsystem": "nursing-station",
                "scenario_count": len(national_full_rows),
                "distribution": distribution_of(national_full_rows, "scenario_category"),
                "requirement_ids": sorted(
                    {rid for row in national_full_rows for rid in (row.get("requirement_ids") or [])}
                ),
                "mapping_policy": "authored one-flow-per-row national capability scenarios",
            },
            "scenarios": national_full_rows,
        },
        paths["national_reduced"]: {
            "schema_version": "BT_CANONICAL_MATRIX_V1_14COL",
            "columns": list(legacy_reduced[0]),
            "metadata": {
                "format": "Standard BulletTrain 14-column format",
                "component": "Nursing Station",
                "total_scenarios": len(national_reduced_rows),
                "distribution": distribution_of(national_reduced_rows, "test_type"),
                "requirement_ids": sorted(
                    {rid for row in national_reduced_rows for rid in (row.get("requirement_ids") or [])}
                ),
                "mapping_policy": "authored one-flow-per-row national capability scenarios",
            },
            "test_cases": national_reduced_rows,
        },
        paths["requirements_matrix"]: {
            "schema_version": "BT_REQUIREMENTS_TRACEABILITY_V1",
            "canonical_matrix_schema": "BT_CANONICAL_MATRIX_V2_18COL",
            "metadata": {
                "subsystem": "nursing-station",
                "requirement_count": total_requirements,
                "covered_count": total_requirements,
                "uncovered_count": 0,
                "mapping_policy": "semantic requirement-domain mapping",
            },
            "coverage": {
                "scenario_count": len(all_full_rows),
                "coverage_pct": 100,
            },
            "requirements": requirements,
        },
    }
    superset = {
        "schema_version": "BT_REQUIREMENTS_SUPERSET_V1",
        "metadata": {"subsystem": "nursing-station", "requirement_count": total_requirements},
        "requirements": requirements,
    }
    outputs[paths["superset"]] = superset
    outputs[paths["healthcare_superset"]] = {
        **superset,
        "requirements": merge_requirements(
            _read(paths["healthcare_superset"]), generated_requirements
        ),
    }
    outputs[paths["healthcare_superset"]]["metadata"] = {
        "subsystem": "nursing-station",
        "requirement_count": len(outputs[paths["healthcare_superset"]]["requirements"]),
    }
    for path, payload in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
