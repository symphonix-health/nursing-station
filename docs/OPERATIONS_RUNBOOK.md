# Phase 1 operations runbook

Install with `python -m pip install -e ".[dev]"` and `npm.cmd install` under `frontend`. Start the API with `python -m nursing_station.main` and the UI with `npm.cmd run dev`. `/health` must return `status: ok`, `database: durable-sqlite`, and `audit_chain_valid: true`.

Run `python -m pytest`, `python -m ruff check backend tests scripts`, `npm.cmd run build`, and `npm.cmd run test:e2e`. Treat any audit-chain failure, authorization failure, JavaScript console error, HTTP error, accessibility violation, or CAID `BLOCKED` result as a stop condition.

The default JWT key is development-only. Production requires managed secrets, TLS, central identity, backup and recovery, monitored storage, policy-approved warning-score configuration, and Clinical Safety Officer approval. Phase 2 integrations must fail explicitly when unavailable; no local success fallback is permitted.
