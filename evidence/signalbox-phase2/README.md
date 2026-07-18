# Phase 2 headed SignalBox evidence

This directory contains signed, GHARRA-verifiable SignalBox evidence for the registered BulletTrain-to-Nursing Station workflow. The browser ran headed against the real seeded services and dedicated workspace ports. No page reload, direct callback bypass, internal service substitute, or synthetic telemetry was used.

- `7a8405ca-69dc-4e52-aa65-643d12ea2532`: nurse persona, pre-event ward dashboard, 17 of 17 assertions passed.
- `9424e94f-f02f-4727-a9f9-3bc925b493a0`: nurse persona, live critical alert appeared without navigation or reload, 4 of 4 assertions passed.
- `f97be553-e35e-4a36-84e5-8c4bd3ab7552`: nurse-superpersona, five-source review, alert provenance, explicit acknowledgement, and dashboard refresh, 20 of 20 assertions passed.

`phase2-headed-result.json` records the governed source event and alert identity. Each referenced manifest has a valid Ed25519 signature, evidence anchor, schema, headed-session flag, non-blank screenshot check, and passing step set. Only the public verification key is retained; the private evidence-signing key is excluded from version control.
