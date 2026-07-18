# Agent Clinical Safety Officer and human approval procedure

## Purpose

Nursing Station uses the registered `clinical-safety-officer-superpersona` to perform the repeatable clinical-safety review. The agent assembles evidence, checks hazards, runs the assurance battery, records exceptions, and recommends approve or reject. A human reviews that packet and makes the release decision. Neither key is sufficient by itself.

The agent is a governed assurance actor, not a legal person. It does not claim a professional registration, statutory office, or signature. Its competence is evidenced through the global agent registry, required skills, tests, maturity level, tool policy, and execution evidence. Human accountability and agent competence are recorded separately.

## Registered actor

- Persona: `clinical-safety-officer-superpersona`
- Registry: `symphonix-health/global-agent-registry`, `seed_data/superpersona_registry/personas.json`
- Version: `1.0.0`
- Maturity: `M2`, validated
- Permitted information: governance metadata and de-identified evidence
- Authority: evidence preparation and recommendation only
- Escalation: human clinical-safety review
- Break glass: unavailable

## Agent procedure

For each release scope, the persona must:

1. Confirm intended use, data class, deployment class, jurisdiction, and excluded uses.
2. Review the clinical risk-management plan, hazard log, integration hazards, DPIA, privacy notice, retention policy, operational runbook, requirements and traceability.
3. Run the Nursing Station tests, CAID test-agent, FP/FN audit, safety-scope assessment, integration scan and post-build review.
4. Review real seeded-service and headed SignalBox evidence, including nurse and nurse-superpersona workflows.
5. Check that no unacceptable residual risk, open high-risk hazard, internal substitute, hardcoded listener, missing audit evidence, or unbounded autonomous clinical action is accepted.
6. Produce a scope-bound recommendation with evidence references, conditions, exceptions, expiry and re-review triggers.
7. Route the packet to a human. The agent cannot populate the human decision.

## Human procedure

The human must review the complete packet, confirm the exact scope, and choose approve or reject. Approval is invalid if its scope differs from the agent recommendation or if a required agent check is missing. The decision records the human role, session identity, date, statement and scope.

For the governed synthetic clinical-simulation scope, the accountable product owner or release authority may approve because the system processes only declared fictional data and is not placed into live patient care. Live-patient deployment remains a separate decision and requires the deploying organisation's named accountable human roles, including a professionally registered CSO where the applicable jurisdiction requires one, plus controller-specific privacy and regulatory decisions.

## Decision states

- `pending_agent_review`: evidence battery incomplete.
- `pending_human_approval`: agent passed and recommended, but no human decision exists.
- `approved`: both keys passed for the exact declared scope.
- `rejected`: the human rejected the recommendation.
- `blocked`: a required check failed, the scopes differ, or an approval attribute is missing.
- `revoked`: a later change, incident, expiry or evidence regression invalidated approval.

## Re-review triggers

Approval is invalidated by live or pseudonymised patient data, a new tenant or jurisdiction, warning-score or escalation-policy changes, new clinical functionality, integration-contract changes, changed safety controls, open high-risk hazards, failed audit verification, failed real-service or headed evidence, material dependency changes, or expiry of the review period.

The machine-readable decision is `safety/CLINICAL_DEPLOYMENT_GATE.json`. `scripts/evaluate_clinical_deployment_gate.py` fails closed when the two-key contract is not satisfied.

## Professional-registration checks

The same agent-persona and human-approval pattern applies when a gate depends on professional registration. A competence-scoped governance persona collects the claimed role, jurisdiction, register, registration identifier, current status, scope of practice, restrictions, and evidence timestamp. It reports a recommendation and any mismatch. A human registration authority or accountable release authority reviews that packet and approves or rejects its use for the declared deployment scope.

The persona does not issue, renew, suspend, or represent a professional registration, and it cannot turn an unregistered human into a registrant. For a live deployment, the two-key record must identify the relevant human registrant and current source evidence. Missing, expired, jurisdiction-mismatched, or unverifiable registration blocks the gate.
