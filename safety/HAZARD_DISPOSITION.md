# Phase 1 hazard disposition

This record maps the CSAA seed hazards to Phase 1 controls and executable evidence. `mitigated` means that the software controls have evidence; it does not mean that clinical release is approved. Human approval remains a separate gate.

## HZ-CLIN-001: patient context

Tenant and ward scope are enforced on every patient lookup. The persistent patient banner carries name, MRN, date of birth, allergy state, escalation status, and bed context. Medication recording requires MRN and date-of-birth verification. Evidence: `tests/test_api.py::test_ward_board_is_ward_scoped`, `tests/test_api.py::test_patient_access_cannot_cross_ward`, `tests/test_api.py::test_medication_rejects_wrong_patient_identifiers`, and `frontend/e2e/nursing-station.spec.ts`.

## HZ-CLIN-002: stale data

Phase 1 has no upstream clinical cache or offline fallback. Mutations are committed to the durable store before success is returned, and the client invalidates the affected React Query state after changes. Phase 2 contracts require freshness and provenance to be designed and tested before an upstream source becomes authoritative. Evidence: `docs/PHASE2_INTEGRATION_CONTRACTS.md`, `tests/test_api.py::test_health_reports_durable_phase_boundary`, and `frontend/src/App.tsx`.

## HZ-CLIN-003: downstream failure

Phase 1 contains no downstream clinical-service client and reports integrations as not implemented. No permissive fallback exists. Phase 2 must add explicit fail-closed and degraded-state behaviour with direct service evidence. Evidence: `docs/PHASE2_INTEGRATION_CONTRACTS.md`, `tests/test_api.py::test_health_reports_durable_phase_boundary`, and the CAID integration scan.

## HZ-CLIN-004: clinical text integrity

Pydantic enforces declared lengths before storage. SQLite stores text without a narrower VARCHAR boundary. The API test rejects oversized clinical text and verifies a Unicode-bearing goal round trip. Evidence: `tests/test_api.py::test_clinical_text_rejects_oversize_and_preserves_unicode`.

## HZ-CLIN-005: duplicate identity

Phase 1 seeds stable patient identifiers, scopes records by tenant and ward, and never performs probabilistic identity merging. Medication recording requires two identifiers. Enterprise master-patient-index matching remains a Phase 2 boundary. Evidence: `backend/nursing_station/database.py`, `tests/test_api.py::test_medication_rejects_wrong_patient_identifiers`, and `docs/PHASE2_INTEGRATION_CONTRACTS.md`.

## HZ-CLIN-006: audit integrity

Audit rows are protected from update and delete by database triggers. Each event includes the previous hash and a computed event hash; verification is exposed only to the nurse-in-charge role and is reported by the health endpoint. Evidence: `tests/test_api.py::test_audit_chain_is_append_only_and_verifiable`, `tests/test_api.py::test_registered_nurse_cannot_read_audit`, and `backend/nursing_station/database.py`.

## HZ-CDS-001: alert fatigue

Phase 1 creates an owned escalation task only when the deterministic observation threshold is crossed. It does not provide batch dismissal or alert override. Routine observations do not create a critical alert, while critical values create a critical escalation with the source score visible. Evidence: `tests/test_api.py::test_observation_normal_values_score_zero` and `tests/test_api.py::test_observation_records_score_and_creates_escalation`.

## HZ-CDS-002: scoring drift

Phase 1 does not use machine learning. The score is a version-controlled deterministic function with direct regression tests for normal, implausible, and critical inputs. Any later scoring-policy change must update the clinical configuration, safety case, traceability, and focused tests before release. Evidence: `backend/nursing_station/main.py`, `tests/test_api.py::test_observation_normal_values_score_zero`, `tests/test_api.py::test_observation_rejects_implausible_value`, and `tests/test_api.py::test_observation_records_score_and_creates_escalation`.
