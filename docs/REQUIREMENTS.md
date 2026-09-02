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

### National capability requirements

Landed 2026-08-05 from the national-capability completeness audit
(`docs/national-capability-audit.md`). Dispositions, evidence and the mapping
from the audit's provisional intake aliases to these native identifiers are in
`docs/NATIONAL_CAPABILITY_DISPOSITION_LEDGER.md`.

- `FR-NS-090`: Present ward work ranked by clinical risk, due time, priority and suspended work, and publish the factor breakdown that produced each rank. Ranking SHALL order work only; it SHALL NOT complete, reassign or close it.
- `FR-NS-091`: Require the assignee's verified competency before nursing work is delegated, and again before that work is accepted or completed. A refusal SHALL name the missing competency.
- `FR-NS-092`: Record an interruption of nursing work with its reason and reason category, and keep the interrupted work raised in the work queue until it is explicitly resumed.
- `FR-NS-100`: Attach a required response interval and a minimum responder seniority to every deterioration escalation, and close it only through a named responder's recorded clinical response. Recording a response SHALL NOT complete the escalation task.
- `FR-NS-101`: Take the early-warning profile identity, its oxygen-saturation band tables including the prescribed Scale 2 target range, its thresholds and its response intervals from the active jurisdiction's country pack. The patient's prescribed oxygen target scale SHALL select the band table; an absent or unknown scale SHALL fall back to Scale 1 rather than be guessed.
- `FR-NS-110`: Reconcile hub-sourced pharmacy medication requests into the eMAR idempotently by source order reference. An order carrying an administration record SHALL NOT be overwritten, and a request missing a dose unit SHALL be reported unmappable rather than defaulted.
- `FR-NS-111`: Queue the administration outcome of a hub-sourced order durably for its owning system with a correlation identifier. The outcome SHALL remain pending until a receipt arrives and SHALL NOT be reported as delivered. A locally authored order SHALL create no external obligation.
- `FR-NS-120`: Transfer every unresolved action to the receiving nurse when a handover is accepted, or record a reasoned decline that leaves the action with the sender. An action the receiver is not competent to perform SHALL be declined automatically with the missing competency named, never silently transferred.
- `FR-NS-130`: Consume the shift roster through BulletTrain against a declared contract covering ward, shift, assignment identity, role, registration status and hours. A malformed, empty or unpublished roster SHALL be reported absent and SHALL NOT be inferred.
- `FR-NS-131`: Compute the ward staffing position from repo-owned occupancy and acuity against the country pack's staffing norm, and report `insufficient-policy` where the jurisdiction sets no numeric norm rather than asserting compliance.
- `FR-NS-132`: Allow only a nurse in charge to declare a staffing shortage, emit exactly BulletTrain's governed staffing-declaration field set, and assert no policy tier, severity or approval of its own. A declaration SHALL be revocable with a recorded reason.
- `FR-NS-140`: Record falls, pressure injuries and healthcare-associated infections as incidents with occurrence and discovery times, classification, body site, present-on-admission status, harm level and named reporter. External reportability SHALL be decided by the country pack, and a present-on-admission pressure injury SHALL NOT count as hospital-acquired harm.
- `FR-NS-141`: Require a harm incident to be reviewed by someone other than its reporter, record avoidability, contributory factors and conclusion, and create owned, due learning actions.
- `FR-NS-150`: Open discharge readiness from the active jurisdiction's criteria set with each criterion's owner role, evidence source and mandatory status, and refuse completion while any mandatory criterion is outstanding.
- `FR-NS-151`: Meet a criterion owned by another system only from that system's own receipt through the hub. A dispatch, an empty successful response or a missing hub route SHALL leave the criterion pending with a typed reason.
- `FR-NS-160`: Carry nursing quality measure definitions as versioned country-pack data with numerator, denominator, exclusions, unit and a dated citation.
- `FR-NS-161`: Compute the nursing quality dataset from ward records, distinguish an unavailable source from a zero and from an absent denominator, and publish it de-identified as an additive block on the proven HMIS measure envelope without changing that envelope's required keys.
- `FR-NS-170`: Ship country policy as a versioned pack per jurisdiction covering the early-warning profile, safe-staffing norms and declaration triggers, harm-incident classification and reporting owner, discharge criteria and quality measures, with publisher, title and effective date for every clinically meaningful entry.

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
- `NFR-NS-027`: A country pack SHALL ship as a candidate. Nursing Station SHALL treat a pack as locally adopted only after a recorded organisational decision pinned to the exact reviewed pack version, and SHALL report the candidate and adopted states separately. Publishing a new pack version SHALL NOT inherit a previous version's adoption.
- `NFR-NS-028`: Nursing Station SHALL consume roster, registration and skill-mix state and SHALL NOT become its author. It SHALL expose no route that writes a roster, and an unavailable roster SHALL degrade the staffing position rather than produce one.
- `NFR-NS-029`: Every outbound national publication SHALL be durable, idempotent by correlation identifier, and written before any transport is attempted. It SHALL remain pending until a receipt arrives, and a publication whose BulletTrain-side route does not exist SHALL be surfaced as a named gap rather than reported as delivered.
- `NFR-NS-030`: Every national safety decision SHALL record the named human who made it. Escalation response, incident review, staffing declaration and revocation, discharge-criterion confirmation, discharge completion and country-pack adoption SHALL NOT resolve automatically, and no automated ranking, computation or import SHALL substitute for that decision.

