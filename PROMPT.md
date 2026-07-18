# CAID build prompt: Nursing Station Phase 1

scope_override: cds_support
scope_override_rationale: The component calculates a warning score from clinical observations and creates deterioration escalation actions, so clinical safety and decision-support assurance are mandatory.

Build a new Symphonix Health clinical sibling for inpatient nursing-station management. Phase 1 must be a complete standalone, durable, seeded implementation. It must cover ward context, nursing accountability, patient banner, observations and deterioration escalation, tasks, SBAR handover, medication-administration recording, safety assessments, audit, role/ward scope, accessibility, responsive light/dark themes, and realistic browser journeys.

Use the Symphonix Health clinical design system in collaboration with ui-ux-pro-max. Respect all existing workspace governance, CAID, canonical-matrix, real-seeded-service, clinical-safety, SignalBox, regression-lock and no-bypass gates.

Phase 2 will implement integrations. Phase 1 may document boundary contracts but must not add internal mock services, pretend that integrations work, or count contract-only artefacts as integration evidence.
