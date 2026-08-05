from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REDUCED_DIR = ROOT / "tests/harness/reduced_json_matrices"
OUTPUT = ROOT / "tests/harness/scenario_success_evidence.json"


def _endpoint(scenario: dict) -> str:
    """The path a scenario exercises, in either 14-column dialect."""
    test_data = scenario.get("test_data") or {}
    if isinstance(test_data, dict):
        for key in ("endpoint", "path"):
            if test_data.get(key):
                return str(test_data[key])
    return "unspecified"


def main() -> None:
    rows = []
    # Every reduced matrix, not a named one: a matrix whose rows carry no
    # success evidence is reported by the CAID test-agent as a traceability
    # failure, so this generator must track the directory rather than a
    # hardcoded file that goes stale the moment a matrix is added.
    for matrix_path in sorted(REDUCED_DIR.glob("*.14col.json")):
        matrix_rel = matrix_path.relative_to(ROOT).as_posix()
        scenarios = json.loads(matrix_path.read_text(encoding="utf-8"))["test_cases"]
        for index, scenario in enumerate(scenarios):
            use_case_id = scenario["use_case_id"]
            rows.append({
                "use_case_id": use_case_id,
                "matrix_row_key": f"{matrix_rel}#{index}:{use_case_id}",
                "pytest_node_id": (
                    "tests/harness/test_matrix_scenario_app_harness.py::"
                    f"test_matrix_scenario[{use_case_id}]"
                ),
                "expected_status": "passed",
                "app_paths_exercised": [_endpoint(scenario)],
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
