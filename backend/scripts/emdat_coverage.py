"""Is the 27-event benchmark a biased sample of the disruption population?

Every hand-curated benchmark invites the reviewer question "how did you choose
these events, and what did you leave out?". Until now the honest answer was a
narrative one. EM-DAT (19,651 disasters, 1995-2026) provides an external,
independently-assembled population to measure our coverage against.

What this does NOT do: EM-DAT records damage in US dollars, not the percentage
decline in a sector's physical output that the benchmark calibrates on. So it
cannot supply new calibration targets. It can do something else that matters —
tell us, quantitatively, which large disruptions our benchmark covers, which it
misses, and whether the misses are systematic.

Run:  python -m scripts.emdat_coverage
Output: data/calibration/emdat_coverage.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from app.data.seed_data import HISTORICAL_EVENTS

ROOT = Path(__file__).resolve().parents[1]
EMDAT = ROOT / "data" / "raw" / "external" / "emdat" / "emdat_public_2026-07-31.xlsx"
LOGGED = ROOT / "data" / "csv" / "historical_events.csv"
OUT = ROOT / "data" / "calibration" / "emdat_coverage.json"

GRAPH_COUNTRIES = {"CHN", "DEU", "IND", "JPN", "KOR", "MEX",
                   "MYS", "NLD", "THA", "TWN", "USA", "VNM"}
DAMAGE = "Total Damage, Adjusted ('000 US$)"

# Benchmark / logged events that originate in a natural disaster, keyed to the
# (ISO3, year) EM-DAT would record them under. Non-disaster events (tariffs,
# lockdowns, strikes, canal blockages, the financial crisis) have no EM-DAT
# counterpart by construction and are excluded from the matching denominator.
DISASTER_EVENTS = {
    ("JPN", 2011): "japan-triple-disaster-2011",
    ("THA", 2011): "thailand-floods-2011",
    ("USA", 2017): "hurricane-harvey-2017",
    ("TWN", 1999): "taiwan-chichi-earthquake-1999",
    ("JPN", 2016): "kumamoto-earthquake-2016",
    ("USA", 2021): "texas-winter-storm-2021",
    ("TWN", 2021): "taiwan-drought-2021",
    ("DEU", 2021): "germany-floods-2021 (logged, not wired)",
    ("USA", 2005): "hurricane-katrina-2005 (logged, not wired)",
    ("JPN", 1995): "kobe-earthquake-1995 (logged, not wired)",
}


def main() -> int:
    if not EMDAT.exists():
        print(f"ERROR: missing {EMDAT}", file=sys.stderr)
        return 1

    df = pd.read_excel(EMDAT)
    df[DAMAGE] = pd.to_numeric(df[DAMAGE], errors="coerce")
    df["ISO"] = df["ISO"].astype(str)

    total_rows = len(df)
    in_graph = df[df["ISO"].isin(GRAPH_COUNTRIES) & (df["Start Year"] >= 1995)].copy()

    tiers = {}
    for label, floor in (("ge_1bn", 1_000_000), ("ge_5bn", 5_000_000),
                         ("ge_10bn", 10_000_000), ("ge_50bn", 50_000_000)):
        sel = in_graph[in_graph[DAMAGE] >= floor]
        matched = sum(1 for _, r in sel.iterrows()
                      if (r["ISO"], int(r["Start Year"])) in DISASTER_EVENTS)
        tiers[label] = {
            "damage_floor_usd_bn": floor / 1e6,
            "n_disasters": int(len(sel)),
            "n_matched_to_our_events": int(matched),
            "coverage": round(matched / len(sel), 4) if len(sel) else None,
        }

    # The largest disasters, flagged by whether we cover them
    top = in_graph.nlargest(25, DAMAGE)
    top_list = []
    for _, r in top.iterrows():
        key = (r["ISO"], int(r["Start Year"]))
        top_list.append({
            "year": int(r["Start Year"]),
            "iso3": r["ISO"],
            "type": str(r["Disaster Type"]),
            "damage_usd_bn": round(float(r[DAMAGE]) / 1e6, 1),
            "in_benchmark": DISASTER_EVENTS.get(key),
        })

    # Composition: what kinds of disaster dominate the population vs our set
    pop_types = in_graph[in_graph[DAMAGE] >= 1_000_000]["Disaster Type"] \
        .value_counts().head(8).to_dict()

    payload = {
        "schema": "geds.emdat_coverage.v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "EM-DAT public (CRED / UCLouvain), custom request 2026-07-31",
        "emdat_rows_total": int(total_rows),
        "emdat_rows_in_graph_countries_since_1995": int(len(in_graph)),
        "benchmark_size": len(HISTORICAL_EVENTS),
        "benchmark_disaster_origin_events": len(DISASTER_EVENTS),
        "coverage_by_damage_tier": tiers,
        "largest_25_disasters": top_list,
        "population_type_mix_ge_1bn": {str(k): int(v) for k, v in pop_types.items()},
        "interpretation": {
            "what_this_measures": "the share of the largest EM-DAT disasters in our "
                                  "12 graph countries that appear in the benchmark "
                                  "(or in the logged not-wired registry)",
            "what_this_cannot_do": "EM-DAT records damage in USD, not the sector "
                                   "output-loss percentage the benchmark calibrates "
                                   "against, so it cannot supply new targets",
            "known_bias": "coverage falls as the damage floor drops: the benchmark "
                          "deliberately favours events with a published sector "
                          "output figure, which correlates with size and with "
                          "manufacturing (rather than residential) exposure",
        },
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"EM-DAT rows: {total_rows}, in our 12 countries since 1995: {len(in_graph)}\n")
    print(f"{'tier':>10} {'disasters':>10} {'covered':>8} {'share':>7}")
    for label, t in tiers.items():
        cov = f"{t['coverage']:.0%}" if t["coverage"] is not None else "—"
        print(f"{label:>10} {t['n_disasters']:>10} {t['n_matched_to_our_events']:>8} {cov:>7}")
    print(f"\nLargest disasters not in the benchmark:")
    for e in top_list:
        if not e["in_benchmark"]:
            print(f"  {e['year']} {e['iso3']} {e['type'][:18]:<18} ${e['damage_usd_bn']:>7.1f}bn")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
