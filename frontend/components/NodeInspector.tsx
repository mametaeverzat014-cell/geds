"use client";

import { useEffect, useMemo, useRef, type ReactNode } from "react";

import { severityColor } from "@/lib/colors";
import { countryName, industryName, nodeName } from "@/lib/names";
import { useSimStore } from "@/lib/store";
import type { Frame, GraphNode, GraphSnapshot } from "@/lib/types";
import { useUI, type Lang } from "@/lib/ui-context";

/**
 * "Why did this node break?" — read strictly off model state.
 *
 * Everything in this panel is arithmetic over the graph and the frames that are
 * already in the store: first crossing, peak, recovery, inbound dependency
 * shares, and whether each supplier was itself disrupted. The prose block at the
 * bottom is assembled from those same values by template. There is no narrative
 * layer and no causal claim: the panel reports what co-occurred in the run, and
 * says so explicitly, because a co-occurrence is all the numbers establish.
 */

/** Below this an output loss is treated as "the shock did not arrive here". */
const REACH = 0.01;
/** "Recovered" = back down to a tenth of this node's own peak. */
const RECOVERY_FRACTION = 0.1;
const TOP_SUPPLIERS = 3;

/**
 * Onset-driver correlations, transcribed from
 * backend/data/calibration/onset_drivers.json.
 *
 * Pinned by backend/tests/test_onset_drivers.py, which reads both this file and
 * the artifact and fails if they disagree. The previous version of these numbers
 * lived only in a source comment, had no artifact behind it, and turned out to
 * have the WRONG SIGN on dependency share: it displayed -0.45 where measurement
 * gives +0.20.
 */
const ONSET = {
  n: 18,
  neverReached: 21,
  horizon: 52,
  minHolm: "0.138",
  collinear: "-0.68",
  drivers: [
    { en: "vulnerability", ru: "уязвимость", rho: "-0.66", lo: "-0.84", hi: "-0.34" },
    { en: "inventory depth", ru: "глубина запасов", rho: "-0.46", lo: "-0.81", hi: "+0.01" },
    { en: "centrality", ru: "центральность", rho: "-0.28", lo: "-0.69", hi: "+0.22" },
    { en: "dependency share", ru: "доля зависимости", rho: "+0.20", lo: "-0.30", hi: "+0.66" },
  ],
} as const;

interface Point {
  week: number;
  loss: number;
}

interface SupplierRow {
  id: string;
  weight: number;
  /** Fraction of this node's total inbound dependency weight; null if that total is 0. */
  share: number | null;
  peakLoss: number;
  onsetWeek: number | null;
  disrupted: boolean;
}

interface Report {
  node: GraphNode | null;
  centrality: number | null;
  hasFrames: boolean;
  lastWeek: number | null;
  reached: boolean;
  onsetWeek: number | null;
  peakLoss: number;
  peakWeek: number | null;
  recoveryWeek: number | null;
  suppliers: SupplierRow[];
  inboundCount: number;
  disruptedTop: SupplierRow[];
  disruptedTopShare: number | null;
}

function seriesFor(frames: Frame[], id: string): Point[] {
  const out: Point[] = [];
  for (const f of frames) {
    const nf = f.nodes.find((n) => n.id === id);
    if (nf && Number.isFinite(nf.output_loss)) out.push({ week: f.week, loss: nf.output_loss });
  }
  return out;
}

function summarise(series: Point[]): {
  onsetWeek: number | null;
  peakLoss: number;
  peakWeek: number | null;
} {
  let onsetWeek: number | null = null;
  let peakLoss = 0;
  let peakWeek: number | null = null;
  for (const p of series) {
    if (onsetWeek === null && p.loss >= REACH) onsetWeek = p.week;
    if (p.loss > peakLoss) {
      peakLoss = p.loss;
      peakWeek = p.week;
    }
  }
  return { onsetWeek, peakLoss, peakWeek };
}

