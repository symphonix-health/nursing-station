"""Country policy packs as versioned data (FR-NS-170, NFR-NS-027).

A country pack carries the jurisdictional overlay that the ward workflow needs:
the early-warning profile, the safe-staffing norms and declaration triggers, the
harm-incident classification and external reporting owner, the discharge
criteria set, and the nursing quality measure definitions.

Three rules make this data rather than code:

1. Every clinically meaningful entry cites a ``source_id`` that resolves to a
   publisher, title and effective date inside the same pack.
2. A pack carries a ``pack_version``. Adoption is pinned to the exact version,
   so shipping a new pack version never silently re-adopts it.
3. A pack ships as ``adoption_status: "candidate"``. Nothing in this module
   promotes a pack; only a recorded organisational adoption decision does
   (``country_pack_adoptions``), and Nursing Station reports the difference
   rather than hiding it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

PACK_DIR = Path(__file__).resolve().parent / "country_packs"
SCHEMA_VERSION = "NS_COUNTRY_PACK_V1"
DEFAULT_JURISDICTION = "IE"

# Sections a pack must carry in full. A pack missing one of these is a
# configuration defect, not a partially-supported jurisdiction: the ward
# workflow would silently lose a national control.
REQUIRED_SECTIONS = (
    "early_warning",
    "safe_staffing",
    "harm_incident",
    "discharge",
    "quality_measures",
)


class CountryPackError(RuntimeError):
    """A pack is missing, malformed, or cites a source it does not define."""


@dataclass(frozen=True)
class CountryPack:
    jurisdiction: str
    payload: dict[str, Any]

    @property
    def pack_version(self) -> str:
        return str(self.payload["pack_version"])

    @property
    def jurisdiction_name(self) -> str:
        return str(self.payload["jurisdiction_name"])

    @property
    def early_warning(self) -> dict[str, Any]:
        return self.payload["early_warning"]

    @property
    def safe_staffing(self) -> dict[str, Any]:
        return self.payload["safe_staffing"]

    @property
    def harm_incident(self) -> dict[str, Any]:
        return self.payload["harm_incident"]

    @property
    def discharge_criteria(self) -> list[dict[str, Any]]:
        return list(self.payload["discharge"]["criteria"])

    @property
    def quality_measures(self) -> list[dict[str, Any]]:
        return list(self.payload["quality_measures"])

    def source(self, source_id: str) -> dict[str, Any]:
        for entry in self.payload.get("sources", []):
            if entry.get("source_id") == source_id:
                return entry
        raise CountryPackError(
            f"{self.jurisdiction} pack cites undefined source_id {source_id!r}"
        )

    def ward_norm(self, specialty: str) -> dict[str, Any] | None:
        for norm in self.safe_staffing.get("ward_norms", []):
            if norm.get("specialty") == specialty:
                return norm
        return None

    def measure(self, measure_id: str) -> dict[str, Any] | None:
        for measure in self.quality_measures:
            if measure.get("measure_id") == measure_id:
                return measure
        return None

    def summary(self) -> dict[str, Any]:
        """Non-clinical description of the pack, safe for any authenticated role."""
        return {
            "jurisdiction": self.jurisdiction,
            "jurisdiction_name": self.jurisdiction_name,
            "pack_version": self.pack_version,
            "effective_from": self.payload["effective_from"],
            "adoption_status": self.payload["adoption_status"],
            "adoption_note": self.payload["adoption_note"],
            "languages": self.payload.get("languages", []),
            "early_warning_profile_id": self.early_warning["profile_id"],
            "safe_staffing_framework_id": self.safe_staffing["framework_id"],
            "quality_measure_ids": [m["measure_id"] for m in self.quality_measures],
            "discharge_criterion_ids": [c["criterion_id"] for c in self.discharge_criteria],
            "sources": self.payload.get("sources", []),
        }


def _validate(jurisdiction: str, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise CountryPackError(f"{jurisdiction} pack is not a JSON object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise CountryPackError(
            f"{jurisdiction} pack schema_version {payload.get('schema_version')!r} "
            f"is not {SCHEMA_VERSION}"
        )
    if payload.get("jurisdiction") != jurisdiction:
        raise CountryPackError(
            f"{jurisdiction} pack declares jurisdiction {payload.get('jurisdiction')!r}"
        )
    for field in ("pack_version", "effective_from", "adoption_status", "adoption_note"):
        if not payload.get(field):
            raise CountryPackError(f"{jurisdiction} pack is missing {field}")
    for section in REQUIRED_SECTIONS:
        if section not in payload:
            raise CountryPackError(f"{jurisdiction} pack is missing section {section}")
    defined = {entry.get("source_id") for entry in payload.get("sources", [])}
    if None in defined or "" in defined:
        raise CountryPackError(f"{jurisdiction} pack has a source without a source_id")
    for entry in payload.get("sources", []):
        for field in ("publisher", "title", "document_type", "effective_from"):
            if not entry.get(field):
                raise CountryPackError(
                    f"{jurisdiction} source {entry.get('source_id')!r} is missing {field}"
                )
    cited: set[str] = set()
    for node in (
        payload["early_warning"],
        payload["safe_staffing"],
        payload["harm_incident"].get("external_reporting", {}),
        *payload["quality_measures"],
    ):
        source_id = node.get("source_id") if isinstance(node, dict) else None
        if source_id:
            cited.add(str(source_id))
    dangling = sorted(cited - defined)
    if dangling:
        raise CountryPackError(f"{jurisdiction} pack cites undefined sources: {dangling}")
    return payload


@cache
def available_jurisdictions() -> tuple[str, ...]:
    return tuple(sorted(path.stem.upper() for path in PACK_DIR.glob("*.json")))


@cache
def load_pack(jurisdiction: str) -> CountryPack:
    code = (jurisdiction or "").strip().upper()
    path = PACK_DIR / f"{code.lower()}.json"
    if not path.exists():
        raise CountryPackError(
            f"No country pack for {code!r}; available: {list(available_jurisdictions())}"
        )
    payload = _validate(code, json.loads(path.read_text(encoding="utf-8")))
    return CountryPack(jurisdiction=code, payload=payload)


def reset_cache() -> None:
    load_pack.cache_clear()
    available_jurisdictions.cache_clear()
