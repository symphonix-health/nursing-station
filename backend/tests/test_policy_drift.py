"""Drift tests pinning the signed capability policy to the live source.

The SITES table in scripts/build_policy.py is the canonical map from
(file, line) -> capability. These tests assert the bijection: every gate call
in the source matches the table, and every table row has a live gate.

Run:  pytest backend/tests/test_policy_drift.py  (PYTHONPATH=backend)
"""

from __future__ import annotations

import ast
import hashlib
import hmac
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from nursing_station.auth_policy import engine as _engine  # noqa: E402
from nursing_station.rbac.signing import (  # noqa: E402
    _POLICY_TAG,
    canonical_json,
    default_verify_key,
)

POLICY_PATH = REPO / "policies" / "policy.json"


def _role_aliases(src: str) -> dict[str, set[str]]:
    """Resolve module-level alias constants to concrete role-name sets.

    Handles chains: NURSES = ["registered_nurse", ...]; STAFF = NURSES + [...]
    """
    tree = ast.parse(src)
    raw: dict[str, ast.expr] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    raw[t.id] = node.value
    out: dict[str, set[str]] = {}
    changed = True
    while changed:
        changed = False
        for name, value in raw.items():
            resolved: set[str] = set()
            if isinstance(value, (ast.List | ast.Tuple | ast.Set)):
                for e in value.elts:
                    if isinstance(e, ast.Constant) and isinstance(e.value, str):
                        resolved.add(e.value)
                    elif isinstance(e, ast.Name) and e.id in out:
                        resolved |= out[e.id]
            elif isinstance(value, ast.Constant) and isinstance(value.value, str):
                resolved = {value.value}
            if resolved and out.get(name) != resolved:
                out[name] = resolved
                changed = True
    return out


