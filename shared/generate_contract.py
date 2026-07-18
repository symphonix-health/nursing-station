from __future__ import annotations

import json
from pathlib import Path

from nursing_station.main import app

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "shared" / "openapi.json"


def main() -> None:
    OUTPUT.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
