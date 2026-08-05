from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_path: Path
    jwt_secret: str
    token_minutes: int = 480
    # The early-warning profile id, its oxygen band tables, its review/escalate/
    # critical thresholds and its response intervals now come from the country
    # pack (see nursing_station.country_packs). The former
    # NURSING_STATION_WARNING_PROFILE / _REVIEW / _ESCALATE / _CRITICAL settings
    # were removed rather than left in place: a threshold environment variable
    # that no longer reaches the scorer is worse than none, because an operator
    # would believe they had changed an escalation trigger when they had not.
    # Select a jurisdiction with NURSING_STATION_JURISDICTION instead.
    escalation_due_minutes: int = 5
    integration_hub_url: str | None = None
    integration_hub_token: str | None = None
    integration_timeout_seconds: float = 10.0
    inbound_hmac_secret: str | None = None
    alert_refresh_seconds: int = 5
    # Jurisdiction selects the country pack. Ireland is the deployment
    # jurisdiction; Dublin is a location inside it, never a pack of its own.
    jurisdiction: str = "IE"


def get_settings() -> Settings:
    root = Path(__file__).resolve().parents[2]
    return Settings(
        database_path=Path(os.getenv("NURSING_STATION_DB", root / "data" / "nursing_station.db")),
        jwt_secret=os.getenv("NURSING_STATION_JWT_SECRET", "phase1-local-development-key-change-me"),
        escalation_due_minutes=int(os.getenv("NURSING_STATION_ESCALATION_DUE_MINUTES", "5")),
        integration_hub_url=os.getenv("NURSING_STATION_HUB_URL") or None,
        integration_hub_token=os.getenv("NURSING_STATION_HUB_TOKEN") or None,
        integration_timeout_seconds=float(
            os.getenv("NURSING_STATION_HUB_TIMEOUT_SECONDS", "10")
        ),
        inbound_hmac_secret=os.getenv("NURSING_STATION_INBOUND_HMAC_SECRET") or None,
        alert_refresh_seconds=int(os.getenv("NURSING_STATION_ALERT_REFRESH_SECONDS", "5")),
        jurisdiction=(os.getenv("NURSING_STATION_JURISDICTION") or "IE").strip().upper(),
    )
