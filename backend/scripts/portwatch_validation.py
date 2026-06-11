"""Run the PortWatch chokepoint validation and write the artifact.

    python -m scripts.portwatch_validation

Writes data/calibration/portwatch_validation.json (served by
/api/v1/portwatch-validation).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.portwatch import run_validation

OUT = Path(__file__).resolve().parents[1] / "data" / "calibration" / "portwatch_validation.json"


def main() -> None:
    payload = run_validation()
    payload["timestamp"] = datetime.now(timezone.utc).isoformat()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
