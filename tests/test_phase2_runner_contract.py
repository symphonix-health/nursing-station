"""Fail-closed lifecycle contracts for the real Phase 2 journey runner."""

from __future__ import annotations

import re

import pytest

from scripts.run_phase2_seeded_journey import (
    resolve_hub_contract,
    runner_owned_hub_auth_env,
    service_auth_headers,
)

# The principal a runner-owned gateway is launched with. Exact, not a pattern:
# a wildcard over DEV_AUTH_* would let an added key (a linked-patients list, an
# identity kind, a wider scope) widen the principal without any assertion
# noticing, so the whole DEV_AUTH_* set is pinned.
EXPECTED_HUB_PRINCIPAL = {
    "DEV_AUTH_SUBJECT": "nursing-station-phase2-journey",
    "DEV_AUTH_ROLES": "service",
    "DEV_AUTH_SCOPES": "connector:exchange",
    "DEV_AUTH_TENANT_ID": "t-platform",
    "DEV_AUTH_PURPOSE_OF_USE": "treatment",
    "DEV_AUTH_LEGAL_BASIS": "consent",
}
# Modes that authenticate nobody. BulletTrain refuses "off" in a deployed
# environment (bullettrain/security/auth/dependencies.py), and estate policy is
# that AUTH_MODE=off is being removed everywhere, so a runner-owned gateway must
# never be launched in either.
UNAUTHENTICATED_MODES = {"off", "disabled"}
PRIVILEGED_ROLES = {"admin", "superuser", "system_admin", "platform_admin"}
ANONYMOUS_SUBJECTS = {"", "anonymous", "unknown", "test-user", "admin", "system"}


def _split(value: str) -> list[str]:
    return [part for part in re.split(r"[ ,]+", value.strip()) if part]


def hub_contract_violations(auth_mode: str, hub_env: dict[str, str]) -> list[str]:
    """Return every way a runner-owned gateway contract breaks the estate rule.

    The rule: AUTH_MODE=dev with a NAMED, least-privilege principal -- never
    off, never superuser. The client half (``auth_mode``, from
    ``resolve_hub_contract``) and the hub half (``hub_env``, what the hub
    process is launched with) must also agree, or the client builds a bare
    bearer for a gateway that expects the dev assertion headers.
    """

    problems: list[str] = []
    if auth_mode in UNAUTHENTICATED_MODES:
        problems.append(f"client contract is {auth_mode!r}, which authenticates nobody")
    elif auth_mode != "dev":
        problems.append(f"client contract is {auth_mode!r}, expected 'dev'")
    hub_mode = hub_env.get("AUTH_MODE", "")
    if hub_mode in UNAUTHENTICATED_MODES:
        problems.append(f"hub is launched with AUTH_MODE={hub_mode!r}")
    if hub_mode != auth_mode:
        problems.append(f"client contract {auth_mode!r} != hub AUTH_MODE {hub_mode!r}")

    principal = {k: v for k, v in hub_env.items() if k.startswith("DEV_AUTH_")}
    if principal != EXPECTED_HUB_PRINCIPAL:
        extra = sorted(set(principal) - set(EXPECTED_HUB_PRINCIPAL))
        missing = sorted(set(EXPECTED_HUB_PRINCIPAL) - set(principal))
        changed = sorted(
            k for k in set(principal) & set(EXPECTED_HUB_PRINCIPAL)
            if principal[k] != EXPECTED_HUB_PRINCIPAL[k]
        )
        problems.append(
            f"DEV_AUTH_* principal drifted: extra={extra} missing={missing} changed={changed}"
        )

    if principal.get("DEV_AUTH_SUBJECT", "").strip().lower() in ANONYMOUS_SUBJECTS:
        problems.append("hub principal has no named subject")
    roles = set(_split(principal.get("DEV_AUTH_ROLES", "")))
    if not roles:
        problems.append("hub principal holds no role")
    if roles & PRIVILEGED_ROLES:
        problems.append(f"hub principal holds a privileged role: {sorted(roles & PRIVILEGED_ROLES)}")
    scopes = set(_split(principal.get("DEV_AUTH_SCOPES", "")))
    if scopes != {"connector:exchange"}:
        problems.append(f"hub principal scopes are {sorted(scopes)}, expected only connector:exchange")
    if any(s == "*" or s.endswith(":*") or s == "system:admin" for s in scopes):
        problems.append(f"hub principal holds a wildcard or admin scope: {sorted(scopes)}")
    return problems


