"""Materialise one canonical 85/10/5 scenario matrix per derived NFR."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DERIVED = ROOT / "tests" / "harness" / "derived_nfrs.json"
OUT_DIR = ROOT / "tests" / "harness" / "nfr_canonical_matrices"
WORKSPACE = Path(os.getenv("SYMPHONIX_WORKSPACE_ROOT", ROOT.parent)).resolve()
CAID_SRC = WORKSPACE / "caid-agent" / "src"
if CAID_SRC.is_dir() and str(CAID_SRC) not in sys.path:
    sys.path.insert(0, str(CAID_SRC))


def main() -> None:
    try:
        from caid.nfr_canonical_matrix import build_all_nfr_matrices, write_matrices
        from caid.task_spec import AcceptanceCriterion, RequirementLink
    except ImportError as exc:
        raise SystemExit(
            f"CAID NFR matrix builder not importable ({exc}); configure "
            "SYMPHONIX_WORKSPACE_ROOT or install caid-agent"
        ) from exc
    if not DERIVED.is_file():
        raise SystemExit(f"missing {DERIVED}; run build_derived_nfrs.py first")

    payload = json.loads(DERIVED.read_text(encoding="utf-8"))
    subsystem = (payload.get("metadata") or {}).get("subsystem", "unknown")
    nfrs: list[RequirementLink] = []
    for row in payload.get("derived_nfrs", []):
        criteria = [
            AcceptanceCriterion(
                ac_id=item.get("ac_id", ""),
                given=item.get("given", ""),
                when=item.get("when", ""),
                then=item.get("then", ""),
                test_type=item.get("test_type", "Positive"),
            )
            for item in row.get("acceptance_criteria", [])
        ]
        nfrs.append(
            RequirementLink(
                req_id=row["requirement_id"],
                title=row.get("title", ""),
                statement=row.get("statement", ""),
                rationale=row.get("rationale", ""),
                category=row.get("category", "non-functional"),
                priority=row.get("priority", "HIGH"),
                nfr_aspects=[
                    row.get("iso_25010_characteristic", ""),
                    row.get("iso_25010_subcharacteristic", ""),
                ],
                regulatory_ref=row.get("regulatory_ref", ""),
                trace_links=row.get("trace_links", []),
                acceptance_criteria=criteria,
            )
        )
    if not nfrs:
        raise SystemExit("derived_nfrs.json contains no NFRs")
    written = write_matrices(
        build_all_nfr_matrices(nfrs, subsystem=subsystem),
        OUT_DIR,
    )
    print(f"[OK] {len(written)} NFR matrices, {len(written) * 100} scenarios")


if __name__ == "__main__":
    main()
