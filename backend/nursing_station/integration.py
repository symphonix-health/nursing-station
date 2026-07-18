"""BulletTrain-only Phase 2 integration client and source contracts."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

from .config import Settings


@dataclass(frozen=True)
class SourceContract:
    connector: str
    resource_type: str
    semantics: tuple[str, ...]


SOURCE_CONTRACTS: dict[str, SourceContract] = {
    "picis-system": SourceContract(
        "picis_system", "NursingPatientContext", ("Patient", "Encounter")
    ),
    "lis": SourceContract(
        "lis", "NursingLabContext", ("Observation", "DiagnosticReport")
    ),
    "pacs-ris": SourceContract(
        "pacs_ris", "NursingImagingContext", ("ImagingStudy", "DiagnosticReport")
    ),
    "pharmacy-system": SourceContract(
        "pharmacy_system",
        "NursingMedicationContext",
        ("MedicationRequest", "MedicationDispense"),
    ),
    "blood-transfusion": SourceContract(
        "blood_transfusion", "NursingBloodContext", ("ServiceRequest", "Procedure")
    ),
}

# Executable declaration of the controls split between this client, the route
# transaction, and BulletTrain. It is kept beside the connector so a future
# transport change cannot silently omit the integration constitution.
INTEGRATION_CONTROL_BOUNDARY = {
    "audit": "caller records attempt, outcome, correlation and hub audit identity",
    "schema_validation": "client validates the success envelope and object body",
    "retry_policy": "one bounded retry for idempotent reads on transient failure",
    "timeout_policy": "one configured bounded timeout applies to every attempt",
    "error_normalization": "transport and hub failures normalize to IntegrationError codes",
    "observability_tracing": "correlation and trace identity cross the hub boundary",
    "security_policy": "hub bearer authentication, role, purpose and scopes are mandatory",
}


class IntegrationError(RuntimeError):
    def __init__(self, code: str, detail: str, *, hub_audit_event_id: str | None = None):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.hub_audit_event_id = hub_audit_event_id


class HubClient:
    def __init__(self, settings: Settings):
        if not settings.integration_hub_url or not settings.integration_hub_token:
            raise IntegrationError(
                "integration_not_configured",
                "Phase 2 requires NURSING_STATION_HUB_URL and NURSING_STATION_HUB_TOKEN",
            )
        self.base_url = settings.integration_hub_url.rstrip("/")
        self.token = settings.integration_hub_token
        self.timeout = settings.integration_timeout_seconds

    async def exchange(
        self,
        *,
        connector: str,
        resource_type: str,
        operation: str,
        payload: dict[str, Any],
        tenant_id: str,
        actor_id: str,
        role: str,
        correlation_id: str,
        purpose_of_use: str = "treatment",
    ) -> dict[str, Any]:
        request_body = {
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "correlation_id": correlation_id,
            "operation": operation,
            "payload": payload,
            "standard": "fhir-r4-semantics",
            "resource_type": resource_type,
            "purpose_of_use": purpose_of_use,
            "scopes": ["nursing.context.read"] if operation == "read" else ["hmis.measure.write"],
            "roles": [role],
            "source_system": "nursing-station",
        }
        retry_count = 1 if operation == "read" else 0
        response: httpx.Response | None = None
        for attempt in range(retry_count + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/v1/connectors/{connector}/exchange",
                        json=request_body,
                        headers={
                            "Authorization": f"Bearer {self.token}",
                            "X-Correlation-ID": correlation_id,
                            "X-Trace-ID": correlation_id,
                        },
                    )
                if response.status_code not in {502, 503, 504} or attempt == retry_count:
                    break
            except httpx.TimeoutException as exc:
                if attempt == retry_count:
                    raise IntegrationError("timeout", "BulletTrain exchange timed out") from exc
            except httpx.HTTPError as exc:
                if attempt == retry_count:
                    raise IntegrationError(
                        "unavailable", f"BulletTrain exchange failed: {exc}"
                    ) from exc
            await asyncio.sleep(0.1 * (attempt + 1))

        if response is None:
            raise IntegrationError("unavailable", "BulletTrain exchange produced no response")

        try:
            envelope = response.json()
        except ValueError as exc:
            raise IntegrationError("invalid_response", "BulletTrain returned non-JSON data") from exc
        if response.status_code >= 400 or envelope.get("status") != "success":
            errors = envelope.get("errors") or [f"HTTP {response.status_code}"]
            raise IntegrationError(
                str(envelope.get("status") or "exchange_failed"),
                "; ".join(str(error) for error in errors),
                hub_audit_event_id=envelope.get("audit_event_id"),
            )
        data = envelope.get("data")
        body = data.get("body") if isinstance(data, dict) else None
        if not isinstance(body, dict):
            raise IntegrationError(
                "invalid_response",
                "BulletTrain success response did not contain an object body",
                hub_audit_event_id=envelope.get("audit_event_id"),
            )
        return {
            "body": body,
            "hub_audit_event_id": envelope.get("audit_event_id"),
            "duration_ms": envelope.get("duration_ms"),
        }
