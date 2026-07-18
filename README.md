# Symphonix Health Nursing Station

The Nursing Station is the Symphonix Health inpatient ward workspace for registered nurses and nurses in charge. It gives a bedside and station view of patients, observations, deterioration warnings, nursing work, care plans, medication administration, safety assessments, and accountable handover.

Phase 1 is implemented as a standalone clinical workflow over durable seeded SQLite data. It includes:

- ward and patient context with facility, ward, role, and care-relationship access controls;
- shared-screen privacy mode across patient, task, and medication surfaces;
- observations with explicit units, warning-profile versioning, and deterioration escalation;
- assignable nursing tasks and version-guarded care plans;
- structured SBAR handover with captured unresolved work, risk snapshot, version guard, and named acceptance;
- medication-administration outcomes, two-identifier checking, and independent high-alert co-signing;
- append-only hash-chained audit and durable synthetic-data lineage;
- responsive React UI with keyboard navigation, WCAG checks, and 200% zoom reflow.

Phase 2 will connect the boundary contracts to their authoritative Symphonix sibling systems through BulletTrain. It must first extend the requirements, use cases, safety analysis, canonical matrices, and requirement-to-test traceability for every interface and failure mode. Phase 1 does not simulate those integrations and makes no integration-readiness claim.

## Status and release boundary

The Phase 1 implementation, API, browser workflows, semantic traceability, port-conflict guards, and CAID technical checks pass locally. This repository is not approved for clinical production use. CAID's clinical release gate remains blocked until the intended-use statement has human Clinical Safety Officer approval, release authority has accepted the safety case, the DPIA has DPO approval, and MHRA review is evidenced where required. Publishing source code does not satisfy or bypass those approvals.

## Run

The workspace port registry owns the local allocations:

- backend: `9201`
- frontend: `5282`

The backend, Vite, and Playwright resolve these from `../workspace-tooling/ports.workspace.json`. Startup fails when the allocation is absent or conflicting; there is no private literal fallback.

```powershell
python -m pip install -e ".[dev]"
python -m nursing_station.main
```

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Seeded credentials use password `Nursing2026!`:

- `amina.okafor@nursing.test` - registered nurse, Medical Ward A
- `grace.mensah@nursing.test` - nurse in charge, Medical Ward A
- `samuel.osei@nursing.test` - registered nurse, Surgical Ward B
- `clinical.safety@nursing.test` - clinical safety officer

## Evidence boundary

Repository tests prove Phase 1 standalone behaviour only. `docs/PHASE_2_INTEGRATION_CONTRACTS.md` lists the future governed ownership boundaries.

The runtime population is deterministic, fabricated, seeded synthetic data. Its declaration is `seed_manifests/uk/nursing_station_phase1.yaml`; `GET /api/governance/seed` exposes the durable landed manifest and observed counts. No real, pseudonymised, or live-system patient data is permitted.

Run the focused gates from the repository root:

```powershell
python -m pytest -q
python -m ruff check backend tests scripts shared
cd frontend
npm.cmd run build
npm.cmd run test:e2e
```

Requirements, use cases, traceability, safety material, and the Phase 2 boundary are under `docs/`, `tests/harness/`, and `safety/`. CAID's explicit workspace cascade, including the port registry and generated BulletTrain catalogue obligations, is recorded in `caid-manifest.json` and `PROMPT.md` so future CAID runs cannot allocate an ad hoc port.
