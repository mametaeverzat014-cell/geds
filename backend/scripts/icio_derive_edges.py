"""Cross-validate the hand-authored EDGES_RAW weights against OECD ICIO 2019.

    python -m scripts.icio_derive_edges

Prints the manual-vs-ICIO table for every production edge and writes
data/calibration/icio_edge_check.json. See app/core/icio.py for method
and sector-mapping caveats.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.core.icio import run_edge_check

OUT = Path(__file__).resolve().parents[1] / "data" / "calibration" / "icio_edge_check.json"


def main() -> None:
    payload = run_edge_check()
    payload["timestamp"] = datetime.now(UTC).isoformat()

    hdr = (f"{'edge':<55}{'manual':>8}{'pen':>9}{'imp_pen':>9}{'imp+fd':>9}"
           f"{'in_share':>9}{'man/imp+fd':>11}  family")
    print(hdr)
    print("-" * len(hdr))
    fmt = lambda v, w=9: f"{v:>{w}.4f}" if v is not None else f"{'n/a':>{w}}"  # noqa: E731
    for r in payload["edges"]:
        edge = f"{r['src']} -> {r['tgt']}"
        ratio = r["manual_over_import_penetration_incl_fd"]
        ratio_s = f"{ratio:.2f}" if ratio is not None else "n/a"
        print(
            f"{edge:<55}{r['manual_weight']:>8.3f}"
            f"{fmt(r['icio_penetration'])}"
            f"{fmt(r['icio_import_penetration'])}"
            f"{fmt(r['icio_import_penetration_incl_fd'])}"
            f"{fmt(r['icio_input_share'])}"
            f"{ratio_s:>11}"
            f"  {r['family']}"
        )
    print(f"\n+ {len(payload['excluded_chokepoint_links'])} chokepoint links excluded "
          f"(capacity-factor convention, see artifact)")

    print("\nsummary:")
    print(json.dumps(payload["summary"], indent=2))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
