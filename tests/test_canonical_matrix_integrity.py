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

# Delegate the full shared suite to CAID via import * so this file tracks
# caid.matrices._integrity_tests.__all__ automatically -- see that module's
# own docstring for the canonical vendoring pattern (also used verbatim by
# pharmacy-system's tests/test_canonical_matrix_integrity.py). Do not hand-list
# test names here: an explicit per-name binding list silently stops tracking
# new/renamed tests upstream and breaks collection outright when a test is
# removed (e.g. test_each_matrix_has_exactly_100_scenarios was superseded by
# test_each_matrix_meets_the_minimum_scenario_floor + the 85/10/5 ratio check).
# NFR-derivation tests are included too: each one skips cleanly via
# pytest.skip when its optional artifact (derived_nfrs.json /
# nfr_canonical_matrices/) is not yet present in this repo.
from caid.matrices._integrity_tests import *  # noqa: F401, F403, E402
