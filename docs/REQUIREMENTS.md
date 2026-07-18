# Nursing Station requirements

## Scope

The service owns inpatient nursing workflow within a ward. Phase 1 provides the
durable ward workflow. Phase 2 adds governed, read-only clinical context from
authoritative siblings and de-identified aggregate reporting through
BulletTrain. Nursing Station does not become the authority for identity,
encounters, prescribing, dispensing, laboratory, imaging, blood-bank, or HMIS
records.

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

### Phase 2 integration requirements

- `FR-NS-070`: Nursing Station SHALL retrieve the authoritative patient context from PICIS through BulletTrain. Nursing Station SHALL reject an external NHS number, name, or birth-date mismatch.
- `FR-NS-071`: Nursing Station SHALL retrieve patient-scoped LIS results through BulletTrain. Each displayed result SHALL retain its status, interpretation flag, unit, tested time, verified time, and LIS identifier.
- `FR-NS-072`: Nursing Station SHALL retrieve patient-scoped imaging context from PACS/RIS through BulletTrain. The display SHALL label each report as draft, preliminary, final, or addended.
- `FR-NS-073`: Nursing Station SHALL retrieve patient-scoped medication requests and dispensing events from pharmacy-system through BulletTrain. Nursing Station SHALL not infer a medication-administration outcome from a dispensing state.
- `FR-NS-074`: Nursing Station SHALL retrieve the patient-scoped blood group, alert, request, issue, administration, and reaction state from blood-transfusion through BulletTrain.
- `FR-NS-075`: Nursing Station SHALL publish only approved ward-level counts to HMIS through BulletTrain. The payload SHALL exclude patient identifiers, names, birth dates, free text, and patient-level events.
- `FR-NS-076`: Nursing Station SHALL persist every integration attempt. A successful snapshot SHALL retain the source content hash, correlation identifier, retrieval time, source update time, status, tenant, patient, and resource type.
- `FR-NS-077`: Nursing Station SHALL present status, source, freshness, reconciliation state, and last successful retrieval time separately for each authoritative owner.
- `FR-NS-078`: Nursing Station SHALL retain ownership of nursing observations, tasks, care plans, handovers, assessments, and medication administrations. An imported snapshot SHALL not overwrite a Nursing Station-owned record.
- `FR-NS-079`: Nursing Station SHALL provide an authorised manual refresh action. The UI SHALL identify denial, mismatch, timeout, circuit-open, unavailable, and invalid-response outcomes.
- `FR-NS-080`: Nursing Station SHALL accept a critical LIS result notification only through the BulletTrain connector hub. It SHALL authenticate the event, resolve the governed patient link, persist one alert per source event identifier, and reject an unknown patient or changed replay.
- `FR-NS-081`: The ward dashboard SHALL surface each open critical-result alert within five seconds of successful hub acceptance without page navigation. It SHALL show patient context, source, result, observed time, and correlation identifier using non-colour critical status.
- `FR-NS-082`: An authorised ward nurse SHALL explicitly acknowledge a critical-result alert. Receipt or display of an alert SHALL NOT record a diagnosis, treatment decision, task completion, or clinical acknowledgement automatically.

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
- `NFR-NS-010`: Resolve dedicated backend and frontend ports from the canonical workspace registry, register service existence in the BulletTrain service catalogue, regenerate dependent catalogue/topology artefacts, and fail the build on conflicts, unregistered binds, hardcoded fallbacks, stale generated metadata, or unimplemented interface-catalogue rows.
- `NFR-NS-011`: Declare governed synthetic seed provenance and landed counts in durable runtime state, label synthetic patient records with their data class and manifest ID, and reject any claim that the fixture contains or represents real, pseudonymised, or live-system data.
- `NFR-NS-012`: Nursing Station SHALL send every Phase 2 exchange to the authenticated BulletTrain hub. The exchange SHALL identify the tenant, actor, purpose, role, scope, correlation, source, and resource type.
- `NFR-NS-013`: Phase 2 SHALL require an explicit hub URL, service token, and bounded timeout. An unavailable dependency SHALL produce a failed or degraded state without fallback success.
- `NFR-NS-014`: Refresh and HMIS submission SHALL be idempotent by correlation identifier or content hash. Nursing Station SHALL reject a source snapshot older than the stored source update time.
- `NFR-NS-015`: Integration payloads SHALL use documented FHIR R4 semantics and source terminology. Nursing Station SHALL display source codes and units without translation or inference.
- `NFR-NS-016`: Deployed transport SHALL use TLS. Nursing Station SHALL minimise requested fields, apply governed retention, and append integration access to the tamper-evident audit chain.
- `NFR-NS-017`: Nursing Station SHALL retain the last successful snapshot during downtime. The UI SHALL mark the snapshot stale and SHALL not label cached data as live.
- `NFR-NS-018`: Phase 2 acceptance SHALL use the shared governed cohort and real seeded sibling services. Acceptance evidence SHALL exclude internal substitutes, synthetic telemetry, and selectable fallback paths.
- `NFR-NS-019`: Each proven Phase 2 interface SHALL enter the BulletTrain catalogue. The cascade SHALL regenerate topology artefacts and pass the workspace port-conflict gate without a new unregistered listener.
- `NFR-NS-020`: Every integration state and refresh control SHALL satisfy WCAG 2.2 AA, keyboard operation, non-colour status, reduced motion, and usable 200% zoom.
- `NFR-NS-021`: Inbound clinical notifications SHALL use a secret-managed HMAC-SHA256 signature, event-kind and event-identity checks, tenant and ward scoping, append-only audit, and fail-closed behaviour when authentication is unavailable.
- `NFR-NS-022`: Critical-result delivery and acknowledgement SHALL be idempotent. Every accepted event SHALL retain its source event identifier, content hash, source resource identifier, observed and received times, correlation identifier, and acknowledgement actor and time.
- `NFR-NS-023`: Near-real-time acceptance SHALL be proven with a real seeded LIS result, the registered BulletTrain hub and Nursing Station ports, an emitted hub exchange, automatic dashboard revalidation, and separate headed SignalBox sessions for the nurse persona and nurse-superpersona. Synthetic counters, direct callback bypasses, and page reload evidence are prohibited.
- `NFR-NS-024`: A governed `clinical-safety-officer-superpersona` SHALL execute the clinical-safety assurance procedure, review metadata and de-identified evidence only, and produce a scope-bound recommendation. The agent SHALL NOT claim professional registration, statutory office, independent approval authority, or a legal signature.
- `NFR-NS-025`: Deployment approval SHALL require two independent keys: a passing agent Clinical Safety Officer evidence battery and an explicit human decision for the identical scope. A missing check, missing human decision, or scope mismatch SHALL fail closed.
- `NFR-NS-026`: Synthetic clinical-simulation approval SHALL remain distinguishable from live-patient release. Any live-patient deployment SHALL require a new controller, jurisdiction, privacy, regulatory, operational, and named accountable-human assessment and SHALL NOT inherit the synthetic approval.

## Standards basis and local adoption boundary

WHO SMART Guidelines, WHO Global Patient Safety Action Plan 2021-2030, WHO Medication Without Harm, ISO 18104:2023, HL7 FHIR R4 workflow semantics, SNOMED CT/ICNP nursing terminology, ISO 27799:2025, and WCAG 2.2. Country-specific controls are overlays, not falsely universalised.

`STANDARDS_PROFILE.md` records the adoption rationale, limits, and primary sources.

The warning-score implementation is a configurable clinical decision support control, not an autonomous diagnosis. The governed seed uses NEWS2-style thresholds for testability. A Clinical Safety Officer must approve the scoring profile and escalation protocol before any clinical deployment.
