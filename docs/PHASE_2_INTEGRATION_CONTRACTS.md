# Phase 2 integration contracts

These are contracts only. They are intentionally not implemented or simulated in Phase 1.

| Boundary | Authoritative owner | Future governed contract |
|---|---|---|
| Patient identity | Platform identity/MPI | FHIR Patient read through BulletTrain |
| Encounter and movement | Future inpatient administration owner | FHIR Encounter and Location events |
| Prescribing | GP/EPS or inpatient prescribing owner | MedicationRequest read |
| Dispensing and supply | Pharmacy and supply-chain systems | MedicationDispense and SupplyDelivery read |
| Laboratory | LIS | Observation/DiagnosticReport read |
| Imaging | PACS-RIS | ImagingStudy/DiagnosticReport read |
| Blood products | blood-transfusion | Transfusion status and administration event |
| Aggregate reporting | HMIS | Approved de-identified nursing measures only |

All transport must be hub-mediated, authenticated, tenant-qualified, replayable, observable, and fail explicitly. No direct sibling calls or selectable fake fallbacks are allowed.

## Requirement-led entry gate

Phase 2 does not begin by wiring endpoints. CAID must first add and review requirement IDs for each boundary, then cascade them through use cases, the BulletTrain 14-column functional matrix, the CAID 18-column non-functional matrix, safety hazards, seeded journeys, direct service tests, and the requirement traceability matrix.

The Phase 2 requirements must cover at least:

- authoritative owner, business key, tenant and facility scope, persona and purpose-of-use for every read and write;
- hub-mediated OIDC, BulletLink/A2A policy, consent or lawful-basis enforcement where applicable, and explicit denial behaviour;
- event ordering, idempotency, versioning, provenance, reconciliation, timeout, retry, circuit-breaking, recovery, and downtime operation;
- terminology binding, data minimisation, retention, audit, clinical-safety ownership, DPIA effects, and human override or escalation;
- real seeded cross-system journeys and headed SignalBox evidence, with no internal mock, stub, fallback, or synthetic telemetry accepted as integration proof.

An interface may be added to the BulletTrain integration catalogue only when its requirement-to-use-case-to-test chain and real-service evidence pass the existing governance gates. Any `BLOCKED`, `PARTIAL`, or unknown result remains an explicit Phase 2 gap.
