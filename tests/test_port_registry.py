from __future__ import annotations

import json
import os
from pathlib import Path

from nursing_station.port_registry import (
    _registry_path,
    resolve_backend_port,
    resolve_frontend_port,
)

WORKSPACE = Path(
    os.environ.get("SYMPHONIX_WORKSPACE_ROOT", Path(__file__).resolve().parents[2])
).resolve()


def test_registry_path_uses_explicit_workspace_in_isolated_worktree(
    monkeypatch,
) -> None:
    monkeypatch.delenv("SYMPHONIX_PORT_REGISTRY", raising=False)
    monkeypatch.setenv("SYMPHONIX_WORKSPACE_ROOT", str(WORKSPACE))

    assert _registry_path() == WORKSPACE / "workspace-tooling" / "ports.workspace.json"


def test_nursing_station_has_dedicated_workspace_registry_allocations() -> None:
    registry = json.loads(
        (WORKSPACE / "workspace-tooling" / "ports.workspace.json").read_text(encoding="utf-8")
    )
    allocation = registry["repo_blocks"]["nursing-station"]
    assert allocation["literal_policy"] == "block"
    assert allocation["blocks"] == [[9201, 9201], [5282, 5282]]
    assert resolve_backend_port() == 9201
    assert resolve_frontend_port() == 5282


def test_bullettrain_service_catalogue_source_matches_workspace_allocation() -> None:
    ports = json.loads(
        (WORKSPACE / "BulletTrain" / "config" / "ports.json").read_text(encoding="utf-8")
    )
    service = ports["external_systems"]["nursing_station"]
    assert service["port"] == resolve_backend_port()
    assert service["repo"] == "nursing-station"
    assert service["health_check"] == "/health"
