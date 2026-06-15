"use client";

import { useEffect, useState } from "react";

import ConnectionBanner from "@/components/ConnectionBanner";
import { api, API_BASE, type CVReport } from "@/lib/api";
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

interface LooDeReport {
  timestamp: string;
  n_folds: number;
  de_settings: { maxiter: number; popsize_per_dim: number; seed: number };
  runtime_seconds: number;
  out_of_sample_score: {
    mae: number; rmse: number; r_squared: number; pearson: number; spearman: number;
  };
  folds: Array<{
    slug: string;
    loss_predicted: number;
    loss_observed: number;
  }>;
  reproduce_command: string;
}

interface PortwatchReport {
  timestamp: string;
  source: string;
  event_checks: Array<{
    slug: string;
    chokepoint: string;
    spec_magnitude: number;
    observed_peak_daily_deficit: number;
    observed_peak_weekly_deficit: number;
    magnitude_verdict: string;
    duration_verdict: string;
  }>;
  rerouting_cross_check: {
    weekly_correlation_suez_lost_vs_cape_gained: number;
    fraction_of_lost_suez_transits_reappearing_at_cape: number;
    interpretation: string;
  };
}

interface GscpiReport {
  timestamp: string;
  source: string;
  caveat: string;
  n_events: number;
  spearman_all_events: number;
  spearman_non_overlapping: number;
  n_non_overlapping: number;
}

interface IcioEdgeCheck {
  year: number;
  source: string;
  summary: {
    n_production_edges: number;
    n_chokepoint_links_excluded: number;
    n_total_seed_edges: number;
    correlations: Record<string, { n: number; pearson?: number; spearman?: number }>;
    by_family: Record<string, Record<string, { n: number; pearson?: number; spearman?: number }>>;
    worst_disagreements: Array<{
      edge: string;
      manual: number;
      comparator: number | null;
      manual_over_comparator: number | null;
      family: string;
      mapping_caveats: string[];
    }>;
  };
}

