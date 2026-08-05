"""Country packs are versioned data, and this suite is their migration test.

`docs/STANDARDS_PROFILE.md` already says country-specific controls are overlays
rather than universal truth. These tests hold the pack files to that: a pack
must validate structurally, must cite a dated publisher for every clinically
meaningful entry, and must never be silently promoted from candidate to adopted
by shipping a new version.
"""

from __future__ import annotations

import json

import pytest
from nursing_station.country_packs import (
    PACK_DIR,
    REQUIRED_SECTIONS,
    SCHEMA_VERSION,
    CountryPackError,
    available_jurisdictions,
    load_pack,
    reset_cache,
)

JURISDICTIONS = ("IE", "GB", "KE", "US")
GOVERNED_DECLARATION_FIELDS = [
    "declaration_id", "scope_unit", "declared_by", "reason", "starts_at", "expires_at",
]


def test_the_shipped_pack_set_is_the_four_country_comparator():
    assert set(available_jurisdictions()) == set(JURISDICTIONS)


@pytest.mark.parametrize("jurisdiction", JURISDICTIONS)
def test_every_pack_carries_a_complete_dated_citation_for_every_clinical_entry(jurisdiction):
    pack = load_pack(jurisdiction)
    assert pack.payload["schema_version"] == SCHEMA_VERSION
    for section in REQUIRED_SECTIONS:
        assert section in pack.payload
    for source_id in (
        pack.early_warning["source_id"],
        pack.safe_staffing["source_id"],
        pack.harm_incident["external_reporting"]["source_id"],
    ):
        source = pack.source(source_id)
        assert source["publisher"] and source["title"] and source["effective_from"]
    for measure in pack.quality_measures:
        assert measure["numerator"] and measure["denominator"] and measure["unit"]
        assert isinstance(measure["exclusions"], list)
        assert pack.source(measure["source_id"])["publisher"]


@pytest.mark.parametrize("jurisdiction", JURISDICTIONS)
def test_no_pack_ships_pre_adopted(jurisdiction):
    pack = load_pack(jurisdiction)
    assert pack.payload["adoption_status"] == "candidate"
    assert "adoption" in pack.payload["adoption_note"].lower()


@pytest.mark.parametrize("jurisdiction", JURISDICTIONS)
def test_no_pack_invents_a_shortage_severity_the_governed_model_does_not_have(jurisdiction):
    """Forking BulletTrain's binary declaration contract would break dispatch."""
    contract = pack_declaration_contract(jurisdiction)
    assert contract["model"] == "binary"
    assert contract["required_fields"] == GOVERNED_DECLARATION_FIELDS
    serialised = json.dumps(load_pack(jurisdiction).safe_staffing)
    for forbidden in ("shortage_severity", '"severity"', '"tier":'):
        assert forbidden not in serialised


def pack_declaration_contract(jurisdiction: str) -> dict:
    return load_pack(jurisdiction).safe_staffing["declaration_policy"]["declaration_contract"]


@pytest.mark.parametrize("jurisdiction", JURISDICTIONS)
def test_every_declared_trigger_is_evaluable_and_every_criterion_has_an_owner(jurisdiction):
    pack = load_pack(jurisdiction)
    known_triggers = {
        "registered-hours-below-norm", "skill-mix-below-minimum",
        "patients-per-registered-nurse-exceeded", "state-ratio-exceeded",
    }
    triggers = pack.safe_staffing["declaration_policy"]["triggers"]
    assert triggers
    for trigger in triggers:
        assert trigger["trigger_id"] in known_triggers, (
            f"{jurisdiction} declares trigger {trigger['trigger_id']!r} that "
            "nursing_station.workforce.compute_position cannot evaluate"
        )
        assert trigger["rule"]
    for criterion in pack.discharge_criteria:
        assert criterion["criterion_id"] and criterion["owner_role"]
        assert criterion["evidence_source"]
        assert isinstance(criterion["mandatory"], bool)


def test_a_jurisdiction_without_a_numeric_norm_reports_insufficient_policy_not_compliance():
    """The United States sets nurse ratios by state, not federally."""
    pack = load_pack("US")
    norm = pack.ward_norm("adult-medical")
    assert norm["nursing_hours_per_patient_day"] == 0
    assert "insufficient-policy" in norm["note"]
    overlays = pack.safe_staffing["state_overlays"]
    assert any(overlay["state"] == "CA" and overlay["mandated_ratio"] for overlay in overlays)


def test_a_pack_version_change_does_not_inherit_the_previous_adoption(client, safety_officer):
    """Adoption is pinned; publishing 2026.09.0 must not reuse 2026.08.0's decision."""
    decision = {
        "jurisdiction": "IE", "pack_version": "2026.08.0", "decision": "adopted",
        "scope": "synthetic clinical simulation on ward MED-A",
        "note": "Reviewed against the ward's local escalation protocol.",
    }
    assert client.post(
        "/api/country-pack/adoptions", headers=safety_officer, json=decision
    ).status_code == 201
    assert client.get("/api/country-pack", headers=safety_officer).json()["locally_adopted"] is True

    row = client.get("/api/country-pack", headers=safety_officer).json()["local_adoption"]
    assert row["pack_version"] == "2026.08.0"
    # A decision recorded for one version is not visible as a decision for another.
    assert client.post(
        "/api/country-pack/adoptions", headers=safety_officer,
        json={**decision, "pack_version": "2026.09.0"},
    ).status_code == 409


def test_a_malformed_pack_is_refused_rather_than_partially_loaded(tmp_path, monkeypatch):
    broken = dict(json.loads((PACK_DIR / "ie.json").read_text(encoding="utf-8")))
    broken["quality_measures"] = [
        {**broken["quality_measures"][0], "source_id": "does-not-exist"}
    ]
    target = tmp_path / "zz.json"
    broken["jurisdiction"] = "ZZ"
    target.write_text(json.dumps(broken), encoding="utf-8")
    monkeypatch.setattr("nursing_station.country_packs.PACK_DIR", tmp_path)
    reset_cache()
    try:
        with pytest.raises(CountryPackError, match="undefined sources"):
            load_pack("ZZ")
    finally:
        reset_cache()


@pytest.fixture()
def safety_officer(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "clinical.safety@nursing.test", "password": "Nursing2026!"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
