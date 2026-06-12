"""Component-wise ablation study.

For each engine component (SEIS state machine, R-state hysteresis, bullwhip
amplification, adaptive rerouting, endogenous distress thresholds), construct
a "ablated" engine config that disables ONLY that component, run the full
historical replay, and measure the performance drop versus the full model.

The output answers: **which engine components actually earn their complexity?**

This is the textbook ablation framework from systems ML (e.g., Sutton &
Barto's RL ablations, He et al. ResNet ablations).  Any component that
ablation removes WITHOUT hurting performance is dead weight.

Output table:
    full                   - baseline (everything on)
    no_seis                - SEIS state machine off → naive shock floor
    no_bullwhip            - bullwhip_factor pinned at 1.0
    no_adaptive_rerouting  - chokepoint cost surcharge off
    no_r_state_floor       - r_output_floor = 0 (no hysteresis)
    no_endogenous_distress - distress_base back to fixed 0.40
    naive_diffusion        - pure linear-diffusion baseline (from baselines.py)

Each row gets MAE/RMSE/Pearson on industry_loss across the 8 events.
A component whose deletion *improves* the score is a candidate for removal.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .backtest import backtest_event
from .baselines import linear_diffusion_predict
from .graph import compile_graph
from .types import EngineConfig, Industry, ShockSpec
from ..data.seed import load_graph
from ..data.seed_data import HISTORICAL_EVENTS


# ─────────────────────────── data classes ──────────────────────────────────


@dataclass
class AblationRow:
    variant: str
    description: str
    mae_loss: float
    rmse_loss: float
    pearson_loss: float
    spearman_loss: float
    pass_rate_50pct: float
    # Delta vs full model (negative = worse than full)
    mae_delta_vs_full: float
    pearson_delta_vs_full: float


@dataclass
class AblationReport:
    timestamp: str
    n_events: int
    rows: list[AblationRow]
    best_variant: str
    worst_variant: str


# ─────────────────────────── variants ──────────────────────────────────────


def _variants() -> list[tuple[str, str, EngineConfig]]:
    """Each ablation is the full config with one knob flipped off/down."""
    base = dict(
        propagation_decay=0.85, rerouting_efficiency=0.55,
        amplification_eps=0.06, amplification_mu=2.2,
        recovery_rate=0.07, bullwhip_factor=1.25,
        inventory_scale=1.0, distress_base=0.40,
        seis_enabled=True, adaptive_rerouting=True,
        stochastic_sigma=0.0, r_output_floor=0.30,
    )
    out: list[tuple[str, str, EngineConfig]] = []

    out.append(("full", "Full engine — all components enabled", EngineConfig(**base)))

    cfg = dict(base); cfg["seis_enabled"] = False
    out.append(("no_seis", "SEIS state machine disabled (raw shock propagation)", EngineConfig(**cfg)))

    cfg = dict(base); cfg["bullwhip_factor"] = 1.0
    out.append(("no_bullwhip", "Bullwhip factor pinned at 1.0", EngineConfig(**cfg)))

    cfg = dict(base); cfg["adaptive_rerouting"] = False
    out.append(("no_adaptive_rerouting", "Chokepoint cost surcharge disabled", EngineConfig(**cfg)))

    cfg = dict(base); cfg["r_output_floor"] = 0.0
    out.append(("no_r_state_floor", "R-state output floor at 0 (no hysteresis)", EngineConfig(**cfg)))

    # Candidate mechanism, default-off after the failed Batch-9b OOS test:
    # ablation keeps measuring what turning it ON would do.
    cfg = dict(base); cfg["per_node_recovery"] = True
    out.append(("with_per_node_recovery", "Shock decay coupled to per-node recovery_delay_weeks", EngineConfig(**cfg)))

    return out


# ─────────────────────────── eval helpers ──────────────────────────────────


def _eval_engine(config: EngineConfig, graph) -> dict:
    """Run the engine on every event, return (pred, obs) arrays plus passes."""
    pred = np.zeros(len(HISTORICAL_EVENTS))
    obs = np.zeros(len(HISTORICAL_EVENTS))
    pass50 = np.zeros(len(HISTORICAL_EVENTS), dtype=bool)
    for i, ev in enumerate(HISTORICAL_EVENTS):
        r = backtest_event(ev, graph, config)
        pred[i] = r.industry_loss_predicted
        obs[i]  = r.industry_loss_observed
        pass50[i] = r.passes_50pct
    return {"pred": pred, "obs": obs, "pass50": pass50}


def _eval_linear_diffusion(graph) -> dict:
    """Linear-diffusion baseline as one of the ablation rows."""
    pred = np.zeros(len(HISTORICAL_EVENTS))
    obs = np.zeros(len(HISTORICAL_EVENTS))
    for i, ev in enumerate(HISTORICAL_EVENTS):
        industry = Industry(ev["observed"]["most_impacted_industry"])
        shocks = [ShockSpec(**s) for s in ev["shocks"]]
        p = linear_diffusion_predict(graph, shocks, industry, ev["horizon_weeks"])
        pred[i] = p.industry_loss
        obs[i] = ev["observed"].get("auto_production_loss_pct", 0.0)
    # No pass50 from the baseline; compute simple tolerance check
    errs = np.abs(pred - obs)
    tol = np.maximum(0.06, 0.50 * obs)
    pass50 = errs <= tol
    return {"pred": pred, "obs": obs, "pass50": pass50}


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 2 or np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    a = a - a.mean(); b = b - b.mean()
    denom = float(np.sqrt((a @ a) * (b @ b)))
    return float((a @ b) / denom) if denom > 0 else float("nan")


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra = np.argsort(np.argsort(a)).astype(np.float64)
    rb = np.argsort(np.argsort(b)).astype(np.float64)
    return _pearson(ra, rb)


def _row_from(name: str, desc: str, pred: np.ndarray, obs: np.ndarray,
              pass50: np.ndarray, full_mae: float, full_pearson: float) -> AblationRow:
    mae = float(np.abs(pred - obs).mean())
    rmse = float(np.sqrt(((pred - obs) ** 2).mean()))
    pr = _pearson(pred, obs)
    sp = _spearman(pred, obs)
    return AblationRow(
        variant=name, description=desc,
        mae_loss=round(mae, 4),
        rmse_loss=round(rmse, 4),
        pearson_loss=round(pr, 4) if not np.isnan(pr) else 0.0,
        spearman_loss=round(sp, 4) if not np.isnan(sp) else 0.0,
        pass_rate_50pct=round(float(pass50.mean()), 4),
        mae_delta_vs_full=round(mae - full_mae, 4),
        pearson_delta_vs_full=round((pr - full_pearson) if not np.isnan(pr) else 0.0, 4),
    )


# ─────────────────────────── runner ────────────────────────────────────────


def run_ablation_study() -> AblationReport:
    snapshot = load_graph()
    graph = compile_graph(snapshot)

    # Run the full model first to compute deltas.
    variants = _variants()
    full_eval = _eval_engine(variants[0][2], graph)
    full_mae = float(np.abs(full_eval["pred"] - full_eval["obs"]).mean())
    full_pr  = _pearson(full_eval["pred"], full_eval["obs"])

    rows: list[AblationRow] = []
    for name, desc, cfg in variants:
        ev = _eval_engine(cfg, graph)
        rows.append(_row_from(name, desc, ev["pred"], ev["obs"], ev["pass50"],
                              full_mae, full_pr))

    # Add the linear-diffusion baseline as a final row.
    ev = _eval_linear_diffusion(graph)
    rows.append(_row_from("naive_diffusion",
                          "Pure linear-diffusion baseline (no SEIRS, no bullwhip)",
                          ev["pred"], ev["obs"], ev["pass50"], full_mae, full_pr))

    # Pick winner (lowest MAE) and loser (highest MAE).
    best = min(rows, key=lambda r: r.mae_loss).variant
    worst = max(rows, key=lambda r: r.mae_loss).variant

    return AblationReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        n_events=len(HISTORICAL_EVENTS),
        rows=rows,
        best_variant=best,
        worst_variant=worst,
    )


# ─────────────────────────── persistence ───────────────────────────────────


def save_ablation(report: AblationReport, path: Path | None = None) -> Path:
    if path is None:
        path = Path(__file__).parent.parent.parent / "data" / "calibration" / "ablation.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": report.timestamp,
        "n_events": report.n_events,
        "rows": [asdict(r) for r in report.rows],
        "best_variant": report.best_variant,
        "worst_variant": report.worst_variant,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


__all__ = ["AblationRow", "AblationReport", "run_ablation_study", "save_ablation"]
