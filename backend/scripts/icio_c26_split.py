"""Split ICIO C26 into semi vs electronics using the committed Comtrade pull.

    python -m scripts.icio_c26_split

Measures each (importer, exporter) semiconductor share of C26-type goods
imports (HS 8541+8542 vs +8471/8517/8528), rescoring the cross-border
semi-family edges with a semi-specific import penetration. Writes
data/calibration/icio_c26_split.json. See app/core/icio.py run_c26_split.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.core.icio import run_c26_split

OUT = Path(__file__).resolve().parents[1] / "data" / "calibration" / "icio_c26_split.json"


def main() -> None:
    payload = run_c26_split()
    payload["timestamp"] = datetime.now(UTC).isoformat()

    print("importer world semi-share of C26-type imports:")
    for k, v in payload["importer_world_semi_share"].items():
        print(f"  {k}: {v:.3f}")

    print(f"\n{'edge':<52}{'manual':>8}{'pair_share':>11}{'semi_pen':>10}")
    for r in payload["edges"]:
        pen = r["icio_semi_import_penetration"]
        print(
            f"{r['src']} -> {r['tgt']:<28}{r['manual_weight']:>6.3f}"
            f"{r['semi_share_pair']:>11.3f}"
            f"{(f'{pen:.4f}' if pen is not None else 'n/a'):>10}"
        )
    print("\nsemi-family correlation manual vs refined:",
          json.dumps(payload["semi_family_correlation_manual_vs_refined"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