## Standards basis and local adoption boundary

WHO SMART Guidelines, WHO Global Patient Safety Action Plan 2021-2030, WHO Medication Without Harm, ISO 18104:2023, HL7 FHIR R4 workflow semantics, SNOMED CT/ICNP nursing terminology, ISO 27799:2025, and WCAG 2.2. Country-specific controls are overlays, not falsely universalised.

`STANDARDS_PROFILE.md` records the adoption rationale, limits, and primary sources.

The warning-score implementation is a configurable clinical decision support control, not an autonomous diagnosis. The governed seed uses NEWS2-style thresholds for testability. A Clinical Safety Officer must approve the scoring profile and escalation protocol before any clinical deployment.

## Incremental additions (`caid add-requirement`)


<!-- CAID:INCREMENTAL:NFR-NS-031:START (auto-generated by `caid add-requirement`; edit above/below this block, not inside it) -->
### NFR-NS-031 — Responsive layout at phone, tablet and desktop widths

**Statement:** Every ward-facing surface SHALL render without horizontal page scroll at 375, 768 and 1280 CSS pixel widths. At phone width the primary navigation SHALL be off-screen until opened by a control of at least 44 CSS pixels, the main content SHALL fill at least 80 percent of the viewport, form fields SHALL stack to at least 75 percent of the viewport, every interactive control SHALL present a 44 CSS pixel touch target with at most five exceptions, and no text SHALL render under 12 CSS pixels with at most three exceptions. Conformance SHALL be measured through SignalBox browser_responsive_audit in a headed persona-driven session against the running application, and the report SHALL be retained as evidence; a unit test or generated matrix alone is not responsive evidence.

**Existing-codebase audit verdict:** NOT_FOUND
**Brownfield disposition:** requirements-only

| Component | Kind | Disposition | Verdict | Evidence |
| --- | --- | --- | --- | --- |
| SignalBox | symbol | requirements-only | NOT_FOUND | PROMPT.md, docs/national-capability-audit.md, docs/NATIONAL_CAPABILITY_DISPOSITION_LEDGER.md, docs/PHASE_2_INTEGRATION_CONTRACTS.md, docs/REQUIREMENTS.md, docs/TRACEABILITY.md, safety/AGENT_CSO_HITL_PROCEDURE.md, evidence/signalbox-phase2/README.md |
<!-- CAID:INCREMENTAL:NFR-NS-031:END -->
