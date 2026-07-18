# Nursing Station Phase 1 requirements

## Scope

The service owns inpatient nursing workflow within a ward. It stores durable patient-level nursing records for Phase 1 and exposes explicit future ownership boundaries for Phase 2.

## Functional requirements

- `FR-NS-001`: Present a ward board scoped to the authenticated user's tenant, facility, ward, and assignment.
- `FR-NS-002`: Maintain a persistent patient banner with two identifiers, demographics, location, allergy, code status, isolation, flags, and photo availability.
- `FR-NS-003`: Record accountable nurse and changes in accountability.
- `FR-NS-004`: Provide a shared-screen privacy mode that masks direct patient identifiers without hiding operational risk.
- `FR-NS-010`: Record structured observations with units, performer, time, provenance, and calculated warning score.
- `FR-NS-011`: Detect implausible observations and require correction before persistence.
- `FR-NS-012`: Create escalation tasks when a warning score reaches the configured threshold.
- `FR-NS-020`: Create, assign, accept, complete, cancel, and list nursing tasks with priority and due time.
- `FR-NS-021`: Prevent a user from completing a task outside their ward or role scope.
- `FR-NS-022`: Create, own, evaluate, achieve, and discontinue patient-centred nursing care plans with version control.
- `FR-NS-030`: Create structured SBAR handovers and explicitly transfer accountability to a receiving nurse.
- `FR-NS-031`: Preserve unresolved tasks and current risks in the handover record.
- `FR-NS-040`: Present medication orders and record administered, withheld, refused, delayed, omitted, or partial outcomes.
- `FR-NS-041`: Require two patient identifiers for every medication-administration event.
- `FR-NS-042`: Require an independent co-signer for high-alert administrations.
- `FR-NS-043`: Never infer medication units or silently treat a failed action as administered.
- `FR-NS-050`: Record falls, pressure-injury, infection/isolation, nutrition, hydration, pain, and delirium assessments where applicable.
- `FR-NS-051`: Translate assessment risks into owned, due nursing actions.
- `FR-NS-060`: Append every regulated mutation to a tamper-evident hash-chained audit log.

## Non-functional and safety requirements

- `NFR-NS-001`: Enforce tenant, facility, ward, role, practitioner, and care-relationship scope.
- `NFR-NS-002`: Use durable storage; in-memory or JSON-file clinical backends are prohibited.
- `NFR-NS-003`: Meet WCAG 2.2 AA, keyboard navigation, reduced-motion, 200% zoom, and non-colour status communication.
- `NFR-NS-004`: Support deterministic light and dark themes with user-visible control.
- `NFR-NS-005`: Keep safety invariants identical across themes and viewport sizes.
- `NFR-NS-006`: Provide explicit freshness, source, author, and action ownership on clinical surfaces.
- `NFR-NS-007`: Reject stale concurrent mutations using record versions.
- `NFR-NS-008`: Produce no synthetic integration telemetry or fallback success.
- `NFR-NS-009`: Maintain clinical safety case, hazard log, DPIA, privacy notice, retention policy, and operational runbook.

## Standards basis and local adoption boundary

WHO SMART Guidelines, WHO Global Patient Safety Action Plan 2021-2030, WHO Medication Without Harm, ISO 18104:2023, HL7 FHIR R4 workflow semantics, SNOMED CT/ICNP nursing terminology, ISO 27799:2025, and WCAG 2.2. Country-specific controls are overlays, not falsely universalised.

`STANDARDS_PROFILE.md` records the adoption rationale, limits, and primary sources.

The warning-score implementation is a configurable clinical decision support control, not an autonomous diagnosis. The Phase 1 seed uses NEWS2-style thresholds for testability. A Clinical Safety Officer must approve the scoring profile and escalation protocol before any clinical deployment.
