from __future__ import annotations

from typing import Any

SEED_MANIFEST_ID = "seed.uk.nursing_station.phase1_v1"
METADATA_PACK_ID = "uk.0.1.fabricated"
METADATA_PACK_VERSION = "0.1"
SCENARIO_PACK_ID = "inpatient-nursing-phase1.v1"
DATA_CLASS = "seeded_synthetic"


def manifest(record_counts: dict[str, int], generated_at: str) -> dict[str, Any]:
    """Return the runtime declaration for the deterministic Phase 1 seed."""
    return {
        "seed_manifest_id": SEED_MANIFEST_ID,
        "seeder_name": "symphonix-nursing-station-deterministic-seeder",
        "seeder_version": "1.0.0",
        "seeder_repository": "nursing-station",
        "seeder_commit_sha": "phase1-source-revision",
        "generation_run_id": "nursing-station-phase1-bootstrap",
        "generation_started_at": generated_at,
        "generation_completed_at": generated_at,
        "target_system": "Symphonix-Health Nursing Station",
        "target_environment": "local_phase1",
        "metadata_pack_id": METADATA_PACK_ID,
        "metadata_pack_version": METADATA_PACK_VERSION,
        "scenario_pack_id": SCENARIO_PACK_ID,
        "seed_config_hash": "nursing-station-phase1-seed-v1",
        "random_seed_policy": "deterministic_fabricated_fixture",
        "synthetic_population_size": record_counts["patients"],
        "domains_seeded": [
            "inpatient_nursing",
            "observations",
            "medication_administration",
            "care_planning",
        ],
        "record_counts_expected": record_counts,
        "record_counts_landed": record_counts,
        "back_correction_enabled": False,
        "back_correction_ruleset_id": "dq.not_applicable.phase1_bootstrap",
        "terminology_ruleset_id": "terminology.nursing_station.phase1_v1",
        "data_quality_ruleset_id": "dq.nursing_station.phase1_v1",
        "privacy_policy_id": "privacy.seeded_synthetic.nursing_station_v1",
        "contains_real_patient_data": False,
        "contains_real_person_data": False,
        "contains_pseudonymised_real_data": False,
        "contains_synthetic_subject_level_records": True,
        "contains_seeded_synthetic_records": True,
        "source_is_symphonix_assurance": False,
        "approved_synthetic_seeder": True,
        "source_is_live_clinical_system": False,
        "generated_by": "nursing-station repo-owned deterministic seeder",
        "approved_for_use_case": [
            "Phase 1 local development",
            "automated testing",
            "headed clinical workflow review",
        ],
        "limitations": [
            "Fabricated records are not clinical truth or epidemiological evidence.",
            "The seed is not authorised for clinical decision-making or production use.",
            "Master-registry and sibling-service resolution are deferred to Phase 2.",
        ],
    }
