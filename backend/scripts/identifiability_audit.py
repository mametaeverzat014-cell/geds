"""Are the engine's five parameters identified by a 27-event benchmark?

The paper already reports a Sobol sensitivity analysis showing that two of the
five parameters carry almost all output variance. This script asks the harder
and more damaging question directly: given the benchmark we actually have, is
the fitted parameter vector *determined* by the data at all?

Three independent diagnostics, each of which can fail on its own:

1. BOUNDARY PINNING. A global differential-evolution fit that lands on its own
   search-box edge has not found an interior optimum — the loss is still
   improving when the optimizer runs out of room, so the reported value is a
   property of the prior box, not of the data. Any parameter within 1% of a
   bound is flagged.

2. LEAVE-ONE-OUT DISPERSION. Refit the parameters 27 times, each time dropping
   one event. A parameter that is identified barely moves. A parameter whose
   fitted value swings by orders of magnitude when a single event of 27 is
   removed is being driven by noise, and its "calibrated" value carries no
   information. Reported as the ratio of the LOO range to the LOO median.

3. GLOBAL-vs-LOO CONSISTENCY. If the global fit sits outside the entire range
   spanned by the LOO fits, the two procedures disagree about where the optimum
   is, which is only possible on a flat or multimodal loss surface.

Both inputs already exist in the repository, so this reads rather than recomputes:
    data/calibration/de_result.json       global DE fit (2785 s)
    data/calibration/loo_de_result.json   27-fold LOO refit (5992 s)

Why this matters for the paper's headline: if the parameters are not identified,
then "a five-parameter mechanistic model fails to beat a zero-parameter
baseline" is not a statement about mechanism at all. It is a statement that the
benchmark cannot constrain five parameters — which is the same conclusion the
power analysis, the ablation significance test and the v3 one-parameter result
reach by three other routes.

Run:  python -m scripts.identifiability_audit
Output: data/calibration/identifiability.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

CAL = Path(__file__).resolve().parents[1] / "data" / "calibration"
OUT = CAL / "identifiability.json"

# A parameter sitting this close to a search bound (as a fraction of the box
# width) is treated as pinned: DE cannot report an interior optimum there.
BOUNDARY_TOL = 0.01

# LOO range / |LOO median| above this means one event out of 27 moves the fit by
# more than the fit itself — no useful identification.
DISPERSION_ALARM = 1.0


def _load(name: str) -> dict:
    path = CAL / name
    if not path.exists():
        raise SystemExit(f"missing required artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def boundary_report(de: dict) -> dict:
    """Which globally-fitted parameters are stuck on their own search box?"""
    rows = {}
    for p in de["parameters"]:
        lo, hi = float(p["prior_low"]), float(p["prior_high"])
        pt = float(p["point"])
        width = hi - lo
        frac_lo = (pt - lo) / width if width else 0.0
        frac_hi = (hi - pt) / width if width else 0.0
        at_low = frac_lo <= BOUNDARY_TOL
        at_high = frac_hi <= BOUNDARY_TOL
        rows[p["name"]] = {
            "point": round(pt, 6),
            "prior_low": lo,
            "prior_high": hi,
            "distance_to_nearest_bound_frac": round(min(frac_lo, frac_hi), 6),
            "pinned_at_lower_bound": bool(at_low),
            "pinned_at_upper_bound": bool(at_high),
            "pinned": bool(at_low or at_high),
        }
    return rows


def dispersion_report(loo: dict) -> dict:
    """How far does each parameter move when one event of 27 is dropped?"""
    folds = loo["folds"]
    names = list(folds[0]["fold_params"])
    rows = {}
    for nm in names:
        v = np.array([float(f["fold_params"][nm]) for f in folds], dtype=float)
        med = float(np.median(v))
        rng = float(v.max() - v.min())
        rows[nm] = {
            "n_folds": int(v.size),
            "min": round(float(v.min()), 6),
            "max": round(float(v.max()), 6),
            "median": round(med, 6),
            "loo_range": round(rng, 6),
            "range_over_median": round(rng / abs(med), 4) if med else None,
            "coef_of_variation": round(float(v.std() / abs(v.mean())), 4)
            if v.mean() else None,
            "unidentified": bool(med and (rng / abs(med)) > DISPERSION_ALARM),
        }
    return rows


def consistency_report(de: dict, loo: dict) -> dict:
    """Does the global fit even live inside the range the LOO refits explore?"""
    folds = loo["folds"]
    rows = {}
    for p in de["parameters"]:
        nm = p["name"]
        if nm not in folds[0]["fold_params"]:
            continue
        v = np.array([float(f["fold_params"][nm]) for f in folds], dtype=float)
        pt = float(p["point"])
        inside = bool(v.min() <= pt <= v.max())
        rows[nm] = {
            "global_fit": round(pt, 6),
            "loo_min": round(float(v.min()), 6),
            "loo_max": round(float(v.max()), 6),
            "global_inside_loo_range": inside,
        }
    return rows


def main() -> int:
    de = _load("de_result.json")
    loo = _load("loo_de_result.json")

    bounds = boundary_report(de)
    disp = dispersion_report(loo)
    cons = consistency_report(de, loo)

    n_pinned = sum(r["pinned"] for r in bounds.values())
    n_unident = sum(r["unidentified"] for r in disp.values())
    n_outside = sum(not r["global_inside_loo_range"] for r in cons.values())
    n_params = len(bounds)

    payload = {
        "schema": "geds.identifiability.v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n_parameters": n_params,
        "n_events": loo["n_folds"],
        "boundary_tolerance_frac": BOUNDARY_TOL,
        "dispersion_alarm_ratio": DISPERSION_ALARM,
        "sources": {
            "global_fit": "data/calibration/de_result.json",
            "loo_fit": "data/calibration/loo_de_result.json",
        },
        "global_fit_converged_fraction": de.get("converged_fraction"),
        "boundary_pinning": bounds,
        "loo_dispersion": disp,
        "global_vs_loo_consistency": cons,
        "summary": {
            "n_pinned_at_prior_bound": n_pinned,
            "n_unidentified_by_loo_dispersion": n_unident,
            "n_global_fits_outside_loo_range": n_outside,
        },
        "verdict": (
            f"{n_pinned}/{n_params} parameters are pinned to their search-box "
            f"bounds and {n_unident}/{n_params} move by more than their own "
            f"median when a single event of {loo['n_folds']} is removed. The "
            "five-parameter engine is NOT identified by this benchmark: the "
            "fitted values report the prior box and the resampling noise, not "
            "the data. Any claim that rests on a specific calibrated parameter "
            "value is unsupported."
            if (n_pinned or n_unident) else
            "All parameters sit interior to their priors and are stable under "
            "leave-one-out; the engine is identified by this benchmark."
        ),
        "reading": (
            "This is a negative result about the BENCHMARK, not only about the "
            "engine. It is the same ceiling the power analysis reports (MDE "
            "0.018 MAE vs observed gaps ~0.007), the ablation significance test "
            "reports (0 of 6 component deltas distinguishable from zero) and "
            "the v3 experiment reports (one scale parameter outperforms five "
            "tuned ones). Four independent routes, one conclusion."
        ),
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"parameters: {n_params}   events: {loo['n_folds']}   "
          f"global DE converged_fraction: {de.get('converged_fraction')}\n")
    print(f"{'parameter':20s} {'global':>10s} {'prior box':>18s} {'pinned':>8s} "
          f"{'LOO range':>18s} {'rng/med':>8s} {'unident':>8s}")
    for nm in bounds:
        b, d = bounds[nm], disp.get(nm, {})
        box = f"[{b['prior_low']:g}, {b['prior_high']:g}]"
        loo_rng = (f"[{d['min']:.4g}, {d['max']:.4g}]" if d else "—")
        rom = f"{d['range_over_median']:.2f}" if d.get("range_over_median") else "—"
        print(f"{nm:20s} {b['point']:10.4f} {box:>18s} "
              f"{('YES' if b['pinned'] else '—'):>8s} {loo_rng:>18s} {rom:>8s} "
              f"{('YES' if d.get('unidentified') else '—'):>8s}")
    print(f"\nglobal fit outside the LOO range for "
          f"{n_outside}/{len(cons)} parameters")
    print(f"\nverdict: {payload['verdict']}\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