def _site_map() -> dict[tuple[str, int], str]:
    """Read the (file, line) -> capability map from scripts/build_policy.py."""

    src = (REPO / "scripts" / "build_policy.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, ast.Assign):
            targets = [t for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            targets = [node.target]
        for t in targets:
            if t.id == "SITES":
                sites = {}
                for elt in node.value.elts:
                    cap = elt.elts[0].value
                    sites_list = elt.elts[2]
                    for loc in sites_list.elts:
                        fname = loc.elts[0].value
                        lineno = loc.elts[1].value
                        sites[(fname, lineno)] = cap
                return sites
    raise AssertionError("SITES table not found in scripts/build_policy.py")


def _source_gates() -> dict[tuple[str, int], tuple[str, set[str]]]:
    """Find every live require_capability gate call in the backend source.

    Returns {(file, line): (capability, legacy-roles-from-comment-or-args)}.
    """
    gates: dict[tuple[str, int], tuple[str, set[str]]] = {}
    for py in (BACKEND / "nursing_station").rglob("*.py"):
        rel = py.relative_to(REPO).as_posix()
        if rel.startswith("backend/nursing_station/rbac/"):
            continue  # vendored engine: not gate-bearing source
        src = py.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else (
                fn.attr if isinstance(fn, ast.Attribute) else "")
            if name not in ("require_capability", "allowed"):
                continue
            if name == "allowed":
                continue  # engine-internal; drift is pinned via SITES
            # capability is arg[1] for require_capability(user, "cap")
            if len(node.args) < 2:
                continue
            cap_node = node.args[1]
            if not (isinstance(cap_node, ast.Constant) and isinstance(cap_node.value, str)):
                continue
            gates[(rel, node.lineno)] = (cap_node.value, set())
    return gates


def test_policy_file_exists_and_parses() -> None:
    doc = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    assert doc["service"] == "nursing-station"
    assert isinstance(doc["version"], int)


def test_policy_signature_verifies() -> None:
    doc = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    signature = doc.pop("signature")
    payload = _POLICY_TAG + canonical_json(doc)
    assert payload is not None
    key = default_verify_key()
    assert key is not None

    expected = "sha256=" + hmac.new(key, payload, hashlib.sha256).hexdigest()
    assert hmac.compare_digest(signature, expected), "policy signature does not verify"


def test_site_map_covers_every_source_gate() -> None:
    sites = _site_map()
    gates = _source_gates()
    missing = set(gates) - set(sites)
    extra = set(sites) - set(gates)
    assert not missing, f"gates in source missing from SITES: {sorted(missing)}"
    assert not extra, f"SITES rows with no live gate: {sorted(extra)}"


def test_gate_site_count_matches_source_calls() -> None:
    sites = _site_map()
    gates = _source_gates()
    assert len(gates) == len(sites) == 36


def test_every_site_capability_is_declared() -> None:
    _e = _engine()
    declared = set(_e.declared_capabilities())
    sites = _site_map()
    for key, cap in sites.items():
        assert cap in declared, f"{key}: capability {cap} not declared in policy"


def test_legacy_role_sets_match_policy_grants() -> None:
    """Every (site capability, legacy role list) pair from main must match the policy."""
    # Legacy role sets (verbatim from the pre-migration require_roles calls).
    legacy = {
        "alerts.read": {"registered_nurse", "nurse_in_charge", "clinical_safety_officer"},
        "alerts.acknowledge": {"registered_nurse", "nurse_in_charge", "clinical_safety_officer"},
        "hmis_measures.submit": {"nurse_in_charge", "clinical_safety_officer"},
        "observation.write": {"registered_nurse", "nurse_in_charge"},
        "task.create": {"registered_nurse", "nurse_in_charge"},
        "task.transition": {"registered_nurse", "nurse_in_charge"},
        "handover.create": {"registered_nurse", "nurse_in_charge"},
        "care_plan.create": {"registered_nurse", "nurse_in_charge"},
        "care_plan.evaluate": {"registered_nurse", "nurse_in_charge"},
        "medication_administration.write": {"registered_nurse", "nurse_in_charge"},
        "safety_assessment.write": {"registered_nurse", "nurse_in_charge"},
        "audit.read": {"nurse_in_charge", "clinical_safety_officer"},
        "patient.read": {"registered_nurse", "nurse_in_charge", "clinical_safety_officer"},
        "country_pack.adopt": {"clinical_safety_officer"},
        "work_queue.read": {"registered_nurse", "nurse_in_charge", "clinical_safety_officer"},
        "competency.read": {"registered_nurse", "nurse_in_charge", "clinical_safety_officer"},
        "task_interruption.create": {"registered_nurse", "nurse_in_charge"},
        "task_interruption.resume": {"registered_nurse", "nurse_in_charge"},
        "escalation.read": {"registered_nurse", "nurse_in_charge", "clinical_safety_officer"},
        "escalation.respond": {"registered_nurse", "nurse_in_charge"},
        "harm_incident.write": {"registered_nurse", "nurse_in_charge"},
        "harm_incident.read": {"registered_nurse", "nurse_in_charge", "clinical_safety_officer"},
        "harm_incident.review": {"nurse_in_charge", "clinical_safety_officer"},
        "discharge_readiness.write": {"registered_nurse", "nurse_in_charge"},
        "discharge_readiness.confirm": {"registered_nurse", "nurse_in_charge"},
        "discharge_readiness.coordinate": {"registered_nurse", "nurse_in_charge"},
        "discharge_readiness.complete": {"registered_nurse", "nurse_in_charge"},
        "staffing.position_read": {"registered_nurse", "nurse_in_charge", "clinical_safety_officer"},
        "staffing.roster_refresh": {"nurse_in_charge", "clinical_safety_officer"},
        "staffing.declare": {"nurse_in_charge"},
        "staffing.revoke": {"nurse_in_charge"},
        "staffing.declarations_read": {"nurse_in_charge", "clinical_safety_officer"},
        "quality_measures.read": {"nurse_in_charge", "clinical_safety_officer"},
        "publications.read": {"nurse_in_charge", "clinical_safety_officer"},
        "publications.dispatch": {"nurse_in_charge", "clinical_safety_officer"},
        "publications.dispatch_pending": {"nurse_in_charge", "clinical_safety_officer"},
    }
    _e = _engine()
    roles = _e.roles()
    for cap, expected_roles in legacy.items():
        holders = {role for role, caps in roles.items() if cap in caps}
        assert holders == expected_roles, (
            f"capability {cap}: policy holders {sorted(holders)} != legacy {sorted(expected_roles)}"
        )


def test_deny_text_is_pinned() -> None:
    src = (BACKEND / "nursing_station" / "authz.py").read_text(encoding="utf-8")
    assert 'DENY_DETAIL = "Role is not authorised for this action"' in src
    main_src = (BACKEND / "nursing_station" / "main.py").read_text(encoding="utf-8")
    # The legacy factory keeps its deny text (retained for non-migrated callers).
    assert '"Role is not authorised for this action"' in main_src


def test_vendored_engine_matches_estate_library() -> None:
    estate = REPO.parent / "workspace-tooling" / "rbac" / "symphonix_rbac"
    if not estate.exists():
        return  # estate not present in isolated checkouts

    for name in ("__init__.py", "engine.py", "lint.py", "signing.py"):
        vendored = (BACKEND / "nursing_station" / "rbac" / name).read_bytes()
        canonical = (estate / name).read_bytes()
        a = hashlib.sha256(vendored).hexdigest()
        b = hashlib.sha256(canonical).hexdigest()
        assert a == b, f"vendored {name} drifted from the estate library"


def test_policy_engine_grants_match_raw_policy_doc() -> None:
    doc = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    _e = _engine()
    assert _e.roles() == {r: sorted(c) for r, c in doc["roles"].items()}


def test_seeded_roles_hold_their_legacy_access() -> None:
    """The 3 seeded roles must be able to do everything they could before."""
    _e = _engine()
    probes = [
        ("registered_nurse", "observation.write"),
        ("registered_nurse", "alerts.read"),
        ("nurse_in_charge", "audit.read"),
        ("nurse_in_charge", "staffing.declare"),
        ("clinical_safety_officer", "country_pack.adopt"),
        ("clinical_safety_officer", "harm_incident.review"),
    ]
    for role, cap in probes:
        assert _e.allowed([role], cap), f"{role} lost {cap}"


def test_patient_role_is_absent_from_the_vocabulary() -> None:
    """nursing-station has no patient-facing role; none may be invented."""
    _e = _engine()
    assert "patient" not in _e.roles()
