"""Isotonic post-calibration layer.

Background
----------
The audit (on the original N=8 event set) found:
    Pearson(pred, obs)   = 0.72
    Spearman(pred, obs)  = 0.83
    pass rate ±25%       = 0/8

(On the expanded N=21 set those correlations dropped sharply -- see
reports/benchmark/summary.md -- so monotone post-calibration helps less:
isotonic regression preserves rank order, and can only help to the extent
the ranks are right.)

The Spearman correlation > Pearson tells us the model is **rank-correct**
but **magnitude-wrong**: when the engine says event A is worse than event B,
A really is worse than B (in 83% of pair rankings).  We just predict the
*wrong magnitude*.

The standard fix is isotonic regression — a monotone calibration mapping
g: predicted_severity → calibrated_severity, fit on out-of-sample (predicted,
observed) pairs, that preserves rank ordering while warping magnitudes
toward the observed scale.  This is the same technique used in:
    - probabilistic forecasting (Niculescu-Mizil & Caruana, ICML 2005)
    - sklearn.isotonic.IsotonicRegression
    - the "Platt scaling" alternative for SVM probability outputs

API
---
    fit_isotonic(predicted, observed) -> CalibrationModel
    CalibrationModel.transform(predicted) -> calibrated
    CalibrationModel.evaluate(predicted, observed) -> CalibrationReport

Cross-validation
----------------
Critical: fit on N−1 events, evaluate on the held-out one, rotate.  Otherwise
the calibration is in-sample and meaningless.  loo_calibration_report() does this.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

try:
    from sklearn.isotonic import IsotonicRegression
    _SKLEARN_OK = True
except ImportError:
    IsotonicRegression = None
    _SKLEARN_OK = False


# ─────────────────────────── data classes ──────────────────────────────────


@dataclass
class CalibrationReport:
    method: str
    n_samples: int
    pearson_before: float
    pearson_after: float
    spearman_before: float
    spearman_after: float
    mae_before: float
    mae_after: float
    rmse_before: float
    rmse_after: float
    pass_rate_25pct_before: float
    pass_rate_25pct_after: float


@dataclass
class IsotonicModelSpec:
    """Serialized form of a fitted isotonic regression."""
    x_thresholds: list[float]
    y_thresholds: list[float]


# ─────────────────────────── core fits ─────────────────────────────────────


class CalibrationModel:
    """Wraps an isotonic mapping with fit/transform/save/load."""

    def __init__(self, regressor: "IsotonicRegression | None" = None) -> None:
        if not _SKLEARN_OK:
            raise ImportError("sklearn is required for isotonic post-calibration")
        self.reg = regressor or IsotonicRegression(
            out_of_bounds="clip", increasing=True, y_min=0.0, y_max=1.0,
        )
        self._fitted = regressor is not None

    @classmethod
    def fit(cls, predicted: np.ndarray, observed: np.ndarray) -> "CalibrationModel":
        m = cls()
        m.reg.fit(np.asarray(predicted, dtype=np.float64),
                  np.asarray(observed, dtype=np.float64))
        m._fitted = True
        return m

    def transform(self, predicted: np.ndarray | float) -> np.ndarray | float:
        if not self._fitted:
            raise RuntimeError("CalibrationModel not fitted")
        x = np.asarray(predicted, dtype=np.float64).ravel()
        y = self.reg.predict(x)
        return float(y[0]) if y.size == 1 else y

    # ── persistence ────────────────────────────────────────────────
    def to_spec(self) -> IsotonicModelSpec:
        if not self._fitted:
            raise RuntimeError("Cannot serialize unfitted model")
        return IsotonicModelSpec(
            x_thresholds=self.reg.X_thresholds_.tolist(),
            y_thresholds=self.reg.y_thresholds_.tolist(),
        )

    @classmethod
    def from_spec(cls, spec: IsotonicModelSpec) -> "CalibrationModel":
        reg = IsotonicRegression(out_of_bounds="clip", increasing=True, y_min=0.0, y_max=1.0)
        reg.X_thresholds_ = np.asarray(spec.x_thresholds, dtype=np.float64)
        reg.y_thresholds_ = np.asarray(spec.y_thresholds, dtype=np.float64)
        reg.X_min_ = float(reg.X_thresholds_.min())
        reg.X_max_ = float(reg.X_thresholds_.max())
        reg.increasing_ = True
        from scipy.interpolate import interp1d
        reg.f_ = interp1d(
            reg.X_thresholds_, reg.y_thresholds_,
            kind="linear", copy=False, bounds_error=False,
            fill_value=(reg.y_thresholds_[0], reg.y_thresholds_[-1]),
        )
        model = cls(regressor=reg)
        model._fitted = True
        return model


# ─────────────────────────── leave-one-out evaluation ──────────────────────


def loo_calibration_report() -> CalibrationReport:
    """Honest out-of-sample calibration evaluation.

    For each held-out event:
        1. Fit isotonic on the other 7 (pred → obs)
        2. Apply mapping to the held-out predicted value
        3. Record (raw_pred, calibrated_pred, observed) tuple
    Then aggregate metrics before/after across all events.

    This is the standard textbook way to evaluate post-calibration:
    in-sample evaluation would be cheating since isotonic can perfectly
    fit any monotone training set.
    """
    if not _SKLEARN_OK:
        raise ImportError("sklearn required")

    # Import here so loading this module without running CV is cheap.
    from .backtest import backtest_event
    from .graph import compile_graph
    from .types import EngineConfig
    from ..data.seed import load_graph
    from ..data.seed_data import HISTORICAL_EVENTS

    snapshot = load_graph()
    graph = compile_graph(snapshot)
    cfg = EngineConfig()

    # Compute raw predictions for all events once.
    raw_pred = np.zeros(len(HISTORICAL_EVENTS))
    observed = np.zeros(len(HISTORICAL_EVENTS))
    for i, ev in enumerate(HISTORICAL_EVENTS):
        r = backtest_event(ev, graph, cfg)
        raw_pred[i] = r.industry_loss_predicted
        observed[i] = r.industry_loss_observed

    # Leave-one-out calibration
    calibrated = np.zeros_like(raw_pred)
    for i in range(len(raw_pred)):
        mask = np.ones(len(raw_pred), dtype=bool)
        mask[i] = False
        if mask.sum() < 2:
            calibrated[i] = raw_pred[i]
            continue
        model = CalibrationModel.fit(raw_pred[mask], observed[mask])
        calibrated[i] = float(model.transform(raw_pred[i]))

    return _summarize_calibration(raw_pred, calibrated, observed, method="isotonic-LOO")


# ─────────────────────────── helpers ───────────────────────────────────────


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


def _pass_rate_25(pred: np.ndarray, obs: np.ndarray) -> float:
    errs = np.abs(pred - obs)
    tol = np.maximum(0.025, 0.25 * obs)
    return float((errs <= tol).mean())


def _summarize_calibration(raw: np.ndarray, cal: np.ndarray, obs: np.ndarray,
                           method: str) -> CalibrationReport:
    return CalibrationReport(
        method=method,
        n_samples=int(raw.size),
        pearson_before=round(_pearson(raw, obs), 4),
        pearson_after=round(_pearson(cal, obs), 4),
        spearman_before=round(_spearman(raw, obs), 4),
        spearman_after=round(_spearman(cal, obs), 4),
        mae_before=round(float(np.abs(raw - obs).mean()), 4),
        mae_after=round(float(np.abs(cal - obs).mean()), 4),
        rmse_before=round(float(np.sqrt(((raw - obs) ** 2).mean())), 4),
        rmse_after=round(float(np.sqrt(((cal - obs) ** 2).mean())), 4),
        pass_rate_25pct_before=round(_pass_rate_25(raw, obs), 4),
        pass_rate_25pct_after=round(_pass_rate_25(cal, obs), 4),
    )


# ─────────────────────────── persistence ───────────────────────────────────


def save_calibration(model: CalibrationModel, path: Path | None = None) -> Path:
    if path is None:
        path = Path(__file__).parent.parent.parent / "data" / "calibration" / "isotonic.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    spec = model.to_spec()
    path.write_text(json.dumps(asdict(spec), indent=2), encoding="utf-8")
    return path


def load_calibration(path: Path | None = None) -> CalibrationModel | None:
    if path is None:
        path = Path(__file__).parent.parent.parent / "data" / "calibration" / "isotonic.json"
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return CalibrationModel.from_spec(IsotonicModelSpec(**raw))


__all__ = [
    "CalibrationModel", "CalibrationReport", "IsotonicModelSpec",
    "loo_calibration_report", "save_calibration", "load_calibration",
]
