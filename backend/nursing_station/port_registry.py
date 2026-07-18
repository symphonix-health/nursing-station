from __future__ import annotations

import json
import os
from pathlib import Path

REPO_NAME = "nursing-station"


def _registry_path() -> Path:
    configured = os.environ.get("SYMPHONIX_PORT_REGISTRY")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / "workspace-tooling" / "ports.workspace.json"


def _repo_ports() -> list[int]:
    registry_path = _registry_path()
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        blocks = registry["repo_blocks"][REPO_NAME]["blocks"]
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(
            f"Cannot resolve {REPO_NAME} backend port from {registry_path}"
        ) from exc

    return [int(block[0]) for block in blocks]


def resolve_backend_port() -> int:
    override = os.environ.get("WS_BACKEND_PORT") or os.environ.get(
        "NURSING_STATION_BACKEND_PORT"
    )
    if override:
        return int(override)

    candidates = [port for port in _repo_ports() if not 5000 <= port <= 5999]
    if len(candidates) != 1:
        raise RuntimeError(
            f"Expected one backend allocation for {REPO_NAME}; found {candidates}"
        )
    return candidates[0]


def resolve_frontend_port() -> int:
    override = os.environ.get("VITE_PORT") or os.environ.get(
        "NURSING_STATION_FRONTEND_PORT"
    )
    if override:
        return int(override)

    candidates = [port for port in _repo_ports() if 5000 <= port <= 5999]
    if len(candidates) != 1:
        raise RuntimeError(
            f"Expected one frontend allocation for {REPO_NAME}; found {candidates}"
        )
    return candidates[0]
