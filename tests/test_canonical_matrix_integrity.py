"""Nursing Station canonical matrix integrity checks via the shared CAID suite."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CAID_SRC = REPO_ROOT.parent / "caid-agent" / "src"
if str(CAID_SRC) not in sys.path:
    sys.path.insert(0, str(CAID_SRC))

import caid.matrices._integrity_tests as _suite  # noqa: E402

_suite._REPO_ROOT = REPO_ROOT
_suite._reset_cache()

# Delegate the Phase 1 functional-matrix contract to CAID. NFR derivation is a
# separate CAID deliverable and is not imported as an optional/skipped suite.
test_canonical_schema_present = _suite.test_canonical_schema_present
test_each_matrix_has_exactly_100_scenarios = _suite.test_each_matrix_has_exactly_100_scenarios
test_each_matrix_distribution_is_85_10_5 = _suite.test_each_matrix_distribution_is_85_10_5
test_every_scenario_has_canonical_columns = _suite.test_every_scenario_has_canonical_columns
test_every_scenario_has_unique_use_case_id = _suite.test_every_scenario_has_unique_use_case_id
test_every_scenario_traces_to_at_least_one_requirement = (
    _suite.test_every_scenario_traces_to_at_least_one_requirement
)
test_requirements_matrix_canonical_schema = _suite.test_requirements_matrix_canonical_schema
test_every_requirement_is_covered = _suite.test_every_requirement_is_covered
test_no_scenario_references_unknown_requirement = _suite.test_no_scenario_references_unknown_requirement
test_no_l202_truncated_requirement_ids = _suite.test_no_l202_truncated_requirement_ids
test_requirements_count_matches_superset = _suite.test_requirements_count_matches_superset
test_every_superset_requirement_has_scenario_coverage = (
    _suite.test_every_superset_requirement_has_scenario_coverage
)
test_use_case_workflows_have_scenario_coverage = _suite.test_use_case_workflows_have_scenario_coverage
