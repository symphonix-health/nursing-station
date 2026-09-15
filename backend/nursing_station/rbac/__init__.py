"""symphonix-rbac: estate-wide configurable role-capability enforcement.

Pure-stdlib core. The FastAPI integration is a lazy import so the engine can
be used in non-FastAPI contexts (CLI tools, background workers) and so
importing this package never pulls a web framework into a test process.

Public surface:
    PolicyEngine        load, verify, hot-reload, evaluate policy documents
    CapabilityDenied    structured denial exception
    lint                policy/source cross-check helpers (drift guard)
"""

from __future__ import annotations

from .engine import CapabilityDenied, PolicyEngine
from .signing import canonical_json, sign_payload, verify_signature

__all__ = [
    "CapabilityDenied",
    "PolicyEngine",
    "canonical_json",
    "sign_payload",
    "verify_signature",
]

__version__ = "1.0.0"