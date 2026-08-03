"use client";

import { useEffect, useState } from "react";
import { api, type BaselineCompare, type ForecastBand } from "@/lib/api";
import { useSimStore } from "@/lib/store";
import { useUI } from "@/lib/ui-context";

/**
 * After a run completes, shows two honesty panels for the SAME scenario:
 *  (1) SEIRS vs the zero-parameter baselines (linear diffusion, Leontief) — so
 *      the cost/benefit of the engine's 5-parameter machinery is visible inline.
 *  (2) The leave-one-out forecast band — peak CSI re-run under all 26 LOO fold
 *      parameter sets, surfacing parametric uncertainty instead of a false-precise
 *      point estimate.
 */
export default function ModelComparisonPanel() {
  const { lang } = useUI();
  const ru = lang === "ru";
  const scenarioId = useSimStore((s) => s.selectedScenarioId);
  const summary = useSimStore((s) => s.summary);
  const running = useSimStore((s) => s.running);

  const [cmp, setCmp] = useState<BaselineCompare | null>(null);
  const [band, setBand] = useState<ForecastBand | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!summary || running) return;
    let cancelled = false;
    setLoading(true);
    const req = { scenario_id: scenarioId };
    Promise.allSettled([api.baselineCompare(req), api.forecastBand(req)]).then(
      ([c, b]) => {
        if (cancelled) return;
        setCmp(c.status === "fulfilled" ? c.value : null);
        setBand(b.status === "fulfilled" ? b.value : null);
        setLoading(false);
      },
    );
    return () => {
      cancelled = true;
    };
    // Re-fetch whenever a new run finishes (summary identity changes) or scenario changes.
  }, [summary, scenarioId, running]);

  if (!summary) return null;

  const maxLoss = cmp ? Math.max(...cmp.models.map((m) => m.industry_loss), 0.0001) : 1;

  return (
    <div className="panel p-4 space-y-3">
      <div className="flex items-baseline justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
          {ru ? "Проверка на честность" : "Model vs baseline"}
        </h2>
        {loading && <span className="text-[12px] text-text-muted num">{ru ? "считаю…" : "computing…"}</span>}
      </div>

      <p className="text-[12px] text-text-muted leading-relaxed">
        {ru
          ? "Тот же сценарий, посчитанный тремя моделями. GEDS имеет 5 настраиваемых параметров, две другие — ни одного. Если модель с параметрами не обгоняет модель без них, это честнее показать, чем спрятать."
          : "The same scenario computed by three models. GEDS has 5 tunable parameters, the other two have none. If the tuned model does not beat the untuned ones, that is worth showing rather than hiding."}
      </p>

      {/* ── SEIRS vs zero-parameter baselines ── */}
      {cmp ? (
        <div className="space-y-1.5">
          {cmp.models.map((m) => {
            const isEngine = m.parameters > 0;
            return (
              <div key={m.model} className="space-y-0.5">
                <div className="flex items-baseline justify-between text-[13px]">
                  <span className={isEngine ? "text-text-primary font-medium" : "text-text-secondary"}>
                    {m.model}
                    <span className="ml-1.5 text-[12px] uppercase tracking-wider text-text-muted">
                      {m.parameters === 0 ? (ru ? "без настроек" : "0-param") : (ru ? `${m.parameters} параметра` : `${m.parameters}-param`)}
                    </span>
                  </span>
                  <span className="num text-text-secondary">
                    {(m.industry_loss * 100).toFixed(1)}% · {m.recovery_weeks.toFixed(0)}{ru ? " нед." : "w"}
                  </span>
                </div>
                <div className="h-1.5 rounded-full bg-bg-base/60 overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${(m.industry_loss / maxLoss) * 100}%`,
                      background: isEngine
                        ? "linear-gradient(90deg, rgba(124,108,251,0.9), rgba(77,208,225,0.9))"
                        : "rgba(120,130,150,0.55)",
                    }}
                  />
                </div>
              </div>
            );
          })}
          <p className="text-[12px] text-text-muted leading-snug pt-0.5">
            {ru
              ? `Слева — насколько просядет отрасль в худший момент, справа — сколько недель до восстановления. Линейная диффузия здесь эталон: она вообще ничего не подгоняет.`
              : `Peak loss on the left, weeks to recovery on the right. Linear diffusion is the zero-free-parameter reference.`}
          </p>
        </div>
      ) : (
        !loading && <p className="text-[12px] text-text-muted">{ru ? "Сравнение недоступно." : "Baseline comparison unavailable."}</p>
      )}

      {/* ── LOO forecast band ── */}
      {band?.available && band.median != null && (
        <div className="hairline pt-3 space-y-1.5">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-[12px] uppercase tracking-wider text-text-muted">
              {ru ? "Насколько модель уверена" : "How confident the model is"}
            </span>
            <span className="num text-[13px] text-text-primary">{band.median.toFixed(3)}</span>
          </div>
          <ForecastBandBar band={band} />
          <p className="text-[12px] text-text-muted leading-relaxed">
            {ru ? (
              <>
                Настройки модели подобраны на исторических событиях — но какие именно,
                зависит от того, какие события взять. Поэтому сценарий пересчитан{" "}
                <b className="text-text-secondary">{band.n_folds} раз</b>, каждый раз с
                настройками, полученными без одного из событий. Полоска показывает разброс
                ответов: чем она короче, тем меньше результат зависит от случайного выбора
                данных. Здесь разброс{" "}
                <b className="text-text-secondary">{((band.rel_width ?? 0) * 100).toFixed(0)}%</b>{" "}
                — то есть настройки почти не влияют на итог.
              </>
            ) : (
              <>
                The model&apos;s settings are fitted on historical events, and which settings
                you get depends on which events you use. So the scenario was re-run{" "}
                <b className="text-text-secondary">{band.n_folds} times</b>, each with settings
                fitted while holding one event out. The bar shows the spread of answers — the
                shorter it is, the less the result depends on that choice. Here the spread is{" "}
                <b className="text-text-secondary">{((band.rel_width ?? 0) * 100).toFixed(0)}%</b>.
              </>
            )}
          </p>
          <p className="text-[12px] text-text-muted/80 leading-relaxed">
            {ru
              ? "Важная оговорка: это разброс только от настроек. Неопределённость самой структуры модели — какие связи в сети и какая физика каскада — больше, и здесь она не показана."
              : "Important caveat: this is spread from the settings only. Structural uncertainty — which links exist and how the cascade physically works — is larger and is not shown here."}
          </p>
        </div>
      )}
    </div>
  );
}

function ForecastBandBar({ band }: { band: ForecastBand }) {
  const lo = band.min ?? 0;
  const hi = band.max ?? 1;
  const span = Math.max(hi - lo, 1e-6);
  const pct = (v: number) => `${((v - lo) / span) * 100}%`;
  const p10 = band.p10 ?? lo;
  const p90 = band.p90 ?? hi;
  const median = band.median ?? (lo + hi) / 2;
  return (
    <div className="relative h-3">
      {/* full min–max track */}
      <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-1 rounded-full bg-bg-base/60" />
      {/* p10–p90 band */}
      <div
        className="absolute top-1/2 -translate-y-1/2 h-1 rounded-full"
        style={{
          left: pct(p10),
          width: `${((p90 - p10) / span) * 100}%`,
          background: "linear-gradient(90deg, rgba(124,108,251,0.7), rgba(77,208,225,0.7))",
        }}
      />
      {/* median marker */}
      <div
        className="absolute top-1/2 -translate-y-1/2 h-3 w-[2px] rounded-full bg-text-primary"
        style={{ left: pct(median) }}
      />
    </div>
  );
}