function buildReport(graph: GraphSnapshot | null, frames: Frame[], nodeId: string): Report {
  const node = graph?.nodes.find((n) => n.id === nodeId) ?? null;

  const rawCentrality = graph?.centrality?.[nodeId];
  const centrality =
    typeof rawCentrality === "number" && Number.isFinite(rawCentrality) ? rawCentrality : null;

  const series = seriesFor(frames, nodeId);
  const { onsetWeek, peakLoss, peakWeek } = summarise(series);
  const reached = onsetWeek !== null;

  // Recovery is measured against this node's own peak, and only after that peak.
  let recoveryWeek: number | null = null;
  if (reached && peakWeek !== null && peakLoss > 0) {
    const floor = peakLoss * RECOVERY_FRACTION;
    for (const p of series) {
      if (p.week > peakWeek && p.loss <= floor) {
        recoveryWeek = p.week;
        break;
      }
    }
  }

  // Edge direction: source is the SUPPLIER, target is the customer. Inbound
  // dependencies of this node are therefore the edges whose target is this node.
  // Parallel edges are summed so one supplier appears once.
  const inbound = new Map<string, number>();
  for (const e of graph?.edges ?? []) {
    if (e.target !== nodeId) continue;
    const w = Number.isFinite(e.dependency_weight) ? e.dependency_weight : 0;
    inbound.set(e.source, (inbound.get(e.source) ?? 0) + w);
  }
  let total = 0;
  inbound.forEach((w) => {
    total += w;
  });

  const suppliers: SupplierRow[] = Array.from(inbound.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, TOP_SUPPLIERS)
    .map(([id, weight]) => {
      const s = summarise(seriesFor(frames, id));
      return {
        id,
        weight,
        share: total > 0 ? weight / total : null,
        peakLoss: s.peakLoss,
        onsetWeek: s.onsetWeek,
        disrupted: s.onsetWeek !== null,
      };
    });

  const disruptedTop = suppliers.filter((s) => s.disrupted);
  const shares = disruptedTop.map((s) => s.share).filter((v): v is number => v !== null);
  const disruptedTopShare =
    disruptedTop.length > 0 && shares.length === disruptedTop.length
      ? shares.reduce((a, b) => a + b, 0)
      : null;

  return {
    node,
    centrality,
    hasFrames: frames.length > 0,
    lastWeek: series.length > 0 ? series[series.length - 1].week : null,
    reached,
    onsetWeek,
    peakLoss,
    peakWeek,
    recoveryWeek,
    suppliers,
    inboundCount: inbound.size,
    disruptedTop,
    disruptedTopShare,
  };
}

const pct1 = (v: number) => `${(v * 100).toFixed(1)}%`;

/**
 * The explanation. Every sentence is a restatement of a number computed above —
 * no clause asserts that one value produced another.
 */
