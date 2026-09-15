"""Canonical JSON serialisation and HMAC-SHA256 signing for policy documents.

The signature is computed over the canonical JSON of the policy document
*excluding* its "signature" field, so the payload is byte-stable across
platforms and JSON re-serialisations.

Key discovery order (fail-closed: no key -> refuse to sign):
    1. SYMPHONIX_RBAC_SIGNING_KEY   (hex-encoded key material)
    2. SYMPHONIX_RBAC_SIGNING_KEY_FILE (path to a file containing hex key)
    3. Estate identity root key file, if SYMPHONIX_IDENTITY_ROOT is set
       and <root>/keys/policy-signing.key exists
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any

_POLICY_TAG = b"symphonix-rbac-policy-v1"


def canonical_json(payload: dict[str, Any]) -> bytes:
    """Serialise to byte-stable canonical JSON: sorted keys, no whitespace."""
    stripped = {k: v for k, v in payload.items() if k != "signature"}
    return json.dumps(stripped, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _load_key() -> bytes | None:
    env_key = os.environ.get("SYMPHONIX_RBAC_SIGNING_KEY")
    if env_key:
        return bytes.fromhex(env_key)
    key_file = os.environ.get("SYMPHONIX_RBAC_SIGNING_KEY_FILE")
    if key_file and Path(key_file).is_file():
        return bytes.fromhex(Path(key_file).read_text(encoding="utf-8").strip())
    identity_root = os.environ.get("SYMPHONIX_IDENTITY_ROOT")
    if identity_root:
        candidate = Path(identity_root) / "keys" / "policy-signing.key"
        if candidate.is_file():
            return bytes.fromhex(candidate.read_text(encoding="utf-8").strip())
    return None


def sign_payload(payload: dict[str, Any]) -> str:
    """Return 'sha256=<hex>' signature over the canonical payload."""
    key = _load_key()
    if key is None:
        raise RuntimeError(
            "[FAIL] no signing key available; set SYMPHONIX_RBAC_SIGNING_KEY "
            "or SYMPHONIX_RBAC_SIGNING_KEY_FILE"
        )
    mac = hmac.new(key, _POLICY_TAG + canonical_json(payload), hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def verify_signature(payload: dict[str, Any], signature: str, key: bytes) -> bool:
    """Constant-time verification of a policy document signature."""
    if not signature.startswith("sha256="):
        return False
    expected_hex = signature.removeprefix("sha256=")
    mac = hmac.new(key, _POLICY_TAG + canonical_json(payload), hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), expected_hex)


def default_verify_key() -> bytes:
    """Key used by consumers to verify; same discovery order, dev fallback."""
    key = _load_key()
    if key is not None:
        return key
    # Dev/test fallback so unit tests can run without provisioning.
    # Production boot with no key is a hard failure in the engine.
    return hashlib.sha256(b"symphonix-rbac-dev-key").digest()