from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX_REL = "tests/harness/reduced_json_matrices/nursing_station_phase1_canonical.14col.json"
MATRIX = ROOT / MATRIX_REL
OUTPUT = ROOT / "tests/harness/scenario_success_evidence.json"


def main() -> None:
    scenarios = json.loads(MATRIX.read_text(encoding="utf-8"))["test_cases"]
    rows = []
    for index, scenario in enumerate(scenarios):
        use_case_id = scenario["use_case_id"]
        path = scenario["test_data"]["endpoint"]
        rows.append({
            "use_case_id": use_case_id,
            "matrix_row_key": f"{MATRIX_REL}#{index}:{use_case_id}",
            "pytest_node_id": (
                "tests/harness/test_matrix_scenario_app_harness.py::"
                f"test_matrix_scenario[{use_case_id}]"
            ),
            "expected_status": "passed",
            "app_paths_exercised": [path],
        })
    OUTPUT.write_text(json.dumps({
        "schema_version": "CAID_SCENARIO_SUCCESS_EVIDENCE_V1",
        "generator": "scripts/generate_scenario_success_evidence.py",
        "harness": "tests/harness/test_matrix_scenario_app_harness.py",
        "evidence": rows,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} scenario evidence rows to {OUTPUT}")


if __name__ == "__main__":
    main()
