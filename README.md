# Nursing Station

Symphonix Health inpatient nursing workflow and ward-station clinical sibling.

Phase 1 is a complete standalone clinical workflow over durable seeded SQLite data. It includes ward and patient context, shared-screen privacy, observations and NEWS2-style escalation, nursing tasks and care plans, structured SBAR handover with named acceptance, medication-administration recording, safety assessments, append-only hash-chained audit, role- and ward-scoped access, and a responsive React clinical console.

Phase 2 will connect the boundary contracts to their authoritative Symphonix sibling systems through BulletTrain. Phase 1 does not simulate those integrations and makes no integration-readiness claim.

## Run

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
