"""Build the signed RBAC capability policy for nursing-station.

Canonical SITES table: every runtime role gate in backend/nursing_station,
with the capability it maps to and the legacy role set that must keep access
exactly. backend/tests/test_policy_drift.py parses this table and asserts the
bijection with the live call sites.

Run from the repo root:  python scripts/build_policy.py
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "backend") not in sys.path:
    sys.path.insert(0, str(REPO / "backend"))

from nursing_station.rbac.signing import _POLICY_TAG, canonical_json  # noqa: E402

# (capability, [granting roles], [(file, line, function)])
# Roles are the repo's seeded vocabulary: registered_nurse / nurse_in_charge /
# clinical_safety_officer. Legacy deny contract: 403 plain-string
# "Role is not authorised for this action" (main.require_roles), pinned by
# tests/test_api.py + tests/test_national_capability.py.
SITES: list[tuple[str, list[str], list[tuple[str, int, str]]]] = [
    # ---- main.py (13 sites) ------------------------------------------------
    (
        "alerts.read",
        ["registered_nurse", "nurse_in_charge", "clinical_safety_officer"],
        [("backend/nursing_station/main.py", 270, "alerts")],
    ),
    (
        "alerts.acknowledge",
        ["registered_nurse", "nurse_in_charge", "clinical_safety_officer"],
        [("backend/nursing_station/main.py", 289, "acknowledge_alert")],
    ),
    (
        "hmis_measures.submit",
        ["nurse_in_charge", "clinical_safety_officer"],
        [("backend/nursing_station/main.py", 646, "submit_hmis_measures")],
    ),
    (
        "observation.write",
        ["registered_nurse", "nurse_in_charge"],
        [("backend/nursing_station/main.py", 1004, "add_observation")],
    ),
    (
        "task.create",
        ["registered_nurse", "nurse_in_charge"],
        [("backend/nursing_station/main.py", 1130, "create_task")],
    ),
    (
        "task.transition",
        ["registered_nurse", "nurse_in_charge"],
        [("backend/nursing_station/main.py", 1163, "transition_task")],
    ),
    (
        "handover.create",
        ["registered_nurse", "nurse_in_charge"],
        [("backend/nursing_station/main.py", 1225, "create_handover")],
    ),
    (
        "care_plan.create",
        ["registered_nurse", "nurse_in_charge"],
        [("backend/nursing_station/main.py", 1380, "create_care_plan")],
    ),
    (
        "care_plan.evaluate",
        ["registered_nurse", "nurse_in_charge"],
        [("backend/nursing_station/main.py", 1401, "evaluate_care_plan")],
    ),
    (
        "medication_administration.write",
        ["registered_nurse", "nurse_in_charge"],
        [("backend/nursing_station/main.py", 1444, "administer")],
    ),
    (
        "safety_assessment.write",
        ["registered_nurse", "nurse_in_charge"],
        [("backend/nursing_station/main.py", 1578, "assess")],
    ),
    (
        "audit.read",
        ["nurse_in_charge", "clinical_safety_officer"],
        [("backend/nursing_station/main.py", 1611, "audit_log")],
    ),
    # scoped_patient is a shared helper called from many routes; its embedded
    # gate is the patient.read capability family.
    (
        "patient.read",
        ["registered_nurse", "nurse_in_charge", "clinical_safety_officer"],
        [("backend/nursing_station/main.py", 127, "scoped_patient")],
    ),
    # ---- national_routes.py (23 sites) -------------------------------------
    (
        "country_pack.adopt",
        ["clinical_safety_officer"],
        [("backend/nursing_station/national_routes.py", 259, "record_adoption")],
    ),
    (
        "work_queue.read",
        ["registered_nurse", "nurse_in_charge", "clinical_safety_officer"],
        [("backend/nursing_station/national_routes.py", 307, "work_queue_view")],
    ),
    (
        "competency.read",
        ["registered_nurse", "nurse_in_charge", "clinical_safety_officer"],
        [("backend/nursing_station/national_routes.py", 380, "ward_competencies")],
    ),
    (
        "task_interruption.create",
        ["registered_nurse", "nurse_in_charge"],
        [("backend/nursing_station/national_routes.py", 403, "record_interruption")],
    ),
    (
        "task_interruption.resume",
        ["registered_nurse", "nurse_in_charge"],
        [("backend/nursing_station/national_routes.py", 437, "resume_interruption")],
    ),
    (
        "escalation.read",
        ["registered_nurse", "nurse_in_charge", "clinical_safety_officer"],
        [("backend/nursing_station/national_routes.py", 466, "escalations")],
    ),
    (
        "escalation.respond",
        ["registered_nurse", "nurse_in_charge"],
        [("backend/nursing_station/national_routes.py", 503, "record_escalation_response")],
    ),
    (
        "harm_incident.write",
        ["registered_nurse", "nurse_in_charge"],
        [("backend/nursing_station/national_routes.py", 585, "report_harm_incident")],
    ),
    (
        "harm_incident.read",
        ["registered_nurse", "nurse_in_charge", "clinical_safety_officer"],
        [("backend/nursing_station/national_routes.py", 662, "list_harm_incidents")],
    ),
    (
        "harm_incident.review",
        ["nurse_in_charge", "clinical_safety_officer"],
        [("backend/nursing_station/national_routes.py", 679, "review_harm_incident")],
    ),
    (
        "discharge_readiness.write",
        ["registered_nurse", "nurse_in_charge"],
        [("backend/nursing_station/national_routes.py", 747, "open_discharge_readiness")],
    ),
    (
        "discharge_readiness.confirm",
        ["registered_nurse", "nurse_in_charge"],
        [("backend/nursing_station/national_routes.py", 825, "confirm_criterion")],
    ),
    (
        "discharge_readiness.coordinate",
        ["registered_nurse", "nurse_in_charge"],
        [("backend/nursing_station/national_routes.py", 878, "coordinate_discharge")],
    ),
    (
        "discharge_readiness.complete",
        ["registered_nurse", "nurse_in_charge"],
        [("backend/nursing_station/national_routes.py", 977, "complete_discharge_readiness")],
    ),
    (
        "staffing.position_read",
        ["registered_nurse", "nurse_in_charge", "clinical_safety_officer"],
        [("backend/nursing_station/national_routes.py", 1048, "staffing_position")],
    ),
    (
        "staffing.roster_refresh",
        ["nurse_in_charge", "clinical_safety_officer"],
        [("backend/nursing_station/national_routes.py", 1070, "refresh_staffing_roster")],
    ),
    (
        "staffing.declare",
        ["nurse_in_charge"],
        [("backend/nursing_station/national_routes.py", 1141, "declare_staffing_shortage")],
    ),
    (
        "staffing.revoke",
        ["nurse_in_charge"],
        [("backend/nursing_station/national_routes.py", 1201, "revoke_staffing_declaration")],
    ),
    (
        "staffing.declarations_read",
        ["nurse_in_charge", "clinical_safety_officer"],
        [("backend/nursing_station/national_routes.py", 1228, "list_staffing_declarations")],
    ),
    (
        "quality_measures.read",
        ["nurse_in_charge", "clinical_safety_officer"],
        [("backend/nursing_station/national_routes.py", 1249, "quality_measures")],
    ),
    (
        "publications.read",
        ["nurse_in_charge", "clinical_safety_officer"],
        [("backend/nursing_station/national_routes.py", 1272, "list_publications")],
    ),
    (
        "publications.dispatch",
        ["nurse_in_charge", "clinical_safety_officer"],
        [("backend/nursing_station/national_routes.py", 1366, "dispatch_publication")],
    ),
    (
        "publications.dispatch_pending",
        ["nurse_in_charge", "clinical_safety_officer"],
        [("backend/nursing_station/national_routes.py", 1386, "dispatch_pending_publications")],
    ),
]

# Star-arg alias constants in main.py (AST-resolved by the drift test):
ROLE_ALIASES: dict[str, list[str]] = {}

SERVICE = "nursing-station"

# Development fallback key. Production MUST set SYMPHONIX_RBAC_SIGNING_KEY and
# use signing.sign_payload instead; the estate engine falls back to this exact
# key so the dev policy verifies out of the box.
_DEV_KEY = hashlib.sha256(b"symphonix-rbac-dev-key").digest()


def _granting(roles: list[str]) -> list[str]:
    return sorted(set(roles))


def build_policy() -> dict:
    roles: dict[str, list[str]] = {}
    for capability, granting, _sites in SITES:
        for role in _granting(granting):
            caps = set(roles.setdefault(role, []))
            caps.add(capability)
            roles[role] = sorted(caps)
    doc = {
        "service": SERVICE,
        "version": 1,
        "effective_at": "2026-09-14T00:00:00Z",
        "issued_by": "scripts/build_policy.py (RBAC rollout)",
        "roles": dict(sorted(roles.items())),
        "reserved_capabilities": [],
    }
    payload = _POLICY_TAG + canonical_json(doc)
    signature = "sha256=" + hmac.new(_DEV_KEY, payload, hashlib.sha256).hexdigest()
    return {**doc, "signature": signature}


def main() -> None:
    doc = build_policy()
    # Write with json.dumps (NOT canonical_json -- it strips the signature).
    out = REPO / "policies" / "policy.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"[OK] wrote {out} (v{doc['version']}, {len(doc['roles'])} roles, {len(SITES)} sites)")


if __name__ == "__main__":
    main()
