"""Find disruption episodes in US industrial production, with measured magnitudes.

The benchmark's binding constraint is not "which events happened" but "which
events have a published output-loss figure". Hand-researching each one costs
hours. The Fed's G.17 release is a monthly industrial-production index per NAICS
industry back to 1967 — so for the US nodes the output loss can be MEASURED
directly rather than looked up, turning event discovery into a data problem.

Method: for each industry series, compute the year-over-year change (seasonally
adjusted, so the comparison is not contaminated by normal seasonality), then
flag months where the drop exceeds a threshold. Contiguous flagged months are
merged into one episode, whose magnitude is the deepest YoY drop in it.

What this gives and does not give: a ranked, measured list of candidate episodes
at USA:automotive / USA:semiconductors / USA:electronics. Attributing an episode
to a *cause* (a hurricane, a strike, a recession) still needs judgement — the
detector finds the dip, not its reason. Cross-referencing against EM-DAT
(scripts/emdat_coverage.py) is how a cause gets proposed.

Run:  python -m scripts.g17_event_detector
Output: data/calibration/g17_episodes.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
G17 = ROOT / "data" / "raw" / "external" / "frb_g17_industrial_production.csv"
OUT = ROOT / "data" / "calibration" / "g17_episodes.json"

# Seasonally-adjusted series only; NAICS → the graph node it corresponds to.
SERIES = {
    "IP.G3361T3.S": ("USA:automotive", "Motor vehicles and parts (NAICS 3361-3)"),
    "IP.G3344.S": ("USA:semiconductors", "Semiconductor and other electronic component (NAICS 3344)"),
    "IP.G3341.S": ("USA:electronics", "Computer and peripheral equipment (NAICS 3341)"),
    "IP.HITEK2.S": ("USA:electronics", "Computers, communications eq. and semiconductors"),
}

DROP_THRESHOLD = 0.08   # a >=8% YoY fall counts as a disruption month
MIN_MONTHS = 2          # ignore single-month blips (revision noise)


def load() -> pd.DataFrame:
    df = pd.read_csv(G17, skiprows=5).rename(columns=lambda c: c.strip())
    df = df.rename(columns={df.columns[0]: "date"})
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m", errors="coerce")
    df = df.dropna(subset=["date"]).set_index("date")
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def episodes_for(series: pd.Series) -> list[dict]:
    """Merge contiguous months of large YoY decline into episodes."""
    yoy = series.pct_change(12).dropna()
    flagged = yoy[yoy <= -DROP_THRESHOLD]
    if flagged.empty:
        return []

    out, run = [], [flagged.index[0]]
    for prev, cur in zip(flagged.index, flagged.index[1:], strict=False):
        # contiguous if the gap is a single month
        if (cur.to_period("M") - prev.to_period("M")).n == 1:
            run.append(cur)
        else:
            out.append(run)
            run = [cur]
    out.append(run)

    episodes = []
    for run in out:
        if len(run) < MIN_MONTHS:
            continue
        window = yoy.loc[run[0]:run[-1]]
        trough = window.idxmin()
        episodes.append({
            "start": f"{run[0]:%Y-%m}",
            "end": f"{run[-1]:%Y-%m}",
            "duration_months": len(run),
            "trough_month": f"{trough:%Y-%m}",
            "peak_yoy_drop": round(float(-window.min()), 4),
            "mean_yoy_drop": round(float(-window.mean()), 4),
        })
    return sorted(episodes, key=lambda e: -e["peak_yoy_drop"])


def main() -> int:
    if not G17.exists():
        print(f"ERROR: missing {G17}", file=sys.stderr)
        return 1
    df = load()

    by_node: dict[str, list[dict]] = {}
    for code, (node, label) in SERIES.items():
        if code not in df.columns:
            continue
        eps = episodes_for(df[code].dropna())
        for e in eps:
            e["series"] = code
            e["series_label"] = label
        by_node.setdefault(node, []).extend(eps)

    for node in by_node:
        by_node[node] = sorted(by_node[node], key=lambda e: -e["peak_yoy_drop"])

    payload = {
        "schema": "geds.g17_episodes.v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "Federal Reserve G.17 Industrial Production, seasonally adjusted, "
                  "downloaded 2026-07 via the Fed Data Download Program",
        "coverage": {"first": f"{df.index.min():%Y-%m}", "last": f"{df.index.max():%Y-%m}",
                     "months": int(len(df))},
        "method": {
            "measure": "year-over-year change of the seasonally-adjusted index",
            "drop_threshold": DROP_THRESHOLD,
            "min_consecutive_months": MIN_MONTHS,
            "magnitude_reported": "deepest YoY drop within the episode",
        },
        "episodes_by_node": by_node,
        "caveats": [
            "the detector finds dips, not causes; attribution needs judgement and "
            "an external event record (see scripts/emdat_coverage.py)",
            "YoY differencing means a long slump shows as one episode, and the "
            "recovery year can mechanically produce a mirror-image rebound",
            "US nodes only — G.17 is a US release; JPN/DEU/CHN nodes need their "
            "own national statistics (JAMA, VDA, NBS)",
        ],
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"G.17 {payload['coverage']['first']} — {payload['coverage']['last']} "
          f"({payload['coverage']['months']} months)\n")
    for node, eps in by_node.items():
        print(f"── {node}: {len(eps)} episodes")
        for e in eps[:6]:
            print(f"   {e['start']}–{e['end']} ({e['duration_months']:>2}m)  "
                  f"trough {e['trough_month']}  −{e['peak_yoy_drop']:.1%}")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
