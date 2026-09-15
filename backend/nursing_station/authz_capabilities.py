"""Capability names granted per role, for tests and deny-text parity."""

from __future__ import annotations

from .auth_policy import engine


def granting_roles_for(capability: str) -> list[str]:
    """Roles in the live policy granted *capability*."""
    roles = engine().roles()
    return sorted(role for role, caps in roles.items() if capability in caps)