"use client";

import { useEffect, useState } from "react";

import { api, type CVReport } from "@/lib/api";
import { useUI } from "@/lib/ui-context";

interface Posterior {
  calibration_date: string;
  n_walkers: number;
  n_steps: number;
  n_effective_samples: number;
  acceptance_fraction_mean: number;
  r_hat_max: number;
  converged: boolean;
  parameters: Array<{
    name: string;
    mean: number; std: number; p05: number; p95: number;
    prior_low: number; prior_high: number; sensitivity: number;
  }>;
}

interface ResearchMetrics {
  systemic_fragility_index: number;
  recovery_elasticity_score: number;
  top_cascading_criticality_nodes: Array<{ node_id: string; ccs: number }>;
  economic_resilience_tensor_summary: {
    mean_resilience_at_4w: number;
    mean_resilience_at_12w: number;
    mean_resilience_at_52w: number;
    slowest_recovering_nodes: string[];
    fastest_recovering_nodes: string[];
  };
  shock_absorption_capacity_summary: {
    mean_sac: number; min_sac: number; max_sac: number;
    most_fragile_nodes: Array<{ node_id: string; sac: number }>;
    most_robust_nodes: Array<{ node_id: string; sac: number }>;
  };
  statistical_evaluation: Array<{
    metric_name: string;
    hypothesis: string;
    pearson: number;
    spearman: number;
    p_value_permutation: number;
    n_samples: number;
    effect_size_cohens_d: number;
    notes: string;
  }>;
}

interface CalibrationReport {
  method: string;
  n_samples: number;
  pearson_before: number; pearson_after: number;
  spearman_before: number; spearman_after: number;
  mae_before: number; mae_after: number;
  rmse_before: number; rmse_after: number;
  pass_rate_25pct_before: number; pass_rate_25pct_after: number;
}

interface AblationReport {
  timestamp: string;
  n_events: number;
  best_variant: string;
  worst_variant: string;
  rows: Array<{
    variant: string;
    description: string;
    mae_loss: number;
    rmse_loss: number;
    pearson_loss: number;
    spearman_loss: number;
    pass_rate_50pct: number;
    mae_delta_vs_full: number;
    pearson_delta_vs_full: number;
  }>;
}

interface BenchmarkReport {
  timestamp: string;
  n_events: number;
  winner_by_mae: string;
  winner_by_rmse: string;
  winner_by_r_squared: string;
  winner_by_pearson: string;
  models: Array<{
    model: string;
    n_events: number;
    mae: number;
    rmse: number;
    mape: number;
    r_squared: number;
    pearson: number;
    spearman: number;
    bias: number;
    skill_score_vs_persistence: number;
  }>;
}

