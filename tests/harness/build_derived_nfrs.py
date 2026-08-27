"""Derive Nursing Station NFRs from the canonical requirement superset.

The CAID ISO/IEC 25010:2023 engine owns the derivation rules.  This consumer
harness records the project posture and persists its reproducible output.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUPERSET = ROOT / "tests" / "harness" / "requirements_superset.json"
OUT = ROOT / "tests" / "harness" / "derived_nfrs.json"
WORKSPACE = Path(os.getenv("SYMPHONIX_WORKSPACE_ROOT", ROOT.parent)).resolve()
CAID_SRC = WORKSPACE / "caid-agent" / "src"
if CAID_SRC.is_dir() and str(CAID_SRC) not in sys.path:
    sys.path.insert(0, str(CAID_SRC))


def _scale_tier_for_subsystem(subsystem: str) -> str:
    return "sovereign" if subsystem == "nursing-station" else "production"


def _project_type_for_subsystem(subsystem: str) -> str:
    del subsystem
    return "backend_api"


def _regulatory_regime_for_subsystem(subsystem: str) -> list[str]:
    base = ["ISO_27001", "ISO_27701"]
    if subsystem == "nursing-station":
        base.extend(["NHS_DCB", "GDPR"])
    return base


def main() -> None:
    try:
        from caid.nfr_derivation import NFRDerivationEngine
        from caid.task_spec import RequirementLink
    except ImportError as exc:
        raise SystemExit(
            f"CAID NFR engine not importable ({exc}); configure "
            "SYMPHONIX_WORKSPACE_ROOT or install caid-agent"
        ) from exc

    if not SUPERSET.is_file():
        raise SystemExit(f"missing canonical requirement superset: {SUPERSET}")
    superset = json.loads(SUPERSET.read_text(encoding="utf-8"))
    metadata = superset.get("metadata") or {}
    subsystem = metadata.get("subsystem", superset.get("subsystem", "unknown"))
    frs = [
        RequirementLink(
            req_id=row["requirement_id"],
            title=row.get("title", row["requirement_id"]),
            statement=row.get("statement", ""),
            rationale=row.get("rationale", ""),
            category="functional",
        )
        for row in superset["requirements"]
        if row.get("category", "functional") != "non-functional"
    ]
    derived = NFRDerivationEngine().derive(
        frs=frs,
        project_type=_project_type_for_subsystem(subsystem),
        regulatory_regime=_regulatory_regime_for_subsystem(subsystem),
        scale_tier=_scale_tier_for_subsystem(subsystem),
        prior_nfrs=OUT if OUT.exists() else None,
    )
    payload = {
        "schema_version": "BT_DERIVED_NFRS_V1",
        "iso_model": "ISO/IEC 25010:2023",
        "metadata": {
            "subsystem": subsystem,
            "fr_count": len(frs),
            "derived_nfr_count": len(derived),
            "project_type": _project_type_for_subsystem(subsystem),
            "regulatory_regime": _regulatory_regime_for_subsystem(subsystem),
            "scale_tier": _scale_tier_for_subsystem(subsystem),
            "characteristics_covered": sorted(
                {item.nfr_aspects[0] for item in derived if item.nfr_aspects}
            ),
        },
        "derived_nfrs": [
            {
                "requirement_id": item.req_id,
                "title": item.title,
                "statement": item.statement,
                "rationale": item.rationale,
                "category": item.category,
                "priority": item.priority,
                "iso_25010_characteristic": (
                    item.nfr_aspects[0] if item.nfr_aspects else ""
                ),
                "iso_25010_subcharacteristic": (
                    item.nfr_aspects[1] if len(item.nfr_aspects) > 1 else ""
                ),
                "regulatory_ref": item.regulatory_ref,
                "trace_links": item.trace_links,
                "acceptance_criteria": [
                    {
                        "ac_id": criterion.ac_id,
                        "given": criterion.given,
                        "when": criterion.when,
                        "then": criterion.then,
                        "test_type": criterion.test_type,
                    }
                    for criterion in item.acceptance_criteria
                ],
            }
            for item in derived
        ],
    }
    OUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"[OK] {OUT.name}: {len(derived)} NFRs from {len(frs)} FRs")


if __name__ == "__main__":
    main()
