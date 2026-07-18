from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_path: Path
    jwt_secret: str
    token_minutes: int = 480


def get_settings() -> Settings:
    root = Path(__file__).resolve().parents[2]
    return Settings(
        database_path=Path(os.getenv("NURSING_STATION_DB", root / "data" / "nursing_station.db")),
        jwt_secret=os.getenv("NURSING_STATION_JWT_SECRET", "phase1-local-development-key-change-me"),
    )
