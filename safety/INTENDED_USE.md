# Intended use

The Nursing Station Phase 1 application is a ward-based nursing workflow system for authenticated registered nurses and nurses in charge. It supports ward overview, patient-context review, observation capture, deterministic early-warning score calculation, escalation tasks, nursing task management, care plans, medication-occurrence recording, structured SBAR handover, safety assessments, and audit review.

The intended setting is an inpatient ward using a managed workstation or tablet. Phase 1 uses its own durable, seeded SQLite data store and does not connect to an EHR, patient registry, prescribing system, laboratory, terminology, consent, messaging, or identity provider. Those connections are explicitly deferred to Phase 2 and the application fails visibly at that boundary; it has no selectable internal mock or service fallback.

The early-warning score is deterministic decision support derived only from the observations entered by the nurse. It does not diagnose, recommend treatment, replace clinical judgement, or use a machine-learning model. Staff must verify the patient banner and two identifiers where prompted, review the source observations, and follow local escalation policy. The score and escalation task are aids to action, not autonomous clinical decisions.

The software is not authorised for live clinical deployment by this document. Deployment requires local clinical configuration and validation, a named Clinical Safety Officer's approval of the clinical safety case, DPIA and DPO approval, applicable medical-device review, release-authority acceptance, training, downtime procedures, and Phase 2 integration assurance where integrations are enabled.
