"""Discover chokepoint disruption episodes from PortWatch daily transit data.

This is the route to growing N that survived scrutiny. Two earlier routes did
not: disaster records paired with national production indices produced no
measurable signal (scripts/emdat_coverage.py, emdat_production_pairing.json),
and industrial-production episode detection mostly rediscovers recessions —
demand-side contractions, the wrong causal class for a supply-cascade engine.

Chokepoints avoid both problems. A blocked strait IS a supply-side shock by
construction, and the transit count is itself the magnitude — no proxy, no
searching a national aggregate for a diluted signal.

Method: weekly transits per chokepoint; a trailing median (excluding the weeks
immediately before, so a slow-onset event does not poison its own baseline)
gives the counterfactual; weeks below a deficit threshold are flagged and
contiguous runs merged into episodes. Reported magnitude is the deepest weekly
deficit, which matches the convention the benchmark's chokepoint events use
(peak throughput loss, not the mean).

Run:  python -m scripts.portwatch_event_detector
Output: data/calibration/portwatch_episodes.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "external" / "portwatch_daily_chokepoints.csv"
OUT = ROOT / "data" / "calibration" / "portwatch_episodes.json"

# PortWatch name -> graph node. Only the five the graph can represent.
CHOKEPOINTS = {
    "Suez Canal": "CP:Suez",
    "Panama Canal": "CP:Panama",
    "Strait of Malacca": "CP:Malacca",
    "Strait of Hormuz": "CP:Hormuz",
    "Taiwan Strait": "CP:TaiwanStrait",
}

DEFICIT_THRESHOLD = 0.15   # a week >=15% below baseline counts as disrupted
MIN_WEEKS = 2              # ignore single-week noise
BASELINE_WEEKS = 26        # trailing window for the counterfactual
GAP_WEEKS = 4              # skip the weeks just before, so onset doesn't bias it


def weekly_series(df: pd.DataFrame, name: str) -> pd.Series:
    d = df[df["portname"] == name].set_index("date").sort_index()
    return d["n_total"].resample("W").sum()


def detect(series: pd.Series) -> list[dict]:
    """Flag weeks far below a trailing median, merge contiguous runs.

    A cross-year seasonal baseline was tried and rejected: it is defeated by
    structural level shifts. After the Red Sea crisis Suez traffic settled at a
    permanently lower level, so comparing 2025 against the same weeks of
    pre-crisis years marks the entire new normal as an ongoing deficit (episode
    count went 19 -> 31, all the additions spurious). The trailing median adapts
    to level shifts; the price is that genuine seasonal troughs can trip the
    threshold, so episodes carry a `likely_seasonal` flag instead (see below).
    """
    baseline = (series.shift(GAP_WEEKS)
                      .rolling(BASELINE_WEEKS, min_periods=8)
                      .median())
    deficit = (1 - series / baseline).dropna()
    flagged = deficit[deficit >= DEFICIT_THRESHOLD]
    if flagged.empty:
        return []

    runs, run = [], [flagged.index[0]]
    for prev, cur in zip(flagged.index, flagged.index[1:], strict=False):
        if (cur - prev).days <= 7:
            run.append(cur)
        else:
            runs.append(run)
            run = [cur]
    runs.append(run)

    # months whose long-run mean sits >=10% below the annual mean
    monthly = series.groupby(series.index.month).mean()
    seasonal_troughs = set(monthly[monthly < monthly.mean() * 0.90].index)

    episodes = []
    for r in runs:
        if len(r) < MIN_WEEKS:
            continue
        window = deficit.loc[r[0]:r[-1]]
        peak = window.idxmax()
        episodes.append({
            "start": f"{r[0]:%Y-%m-%d}",
            "end": f"{r[-1]:%Y-%m-%d}",
            "duration_weeks": len(r),
            "peak_week": f"{peak:%Y-%m-%d}",
            "peak_deficit": round(float(window.max()), 4),
            "mean_deficit": round(float(window.mean()), 4),
            "baseline_transits_per_week": round(float(baseline.loc[peak]), 1),
            # months where this chokepoint is routinely quiet: a hit here needs
            # corroboration before it can be called an event
            "likely_seasonal": bool(pd.Timestamp(peak).month in seasonal_troughs),
        })
    return sorted(episodes, key=lambda e: -e["peak_deficit"])


def main() -> int:
    if not DATA.exists():
        print(f"ERROR: missing {DATA}", file=sys.stderr)
        return 1

    df = pd.read_csv(DATA)
    df["date"] = pd.to_datetime(df["date"])

    by_node, total = {}, 0
    for name, node in CHOKEPOINTS.items():
        s = weekly_series(df, name)
        if s.empty:
            continue
        eps = detect(s)
        for e in eps:
            e["chokepoint"] = name
        by_node[node] = eps
        total += len(eps)

    payload = {
        "schema": "geds.portwatch_episodes.v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "IMF PortWatch, Daily Chokepoint Transit Calls and Trade Volume "
                  "Estimates (28 chokepoints), downloaded 2026-07",
        "coverage": {"first": f"{df['date'].min():%Y-%m-%d}",
                     "last": f"{df['date'].max():%Y-%m-%d}",
                     "chokepoints_in_file": int(df["portname"].nunique())},
        "method": {
            "unit": "weekly total transits",
            "baseline": f"trailing {BASELINE_WEEKS}-week median, offset {GAP_WEEKS} weeks",
            "deficit_threshold": DEFICIT_THRESHOLD,
            "min_consecutive_weeks": MIN_WEEKS,
            "magnitude_reported": "deepest weekly deficit in the episode",
        },
        "n_episodes": total,
        "episodes_by_node": by_node,
        "caveats": [
            "the detector finds throughput drops, not their causes; attribution "
            "still needs an external record",
            "PortWatch revised the Hormuz boundary in March 2026, so apparent "
            "level shifts there may be methodological rather than real",
            "seasonal patterns (Lunar New Year, monsoon) can trip the threshold; "
            "candidates need a plausibility check before entering the benchmark",
        ],
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"PortWatch {payload['coverage']['first']} — {payload['coverage']['last']}\n")
    for node, eps in by_node.items():
        print(f"── {node}: {len(eps)} episodes")
        for e in eps[:8]:
            print(f"   {e['start']} → {e['end']} ({e['duration_weeks']:>2}w)  "
                  f"peak −{e['peak_deficit']:.1%}  (baseline {e['baseline_transits_per_week']:.0f}/wk)")
    print(f"\ntotal: {total} candidate episodes\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
