# CAID build prompt: Nursing Station Phase 1

scope_override: cds_support
scope_override_rationale: The component calculates a warning score from clinical observations and creates deterioration escalation actions, so clinical safety and decision-support assurance are mandatory.

Build a new Symphonix Health clinical sibling for inpatient nursing-station management. Phase 1 must be a complete standalone, durable, seeded implementation. It must cover ward context, nursing accountability, patient banner, observations and deterioration escalation, tasks, SBAR handover, medication-administration recording, safety assessments, audit, role/ward scope, accessibility, responsive light/dark themes, and realistic browser journeys.

Use the Symphonix Health clinical design system in collaboration with ui-ux-pro-max. Respect all existing workspace governance, CAID, canonical-matrix, real-seeded-service, clinical-safety, SignalBox, regression-lock and no-bypass gates.

Port and catalogue cascade is a Phase 1 acceptance condition. CAID must allocate the sibling in `workspace-tooling/ports.workspace.json`, use dedicated backend and frontend ports, and make every backend, Vite, Playwright, documentation, and launcher reference resolve from that registry without a hardcoded fallback. CAID must also register the service in `BulletTrain/config/ports.json`, regenerate the service catalogue and interface-network metadata, and run the workspace and BulletTrain port gates. A build with an unregistered bind, a shared dev-port collision, stale generated catalogue hashes, or a literal fallback is incomplete. Phase 1 registers service existence only; governed interface catalogue rows remain Phase 2 work until their real integrations exist.

Phase 1 synthetic records must follow the metadata-library seed-manifest and safety rules. The durable runtime must expose its seed declaration and landed counts, label synthetic patient records with their data class and manifest ID, and state that no real, pseudonymised, or live-system data is present. A README-only synthetic label is insufficient.

Phase 2 will implement integrations. Phase 1 may document boundary contracts but must not add internal mock services, pretend that integrations work, or count contract-only artefacts as integration evidence.
