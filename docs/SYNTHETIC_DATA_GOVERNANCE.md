# Phase 1 synthetic data governance

Nursing Station Phase 1 uses a compact, deterministic, fabricated inpatient ward seed. It contains synthetic subject-level records and no real, pseudonymised, or live-system patient data. The records exist to exercise the standalone ward workflow, safety controls, accessibility review, and automated tests.

The runtime source is `backend/nursing_station/database.py`. Its declaration is `seed_manifests/uk/nursing_station_phase1.yaml`. On first database initialisation, the service writes the declaration and observed table counts into the durable `seed_runs` table. `GET /api/governance/seed` exposes the landed declaration and counts, and every seeded patient carries `data_class=seeded_synthetic` plus `seed_manifest_id=seed.uk.nursing_station.phase1_v1`.

The manifest marks the repo-owned deterministic seeder as explicitly approved for the Phase 1 workflow, integration, UAT, and synthetic-sandpit use cases. This approval does not identify the seeder as `symphonix-health-assurance`, does not permit live or pseudonymised patient data, and does not extend to production clinical use.

The evidence chain for Phase 1 is:

```text
fabricated UK metadata pack reference
  -> Nursing Station seed manifest
  -> deterministic repo-owned seeder
  -> durable SQLite records
  -> runtime seed declaration and observed counts
  -> API, browser, and CAID evidence
```

The seed deliberately covers ordinary and safety-sensitive conditions: an elevated warning score, overdue and future tasks, allergy and isolation states, a high-alert medication requiring an independent co-signer, pressure-injury risk, and two wards for access-scope tests. The distribution is a workflow coverage fixture, not a population model. It cannot support epidemiology, clinical effectiveness, patient-outcome, or production-readiness claims.

The seed follows the metadata-library safety position: model operational record shapes without copying patient records, state provenance, prohibit live clinical sources, and fail when the runtime declaration is absent. Country-scale distribution calibration, master client/facility/workforce registry resolution, and authoritative sibling data are Phase 2 obligations and must not be simulated in Phase 1.
