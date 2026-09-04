"use client";

import { useMemo } from "react";

import CountUp from "@/components/CountUp";
import { severityColor } from "@/lib/colors";
import { useSimStore } from "@/lib/store";
import { useUI } from "@/lib/ui-context";

/**
 * ECONOMIC DOMINO EFFECT — the cascade, counted.
 *
 * Everything on this panel is derived from the frames already in the store.
 * Nothing is fetched, nothing is assumed, nothing is hardcoded: the origin set,
 * the weekly additions, the country spread, the depth in weeks, the peak share
 * and the week of peak severity are all read straight off `Frame[]`, and every
 * figure is evaluated AS OF `currentWeek`, so the numbers climb while the
 * animation plays and stop where the run stops.
 *
 * A node counts as reached at output_loss >= 0.01 — the same reach threshold the
 * project publishes its spatial-recall table at. The threshold is the only
 * constant in this file; it is a definition, not a result.
 *
 * The strip below the counters is the actual domino chain: the cumulative
 * reached-count at each week it CHANGED, in order. If a run only ever produces
 * two distinct values, two values are what it shows.
 */

const REACHED = 0.01;

/** Severity ramp for colour intensity; below the ramp's floor stay muted. */
function tone(v: number): string {
  return v > 0.0001 ? severityColor(v) : "#5B6473";
}

const fmtInt = (v: number) => Math.round(v).toString();
const fmtPct = (v: number) => v.toFixed(1) + "%";

interface Step {
  frameIndex: number;
  week: number;
  value: number;
  share: number;
}

interface Series {
  total: number;
  originCount: number;
  countryUniverse: number;
  span: number;
  firstSpreadWeek: number | null;
  cumulative: number[];
  newly: number[];
  countries: number[];
  peakShare: number[];
  peakCsiWeek: number[];
  peakCsiValue: number[];
  steps: Step[];
}

