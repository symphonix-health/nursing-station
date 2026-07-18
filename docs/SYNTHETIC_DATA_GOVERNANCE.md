# Phase 2 synthetic data governance

Nursing Station Phase 2 uses a compact, deterministic, fabricated inpatient ward seed. It contains synthetic subject-level records and no real, pseudonymised, or live-system patient data. Ava Patel and Finn Jackson align to existing fictional sibling records solely to exercise governed integration, reconciliation, failure handling, safety controls, accessibility review, and automated tests.

The runtime source is `backend/nursing_station/database.py`. Its declaration is `seed_manifests/uk/nursing_station_phase2.yaml`. On database initialisation, the service writes the declaration and observed table counts into the durable `seed_runs` table. `GET /api/governance/seed` exposes the landed declaration and counts, and Phase 2 seeded patients carry `data_class=seeded_synthetic` plus `seed_manifest_id=seed.uk.nursing_station.phase2_v1`.

The manifest marks the repo-owned deterministic seeder as explicitly approved for the Phase 2 workflow, integration, UAT, and synthetic-sandpit use cases. This approval does not identify the seeder as `symphonix-health-assurance`, does not permit live or pseudonymised patient data, and does not extend to production clinical use.

The evidence chain for Phase 2 is:

```text
fabricated UK metadata pack reference
  -> Nursing Station seed manifest
  -> deterministic repo-owned seeder
  -> durable SQLite records
  -> runtime seed declaration and observed counts
  -> API, browser, and CAID evidence
```

The seed deliberately covers ordinary and safety-sensitive conditions: an elevated warning score, overdue and future tasks, allergy and isolation states, a high-alert medication requiring an independent co-signer, pressure-injury risk, and two wards for access-scope tests. The distribution is a workflow coverage fixture, not a population model. It cannot support epidemiology, clinical effectiveness, patient-outcome, or production-readiness claims.

The seed follows the metadata-library safety position: model operational record shapes without copying patient records, state provenance, prohibit live clinical sources, and fail when the runtime declaration is absent. Country-scale distribution calibration remains outside this fixture. Master client, facility, and workforce registry resolution and authoritative sibling data must use the shared governed fictional cohort and real seeded services; they must not be replaced by repo-local stand-ins.
