# Nursing Station use cases

- `UC-NS-001`: A ward-assigned nurse opens the live ward board and sees operational risk, observation freshness, outstanding work, and accountable nurse.
- `UC-NS-002`: A nurse opens a patient using the ward board and verifies the persistent safety banner before acting.
- `UC-NS-003`: A nurse records observations; invalid values are rejected and deterioration creates a due, owned escalation task.
- `UC-NS-004`: A nurse creates, accepts, completes, or cancels nursing work with stale-update protection.
- `UC-NS-005`: A nurse records and evaluates a patient-centred care plan with named ownership.
- `UC-NS-006`: A nurse records a medication outcome after two-identifier verification; high-alert administration requires an independent eligible co-signer.
- `UC-NS-007`: A nurse sends structured SBAR to a named receiver. Accountability changes only when that receiver accepts.
- `UC-NS-008`: A nurse records a safety assessment and the system creates owned actions from its interventions.
- `UC-NS-009`: A nurse uses privacy mode on a shared display while maintaining operational risk awareness.
- `UC-NS-010`: An authorised nurse in charge or Clinical Safety Officer inspects the append-only audit chain.
- `UC-NS-011`: A developer or CAID run starts Nursing Station using its dedicated registry allocations and verifies that workspace, service-catalogue, and generated topology gates remain conflict-free.
- `UC-NS-012`: A nurse or reviewer opens Governance and sees the durable synthetic seed manifest, landed counts, privacy declarations, and non-production limitations.

## Phase 2 governed integration use cases

- `UC-NS-013`: A ward-assigned nurse opens a shared-cohort patient and refreshes the PICIS encounter context through BulletTrain; the patient identifiers and demographics reconcile before the context is shown.
- `UC-NS-014`: A nurse reviews LIS results with source status, units, abnormal flag, tested time, verification time, and freshness, while preliminary results remain visibly preliminary.
- `UC-NS-015`: A nurse reviews PACS/RIS imaging status and report state without treating a draft or preliminary report as final.
- `UC-NS-016`: A nurse reviews pharmacy medication-request and dispensing state without recording or inferring a Nursing Station administration outcome.
- `UC-NS-017`: A nurse reviews blood-group, special-requirement, request, issue, administration, and reaction status from blood-transfusion before a bedside workflow.
- `UC-NS-018`: A nurse sees separate failed, stale, denied, mismatched, and unavailable integration states and continues only repo-owned downtime workflows where the UI identifies the cached source and age.
- `UC-NS-019`: An authorised nurse in charge submits an idempotent de-identified ward-count bundle to HMIS and receives a durable receipt; patient-level and free-text fields are rejected.
- `UC-NS-020`: A Clinical Safety Officer or auditor traces a refresh or HMIS submission from Nursing Station audit event to BulletTrain correlation identifier and authoritative source receipt.
- `UC-NS-021`: LIS identifies a critical result for a governed seeded patient and routes a signed notification through BulletTrain. The open alert appears on the assigned ward dashboard within five seconds without navigation or reload.
- `UC-NS-022`: A ward-assigned nurse reviews source, result, patient, observed time, and correlation context, then explicitly acknowledges the alert. The nurse-superpersona independently reviews the same governed workflow without autonomous diagnosis or treatment action.
