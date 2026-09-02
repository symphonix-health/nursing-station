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

National capability requirements `FR-NS-090` through `FR-NS-170` and
`NFR-NS-027` through `NFR-NS-030` are evidenced by
`tests/test_national_capability.py` (direct service behaviour, authority,
fail-closed and de-identification evidence), `tests/test_country_packs.py`
(the country-pack migration test: structural validation, dated citations,
version-pinned adoption, and the refusal to invent a shortage severity the
governed model does not have), and `tests/test_bt_connector_seam.py` (a
read-only pin on BulletTrain's connector manifests and canonical event registry
that turns red the day a missing route is registered).

Their canonical scenarios live in
`tests/harness/json_matrices/nursing_station_national_capability_canonical.json`
and its 14-column companion: forty authored rows, one requirement per row, with
no rotated template and no padded body. `scripts/generate_canonical_matrices.py`
is read-merge-write and is itself guarded by
`tests/test_matrix_builder_brownfield.py`, which plants a foreign requirement
and a foreign matrix row in a sandbox copy of `tests/harness/` and asserts both
survive a rebuild. The legacy 100-row matrix is generated from a frozen
requirement-id tuple so that growing the catalogue cannot reshuffle rows whose
coverage atoms are recorded in `matrix-integrity-baseline.json`.

`docs/NATIONAL_CAPABILITY_DISPOSITION_LEDGER.md` holds the per-family
disposition with file:line evidence and is the only place the audit's
provisional intake aliases appear; they are deliberately kept out of this
document and out of `docs/REQUIREMENTS.md` so they cannot become phantom
requirement obligations for any gate that scrapes them.

`NFR-NS-024` through `NFR-NS-026` are evidenced by
`safety/AGENT_CSO_HITL_PROCEDURE.md`, the machine-readable
`safety/CLINICAL_DEPLOYMENT_GATE.json`,
`scripts/evaluate_clinical_deployment_gate.py`, and the direct governance tests.
The agent persona prepares and recommends; the human decides. The approved
synthetic clinical-simulation scope cannot be interpreted as live-patient,
professional-registration, statutory, or medical-device approval.

`NFR-NS-031` (responsive layout, landed 2026-09-02) is evidenced by
`tests/test_responsive_layout.py`, which pins the phone-width stylesheet rules
(off-screen navigation drawer, 44px controls, 12px minimum text, single-column
grids) and refuses `evidence/signalbox-responsive/latest.json` unless it was
produced by SignalBox's `browser_responsive_audit` in a HEADED, persona-driven
session against the running application with every route and width passing
the estate criteria (BulletTrain `frontend/e2e/L3-VIS-responsive.spec.ts`).
The report and SignalBox's own screenshots per width live under
`evidence/signalbox-responsive/`; the driver is BulletTrain
`scripts/signalbox_responsive_audit.py`. The defect this closes was found by a
person looking at a 375px window, not by any automated check: there was no
horizontal overflow, so a scrollWidth test passed while the navigation stayed
on screen and the metadata rendered at 9px.

The ward-facing UI for the national capability requirements (landed
2026-09-02, `frontend/src/national.tsx`) is evidenced by headed SignalBox
sessions driven as the nurse, the nurse in charge and the Clinical Safety
Officer, each exercising the surface whose named act it records and each
assertion checked against the real API after the real click:
`evidence/signalbox-national-ui/latest.json` with SignalBox's own
screenshots, and the responsive audit of every route under
`evidence/signalbox-responsive/`. `FR-NS-101`'s thresholds now reach the UI
from `GET /api/country-pack` (`early_warning`), asserted in
`tests/test_national_capability.py`; `FR-NS-092`'s open interruptions are
served with their identifiers on the work queue so they can be resumed.

`FR-NS-111` (medication outcome) and `NFR-NS-029` (durable outbound
publication) are evidenced end to end by BulletTrain
`scripts/verify_nursing_publication_loops.py`, which drives each seam through
the real connector against the real receiving service and refuses to report a
delivery it cannot read back from that service's own API. Its report is
`BulletTrain/docs/verification/publication-loops/nursing-station/latest.json`.
The medication seam records which leg it proved and names the blocker on the
ward half; see the disposition ledger section 8.
