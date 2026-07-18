from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GATE_PATH = ROOT / "safety" / "CLINICAL_DEPLOYMENT_GATE.json"

REQUIRED_AGENT_CHECKS = {
    "nursing_station_tests",
    "frontend_build",
    "real_seeded_journey",
    "headed_nurse_persona",
    "headed_live_alert",
    "headed_nurse_superpersona",
    "caid_test_agent",
    "caid_fpfn",
    "caid_post_build_gatekeeper",
    "bullettrain_pre_push",
    "hazards_reviewed",
}

AGENT_CSO_CONTRACT = {
    "persona_id": "clinical-safety-officer-superpersona",
    "persona_version": "1.0.0",
    "maturity": "M2-validated",
    "authority": "prepare_evidence_and_recommend_only",
    "operating_procedure": "safety/AGENT_CSO_HITL_PROCEDURE.md",
    "evidence_scope": "governance_metadata_and_deidentified_assurance_evidence",
}


def evaluate_gate(record: dict[str, Any], *, root: Path = ROOT) -> dict[str, Any]:
    blockers: list[str] = []
    scope = record.get("scope", {})
    agent = record.get("agent_key", {})
    human = record.get("human_key", {})
    decision = record.get("decision", {})

    for field, expected in AGENT_CSO_CONTRACT.items():
        if agent.get(field) != expected:
            blockers.append(f"agent_competence_contract_mismatch:{field}")
    if agent.get("status") != "passed":
        blockers.append("agent_assurance_not_passed")
    if agent.get("recommendation") != "approve_declared_scope":
        blockers.append("agent_did_not_recommend_approval")
    if agent.get("professional_registration_claimed") is not False:
        blockers.append("agent_must_not_claim_professional_registration")

    checks = agent.get("checks", {})
    for check in sorted(REQUIRED_AGENT_CHECKS):
        if not str(checks.get(check, "")).startswith("passed"):
            blockers.append(f"agent_check_not_passed:{check}")
    for relative in agent.get("evidence", []):
        if not (root / relative).is_file():
            blockers.append(f"evidence_missing:{relative}")

    if human.get("status") != "approved":
        blockers.append("human_approval_missing")
    if human.get("decision") != "approve_declared_scope":
        blockers.append("human_did_not_approve")
    if not str(human.get("approver_identity", "")).strip():
        blockers.append("human_identity_missing")
    if human.get("scope") != scope.get("deployment_class"):
        blockers.append("human_scope_mismatch")

    if scope.get("deployment_class") == "synthetic_clinical_simulation":
        if scope.get("data_class") != "seeded_synthetic":
            blockers.append("synthetic_scope_data_class_mismatch")
        for flag in ("live_patient_data", "pseudonymised_patient_data", "production_clinical_use"):
            if scope.get(flag) is not False:
                blockers.append(f"synthetic_scope_forbids:{flag}")
    else:
        registration_gate = record.get("professional_registration_gate", {})
        if registration_gate.get("status") != "verified_for_declared_live_scope":
            blockers.append("live_scope_professional_registration_not_verified")
        if not human.get("professional_registration_claimed"):
            blockers.append("live_scope_requires_accountable_registered_human")

    expected_status = "approved" if not blockers else "blocked"
    if decision.get("status") != expected_status:
        blockers.append("recorded_decision_does_not_match_two_key_evaluation")
        expected_status = "blocked"

    return {
        "decision_id": record.get("decision_id"),
        "status": expected_status,
        "scope": scope.get("deployment_class"),
        "agent_persona": agent.get("persona_id"),
        "agent_competence_contract": "passed"
        if not any(blocker.startswith("agent_competence_contract_mismatch:") for blocker in blockers)
        else "failed",
        "human_approval": human.get("status"),
        "blockers": blockers,
    }


def main() -> int:
    record = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    result = evaluate_gate(record)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "approved" else 1


if __name__ == "__main__":
    raise SystemExit(main())
