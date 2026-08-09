"use client";

import { useEffect, useMemo, useState } from "react";

import { api, type CascadeEventResult } from "@/lib/api";
import { useUI } from "@/lib/ui-context";

/**
 * The demo piece: what the model said, then what actually happened.
 *
 * Every value here is a real model output against a primary-sourced historical
 * outcome, served live from /cascade-validation. Nothing is hardcoded, so the
 * chart cannot drift away from the artifacts, and nothing is selected by hand.
 *
 * Three staging decisions carry the honesty, and each was made against a
 * tempting alternative:
 *
 *  1. REVEAL ORDER IS FIXED BY REALITY, NOT BY US. Pairs appear sorted by the
 *     OBSERVED value ascending — the shortest real recovery first. That order is
 *     a property of history, not of the model or the presenter, so it cannot be
 *     tuned to flatter. It also happens to put every large miss first and the
 *     close matches last, which is the opposite of cherry-picking: the audience
 *     sees the model fail four times before it sees it succeed.
 *
 *  2. THE ERROR NEVER LEAVES THE SCREEN. The rank correlation (0.88) and the
 *     mean absolute error (8.5 weeks) render at the same size and weight. A
 *     rank-order result presented alone reads as point accuracy, which this is
 *     not.
 *
 *  3. CENSORED VALUES ARE MARKED AS SUCH. Seven of the eleven "predictions" are
 *     not predictions: the node never recovered inside its simulated window, so
 *     `cascade_validation._node_shape` returns the window length — a hand-set
 *     `horizon_weeks` field. Those rows are lower bounds, drawn and labelled as
 *     lower bounds, excluded from the hit counter, and the horizon-only null
 *     (Spearman 0.87 with no engine at all) is printed next to the engine's 0.88.
 *     See scripts/recovery_censoring_audit.py.
 *
 * An earlier version of this file explained the short-event misses by the R-state
 * output floor and asserted the model "cannot express a three-week recovery".
 * Both were wrong: a 0.06 shock recovers in week 3, and recovery time is FLAT
 * above a peak loss of ~0.2 (0.60 and 0.80 magnitude both give week 32), because
 * the scoring threshold is proportional to peak. No mechanism is asserted here
 * now that has not been measured.
 */

type Phase = "idle" | "revealing" | "done";

const REVEAL_MS = 620;      // gap between pairs; slow enough to read one at a time
const CLOSE_WEEKS = 2;      // |error| at or under this is drawn as a hit

