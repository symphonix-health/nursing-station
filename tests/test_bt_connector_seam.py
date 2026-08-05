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
from pathlib import Path

import pytest
from nursing_station import publications, workforce

BT_ROOT = Path(__file__).resolve().parents[2] / "BulletTrain"
MANIFEST_DIR = BT_ROOT / "connectors" / "manifests"
EVENT_REGISTRY = BT_ROOT / "connectors" / "registries" / "outbound_webhook_events.json"

pytestmark = pytest.mark.skipif(
    not MANIFEST_DIR.exists(),
    reason=f"BulletTrain connector manifests not present at {MANIFEST_DIR}",
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
    gaps = publications.open_gaps()
    assert gaps, "expected at least one open BulletTrain-side gap while routes are missing"
    for gap in gaps:
        assert gap["gap"].strip(), f"{gap['kind']} is undeliverable but names no gap"


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


def test_no_roster_exchange_route_exists_yet():
    """The roster has no owner and no route; the staffing family must say so."""
    routes = _exchange_routes(workforce.ROSTER_CONNECTOR)
    assert workforce.ROSTER_RESOURCE_TYPE not in routes, (
        f"BulletTrain now publishes {workforce.ROSTER_CONNECTOR}/"
        f"{workforce.ROSTER_RESOURCE_TYPE}. The staffing family can be regraded from "
        "'consumed contract declared, no publisher' to a real consumption loop."
    )


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
    if not EVENT_REGISTRY.exists():
        pytest.skip(f"BulletTrain event registry not present at {EVENT_REGISTRY}")
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
