"""Read-only seam against BulletTrain's own connector and event registries.

Nursing Station declares, in :mod:`nursing_station.publications` and
:mod:`nursing_station.workforce`, which BulletTrain-side routes exist today and
which do not. Those declarations decide whether a national workflow reports
itself as delivered or as queued, so they must not be allowed to rot.

This suite reads BulletTrain's manifests and registry WITHOUT importing or
mutating anything in that repository. It deliberately turns RED the moment
BulletTrain registers one of the missing routes: at that point the gap notes
here, the disposition ledger and the publication contracts must be updated
together, and the workflow can finally be graded closed-loop instead of
implemented-to-the-queue.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from nursing_station import national_routes, publications, workforce

WORKSPACE = Path(
    os.environ.get("SYMPHONIX_WORKSPACE_ROOT", Path(__file__).resolve().parents[2])
).resolve()
BT_ROOT = WORKSPACE / "BulletTrain"
MANIFEST_DIR = BT_ROOT / "connectors" / "manifests"
EVENT_REGISTRY = BT_ROOT / "connectors" / "registries" / "outbound_webhook_events.json"


def test_bullettrain_connector_evidence_is_available() -> None:
    assert MANIFEST_DIR.is_dir(), (
        f"BulletTrain connector manifests not present at {MANIFEST_DIR}; "
        "configure SYMPHONIX_WORKSPACE_ROOT or restore the required sibling"
    )


def _exchange_routes(connector: str) -> dict:
    """Every exchange route a connector publishes, by resource type."""
    for candidate in (
        MANIFEST_DIR / f"{connector}_manifest.json",
        MANIFEST_DIR / f"{connector}_connector_manifest.json",
    ):
        if candidate.exists():
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            return dict((payload.get("runtime") or {}).get("exchange_routes") or {})
    return {}


def test_publication_contract_route_status_matches_bullettrain():
    for contract in publications.PUBLICATION_CONTRACTS.values():
        routes = _exchange_routes(contract.connector)
        exists = contract.resource_type in routes
        assert exists == contract.deliverable, (
            f"{contract.kind}: BulletTrain route "
            f"{contract.connector}/{contract.resource_type} "
            f"{'now exists' if exists else 'no longer exists'} but Nursing Station "
            f"declares route_status={contract.route_status!r}. Update "
            "nursing_station/publications.py, docs/NATIONAL_CAPABILITY_DISPOSITION_LEDGER.md "
            "and the family grading together."
        )


def test_every_undeliverable_contract_states_its_gap():
    """Every publication now has a destination, and the rule still holds.

    This asserted a non-empty gap list until 2026-09-02, when the last of the
    four BulletTrain-side routes landed. The invariant it protects is the one
    that matters and is kept: a contract that CANNOT be delivered must name why.
    An empty gap list is now the honest state, not a silenced check.
    """
    gaps = publications.open_gaps()
    for gap in gaps:
        assert gap["gap"].strip(), f"{gap['kind']} is undeliverable but names no gap"
    undeliverable = [
        contract.kind
        for contract in publications.PUBLICATION_CONTRACTS.values()
        if not contract.deliverable
    ]
    assert [gap["kind"] for gap in gaps] == undeliverable


def test_the_quality_dataset_reuses_the_proven_hmis_envelope():
    """The measure block must not fork HMIS's ward-report vocabulary."""
    routes = _exchange_routes("hmis")
    assert "NursingMeasureReport" in routes, (
        "hmis no longer publishes NursingMeasureReport; the quality dataset has lost its "
        "only registered destination"
    )
    required = set(routes["NursingMeasureReport"].get("required_keys") or [])
    declared = set(
        publications.contract(publications.KIND_QUALITY_DATASET).required_fields
    )
    assert declared == required, (
        "Nursing Station's quality-dataset envelope has drifted from HMIS's own required "
        f"keys: declared={sorted(declared)} bullettrain={sorted(required)}"
    )


def test_the_roster_route_exists_and_is_a_read():
    """The roster has an owner now: the Health Worker Registry publishes it.

    This test was the inverse until 2026-09-02, pinning the absence. It is
    inverted rather than deleted so the seam still fails loudly if the route is
    ever withdrawn and Nursing Station is left consuming nothing.
    """
    routes = _exchange_routes(workforce.ROSTER_CONNECTOR)
    assert workforce.ROSTER_RESOURCE_TYPE in routes, (
        f"BulletTrain no longer publishes {workforce.ROSTER_CONNECTOR}/"
        f"{workforce.ROSTER_RESOURCE_TYPE}; the staffing position would silently lose its "
        "actuals and two quality measures would return to source-unavailable."
    )
    route = routes[workforce.ROSTER_RESOURCE_TYPE]
    assert route["operation"] == "read", "Nursing Station must never be able to write a roster"
    assert set(route["required_keys"]) == {"ward_id", "shift_date", "shift"}


def test_nursing_station_still_owns_only_the_critical_result_route():
    """A guard against a second nursing connector appearing beside this one."""
    routes = _exchange_routes("nursing_station")
    assert routes, "nursing_station connector manifest lost its exchange routes"
    assert "CriticalResultAlert" in routes
    unexpected = set(routes) - {"CriticalResultAlert"}
    assert not unexpected, (
        f"nursing_station gained exchange routes {sorted(unexpected)}; Nursing Station's "
        "inbound contract and its requirement catalogue must be updated to match."
    )


def test_no_canonical_event_kind_exists_for_nursing_staffing_or_handover():
    """Producing an unregistered kind is rejected before dispatch, so do not claim one."""
    assert EVENT_REGISTRY.is_file(), (
        f"BulletTrain event registry not present at {EVENT_REGISTRY}; "
        "this seam cannot be treated as tested"
    )
    kinds = set(json.loads(EVENT_REGISTRY.read_text(encoding="utf-8")).get("events") or {})
    claimed = {
        kind
        for kind in kinds
        if kind.split(".")[0] in {"nursing", "staffing", "ward", "handover", "observation"}
    }
    assert not claimed, (
        f"BulletTrain registered {sorted(claimed)}. Nursing Station's outbound publications "
        "can now target a canonical event kind instead of stopping at the durable queue."
    )


def test_every_discharge_criterion_owner_has_a_read_route_in_bullettrain():
    """The four owners can answer, and can only ever be asked -- never told.

    FR-NS-151 meets a criterion only from the owning system's own receipt, so
    the day one of these routes is withdrawn the criterion silently returns to
    permanently pending and a ward waits on an answer nobody is being asked
    for. Read-only is asserted as firmly as existence: a write route here
    would let this repo assert another system's criterion met, which is the
    one thing the requirement forbids.
    """
    for source, contract in national_routes.DISCHARGE_CONFIRMATIONS.items():
        routes = _exchange_routes(contract["connector"])
        resource_type = contract["resource_type"]
        assert resource_type in routes, (
            f"BulletTrain no longer routes {contract['connector']}/{resource_type}, so the "
            f"{source} discharge criterion can never be met again"
        )
        route = routes[resource_type]
        assert route["operation"] == "read", (
            f"{source} must be ASKED for its confirmation; a write route would let this "
            "repo assert another system's criterion met"
        )
        assert route["method"] == "GET"