export default function ValidationPage() {
  const { lang } = useUI();
  const [cv, setCv] = useState<CVReport | null>(null);
  const [posterior, setPosterior] = useState<Posterior | null>(null);
  const [research, setResearch] = useState<ResearchMetrics | null>(null);
  const [calibration, setCalibration] = useState<CalibrationReport | null>(null);
  const [ablation, setAblation] = useState<AblationReport | null>(null);
  const [bench, setBench] = useState<BenchmarkReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    Promise.allSettled([
      api.cvReport().then(setCv),
      fetch(`${API}/api/v1/posterior`).then(r => r.ok ? r.json() : null).then(setPosterior),
      fetch(`${API}/api/v1/research-metrics`).then(r => r.ok ? r.json() : null).then(setResearch),
      fetch(`${API}/api/v1/calibration-report`).then(r => r.ok ? r.json() : null).then(setCalibration),
      fetch(`${API}/api/v1/ablation`).then(r => r.ok ? r.json() : null).then(setAblation),
      fetch(`${API}/api/v1/benchmark`).then(r => r.ok ? r.json() : null).then(setBench),
    ]).catch((e) => setError(String(e)));
  }, []);

  const tr = (en: string, ru: string) => lang === "ru" ? ru : en;

  return (
    <main className="max-w-[1600px] mx-auto px-6 py-6 space-y-4">
      <div className="border-b border-border-subtle pb-3">
        <h1 className="text-2xl font-extrabold tracking-tight">
          <span className="text-accent-cyan">GEDS</span>
          <span className="text-text-secondary font-semibold text-sm uppercase tracking-[0.2em] ml-3">
            {tr("Validation Mode", "Режим валидации")}
          </span>
        </h1>
        <p className="text-xs text-text-muted mt-1 max-w-3xl leading-relaxed">
          {tr(
            "Live, computed validation metrics. Nothing on this page is hardcoded — every number is fetched from the running backend.",
            "Live-метрики валидации. Ни одно число на этой странице не хардкодировано — все значения берутся из работающего backend.",
          )}
        </p>
      </div>

      {error && <div className="text-xs text-sev-5">{error}</div>}

      {/* CV report */}
      <div className="panel p-4 space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
          {tr("Leave-one-out cross-validation", "LOO-кросс-валидация")}
        </h2>
        {cv ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <Cell label={tr("Events", "Событий")} value={String(cv.n_events)} />
            <Cell label="Pearson r" value={cv.pearson_loss.toFixed(3)} />
            <Cell label="Spearman ρ" value={cv.spearman_loss.toFixed(3)} />
            <Cell label="RMSE (norm.)" value={cv.rmse_normalized.toFixed(3)} />
            <Cell label={tr("Pass ±25%", "Точность ±25%")}
                  value={`${(cv.pass_rate_25pct * 100).toFixed(0)}% [${(cv.pass_rate_25pct_ci95_lo*100).toFixed(0)}–${(cv.pass_rate_25pct_ci95_hi*100).toFixed(0)}%]`} />
            <Cell label={tr("Pass ±50%", "Точность ±50%")}
                  value={`${(cv.pass_rate_50pct * 100).toFixed(0)}% [${(cv.pass_rate_50pct_ci95_lo*100).toFixed(0)}–${(cv.pass_rate_50pct_ci95_hi*100).toFixed(0)}%]`} />
            <Cell label={tr("MAE loss", "MAE потерь")} value={cv.mae_industry_loss.toFixed(3)} />
            <Cell label={tr("MAE recovery (w)", "MAE восст. (нед.)")} value={cv.mae_recovery_weeks.toFixed(1)} />
          </div>
        ) : <div className="text-xs text-text-muted">{tr("Loading…", "Загрузка…")}</div>}
      </div>

      {/* Isotonic calibration */}
      <div className="panel p-4 space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
          {tr("Isotonic post-calibration (LOO)", "Изотоническая пост-калибровка (LOO)")}
        </h2>
        {calibration ? (
          <table className="text-xs w-full">
            <thead>
              <tr className="text-text-muted uppercase text-[10px] tracking-widest">
                <th className="text-left py-1">{tr("metric", "метрика")}</th>
                <th className="text-right py-1">{tr("before", "до")}</th>
                <th className="text-right py-1">{tr("after", "после")}</th>
                <th className="text-right py-1">Δ</th>
              </tr>
            </thead>
            <tbody>
              <CalRow label="Pearson r"  b={calibration.pearson_before}  a={calibration.pearson_after} />
              <CalRow label="Spearman ρ" b={calibration.spearman_before} a={calibration.spearman_after} />
              <CalRow label="MAE"        b={calibration.mae_before}      a={calibration.mae_after} negativeGood />
              <CalRow label="RMSE"       b={calibration.rmse_before}     a={calibration.rmse_after} negativeGood />
              <CalRow label={tr("Pass ±25%", "Точность ±25%")}
                      b={calibration.pass_rate_25pct_before * 100}
                      a={calibration.pass_rate_25pct_after * 100}
                      suffix="%" />
            </tbody>
          </table>
        ) : <div className="text-xs text-text-muted">{tr("Loading…", "Загрузка…")}</div>}
      </div>

      {/* MCMC posterior */}
      <div className="panel p-4 space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
          {tr("MCMC posterior", "MCMC апостериор")}
        </h2>
        {posterior ? (
          <>
            <div className="text-[10px] text-text-muted">
              {posterior.n_walkers} {tr("walkers", "уокеров")} × {posterior.n_steps} {tr("steps", "шагов")} = {posterior.n_effective_samples} {tr("effective samples", "эффективных сэмплов")} ·
              accept={posterior.acceptance_fraction_mean.toFixed(2)} · R̂={posterior.r_hat_max.toFixed(2)} ·
              <span className={posterior.converged ? "text-accent-cyan ml-1" : "text-sev-4 ml-1"}>
                {posterior.converged ? "converged" : tr("not converged", "не сошёлся")}
              </span>
            </div>
            <table className="text-xs w-full">
              <thead>
                <tr className="text-text-muted uppercase text-[10px] tracking-widest">
                  <th className="text-left py-1">{tr("parameter", "параметр")}</th>
                  <th className="text-right py-1">mean</th>
                  <th className="text-right py-1">±std</th>
                  <th className="text-right py-1">p05</th>
                  <th className="text-right py-1">p95</th>
                  <th className="text-right py-1">{tr("sens.", "чувств.")}</th>
                </tr>
              </thead>
              <tbody>
                {posterior.parameters.map((p) => (
                  <tr key={p.name} className="border-t border-border-subtle/30">
                    <td className="py-1 num text-text-primary">{p.name}</td>
                    <td className="py-1 num text-right">{p.mean.toFixed(3)}</td>
                    <td className="py-1 num text-right text-text-muted">±{p.std.toFixed(3)}</td>
                    <td className="py-1 num text-right text-text-muted">{p.p05.toFixed(3)}</td>
                    <td className="py-1 num text-right text-text-muted">{p.p95.toFixed(3)}</td>
                    <td className="py-1 num text-right">{(p.sensitivity * 100).toFixed(0)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : (
          <div className="text-xs text-text-muted">
            {tr(
              "No posterior available. Run: python -m scripts.mcmc_calibrate --n-steps 600",
              "Апостериор не вычислен. Запустите: python -m scripts.mcmc_calibrate --n-steps 600",
            )}
          </div>
        )}
      </div>

      {/* Research metrics */}
      <div className="panel p-4 space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
          {tr("Novel research metrics", "Новые метрики (исследование)")}
        </h2>
        {research ? (
          <>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs">
              <Cell label="SFI" value={research.systemic_fragility_index.toFixed(4)} />
              <Cell label="RES" value={research.recovery_elasticity_score.toFixed(4)} />
              <Cell label={tr("Mean SAC", "Средний SAC")}
                    value={research.shock_absorption_capacity_summary.mean_sac.toFixed(3)} />
              <Cell label={tr("Resilience @ 4w",  "Устойчивость @ 4 нед.")}
                    value={research.economic_resilience_tensor_summary.mean_resilience_at_4w.toFixed(3)} />
              <Cell label={tr("Resilience @ 12w", "Устойчивость @ 12 нед.")}
                    value={research.economic_resilience_tensor_summary.mean_resilience_at_12w.toFixed(3)} />
              <Cell label={tr("Resilience @ 52w", "Устойчивость @ 52 нед.")}
                    value={research.economic_resilience_tensor_summary.mean_resilience_at_52w.toFixed(3)} />
            </div>

            <div>
              <div className="text-[10px] uppercase tracking-widest text-text-muted font-bold mb-1">
                {tr("Top cascading-criticality nodes", "Топ узлов по каскадной критичности")}
              </div>
              <div className="flex flex-wrap gap-1">
                {research.top_cascading_criticality_nodes.map((n) => (
                  <span key={n.node_id} className="text-[10px] px-2 py-0.5 rounded bg-bg-base/60 border border-border-subtle num">
                    {n.node_id} <span className="text-accent-cyan">{n.ccs.toFixed(3)}</span>
                  </span>
                ))}
              </div>
            </div>

            <div>
              <div className="text-[10px] uppercase tracking-widest text-text-muted font-bold mb-1">
                {tr("Most fragile nodes (low SAC)", "Самые хрупкие узлы (низкий SAC)")}
              </div>
              <div className="flex flex-wrap gap-1">
                {research.shock_absorption_capacity_summary.most_fragile_nodes.map((n) => (
                  <span key={n.node_id} className="text-[10px] px-2 py-0.5 rounded bg-sev-4/10 text-sev-4 border border-sev-4/30 num">
                    {n.node_id} <span>{n.sac.toFixed(3)}</span>
                  </span>
                ))}
              </div>
            </div>

            <div>
              <div className="text-[10px] uppercase tracking-widest text-text-muted font-bold mb-1">
                {tr("Statistical evaluation", "Статистическая оценка")}
              </div>
              <table className="text-xs w-full">
                <thead>
                  <tr className="text-text-muted uppercase text-[10px] tracking-widest">
                    <th className="text-left py-1">{tr("metric", "метрика")}</th>
                    <th className="text-right py-1">Pearson</th>
                    <th className="text-right py-1">Spearman</th>
                    <th className="text-right py-1">p-value</th>
                    <th className="text-right py-1">Cohen's d</th>
                    <th className="text-right py-1">n</th>
                  </tr>
                </thead>
                <tbody>
                  {research.statistical_evaluation.map((e, i) => (
                    <tr key={i} className="border-t border-border-subtle/30">
                      <td className="py-1 num text-text-primary text-[11px]">{e.metric_name}</td>
                      <td className="py-1 num text-right">{Number.isFinite(e.pearson) ? e.pearson.toFixed(3) : "—"}</td>
                      <td className="py-1 num text-right">{Number.isFinite(e.spearman) ? e.spearman.toFixed(3) : "—"}</td>
                      <td className={`py-1 num text-right ${e.p_value_permutation < 0.05 ? "text-accent-cyan font-bold" : ""}`}>
                        {Number.isFinite(e.p_value_permutation) ? e.p_value_permutation.toFixed(3) : "—"}
                      </td>
                      <td className="py-1 num text-right">{Number.isFinite(e.effect_size_cohens_d) ? e.effect_size_cohens_d.toFixed(2) : "—"}</td>
                      <td className="py-1 num text-right text-text-muted">{e.n_samples}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : <div className="text-xs text-text-muted">{tr("Loading…", "Загрузка…")}</div>}
      </div>

      {/* Benchmark leaderboard */}
      <div className="panel p-4 space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
          {tr("Model benchmark leaderboard", "Сравнение моделей (лидерборд)")}
        </h2>
        <p className="text-[10px] text-text-muted leading-relaxed">
          {tr(
            "All implemented propagation models vs the naive 'predict-the-mean' baseline.",
            "Все реализованные модели против наивного бейзлайна «всегда предсказывай среднее».",
          )}
        </p>
        {bench ? (
          <>
            <table className="text-xs w-full">
              <thead>
                <tr className="text-text-muted uppercase text-[10px] tracking-widest">
                  <th className="text-left py-1">model</th>
                  <th className="text-right py-1">MAE</th>
                  <th className="text-right py-1">RMSE</th>
                  <th className="text-right py-1">R²</th>
                  <th className="text-right py-1">Pearson</th>
                  <th className="text-right py-1">Skill</th>
                  <th className="text-right py-1">Bias</th>
                </tr>
              </thead>
              <tbody>
                {bench.models.map((m) => {
                  const isWinner = m.model === bench.winner_by_mae;
                  return (
                    <tr key={m.model} className={`border-t border-border-subtle/30 ${isWinner ? "bg-accent-cyan/5" : ""}`}>
                      <td className={`py-1 text-[11px] ${isWinner ? "text-accent-cyan font-bold" : "text-text-primary"}`}>
                        {isWinner && "★ "}{m.model}
                      </td>
                      <td className="py-1 num text-right">{m.mae.toFixed(4)}</td>
                      <td className="py-1 num text-right">{m.rmse.toFixed(4)}</td>
                      <td className={`py-1 num text-right ${m.r_squared >= 0 ? "" : "text-sev-5"}`}>
                        {m.r_squared >= 0 ? "+" : ""}{m.r_squared.toFixed(3)}
                      </td>
                      <td className="py-1 num text-right">{m.pearson >= 0 ? "+" : ""}{m.pearson.toFixed(3)}</td>
                      <td className={`py-1 num text-right ${m.skill_score_vs_persistence >= 0 ? "text-accent-cyan" : "text-sev-5"}`}>
                        {m.skill_score_vs_persistence >= 0 ? "+" : ""}{m.skill_score_vs_persistence.toFixed(3)}
                      </td>
                      <td className="py-1 num text-right text-text-muted">{m.bias >= 0 ? "+" : ""}{m.bias.toFixed(4)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div className="text-[10px] text-text-muted pt-1">
              {tr("Winner (MAE):", "Победитель (MAE):")} <span className="text-accent-cyan font-bold">{bench.winner_by_mae}</span>
              &nbsp;·&nbsp;
              {tr("Skill > 0 means the model beats predicting the mean.", "Skill > 0 — модель побеждает наивный бейзлайн.")}
            </div>
          </>
        ) : <div className="text-xs text-text-muted">{tr("Loading…", "Загрузка…")}</div>}
      </div>

      {/* Ablation */}
      <div className="panel p-4 space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
          {tr("Component-wise ablation", "Покомпонентная аблация")}
        </h2>
        <p className="text-[10px] text-text-muted leading-relaxed">
          {tr(
            "Each row disables one engine component. Components whose deletion doesn't hurt performance are dead weight.",
            "Каждая строка отключает один компонент движка. Компоненты, чьё удаление не ухудшает результат, — балласт.",
          )}
        </p>
        {ablation ? (
          <table className="text-xs w-full">
            <thead>
              <tr className="text-text-muted uppercase text-[10px] tracking-widest">
                <th className="text-left py-1">variant</th>
                <th className="text-right py-1">MAE</th>
                <th className="text-right py-1">Pearson</th>
                <th className="text-right py-1">Δ MAE</th>
                <th className="text-right py-1">Δ Pearson</th>
                <th className="text-right py-1">pass50</th>
              </tr>
            </thead>
            <tbody>
              {ablation.rows.map((r) => (
                <tr key={r.variant} className="border-t border-border-subtle/30">
                  <td className="py-1 text-[11px] text-text-primary">
                    {r.variant === "full" && "★ "}{r.variant}
                    <span className="text-text-muted ml-2 text-[10px]">{r.description}</span>
                  </td>
                  <td className="py-1 num text-right">{r.mae_loss.toFixed(4)}</td>
                  <td className="py-1 num text-right">{r.pearson_loss >= 0 ? "+" : ""}{r.pearson_loss.toFixed(3)}</td>
                  <td className={`py-1 num text-right ${r.mae_delta_vs_full > 0 ? "text-sev-5" : r.mae_delta_vs_full < 0 ? "text-accent-cyan" : "text-text-muted"}`}>
                    {r.mae_delta_vs_full >= 0 ? "+" : ""}{r.mae_delta_vs_full.toFixed(4)}
                  </td>
                  <td className={`py-1 num text-right ${r.pearson_delta_vs_full < 0 ? "text-sev-5" : r.pearson_delta_vs_full > 0 ? "text-accent-cyan" : "text-text-muted"}`}>
                    {r.pearson_delta_vs_full >= 0 ? "+" : ""}{r.pearson_delta_vs_full.toFixed(3)}
                  </td>
                  <td className="py-1 num text-right">{(r.pass_rate_50pct * 100).toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <div className="text-xs text-text-muted">{tr("Loading…", "Загрузка…")}</div>}
      </div>

      <footer className="text-[10px] text-text-muted pt-3 border-t border-border-subtle">
        {tr(
          "Endpoints: /cv-report · /posterior · /research-metrics · /calibration-report · /tail-risk · /backtest · /ablation · /benchmark · /sobol-sensitivity (run as script)",
          "Эндпоинты: /cv-report · /posterior · /research-metrics · /calibration-report · /tail-risk · /backtest · /ablation · /benchmark · /sobol-sensitivity (через скрипт)",
        )}
      </footer>
    </main>
  );
}

function Cell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-border-subtle bg-bg-base/30 p-2">
      <div className="text-[9px] uppercase tracking-widest text-text-muted font-bold">{label}</div>
      <div className="num text-text-primary text-sm mt-0.5">{value}</div>
    </div>
  );
}

function CalRow({ label, b, a, suffix = "", negativeGood = false }: {
  label: string; b: number; a: number; suffix?: string; negativeGood?: boolean;
}) {
  const delta = a - b;
  const improved = negativeGood ? delta < 0 : delta > 0;
  return (
    <tr className="border-t border-border-subtle/30">
      <td className="py-1 num text-text-primary">{label}</td>
      <td className="py-1 num text-right text-text-muted">{b.toFixed(3)}{suffix}</td>
      <td className={`py-1 num text-right ${improved ? "text-accent-cyan font-bold" : "text-sev-4"}`}>
        {a.toFixed(3)}{suffix}
      </td>
      <td className={`py-1 num text-right ${improved ? "text-accent-cyan" : "text-sev-4"}`}>
        {delta >= 0 ? "+" : ""}{delta.toFixed(3)}{suffix}
      </td>
    </tr>
  );
}
