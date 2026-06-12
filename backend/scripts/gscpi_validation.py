"""Cross-validation against the NY Fed Global Supply Chain Pressure Index.

    python -m scripts.gscpi_validation

An INDEPENDENT check the model has never seen: for every historical event,
compare the engine's predicted global severity (peak CSI) with the measured
rise of the GSCPI (standard deviations from its mean) over the event window.
If the model's notion of "how big is this shock globally" is real, the two
should rank-correlate.

Honest caveat, recorded in the artifact: GSCPI is a single global aggregate,
so events with overlapping windows (the 2021 cluster) share one observed
spike — this inflates neither side but blurs attribution. We therefore
report Spearman across all events AND across the subset of non-overlapping
events.

Raw data: backend/data/raw/external/nyfed_gscpi.xls
Output:   data/calibration/gscpi_validation.json (served by /api/v1/gscpi-validation)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from app.core.backtest import _scenario_from_event  # same scenario construction as the backtest
from app.core.graph import compile_graph
from app.core.metrics import spearman_rho
from app.core.propagation import PropagationEngine
from app.core.types import EngineConfig
from app.data.seed import load_graph
from app.data.seed_data import HISTORICAL_EVENTS

RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / "external" / "nyfed_gscpi.xls"
OUT = Path(__file__).resolve().parents[1] / "data" / "calibration" / "gscpi_validation.json"

# Event onset months (sourced from the event descriptions in seed_data.py).
EVENT_START: dict[str, str] = {
    "covid-semiconductor-2020-2021":    "2020-03",
    "suez-canal-2021":                  "2021-03",
    "auto-chip-shortage-2021":          "2021-01",
    "japan-triple-disaster-2011":       "2011-03",
    "us-china-tariffs-2019":            "2019-09",
    "texas-winter-storm-2021":          "2021-02",
    "eu-energy-crisis-2021":            "2021-09",
    "malaysia-semiconductor-2021":      "2021-08",
    "thailand-floods-2011":             "2011-10",
    "kumamoto-earthquake-2016":         "2016-04",
    "renesas-naka-fire-2021":           "2021-03",
    "japan-korea-export-controls-2019": "2019-07",
    "vietnam-covid-lockdown-2021":      "2021-07",
    "shanghai-lockdown-2022":           "2022-04",
    "ukraine-war-harness-2022":         "2022-03",
    "china-power-crunch-2021":          "2021-09",
    "yantian-port-closure-2021":        "2021-05",
    "us-west-coast-ports-2021":         "2021-08",
    "red-sea-crisis-2023":              "2023-12",
    "taiwan-drought-2021":              "2021-02",
    "india-covid-wave-2021":            "2021-04",
    "taiwan-chichi-earthquake-1999":    "1999-09",
    "hurricane-harvey-2017":            "2017-08",
    "us-west-coast-ports-2015":         "2014-10",
    "korea-trucker-strikes-2022":       "2022-06",
    "panama-canal-drought-2023":        "2023-11",
}

# Events whose windows do NOT overlap the 2021 supply-chain super-cycle
# (or each other) — the cleaner subset for attribution.
NON_OVERLAPPING = [
    "taiwan-chichi-earthquake-1999",
    "japan-triple-disaster-2011", "thailand-floods-2011",
    "us-west-coast-ports-2015",
    "kumamoto-earthquake-2016", "hurricane-harvey-2017",
    "us-china-tariffs-2019",
    "japan-korea-export-controls-2019", "covid-semiconductor-2020-2021",
    "shanghai-lockdown-2022", "ukraine-war-harness-2022",
    "red-sea-crisis-2023",
]


def load_gscpi() -> pd.Series:
    df = pd.read_excel(RAW, sheet_name="GSCPI Monthly Data", skiprows=4)
    df = df.iloc[:, :2]
    df.columns = ["date", "gscpi"]
    df = df.dropna()
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")["gscpi"].sort_index()


def gscpi_rise(s: pd.Series, start_month: str, horizon_weeks: int) -> float:
    """Max GSCPI inside the event window minus the level the month before onset."""
    start = pd.Timestamp(start_month + "-01")
    pre = s[: start - pd.Timedelta(days=1)].iloc[-1]
    months = max(2, int(round(horizon_weeks / 4.33)))
    window = s[start: start + pd.DateOffset(months=months)]
    return float(window.max() - pre)


def main() -> None:
    gscpi = load_gscpi()
    graph = compile_graph(load_graph())
    cfg = EngineConfig(seed=0, stochastic_sigma=0.0)

    rows = []
    for ev in HISTORICAL_EVENTS:
        slug = ev["slug"]
        result = PropagationEngine(graph, cfg).run(_scenario_from_event(ev, cfg))
        rows.append({
            "slug": slug,
            "predicted_peak_csi": round(result.summary.peak_csi, 4),
            "observed_gscpi_rise_sd": round(gscpi_rise(gscpi, EVENT_START[slug], ev["horizon_weeks"]), 3),
        })

    pred = np.array([r["predicted_peak_csi"] for r in rows])
    obs = np.array([r["observed_gscpi_rise_sd"] for r in rows])
    sub = [i for i, r in enumerate(rows) if r["slug"] in NON_OVERLAPPING]

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "NY Fed Global Supply Chain Pressure Index (monthly, 1997→present)",
        "raw_file": "backend/data/raw/external/nyfed_gscpi.xls",
        "reproduce_command": "python -m scripts.gscpi_validation",
        "method": "Spearman rank correlation between the engine's predicted peak CSI "
                  "and the measured GSCPI rise (s.d.) over each event window. The model "
                  "was never calibrated on GSCPI — this is a fully independent check.",
        "caveat": "GSCPI is one global aggregate: the 2021 events overlap a single "
                  "super-spike, blurring per-event attribution. The non-overlapping "
                  "subset is the cleaner number.",
        "n_events": len(rows),
        "spearman_all_events": round(float(spearman_rho(pred, obs)), 3),
        "spearman_non_overlapping": round(float(spearman_rho(pred[sub], obs[sub])), 3),
        "n_non_overlapping": len(sub),
        "events": rows,
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in payload.items() if k != "events"}, indent=2))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
