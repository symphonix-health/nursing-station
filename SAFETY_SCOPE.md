# Clinical Safety Scope - nursing-station

- **Decided at:** gatekeeper invocation
- **CSAA available:** True (transport: library)
- **Scope:** `cds_support`
- **CSAA invocation required:** True
- **MHRA review required:** True
- **DPIA required:** True

## Rationale

scope_override:cds_support accepted. Override rationale: The component calculates a warning score from clinical observations and creates deterioration escalation actions, so clinical safety and decision-support assurance are mandatory. CSAA automatic classification was out_of_scope.

## Release readiness

- **Assessment execution:** `succeeded`
- **Release gate:** `blocked`

### Blocking conditions

- The canonical intended-use statement requires human CSO approval.
- Human CSO approval is not evidenced by this generated draft.
- Release-authority and top-management acceptance are not evidenced.
- Required DPIA completion and DPO approval are not evidenced.
- Required MHRA review is not evidenced.
