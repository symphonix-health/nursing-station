<!--
INTAKE ARTEFACT. Committed verbatim as the requirements-intake record for the
2026-08-05 national-capability wave.

The REQ-NS-NAT-00N identifiers below are PROVISIONAL INTAKE ALIASES. They are
NOT requirements of this repository and must never be treated as obligations by
any traceability, seeding or coverage gate. The native requirements landed from
this audit are FR-NS-090..FR-NS-170 and NFR-NS-027..NFR-NS-030 in
docs/REQUIREMENTS.md; the alias mapping and the verified dispositions are in
docs/NATIONAL_CAPABILITY_DISPOSITION_LEDGER.md.
-->

# nursing-station: National Capability Completeness Audit and CAID Refactoring Handoff

**Generated:** 22 July 2026  
**Implementation wave:** 3  
**Audit confidence:** Medium  
**Status:** Requirements-intake artefact. No source repository files were edited.

## 1. Executive finding

**Repository role:** Ward nursing work management, observations, care plans, handover, eMAR, deterioration and staffing surface.

The repository is applicable because it either owns a national/shared health capability or must exchange nationally governed events with the owning service. Its present catalogue is not assumed to be incomplete merely because a capability is absent locally: the first decision is whether the function should be retained here, consumed through BulletTrain, exposed here as a migrated surface, or built in another canonical owner.

**Disposition vocabulary**

- `RETAIN-AS-OWNER`: this repository owns the canonical state and rules.
- `HUB-CONSUME`: consume a sibling or external service through BulletTrain.
- `MIGRATE-SURFACE`: place the user-facing workflow here while retaining the engine elsewhere.
- `BUILD-NEW`: no suitable owner or complete implementation was evidenced; confirm estate-wide before construction.
- `REJECT/DUPLICATE`: use traceability/navigation rather than additional code.

## 2. Repository evidence inspected

- `tests/harness/requirements_matrix.json`
- `reports/CAID_AUDIT_SUMMARY.md`
- `frontend/src`

**Evidence judgement:** The repository boundary and discoverable requirements/assurance artefacts were inspected, but CAID must read the full current catalogue and implementation before allocating IDs.

## 3. Requirements-completeness gaps

1. National nursing quality, staffing and safety datasets need explicit coverage.
2. Closed-loop medication, deterioration, handover and discharge need end-to-end ownership.
3. Workforce registration, delegation and temporary staffing need registry integration.
4. Country nursing scope/practice rules are not established.
5. Canonical requirements must be inspected locally before allocation.

## 4. Proposed missing requirement families

These IDs are **provisional intake IDs**. CAID must locate the true source of requirements, discover the maximum current identifier, de-duplicate against all catalogues and allocate a collision-free range before landing any entry.

| Provisional ID | Requirement family | Disposition | Draft intent |
|---|---|---|---|
| `REQ-NS-NAT-001` | Ward work orchestration | **RETAIN-AS-OWNER** | Prioritise tasks by risk, due time, delegation, skill and interruption. |
| `REQ-NS-NAT-002` | Observation/deterioration | **BUILD-NEW** | Capture national early-warning scores, escalation, acknowledgement and response. |
| `REQ-NS-NAT-003` | eMAR closed loop | **HUB-CONSUME** | Receive orders/dispense and record administration/omission. |
| `REQ-NS-NAT-004` | Structured handover | **BUILD-NEW** | Transfer responsibility with unresolved-action acceptance. |
| `REQ-NS-NAT-005` | Staffing/skill mix | **HUB-CONSUME** | Use registration, roster, acuity and safe-staffing rules. |
| `REQ-NS-NAT-006` | Pressure injury/falls/infection | **BUILD-NEW** | Run prevention, incident, review and reporting workflows. |
| `REQ-NS-NAT-007` | Discharge readiness | **HUB-CONSUME** | Coordinate medicines, equipment, community referral and education. |
| `REQ-NS-NAT-008` | Nursing quality dataset | **BUILD-NEW** | Produce staffing, missed care, safety, experience and outcome measures. |

## 5. Four-country delta

| Jurisdiction | Required capability delta |
|---|---|
| United Kingdom | NEWS2, safe staffing, patient safety and discharge models. |
| Ireland | HSE nursing documentation, staffing and quality programmes. |
| Kenya | Nursing Council scope, county staffing, offline and KHIS. |
| United States | State scope/staffing, CMS quality and accreditation. |

