# Phase 2 operations runbook

Install with `python -m pip install -e ".[dev]"` and `npm.cmd install` under `frontend`. Set `NURSING_STATION_HUB_URL`, `NURSING_STATION_HUB_TOKEN`, and a bounded `NURSING_STATION_HUB_TIMEOUT_SECONDS`; start the API with `python -m nursing_station.main` and the UI with `npm.cmd run dev`. `/health` must return Phase 2, `status: ok`, `database: durable-sqlite`, `audit_chain_valid: true`, and `integrations: configured-bullettrain-hub`. Missing hub configuration is an intentional fail-closed state.

Set `NURSING_STATION_INBOUND_HMAC_SECRET` from the same secret-managed value used by the BulletTrain Nursing Station connector. The API rejects critical-result notifications when the secret, signature, event identity, patient link, tenant, or ward scope is missing or invalid. `NURSING_STATION_ALERT_REFRESH_SECONDS` defaults to five seconds; monitoring must alert when hub delivery fails, the dashboard does not revalidate, or the audit chain becomes invalid. Alert receipt never substitutes for human acknowledgement.

Run `python -m pytest`, `python -m ruff check backend tests scripts`, `npm.cmd run build`, and `npm.cmd run test:e2e`. Treat any audit-chain failure, authorization failure, JavaScript console error, HTTP error, accessibility violation, or CAID `BLOCKED` result as a stop condition.

The default JWT key is development-only. Production requires managed secrets, TLS, central identity, backup and recovery, monitored storage, policy-approved warning-score configuration, and Clinical Safety Officer approval. Phase 2 integrations must fail explicitly when unavailable; no local success fallback is permitted.
