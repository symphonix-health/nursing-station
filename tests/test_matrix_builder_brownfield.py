"""The canonical-matrix builder must merge, never overwrite.

`scripts/generate_canonical_matrices.py` writes seven shared artefacts that
other agent sessions also inject rows into. Before 2026-08-05 it rebuilt each
file from its own inputs alone; a planted foreign requirement and a planted
foreign matrix row were both deleted by a single run.

These tests run the real builder against a temporary copy of `tests/harness/`
so the repository's committed artefacts are never touched, and they fail if the
merge behaviour regresses.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = REPO_ROOT / "scripts" / "generate_canonical_matrices.py"

FOREIGN_REQUIREMENT = {
    "requirement_id": "FR-FOREIGN-901",
    "title": "Injected by another session",
    "category": "functional",
    "source": "another-session/docs/REQUIREMENTS.md",
    "coverage_status": "covered",
    "statement": "A requirement this builder does not own",
    "acceptance_criteria": [],
    "matrix_row_ids": ["NS-FOREIGN-9901"],
    "direct_evidence": ["another-session/tests/test_foreign.py"],
    "domain": "foreign",
}
FOREIGN_18COL_ROW = {
    "use_case_id": "NS-FOREIGN-9901",
    "subsystem": "nursing-station",
    "requirement_ids": ["FR-FOREIGN-901"],
    "scenario_category": "Positive",
    "title": "Foreign row injected by another session",
    "description": "Must survive a rebuild",
    "preconditions": ["foreign"],
    "trigger": {"method": "GET", "path": "/api/foreign"},
    "input_payload": {"foreign": True},
    "expected_connector_calls": [],
    "expected_events": [],
    "expected_outputs": {"foreign": True},
    "fault_profile": {"kind": "none"},
    "security_profile": {"tenant_scoped": True},
    "priority": "high",
    "automation_status": "automated",
    "estimated_duration_seconds": 1,
    "tags": ["foreign"],
}
FOREIGN_14COL_ROW = {
    "use_case_id": "NS-FOREIGN-9901",
    "component": "Nursing Station",
    "scenario": "Foreign row injected by another session",
    "test_type": "positive",
    "priority": "high",
    "expected_outcomes": ["survives a rebuild"],
    "preconditions": {"foreign": True},
    "test_data": {"foreign": True},
    "validation_rules": ["row is preserved verbatim"],
    "dependencies": [],
    "tags": ["foreign"],
    "estimated_duration": "1s",
    "automation_status": "automated",
    "notes": "planted by tests/test_matrix_builder_brownfield.py",
}

MATRIX_FILES = {
    "tests/harness/json_matrices/nursing_station_phase2_canonical.json": ("scenarios", FOREIGN_18COL_ROW),
    "tests/harness/reduced_json_matrices/nursing_station_phase2_canonical.14col.json": ("test_cases", FOREIGN_14COL_ROW),
    "tests/harness/json_matrices/nursing_station_national_capability_canonical.json": ("scenarios", FOREIGN_18COL_ROW),
    "tests/harness/reduced_json_matrices/nursing_station_national_capability_canonical.14col.json": ("test_cases", FOREIGN_14COL_ROW),
}
REQUIREMENT_FILES = (
    "tests/harness/requirements_superset.json",
    "tests/harness/healthcare_requirements_superset.json",
    "tests/harness/requirements_matrix.json",
)


def _load_builder(root: Path):
    """Import the real builder with its ROOT pointed at a sandbox copy.

    The module must be registered in ``sys.modules`` BEFORE it executes:
    ``@dataclass`` resolves string annotations through ``sys.modules[cls.
    __module__]``, and a module absent from that table makes the decorator
    raise instead of building the class.
    """
    name = f"generate_canonical_matrices_{root.name}"
    spec = importlib.util.spec_from_file_location(name, BUILDER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    module.ROOT = root
    return module


@pytest.fixture()
def sandbox(tmp_path):
    """A throwaway copy of the harness tree, so the real one is never written."""
    shutil.copytree(REPO_ROOT / "tests" / "harness", tmp_path / "tests" / "harness")
    return tmp_path


def _read(root: Path, relative: str) -> dict:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def _write(root: Path, relative: str, payload: dict) -> None:
    (root / relative).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_a_rebuild_on_an_unchanged_tree_is_a_byte_identical_no_op(sandbox):
    before = {
        relative: (sandbox / relative).read_bytes()
        for relative in (*MATRIX_FILES, *REQUIREMENT_FILES)
    }
    _load_builder(sandbox).main()
    for relative, content in before.items():
        assert (sandbox / relative).read_bytes() == content, f"{relative} changed on a no-op rebuild"


def test_a_foreign_requirement_survives_a_rebuild(sandbox):
    for relative in REQUIREMENT_FILES:
        payload = _read(sandbox, relative)
        payload["requirements"].append(dict(FOREIGN_REQUIREMENT))
        _write(sandbox, relative, payload)

    _load_builder(sandbox).main()

    for relative in REQUIREMENT_FILES:
        payload = _read(sandbox, relative)
        survivors = [r for r in payload["requirements"] if r["requirement_id"] == "FR-FOREIGN-901"]
        assert survivors, f"{relative} deleted the foreign requirement"
        assert survivors[0] == FOREIGN_REQUIREMENT, f"{relative} mutated the foreign requirement"

    # Totals are recomputed over the UNION, not over what this builder owns.
    superset = _read(sandbox, "tests/harness/requirements_superset.json")
    matrix = _read(sandbox, "tests/harness/requirements_matrix.json")
    assert superset["metadata"]["requirement_count"] == len(superset["requirements"])
    assert matrix["metadata"]["requirement_count"] == len(matrix["requirements"])
    assert matrix["metadata"]["requirement_count"] == superset["metadata"]["requirement_count"]


def test_a_foreign_matrix_row_survives_a_rebuild(sandbox):
    for relative, (key, row) in MATRIX_FILES.items():
        payload = _read(sandbox, relative)
        payload[key].append(dict(row))
        _write(sandbox, relative, payload)

    _load_builder(sandbox).main()

    for relative, (key, row) in MATRIX_FILES.items():
        payload = _read(sandbox, relative)
        survivors = [r for r in payload[key] if r["use_case_id"] == "NS-FOREIGN-9901"]
        assert survivors, f"{relative} deleted the foreign row"
        assert survivors[0] == row, f"{relative} mutated the foreign row"
        counted = payload["metadata"].get("scenario_count") or payload["metadata"]["total_scenarios"]
        assert counted == len(payload[key]), f"{relative} did not recount over the union"


def test_growing_the_catalogue_never_reshuffles_the_legacy_matrix(sandbox):
    """The frozen rotation is what protects the committed coverage atoms."""
    module = _load_builder(sandbox)
    relative = "tests/harness/json_matrices/nursing_station_phase2_canonical.json"
    before = _read(sandbox, relative)["scenarios"]

    module.REQUIREMENTS["FR-NS-999"] = module.RequirementSpec(
        "A newly added requirement", "ward-board", "/api/ward-board", ("tests/test_api.py",)
    )
    module.main()

    after = _read(sandbox, relative)["scenarios"]
    assert [row["use_case_id"] for row in after] == [row["use_case_id"] for row in before]
    assert [row["requirement_ids"] for row in after] == [row["requirement_ids"] for row in before]
    assert "FR-NS-999" not in module.LEGACY_MATRIX_REQUIREMENT_IDS
