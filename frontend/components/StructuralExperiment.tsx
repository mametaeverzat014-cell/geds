"use client";

import { useMemo, useState } from "react";
import { useUI } from "@/lib/ui-context";

/**
 * StructuralExperiment — the project's strongest positive result.
 *
 * Same engine, same shocks, same parameters; only the graph changes. Two
 * schematics (v2 hand-authored vs v3 OECD ICIO 2019) with their pooled spatial
 * recall, plus the full seven-threshold robustness sweep so the reader can see
 * that v3 leads everywhere and the result is not an artifact of one cutoff.
 *
 * Presentational only — no store, no fetch. Every number below is a constant
 * transcribed from the frozen artifacts.
 */

// ── canonical data ───────────────────────────────────────────────────────────

type Marker = "published" | "scale" | null;

interface SweepRow {
  readonly label: string;
  readonly v2: number;
  readonly v2Hit: number;
  readonly v2Of: number;
  readonly v3: number;
  readonly v3Hit: number;
  readonly v3Of: number;
  readonly mark: Marker;
}

const SWEEP: readonly SweepRow[] = [
  { label: "0.001",  v2: 0.571, v2Hit: 20, v2Of: 35, v3: 0.895, v3Hit: 34, v3Of: 38, mark: null },
  { label: "0.005",  v2: 0.400, v2Hit: 14, v2Of: 35, v3: 0.816, v3Hit: 31, v3Of: 38, mark: null },
  { label: "0.01",   v2: 0.286, v2Hit: 10, v2Of: 35, v3: 0.789, v3Hit: 30, v3Of: 38, mark: "published" },
  { label: "0.02",   v2: 0.171, v2Hit: 6,  v2Of: 35, v3: 0.711, v3Hit: 27, v3Of: 38, mark: null },
  { label: "0.0388", v2: 0.143, v2Hit: 5,  v2Of: 35, v3: 0.526, v3Hit: 20, v3Of: 38, mark: "scale" },
  { label: "0.05",   v2: 0.086, v2Hit: 3,  v2Of: 35, v3: 0.474, v3Hit: 18, v3Of: 38, mark: null },
  { label: "0.10",   v2: 0.086, v2Hit: 3,  v2Of: 35, v3: 0.421, v3Hit: 16, v3Of: 38, mark: null },
];

const PUBLISHED_INDEX = 2;

const V2_NODES = 41;
const V2_EDGES = 74;
const V3_NODES = 405;
const V3_EDGES = 1964;

// ── deterministic layout ─────────────────────────────────────────────────────
//
// A fixed seed and an inline LCG keep the picture byte-identical between the
// server render and the client hydrate. Math.random is never called.

const SEED_A = 20260810;
const SEED_B = 91442071;

