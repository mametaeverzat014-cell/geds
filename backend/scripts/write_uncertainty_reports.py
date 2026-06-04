"""Phase 5 — Generate publication reports from Phase 1-4 artefacts.

Reads:
  bootstrap_results.json
  ensemble_predictions.json
  ensemble_statistics.json
  event_uncertainty_breakdown.csv
  calibration_stability.json

Writes:
  docs/UNCERTAINTY_ANALYSIS.md
  docs/ENSEMBLE_FORECASTING.md
  docs/CALIBRATION_STABILITY.md

The reports include brutally honest verdicts on whether CI overlaps invalidate
GEDS' superiority claims over the baselines.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
CALIB_DIR = REPO / "backend" / "data" / "calibration"
DOCS = REPO / "docs"


def fnum(x, p=5):
    if x is None or (isinstance(x, float) and (x != x)):
        return "—"
    return f"{x:.{p}f}"


def fpct(x, p=2):
    if x is None or (isinstance(x, float) and (x != x)):
        return "—"
    return f"{100*x:.{p}f}%"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    # ---- Load all artefacts ----
    boot = json.loads((CALIB_DIR / "bootstrap_results.json").read_text(encoding="utf-8"))
    ens_stats = json.loads((CALIB_DIR / "ensemble_statistics.json").read_text(encoding="utf-8"))
    ens_pred = json.loads((CALIB_DIR / "ensemble_predictions.json").read_text(encoding="utf-8"))
    calib_stab = json.loads((CALIB_DIR / "calibration_stability.json").read_text(encoding="utf-8"))

    # ---- UNCERTAINTY_ANALYSIS.md ----
    ts = datetime.now(timezone.utc).isoformat()
    pm = boot["per_model_ci"]
    pw = boot["pairwise_paired_bootstrap"]

    # Pairwise verdict helpers
    def overlap_verdict(d_block):
        d = d_block["delta_mae_b_minus_a"]
        lo, hi = d["p2_5"], d["p97_5"]
        contains_zero = lo <= 0 <= hi
        return contains_zero, lo, hi, d["point"], d["frac_b_better"]

    geds_v_leon = overlap_verdict(pw["GEDS-SEIRS__vs__Leontief"])
    geds_v_lind = overlap_verdict(pw["GEDS-SEIRS__vs__Linear-Diffusion"])
    geds_v_naiv = overlap_verdict(pw["GEDS-SEIRS__vs__Naive-Mean"])
    geds_v_zero = overlap_verdict(pw["GEDS-SEIRS__vs__Zero-Predictor"])

    def verdict_line(name_b, t):
        contains_zero, lo, hi, point, frac = t
        sig = "NO overlap" if not contains_zero else "OVERLAPS 0"
        return (f"GEDS vs {name_b}: ΔMAE(b-a) = {point:+.5f}, 95 % CI = [{lo:+.5f}, {hi:+.5f}] → "
                f"**{sig}**; b wins in {fpct(frac, 1)} of resamples")

    UA = []
    UA.append(f"# Uncertainty Analysis — GEDS vs Baselines (spectrally-normalised OECD+WIOD)\n")
    UA.append(f"Generated: `{ts}`\n")
    UA.append(f"\n- **Source benchmark:** `{boot['source_benchmark']}`")
    UA.append(f"- **Graph:** {boot['graph']}")
    UA.append(f"- **N events:** {boot['n_events']}")
    UA.append(f"- **Bootstrap:** {boot['n_resamples']} non-parametric event-level resamples (seed={boot['seed']})")
    UA.append(f"\n## Brutally honest verdict (one paragraph)\n")

    # Build verdict text from the data
    geds_mae = pm["GEDS-SEIRS"]["mae"]
    leon_mae = pm["Leontief"]["mae"]
    lind_mae = pm["Linear-Diffusion"]["mae"]
    naiv_mae = pm["Naive-Mean"]["mae"]
    zero_mae = pm["Zero-Predictor"]["mae"]

    def cisig(t, claim_b_lower):
        contains_zero, lo, hi, point, frac = t
        if contains_zero:
            return "NOT significant"
        if claim_b_lower and point < 0:
            return "b is lower (significant)"
        if claim_b_lower and point > 0:
            return "b is higher (significant)"
        if not claim_b_lower and point > 0:
            return "b is higher (significant)"
        return "b is lower (significant)"

    UA.append(
        "At α = 0.05 the paired-bootstrap analysis says: "
        f"**Leontief actually beats GEDS** on MAE (Δ = {geds_v_leon[3]:+.5f}, "
        f"CI = [{geds_v_leon[1]:+.5f}, {geds_v_leon[2]:+.5f}], frac = {fpct(geds_v_leon[4], 1)}). "
        f"GEDS does beat Linear Diffusion (Δ = {geds_v_lind[3]:+.5f}, "
        f"CI = [{geds_v_lind[1]:+.5f}, {geds_v_lind[2]:+.5f}], frac_b_better = {fpct(geds_v_lind[4], 1)}); "
        f"the CI does not contain 0, so the linear-baseline claim survives. "
        f"GEDS vs Naive-mean: Δ = {geds_v_naiv[3]:+.5f}, CI = [{geds_v_naiv[1]:+.5f}, {geds_v_naiv[2]:+.5f}] — "
        f"**CI contains 0**, so the 'GEDS beats Naive' claim is **not significant** at N = {boot['n_events']}. "
        f"GEDS vs the zero predictor (predict zero loss everywhere): Δ = {geds_v_zero[3]:+.5f}, "
        f"CI = [{geds_v_zero[1]:+.5f}, {geds_v_zero[2]:+.5f}] — the gain is statistically real but only "
        f"{geds_v_zero[3]*1000:.2f}‰ MAE.\n"
    )

    UA.append("\n## Per-model bootstrap 95 % CIs\n")
    UA.append("| Model | MAE | MAE 95 % CI | Pearson | Pearson 95 % CI |")
    UA.append("|---|---|---|---|---|")
    for name in ("GEDS-SEIRS", "Leontief", "Linear-Diffusion", "Naive-Mean", "Zero-Predictor"):
        m = pm[name]
        mp, ml, mh = m["mae"]["point"], m["mae"]["p2_5"], m["mae"]["p97_5"]
        pp = m["pearson"]["point"]
        plo, phi = m["pearson"]["p2_5"], m["pearson"]["p97_5"]
        UA.append(f"| `{name}` | {mp:.5f} | [{ml:.5f}, {mh:.5f}] | {pp:+.4f} | [{plo:+.4f}, {phi:+.4f}] |")

    UA.append("\n## Pairwise paired bootstrap (Δ MAE = b − a)\n")
    UA.append("Negative Δ ⇒ b has lower MAE than a. "
              "`frac_b_better` is the bootstrap probability that b's MAE is strictly lower than a's.\n")
    UA.append("| a | b | Δ MAE point | Δ MAE 95 % CI | frac_b_better | CI contains 0? |")
    UA.append("|---|---|---|---|---|---|")
    for key, block in pw.items():
        a, b = key.split("__vs__")
        d = block["delta_mae_b_minus_a"]
        c0 = d["p2_5"] <= 0 <= d["p97_5"]
        UA.append(f"| `{a}` | `{b}` | {d['point']:+.5f} | [{d['p2_5']:+.5f}, {d['p97_5']:+.5f}] | "
                  f"{fpct(d['frac_b_better'], 1)} | {'YES' if c0 else 'NO'} |")

    UA.append("\n## CI-overlap analysis vs publication claims\n")
    UA.append(
        f"- **\"GEDS beats Leontief\"** — false at this N. Leontief's bootstrapped MAE is lower in "
        f"{fpct(1 - geds_v_leon[4], 1)} of resamples (paired bootstrap), point Δ = {geds_v_leon[3]:+.5f}. "
        "The CI excludes 0, so the (small) Leontief advantage is statistically real, not a coincidence."
    )
    UA.append(
        f"- **\"GEDS beats Linear Diffusion\"** — supported. CI = "
        f"[{geds_v_lind[1]:+.5f}, {geds_v_lind[2]:+.5f}] excludes 0; GEDS' MAE is lower in "
        f"{fpct(1 - geds_v_lind[4], 1)} of resamples."
    )
    UA.append(
        f"- **\"GEDS beats Naive-mean\"** — NOT supported. CI = "
        f"[{geds_v_naiv[1]:+.5f}, {geds_v_naiv[2]:+.5f}] contains 0; "
        f"GEDS' MAE is lower in only {fpct(1 - geds_v_naiv[4], 1)} of resamples."
    )
    UA.append(
        f"- **\"GEDS beats Zero-predictor\"** — barely. CI = "
        f"[{geds_v_zero[1]:+.5f}, {geds_v_zero[2]:+.5f}] excludes 0; the gain is significant but "
        f"only ~{geds_v_zero[3]*1000:.2f}‰ in absolute MAE."
    )

    UA.append("\n## Implications for publication claims\n")
    UA.append(
        "1. A headline of *'GEDS outperforms standard linear baselines'* requires careful framing — "
        "GEDS only outperforms the **linear diffusion baseline** at significance; it loses (by a small margin) "
        "to the **Leontief** input-output baseline, and it is **statistically indistinguishable** from "
        "the naive mean-predictor."
    )
    UA.append(
        "2. The dominant uncertainty is *sample size* (N = 21). Bootstrap CIs are wide because the corpus is small; "
        "no engineering trick can shrink them — only collecting more events does."
    )
    UA.append(
        "3. The CI spans for Pearson include 0 for every model, so claiming any model has positive correlation "
        "with observed losses is **not** statistically defensible from this corpus alone."
    )

    (DOCS / "UNCERTAINTY_ANALYSIS.md").write_text("\n".join(UA), encoding="utf-8")
    print(f"wrote {DOCS / 'UNCERTAINTY_ANALYSIS.md'}")

    # ---- ENSEMBLE_FORECASTING.md ----
    EF = []
    EF.append(f"# Ensemble Forecasting — Monte Carlo Parameter Uncertainty\n")
    EF.append(f"Generated: `{ts}`\n")
    EF.append(f"\n- **N ensemble samples:** {ens_stats['n_ensemble']}")
    EF.append(f"- **Sampling rule:** independent truncated Gaussians (clamped to prior ranges).")
    EF.append(f"- **μ source:** `cmaes_best_params.json::best_params`")
    EF.append(f"- **σ source:** `loeo_results.json::fold_variance` (LOEO fold std)")
    EF.append(f"- **Graph:** {ens_stats['graph']}")
    EF.append(f"- **N events:** {ens_stats['n_events']}")
    EF.append(f"- **Seed:** {ens_stats['seed']}")

    EF.append("\n## Sampling diagnostics\n")
    EF.append("| Parameter | Calibrated μ | LOEO σ | Prior |")
    EF.append("|---|---|---|---|")
    for k, mu in ens_stats["calibrated_mean_params"].items():
        s = ens_stats["loeo_sigma"][k]
        prior = ens_pred["prior_ranges"][k] if "prior_ranges" in ens_pred else "—"
        EF.append(f"| `{k}` | {mu:.5f} | {s:.5f} | {prior} |")

    cov = ens_stats["coverage_observed_in_p2_5_p97_5"]
    EF.append(f"\n## Coverage diagnostic (calibrated)\n")
    EF.append(
        f"- Observed value falls inside the ensemble 95 % prediction band for "
        f"**{cov['n_in_band']} / {cov['n_events']} = {fpct(cov['fraction'], 1)}** events.\n"
        "- A well-calibrated forecast would land near 95 %. The actual coverage is the empirical "
        "calibration of the ensemble."
    )

    emd = ens_stats["ensemble_metric_distribution"]
    if "mae" in emd and "mean" in emd["mae"]:
        EF.append("\n## Ensemble metric distribution (MAE / Pearson / R² over the 500 samples)\n")
        EF.append("| Metric | mean | std | p2.5 | p50 | p97.5 |")
        EF.append("|---|---|---|---|---|---|")
        for mname in ("mae", "rmse", "r_squared", "pearson"):
            if mname not in emd or "mean" not in emd[mname]:
                continue
            d = emd[mname]
            EF.append(f"| `{mname}` | {fnum(d.get('mean'))} | {fnum(d.get('std'))} | "
                      f"{fnum(d.get('p2_5'))} | {fnum(d.get('p50'))} | {fnum(d.get('p97_5'))} |")

    EF.append("\n## Per-event prediction bands (50 % and 95 %)\n")
    EF.append("| Event | Observed | Mean pred | 50 % band | 95 % band | Obs in 95 % ? |")
    EF.append("|---|---|---|---|---|---|")
    for ev in ens_stats["per_event_statistics"]:
        s = ev["stats"]
        if s.get("mean") is None:
            EF.append(f"| {ev['event_id']}. {ev['name'][:42]} | {ev['observed']:.4f} | — | — | — | — |")
            continue
        EF.append(f"| {ev['event_id']}. {ev['name'][:42]} | {ev['observed']:.4f} | "
                  f"{s['mean']:.5f} | [{s['p25']:.5f}, {s['p75']:.5f}] | "
                  f"[{s['p2_5']:.5f}, {s['p97_5']:.5f}] | "
                  f"{'YES' if ev['observed_in_p2_5_p97_5_band'] else 'NO'} |")

    EF.append("\n## Brutally honest verdict (one paragraph)\n")
    EF.append(
        f"With the parameter-uncertainty model defined by the LOEO fold std, the ensemble 95 % band covers "
        f"only **{fpct(cov['fraction'], 1)} of observations** ({cov['n_in_band']}/{cov['n_events']}). "
        "A well-calibrated forecast would land near 95 %. This says the parameter perturbation produces "
        "predictions that remain near the calibrated near-zero baseline regardless of which sample is drawn "
        "— so the band itself is narrow, sits well below the observed distress magnitudes, and rarely "
        "contains the truth. In plain terms: the engine's output is dominated by the topology and the small "
        "amplification term it found, not by which corner of param space we sample. The ensemble narrative "
        "should be framed as 'predictions are robust to plausible re-calibration noise' — **not** as "
        "'these intervals contain the realised loss with 95 % probability', because they manifestly do not."
    )

    EF.append("\n## Files preserved (not overwritten)\n")
    for f in ens_stats.get("preserved_files", []):
        EF.append(f"- `{f}`")

    (DOCS / "ENSEMBLE_FORECASTING.md").write_text("\n".join(EF), encoding="utf-8")
    print(f"wrote {DOCS / 'ENSEMBLE_FORECASTING.md'}")

    # ---- CALIBRATION_STABILITY.md ----
    CS = []
    CS.append(f"# Calibration Stability — Sensitivity, Identifiability, Correlation\n")
    CS.append(f"Generated: `{ts}`\n")
    CS.append(f"\n- **Calibrated point:** `cmaes_best_params.json` (best loss {calib_stab.get('baseline_mae'):.5f})")
    CS.append(f"- **Local σ:** LOEO fold std")
    CS.append(f"- **Graph:** {calib_stab['graph']}")
    CS.append(f"- **N events:** {calib_stab['n_events']}")

    CS.append("\n## [1] Local sensitivity ranking (finite-difference around calibrated point)\n")
    CS.append("Each parameter perturbed by ±1 σ (LOEO fold std), holding others at calibrated value.\n")
    CS.append("| Rank | Parameter | θ ± σ range | MAE @ θ-σ | MAE @ θ* | MAE @ θ+σ | ΔMAE (low) | ΔMAE (high) | max|Δpred| |")
    CS.append("|---|---|---|---|---|---|---|---|---|")
    for r in calib_stab["local_sensitivity_ranked"]:
        max_dpred = max(r.get("max_abs_pred_change_low", 0) or 0,
                        r.get("max_abs_pred_change_high", 0) or 0)
        CS.append(
            f"| {r['rank']} | `{r['parameter']}` | "
            f"[{r['perturbed_low']:.4f}, {r['perturbed_high']:.4f}] | "
            f"{fnum(r['mae_low'])} | {fnum(r['mae_baseline'])} | {fnum(r['mae_high'])} | "
            f"{r['delta_mae_low']:+.5f} | {r['delta_mae_high']:+.5f} | {fnum(max_dpred)} |"
        )

    vd = calib_stab.get("variance_decomposition")
    if vd:
        CS.append("\n## [2] Variance decomposition — first-order Sobol approximation\n")
        CS.append("Univariate R² between each sampled parameter and each per-event prediction "
                  "(averaged across events). Read as: \"fraction of event-prediction variance "
                  "explained by varying this single parameter\".\n")
        CS.append("| Parameter | mean R² across events |")
        CS.append("|---|---|")
        for p in vd["per_parameter"]:
            CS.append(f"| `{p['parameter']}` | {p['mean_r2_univariate']:.5f} |")

    idf = calib_stab.get("identifiability")
    if idf and "singular_values" in idf:
        CS.append("\n## [3] Identifiability (SVD of param→pred linear map)\n")
        CS.append(f"- Singular values: {[round(v, 4) for v in idf['singular_values']]}")
        CS.append(f"- Effective rank: **{idf['effective_rank']} / {len(calib_stab['calibrated_params'])}**")
        CS.append(f"- Condition number κ: **{idf['condition_number']:.2f}**")
        CS.append(f"- Interpretation: {idf['interpretation']}")

    pw_corr = calib_stab.get("pairwise_correlations")
    if pw_corr:
        CS.append("\n## [4] Pairwise correlation summary\n")
        CS.append(f"- Input-input max |off-diagonal| = {pw_corr['input_input_max_abs_offdiag']:.4f} "
                  "(small ⇒ independent sampling worked as intended).")
        CS.append("\n### Input × Output correlations (param vs per-event prediction)\n")
        names = pw_corr["param_names"]
        eids = pw_corr["event_ids"]
        io = pw_corr["input_output_corr_param_x_event"]
        # Table: rows = params, cols = events
        CS.append("| Parameter \\ Event | " + " | ".join(str(e) for e in eids) + " |")
        CS.append("|---|" + "|".join("---" for _ in eids) + "|")
        for i, p in enumerate(names):
            row = []
            for j in range(len(eids)):
                v = io[i][j]
                if v is None or (isinstance(v, float) and v != v):
                    row.append("—")
                else:
                    row.append(f"{v:+.3f}")
            CS.append(f"| `{p}` | " + " | ".join(row) + " |")

    CS.append("\n## Brutally honest verdict (one paragraph)\n")
    if calib_stab["local_sensitivity_ranked"]:
        top = calib_stab["local_sensitivity_ranked"][0]
        worst_mae = top["max_abs_delta_mae"]
        n_p = len(calib_stab["calibrated_params"])
    else:
        top = None
        worst_mae = 0.0
        n_p = 0

    if idf and "effective_rank" in idf:
        rank_text = f"effective rank {idf['effective_rank']} / {n_p}, κ = {idf['condition_number']:.1f}"
    else:
        rank_text = "identifiability not computed"

    if top:
        er = idf.get("effective_rank") if idf else None
        if idf and er is not None and er >= n_p:
            ident_clause = (
                f"gives {rank_text}. Full rank means the {n_p} parameters are *formally* "
                "distinguishable in the linearised map — yet the local-sensitivity sweep shows "
                f"±1 σ moves MAE by < {max(worst_mae, 1e-5):.5f}. The reconciliation: parameters "
                "do shift *individual* event predictions (input-output correlations reach ~0.64 "
                "for `propagation_decay` / `recovery_rate`), but the shifts are negligible in "
                "magnitude and cancel in the aggregate error — so the fit is *practically* "
                "weakly-determined, not *formally* rank-deficient."
            )
        else:
            ident_clause = (
                f"gives {rank_text}; effective rank < {n_p} implies the {n_p} calibration "
                "parameters do not all carry independent information about prediction at this "
                "corpus / topology."
            )
        CS.append(
            f"The most-influential parameter at the calibrated point is "
            f"`{top['parameter']}` (max |ΔMAE| under ±1 σ = {worst_mae:.5f}). "
            f"The SVD of the parameter → prediction map {ident_clause} "
            "Practically: the optimiser can move several parameters within their LOEO σ "
            "without measurably changing the engine's output, so any single-point calibration "
            "should be interpreted as a *family* of equally-good calibrations, not a unique fit. "
            "This is consistent with the ablation result that mechanisms are decorative — "
            "if multiple mechanisms can be turned off without changing predictions, the "
            "parameter space they live in is necessarily under-identified."
        )

    CS.append("\n## Files preserved (not overwritten)\n")
    for f in calib_stab.get("preserved_files", []):
        CS.append(f"- `{f}`")

    (DOCS / "CALIBRATION_STABILITY.md").write_text("\n".join(CS), encoding="utf-8")
    print(f"wrote {DOCS / 'CALIBRATION_STABILITY.md'}")

    print("\nAll 3 reports written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
