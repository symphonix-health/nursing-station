from __future__ import annotations

import json
from pathlib import Path

from nursing_station.port_registry import resolve_backend_port, resolve_frontend_port

WORKSPACE = Path(__file__).resolve().parents[2]


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