function lcg(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

const VB_W = 120;
const VB_H = 84;
const OX = 16; // shock origin, left-of-centre so the wave travels rightward
const OY = 42;
const MAX_D = 112; // shared distance scale => both panels run on ONE clock
const CYCLE_MS = 6000;
const SWEEP_MS = 2600; // wave-front travel time across MAX_D

interface NetNode {
  x: number;
  y: number;
  d: number; // normalised distance from origin, 0..1
}

interface NetEdge {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  a: number;
  b: number;
  d: number;
}

interface Net {
  nodes: NetNode[];
  edges: NetEdge[];
}

function buildNet(seed: number, n: number, edgeCount: number): Net {
  const rnd = lcg(seed);

  const nodes: NetNode[] = [];
  for (let i = 0; i < n; i++) {
    const x = 5 + rnd() * (VB_W - 10);
    const y = 5 + rnd() * (VB_H - 10);
    nodes.push({ x, y, d: Math.min(1, Math.hypot(x - OX, y - OY) / MAX_D) });
  }
  // Sorting by distance makes "index < litCount" == "inside the wave front".
  nodes.sort((p, q) => p.d - q.d || p.x - q.x || p.y - q.y);

  const taken = new Set<number>();
  const picked: { a: number; b: number; w: number }[] = [];
  const push = (a: number, b: number, w: number) => {
    const lo = a < b ? a : b;
    const hi = a < b ? b : a;
    const key = lo * n + hi;
    if (taken.has(key)) return;
    taken.add(key);
    picked.push({ a: lo, b: hi, w });
  };

  // Pass 1 — every node keeps its single nearest neighbour, so nothing is
  // stranded as an isolated dot.
  for (let i = 0; i < n; i++) {
    let best = -1;
    let bestW = Infinity;
    for (let j = 0; j < n; j++) {
      if (j === i) continue;
      const dx = nodes[i].x - nodes[j].x;
      const dy = nodes[i].y - nodes[j].y;
      const w = dx * dx + dy * dy;
      if (w < bestW) {
        bestW = w;
        best = j;
      }
    }
    if (best >= 0) push(i, best, bestW);
  }

  // Pass 2 — fill up to the true edge count with the shortest remaining pairs
  // found inside a growing radius (cheaper than a full O(n^2 log n) sort).
  let radius = Math.sqrt(((VB_W - 10) * (VB_H - 10) * 18) / (Math.PI * n));
  for (let attempt = 0; attempt < 8 && picked.length < edgeCount; attempt++) {
    const r2 = radius * radius;
    const cand: { a: number; b: number; w: number }[] = [];
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const dx = nodes[i].x - nodes[j].x;
        const dy = nodes[i].y - nodes[j].y;
        const w = dx * dx + dy * dy;
        if (w <= r2) cand.push({ a: i, b: j, w });
      }
    }
    cand.sort((p, q) => p.w - q.w || p.a - q.a || p.b - q.b);
    for (const c of cand) {
      if (picked.length >= edgeCount) break;
      push(c.a, c.b, c.w);
    }
    radius *= 1.6;
  }

  const edges: NetEdge[] = picked.slice(0, edgeCount).map((e) => ({
    x1: nodes[e.a].x,
    y1: nodes[e.a].y,
    x2: nodes[e.b].x,
    y2: nodes[e.b].y,
    a: e.a,
    b: e.b,
    d: Math.max(nodes[e.a].d, nodes[e.b].d),
  }));

  return { nodes, edges };
}

// ── schematic ────────────────────────────────────────────────────────────────

function Schematic({
  net,
  litCount,
  variant,
  label,
}: {
  net: Net;
  litCount: number;
  variant: "a" | "b";
  label: string;
}) {
  const nr = variant === "a" ? 1.55 : 0.78;
  const ew = variant === "a" ? 0.34 : 0.13;

  return (
    <svg
      viewBox={`0 0 ${VB_W} ${VB_H}`}
      className="block h-auto w-full"
      role="img"
      aria-label={label}
    >
      {/* Remounting on litCount replays the sweep whenever the reader picks a
          new threshold, so the selection has a visible consequence. */}
      <g key={litCount}>
        {net.edges.map((e, i) => {
          const on = e.a < litCount && e.b < litCount;
          return (
            <line
              key={i}
              x1={e.x1}
              y1={e.y1}
              x2={e.x2}
              y2={e.y2}
              strokeWidth={ew}
              strokeLinecap="round"
              className={on ? `se-e-${variant}` : "se-e-off"}
              style={on ? { animationDelay: `${Math.round(e.d * SWEEP_MS)}ms` } : undefined}
            />
          );
        })}
        {net.nodes.map((p, i) => {
          const on = i < litCount;
          return (
            <circle
              key={i}
              cx={p.x}
              cy={p.y}
              r={nr}
              className={on ? `se-n-${variant}` : "se-n-off"}
              style={on ? { animationDelay: `${Math.round(p.d * SWEEP_MS)}ms` } : undefined}
            />
          );
        })}
        <circle
          className={`se-ring se-ring-${variant}`}
          cx={OX}
          cy={OY}
          r={1}
          fill="none"
          strokeWidth={0.9}
          vectorEffect="non-scaling-stroke"
        />
        <circle cx={OX} cy={OY} r={variant === "a" ? 2.6 : 2.1} className="se-origin" />
      </g>
    </svg>
  );
}

