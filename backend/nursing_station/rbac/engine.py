"""PolicyEngine: load, verify, hot-reload and evaluate role-capability policies.

Fail-closed semantics:
    - Missing policy file at boot            -> RuntimeError (startup failure)
    - Invalid signature on any document      -> RuntimeError
    - Version rollback (lower than loaded)   -> ignored, last-good kept
    - Unparsable refresh payload             -> last-good kept, error logged
    - No policy at all for a capability gate -> denied

Hot reload: `refresh()` re-reads the bound source (file or HTTP URL) and
swaps the in-memory policy atomically if the document verifies and its
version is higher. Call it from a background poller, a webhook handler, or
a lifespan task.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable

from .signing import default_verify_key, verify_signature

log = logging.getLogger("symphonix.rbac")

# Module-level fastapi import so that `request: Request` annotations on
# dependency factories resolve via get_type_hints() (which reads module
# globals). Guarded so non-web consumers (CLI, workers) can still import
# the engine without fastapi installed.
try:
    from fastapi import Request as _Request
except ImportError:  # pragma: no cover - non-web consumer
    _Request = None  # type: ignore[assignment,misc]

_ALLOWED_TOP_KEYS = {"service", "version", "effective_at", "issued_by",
                     "roles", "reserved_capabilities", "signature"}
_RESERVED = "__reserved__"


class CapabilityDenied(Exception):
    """Structured denial: raised when roles lack a required capability.

    deny_shape='capability' (default):
        {"detail": "forbidden", "required_capability": ...,
         "held_roles": [...]}
    deny_shape='role_forbidden':
        {"error": "role_forbidden", "required_capability": ...,
         "held_roles": [...], "required_roles": ["<capability:%s>"]}
        — preserves the legacy {error: role_forbidden} contract repos pin
        in tests (e.g. analytics-bi test_coverage_gaps_refusals).
    """

    def __init__(self, capability: str, held_roles: list[str],
                 deny_shape: str = "capability"):
        self.capability = capability
        self.held_roles = held_roles
        self.deny_shape = deny_shape
        super().__init__(
            f"forbidden: missing capability '{capability}' "
            f"(held roles: {held_roles or ['<anonymous>']})"
        )

    def payload(self, granting_roles: list[str] | None = None) -> dict[str, Any]:
        if self.deny_shape == "role_forbidden":
            # required_roles mirrors the legacy shape: the roles that DO hold
            # the capability (resolved from the live policy), so a caller can
            # see who is allowed — exactly what require_role used to emit.
            roles = granting_roles or [f"capability:{self.capability}"]
            return {
                "error": "role_forbidden",
                "required_capability": self.capability,
                "required_roles": roles,
                "held_roles": self.held_roles,
            }
        return {
            "detail": "forbidden",
            "required_capability": self.capability,
            "held_roles": self.held_roles,
        }


class PolicyEngine:
    """In-memory policy holder with verified hot-reload."""

    def __init__(self, service: str, policy_path: Path | str | None = None,
                 verify_key: bytes | None = None,
                 allow_unsigned_dev: bool | None = None,
                 deny_shape: str = "capability"):
        self.service = service
        self._path = Path(policy_path) if policy_path else self._env_path()
        self._key = verify_key or default_verify_key()
        self._deny_shape = deny_shape
        # Unsigned policies are permitted only when explicitly enabled AND
        # the environment is not production; default is signed-only.
        if allow_unsigned_dev is None:
            allow_unsigned_dev = os.environ.get(
                "SYMPHONIX_RBAC_ALLOW_UNSIGNED", ""
            ).lower() in {"1", "true", "yes"}
        self._allow_unsigned_dev = allow_unsigned_dev
        self._lock = threading.Lock()
        self._policy: dict[str, Any] | None = None
        self._version = 0
        self._load_boot()

    # ------------------------------------------------------------------ boot
    @staticmethod
    def _env_path() -> Path | None:
        custom = os.environ.get("SYMPHONIX_RBAC_POLICY_PATH")
        if custom:
            return Path(custom)
        # Conventional per-repo location: <repo>/policies/policy.json
        for base in (Path.cwd(), Path.cwd().parent):
            candidate = base / "policies" / "policy.json"
            if candidate.is_file():
                return candidate
        return None

    def _load_boot(self) -> None:
        if self._path is None or not self._path.is_file():
            raise RuntimeError(
                f"[FAIL] no policy document for service '{self.service}' "
                f"(looked at {self._path or '<unset>'}); boot is fail-closed"
            )
        doc = self._read_verified(self._path)
        self._apply(doc, source=str(self._path))

    # --------------------------------------------------------------- loading
    def _read_verified(self, path: Path) -> dict[str, Any]:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return self._verify_doc(raw)

    def _verify_doc(self, doc: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(doc, dict):
            raise RuntimeError("[FAIL] policy document is not an object")
        unknown = set(doc) - _ALLOWED_TOP_KEYS
        if unknown:
            raise RuntimeError(f"[FAIL] policy has unknown keys: {sorted(unknown)}")
        sig = doc.get("signature")
        if not sig or not isinstance(sig, str):
            if self._allow_unsigned_dev and os.environ.get("SYMPHONIX_ENV") != "production":
                log.warning("[WARN] accepting UNSIGNED policy (dev mode)")
            else:
                raise RuntimeError("[FAIL] policy document is unsigned")
        elif not verify_signature(doc, sig, self._key):
            raise RuntimeError("[FAIL] policy signature verification failed")
        if doc.get("service") != self.service:
            raise RuntimeError(
                f"[FAIL] policy service mismatch: doc={doc.get('service')!r} "
                f"engine={self.service!r}"
            )
        roles = doc.get("roles")
        if not isinstance(roles, dict) or not roles:
            raise RuntimeError("[FAIL] policy 'roles' must be a non-empty object")
        for role, caps in roles.items():
            if not isinstance(role, str) or not role:
                raise RuntimeError("[FAIL] policy role names must be non-empty strings")
            if not isinstance(caps, list) or not all(isinstance(c, str) and c for c in caps):
                raise RuntimeError(f"[FAIL] role '{role}' capabilities must be a list of strings")
            if "*" in caps:
                raise RuntimeError(f"[FAIL] wildcard capability rejected for role '{role}'")
        return doc

    def _apply(self, doc: dict[str, Any], source: str) -> None:
        version = int(doc.get("version", 0))
        with self._lock:
            if version < self._version:
                log.warning(
                    "[WARN] ignoring policy v%d from %s (running v%d)",
                    version, source, self._version,
                )
                return
            self._policy = doc
            self._version = version
        log.info("[OK] loaded policy %s v%d from %s", self.service, version, source)

    # ---------------------------------------------------------------- access
    @property
    def version(self) -> int:
        with self._lock:
            return self._version

    @property
    def policy(self) -> dict[str, Any]:
        with self._lock:
            if self._policy is None:  # pragma: no cover - boot guarantees load
                raise RuntimeError("[FAIL] no policy loaded")
            return self._policy

    def roles(self) -> dict[str, list[str]]:
        return dict(self.policy["roles"])

    def declared_capabilities(self) -> set[str]:
        caps: set[str] = set()
        for granted in self.policy["roles"].values():
            caps.update(granted)
        for r in self.policy.get("reserved_capabilities", []):
            caps.add(r if isinstance(r, str) else r["name"])
        return caps

    def allowed(self, held_roles: Iterable[str], capability: str) -> bool:
        with self._lock:
            policy = self._policy
        if policy is None:
            return False
        granted: set[str] = set()
        roles = set(held_roles)
        for role, caps in policy["roles"].items():
            if role in roles:
                granted.update(caps)
        return capability in granted

    def require(self, *capabilities: str,
                auth_dependency: Any = None) -> Callable[..., Awaitable[None]]:
        """FastAPI dependency factory. 401 unauthenticated, 403 without cap.

        auth_dependency: the host repo's FastAPI auth dependency (e.g. its
        ``require_auth``), which returns the authenticated principal. The
        capability gate composes it with ``Depends`` so identity resolution
        stays the repo's own — the engine never guesses where the principal
        lives. Without it, the gate falls back to ``request.state.auth``
        (middleware-injected principals).
        """
        # fastapi is imported at module level below (see _Request); the
        # dependency's `request: Request` annotation MUST be resolvable via
        # get_type_hints(), which reads module globals -- a function-local
        # import would leave the annotation unresolvable and FastAPI would
        # then treat `request` as a query parameter (422 on every call).
        from fastapi import Depends, HTTPException, status

        engine = self

        def _held(auth: Any) -> list[str]:
            roles = list(getattr(auth, "roles", None) or [])
            if not roles and getattr(auth, "role", None):
                roles = [str(auth.role)]
            return roles

        def _enforce(held: list[str]) -> None:
            for cap in capabilities:
                if not engine.allowed(held, cap):
                    # Roles that legitimately hold the capability, resolved
                    # from the live policy: the legacy required_roles contract.
                    granting = sorted(
                        role for role, caps in engine.roles().items() if cap in caps
                    )
                    log.info(
                        "[DENY] capability=%s held_roles=%s", cap, held,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=CapabilityDenied(
                            cap, held, deny_shape=engine._deny_shape
                        ).payload(granting_roles=granting),
                    )

        if auth_dependency is not None:
            async def dependency(
                _auth: Any = Depends(auth_dependency),
            ) -> Any:
                """Authenticate via the host repo, then enforce capabilities.

                Returns the principal: repo handlers annotate
                ``auth: AuthContext = Depends(require_capability(...))`` and
                use it, so the gate must yield the auth context (same
                contract as the require_role it replaced).
                """
                _enforce(_held(_auth))
                return _auth
        else:
            async def dependency(request: _Request) -> Any:
                auth = getattr(request.state, "auth", None)
                if auth is None:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="unauthenticated",
                    )
                _enforce(_held(auth))
                return auth

        dependency.__name__ = f"require_capability_{ '_'.join(capabilities) }"
        return dependency

    # ------------------------------------------------------------- hot reload
    def refresh(self) -> bool:
        """Re-read the bound source; returns True if a newer policy applied."""
        if self._path is None or not self._path.is_file():
            log.error("[ERROR] refresh failed: policy source missing")
            return False
        try:
            doc = self._read_verified(self._path)
        except Exception as exc:  # unparsable/unsigned refresh keeps last-good
            log.error("[ERROR] refresh failed: %s", exc)
            return False
        current = self.version
        if int(doc.get("version", 0)) <= current:
            return False
        self._apply(doc, source=f"refresh:{self._path}")
        return True