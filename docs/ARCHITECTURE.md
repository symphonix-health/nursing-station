# Phase 1 architecture

The Nursing Station is a standalone Symphonix clinical sibling. React presents the ward and patient workflows. FastAPI owns authorization, validation, warning-score calculation, state transitions, and audit. SQLite is the durable Phase 1 store. Every clinical read is tenant and ward scoped; regulated writes are server-confirmed and hash-chain audited.

Phase 1 has no internal-service fallback, integration adapter, or simulated upstream success. The future patient, encounter, medication-order, laboratory, imaging, terminology, identity, event, and reporting boundaries are specified in `PHASE_2_INTEGRATION_CONTRACTS.md`. Phase 2 should replace local authority only after contract, security, reconciliation, failure-mode, and seeded cross-service evidence passes the existing gates.

The component is kept in its own repository because it owns a clinical bounded context, persistent schema, safety case, deployment lifecycle, frontend, and CAID evidence. It should later join the Symphonix service catalogue and BulletTrain dependency graph as a sibling, rather than becoming a UI folder in an unrelated clinical system.
