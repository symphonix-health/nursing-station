# Phase 2 integration contracts

These contracts are implemented in Phase 2. Runtime acceptance still requires the real seeded journey and the existing safety, privacy, security, port, CAID, and headed-browser gates.

| Boundary | Authoritative owner | Future governed contract |
|---|---|---|
| Patient identity and encounter | PICIS | FHIR Patient/Encounter semantics through BulletTrain |
| Prescribing and dispensing | pharmacy-system | MedicationRequest/MedicationDispense semantics through BulletTrain |
| Laboratory | LIS | Observation/DiagnosticReport read |
| Imaging | PACS-RIS | ImagingStudy/DiagnosticReport read |
| Blood products | blood-transfusion | Transfusion status and administration event |
| Aggregate reporting | HMIS | Approved de-identified nursing measures only |

All transport must be hub-mediated, authenticated, tenant-qualified, replayable, observable, and fail explicitly. No direct sibling calls or selectable fake fallbacks are allowed.

## Implemented control boundary

`FR-NS-070` through `FR-NS-079` and `NFR-NS-012` through `NFR-NS-020` define the implemented boundary. Ava Patel (`9991000003`, `pat-ava`) and Finn Jackson (`9990000042`, `pat-finn`) are governed fictional identity-alignment records already present in each source seeder.

The Phase 2 requirements must cover at least:

- authoritative owner, business key, tenant and facility scope, persona and purpose-of-use for every read and write;
- hub-mediated OIDC, BulletLink/A2A policy, consent or lawful-basis enforcement where applicable, and explicit denial behaviour;
- event ordering, idempotency, versioning, provenance, reconciliation, timeout, retry, circuit-breaking, recovery, and downtime operation;
- terminology binding, data minimisation, retention, audit, clinical-safety ownership, DPIA effects, and human override or escalation;
- real seeded cross-system journeys and headed SignalBox evidence, with no internal mock, stub, fallback, or synthetic telemetry accepted as integration proof.

The BulletTrain catalogue contains one row per implemented exchange. A `BLOCKED`, `PARTIAL`, unavailable, mismatched, or unknown result remains visible and cannot be converted into success by cached or locally fabricated data.

## Critical LIS result notification

LIS emits `CriticalResultAlert` through the registered BulletTrain Nursing Station connector. BulletTrain signs the canonical payload with HMAC-SHA256 and forwards it to `/api/integrations/lis/critical-result`. Nursing Station validates the signature, event kind, source event identity, governed NHS-number link, tenant and ward scope, and content hash before persisting an open alert. Replays with the same event and content are idempotent; changed replays fail closed.

The dashboard polls `/api/alerts` at the governed five-second interval and shows non-colour critical status, source provenance, observed time, and correlation identity. Receipt and display do not diagnose, treat, complete a task, or acknowledge the result. An assigned nurse must use the explicit acknowledgement action, which records the actor and time in durable state and the audit chain.
