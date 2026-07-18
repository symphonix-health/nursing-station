# Phase 2 architecture

The Nursing Station is a Symphonix clinical sibling. React presents the ward and patient workflows. FastAPI owns authorization, validation, warning-score calculation, state transitions, integration reconciliation, and audit. SQLite is the durable nursing and integration-snapshot store. Every clinical read is tenant and ward scoped; regulated writes are server-confirmed and hash-chain audited.

Phase 2 sends sibling traffic to the authenticated BulletTrain connector hub. PICIS owns patient and encounter context; LIS owns laboratory results; PACS/RIS owns imaging; pharmacy-system owns requests and dispensing; blood-transfusion owns blood-product state; HMIS receives allow-listed ward aggregates. Nursing-owned observations, tasks, care plans, handovers, assessments, and medication administrations are never overwritten by imported snapshots. There is no direct sibling call or selectable fallback.

The component remains in its own repository because it owns a clinical bounded context, persistent schema, safety case, deployment lifecycle, frontend, and CAID evidence. The backend and frontend resolve ports 9201 and 5282 from `workspace-tooling/ports.workspace.json`; sibling traffic reuses existing registered ports through api_gateway on 8000. BulletTrain owns six Phase 2 interface rows and the generated interface network.