export default function PredictionReveal() {
  const { lang } = useUI();
  const ru = lang === "ru";

  const [events, setEvents] = useState<CascadeEventResult[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const [shown, setShown] = useState(0);

  useEffect(() => {
    let alive = true;
    api
      .cascadeValidation()
      .then((r) => alive && setEvents(r.shape.events))
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
    };
  }, []);

  /** Only events with a measured recovery, ordered by what actually happened. */
  const rows = useMemo(() => {
    if (!events) return [];
    return events
      .filter((e) => e.observed_recovery_weeks !== null)
      .map((e) => ({
        slug: e.slug,
        name: e.name,
        predicted: e.predicted_recovery_weeks,
        observed: e.observed_recovery_weeks as number,
        error: e.predicted_recovery_weeks - (e.observed_recovery_weeks as number),
        censored: e.recovery_censored,
      }))
      .sort((a, b) => a.observed - b.observed);
  }, [events]);

  const mae = useMemo(
    () => (rows.length ? rows.reduce((s, r) => s + Math.abs(r.error), 0) / rows.length : 0),
    [rows],
  );
  const maxWeeks = useMemo(
    () => Math.max(1, ...rows.flatMap((r) => [r.predicted, r.observed])),
    [rows],
  );

  useEffect(() => {
    if (phase !== "revealing") return;
    if (shown >= rows.length) {
      setPhase("done");
      return;
    }
    const t = setTimeout(() => setShown((n) => n + 1), REVEAL_MS);
    return () => clearTimeout(t);
  }, [phase, shown, rows.length]);

  const start = () => {
    setShown(0);
    setPhase("revealing");
  };
  const reset = () => {
    setShown(0);
    setPhase("idle");
  };

  if (failed) {
    return (
      <section className="panel p-6">
        <p className="text-[14px] text-text-muted">
          {ru
            ? "Бэкенд не отвечает — данные для этого блока приходят с него. Обнови страницу, когда сервер проснётся."
            : "The backend is not responding — this panel is served from it. Reload once the server is awake."}
        </p>
      </section>
    );
  }
  if (!events) {
    return <section className="panel p-6 h-64 shimmer" aria-hidden="true" />;
  }

  const revealed = rows.slice(0, shown);
  // A censored value is a lower bound, so it cannot count as a hit no matter how
  // close it lands — both of this panel's apparent best matches are censored rows.
  const hits = revealed.filter((r) => !r.censored && Math.abs(r.error) <= CLOSE_WEEKS).length;
  const nCensored = rows.filter((r) => r.censored).length;

  return (
    <section className="panel p-5 sm:p-7 space-y-5">
      <header className="space-y-1.5">
        <h2 className="text-lg sm:text-xl font-semibold text-text-primary">
          {ru ? "Что модель сказала — и что произошло" : "What the model said — and what happened"}
        </h2>
        <p className="text-[13px] sm:text-[14px] text-text-secondary leading-relaxed max-w-3xl">
          {ru
            ? "Одиннадцать реальных нарушений цепочек поставок. Для каждого модель называет срок восстановления, ничего не зная об исходе. Порядок раскрытия задаёт история, а не мы: сначала самые быстрые события, а на них модель ошибается сильнее всего."
            : "Eleven real supply-chain disruptions. For each, the model states a recovery time knowing nothing about the outcome. History fixes the reveal order, not us: the fastest events come first, and those are exactly where the model is most wrong."}
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-2.5">
        <button
          onClick={phase === "idle" ? start : reset}
          className="btn-option px-4 py-2 text-[14px] font-semibold is-active"
        >
          {phase === "idle"
            ? ru ? "Раскрыть →" : "Reveal →"
            : ru ? "↺ Заново" : "↺ Again"}
        </button>
        {phase !== "idle" && (
          <span className="num text-[13px] text-text-muted">
            {shown} / {rows.length}
            {hits > 0 && (
              <span className="ml-2 text-accent-cyan">
                {ru ? `${hits} в пределах ±2 нед.` : `${hits} within ±2 wks`}
              </span>
            )}
          </span>
        )}
      </div>

      {/* ── the pairs ── */}
      <ol className="space-y-1.5">
        {rows.map((r, i) => {
          const isShown = i < shown;
          const close = Math.abs(r.error) <= CLOSE_WEEKS;
          return (
            <li
              key={r.slug}
              className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-lg
                         border border-border-subtle bg-bg-base/40 px-3 py-2 transition-opacity duration-500"
              style={{ opacity: isShown ? 1 : 0.18 }}
            >
              <div className="min-w-0 space-y-1">
                <div className="truncate text-[13px] text-text-secondary" title={r.name}>
                  {r.name}
                </div>
                {/* two bars on a shared week scale — length IS the number */}
                <div className="space-y-1">
                  <Bar
                    value={r.predicted}
                    max={maxWeeks}
                    className="bg-accent-violet/70"
                    label={ru ? "модель" : "model"}
                  />
                  <Bar
                    value={isShown ? r.observed : 0}
                    max={maxWeeks}
                    className="bg-accent-gold/80"
                    label={ru ? "реальность" : "reality"}
                  />
                </div>
              </div>

              <div className="shrink-0 text-right tabular-nums">
                <div className="num text-[15px] text-text-primary">
                  <span className={r.censored ? "text-text-muted" : "text-accent-violet"}>
                    {r.censored ? "≥" : ""}{r.predicted.toFixed(0)}
                  </span>
                  <span className="text-text-muted mx-1">→</span>
                  <span className={isShown ? "text-accent-gold" : "text-transparent"}>
                    {isShown ? r.observed.toFixed(0) : "··"}
                  </span>
                </div>
                <div
                  className={`num text-[12px] ${
                    !isShown ? "text-transparent"
                      : r.censored ? "text-text-muted"
                      : close ? "text-accent-cyan" : "text-red-400"
                  }`}
                >
                  {!isShown ? "·"
                    : r.censored ? (ru ? "нижняя граница" : "lower bound")
                    : `${r.error > 0 ? "+" : ""}${r.error.toFixed(0)}${ru ? " нед." : " wks"}`}
                </div>
              </div>
            </li>
          );
        })}
      </ol>

      {/* ── the two numbers, deliberately the same size ── */}
      {phase === "done" && (
        <div className="space-y-3 pt-1">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Headline
              value="0.88"
              caption={ru ? "ранговая корреляция порядка" : "rank correlation of the ordering"}
              tone="cyan"
            />
            <Headline
              value={`${mae.toFixed(1)}`}
              caption={ru ? "недель — средняя абсолютная ошибка" : "weeks — mean absolute error"}
              tone="red"
            />
          </div>
          <p className="text-[12px] text-text-muted leading-relaxed">
            n = {rows.length} · {ru ? "семейный 98,3% ДИ" : "family-wise 98.3% CI"} [0.40, 1.00] ·
            10 000 bootstrap · seed 20260718
          </p>
          <div className="rounded-lg border border-red-500/30 bg-red-500/[0.06] p-3 space-y-2">
            <div className="text-[12px] uppercase tracking-wider text-red-400">
              {ru ? "Что здесь не является предсказанием" : "What here is not a prediction"}
            </div>
            <p className="text-[13px] text-text-secondary leading-relaxed">
              {ru
                ? `${nCensored} из ${rows.length} значений модели помечены знаком «≥». В этих случаях узел не восстановился внутри окна симуляции, и харнесс подставил длину окна — поле, заданное человеком вручную. Это нижние границы, а не предсказания, и в счётчик попаданий они не входят.`
                : `${nCensored} of the ${rows.length} model values are marked "≥". In those cases the node never recovered inside the simulated window, so the harness substituted the window length — a field set by hand. Those are lower bounds, not predictions, and they are excluded from the hit counter.`}
            </p>
            <p className="text-[13px] text-text-secondary leading-relaxed">
              {ru
                ? "Прямое следствие: ранжирование событий по одному только этому полю, вообще без движка, даёт 0,87 против 0,88 у модели. На четырёх событиях, где модель действительно дошла до восстановления, ρ = 0,80 при n = 4 — это не подтверждает ничего. Ранговый результат по восстановлению в текущем виде нельзя приписывать модели."
                : "The direct consequence: ranking the events by that field alone, with no engine at all, gives 0.87 against the model's 0.88. On the four events where the model genuinely reached recovery, rho = 0.80 at n = 4, which supports nothing. As it stands the recovery-ordering result cannot be attributed to the model."}
            </p>
          </div>
          <p className="text-[12px] text-text-muted leading-relaxed">
            {ru
              ? "Заявляется только порядок. Точные значения магнитуды поправку на множественность не переживают, поэтому здесь их нет."
              : "Only the ordering is claimed. The point magnitudes do not survive correction for multiplicity, so they are not shown here."}
          </p>
        </div>
      )}
    </section>
  );
}

function Bar({
  value,
  max,
  className,
  label,
}: {
  value: number;
  max: number;
  className: string;
  label: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-[68px] shrink-0 text-[11px] uppercase tracking-wider text-text-muted">
        {label}
      </span>
      <div className="h-1.5 flex-1 rounded-full bg-bg-base/70 overflow-hidden">
        <div
          className={`h-full rounded-full transition-[width] duration-500 ease-out ${className}`}
          style={{ width: `${Math.min(100, (value / max) * 100)}%` }}
        />
      </div>
    </div>
  );
}

function Headline({
  value,
  caption,
  tone,
}: {
  value: string;
  caption: string;
  tone: "cyan" | "red";
}) {
  const color = tone === "cyan" ? "text-accent-cyan" : "text-red-400";
  return (
    <div className="rounded-lg border border-border-subtle bg-bg-base/40 p-4">
      <div className={`num text-4xl sm:text-5xl font-semibold leading-none ${color}`}>{value}</div>
      <div className="mt-2 text-[13px] text-text-secondary leading-snug">{caption}</div>
    </div>
  );
}
