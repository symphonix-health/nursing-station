"""Durable outbound publication contracts (FR-NS-111, FR-NS-132, FR-NS-161, NFR-NS-029).

Every national workflow this repository owns ends by telling somebody else what
happened: pharmacy learns the administration outcome, the governed
role-assumption service learns that a ward declared a staffing shortage, HMIS
learns the nursing quality dataset.

Three rules keep that honest.

**One transport.** Nothing here opens a socket to a sibling. Each contract names
a BulletTrain connector and the resource type on that connector's manifest; the
existing :class:`~nursing_station.integration.HubClient` is the only egress.

**Route status is declared, not discovered at runtime.** ``route_status`` records
whether the BulletTrain-side exchange route exists today. A contract marked
``unregistered`` is still implemented end to end -- payload built, validated,
persisted, correlation minted -- but it stops at the durable queue with status
``pending-publication`` and a named gap. It is never reported as delivered.
``tests/test_bt_connector_seam.py`` pins these values against BulletTrain's own
manifests read-only, so the day a route lands the seam turns red and this table
must be updated rather than rotting silently.

**Dispatch is not completion.** A publication reaches ``published`` only when the
hub returns a success envelope, and the receipt is stored beside it. A failure
is recorded as ``failed`` with its typed error code. There is no fallback that
turns an unreachable dependency into a success (NFR-NS-008).
"""

from __future__ import annotations

from dataclasses import dataclass

ROUTE_REGISTERED = "registered"
ROUTE_UNREGISTERED = "unregistered"

STATUS_PENDING = "pending-publication"
STATUS_PUBLISHED = "published"
STATUS_FAILED = "failed"

KIND_MEDICATION_OUTCOME = "medication.administration.outcome"
KIND_STAFFING_DECLARATION = "staffing.shortage.declaration"
KIND_HARM_INCIDENT = "harm.incident.reported"
KIND_QUALITY_DATASET = "nursing.quality.dataset"


@dataclass(frozen=True)
class PublicationContract:
    kind: str
    connector: str
    resource_type: str
    operation: str
    scope: str
    route_status: str
    required_fields: tuple[str, ...]
    gap_note: str = ""

    @property
    def deliverable(self) -> bool:
        return self.route_status == ROUTE_REGISTERED


PUBLICATION_CONTRACTS: dict[str, PublicationContract] = {
    KIND_MEDICATION_OUTCOME: PublicationContract(
        kind=KIND_MEDICATION_OUTCOME,
        connector="pharmacy_system",
        resource_type="NursingMedicationOutcome",
        operation="write",
        scope="pharmacy.administration.write",
        route_status=ROUTE_UNREGISTERED,
        required_fields=(
            "tenant_id", "patient_id", "source_order_id", "outcome",
            "administered_at", "administered_by", "correlation_id",
        ),
        gap_note=(
            "pharmacy_system's connector manifest exposes NursingMedicationContext (read) "
            "but no write route for a nursing administration outcome. The outcome is "
            "queued with its correlation id and never reported as delivered."
        ),
    ),
    KIND_STAFFING_DECLARATION: PublicationContract(
        kind=KIND_STAFFING_DECLARATION,
        connector="global_agent_registry",
        resource_type="StaffingDeclaration",
        operation="write",
        scope="gra.staffing.declare",
        route_status=ROUTE_UNREGISTERED,
        # The field list is the governed role-assumption declaration contract
        # verbatim (governance/policies/role_assumption.yaml
        # staffing_escalation.declaration_required_fields). Nursing Station adds
        # no severity, no role enum and no approval field, because the governed
        # model has none and inventing one would fork the contract.
        required_fields=(
            "declaration_id", "scope_unit", "declared_by", "reason",
            "starts_at", "expires_at",
        ),
        gap_note=(
            "BulletTrain's governed role assumption owns StaffingDeclaration but exposes "
            "no declare/revoke HTTP surface yet, so no connector exchange route exists. "
            "The declaration is durable here and queued; the effective policy tier is "
            "BulletTrain's to decide and is never computed locally."
        ),
    ),
    KIND_HARM_INCIDENT: PublicationContract(
        kind=KIND_HARM_INCIDENT,
        connector="hmis",
        resource_type="NursingHarmIncidentReport",
        operation="write",
        scope="hmis.incident.write",
        route_status=ROUTE_UNREGISTERED,
        required_fields=(
            "tenant_id", "facility_id", "ward_id", "incident_type",
            "harm_level", "occurred_at", "correlation_id",
        ),
        gap_note=(
            "hmis exposes NursingMeasureReport but no incident route. Externally "
            "reportable ward incidents are queued de-identified; Nursing Station is not "
            "the national incident registry and never claims the report was filed."
        ),
    ),
    KIND_QUALITY_DATASET: PublicationContract(
        kind=KIND_QUALITY_DATASET,
        connector="hmis",
        resource_type="NursingMeasureReport",
        operation="write",
        scope="hmis.measure.write",
        route_status=ROUTE_REGISTERED,
        # Deliberately the SAME required keys hmis already publishes for the
        # existing ward-count submission. The quality dataset travels as an
        # additive `measures` block on that proven envelope rather than forking
        # a second nursing vocabulary on the same connector.
        required_fields=(
            "tenant_id", "facility_id", "ward_id", "period_start", "period_end", "counts",
        ),
    ),
}


def contract(kind: str) -> PublicationContract:
    try:
        return PUBLICATION_CONTRACTS[kind]
    except KeyError as exc:  # pragma: no cover - guarded by the route enums
        raise KeyError(f"unknown publication kind {kind!r}") from exc


def missing_fields(kind: str, payload: dict) -> list[str]:
    return [field for field in contract(kind).required_fields if field not in payload]


def open_gaps() -> list[dict]:
    """Every contract whose BulletTrain-side route does not exist yet."""
    return [
        {
            "kind": item.kind,
            "connector": item.connector,
            "resource_type": item.resource_type,
            "operation": item.operation,
            "gap": item.gap_note,
        }
        for item in PUBLICATION_CONTRACTS.values()
        if not item.deliverable
    ]
