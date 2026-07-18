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
