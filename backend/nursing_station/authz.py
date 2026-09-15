"""Capability gates for nursing-station.

Replaces the legacy hardcoded role gate (main.require_roles) with the signed
capability policy while preserving the legacy deny contract verbatim:

    HTTP 403, detail "Role is not authorised for this action"

Both gate helpers raise through the same HTTPException shape the tests pin
(tests/test_api.py, tests/test_national_capability.py).
"""

from __future__ import annotations

from fastapi import HTTPException

from .auth_policy import engine

DENY_DETAIL = "Role is not authorised for this action"


def _held_roles(user: object) -> list[str]:
    role = getattr(user, "role", None)
    if isinstance(role, str) and role:
        return [role]
    if isinstance(role, (list, tuple, set)):
        return [str(r) for r in role if r]
    return []


def require_capability(user: object, capability: str) -> None:
    """Imperative in-handler gate (legacy require_roles shape)."""
    if not engine().allowed(_held_roles(user), capability):
        raise HTTPException(status_code=403, detail=DENY_DETAIL)


def granting_roles_for(capability: str) -> list[str]:
    """Roles in the live policy granted *capability* (for deny-text parity)."""
    roles = engine().roles()
    return sorted(role for role, caps in roles.items() if capability in caps)


def make_capability_check(capability: str):
    """Return a Depends-compatible callable enforcing *capability*.

    Matches the legacy Depends(user) -> gate call ordering used by
    national_routes via ctx; the gate runs inside the handler, preserving the
    legacy call shape exactly.
    """

    def _check(user: object) -> object:
        require_capability(user, capability)
        return user

    return _check_dep if False else _make_dep(capability)


def _make_dep(capability: str):
    def _dep(user: object) -> object:
        require_capability(user, capability)
        return user

    return _dep


_check_dep = None
