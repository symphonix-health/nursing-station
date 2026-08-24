from __future__ import annotations

from nursing_station.integration import _exchange_headers


def test_exchange_headers_use_the_exchange_principal_for_supervised_dev_gateway():
    headers = _exchange_headers(
        token="synthetic-token",
        correlation_id="corr-123",
        auth_mode="dev",
        actor_id="staff-icu-nurse",
        tenant_id="tenant-uat",
        role="ward_nurse",
        scopes=["nursing.context.read"],
    )

    assert headers == {
        "Authorization": "Bearer synthetic-token",
        "X-Correlation-ID": "corr-123",
        "X-Trace-ID": "corr-123",
        "X-Dev-Subject": "staff-icu-nurse",
        "X-Dev-Roles": "ward_nurse",
        "X-Dev-Scopes": "nursing.context.read",
        "X-Dev-Tenant": "tenant-uat",
    }


def test_exchange_headers_do_not_add_dev_auth_without_explicit_opt_in():
    headers = _exchange_headers(
        token="synthetic-token",
        correlation_id="corr-123",
        auth_mode="",
        actor_id="staff-icu-nurse",
        tenant_id="tenant-uat",
        role="ward_nurse",
        scopes=["nursing.context.read"],
    )

    assert headers == {
        "Authorization": "Bearer synthetic-token",
        "X-Correlation-ID": "corr-123",
        "X-Trace-ID": "corr-123",
    }