export default function CascadeCounters() {
  const frames = useSimStore((s) => s.frames);
  const summary = useSimStore((s) => s.summary);
  const currentWeek = useSimStore((s) => s.currentWeek);
  const { lang } = useUI();
  const ru = lang === "ru";

  // ── one pass over the whole run, independent of the playhead ──────────────
  const series = useMemo<Series | null>(() => {
    if (frames.length === 0) return null;

    const first = frames[0];
    const total = first.nodes.length;

    const originIds = new Set<string>();
    for (const n of first.nodes) {
      if (n.output_loss >= REACHED) originIds.add(n.id);
    }

    // how many distinct economies the graph can represent at all
    const universe = new Set<string>();
    for (const n of first.nodes) {
      const head = n.id.split(":")[0];
      if (head !== "CP") universe.add(head);
    }

    const seen = new Set<string>();
    const seenCountries = new Set<string>();
    const cumulative: number[] = [];
    const newly: number[] = [];
    const countries: number[] = [];
    const peakShare: number[] = [];
    const peakCsiWeek: number[] = [];
    const peakCsiValue: number[] = [];
    const steps: Step[] = [];

    let firstSpreadWeek: number | null = null;
    let runningPeakShare = 0;
    let bestCsi = -Infinity;
    let bestCsiWeek = first.week;

    // plain for-loop: assignments to firstSpreadWeek must stay visible to the
    // checker's control-flow analysis after the loop ends.
    for (let i = 0; i < frames.length; i++) {
      const f = frames[i];
      let added = 0;

      // Nodes over the reach threshold in THIS frame — the instantaneous count,
      // as distinct from `seen`, which never shrinks.
      let inst = 0;

      for (const n of f.nodes) {
        if (n.output_loss < REACHED) continue;
        inst += 1;
        if (seen.has(n.id)) continue;
        seen.add(n.id);
        added += 1;
        if (firstSpreadWeek === null && !originIds.has(n.id)) firstSpreadWeek = f.week;
        const head = n.id.split(":")[0];
        if (head !== "CP") seenCountries.add(head);
      }

      cumulative[i] = seen.size;
      newly[i] = added;
      countries[i] = seenCountries.size;

      // Counted here rather than read from `f.affected_count`, which the engine
      // defines as `shock > 0.10` (propagation.py AFFECTED_THRESHOLD) — a
      // different criterion from this panel's `output_loss >= 0.01`, selecting a
      // materially different set. On the flagship run its peak is 16/41 where
      // this panel's own rule gives 20/41, so the share printed here contradicted
      // both the counter beside it and the provenance note below it, which states
      // that every figure in this panel comes from the published reach threshold.
      // Now it does.
      const share = total > 0 ? inst / total : 0;
      if (share > runningPeakShare) runningPeakShare = share;
      peakShare[i] = runningPeakShare;

      if (f.csi > bestCsi) {
        bestCsi = f.csi;
        bestCsiWeek = f.week;
      }
      peakCsiWeek[i] = bestCsiWeek;
      peakCsiValue[i] = bestCsi;

      if (i === 0 || cumulative[i] !== cumulative[i - 1]) {
        steps.push({
          frameIndex: i,
          week: f.week,
          value: seen.size,
          share: total > 0 ? seen.size / total : 0,
        });
      }
    }

    const span = frames[frames.length - 1].week - first.week;

    return {
      total,
      originCount: originIds.size,
      countryUniverse: universe.size,
      span,
      firstSpreadWeek,
      cumulative,
      newly,
      countries,
      peakShare,
      peakCsiWeek,
      peakCsiValue,
      steps,
    };
  }, [frames]);

  // ── read the series at the playhead ───────────────────────────────────────
  const view = useMemo(() => {
    if (!series) return null;

    let idx = 0;
    for (let i = 0; i < frames.length; i++) {
      if (frames[i].week <= currentWeek) idx = i;
    }

    const week = frames[idx].week;
    const total = series.total;
    const affected = series.cumulative[idx];
    const newly = series.newly[idx];
    const countries = series.countries[idx];
    const depth =
      series.firstSpreadWeek === null ? 0 : Math.max(0, week - series.firstSpreadWeek);
    const peakShare = series.peakShare[idx];

    return {
      idx,
      week,
      total,
      affected,
      newly,
      countries,
      depth,
      peakShare,
      peakCsiWeek: series.peakCsiWeek[idx],
      peakCsiValue: series.peakCsiValue[idx],
      csi: frames[idx].csi,
      steps: series.steps.filter((s) => s.frameIndex <= idx),
      shareNow: total > 0 ? affected / total : 0,
      newShare: total > 0 ? newly / total : 0,
      originShare: total > 0 ? series.originCount / total : 0,
      countryShare: series.countryUniverse > 0 ? countries / series.countryUniverse : 0,
      depthShare: series.span > 0 ? depth / series.span : 0,
    };
  }, [series, frames, currentWeek]);

  if (!series || !view) return null;

  const spreading = view.newly > 0;
  const pulseColor = tone(spreading ? Math.max(view.newShare, 0.02) : 0);

  const counters: {
    key: string;
    label: string;
    value: number;
    format: (v: number) => string;
    sub: string;
    intensity: number;
  }[] = [
    {
      key: "origin",
      label: ru ? "Узлы-источники" : "Origin nodes",
      value: series.originCount,
      format: fmtInt,
      sub: ru ? "неделя 0" : "at week 0",
      intensity: view.originShare,
    },
    {
      key: "new",
      label: ru ? "Новых за неделю" : "New this week",
      value: view.newly,
      format: fmtInt,
      sub: ru ? `неделя ${view.week}` : `week ${view.week}`,
      intensity: view.newShare,
    },
    {
      key: "total",
      label: ru ? "Всего затронуто" : "Total affected",
      value: view.affected,
      format: fmtInt,
      sub: ru ? `из ${series.total} узлов` : `of ${series.total} nodes`,
      intensity: view.shareNow,
    },
    {
      key: "countries",
      label: ru ? "Затронуто стран" : "Countries touched",
      value: view.countries,
      format: fmtInt,
      sub: ru ? `из ${series.countryUniverse}` : `of ${series.countryUniverse}`,
      intensity: view.countryShare,
    },
    {
      key: "depth",
      label: ru ? "Глубина каскада" : "Cascade depth",
      value: view.depth,
      format: fmtInt,
      sub:
        series.firstSpreadWeek === null
          ? ru
            ? "распространения нет"
            : "no spread yet"
          : ru
            ? `нед. с недели ${series.firstSpreadWeek}`
            : `wks since week ${series.firstSpreadWeek}`,
      intensity: view.depthShare,
    },
    {
      key: "peakshare",
      label: ru ? "Пик доли затронутых" : "Peak affected share",
      value: view.peakShare * 100,
      format: fmtPct,
      sub: ru ? "максимум по кадрам" : "max over frames",
      intensity: view.peakShare,
    },
    {
      key: "peakweek",
      label: ru ? "Неделя пика тяжести" : "Week of peak severity",
      value: view.peakCsiWeek,
      format: fmtInt,
      sub: `CSI ${view.peakCsiValue.toFixed(3)}`,
      intensity: view.peakCsiValue,
    },
  ];

  return (
    <section className="panel p-5 sm:p-6 space-y-6 fade-up fade-up-1">
      {/* header */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span
          aria-hidden="true"
          className={`inline-block w-1.5 h-1.5 rounded-full shrink-0 ${spreading ? "glow-dot" : ""}`}
          style={{ background: pulseColor, color: pulseColor }}
        />
        <h2 className="text-sm font-semibold uppercase tracking-[0.16em] text-text-secondary">
          {ru ? "Эффект экономического домино" : "Economic domino effect"}
        </h2>
        <span className="num text-[12px] text-text-muted ml-auto">
          {ru ? "неделя" : "week"}{" "}
          <span className="text-text-secondary">{view.week}</span>
          <span className="text-text-muted/60"> / {frames[frames.length - 1].week}</span>
        </span>
      </div>

      {/* counters */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-x-4 gap-y-5">
        {counters.map((c) => {
          const color = tone(c.intensity);
          return (
            <div key={c.key} className="min-w-0">
              <div className="text-[11px] uppercase tracking-[0.12em] text-text-muted leading-tight">
                {c.label}
              </div>
              <div
                className="num text-[28px] sm:text-[32px] leading-none mt-2"
                style={{ color, textShadow: `0 0 22px ${color}33` }}
              >
                <CountUp value={c.value} format={c.format} />
              </div>
              <div className="num text-[11px] text-text-muted mt-1.5 leading-tight">{c.sub}</div>
            </div>
          );
        })}
      </div>

      {/* domino progression */}
      <div className="space-y-2 min-w-0">
        <div className="text-[11px] uppercase tracking-[0.12em] text-text-muted">
          {ru ? "Прогрессия домино" : "Domino progression"}
        </div>
        <ol className="flex items-end gap-1.5 sm:gap-2 overflow-x-auto no-scrollbar -mx-1 px-1 pb-1">
          {view.steps.map((s, i) => {
            const color = tone(s.share);
            const isLast = i === view.steps.length - 1;
            return (
              <li key={s.week} className="flex items-end gap-1.5 sm:gap-2 shrink-0">
                {i > 0 && (
                  <span aria-hidden="true" className="text-[13px] text-text-muted/60 pb-2">
                    →
                  </span>
                )}
                <span
                  className={[
                    "flex flex-col items-center rounded-md border px-2 py-1 transition-colors duration-500",
                    isLast ? "border-border-strong bg-bg-base/50" : "border-border-subtle",
                  ].join(" ")}
                >
                  <span
                    className="num text-[15px] sm:text-[16px] leading-none"
                    style={{ color, textShadow: isLast ? `0 0 16px ${color}44` : undefined }}
                  >
                    {s.value}
                  </span>
                  <span className="num text-[10px] text-text-muted mt-1 leading-none">
                    {ru ? "н" : "w"}
                    {s.week}
                  </span>
                </span>
              </li>
            );
          })}
        </ol>
        <p className="text-[12px] text-text-muted leading-snug">
          {ru
            ? "Накопленное число затронутых узлов — на каждой неделе, когда счёт менялся."
            : "Cumulative nodes reached, shown at every week the count changed."}
        </p>
      </div>

      {/* provenance */}
      <div className="hairline pt-3 space-y-1">
        <p className="text-[12px] text-text-muted leading-relaxed">
          {ru ? (
            <>
              Узел считается затронутым при потере выпуска{" "}
              <span className="num text-text-secondary">≥ 0.01</span> — это опубликованный порог
              охвата. Все значения на панели считаются по кадрам текущего прогона на неделе{" "}
              <span className="num text-text-secondary">{view.week}</span>; ничего не задано
              заранее.
            </>
          ) : (
            <>
              A node counts as reached at output loss{" "}
              <span className="num text-text-secondary">≥ 0.01</span> — the published reach
              threshold. Every figure here is counted from the frames of the current run as of week{" "}
              <span className="num text-text-secondary">{view.week}</span>; none of it is
              pre-set.
            </>
          )}
        </p>
        <p className="text-[12px] text-text-muted leading-relaxed">
          {ru ? (
            <>
              Это описание одного прогона, а не проверенный прогноз. Порядковые результаты модели
              (ранги) и точность по величине — разные вещи; по величине GEDS имеет худшую MAE из
              четырёх моделей эталона.
            </>
          ) : (
            <>
              This describes one run; it is not a validated forecast. Rank-order results and
              point-magnitude accuracy are separate claims — on magnitude, GEDS has the worst MAE of
              the four models in the benchmark.
            </>
          )}
        </p>
        {summary && (
          <p className="num text-[12px] text-text-muted">
            {ru ? "Пик CSI прогона" : "Run peak CSI"}{" "}
            <span className="text-text-secondary">{summary.peak_csi.toFixed(3)}</span>
          </p>
        )}
      </div>
    </section>
  );
}
