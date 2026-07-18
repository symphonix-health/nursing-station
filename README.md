# Symphonix Health Nursing Station

The Nursing Station is the Symphonix Health inpatient ward workspace for registered nurses and nurses in charge. It gives a bedside and station view of patients, observations, deterioration warnings, nursing work, care plans, medication administration, safety assessments, and accountable handover.

Phase 2 retains the durable nursing workflow and adds governed sibling context. It includes:

- ward and patient context with facility, ward, role, and care-relationship access controls;
- shared-screen privacy mode across patient, task, and medication surfaces;
- observations with explicit units, warning-profile versioning, and deterioration escalation;
- assignable nursing tasks and version-guarded care plans;
- structured SBAR handover with captured unresolved work, risk snapshot, version guard, and named acceptance;
- medication-administration outcomes, two-identifier checking, and independent high-alert co-signing;
- append-only hash-chained audit and durable synthetic-data lineage;
- responsive React UI with keyboard navigation, WCAG checks, and 200% zoom reflow;
- BulletTrain-mediated patient, laboratory, imaging, medication, and blood-product snapshots with identity reconciliation, source, freshness, content hash, and correlation evidence;
- authenticated BulletTrain critical-result delivery from the real seeded LIS path, automatic ward-dashboard revalidation within five seconds, and explicit nurse acknowledgement;
- allow-listed, de-identified ward measure submission to HMIS;
- explicit unavailable, stale, mismatch, timeout, policy-denial, and invalid-response states without a fake or direct-sibling fallback.

PICIS, LIS, PACS/RIS, pharmacy-system, blood-transfusion, and HMIS remain authoritative for their own records. Nursing Station stores read-only snapshots and never overwrites its observations, tasks, care plans, handovers, assessments, or medication administrations.

## Status and release boundary

Phase 1 is complete. Phase 2 source contracts, connector manifests, API and UI implementation, direct service tests, and catalogue cascades are implemented. The evidence commands below determine the current local gate state. This repository is not approved for clinical production use. CAID's clinical release gate remains blocked until the intended-use statement has human Clinical Safety Officer approval, release authority has accepted the safety case, the DPIA has DPO approval, and MHRA review is evidenced where required. Publishing source code does not satisfy or bypass those approvals.

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

Phase 2 fails closed unless the hub is explicitly configured:

```powershell
$env:NURSING_STATION_HUB_URL='http://127.0.0.1:8000'
$env:NURSING_STATION_HUB_TOKEN='<service-token>'
$env:NURSING_STATION_HUB_TIMEOUT_SECONDS='10'
$env:NURSING_STATION_INBOUND_HMAC_SECRET='<managed-shared-secret>'
```

Seeded credentials use password `Nursing2026!`:

- `amina.okafor@nursing.test` - registered nurse, Medical Ward A
- `grace.mensah@nursing.test` - nurse in charge, Medical Ward A
- `samuel.osei@nursing.test` - registered nurse, Surgical Ward B
- `clinical.safety@nursing.test` - clinical safety officer

## Evidence boundary

Repository tests prove the Nursing Station-owned behavior and fail-closed integration boundary. A Phase 2 integration claim additionally requires real seeded sibling, BulletTrain, and headed GUI evidence.

The runtime population is deterministic, fabricated, seeded synthetic data. Its Phase 2 declaration is `seed_manifests/uk/nursing_station_phase2.yaml`; `GET /api/governance/seed` exposes the durable landed manifest and observed counts. No real, pseudonymised, or live-system patient data is permitted.

Run the focused gates from the repository root:

```powershell
python -m pytest -q
python -m ruff check backend tests scripts shared
cd frontend
npm.cmd run build
npm.cmd run test:e2e
```

Requirements, use cases, traceability, safety material, and the Phase 2 boundary are under `docs/`, `tests/harness/`, and `safety/`. CAID's explicit workspace cascade, including the port registry and generated BulletTrain catalogue obligations, is recorded in `caid-manifest.json` and `PROMPT.md` so future CAID runs cannot allocate an ad hoc port.