def test_runner_owned_gateway_uses_isolated_auth_contract(monkeypatch):
    monkeypatch.delenv("NURSING_STATION_HUB_TOKEN", raising=False)
    monkeypatch.delenv("NURSING_STATION_HUB_AUTH_MODE", raising=False)
    token, auth_mode = resolve_hub_contract(reuse_hub=False)
    assert len(token) >= 32
    # A runner-owned gateway is launched in dev with a NAMED principal, never
    # with authentication off (see runner_owned_hub_auth_env).
    assert auth_mode == "dev"
    assert auth_mode not in UNAUTHENTICATED_MODES


def test_runner_owned_gateway_principal_is_named_and_least_privilege(monkeypatch):
    monkeypatch.delenv("NURSING_STATION_HUB_TOKEN", raising=False)
    monkeypatch.delenv("NURSING_STATION_HUB_AUTH_MODE", raising=False)
    _, auth_mode = resolve_hub_contract(reuse_hub=False)
    hub_env = runner_owned_hub_auth_env()
    assert hub_env["AUTH_MODE"] == "dev"
    principal = {k: v for k, v in hub_env.items() if k.startswith("DEV_AUTH_")}
    assert principal == EXPECTED_HUB_PRINCIPAL
    assert hub_contract_violations(auth_mode, hub_env) == []


def test_runner_owned_gateway_client_sends_dev_headers_the_hub_expects(monkeypatch):
    monkeypatch.delenv("NURSING_STATION_HUB_TOKEN", raising=False)
    monkeypatch.delenv("NURSING_STATION_HUB_AUTH_MODE", raising=False)
    token, auth_mode = resolve_hub_contract(reuse_hub=False)
    headers = service_auth_headers(
        token=token,
        auth_mode=auth_mode,
        subject="lis",
        role="system",
        scopes="nursing.critical-result.notify",
        tenant="tenant-st-brigids",
    )
    # The hub runs dev, whose principal comes from X-Dev-* assertions. A bare
    # bearer here is the half-change that returning "off" once produced.
    assert headers["X-Dev-Subject"] == "lis"
    assert headers["X-Dev-Roles"] == "system"
    assert headers["X-Dev-Tenant"] == "tenant-st-brigids"


@pytest.mark.parametrize(
    ("label", "auth_mode", "mutate"),
    [
        ("old off client contract against the dev hub", "off", lambda env: None),
        ("hub launched with AUTH_MODE=off", "dev", lambda env: env.update(AUTH_MODE="off")),
        ("hub launched with AUTH_MODE=disabled", "dev", lambda env: env.update(AUTH_MODE="disabled")),
        ("superuser role", "dev", lambda env: env.update(DEV_AUTH_ROLES="superuser")),
        ("admin alongside service", "dev", lambda env: env.update(DEV_AUTH_ROLES="service admin")),
        ("wildcard scope", "dev", lambda env: env.update(DEV_AUTH_SCOPES="*")),
        ("admin scope added", "dev", lambda env: env.update(DEV_AUTH_SCOPES="connector:exchange system:admin")),
        ("anonymous subject", "dev", lambda env: env.update(DEV_AUTH_SUBJECT="anonymous")),
        ("subject removed", "dev", lambda env: env.pop("DEV_AUTH_SUBJECT")),
        ("extra DEV_AUTH key widens the principal", "dev", lambda env: env.update(DEV_AUTH_IDENTITY_KIND="human_persona")),
        ("linked patients added", "dev", lambda env: env.update(DEV_AUTH_LINKED_PATIENTS="pat-005")),
    ],
)
def test_contract_check_rejects_the_contracts_the_estate_forbids(label, auth_mode, mutate):
    """Negative controls: the check above must be able to fail.

    Each case is a contract the estate forbids (off, superuser, wildcard, an
    unnamed or widened principal, or a client/hub disagreement). If the
    validator ever returned an empty list for one of these, the positive
    assertion on the real runner would be vacuous.
    """

    env = runner_owned_hub_auth_env()
    mutate(env)
    assert hub_contract_violations(auth_mode, env), label


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
