"""Export the ICIO-derived expanded-graph prototype (NOT wired into the engine).

    python -m scripts.icio_expand_graph [--min-flow 50] [--min-input-share 0.002]
                                        [--min-penetration 0.05]

Writes
    data/csv/expanded_graph_nodes_v3.csv   81 economies x 5 industry groups
    data/csv/expanded_graph_edges_v3.csv   measured flows passing the filters
    data/csv/expanded_graph_meta_v3.json   filters + sector map + counts

Industry note: ICIO C26 cannot be split into semiconductors vs electronics,
so the prototype carries one merged `electronics_c26` industry; see
app/core/icio.py EXPANSION_SECTOR_MAP.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from app.core.icio import run_graph_expansion

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "csv"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-flow", type=float, default=50.0,
                    help="minimum flow in USD million (default 50)")
    ap.add_argument("--min-input-share", type=float, default=0.002)
    ap.add_argument("--min-penetration", type=float, default=0.05)
    args = ap.parse_args()

    nodes, edges, meta = run_graph_expansion(
        min_flow_usd_m=args.min_flow,
        min_input_share=args.min_input_share,
        min_penetration=args.min_penetration,
    )
    meta["timestamp"] = datetime.now(UTC).isoformat()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    nodes_path = OUT_DIR / "expanded_graph_nodes_v3.csv"
    edges_path = OUT_DIR / "expanded_graph_edges_v3.csv"
    meta_path = OUT_DIR / "expanded_graph_meta_v3.json"
    nodes.to_csv(nodes_path, index=False)
    edges.to_csv(edges_path, index=False)
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(json.dumps(meta, indent=2))
    print(f"\ntop-10 edges by flow:\n{edges.head(10).to_string(index=False)}")
    print(f"\nWrote {nodes_path} ({len(nodes)} nodes)")
    print(f"Wrote {edges_path} ({len(edges)} edges)")
    print(f"Wrote {meta_path}")


if __name__ == "__main__":
    main()