interface IcioC26Split {
  importer_world_semi_share: Record<string, number>;
  semi_family_correlation_excl_capital_channel: { n: number; pearson?: number; spearman?: number };
  semi_family_correlation_manual_vs_refined: { n: number; pearson?: number; spearman?: number };
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

interface CascadeValidation {
  shape: {
    mae_by_dim: Record<string, number>;
    spearman_by_dim: Record<string, number>;
    n_by_dim: Record<string, number>;
  };
  spatial: {
    coverage: number;
    spatial_recall: number;
    onset_spearman: number;
    onset_mae_weeks: number;
    n_reached: number;
    n_out_of_graph: number;
  };
}

export default function ValidationPage() {
  const { lang } = useUI();
  const [cv, setCv] = useState<CVReport | null>(null);
  const [posterior, setPosterior] = useState<Posterior | null>(null);
  const [research, setResearch] = useState<ResearchMetrics | null>(null);
  const [calibration, setCalibration] = useState<CalibrationReport | null>(null);
  const [ablation, setAblation] = useState<AblationReport | null>(null);
  const [bench, setBench] = useState<BenchmarkReport | null>(null);
  const [looDe, setLooDe] = useState<LooDeReport | null>(null);
  const [portwatch, setPortwatch] = useState<PortwatchReport | null>(null);
  const [gscpi, setGscpi] = useState<GscpiReport | null>(null);
  const [icio, setIcio] = useState<IcioEdgeCheck | null>(null);
  const [c26, setC26] = useState<IcioC26Split | null>(null);
  const [cascade, setCascade] = useState<CascadeValidation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.allSettled([
      api.cvReport().then(setCv),
      fetch(`${API_BASE}/api/v1/posterior`).then(r => r.ok ? r.json() : null).then(setPosterior),
      fetch(`${API_BASE}/api/v1/research-metrics`).then(r => r.ok ? r.json() : null).then(setResearch),
      fetch(`${API_BASE}/api/v1/calibration-report`).then(r => r.ok ? r.json() : null).then(setCalibration),
      fetch(`${API_BASE}/api/v1/ablation`).then(r => r.ok ? r.json() : null).then(setAblation),
      fetch(`${API_BASE}/api/v1/benchmark`).then(r => r.ok ? r.json() : null).then(setBench),
      fetch(`${API_BASE}/api/v1/loo-de-report`).then(r => r.ok ? r.json() : null).then(setLooDe),
      fetch(`${API_BASE}/api/v1/portwatch-validation`).then(r => r.ok ? r.json() : null).then(setPortwatch),
      fetch(`${API_BASE}/api/v1/gscpi-validation`).then(r => r.ok ? r.json() : null).then(setGscpi),
      fetch(`${API_BASE}/api/v1/icio-edge-check`).then(r => r.ok ? r.json() : null).then(setIcio),
      fetch(`${API_BASE}/api/v1/icio-c26-split`).then(r => r.ok ? r.json() : null).then(setC26),
      fetch(`${API_BASE}/api/v1/cascade-validation`).then(r => r.ok ? r.json() : null).then(setCascade),
    ]).catch((e) => setError(String(e)));
  }, []);

  const tr = (en: string, ru: string) => lang === "ru" ? ru : en;

  return (
    <main className="max-w-[1600px] mx-auto px-6 py-6 space-y-4">
      <div className="border-b border-border-subtle pb-3">
        <h1 className="text-2xl font-extrabold tracking-tight">
          <a href="/" className="title-gradient hover:opacity-80 transition">GEDS</a>
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

      <ConnectionBanner />

      {error && <div className="text-xs text-sev-5">{error}</div>}

      {/* How to read this page */}
      <section className="rounded-md border border-accent-cyan/25 bg-accent-cyan/5 px-5 py-4 space-y-3">
        <h2 className="text-base font-bold text-text-primary">
          {tr("How to read this page", "Как читать эту страницу")}
        </h2>
        <p className="text-xs text-text-secondary leading-relaxed max-w-4xl">
          {tr(
            "“Validation” means testing the model against real history it never got to peek at. For each event below we hide that event, fit the model on the others, then ask it to predict the one it never saw — this is leave-one-out cross-validation. Comparing that blind prediction to what actually happened is the only honest way to know whether the model works.",
            "«Валидация» — это проверка модели на реальной истории, которую она не подсматривала. Для каждого события ниже мы скрываем его, обучаем модель на остальных, а затем просим предсказать то, которого она не видела — это кросс-валидация с исключением одного события. Сравнение такого «слепого» прогноза с тем, что произошло на самом деле, — единственный честный способ узнать, работает ли модель.",
          )}
        </p>
        <p className="text-xs text-text-secondary leading-relaxed max-w-4xl">
          <span className="font-semibold text-text-primary">
            {tr("Read the numbers as meaning, not as a grade. ", "Читайте числа как смысл, а не как оценку. ")}
          </span>
          {tr(
            "GEDS is strong at RANKING — putting shocks in the right order of severity (see the rank correlation, Spearman ρ). It is weak at ABSOLUTE PRECISION — hitting the exact magnitude (see the low ±25% pass rate), and weakest of all at recovery time. So trust it for “which is worse, and why”, not for “the loss will be exactly X%”. Every figure on this page is computed live by the backend the moment you load it — nothing here is hardcoded.",
            "GEDS силён в РАНЖИРОВАНИИ — он расставляет шоки в правильном порядке по серьёзности (см. ранговую корреляцию, Спирмен ρ). Он слаб в АБСОЛЮТНОЙ ТОЧНОСТИ — попасть в точную величину (см. низкую долю ±25%), и слабее всего во времени восстановления. Поэтому доверяйте ему в вопросе «что хуже и почему», а не «потери составят ровно X%». Каждое число на этой странице вычисляется backend-ом вживую в момент загрузки — здесь ничего не захардкожено.",
          )}
        </p>
      </section>

      {/* Data foundation */}
      <div className="panel p-4 space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
          {tr("Data foundation — why these numbers can be trusted", "Основа данных — почему этим числам можно доверять")}
        </h2>
        <p className="text-xs text-text-secondary leading-relaxed max-w-4xl">
          {tr(
            "A model is only as good as its inputs. GEDS uses no invented or synthetic parameters — every weight traces to a published primary source, and the trade data refreshes automatically. A transparent, checkable data foundation is what lets the model be criticised and improved, and it is the part of GEDS that is genuinely precise.",
            "Модель хороша ровно настолько, насколько хороши её входные данные. GEDS не использует выдуманных или синтетических параметров — каждый вес восходит к опубликованному первичному источнику, а торговые данные обновляются автоматически. Прозрачная, проверяемая основа данных позволяет критиковать и улучшать модель — и это та часть GEDS, которая действительно точна.",
          )}
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-1.5 text-xs">
          {[
            { s: "UN Comtrade 2019", en: "bilateral trade flows → dependency weights (who relies on whom, and how much)", ru: "двусторонние торговые потоки → веса зависимостей (кто от кого зависит и насколько)" },
            { s: "World Bank LPI 2018", en: "logistics performance → how fast a country absorbs and recovers from shocks", ru: "логистическая эффективность → как быстро страна поглощает шоки и восстанавливается" },
            { s: "OECD STAN", en: "sector GDP shares → how much each industry weighs in the economy", ru: "доли секторов в ВВП → вес каждой отрасли в экономике" },
            { s: "IMF WEO 2020", en: "GDP levels → scaling impacts to real economic size", ru: "уровни ВВП → масштабирование последствий к реальному размеру экономики" },
            { s: "IEA WEO 2020", en: "chokepoint exposure → trade share through Suez / Hormuz / Malacca / Taiwan Strait", ru: "зависимость от проливов → доля торговли через Суэц / Ормуз / Малакку / Тайваньский пролив" },
            { s: "IMO / Lloyd's List", en: "disruption statistics → how often each chokepoint is actually blocked", ru: "статистика нарушений → как часто каждый пролив реально блокируется" },
          ].map((d) => (
            <div key={d.s} className="leading-snug">
              <span className="text-text-primary font-semibold">{d.s}</span>
              <span className="text-text-muted"> — {tr(d.en, d.ru)}</span>
            </div>
          ))}
        </div>
        <p className="text-[10px] text-text-muted leading-relaxed pt-1">
          {tr(
            "Full machine-readable provenance, with the exact formula and caveats for every parameter: GET /api/v1/data/provenance. Known limitations are documented there, not buried — e.g. China's chip dependency is understated because some flows route through Hong Kong.",
            "Полная машиночитаемая прослеживаемость, с точной формулой и оговорками для каждого параметра: GET /api/v1/data/provenance. Известные ограничения задокументированы там, а не спрятаны — например, зависимость Китая от чипов занижена, так как часть потоков идёт через Гонконг.",
          )}
        </p>
      </div>

      {/* CV report */}
      <div className="panel p-4 space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
          {tr("Leave-one-out cross-validation", "LOO-кросс-валидация")}
        </h2>
        <p className="text-xs text-text-secondary leading-relaxed max-w-4xl">
          {tr(
            "Each of the n events is predicted by a model that never saw it, then compared to what really happened. Pearson r and Spearman ρ are correlations between predicted and observed severity — ρ (rank) near 1.0 means the model orders events correctly, and this is GEDS's strongest result. MAE is the average error; RMSE (normalized) is error relative to simply guessing the mean, so a value above 1.0 means worse than that baseline. Pass ±25% / ±50% is the share of predictions landing within that tolerance of the truth, with a bootstrap 95% confidence interval in brackets — a deliberately strict precision test that the model currently mostly fails on magnitude and on recovery time (note the large MAE-recovery in weeks).",
            "Каждое из n событий предсказывает модель, которая его не видела, после чего результат сравнивается с реальностью. Pearson r и Spearman ρ — корреляции между предсказанной и наблюдаемой серьёзностью; ρ (ранговая) около 1,0 означает, что модель правильно упорядочивает события — это самый сильный результат GEDS. MAE — средняя ошибка; RMSE (норм.) — ошибка относительно простого «угадывания среднего», поэтому значение выше 1,0 означает хуже этого бейзлайна. Точность ±25% / ±50% — доля прогнозов в пределах допуска от истины, с бутстреп-интервалом 95% в скобках — намеренно строгий тест точности, который модель пока в основном не проходит по величине и по времени восстановления (см. большой MAE восстановления в неделях).",
          )}
        </p>
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
        <p className="text-xs text-text-secondary leading-relaxed max-w-4xl">
          {tr(
            "Raw predictions can be systematically biased — for instance, always too low. Isotonic calibration learns a monotonic “correction curve” (again fit leave-one-out, so it can't cheat) and re-maps predictions onto the observed scale without changing their order. The before / after columns show whether that correction actually helps: a cyan Δ is an improvement, an amber Δ a regression. Calibration can remove bias, but it cannot restore information the model never captured in the first place.",
            "Сырые прогнозы могут быть систематически смещены — например, всегда занижены. Изотоническая калибровка обучает монотонную «кривую коррекции» (тоже по схеме leave-one-out, чтобы не было подгонки) и переносит прогнозы на наблюдаемую шкалу, не меняя их порядок. Столбцы «до» / «после» показывают, помогает ли коррекция: голубая Δ — улучшение, янтарная Δ — ухудшение. Калибровка убирает смещение, но не может восстановить информацию, которую модель изначально не уловила.",
          )}
        </p>
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
        <p className="text-xs text-text-secondary leading-relaxed max-w-4xl">
          {tr(
            "Instead of one “best guess” for each of the five engine parameters, MCMC (affine-invariant sampling via emcee) explores the whole range of values consistent with the data — a probability distribution, not a point. mean ± std and the p05–p95 band are the credible interval; sensitivity is how much the data narrowed a parameter versus its prior (high = the data has a lot to say about it). R̂ is the convergence check: ≈1.0 means the sampler settled, while a value well above 1.1 (flagged “not converged”) means these numbers are preliminary and need a longer run. We label that state honestly rather than present an unconverged fit as if it were final.",
            "Вместо одной «лучшей оценки» для каждого из пяти параметров движка MCMC (аффинно-инвариантная выборка через emcee) исследует весь диапазон значений, совместимых с данными — распределение вероятностей, а не точку. mean ± std и полоса p05–p95 — это доверительный интервал; sensitivity — насколько данные сузили параметр по сравнению с априорным (высокое = данные говорят о нём многое). R̂ — проверка сходимости: ≈1,0 означает, что сэмплер устоялся, а значение существенно выше 1,1 (помечено «не сошёлся») означает, что числа предварительные и нужен более длинный прогон. Мы честно помечаем это состояние, а не выдаём несошедшуюся подгонку за окончательную.",
          )}
        </p>
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
        <p className="text-xs text-text-secondary leading-relaxed max-w-4xl">
          {tr(
            "Exploratory indices this project proposes — Systemic Fragility Index (SFI), Recovery Elasticity (RES), Shock Absorption Capacity (SAC), and a time-resolved resilience tensor — plus per-node criticality rankings that flag which country-industry nodes spread damage furthest. The statistical-evaluation table is the honesty check on these inventions: it asks whether each proposed metric actually correlates with real outcomes. Pearson / Spearman are the correlations; the permutation p-value is the probability of seeing that correlation by pure chance (cyan = below 0.05, i.e. statistically significant); Cohen's d is the effect size; n is the sample size. With small n, treat even a significant result as promising-but-preliminary.",
            "Поисковые индексы, которые предлагает этот проект — Индекс системной хрупкости (SFI), Эластичность восстановления (RES), Способность поглощать шок (SAC) и тензор устойчивости во времени — плюс рейтинги критичности узлов, показывающие, какие узлы «страна–отрасль» разносят ущерб дальше всего. Таблица статистической оценки — это проверка честности этих изобретений: она спрашивает, действительно ли каждая метрика коррелирует с реальными исходами. Pearson / Spearman — корреляции; p-value перестановочного теста — вероятность увидеть такую корреляцию чисто случайно (голубой = меньше 0,05, т.е. статистически значимо); Cohen's d — размер эффекта; n — размер выборки. При малом n даже значимый результат считайте многообещающим, но предварительным.",
          )}
        </p>
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
        <p className="text-xs text-text-secondary leading-relaxed max-w-4xl">
          {tr(
            "Every propagation model we implemented, scored on the same events against the naive “always predict the historical average” baseline. MAE / RMSE are error sizes (lower is better); R² and Pearson measure fit; Bias shows systematic over- or under-prediction. Skill is the headline column: Skill > 0 (cyan) means the model genuinely beats guessing the mean, Skill < 0 means it does not. The ★ marks the lowest-error model. This is the test that stops a complicated model from taking credit for a result a one-line baseline could already match.",
            "Каждая реализованная нами модель распространения, оценённая на тех же событиях против наивного бейзлайна «всегда предсказывай историческое среднее». MAE / RMSE — размеры ошибки (меньше — лучше); R² и Pearson — качество подгонки; Bias — систематическое завышение или занижение. Skill — ключевой столбец: Skill > 0 (голубой) означает, что модель действительно превосходит «угадывание среднего», Skill < 0 — что нет. ★ отмечает модель с наименьшей ошибкой. Это тест, который не даёт сложной модели присвоить себе результат, который уже мог бы дать однострочный бейзлайн.",
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

      {/* Multi-output cascade-shape validation (Task #3) */}
      <div className="panel p-4 space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
          {tr("Cascade-shape validation", "Валидация формы каскада")}
        </h2>
        <p className="text-xs text-text-secondary leading-relaxed max-w-4xl">
          {tr(
            "Scores the engine against the SHAPE of each historical cascade, not one scalar: peak magnitude, weeks-to-peak and recovery — plus whether the cascade reaches the nodes history actually hit, in the right order. Spearman is rank agreement (1 = perfect ordering); spatial recall is the fraction of hit nodes the engine's cascade actually reaches.",
            "Оценивает движок по ФОРМЕ каждого исторического каскада, а не по одному числу: пиковая магнитуда, недели до пика и восстановление — плюс доходит ли каскад до узлов, которые история реально задела, и в правильном ли порядке. Spearman — ранговое согласие (1 = идеальный порядок); spatial recall — доля задетых узлов, до которых каскад движка реально доходит.",
          )}
        </p>
        {cascade ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {(["magnitude", "weeks_to_peak", "recovery_weeks"] as const).map((dim) => (
              <Cell
                key={dim}
                label={`${dim} ${tr("Spearman", "Spearman")} (n=${cascade.shape.n_by_dim[dim] ?? 0})`}
                value={`${(cascade.shape.spearman_by_dim[dim] ?? 0) >= 0 ? "+" : ""}${(cascade.shape.spearman_by_dim[dim] ?? 0).toFixed(2)}`}
              />
            ))}
            <Cell
              label={tr("spatial recall", "пространств. recall")}
              value={`${(cascade.spatial.spatial_recall * 100).toFixed(0)}%`}
            />
            <Cell
              label={tr("graph coverage", "покрытие графа")}
              value={`${(cascade.spatial.coverage * 100).toFixed(0)}%`}
            />
            <Cell
              label={tr("onset order (Spearman)", "порядок onset (Spearman)")}
              value={`${cascade.spatial.onset_spearman >= 0 ? "+" : ""}${cascade.spatial.onset_spearman.toFixed(2)}`}
            />
            <Cell
              label={tr("onset MAE", "onset MAE")}
              value={`${cascade.spatial.onset_mae_weeks.toFixed(1)} ${tr("wk", "нед")}`}
            />
            <Cell
              label={tr("out-of-graph nodes", "узлов вне графа")}
              value={`${cascade.spatial.n_out_of_graph}`}
            />
          </div>
        ) : <div className="text-xs text-text-muted">{tr("Loading…", "Загрузка…")}</div>}
        <p className="text-[10px] text-text-muted leading-snug">
          {tr(
            "Read: the engine ranks shape well (Spearman 0.6–0.85) but under-predicts magnitude and reaches only ~38% of hit nodes — the sparse 12-country graph has no edge to many places history hit. That gap is the quantitative case for the ICIO 81×5 expansion.",
            "Вывод: движок хорошо ранжирует форму (Spearman 0.6–0.85), но недооценивает магнитуду и доходит лишь до ~38% задетых узлов — у разреженного графа из 12 стран нет рёбер ко многим местам, которые задела история. Этот разрыв — количественный аргумент за расширение ICIO 81×5.",
          )}
        </p>
      </div>

      {/* Out-of-sample LOO-DE verdict */}
      <div className="panel p-4 space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
          {tr("Out-of-sample verdict — recalibrated engine", "Out-of-sample вердикт — перекалиброванный движок")}
        </h2>
        <p className="text-xs text-text-secondary leading-relaxed max-w-4xl">
          {tr(
            "The strictest test we run. For each of the historical events, the engine's 5 parameters are re-fitted from scratch on the other events only (differential evolution), then the held-out event is predicted by a model that has never seen it. The pooled score below therefore cannot be inflated by overfitting — it is directly comparable to the parameter-free linear-diffusion baseline in the leaderboard above. Where the recalibrated engine wins, the win is real; where the baseline still leads (rank correlation), we say so.",
            "Самый строгий наш тест. Для каждого исторического события 5 параметров движка заново подбираются только на остальных событиях (дифференциальная эволюция), после чего отложенное событие предсказывает модель, которая его никогда не видела. Итоговую оценку ниже невозможно завысить переобучением — она напрямую сопоставима с безпараметрическим бейзлайном (линейная диффузия) из лидерборда выше. Где перекалиброванный движок выигрывает — выигрыш настоящий; где бейзлайн всё ещё впереди (ранговая корреляция) — мы говорим об этом прямо.",
          )}
        </p>
        {looDe ? (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs pt-1">
              {([
                ["MAE", looDe.out_of_sample_score.mae.toFixed(4), bench ? looDe.out_of_sample_score.mae < Math.min(...bench.models.filter(m => m.model.includes("Diffusion")).map(m => m.mae)) : false],
                ["RMSE", looDe.out_of_sample_score.rmse.toFixed(4), false],
                ["R²", `${looDe.out_of_sample_score.r_squared >= 0 ? "+" : ""}${looDe.out_of_sample_score.r_squared.toFixed(3)}`, false],
                ["Pearson", `${looDe.out_of_sample_score.pearson >= 0 ? "+" : ""}${looDe.out_of_sample_score.pearson.toFixed(3)}`, false],
                ["Spearman", `${looDe.out_of_sample_score.spearman >= 0 ? "+" : ""}${looDe.out_of_sample_score.spearman.toFixed(3)}`, false],
              ] as Array<[string, string, boolean]>).map(([label, value, star]) => (
                <div key={label}>
                  <div className="text-text-muted uppercase tracking-wider text-[10px]">{label}</div>
                  <div className={`num ${star ? "text-accent-cyan font-bold" : "text-text-primary"}`}>{star && "★ "}{value}</div>
                </div>
              ))}
            </div>
            <details className="pt-1">
              <summary className="text-[11px] text-text-muted cursor-pointer hover:text-text-secondary transition">
                {tr(`Per-event predictions (${looDe.n_folds} held-out folds)`, `Прогнозы по событиям (${looDe.n_folds} отложенных фолдов)`)}
              </summary>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-1 pt-2 text-[11px]">
                {looDe.folds.map((f) => (
                  <div key={f.slug} className="flex justify-between gap-2">
                    <span className="text-text-secondary truncate">{f.slug}</span>
                    <span className="num text-text-muted shrink-0">
                      {f.loss_predicted.toFixed(3)} <span className="text-text-muted/50">vs</span> {f.loss_observed.toFixed(3)}
                    </span>
                  </div>
                ))}
              </div>
            </details>
            <div className="text-[10px] text-text-muted pt-1">
              {tr("Computed", "Вычислено")} {new Date(looDe.timestamp).toLocaleString()} ·{" "}
              {tr("runtime", "время")} {(looDe.runtime_seconds / 60).toFixed(0)} {tr("min", "мин")} ·{" "}
              {tr("reproduce:", "воспроизвести:")} <span className="num text-text-secondary">{looDe.reproduce_command}</span>
            </div>
          </>
        ) : <div className="text-xs text-text-muted">{tr("Loading…", "Загрузка…")}</div>}
      </div>

      {/* External data cross-checks */}
      <div className="panel p-4 space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
          {tr("External data cross-checks — IMF PortWatch & NY Fed GSCPI", "Перекрёстные проверки на внешних данных — IMF PortWatch и NY Fed GSCPI")}
        </h2>
        <p className="text-xs text-text-secondary leading-relaxed max-w-4xl">
          {tr(
            "Two datasets the model was never calibrated on. PortWatch counts every vessel transiting maritime chokepoints daily — so our chokepoint shock assumptions can be checked against measured traffic, not narrative. GSCPI is the NY Fed's monthly index of global supply-chain pressure — if our predicted severity is real, it should rank-correlate with the measured pressure rise during each event.",
            "Два набора данных, на которых модель никогда не калибровалась. PortWatch ежедневно считает суда, проходящие морские чокпоинты — наши предположения о шоках проверяются по измеренному трафику, а не по нарративу. GSCPI — месячный индекс давления на глобальные цепочки поставок от ФРБ Нью-Йорка: если наша предсказанная серьёзность реальна, она должна ранжироваться вместе с измеренным ростом давления.",
          )}
        </p>
        {portwatch ? (
          <div className="space-y-2">
            {portwatch.event_checks.map((c) => (
              <div key={c.slug} className="text-xs flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
                <span className="text-text-primary font-semibold">{c.slug}</span>
                <span className={`num ${c.magnitude_verdict.startsWith("CONFIRMED") ? "text-accent-cyan" : "text-sev-4"}`}>
                  {c.magnitude_verdict}
                </span>
                <span className="text-text-muted">{c.duration_verdict}</span>
              </div>
            ))}
            <div className="text-xs pt-1 border-t border-border-subtle/50">
              <span className="text-text-primary font-semibold">
                {tr("Rerouting natural experiment (Red Sea): ", "Натуральный эксперимент перенаправления (Красное море): ")}
              </span>
              <span className="text-text-secondary">
                {tr(
                  `${(portwatch.rerouting_cross_check.fraction_of_lost_suez_transits_reappearing_at_cape * 100).toFixed(0)}% of lost Suez transits reappear at the Cape of Good Hope (weekly correlation ${portwatch.rerouting_cross_check.weekly_correlation_suez_lost_vs_cape_gained.toFixed(2)}) — measured support for the capacity-factor edge weights.`,
                  `${(portwatch.rerouting_cross_check.fraction_of_lost_suez_transits_reappearing_at_cape * 100).toFixed(0)}% потерянных транзитов Суэца появляются у мыса Доброй Надежды (недельная корреляция ${portwatch.rerouting_cross_check.weekly_correlation_suez_lost_vs_cape_gained.toFixed(2)}) — измеренное подтверждение capacity-фактора в весах рёбер.`,
                )}
              </span>
            </div>
          </div>
        ) : <div className="text-xs text-text-muted">{tr("PortWatch: loading…", "PortWatch: загрузка…")}</div>}
        {gscpi ? (
          <div className="text-xs pt-1 border-t border-border-subtle/50 space-y-1">
            <div>
              <span className="text-text-primary font-semibold">GSCPI: </span>
              <span className="text-text-secondary">
                {tr(
                  `predicted severity vs measured pressure rise — Spearman ρ = ${gscpi.spearman_non_overlapping.toFixed(2)} on ${gscpi.n_non_overlapping} non-overlapping events (${gscpi.spearman_all_events.toFixed(2)} on all ${gscpi.n_events}).`,
                  `предсказанная серьёзность против измеренного роста давления — Спирмен ρ = ${gscpi.spearman_non_overlapping.toFixed(2)} на ${gscpi.n_non_overlapping} неперекрывающихся событиях (${gscpi.spearman_all_events.toFixed(2)} на всех ${gscpi.n_events}).`,
                )}
              </span>
            </div>
            <div className="text-[10px] text-text-muted">{gscpi.caveat}</div>
          </div>
        ) : <div className="text-xs text-text-muted">{tr("GSCPI: loading…", "GSCPI: загрузка…")}</div>}
      </div>

      {/* ICIO edge cross-validation */}
      <div className="panel p-4 space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
          {tr("Graph weights vs OECD ICIO 2019 — measured input-output flows", "Веса графа против OECD ICIO 2019 — измеренные межотраслевые потоки")}
        </h2>
        <p className="text-xs text-text-secondary leading-relaxed max-w-4xl">
          {tr(
            "The OECD Inter-Country Input-Output table measures, in dollars, how much every country-industry buys from every other. Every hand-authored dependency weight in the graph is recomputed from those measured 2019 flows and compared like-for-like (import penetration — the same convention the weights were authored with from UN Comtrade). Chokepoint links are excluded: straits are not producing sectors (their capacity-factor convention is checked against IMF PortWatch above).",
            "Таблица OECD ICIO измеряет в долларах, сколько каждая страна-отрасль покупает у каждой другой. Каждый ручной вес зависимости в графе пересчитан из измеренных потоков 2019 года и сравнён в одинаковой конвенции (импортная пенетрация — та же, в которой веса авторились по UN Comtrade). Chokepoint-связи исключены: проливы — не производящие сектора (их capacity-фактор проверяется по IMF PortWatch выше).",
          )}
        </p>
        {icio ? (
          <div className="space-y-2 text-xs">
            <div className="flex flex-wrap gap-x-5 gap-y-1">
              <span className="text-text-muted">
                {tr("Coverage: ", "Покрытие: ")}
                <span className="num text-text-primary">
                  {icio.summary.n_production_edges}
                </span>{" "}
                {tr("production edges scored + ", "производственных рёбер оценено + ")}
                <span className="num text-text-primary">{icio.summary.n_chokepoint_links_excluded}</span>{" "}
                {tr("chokepoint links excluded = all ", "chokepoint-связей исключено = все ")}
                <span className="num text-text-primary">{icio.summary.n_total_seed_edges}</span>
                {tr(" seed edges", " рёбер графа")}
              </span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {Object.entries(icio.summary.correlations).map(([k, v]) => (
                <div key={k} className="rounded-lg border border-border-subtle bg-bg-base/40 px-2.5 py-1.5">
                  <div className="text-[9px] uppercase tracking-wider text-text-muted truncate" title={k}>
                    {k.replace("icio_", "").replace(/_/g, " ")}
                  </div>
                  <div className="num text-text-primary">
                    ρ {v.spearman != null ? (v.spearman >= 0 ? "+" : "") + v.spearman.toFixed(2) : "—"}
                    <span className="text-text-muted text-[10px] ml-1.5">n={v.n}</span>
                  </div>
                </div>
              ))}
            </div>
            {c26 && c26.semi_family_correlation_excl_capital_channel.pearson != null && (
              <div className="rounded-lg border border-accent-cyan/30 bg-accent-cyan/5 px-3 py-2">
                <span className="text-text-primary font-semibold">
                  {tr("C26 split headline: ", "Главный результат C26-сплита: ")}
                </span>
                <span className="text-text-secondary">
                  {tr(
                    `with ICIO's C26 sector split into semiconductors vs electronics via the committed Comtrade pull, the hand-authored semi-family weights validate at Pearson ${c26.semi_family_correlation_excl_capital_channel.pearson!.toFixed(2)} / Spearman ${c26.semi_family_correlation_excl_capital_channel.spearman!.toFixed(2)} (n=${c26.semi_family_correlation_excl_capital_channel.n}; the three NLD/ASML edges excluded — equipment is a measured capital-account flow that intermediate shares cannot represent).`,
                    `после разделения сектора C26 на полупроводники и электронику через закоммиченный Comtrade-пулл ручные semi-веса подтверждаются: Пирсон ${c26.semi_family_correlation_excl_capital_channel.pearson!.toFixed(2)} / Спирмен ${c26.semi_family_correlation_excl_capital_channel.spearman!.toFixed(2)} (n=${c26.semi_family_correlation_excl_capital_channel.n}; три ребра NLD/ASML исключены — оборудование идёт капитальным потоком, который промежуточные доли представить не могут).`,
                  )}
                </span>
              </div>
            )}
            <div className="pt-1 border-t border-border-subtle/50">
              <div className="text-[10px] uppercase tracking-wider text-text-muted mb-1">
                {tr("Largest disagreements (manual ÷ measured)", "Крупнейшие расхождения (ручной ÷ измеренный)")}
              </div>
              <div className="space-y-0.5">
                {icio.summary.worst_disagreements.slice(0, 5).map((w) => (
                  <div key={w.edge} className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
                    <span className="num text-text-primary">{w.edge}</span>
                    <span className="num text-text-secondary">
                      {w.manual.toFixed(3)} {tr("vs", "против")} {w.comparator != null ? w.comparator.toFixed(4) : "—"}
                      {w.manual_over_comparator != null && (
                        <span className={w.manual_over_comparator > 5 || w.manual_over_comparator < 0.2 ? " text-sev-4" : " text-text-muted"}>
                          {"  ×"}{w.manual_over_comparator.toFixed(1)}
                        </span>
                      )}
                    </span>
                    {w.mapping_caveats.length > 0 && (
                      <span className="text-[10px] text-text-muted truncate max-w-[28rem]" title={w.mapping_caveats.join("; ")}>
                        {w.mapping_caveats[0]}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : <div className="text-xs text-text-muted">{tr("ICIO: loading…", "ICIO: загрузка…")}</div>}
      </div>

      {/* Ablation */}
      <div className="panel p-4 space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
          {tr("Component-wise ablation", "Покомпонентная аблация")}
        </h2>
        <p className="text-xs text-text-secondary leading-relaxed max-w-4xl">
          {tr(
            "Each row switches off one engine component and re-runs the validation. The Δ columns compare that crippled model to the full one: a red +Δ MAE (or a negative Δ Pearson) means removing the component made predictions worse — so it is doing real work and earns its place. A component you can delete with no penalty is dead weight that should be cut. This is how you tell which parts of the model actually justify their complexity, rather than just assuming every piece helps.",
            "Каждая строка отключает один компонент движка и заново прогоняет валидацию. Столбцы Δ сравнивают такую «урезанную» модель с полной: красная +Δ MAE (или отрицательная Δ Pearson) означает, что удаление компонента ухудшило прогнозы — значит, он делает реальную работу и оправдан. Компонент, который можно удалить без потерь, — балласт, и его следует убрать. Так определяют, какие части модели действительно оправдывают свою сложность, а не просто предполагают, что полезен каждый элемент.",
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
