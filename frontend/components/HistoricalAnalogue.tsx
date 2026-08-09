"use client";

import { useEffect, useMemo, useState } from "react";

import { api, type HistoricalEvent } from "@/lib/api";
import { findAnalogue } from "@/lib/analogue";
import { nodeName } from "@/lib/names";
import { useSimStore } from "@/lib/store";
import { useUI } from "@/lib/ui-context";

/**
 * "When something like this actually happened, here is what it did."
 *
 * Everything else on this page is model output. This panel is not: it reports
 * measured figures from the benchmark's primary sources for the closest real
 * event to the scenario being run. It exists because the model's weakest axis
 * is exactly the one a reader most wants a number for — how bad — and on that
 * axis a historical record beats a simulation that does not outperform a naive
 * mean. Kept visually distinct so the two are never confused.
 */
export default function HistoricalAnalogue() {
  const scenarios = useSimStore((s) => s.scenarios);
  const selectedId = useSimStore((s) => s.selectedScenarioId);
  const summary = useSimStore((s) => s.summary);
  const { lang } = useUI();
  const ru = lang === "ru";

  const [events, setEvents] = useState<HistoricalEvent[] | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .historicalEvents()
      .then((r) => alive && setEvents(r.events))
      .catch(() => alive && setEvents(null)); // backend asleep → panel simply hides
    return () => {
      alive = false;
    };
  }, []);

  const scenario = scenarios.find((s) => s.id === selectedId);
  const match = useMemo(
    () => findAnalogue(events, scenario?.shocks ?? []),
    [events, scenario],
  );

  if (!match || !summary) return null;

  const e = match.event;
  const year = e.start_date?.slice(0, 4) ?? "";
  const title = ru ? e.name_ru || e.name_en : e.name_en || e.name_ru;
  const pct = (v: number) => `${(v * 100).toFixed(0)}%`;

  const predictedRecovery = summary.global_recovery_weeks;
  const observedRecovery = e.recovery_weeks;

  return (
    <section className="panel p-4 space-y-3">
      <div className="flex items-center gap-2.5">
        <span
          className="w-6 h-6 shrink-0 rounded-md grid place-items-center text-[12px] font-bold
                     bg-accent-gold/15 text-accent-gold border border-accent-gold/30"
          aria-hidden="true"
        >
          ⌛
        </span>
        <div>
          <h3 className="text-sm font-semibold text-text-primary">
            {ru ? "Когда это случилось на самом деле" : "When this actually happened"}
          </h3>
          <p className="text-[12px] text-text-muted">
            {ru
              ? "Не прогноз модели — измеренные факты по ближайшему реальному событию"
              : "Not model output — measured facts from the closest real event"}
          </p>
        </div>
      </div>

      <div className="rounded-lg border border-accent-gold/25 bg-accent-gold/[0.06] p-3 space-y-2">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-[14px] font-semibold text-text-primary leading-snug">
            {title}
          </span>
          <span className="num shrink-0 text-[13px] text-text-muted">{year}</span>
        </div>

        <p className="text-[12px] text-text-muted leading-snug">
          {match.matchKind === "same_node"
            ? ru
              ? `Тот же узел — ${nodeName(e.target_node_geds ?? "", lang)}.`
              : `Same node — ${nodeName(e.target_node_geds ?? "", lang)}.`
            : ru
              ? `Та же отрасль, другая страна — ${nodeName(e.target_node_geds ?? "", lang)}.`
              : `Same industry, different country — ${nodeName(e.target_node_geds ?? "", lang)}.`}
          {ru
            ? ` Тогда шок был ${pct(e.shock_magnitude_geds ?? 0)} на ${e.duration_weeks_geds} нед.`
            : ` That shock was ${pct(e.shock_magnitude_geds ?? 0)} for ${e.duration_weeks_geds} weeks.`}
        </p>

        <div className="grid grid-cols-2 gap-2 pt-1">
          {e.delta_output_pct !== null && (
            <div className="rounded-md border border-border-subtle bg-bg-base/50 p-2">
              <div className="text-[11px] uppercase tracking-wider text-text-muted">
                {ru ? "Фактическая потеря" : "Measured loss"}
              </div>
              <div className="num text-[16px] font-semibold text-text-primary">
                −{pct(e.delta_output_pct)}
              </div>
            </div>
          )}
          {observedRecovery !== null && (
            <div className="rounded-md border border-border-subtle bg-bg-base/50 p-2">
              <div className="text-[11px] uppercase tracking-wider text-text-muted">
                {ru ? "Фактическое восстановление" : "Measured recovery"}
              </div>
              <div className="num text-[16px] font-semibold text-text-primary">
                {observedRecovery.toFixed(0)} {ru ? "нед." : "wks"}
              </div>
            </div>
          )}
        </div>

        {observedRecovery !== null && (
          <p className="text-[12px] text-text-secondary leading-relaxed pt-0.5">
            {ru
              ? `Модель на этом сценарии даёт ${predictedRecovery.toFixed(0)} нед. до восстановления, история дала ${observedRecovery.toFixed(0)}. Сравнивать эти два числа надо осторожно: в бенчмарке 7 из 11 «предсказаний» восстановления — нижние границы окна симуляции, а не предсказания, и ранжирование по одной длине окна даёт почти тот же результат.`
              : `On this scenario the model gives ${predictedRecovery.toFixed(0)} weeks to recovery; history gave ${observedRecovery.toFixed(0)}. Compare the two with care: in the benchmark 7 of 11 recovery "predictions" are lower bounds at the simulation window rather than predictions, and ranking by window length alone scores almost the same.`}
          </p>
        )}

        {e.sources?.length > 0 && (
          <p className="text-[11px] text-text-muted leading-snug border-t border-border-subtle pt-2">
            <span className="uppercase tracking-wider">
              {ru ? "Источник: " : "Source: "}
            </span>
            {e.sources[0]}
          </p>
        )}
      </div>
    </section>
  );
}
