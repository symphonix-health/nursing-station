from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_phase1_governance_artifacts_exist_and_are_substantive() -> None:
    paths = [
        "safety/CLINICAL_SAFETY_CASE_REPORT.md",
        "safety/HAZARD_LOG.md",
        "docs/DPIA.md",
        "docs/PRIVACY_NOTICE.md",
        "docs/RETENTION_POLICY.md",
        "docs/OPERATIONS_RUNBOOK.md",
        "docs/SYNTHETIC_DATA_GOVERNANCE.md",
        "seed_manifests/uk/nursing_station_phase1.yaml",
    ]
    for relative in paths:
        path = ROOT / relative
        assert path.is_file(), relative
        assert len(path.read_text(encoding="utf-8").strip()) >= 100, relative


def test_every_requirement_maps_to_its_declared_semantic_domain() -> None:
    matrix = json.loads(
        (ROOT / "tests/harness/json_matrices/nursing_station_phase1_canonical.json").read_text(
            encoding="utf-8"
        )
    )
    traceability = json.loads(
        (ROOT / "tests/harness/requirements_matrix.json").read_text(encoding="utf-8")
    )
    requirements = {
        row["requirement_id"]: row for row in traceability["requirements"]
    }
    for scenario in matrix["scenarios"]:
        requirement_id = scenario["requirement_ids"][0]
        domain = requirements[requirement_id]["domain"]
        assert domain in scenario["tags"], scenario["use_case_id"]
        assert requirement_id in scenario["title"], scenario["use_case_id"]


def test_port_and_synthetic_requirements_have_direct_gate_evidence() -> None:
    matrix = json.loads(
        (ROOT / "tests/harness/requirements_matrix.json").read_text(encoding="utf-8")
    )
    requirements = {
        row["requirement_id"]: row for row in matrix["requirements"]
    }
    assert requirements["NFR-NS-010"]["direct_evidence"] == ["tests/test_port_registry.py"]
    assert requirements["NFR-NS-011"]["direct_evidence"] == [
        "tests/test_api.py::test_seed_governance_is_durable_explicit_and_non_live"
    ]
