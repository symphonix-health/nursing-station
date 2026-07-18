# Phase 1 traceability

`docs/REQUIREMENTS.md` is the requirement source. `docs/USE_CASES.md` supplies the workflow layer. `scripts/generate_canonical_matrices.py` maps all requirement IDs into the 100-row CAID 18-column matrix and the BulletTrain 14-column functional matrix. `tests/test_api.py` supplies direct service behavior, authorization, clinical calculation, concurrency, and audit evidence. `frontend/e2e/clinical.spec.ts` supplies real browser and API-path evidence. `safety/HAZARD_LOG.md` links hazards to the same focused tests.

Generated matrices live under `tests/harness/`; generated OpenAPI and TypeScript types live under `shared/` and `frontend/src/api/openapi.generated.ts`. A generated matrix or report is not a verdict. Acceptance requires the direct tests and CAID checks to pass against the real seeded service.