// ── component ────────────────────────────────────────────────────────────────

export default function StructuralExperiment() {
  const { lang } = useUI();
  const ru = lang === "ru";
  const tr = (en: string, rus: string) => (ru ? rus : en);

  const [sel, setSel] = useState(PUBLISHED_INDEX);
  const row = SWEEP[sel];

  const netA = useMemo(() => buildNet(SEED_A, V2_NODES, V2_EDGES), []);
  const netB = useMemo(() => buildNet(SEED_B, V3_NODES, V3_EDGES), []);

  const litA = Math.round(row.v2 * V2_NODES);
  const litB = Math.round(row.v3 * V3_NODES);
  const delta = (row.v3 - row.v2).toFixed(3);

  const panels = [
    {
      key: "a" as const,
      tag: "A",
      name: tr("Network A — v2, hand-authored", "Сеть A — v2, собрана вручную"),
      version: "v2",
      nodes: V2_NODES,
      edges: V3_EDGES && V2_EDGES,
      composition: tr(
        "12 countries × 6 industries + 5 chokepoints",
        "12 стран × 6 отраслей + 5 узких мест",
      ),
      source: tr("Hand-authored map", "Карта, собранная вручную"),
      recall: row.v2,
      hit: row.v2Hit,
      of: row.v2Of,
      lit: litA,
      net: netA,
      color: "#7C6CFB",
    },
    {
      key: "b" as const,
      tag: "B",
      name: tr("Network B — v3, OECD ICIO 2019", "Сеть B — v3, OECD ICIO 2019"),
      version: "v3",
      nodes: V3_NODES,
      edges: V3_EDGES,
      composition: tr("81 economies × 5 sectors", "81 экономика × 5 секторов"),
      source: tr("Straight from OECD ICIO 2019", "Напрямую из OECD ICIO 2019"),
      recall: row.v3,
      hit: row.v3Hit,
      of: row.v3Of,
      lit: litB,
      net: netB,
      color: "#4DD0E1",
    },
  ];

  return (
    <section className="panel fade-up space-y-6 p-4 sm:p-6">
      <style>{`
        .se-n-off  { fill: #2A3140; opacity: .40; }
        .se-e-off  { stroke: #1A1E26; opacity: .55; }
        .se-origin { fill: #FFC34D; }

        .se-n-a { fill: #7C6CFB; opacity: 1;
                  animation: se-na ${CYCLE_MS}ms linear infinite both; }
        .se-n-b { fill: #4DD0E1; opacity: 1;
                  animation: se-nb ${CYCLE_MS}ms linear infinite both; }
        .se-e-a { stroke: #7C6CFB; opacity: .55;
                  animation: se-ea ${CYCLE_MS}ms linear infinite both; }
        .se-e-b { stroke: #4DD0E1; opacity: .30;
                  animation: se-eb ${CYCLE_MS}ms linear infinite both; }

        @keyframes se-na {
          0%, 100% { fill: #2A3140; opacity: .40; }
          6%, 80%  { fill: #7C6CFB; opacity: 1; }
          93%      { fill: #2A3140; opacity: .40; }
        }
        @keyframes se-nb {
          0%, 100% { fill: #2A3140; opacity: .40; }
          6%, 80%  { fill: #4DD0E1; opacity: 1; }
          93%      { fill: #2A3140; opacity: .40; }
        }
        @keyframes se-ea {
          0%, 100% { stroke: #1A1E26; opacity: .55; }
          6%, 80%  { stroke: #7C6CFB; opacity: .55; }
          93%      { stroke: #1A1E26; opacity: .55; }
        }
        @keyframes se-eb {
          0%, 100% { stroke: #1A1E26; opacity: .55; }
          6%, 80%  { stroke: #4DD0E1; opacity: .30; }
          93%      { stroke: #1A1E26; opacity: .55; }
        }

        /* wave front, drawn from the same origin on the same clock */
        .se-ring {
          opacity: 0;
          transform-box: view-box;
          transform-origin: ${OX}px ${OY}px;
          animation: se-ring ${CYCLE_MS}ms linear infinite both;
        }
        .se-ring-a { stroke: #7C6CFB; }
        .se-ring-b { stroke: #4DD0E1; }
        @keyframes se-ring {
          0%   { transform: scale(1);   opacity: .45; }
          43%  { transform: scale(${MAX_D}); opacity: 0; }
          100% { transform: scale(${MAX_D}); opacity: 0; }
        }

        /* Base styles above ARE the fully-propagated end state, so switching
           the animation off leaves the finished picture rather than a blank. */
        @media (prefers-reduced-motion: reduce) {
          .se-n-a, .se-n-b, .se-e-a, .se-e-b, .se-ring {
            animation: none !important;
          }
          .se-ring { opacity: 0; }
        }
      `}</style>

      {/* ── header ───────────────────────────────────────────────────────── */}
      <header className="space-y-3">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[10px] uppercase tracking-[0.16em] text-text-muted sm:text-[11px]">
          <span>{tr("Same engine", "Тот же движок")}</span>
          <span className="text-border-strong">·</span>
          <span>{tr("Same shocks", "Те же шоки")}</span>
          <span className="text-border-strong">·</span>
          <span>{tr("Same parameters", "Те же параметры")}</span>
          <span className="text-border-strong">·</span>
          <span className="text-accent-gold">
            {tr("Only the graph changes", "Меняется только граф")}
          </span>
        </div>

        <h2 className="text-xl font-extrabold tracking-tight text-text-primary sm:text-2xl">
          {tr("Structural experiment", "Структурный эксперимент")}
        </h2>

        <p className="max-w-[68ch] text-[13px] leading-relaxed text-text-secondary">
          {tr(
            "Twelve comparable production events were replayed twice. The engine, the shocks and the five fitted parameters were held fixed; the only thing swapped was the dependency graph underneath.",
            "Двенадцать сопоставимых производственных событий проиграны дважды. Движок, шоки и пять подобранных параметров зафиксированы; менялся только граф зависимостей под ними.",
          )}
        </p>
      </header>

      {/* ── the two networks ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {panels.map((p) => (
          <article
            key={p.key}
            className="rounded-xl border border-border-subtle bg-bg-base/50 p-3 sm:p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span
                    className="grid h-5 w-5 shrink-0 place-items-center rounded-md font-mono text-[11px] font-bold text-bg-base"
                    style={{ background: p.color }}
                  >
                    {p.tag}
                  </span>
                  <h3 className="truncate text-[13px] font-semibold text-text-primary">
                    {p.name}
                  </h3>
                </div>
                <p className="mt-1.5 text-[11px] text-text-muted">{p.composition}</p>
              </div>
              <div className="shrink-0 text-right">
                <div className="num text-[13px] font-semibold text-text-primary">
                  {p.nodes}
                </div>
                <div className="text-[9px] uppercase tracking-[0.14em] text-text-muted">
                  {tr("nodes", "узлов")}
                </div>
                <div className="num mt-1 text-[13px] font-semibold text-text-primary">
                  {p.edges}
                </div>
                <div className="text-[9px] uppercase tracking-[0.14em] text-text-muted">
                  {tr("edges", "связей")}
                </div>
              </div>
            </div>

            <div className="mt-3 overflow-hidden rounded-lg border border-border-subtle bg-bg-base">
              <Schematic
                net={p.net}
                litCount={p.lit}
                variant={p.key}
                label={tr(
                  `${p.version} schematic: ${p.nodes} nodes, ${p.edges} edges. A propagation wave leaves one origin and reaches ${p.hit} of ${p.of} historically hit nodes at threshold ${row.label}.`,
                  `Схема ${p.version}: ${p.nodes} узлов, ${p.edges} связей. Волна расходится из одной точки и достигает ${p.hit} из ${p.of} исторически задетых узлов при пороге ${row.label}.`,
                )}
              />
            </div>

            <div className="mt-3">
              <div className="text-[9px] uppercase tracking-[0.18em] text-text-muted">
                {tr("Pooled spatial recall", "Агрегированная пространственная полнота")}
              </div>
              <div key={sel} className="value-pop mt-1 flex flex-wrap items-baseline gap-x-3">
                <span
                  className="num text-5xl font-semibold leading-none sm:text-6xl"
                  style={{ color: p.color }}
                >
                  {p.recall.toFixed(3)}
                </span>
                <span className="num text-sm text-text-secondary">
                  {p.hit}/{p.of}
                </span>
              </div>
              <div className="num mt-2 text-[11px] text-text-muted">
                {tr("at reach threshold", "при пороге охвата")} {row.label}
              </div>
            </div>
          </article>
        ))}
      </div>

      {/* ── schematic honesty caption ────────────────────────────────────── */}
      <p className="hairline max-w-[80ch] pt-4 text-[11px] leading-relaxed text-text-muted">
        <span className="text-text-secondary">
          {tr("Reading the schematics.", "Как читать схемы.")}
        </span>{" "}
        {tr(
          "Each picture is a deterministic scatter carrying the true node and edge counts — it is a diagram, not a map of the real graph. The gold dot is one shock origin; both waves expand from it on the same clock. The share of dots that light up is the recall shown beneath: dots left dim stand for hit nodes the graph never reaches.",
          "Каждая картинка — детерминированная раскладка с настоящим числом узлов и связей: это диаграмма, а не карта реального графа. Золотая точка — одна точка шока; обе волны расходятся из неё по одним часам. Доля загорающихся точек равна полноте, указанной ниже: тусклые точки — задетые узлы, до которых граф не дотягивается.",
        )}
      </p>

      {/* ── robustness sweep ─────────────────────────────────────────────── */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
            {tr("Robustness sweep", "Проверка на устойчивость")}
          </h3>
          <p className="text-[11px] text-text-muted">
            {tr("Tap a threshold", "Нажмите на порог")}
          </p>
        </div>

        <p className="max-w-[72ch] text-[12px] leading-relaxed text-text-secondary">
          {tr(
            "v3 leads at every one of the seven thresholds, so the result does not rest on one arbitrary cutoff.",
            "v3 впереди на каждом из семи порогов — значит, результат не держится на одном произвольно выбранном отсечении.",
          )}
        </p>

        <div
          className="grid grid-cols-7 gap-1 sm:gap-2"
          role="group"
          aria-label={tr("Reach threshold", "Порог охвата")}
        >
          {SWEEP.map((r, i) => {
            const on = i === sel;
            return (
              <button
                key={r.label}
                type="button"
                onClick={() => setSel(i)}
                aria-pressed={on}
                className={`btn-option flex flex-col items-center gap-1.5 px-0.5 py-2 ${
                  on ? "is-active" : ""
                }`}
              >
                <span className="flex h-14 w-full items-end justify-center gap-[3px] sm:h-20">
                  <span
                    className="w-2 max-w-[9px] rounded-t-[2px] bg-accent-violet/80 sm:w-2.5"
                    style={{ height: `${Math.max(2, r.v2 * 100)}%` }}
                  />
                  <span
                    className="w-2 max-w-[9px] rounded-t-[2px] bg-accent-cyan sm:w-2.5"
                    style={{ height: `${Math.max(2, r.v3 * 100)}%` }}
                  />
                </span>
                <span
                  className={`num text-[8px] leading-none sm:text-[10px] ${
                    on ? "text-text-primary" : "text-text-secondary"
                  }`}
                >
                  {r.label}
                </span>
                <span className="grid h-2 place-items-center">
                  {r.mark === "published" && (
                    <span className="block h-1.5 w-1.5 rounded-full bg-accent-gold" />
                  )}
                  {r.mark === "scale" && (
                    <span className="block h-1.5 w-1.5 rounded-full border border-accent-gold" />
                  )}
                </span>
              </button>
            );
          })}
        </div>

        {/* marker legend */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[10px] text-text-muted">
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent-gold" />
            <span className="num">0.01</span>
            <span>{tr("published threshold", "опубликованный порог")}</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 shrink-0 rounded-full border border-accent-gold" />
            <span className="num">0.0388</span>
            <span>
              {tr(
                "scale-corrected — v3 runs ~4× hot, 0.01 / k with k = 0.2578",
                "с поправкой на масштаб — v3 идёт примерно в 4× «горячее», 0.01 / k при k = 0.2578",
              )}
            </span>
          </span>
        </div>

        {/* paired bar for the selected threshold */}
        <div className="space-y-2.5 rounded-xl border border-border-subtle bg-bg-base/50 p-3 sm:p-4">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <span className="num text-[11px] text-text-secondary">
              {tr("reach threshold", "порог охвата")}{" "}
              <span className="text-text-primary">{row.label}</span>
              {row.mark === "published" && (
                <span className="ml-2 text-accent-gold">
                  {tr("· published", "· опубликовано")}
                </span>
              )}
              {row.mark === "scale" && (
                <span className="ml-2 text-accent-gold">
                  {tr("· scale-corrected", "· с поправкой на масштаб")}
                </span>
              )}
            </span>
            <span className="num text-[11px] text-text-muted">
              v3 − v2 <span className="text-text-primary">+{delta}</span>
            </span>
          </div>

          {[
            {
              id: "v2",
              name: tr("A · v2 hand-authored", "A · v2 вручную"),
              value: row.v2,
              hit: row.v2Hit,
              of: row.v2Of,
              color: "#7C6CFB",
            },
            {
              id: "v3",
              name: tr("B · v3 OECD ICIO", "B · v3 OECD ICIO"),
              value: row.v3,
              hit: row.v3Hit,
              of: row.v3Of,
              color: "#4DD0E1",
            },
          ].map((b) => (
            <div key={b.id} className="flex items-center gap-2 sm:gap-3">
              <span className="w-[92px] shrink-0 truncate text-[10px] text-text-secondary sm:w-[140px] sm:text-[11px]">
                {b.name}
              </span>
              <span className="h-2.5 flex-1 overflow-hidden rounded-full border border-border-subtle bg-bg-base">
                <span
                  className="block h-full rounded-full transition-[width] duration-500 ease-out"
                  style={{ width: `${b.value * 100}%`, background: b.color }}
                />
              </span>
              <span className="num w-[46px] shrink-0 text-right text-[12px] font-semibold text-text-primary">
                {b.value.toFixed(3)}
              </span>
              <span className="num hidden w-[44px] shrink-0 text-right text-[11px] text-text-muted sm:block">
                {b.hit}/{b.of}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* ── honest notes ─────────────────────────────────────────────────── */}
      <div className="space-y-2.5 rounded-xl border border-border-subtle bg-bg-base/40 p-3 sm:p-4">
        <h4 className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
          {tr("What this does and does not show", "Что здесь показано, а что нет")}
        </h4>
        <p className="max-w-[80ch] text-[12px] leading-relaxed text-text-secondary">
          <span className="text-accent-gold">
            {tr("The denominators differ by design.", "Знаменатели различаются намеренно.")}
          </span>{" "}
          {tr(
            "Nodes that v2 cannot represent at all are excluded from its denominator rather than counted against it. That choice favours v2, so the measured gap is a conservative one.",
            "Узлы, которые v2 в принципе не может представить, исключены из её знаменателя, а не засчитаны против неё. Такой выбор работает в пользу v2, поэтому измеренный разрыв — консервативная оценка.",
          )}
        </p>
        <p className="max-w-[80ch] text-[12px] leading-relaxed text-text-muted">
          {tr(
            "Spatial recall counts which nodes a cascade reaches. It is not a magnitude score and says nothing about how large the effect is at any node.",
            "Пространственная полнота считает, до каких узлов доходит каскад. Это не мера величины эффекта и ничего не говорит о том, насколько сильным он окажется в конкретном узле.",
          )}
        </p>
        <p className="num max-w-[80ch] text-[11px] leading-relaxed text-text-muted">
          {tr(
            "12 comparable production events · same engine, shocks and parameters throughout.",
            "12 сопоставимых производственных событий · движок, шоки и параметры неизменны.",
          )}
        </p>
      </div>
    </section>
  );
}
