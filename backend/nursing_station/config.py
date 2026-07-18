from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_path: Path
    jwt_secret: str
    token_minutes: int = 480
    warning_profile_version: str = "NS-NEWS2-PHASE1-v1"
    warning_review_threshold: int = 3
    warning_escalation_threshold: int = 5
    warning_critical_threshold: int = 7
    escalation_due_minutes: int = 5


def get_settings() -> Settings:
    root = Path(__file__).resolve().parents[2]
    return Settings(
        database_path=Path(os.getenv("NURSING_STATION_DB", root / "data" / "nursing_station.db")),
        jwt_secret=os.getenv("NURSING_STATION_JWT_SECRET", "phase1-local-development-key-change-me"),
        warning_profile_version=os.getenv("NURSING_STATION_WARNING_PROFILE", "NS-NEWS2-PHASE1-v1"),
        warning_review_threshold=int(os.getenv("NURSING_STATION_WARNING_REVIEW", "3")),
        warning_escalation_threshold=int(os.getenv("NURSING_STATION_WARNING_ESCALATE", "5")),
        warning_critical_threshold=int(os.getenv("NURSING_STATION_WARNING_CRITICAL", "7")),
        escalation_due_minutes=int(os.getenv("NURSING_STATION_ESCALATION_DUE_MINUTES", "5")),
    )