Use **Ireland** as the jurisdiction. Dublin may be recorded as a deployment location, region or service catchment, not as the country pack.

## 6. Ownership and implementation rules


1. **Keep the canonical owner.** Do not duplicate a sibling's state machine, rules engine or source-of-truth data merely because a portal needs a user-facing workflow.
2. **Use BulletTrain mediation.** New cross-repository and external national-rail traffic must go through the BulletTrain gateway/connector pattern. Do not introduce direct sibling-to-sibling HTTP coupling.
3. **Separate domain from transport.** X12, NCPDP, MESH, Healthlink, DHIS2, DICOM, HL7 v2 and other national/industry formats belong at connector boundaries, not throughout domain models.
4. **Treat country policy as versioned data.** Identifiers, terminology, forms, eligibility rules, deadlines, statutory returns and legal constraints require sources, effective dates and migration tests.
5. **Require closed-loop evidence.** Dispatching a message is not completion. National workflows need acceptance/rejection receipts, escalation, correction, replay and reconciliation.
6. **Preserve human authority.** Clinical, legal, financial, safeguarding and AI-mediated decisions must expose reviewer, evidence, override and final responsibility.
7. **Prove the visible workflow.** Map requirement -> route/service -> data/state -> persona permission -> UI control -> headed-browser evidence -> SignalBox trace.


## 7. CAID execution sequence

1. Locate and read the canonical requirements source, builder/renderer, use cases, matrix configuration, APIs, data models, frontend routes, persona permissions and seed data.
2. Produce an inventory that marks every proposed family `already-covered`, `partial`, `code-only`, `requirements-only`, `owned-by-sibling`, `missing` or `not-applicable`.
3. Resolve contradictions, stale out-of-scope declarations and duplicate ownership before creating requirements.
4. Update the real requirements source and regenerate derived catalogues/NFRs without deleting injected traceability rows.
5. Add or amend shared contracts before implementation. Every cross-system operation must declare idempotency, correlation, compensation and receipt/reconciliation behaviour.
6. Generate genuine positive, negative and edge scenarios. Do not obtain a green gate using filler cases or all-to-all requirement annotations.
7. Implement backend, shared contract and UI surfaces; use seeded personae, headed browser/computer use, SignalBox observability and visual inspection.
8. Verify scenario-success evidence, runtime paths, seed realism, referential integrity, country configuration and the full local CAID gate.
9. Leave unrelated working-tree changes untouched. Report required BulletTrain connector work separately.

### Suggested implementation order

1. Work/deterioration
2. eMAR/handover
3. Staffing/safety
4. Discharge
5. Country quality

## 8. Required output from the implementing session

- Updated canonical requirements source and rendered catalogue.
- A disposition ledger for every proposed family.
- Ownership/API/event contract changes.
- Models, state machines, migrations and realistic seed records.
- UI workflows where the repository owns or surfaces them.
- Versioned country-pack configuration with official sources.
- Acceptance criteria and canonical matrices with meaningful coverage.
- Headed-browser screenshots, SignalBox traces and test results.
- Residual gaps, connector dependencies and rollback/compensation notes.

## 9. References

This file applies `../00_COMMON_NATIONAL_CAPABILITY_BENCHMARK.md` and the provider-portal audit pattern supplied with the task.

- Primary Care Support England. (2026). *Primary Care Support England services*. https://pcse.england.nhs.uk/
- Health Service Executive. (2026). *Primary Care Reimbursement Service*. https://healthservice.hse.ie/staff/information-healthcare-workers/pcrs/pcrs/
- Health Service Executive. (2026). *Healthlink*. https://healthservice.hse.ie/staff/information-healthcare-workers/healthlink/
- Kenya Ministry of Health. (2026). *National health portals*. https://health.go.ke/
- Kenya Ministry of Health. (2026). *Kenya Master Health Facility Registry*. https://kmhfr.health.go.ke/public/about
- Centers for Medicare & Medicaid Services. (2026). *PECOS enrolment management*. https://www.cms.gov/medicare/enrollment-renewal/providers-suppliers/chain-ownership-system-pecos
