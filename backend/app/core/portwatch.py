"""IMF PortWatch chokepoint-transit validation.

First *time-series* validation in GEDS: daily vessel transits through
maritime chokepoints (IMF PortWatch, portwatch.imf.org, 2019 → present)
are compared against the chokepoint shock specifications of the historical
events and against the engine's simulated chokepoint trajectories.

What this gives us that scalar validation cannot:
  - event shock magnitudes checked against MEASURED transit deficits,
  - durations checked against how long the deficit actually persisted,
  - the rerouting hypothesis (capacity-factor weights, see seed_data
    CHOKEPOINT_LINKS) checked against the Cape of Good Hope mirror surge.

Raw data: backend/data/raw/external/portwatch_daily_chokepoints.csv
Reproduce: python -m scripts.portwatch_validation
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

DATA_PATH = (
    Path(__file__).resolve().parents[2]
    / "data" / "raw" / "external" / "portwatch_daily_chokepoints.csv"
)


# ─────────────────────────── loading ────────────────────────────────────────


def load_daily(chokepoint: str) -> pd.Series:
    """Daily total transits for one chokepoint, indexed by date."""
    df = pd.read_csv(DATA_PATH)
    df["date"] = pd.to_datetime(df["date"])
    d = df[df["portname"] == chokepoint].set_index("date").sort_index()
    if d.empty:
        raise KeyError(f"chokepoint {chokepoint!r} not in PortWatch data")
    return d["n_total"]


def weekly(chokepoint: str) -> pd.Series:
    """Weekly transit totals (calendar weeks, summed)."""
    return load_daily(chokepoint).resample("W").sum()


def deficit_profile(
    chokepoint: str,
    event_start: str,
    n_weeks: int,
    baseline_weeks: int = 10,
) -> tuple[np.ndarray, float]:
    """Weekly fractional transit deficit vs the pre-event baseline.

    Returns (deficits[n_weeks], baseline_transits_per_week). Deficit is
    1 − observed/baseline: +0.5 means half the traffic is gone; negative
    values are catch-up surges above baseline.
    """
    w = weekly(chokepoint)
    start = pd.Timestamp(event_start)
    base = w[start - pd.Timedelta(weeks=baseline_weeks): start - pd.Timedelta(days=1)].mean()
    seg = w[start: start + pd.Timedelta(weeks=n_weeks)].iloc[:n_weeks]
    return (1.0 - seg.to_numpy() / base), float(base)


# ─────────────────────────── event checks ───────────────────────────────────


@dataclass
class ChokepointEventCheck:
    slug: str
    chokepoint: str
    event_start: str
    spec_magnitude: float
    spec_duration_weeks: int
    observed_peak_weekly_deficit: float
    observed_peak_daily_deficit: float
    observed_mean_deficit_over_spec_window: float
    observed_weeks_above_half_spec: int      # how long the deficit stayed > spec/2
    catchup_surge_min_deficit: float         # most negative deficit after the event (queue clearing)
    magnitude_verdict: str
    duration_verdict: str


# Event start dates and the PortWatch chokepoint they map to.
CHOKEPOINT_EVENTS = [
    {"slug": "suez-canal-2021", "chokepoint": "Suez Canal",
     "event_start": "2021-03-23", "spec_magnitude": 0.90, "spec_duration_weeks": 2},
    {"slug": "red-sea-crisis-2023", "chokepoint": "Suez Canal",
     "event_start": "2023-12-15", "spec_magnitude": 0.55, "spec_duration_weeks": 40},
]


def _verdict(measured: float, spec: float, tol: float = 0.30) -> str:
    if abs(measured - spec) <= tol * max(spec, 1e-9):
        return f"CONFIRMED (spec {spec:.2f} vs measured {measured:.2f})"
    return f"MISMATCH (spec {spec:.2f} vs measured {measured:.2f})"


def check_event(ev: dict, follow_weeks: int = 60) -> ChokepointEventCheck:
    deficits, _ = deficit_profile(ev["chokepoint"], ev["event_start"], follow_weeks)
    daily = load_daily(ev["chokepoint"])
    start = pd.Timestamp(ev["event_start"])
    daily_base = daily[start - pd.Timedelta(weeks=10): start - pd.Timedelta(days=1)].mean()
    daily_seg = daily[start: start + pd.Timedelta(weeks=ev["spec_duration_weeks"])]
    daily_peak = float((1.0 - daily_seg / daily_base).max())

    spec_window = deficits[: ev["spec_duration_weeks"]]
    weeks_above = int((deficits > ev["spec_magnitude"] / 2).sum())
    # For a short sharp blockage the honest magnitude comparison is the DAILY
    # peak (weekly bins smear a 6-day closure); for a long partial disruption
    # it is the mean deficit over the spec window.
    measured_mag = daily_peak if ev["spec_duration_weeks"] <= 4 else float(np.mean(spec_window))

    dur_verdict = (
        f"deficit stayed > {ev['spec_magnitude']/2:.2f} for {weeks_above} weeks "
        f"(spec window {ev['spec_duration_weeks']}w"
        + (", still elevated at end of data)" if deficits[-1] > ev["spec_magnitude"] / 2 else ")")
    )
    return ChokepointEventCheck(
        slug=ev["slug"],
        chokepoint=ev["chokepoint"],
        event_start=ev["event_start"],
        spec_magnitude=ev["spec_magnitude"],
        spec_duration_weeks=ev["spec_duration_weeks"],
        observed_peak_weekly_deficit=round(float(np.max(spec_window)), 3),
        observed_peak_daily_deficit=round(daily_peak, 3),
        observed_mean_deficit_over_spec_window=round(float(np.mean(spec_window)), 3),
        observed_weeks_above_half_spec=weeks_above,
        catchup_surge_min_deficit=round(float(np.min(deficits)), 3),
        magnitude_verdict=_verdict(measured_mag, ev["spec_magnitude"]),
        duration_verdict=dur_verdict,
    )


def rerouting_cross_check(event_start: str = "2023-12-15", n_weeks: int = 26) -> dict:
    """The Red-Sea natural experiment for the capacity-factor edge weights.

    If carriers reroute rather than vanish, the Suez transit deficit must be
    mirrored by a Cape of Good Hope surge of comparable absolute size.
    """
    suez_def, suez_base = deficit_profile("Suez Canal", event_start, n_weeks)
    cape_def, cape_base = deficit_profile("Cape of Good Hope", event_start, n_weeks)
    suez_lost = suez_def * suez_base                 # transits/week lost at Suez
    cape_gained = -cape_def * cape_base              # transits/week gained at Cape
    corr = float(np.corrcoef(suez_lost, cape_gained)[0, 1])
    recovered = float(cape_gained[8:].mean() / suez_lost[8:].mean())  # after ramp-up
    return {
        "window_weeks": n_weeks,
        "suez_mean_weekly_deficit": round(float(suez_def.mean()), 3),
        "cape_mean_weekly_gain": round(float(-cape_def.mean()), 3),
        "weekly_correlation_suez_lost_vs_cape_gained": round(corr, 3),
        "fraction_of_lost_suez_transits_reappearing_at_cape": round(recovered, 3),
        "interpretation": (
            "Traffic shifts route rather than disappearing — supports modelling "
            "carrier output loss as traffic_share × (cost−1)/cost rather than "
            "the full traffic share (see CHOKEPOINT_LINKS in seed_data.py)."
        ),
    }


def run_validation() -> dict:
    checks = [asdict(check_event(ev)) for ev in CHOKEPOINT_EVENTS]
    return {
        "source": "IMF PortWatch daily chokepoint transits (portwatch.imf.org)",
        "raw_file": "backend/data/raw/external/portwatch_daily_chokepoints.csv",
        "reproduce_command": "python -m scripts.portwatch_validation",
        "event_checks": checks,
        "rerouting_cross_check": rerouting_cross_check(),
    }


__all__ = [
    "load_daily", "weekly", "deficit_profile",
    "check_event", "rerouting_cross_check", "run_validation",
    "CHOKEPOINT_EVENTS", "ChokepointEventCheck",
]
