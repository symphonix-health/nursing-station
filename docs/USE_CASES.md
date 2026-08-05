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
- `UC-NS-023`: The registered Agent Clinical Safety Officer reviews the intended use, hazards, privacy and operational artefacts, CAID results, real seeded journey, and headed evidence, then issues a scope-bound approve or reject recommendation without asserting a professional licence.
- `UC-NS-024`: A human release authority reviews the agent packet and approves or rejects the exact synthetic clinical-simulation scope. The gate remains blocked when either key is absent or the scopes differ, and the decision cannot activate live-patient deployment.

## National capability use cases

- `UC-NS-025`: A nurse opens the ward work queue and sees the deteriorating patient's work at the top with the factors that put it there, rather than a flat due-time list.
- `UC-NS-026`: A charge nurse delegates work that requires a verified competency and the system refuses an assignee who does not hold it, naming the competency.
- `UC-NS-027`: A nurse interrupted by a clinical emergency records the interruption; the suspended work stays raised in the queue until it is resumed.
- `UC-NS-028`: A patient prescribed an 88-92 percent oxygen target is scored against the Scale 2 band table, so an on-target saturation does not manufacture a false escalation.
- `UC-NS-029`: A nurse in charge answers a critical escalation inside the jurisdiction's response interval; the response is attributed to her by name and does not close the escalation task on her behalf.
- `UC-NS-030`: A pharmacy medication request arrives through the hub and becomes an eMAR order; a request with no dose unit is refused rather than defaulted, and an already-administered order is never overwritten.
- `UC-NS-031`: A nurse records an omission against a hub-sourced order; the outcome is queued for pharmacy with its correlation identifier and is never presented as delivered.
- `UC-NS-032`: A receiving nurse accepts a handover and takes the unresolved actions with the patient, declining one with a reason that leaves it with the sender.
- `UC-NS-033`: A charge nurse reviews the ward staffing position against the jurisdiction's norm while the roster is unpublished, and sees required staffing with an explicitly absent actual.
- `UC-NS-034`: A charge nurse declares a staffing shortage; the declaration carries exactly the governed field set, names her as the declaring human, and leaves the policy tier to the governing service.
- `UC-NS-035`: A nurse records a fall with harm; the jurisdiction's reportable-type list decides that it must be reported externally, and the report is queued rather than claimed.
- `UC-NS-036`: A charge nurse reviews an incident she did not report, records avoidability and contributory factors, and the learning actions become owned ward work.
- `UC-NS-037`: A nurse opens discharge readiness for a patient, meets the education criterion herself, and cannot mark the pharmacy-owned criterion met without pharmacy's own receipt.
- `UC-NS-038`: A charge nurse reviews the nursing quality dataset and sees which measures are computed, which have no denominator, and which are unavailable because no roster was published.
- `UC-NS-039`: A Clinical Safety Officer records an adoption decision for the exact country-pack version reviewed; a later pack version does not inherit it.
- `UC-NS-040`: A charge nurse or auditor inspects the durable outbound publication queue and sees, per national workflow, whether a destination exists and what remains pending.
