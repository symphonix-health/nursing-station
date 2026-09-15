"""PolicyEngine singleton for nursing-station (signed capability policy).

Loads policies/policy.json at import; the path can be overridden with
NURSING_STATION_POLICY_PATH. Gate helpers live in authz.py to keep this module
import-light.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from .rbac.engine import PolicyEngine


def _default_policy_path() -> Path:
    override = os.getenv("NURSING_STATION_POLICY_PATH", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "policies" / "policy.json"


@lru_cache(maxsize=1)
def engine() -> PolicyEngine:
    return PolicyEngine(SERVICE_NAME, policy_path=str(_default_policy_path()))


SERVICE_NAME = "nursing-station"