function buildExplanation(r: Report, nodeId: string, lang: Lang): string[] {
  const ru = lang === "ru";
  const lines: string[] = [];
  const label = (id: string) => nodeName(id, lang);

  if (!r.hasFrames) {
    lines.push(
      ru
        ? "В этой сессии симуляция не запускалась, поэтому понедельного состояния для этого узла нет."
        : "No simulation has been run in this session, so there is no per-week state for this node.",
    );
    return lines;
  }

  // ── timing ────────────────────────────────────────────────────────────────
  if (!r.reached) {
    lines.push(
      ru
        ? `Потери выпуска в этом узле ни разу не достигают 1% в смоделированном окне; максимум за окно — ${pct1(r.peakLoss)}.`
        : `Output loss at this node never reaches 1% in the simulated window; the maximum recorded is ${pct1(r.peakLoss)}.`,
    );
  } else if (r.peakWeek !== null && r.onsetWeek !== null) {
    lines.push(
      ru
        ? `Потери выпуска впервые достигают 1% на неделе ${r.onsetWeek} и доходят до максимума ${pct1(r.peakLoss)} на неделе ${r.peakWeek}.`
        : `Output loss first reaches 1% in week ${r.onsetWeek} and peaks at ${pct1(r.peakLoss)} in week ${r.peakWeek}.`,
    );
    if (r.recoveryWeek !== null) {
      lines.push(
        ru
          ? `К неделе ${r.recoveryWeek} значение опускается до 10% от этого максимума или ниже.`
          : `By week ${r.recoveryWeek} it is back to 10% of that peak or below.`,
      );
    } else {
      lines.push(
        ru
          ? `До конца смоделированного окна${r.lastWeek !== null ? ` (неделя ${r.lastWeek})` : ""} значение остаётся выше 10% от этого максимума.`
          : `It is still above 10% of that peak at the end of the simulated window${r.lastWeek !== null ? ` (week ${r.lastWeek})` : ""}.`,
      );
    }
  }

  // ── inbound dependencies ──────────────────────────────────────────────────
  if (r.inboundCount === 0) {
    lines.push(
      ru
        ? "В графе у этого узла нет входящих зависимостей."
        : "The graph records no inbound dependencies for this node.",
    );
  } else if (r.disruptedTop.length === 0) {
    lines.push(
      ru
        ? `Ни один из ${r.suppliers.length} крупнейших поставщиков этого узла не показывает потери выпуска в 1% и выше в этом прогоне.`
        : `None of its ${r.suppliers.length} largest inbound suppliers record an output loss of 1% or more in this run.`,
    );
  } else {
    const names = r.disruptedTop.map((s) => label(s.id)).join(ru ? ", " : ", ");
    const shareClause =
      r.disruptedTopShare !== null
        ? ru
          ? ` — суммарно ${pct1(r.disruptedTopShare)} всей входящей зависимости этого узла`
          : `, together ${pct1(r.disruptedTopShare)} of this node's total inbound dependency weight`
        : "";
    lines.push(
      ru
        ? `${r.disruptedTop.length} из ${r.suppliers.length} крупнейших поставщиков этого узла также показывают потери выпуска не менее 1% в этом прогоне (${names})${shareClause}.`
        : `${r.disruptedTop.length} of its ${r.suppliers.length} largest inbound suppliers also record an output loss of 1% or more in this run (${names})${shareClause}.`,
    );

    // Purely temporal ordering between two measured onsets.
    const lead = r.disruptedTop[0];
    if (lead.onsetWeek !== null && r.onsetWeek !== null) {
      const d = r.onsetWeek - lead.onsetWeek;
      if (d > 0) {
        lines.push(
          ru
            ? `Крупнейший из них, ${label(lead.id)}, достигает 1% на неделе ${lead.onsetWeek} — на ${d} нед. раньше этого узла.`
            : `The largest of them, ${label(lead.id)}, reaches 1% in week ${lead.onsetWeek}, ${d} ${d === 1 ? "week" : "weeks"} before this node does.`,
        );
      } else if (d === 0) {
        lines.push(
          ru
            ? `Крупнейший из них, ${label(lead.id)}, достигает 1% на той же неделе, что и этот узел.`
            : `The largest of them, ${label(lead.id)}, reaches 1% in the same week as this node.`,
        );
      } else {
        lines.push(
          ru
            ? `Крупнейший из них, ${label(lead.id)}, достигает 1% на неделе ${lead.onsetWeek} — на ${-d} нед. позже этого узла.`
            : `The largest of them, ${label(lead.id)}, reaches 1% in week ${lead.onsetWeek}, ${-d} ${-d === 1 ? "week" : "weeks"} after this node does.`,
        );
      }
    }
  }

  // ── the standing non-claim ────────────────────────────────────────────────
  lines.push(
    ru
      ? "Это совпадения в состоянии модели за один прогон. Панель не устанавливает причину."
      : "These are co-occurrences in the model state for one run. This panel does not identify a cause.",
  );

  return lines;
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5">
      <span className="text-[12px] text-text-muted shrink-0">{label}</span>
      <span className="text-[13px] text-text-primary num text-right min-w-0 truncate">
        {children}
      </span>
    </div>
  );
}

export interface NodeInspectorProps {
  nodeId: string | null;
  onClose: () => void;
}

