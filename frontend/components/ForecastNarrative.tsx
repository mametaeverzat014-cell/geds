"use client";

import { useMemo } from "react";

import { countryName, nodeName } from "@/lib/names";
import { useSimStore } from "@/lib/store";
import { buildTransmission } from "@/lib/transmission";
import { useUI } from "@/lib/ui-context";

/**
 * Plain-language account of what the model actually predicted.
 *
 * The Grok narrative panel needs an external API key and can be unavailable;
 * this one is derived arithmetically from the simulation frames, so it always
 * renders and can never state anything the run did not produce. Every sentence
 * here is traceable to a number in the frames.
 */

const REACHED = 0.01; // output-loss threshold that counts a node as "hit"

export default function ForecastNarrative() {
  const frames = useSimStore((s) => s.frames);
  const summary = useSimStore((s) => s.summary);
  const scenarios = useSimStore((s) => s.scenarios);
  const selectedId = useSimStore((s) => s.selectedScenarioId);
  const graph = useSimStore((s) => s.graph);
  const { lang } = useUI();
  const ru = lang === "ru";

  const scenarioNow = scenarios.find((s) => s.id === selectedId);
  const originIds = useMemo(
    () => (scenarioNow?.shocks ?? []).map((s) => s.target_node_id),
    [scenarioNow],
  );

  // why each node was hit: the path the shock took through the dependency graph
  const transmission = useMemo(
    () => buildTransmission(graph, frames, originIds, REACHED),
    [graph, frames, originIds],
  );

  const story = useMemo(() => {
    if (!frames.length || !summary) return null;

    // peak week by network severity
    let peakWeek = 0;
    for (let i = 1; i < frames.length; i++) {
      if (frames[i].csi > frames[peakWeek].csi) peakWeek = i;
    }
    const peak = frames[peakWeek];
    const last = frames[frames.length - 1];

    // first week each node crosses the "hit" threshold → the spreading order
    const firstHit = new Map<string, number>();
    for (const f of frames) {
      for (const n of f.nodes) {
        if (n.output_loss >= REACHED && !firstHit.has(n.id)) firstHit.set(n.id, f.week);
      }
    }
    const order = [...firstHit.entries()].sort((a, b) => a[1] - b[1]);

    // worst-hit nodes at the peak week
    const worst = [...peak.nodes]
      .filter((n) => n.output_loss >= REACHED)
      .sort((a, b) => b.output_loss - a.output_loss)
      .slice(0, 6);

    // group the spread into waves by onset week
    const waves: { week: number; nodes: string[] }[] = [];
    for (const [id, wk] of order) {
      const bucket = waves.find((w) => w.week === wk);
      if (bucket) bucket.nodes.push(id);
      else waves.push({ week: wk, nodes: [id] });
    }

    const countries = new Set(
      [...firstHit.keys()].map((id) => id.split(":")[0]).filter((c) => c !== "CP"),
    );

    return { peakWeek, peak, last, waves: waves.slice(0, 5), worst, countries: countries.size };
  }, [frames, summary]);

  if (!story || !summary) return null;

  const scenario = scenarioNow;
  const shocks = scenario?.shocks ?? [];
  const wk = (n: number) => (ru ? `неделя ${n}` : `week ${n}`);
  const pct = (v: number) => `${(v * 100).toFixed(0)}%`;

  return (
    <section className="panel p-4 space-y-3">
      <div className="flex items-center gap-2.5">
        <span
          className="w-6 h-6 shrink-0 rounded-md grid place-items-center text-[12px] font-bold
                     bg-accent-violet/15 text-accent-violet border border-accent-violet/30"
          aria-hidden="true"
        >
          ▶
        </span>
        <div>
          <h3 className="text-sm font-semibold text-text-primary">
            {ru ? "Что предсказывает модель" : "What the model predicts"}
          </h3>
          <p className="text-[12px] text-text-muted">
            {ru
              ? "Пересказ этого прогона обычным языком — каждая цифра из симуляции"
              : "This run in plain language — every figure comes from the simulation"}
          </p>
        </div>
      </div>

      {/* 1 — the shock */}
      <div className="rounded-lg border border-border-subtle bg-bg-base/40 p-3 space-y-1.5">
        <div className="text-[12px] uppercase tracking-wider text-text-muted">
          {ru ? "1 · Что происходит" : "1 · The shock"}
        </div>
        <p className="text-[13px] text-text-secondary leading-relaxed">
          {shocks.length > 0 ? (
            <>
              {ru ? "Удар приходится по " : "The shock hits "}
              {shocks.map((s, i) => (
                <span key={i}>
                  <b className="text-text-primary">{nodeName(s.target_node_id, lang)}</b>
                  {ru
                    ? ` — потеря ${pct(s.magnitude)} мощности на ${s.duration_weeks} нед.`
                    : ` — losing ${pct(s.magnitude)} of capacity for ${s.duration_weeks} weeks`}
                  {i < shocks.length - 1 ? (ru ? "; также " : "; also ") : "."}
                </span>
              ))}
            </>
          ) : (
            ru ? "Сценарий задан вручную." : "Custom scenario."
          )}
        </p>
      </div>

      {/* 2 — how it spreads */}
      <div className="rounded-lg border border-border-subtle bg-bg-base/40 p-3 space-y-2">
        <div className="text-[12px] uppercase tracking-wider text-text-muted">
          {ru ? "2 · Как расходится по миру" : "2 · How it spreads"}
        </div>
        <div className="space-y-1.5">
          {story.waves.map((w) => (
            <div key={w.week} className="flex gap-2.5 text-[13px]">
              <span className="shrink-0 w-20 text-accent-cyan font-semibold">{wk(w.week)}</span>
              <span className="text-text-secondary leading-snug">
                {w.nodes.slice(0, 4).map((id) => nodeName(id, lang)).join(", ")}
                {w.nodes.length > 4 &&
                  (ru ? ` и ещё ${w.nodes.length - 4}` : ` and ${w.nodes.length - 4} more`)}
              </span>
            </div>
          ))}
        </div>
        <p className="text-[13px] text-text-muted leading-relaxed">
          {ru
            ? `Всего затронуто ${story.countries} стран.`
            : `${story.countries} countries are affected in total.`}
        </p>
      </div>

      {/* 3 — why these places: the path the shock travelled */}
      {transmission && (
        <div className="rounded-lg border border-border-subtle bg-bg-base/40 p-3 space-y-2">
          <div className="text-[12px] uppercase tracking-wider text-text-muted">
            {ru ? "3 · Почему именно эти страны" : "3 · Why these places"}
          </div>
          <p className="text-[13px] text-text-muted leading-relaxed">
            {ru
              ? "Через какого поставщика удар дошёл до каждого узла — путь по графу зависимостей:"
              : "Which supplier carried the shock to each node — the path through the dependency graph:"}
          </p>
          <div className="space-y-2">
            {story.worst.slice(0, 4).map((n) => {
              const chain = transmission.chainFor(n.id);
              const link = transmission.parent.get(n.id);
              if (chain.length < 2) return null;
              return (
                <div key={n.id} className="space-y-0.5">
                  <div className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[13px] leading-snug">
                    {chain.map((id, i) => (
                      <span key={id} className="flex items-center gap-1.5">
                        {i > 0 && <span className="text-accent-cyan" aria-hidden="true">→</span>}
                        <span
                          className={
                            i === chain.length - 1
                              ? "text-text-primary font-semibold"
                              : "text-text-secondary"
                          }
                          title={id}
                        >
                          {nodeName(id, lang)}
                        </span>
                      </span>
                    ))}
                  </div>
                  {link && (
                    <p className="text-[12px] text-text-muted leading-snug">
                      {/* Two facts, deliberately joined by "and" rather than a
                          causal clause. Putting the dependency share next to the
                          lag invites the reading that the share explains the lag,
                          and measurement says it does not: across the 18 nodes
                          the flagship run reaches, onset week correlates with
                          dependency share at rho +0.20, CI [-0.30, +0.66] — the
                          interval spans zero, and the sign is the OPPOSITE of the
                          -0.45 the old comment here asserted with no artifact
                          behind it. See backend/scripts/onset_drivers.py.
                          The closing clause is gone too: "the timing is set by
                          the node's whole position in the network" was a
                          mechanism claim, and no pair of candidate drivers is
                          even distinguishable after Holm correction. */}
                      {ru
                        ? `Зависимость от этого поставщика — ${pct(link.share)} входа, и удар дошёл на ${link.lagWeeks}-й нед. Это два факта об одном прогоне, а не объяснение: доля зависимости и неделя прихода связаны слабо (ρ=+0,20, ДИ [−0,30; +0,66]).`
                        : `${pct(link.share)} of this node's input runs through that supplier, and the disruption arrived in week ${link.lagWeeks}. Those are two facts about one run, not an explanation: dependency share and onset week are barely related (rho +0.20, CI [-0.30, +0.66]).`}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 4 — the worst of it, ranked (ordering is the validated claim, not the %) */}
      <div className="rounded-lg border border-border-subtle bg-bg-base/40 p-3 space-y-2">
        <div className="text-[12px] uppercase tracking-wider text-text-muted">
          {ru ? "4 · Пик кризиса" : "4 · The worst of it"}
        </div>
        <p className="text-[13px] text-text-secondary leading-relaxed">
          {ru
            ? `Тяжелее всего становится на ${story.peakWeek}-й неделе. Порядок по тяжести:`
            : `The peak arrives in week ${story.peakWeek}. Ranked by severity:`}
        </p>
        <div className="space-y-1">
          {story.worst.map((n, i) => (
            <div key={n.id} className="flex items-center justify-between gap-2 text-[13px]">
              <span className="flex min-w-0 items-center gap-2">
                <span
                  className="shrink-0 w-5 h-5 grid place-items-center rounded text-[11px] font-bold
                             bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/30"
                  aria-hidden="true"
                >
                  {i + 1}
                </span>
                <span className="truncate text-text-secondary" title={n.id}>
                  {nodeName(n.id, lang)}
                </span>
              </span>
              <span className="num shrink-0 text-text-muted" title={ru
                ? "Точное значение — ориентир; надёжен порядок, а не число"
                : "The figure is indicative; the ranking is what holds, not the number"}>
                ≈ −{pct(n.output_loss)}
              </span>
            </div>
          ))}
        </div>
        <p className="text-[12px] text-text-muted leading-snug">
          {ru
            ? "Номер слева — то, что модель предсказывает надёжно. Процент справа — ориентир: на точных значениях модель не точнее наивного среднего."
            : "The number on the left is what the model predicts reliably. The percentage on the right is indicative: on exact values the model is no better than a naive mean."}
        </p>
      </div>

      {/* 4 — aftermath */}
      <div className="rounded-lg border border-border-subtle bg-bg-base/40 p-3 space-y-1.5">
        <div className="text-[12px] uppercase tracking-wider text-text-muted">
          {ru ? "5 · Чем заканчивается" : "5 · How it ends"}
        </div>
        <p className="text-[13px] text-text-secondary leading-relaxed">
          {ru ? (
            <>
              К {story.last.week}-й неделе общая тяжесть по сети падает с{" "}
              <b className="text-text-primary">{story.peak.csi.toFixed(3)}</b> до{" "}
              <b className="text-text-primary">{story.last.csi.toFixed(3)}</b> — это шкала
              от 0 (всё в порядке) до 1 (полный коллапс мировой сети), поэтому даже
              крупный кризис даёт сотые доли. Полное
              восстановление сети — около{" "}
              <b className="text-text-primary">{summary.global_recovery_weeks.toFixed(0)} нед.</b>{" "}
              Наибольший рост цен ожидается в стране{" "}
              <b className="text-text-primary">
                {countryName(summary.max_inflation_country[0], lang)}
              </b>
              .
            </>
          ) : (
            <>
              By week {story.last.week} network-wide severity falls from{" "}
              <b className="text-text-primary">{story.peak.csi.toFixed(3)}</b> to{" "}
              <b className="text-text-primary">{story.last.csi.toFixed(3)}</b> — on a scale
              from 0 (nothing wrong) to 1 (total global collapse), so even a major crisis
              lands in the hundredths. Full network
              recovery takes about{" "}
              <b className="text-text-primary">
                {summary.global_recovery_weeks.toFixed(0)} weeks
              </b>
              . The sharpest price pressure lands on{" "}
              <b className="text-text-primary">
                {countryName(summary.max_inflation_country[0], lang)}
              </b>
              .
            </>
          )}
        </p>
      </div>

      {/* honesty note — the paper's own finding, stated where the forecast is read */}
      <p className="text-[12px] text-text-muted leading-relaxed border-t border-border-subtle pt-2">
        {ru
          ? "Как это читать: модель надёжна в порядке событий — что пострадает сильнее и что дольше восстановится. В точных процентах она не точнее простых бейслайнов (см. страницу валидации)."
          : "How to read this: the model is reliable about ordering — what gets hit harder and what recovers longer. On exact percentages it is no better than simple baselines (see the validation page)."}
      </p>
    </section>
  );
}
