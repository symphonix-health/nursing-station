"""Fail-closed lifecycle contracts for the real Phase 2 journey runner."""

from __future__ import annotations

import pytest

from scripts.run_phase2_seeded_journey import (
    resolve_hub_contract,
    service_auth_headers,
)


def test_runner_owned_gateway_uses_isolated_auth_contract(monkeypatch):
    monkeypatch.delenv("NURSING_STATION_HUB_TOKEN", raising=False)
    monkeypatch.delenv("NURSING_STATION_HUB_AUTH_MODE", raising=False)
    token, auth_mode = resolve_hub_contract(reuse_hub=False)
    assert len(token) >= 32
    assert auth_mode == "off"


def test_existing_gateway_is_not_inferred_from_open_port(monkeypatch):
    monkeypatch.delenv("NURSING_STATION_REUSE_REGISTERED_HUB", raising=False)
    monkeypatch.setenv("NURSING_STATION_HUB_TOKEN", "would-not-be-used")
    monkeypatch.setenv("NURSING_STATION_HUB_AUTH_MODE", "dev")
    with pytest.raises(RuntimeError, match="Refusing to infer"):
        resolve_hub_contract(reuse_hub=True)


def test_explicit_reuse_requires_token_and_auth_mode(monkeypatch):
    monkeypatch.setenv("NURSING_STATION_REUSE_REGISTERED_HUB", "1")
    monkeypatch.delenv("NURSING_STATION_HUB_TOKEN", raising=False)
    monkeypatch.delenv("NURSING_STATION_HUB_AUTH_MODE", raising=False)
    with pytest.raises(RuntimeError, match="requires both"):
        resolve_hub_contract(reuse_hub=True)


def test_explicit_reuse_preserves_operator_contract(monkeypatch):
    monkeypatch.setenv("NURSING_STATION_REUSE_REGISTERED_HUB", "true")
    monkeypatch.setenv("NURSING_STATION_HUB_TOKEN", "signed-operator-token")
    monkeypatch.setenv("NURSING_STATION_HUB_AUTH_MODE", "oidc")
    assert resolve_hub_contract(reuse_hub=True) == (
        "signed-operator-token",
        "oidc",
    )


def test_dev_headers_are_emitted_only_for_explicit_dev_auth():
    oidc = service_auth_headers(
        token="signed-token",
        auth_mode="oidc",
        subject="lis",
        role="system",
        scopes="nursing.critical-result.notify",
        tenant="tenant-st-brigids",
    )
    dev = service_auth_headers(
        token="dev-token",
        auth_mode="dev",
        subject="lis",
        role="system",
        scopes="nursing.critical-result.notify",
        tenant="tenant-st-brigids",
    )
    assert oidc == {"Authorization": "Bearer signed-token"}
    assert dev["X-Dev-Subject"] == "lis"
    assert dev["X-Dev-Tenant"] == "tenant-st-brigids"