export default function NodeInspector({ nodeId, onClose }: NodeInspectorProps) {
  const graph = useSimStore((s) => s.graph);
  const frames = useSimStore((s) => s.frames);
  const { lang } = useUI();
  const ru = lang === "ru";

  const panelRef = useRef<HTMLDivElement | null>(null);
  const restoreRef = useRef<HTMLElement | null>(null);

  const report = useMemo(
    () => (nodeId ? buildReport(graph, frames, nodeId) : null),
    [graph, frames, nodeId],
  );

  // Escape closes, from anywhere on the page.
  useEffect(() => {
    if (!nodeId) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [nodeId, onClose]);

  // Focus moves into the panel on open and back to the opener on close. No trap:
  // Tab walks out of the panel normally, which is the point — this is a
  // non-modal slide-over, not a dialog that holds the keyboard hostage.
  useEffect(() => {
    if (!nodeId) return;
    restoreRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const raf = window.requestAnimationFrame(() => panelRef.current?.focus());
    return () => {
      window.cancelAnimationFrame(raf);
      const prev = restoreRef.current;
      restoreRef.current = null;
      if (prev && document.contains(prev)) prev.focus();
    };
  }, [nodeId]);

  if (!nodeId || !report) return null;

  const { node } = report;
  const title = nodeName(nodeId, lang);
  const explanation = buildExplanation(report, nodeId, lang);
  const weekLabel = (w: number) => (ru ? `неделя ${w}` : `week ${w}`);

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-black/50 sm:bg-black/30 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden="true"
      />

      <div
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="false"
        aria-labelledby="node-inspector-title"
        className="fade-up fixed z-50 flex flex-col bg-bg-elevated shadow-2xl outline-none
                   inset-x-0 bottom-0 max-h-[85vh] rounded-t-2xl border-t border-border-strong
                   sm:inset-x-auto sm:right-0 sm:top-0 sm:bottom-0 sm:max-h-none
                   sm:w-[440px] sm:max-w-[95vw] sm:rounded-t-none sm:border-t-0 sm:border-l"
      >
        {/* header */}
        <div className="flex items-start justify-between gap-3 px-5 py-4 border-b border-border-subtle shrink-0">
          <div className="min-w-0">
            <div className="text-[11px] font-bold uppercase tracking-widest text-text-muted">
              {ru ? "Инспектор узла" : "Node inspector"}
            </div>
            <h2
              id="node-inspector-title"
              className="font-display text-[17px] font-bold text-text-primary leading-tight truncate mt-0.5"
            >
              {title}
            </h2>
            <div className="num text-[11px] text-text-muted truncate mt-0.5">{nodeId}</div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={ru ? "Закрыть панель узла" : "Close node panel"}
            className="btn-pill shrink-0"
          >
            {ru ? "Закрыть" : "Close"} ✕
          </button>
        </div>

        {/* scrollable body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {!node ? (
            <p className="text-[13px] text-text-secondary leading-relaxed">
              {ru
                ? "Этого узла нет в загруженном графе, поэтому его свойства недоступны."
                : "This node is not present in the loaded graph, so its properties are unavailable."}
            </p>
          ) : (
            <section className="fade-up fade-up-1">
              <h3 className="text-[11px] font-bold uppercase tracking-widest text-text-muted mb-1 pb-1 border-b border-border-subtle">
                {ru ? "Свойства узла" : "Node properties"}
              </h3>
              {node.country ? (
                <Row label={ru ? "Страна" : "Country"}>{countryName(node.country, lang)}</Row>
              ) : null}
              {node.industry ? (
                <Row label={ru ? "Отрасль" : "Industry"}>{industryName(node.industry, lang)}</Row>
              ) : null}
              {report.centrality !== null ? (
                <Row label={ru ? "Центральность" : "Centrality"}>
                  {report.centrality.toFixed(3)}
                </Row>
              ) : null}
              {Number.isFinite(node.vulnerability) ? (
                <Row label={ru ? "Уязвимость" : "Vulnerability"}>
                  {node.vulnerability.toFixed(2)}
                </Row>
              ) : null}
              {Number.isFinite(node.resilience) ? (
                <Row label={ru ? "Устойчивость" : "Resilience"}>{node.resilience.toFixed(2)}</Row>
              ) : null}
              {Number.isFinite(node.recovery_delay_weeks) ? (
                <Row label={ru ? "Задержка восстановления" : "Recovery delay"}>
                  {node.recovery_delay_weeks} {ru ? "нед." : "wk"}
                </Row>
              ) : null}
            </section>
          )}

          {/* ── timeline ─────────────────────────────────────────────────── */}
          <section className="fade-up fade-up-2">
            <h3 className="text-[11px] font-bold uppercase tracking-widest text-text-muted mb-2 pb-1 border-b border-border-subtle">
              {ru ? "Ход в этом прогоне" : "Course of this run"}
            </h3>

            {!report.hasFrames ? (
              <p className="text-[13px] text-text-secondary leading-relaxed">
                {ru
                  ? "Кадры симуляции ещё не загружены."
                  : "No simulation frames are loaded yet."}
              </p>
            ) : (
              <>
                <div className="flex items-end gap-3 mb-3">
                  <div
                    className="num text-3xl font-bold leading-none"
                    style={{ color: severityColor(Math.min(1, report.peakLoss)) }}
                  >
                    {pct1(report.peakLoss)}
                  </div>
                  <div className="text-[12px] text-text-muted leading-tight pb-0.5">
                    {ru ? "пиковые потери выпуска" : "peak output loss"}
                    {report.peakWeek !== null ? (
                      <>
                        <br />
                        <span className="num">{weekLabel(report.peakWeek)}</span>
                      </>
                    ) : null}
                  </div>
                </div>

                <Row label={ru ? "Шок доходит" : "Shock arrives"}>
                  {report.onsetWeek !== null ? (
                    weekLabel(report.onsetWeek)
                  ) : (
                    <span className="text-text-muted">
                      {ru ? "не достигнут" : "never reached"}
                    </span>
                  )}
                </Row>

                {report.reached ? (
                  <Row label={ru ? "Возврат к ≤10% пика" : "Back to ≤10% of peak"}>
                    {report.recoveryWeek !== null ? (
                      weekLabel(report.recoveryWeek)
                    ) : (
                      <span className="text-accent-gold">
                        {ru ? "не в пределах окна" : "not within the window"}
                      </span>
                    )}
                  </Row>
                ) : null}

                {report.lastWeek !== null ? (
                  <Row label={ru ? "Окно симуляции" : "Simulated window"}>
                    {ru ? `до недели ${report.lastWeek}` : `through week ${report.lastWeek}`}
                  </Row>
                ) : null}
              </>
            )}
          </section>

          {/* ── suppliers ────────────────────────────────────────────────── */}
          <section className="fade-up fade-up-3">
            <h3 className="text-[11px] font-bold uppercase tracking-widest text-text-muted mb-2 pb-1 border-b border-border-subtle">
              {ru ? "Крупнейшие поставщики" : "Top inbound suppliers"}
            </h3>

            {report.inboundCount === 0 ? (
              <p className="text-[13px] text-text-secondary leading-relaxed">
                {ru
                  ? "В графе у этого узла нет входящих зависимостей."
                  : "The graph records no inbound dependencies for this node."}
              </p>
            ) : (
              <div className="space-y-3">
                {report.suppliers.map((s) => (
                  <div key={s.id} className="min-w-0">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-[13px] text-text-primary truncate min-w-0">
                        {nodeName(s.id, lang)}
                      </span>
                      <span className="num text-[13px] text-text-primary shrink-0">
                        {s.share !== null ? pct1(s.share) : s.weight.toFixed(3)}
                      </span>
                    </div>

                    <div className="h-1.5 rounded-sm bg-border-subtle overflow-hidden mt-1.5">
                      <div
                        className="h-full rounded-sm transition-[width] duration-500"
                        style={{
                          width: `${Math.max(2, Math.min(100, (s.share ?? 0) * 100))}%`,
                          background: s.disrupted
                            ? severityColor(Math.min(1, s.peakLoss))
                            : "#2A3140",
                        }}
                      />
                    </div>

                    <div className="flex items-center justify-between gap-2 mt-1">
                      <span className="text-[11px] text-text-muted">
                        {s.share !== null
                          ? ru
                            ? "доля входящей зависимости"
                            : "share of inbound dependency"
                          : ru
                            ? "вес зависимости"
                            : "dependency weight"}
                      </span>
                      {s.disrupted ? (
                        <span className="num text-[11px] text-accent-gold shrink-0">
                          {ru ? "нарушен" : "disrupted"} · {pct1(s.peakLoss)}
                          {s.onsetWeek !== null ? ` · ${ru ? "нед." : "wk"} ${s.onsetWeek}` : ""}
                        </span>
                      ) : (
                        <span className="text-[11px] text-text-muted shrink-0">
                          {report.hasFrames
                            ? ru
                              ? "не нарушен"
                              : "not disrupted"
                            : ru
                              ? "нет данных"
                              : "no run data"}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* ── generated explanation ────────────────────────────────────── */}
          <section className="panel p-3.5">
            <h3 className="text-[11px] font-bold uppercase tracking-widest text-text-muted mb-2">
              {ru ? "Собрано из чисел выше" : "Assembled from the numbers above"}
            </h3>
            <div className="space-y-2">
              {explanation.map((line, i) => (
                <p
                  key={i}
                  className={
                    i === explanation.length - 1
                      ? "text-[12px] text-text-muted leading-relaxed"
                      : "text-[13px] text-text-secondary leading-relaxed"
                  }
                >
                  {line}
                </p>
              ))}
            </div>
          </section>

          {/* ── the timing caveat ────────────────────────────────────────── */}
          <section className="rounded-lg border border-border-subtle bg-bg-base/40 p-3.5">
            <h3 className="text-[11px] font-bold uppercase tracking-widest text-text-muted mb-2">
              {ru ? "О сроках" : "On timing"}
            </h3>
            <p className="text-[12px] text-text-secondary leading-relaxed">
              {ru
                ? `Ни одно свойство узла по отдельности не объясняет время прихода. Корреляции Спирмена недели прихода с кандидатами, n=${ONSET.n} узлов:`
                : `No single node property explains when the shock arrives. Spearman correlations of onset week against each candidate, n=${ONSET.n} nodes:`}
            </p>
            <div className="space-y-1 my-2">
              {ONSET.drivers.map((d) => (
                <div key={d.en} className="flex items-baseline justify-between gap-2 min-w-0">
                  <span className="text-[11px] text-text-muted truncate">{ru ? d.ru : d.en}</span>
                  <span className="num text-[12px] shrink-0 tabular-nums">
                    <span className="text-text-primary">{d.rho}</span>
                    <span className="text-text-muted"> [{d.lo}, {d.hi}]</span>
                  </span>
                </div>
              ))}
            </div>
            {/* Two things stood here before and both were wrong.
                The numbers came from a source comment with no artifact behind
                them, and measuring the same quantity puts dependency share at
                +0.20 — the opposite sign to the -0.45 that was displayed. The
                closing line ("the timing falls out of the whole propagation
                step") turned a negative finding into a mechanism claim, which
                this same panel disclaims two hundred lines up. Four
                similarly-sized coefficients are equally consistent with the
                candidates being collinear or with an unmeasured fifth driver.
                scripts/onset_drivers.py measures it properly now: paired
                bootstrap on the same nodes, Holm across all six pairs. */}
            <p className="text-[12px] text-text-secondary leading-relaxed">
              {ru
                ? `Ни одна пара кандидатов не различима после поправки Холма (наименьшее p=${ONSET.minHolm}), поэтому утверждать «уязвимость важнее» здесь нельзя. Доля зависимости и уязвимость к тому же коллинеарны (ρ=${ONSET.collinear}) — на таком n их не разделить.`
                : `No pair of these is distinguishable after Holm correction (smallest p=${ONSET.minHolm}), so "vulnerability matters most" is not a claim this supports. Dependency share and vulnerability are also collinear (rho ${ONSET.collinear}), which at this n cannot be untangled.`}
            </p>
            <p className="text-[11px] text-text-muted leading-relaxed mt-1.5">
              {ru
                ? `Один прогон флагманского сценария на графе v2. Из 41 узла оценены ${ONSET.n}: ${ONSET.neverReached} ни разу не достигнуты за ${ONSET.horizon} нед. и исключены, а не подставлены горизонтом; ещё 2 — точки шока. Воспроизводится: python -m scripts.onset_drivers`
                : `One flagship run on the v2 graph. ${ONSET.n} of 41 nodes scored: ${ONSET.neverReached} are never reached inside ${ONSET.horizon} weeks and are excluded rather than imputed at the horizon, and 2 are shock origins. Reproduce: python -m scripts.onset_drivers`}
            </p>
          </section>
        </div>
      </div>
    </>
  );
}
