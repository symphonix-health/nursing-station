# Phase 2 integration hazards

These hazards supplement the generated clinical hazard log. They require human
Clinical Safety Officer review and do not change the blocked release verdict.

| ID | Hazard | Clinical effect | Implemented controls | Residual action |
|---|---|---|---|---|
| HZ-NS-INT-001 | Sibling record belongs to another patient | Nurse acts on another person's result, medicine, imaging, or blood state | Governed external/source identifiers; PICIS and blood demographic reconciliation; mismatch rejects persistence; audit event | Approve production MPI and local identity policy |
| HZ-NS-INT-002 | Source snapshot is stale or regresses | Delayed or incorrect care based on obsolete context | Source and fetch timestamps; content hash; older source version rejection; stale label after failure; no live label for cached data | Define source-specific freshness limits and downtime SOP |
| HZ-NS-INT-003 | Source or hub unavailable | Missing context is mistaken for normal findings | Typed explicit failure; retained snapshot marked stale; no direct call, internal substitute, or fallback success | Approve escalation and paper/downtime workflow |
| HZ-NS-INT-004 | Dispense state is treated as administration | Medication is omitted or duplicated | Pharmacy data is read-only and visually source-owned; Nursing Station administration remains separate and requires identifiers and server confirmation | Clinical walkthrough of medication display |
| HZ-NS-INT-005 | Patient data leaks into HMIS aggregate | Confidentiality breach and unlawful secondary processing | Fixed allow-list of non-negative ward counts; Pydantic rejects extra fields; correlation/content idempotency; nurse-in-charge role | DPO approves measure set, retention, and lawful basis |
| HZ-NS-INT-006 | Partial refresh hides source failure | Nurse assumes all systems are current | Per-source attempts, timestamps, state and error detail; aggregate response reports `all_succeeded`; successful sources cannot mask failures | Monitor failure and stale-age thresholds |
| HZ-NS-INT-007 | Critical-result event is forged, replayed, misrouted, or delayed | Wrong or late escalation may cause harm | BulletTrain-only HMAC event; event-kind and identity checks; governed patient resolution; content-hash replay conflict; observed and received time; ward scope; audit chain | Secret rotation, delivery monitoring, and local critical-result escalation policy |
| HZ-NS-INT-008 | Alert display is treated as clinical action | Necessary review or escalation is assumed complete | Alert remains open until an authorised nurse explicitly acknowledges it; receipt does not create diagnosis, treatment, task completion, or acknowledgement | Clinical Safety Officer approves acknowledgement and escalation responsibilities |

Evidence links: `docs/REQUIREMENTS.md`, `docs/TRACEABILITY.md`,
`backend/nursing_station/main.py`, `backend/nursing_station/integration.py`,
`frontend/src/App.tsx`, and the authoritative sibling endpoint tests.
