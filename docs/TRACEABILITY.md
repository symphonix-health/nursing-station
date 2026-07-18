# Nursing Station traceability

`docs/REQUIREMENTS.md` is the requirement source. `docs/USE_CASES.md` supplies the workflow layer. `scripts/generate_canonical_matrices.py` maps all requirement IDs into the 100-row CAID 18-column matrix and the BulletTrain 14-column functional matrix. `tests/test_api.py` supplies direct service behavior, authorization, clinical calculation, concurrency, and audit evidence. `frontend/e2e/clinical.spec.ts` supplies real browser and API-path evidence. `safety/HAZARD_LOG.md` links hazards to the same focused tests.

Generated matrices live under `tests/harness/`; generated OpenAPI and TypeScript types live under `shared/` and `frontend/src/api/openapi.generated.ts`. A generated matrix or report is not a verdict. Acceptance requires the direct tests and CAID checks to pass against the real seeded service.

`NFR-NS-010` is guarded by `tests/test_port_registry.py`: the component allocation must exist in `../workspace-tooling/ports.workspace.json`, match `../BulletTrain/config/ports.json`, and be resolved by backend, Vite, and Playwright without a literal fallback. `caid-manifest.json` and `PROMPT.md` make the required catalogue regeneration and port-validation commands part of every future CAID handoff.

`NFR-NS-011` is guarded by `tests/test_api.py`, `tests/test_governance_artifacts.py`, and the metadata-library seed-manifest validator. The runtime stores the declared manifest and landed counts in `seed_runs`; seeded patients retain their data class and manifest ID; the governance route exposes both. The seeder is explicitly approved for the declared non-production use cases and is not represented as `symphonix-health-assurance` or a live clinical source.

Phase 2 requirements `FR-NS-070` through `FR-NS-082` and `NFR-NS-012`
through `NFR-NS-023` are evidenced by the patient integration API, durable
integration snapshots and attempts, the HMIS submission receipt, the integration
UI, authenticated critical-result alert receipt and acknowledgement, authoritative
sibling endpoint tests, BulletTrain connector tests, the real seeded cross-system
journey, and signed headed SignalBox evidence for the nurse and nurse-superpersona.
A unit test or generated matrix alone is not Phase 2 integration evidence.

`NFR-NS-024` through `NFR-NS-026` are evidenced by
`safety/AGENT_CSO_HITL_PROCEDURE.md`, the machine-readable
`safety/CLINICAL_DEPLOYMENT_GATE.json`,
`scripts/evaluate_clinical_deployment_gate.py`, and the direct governance tests.
The agent persona prepares and recommends; the human decides. The approved
synthetic clinical-simulation scope cannot be interpreted as live-patient,
professional-registration, statutory, or medical-device approval.
