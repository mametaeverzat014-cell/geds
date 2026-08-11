"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { useUI } from "@/lib/ui-context";

/**
 * JUDGE MODE — the whole project in 90–120 seconds.
 *
 * Seven questions, one sentence each, one number each, one picture each. The
 * order is deliberate: what it is, what you give it, what it does, what you get
 * back, whether it is accurate (it is not — section 05 says so in the largest
 * type on the page), what it nonetheless established, and where it breaks.
 *
 * Every figure here is read from the repository's own artifacts. Nothing is
 * rounded in the project's favour, and the one number this project had to
 * withdraw is shown as a withdrawal rather than quietly deleted.
 */

// ── data (canonical; do not edit without re-reading the artifacts) ───────────

interface ModelRow {
  name: string;
  params: number;
  mae: number;
  lo: number;
  hi: number;
  worst: boolean;
}

/** Track A — point magnitude, MAE with 95% bootstrap CI. Lower is better. */
const MODELS: ModelRow[] = [
  { name: "Leontief",         params: 0, mae: 0.0168, lo: 0.0079, hi: 0.0278, worst: false },
  { name: "Linear diffusion", params: 0, mae: 0.0171, lo: 0.0089, hi: 0.0286, worst: false },
  { name: "Naive mean",       params: 0, mae: 0.0208, lo: 0.0126, hi: 0.0311, worst: false },
  { name: "GEDS",             params: 5, mae: 0.0242, lo: 0.0110, hi: 0.0402, worst: true  },
];

/** Axis maximum for the MAE bars — a drawing choice, not a measurement. */
const MAE_AXIS = 0.045;

interface RecallRow {
  thr: string;
  v2: number;
  v2n: string;
  v3: number;
  v3n: string;
  mark: "published" | "scaled" | null;
}

/** Pooled spatial recall by reach threshold: v2 hand-authored vs v3 OECD ICIO. */
const RECALL: RecallRow[] = [
  { thr: "0.001",  v2: 0.571, v2n: "20/35", v3: 0.895, v3n: "34/38", mark: null },
  { thr: "0.005",  v2: 0.400, v2n: "14/35", v3: 0.816, v3n: "31/38", mark: null },
  { thr: "0.01",   v2: 0.286, v2n: "10/35", v3: 0.789, v3n: "30/38", mark: "published" },
  { thr: "0.02",   v2: 0.171, v2n: "6/35",  v3: 0.711, v3n: "27/38", mark: null },
  { thr: "0.0388", v2: 0.143, v2n: "5/35",  v3: 0.526, v3n: "20/38", mark: "scaled" },
  { thr: "0.05",   v2: 0.086, v2n: "3/35",  v3: 0.474, v3n: "18/38", mark: null },
  { thr: "0.10",   v2: 0.086, v2n: "3/35",  v3: 0.421, v3n: "16/38", mark: null },
];

/** Section 01 network sketch: one shocked node, three rings outward. */
const NET_NODES: Array<{ x: number; y: number; r: number; c: string }> = [
  { x: 26,  y: 62, r: 9, c: "#EF4444" },
  { x: 108, y: 26, r: 6, c: "#F97316" },
  { x: 108, y: 62, r: 6, c: "#F97316" },
  { x: 108, y: 98, r: 6, c: "#FFC34D" },
  { x: 194, y: 16, r: 5, c: "#FFC34D" },
  { x: 194, y: 50, r: 5, c: "#67D6A4" },
  { x: 194, y: 84, r: 5, c: "#67D6A4" },
  { x: 194, y: 112, r: 5, c: "#2DD4BF" },
  { x: 282, y: 36, r: 4, c: "#2DD4BF" },
  { x: 282, y: 92, r: 4, c: "#5B6473" },
];

const NET_EDGES: Array<[number, number]> = [
  [0, 1], [0, 2], [0, 3],
  [1, 4], [1, 5], [2, 5], [2, 6], [3, 6], [3, 7],
  [4, 8], [5, 8], [6, 9], [7, 9],
];

const WEEK_DOTS = 26;

// ── page ────────────────────────────────────────────────────────────────────

export default function JudgePage() {
  const { lang, toggleLang, t } = useUI();
  const ru = lang === "ru";
  const tr = (en: string, r: string) => (ru ? r : en);

  const sectionRefs = useRef<Array<HTMLElement | null>>([]);
  const visible = useRef<Set<number>>(new Set());
  const [active, setActive] = useState(0);

  const nav: Array<{ n: string; label: string }> = [
    { n: "01", label: tr("What is it?", "Что это?") },
    { n: "02", label: tr("Input", "Вход") },
    { n: "03", label: tr("Mechanics", "Механика") },
    { n: "04", label: tr("Output", "Выход") },
    { n: "05", label: tr("Accuracy", "Точность") },
    { n: "06", label: tr("Finding", "Находка") },
    { n: "07", label: tr("Limits", "Пределы") },
  ];

  // Which of the seven is the reader on? The section crossing the viewport's
  // middle band wins; the observer is torn down on unmount.
  useEffect(() => {
    const els = sectionRefs.current.filter((el): el is HTMLElement => el !== null);
    if (els.length === 0 || typeof IntersectionObserver === "undefined") return;

    const seen = visible.current;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const raw = (entry.target as HTMLElement).dataset.index;
          const i = raw === undefined ? -1 : Number(raw);
          if (!Number.isInteger(i) || i < 0) continue;
          if (entry.isIntersecting) seen.add(i);
          else seen.delete(i);
        }
        if (seen.size > 0) {
          let lowest = Number.POSITIVE_INFINITY;
          seen.forEach((i) => { if (i < lowest) lowest = i; });
          setActive(lowest);
        }
      },
      { rootMargin: "-45% 0px -45% 0px", threshold: 0 },
    );

    els.forEach((el) => observer.observe(el));
    return () => {
      observer.disconnect();
      seen.clear();
    };
  }, []);

  const goTo = useCallback((i: number) => {
    const el = sectionRefs.current[i];
    if (!el) return;
    const reduced =
      typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
  }, []);

  const register = (i: number) => (el: HTMLElement | null) => {
    sectionRefs.current[i] = el;
  };

  return (
    <main className="min-h-screen pb-24">
      {/* ── sticky header + 7-step progress ─────────────────────────────── */}
      <header className="sticky top-0 z-30 border-b border-border-subtle bg-bg-base/90 backdrop-blur-md">
        <div className="mx-auto max-w-[1100px] space-y-2.5 px-5 py-3 sm:px-6">
          <div className="flex items-center justify-between gap-3">
            <h1 className="min-w-0 text-lg font-extrabold tracking-tight sm:text-xl">
              <a href="/" className="title-gradient transition hover:opacity-80">GEDS</a>
              <span className="ml-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-text-secondary sm:ml-3 sm:text-[11px] sm:tracking-[0.24em]">
                {tr("Judge mode", "Режим жюри")}
              </span>
            </h1>
            <div className="flex shrink-0 items-center gap-2">
              <a href="/" className="btn-pill">{tr("← Simulator", "← Симулятор")}</a>
              <a href="/validation" className="btn-pill hidden sm:inline-block">
                {tr("Validation →", "Валидация →")}
              </a>
              <button onClick={toggleLang} className="btn-pill">{t("langBtn")}</button>
            </div>
          </div>

          <nav
            className="flex items-stretch gap-1"
            aria-label={tr("Section progress", "Прогресс по разделам")}
          >
            {nav.map((s, i) => (
              <button
                key={s.n}
                type="button"
                onClick={() => goTo(i)}
                aria-current={i === active ? "step" : undefined}
                aria-label={`${s.n} — ${s.label}`}
                className="min-w-0 flex-1 text-left"
              >
                <span
                  className={`block h-[3px] rounded-full transition-colors duration-300 ${
                    i === active
                      ? "bg-accent-cyan"
                      : i < active
                        ? "bg-accent-cyan/40"
                        : "bg-border-subtle"
                  }`}
                />
                <span
                  className={`mt-1 block truncate font-mono text-[9px] tracking-[0.14em] transition-colors sm:text-[10px] ${
                    i === active ? "text-text-primary" : "text-text-muted"
                  }`}
                >
                  {s.n}
                  <span className="ml-1.5 hidden font-sans tracking-normal md:inline">{s.label}</span>
                </span>
              </button>
            ))}
          </nav>
        </div>
      </header>

      <div className="mx-auto max-w-[1100px] px-5 sm:px-6">
        {/* ── opening line ──────────────────────────────────────────────── */}
        <section className="fade-up py-12 sm:py-16">
          <p className="max-w-3xl text-[15px] leading-relaxed text-text-secondary sm:text-base">
            {tr(
              "Seven questions, one sentence and one number each. Nothing here is rounded in this project's favour: section 05 reports that our own model is the least accurate of the four we tested, and section 07 lists what the evidence cannot support.",
              "Семь вопросов, по одному предложению и одному числу на каждый. Ничто здесь не округлено в пользу проекта: раздел 05 сообщает, что наша собственная модель — наименее точная из четырёх протестированных, а раздел 07 перечисляет то, что доказательства не подтверждают.",
            )}
          </p>
          <p className="num mt-4 text-[11px] uppercase tracking-[0.22em] text-text-muted">
            {tr("about 2 minutes", "около 2 минут")}
          </p>
        </section>

        {/* ── 01 ─────────────────────────────────────────────────────────── */}
        <Section
          innerRef={register(0)}
          index={0}
          id="s01"
          num="01"
          eyebrow={tr("What is GEDS?", "Что такое GEDS?")}
          sentence={tr(
            "GEDS is two things at once: a simulator of how a single supply-chain shock spreads through a network of dependencies, and a benchmark built to test whether models of that kind work at all.",
            "GEDS — это две вещи сразу: симулятор того, как один шок в цепочке поставок распространяется по сети зависимостей, и бенчмарк, созданный для проверки того, работают ли такие модели вообще.",
          )}
          value="27"
          valueClass="text-accent-cyan"
          valueLabel={tr(
            "historical events, primary-sourced, 1999–2023 — the full benchmark",
            "исторических событий из первичных источников, 1999–2023 — весь бенчмарк",
          )}
        >
          <Figure
            caption={tr(
              "One shocked node (red) and the dependency edges the disruption can travel along. Schematic.",
              "Один шокированный узел (красный) и рёбра зависимостей, по которым может пройти нарушение. Схема.",
            )}
          >
            <svg viewBox="0 0 320 130" className="h-auto w-full max-w-[460px]" role="img"
                 aria-label={tr("Network sketch: one shocked node spreading outward",
                                "Схема сети: один шокированный узел распространяется наружу")}>
              {NET_EDGES.map(([a, b], i) => (
                <line
                  key={`e${i}`}
                  x1={NET_NODES[a].x} y1={NET_NODES[a].y}
                  x2={NET_NODES[b].x} y2={NET_NODES[b].y}
                  stroke="#2A3140" strokeWidth={1}
                />
              ))}
              {NET_EDGES.map(([a, b], i) => (
                <line
                  key={`p${i}`}
                  className="hero-arc"
                  x1={NET_NODES[a].x} y1={NET_NODES[a].y}
                  x2={NET_NODES[b].x} y2={NET_NODES[b].y}
                  stroke="#4DD0E1" strokeWidth={1.5} strokeLinecap="round"
                  style={{ animationDelay: `${i * 240}ms` }}
                />
              ))}
              {NET_NODES.map((n, i) => (
                <g key={`n${i}`}>
                  {i === 0 && <circle cx={n.x} cy={n.y} r={n.r + 6} fill="#EF4444" opacity={0.14} />}
                  <circle cx={n.x} cy={n.y} r={n.r} fill={n.c} />
                </g>
              ))}
            </svg>
          </Figure>
        </Section>

        {/* ── 02 ─────────────────────────────────────────────────────────── */}
        <Section
          innerRef={register(1)}
          index={1}
          id="s02"
          num="02"
          eyebrow={tr("What goes in?", "Что на входе?")}
          sentence={tr(
            "A scenario is only three things: which node is shocked, how much capacity it loses, and how long the loss lasts.",
            "Сценарий — это всего три вещи: какой узел получает шок, сколько мощности он теряет и как долго длится потеря.",
          )}
          value="405"
          valueClass="text-accent-cyan"
          valueLabel={tr(
            "nodes to choose from in the v3 network — 81 economies × 5 sectors, straight from OECD ICIO 2019",
            "узлов на выбор в сети v3 — 81 экономика × 5 секторов, напрямую из OECD ICIO 2019",
          )}
        >
          <Figure
            caption={tr(
              "The three inputs and where they go. The bar and the segments are illustrations, not values.",
              "Три входа и куда они идут. Полоса и сегменты — иллюстрации, а не значения.",
            )}
          >
            <div className="w-full space-y-4">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <InputChip
                  accent="#4DD0E1"
                  kicker={tr("shocked node", "шокированный узел")}
                  body={tr("one of the 405", "один из 405")}
                >
                  <span className="glow-dot inline-block h-2.5 w-2.5" style={{ background: "#EF4444", color: "#EF4444" }} />
                </InputChip>
                <InputChip
                  accent="#7C6CFB"
                  kicker={tr("capacity loss", "потеря мощности")}
                  body={tr("how much it loses", "сколько он теряет")}
                >
                  <span className="block h-2 w-full max-w-[110px] overflow-hidden rounded-sm bg-bg-base">
                    <span className="block h-full w-2/3 rounded-sm" style={{ background: "#7C6CFB" }} />
                  </span>
                </InputChip>
                <InputChip
                  accent="#FFC34D"
                  kicker={tr("duration", "длительность")}
                  body={tr("how long it lasts", "как долго она длится")}
                >
                  <span className="flex gap-[3px]">
                    {Array.from({ length: 8 }, (_, i) => (
                      <span
                        key={i}
                        className="h-2 w-2 rounded-[1px]"
                        style={{ background: i < 5 ? "#FFC34D" : "#1A1E26" }}
                      />
                    ))}
                  </span>
                </InputChip>
              </div>

              <div className="flex items-center justify-center">
                <span className="num text-sm text-text-muted" aria-hidden="true">↓</span>
              </div>

              <div className="rounded-lg border border-border-strong bg-bg-base/60 px-4 py-3 text-center">
                <div className="num text-[10px] uppercase tracking-[0.22em] text-accent-cyan">
                  {tr("propagation engine", "движок распространения")}
                </div>
                <div className="num mt-1 text-[12px] text-text-secondary">
                  {tr("405 nodes · deterministic · seed 0", "405 узлов · детерминирован · seed 0")}
                </div>
              </div>
            </div>
          </Figure>
        </Section>

        {/* ── 03 ─────────────────────────────────────────────────────────── */}
        <Section
          innerRef={register(2)}
          index={2}
          id="s03"
          num="03"
          eyebrow={tr("What happens?", "Что происходит?")}
          sentence={tr(
            "The shock is carried week by week along the dependency edges, and different industries turn at different weeks.",
            "Шок переносится неделя за неделей по рёбрам зависимостей, и разные отрасли разворачиваются на разных неделях.",
          )}
          value="260"
          valueClass="text-accent-violet"
          valueLabel={tr(
            "weeks — the single fixed simulation window every scored event now runs on",
            "недель — единое фиксированное окно симуляции, на котором теперь считается каждое оцениваемое событие",
          )}
        >
          <Figure
            caption={tr(
              "Illustrative timing strip: the offset between the two rows is the point, the positions are not measured values.",
              "Иллюстративная полоса времени: смысл в сдвиге между двумя рядами, сами позиции — не измеренные значения.",
            )}
          >
            <div className="w-full space-y-4">
              <WeekStrip
                label={tr("industry A", "отрасль A")}
                note={tr("turns earlier", "разворачивается раньше")}
                color="77, 208, 225"
                offset={0}
              />
              <WeekStrip
                label={tr("industry B", "отрасль B")}
                note={tr("turns later", "разворачивается позже")}
                color="124, 108, 251"
                offset={520}
              />
              <div className="num flex justify-between text-[10px] text-text-muted">
                <span>{tr("week 0", "неделя 0")}</span>
                <span>{tr("week 25", "неделя 25")}</span>
              </div>
            </div>
          </Figure>

          <Note
            tone="plain"
            title={tr("What the benchmark says about this ordering", "Что бенчмарк говорит об этом порядке")}
            body={tr(
              "Spearman rho +0.691 on weeks-to-peak across n = 15 nodes, 95% CI [+0.201, +0.869]. Widened to family-wise coverage it is [+0.000, +0.904] — it does not survive. This is a rank ordering, never a claim of point accuracy.",
              "Спирмен rho +0,691 по неделям до пика при n = 15 узлах, 95% ДИ [+0,201, +0,869]. При расширении до семейного покрытия — [+0,000, +0,904] — не выдерживает. Это порядок рангов, а не утверждение о точечной точности.",
            )}
          />
        </Section>

        {/* ── 04 ─────────────────────────────────────────────────────────── */}
        <Section
          innerRef={register(3)}
          index={3}
          id="s04"
          num="04"
          eyebrow={tr("What comes out?", "Что на выходе?")}
          sentence={tr(
            "For every node the run returns three things: how much output it loses, the week that loss peaks, and the week it recovers.",
            "Для каждого узла прогон возвращает три вещи: сколько выпуска он теряет, на какой неделе эта потеря достигает пика и на какой неделе происходит восстановление.",
          )}
          value="149"
          valueClass="text-accent-cyan"
          valueLabel={tr(
            "automated tests, all passing; golden-snapshot tests freeze the results so no number can drift silently",
            "автоматических тестов, все проходят; golden-снимки фиксируют результаты, чтобы ни одно число не сместилось незаметно",
          )}
        >
          <Figure
            caption={tr(
              "Schematic of one node's output path. The axes carry no units and this is not a data series.",
              "Схема траектории выпуска одного узла. Оси без единиц измерения, это не ряд данных.",
            )}
          >
            <svg viewBox="0 0 320 120" className="h-auto w-full max-w-[460px]" role="img"
                 aria-label={tr("Schematic: output falls, reaches a peak loss, then recovers",
                                "Схема: выпуск падает, достигает пика потерь, затем восстанавливается")}>
              <line x1={14} y1={26} x2={306} y2={26} stroke="#2A3140" strokeWidth={1} strokeDasharray="3 4" />
              <path
                d="M14 26 L58 26 C78 26 88 76 112 84 C142 94 196 52 306 34"
                fill="none" stroke="#4DD0E1" strokeWidth={2} strokeLinecap="round"
              />
              <circle cx={112} cy={84} r={4.5} fill="#FFC34D" />
              <circle cx={252} cy={39} r={4.5} fill="#2DD4BF" />
              <text x={112} y={104} fill="#FFC34D" fontSize={9} fontFamily="JetBrains Mono, monospace" textAnchor="middle">
                {tr("peak", "пик")}
              </text>
              <text x={252} y={26} fill="#2DD4BF" fontSize={9} fontFamily="JetBrains Mono, monospace" textAnchor="middle">
                {tr("recovery", "восстановление")}
              </text>
              <text x={14} y={17} fill="#5B6473" fontSize={9} fontFamily="JetBrains Mono, monospace">
                {tr("output", "выпуск")}
              </text>
              <text x={306} y={112} fill="#5B6473" fontSize={9} fontFamily="JetBrains Mono, monospace" textAnchor="end">
                {tr("weeks →", "недели →")}
              </text>
            </svg>
          </Figure>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <Note
              tone="good"
              title={tr("The one result that survives correction", "Единственный результат, выдерживающий поправку")}
              body={tr(
                "Recovery-week ordering: Spearman rho +0.711, n = 11, 95% CI [+0.215, +0.917], family-wise [+0.044, +0.962] — it survives. Peak magnitude (n = 6, rho +0.714) does not.",
                "Порядок недель восстановления: Спирмен rho +0,711, n = 11, 95% ДИ [+0,215, +0,917], семейный [+0,044, +0,962] — выдерживает. Величина пика (n = 6, rho +0,714) — нет.",
              )}
            />
            <Note
              tone="withdrawn"
              title={tr("Withdrawn: recovery 0.8828", "Отозвано: восстановление 0,8828")}
              body={tr(
                "That earlier figure was confounded. Recovery was scored against each event's own hand-set horizon, and 7 of 11 predictions were lower bounds equal to that hand-typed field — ranking by the field alone scored 0.8717 with no engine at all. On one fixed 260-week window, censored cases go 7 → 0 and the clean value is 0.7107.",
                "Эта прежняя цифра была искажена. Восстановление оценивалось по собственному, вручную заданному горизонту каждого события, и 7 из 11 предсказаний были нижними границами, равными этому вручную вписанному полю — ранжирование по одному лишь полю давало 0,8717 вообще без движка. На едином фиксированном окне в 260 недель цензурированные случаи идут 7 → 0, а чистое значение равно 0,7107.",
              )}
            />
          </div>
        </Section>

        {/* ── 05 ─────────────────────────────────────────────────────────── */}
        <Section
          innerRef={register(4)}
          index={4}
          id="s05"
          num="05"
          eyebrow={tr("Can we trust it?", "Можно ли ему доверять?")}
          sentence={tr(
            "On point magnitude GEDS has the worst mean absolute error of the four models tested, and not one of the six pairwise differences is significant after Holm correction.",
            "По точечной величине у GEDS худшая средняя абсолютная ошибка из четырёх протестированных моделей, и ни одно из шести парных различий не значимо после поправки Холма.",
          )}
          value="0.0242"
          valueClass="text-sev-5"
          valueLabel={tr(
            "GEDS mean absolute error — the worst of the four models, with 5 parameters against three that have none",
            "средняя абсолютная ошибка GEDS — худшая из четырёх моделей, при 5 параметрах против трёх моделей без параметров",
          )}
        >
          <Figure
            caption={tr(
              "MAE with 95% bootstrap CI, lower is better. The intervals overlap, which is what \"0 of 6 significant\" looks like.",
              "MAE с 95% бутстрэп-ДИ, меньше — лучше. Интервалы перекрываются — так и выглядит «0 из 6 значимы».",
            )}
          >
            <div className="w-full space-y-4">
              {MODELS.map((m) => (
                <div key={m.name} className="space-y-1.5">
                  <div className="flex items-baseline justify-between gap-3">
                    <div className="flex min-w-0 items-baseline gap-2">
                      <span className={`truncate text-[13px] font-semibold ${m.worst ? "text-sev-5" : "text-text-primary"}`}>
                        {m.name}
                      </span>
                      <span className="num shrink-0 text-[10px] text-text-muted">
                        {m.params} {tr("params", "парам.")}
                      </span>
                      {m.worst && (
                        <span className="num shrink-0 rounded-full border border-sev-5/50 px-1.5 py-0.5 text-[9px] uppercase tracking-[0.12em] text-sev-5">
                          {tr("worst", "худший")}
                        </span>
                      )}
                    </div>
                    <span className={`num shrink-0 text-[13px] ${m.worst ? "text-sev-5" : "text-text-primary"}`}>
                      {m.mae.toFixed(4)}
                    </span>
                  </div>

                  <div className="relative h-[12px] w-full overflow-hidden rounded-sm border border-border-subtle bg-bg-base">
                    <div
                      className="absolute inset-y-0 left-0"
                      style={{
                        width: `${(m.mae / MAE_AXIS) * 100}%`,
                        background: m.worst ? "#EF4444" : "#5B6473",
                      }}
                    />
                    <div
                      className="absolute top-1/2 h-px -translate-y-1/2"
                      style={{
                        left: `${(m.lo / MAE_AXIS) * 100}%`,
                        width: `${((m.hi - m.lo) / MAE_AXIS) * 100}%`,
                        background: "#E6EBF4",
                        opacity: 0.75,
                      }}
                    />
                    {[m.lo, m.hi].map((v) => (
                      <div
                        key={v}
                        className="absolute top-1/2 h-[8px] w-px -translate-y-1/2"
                        style={{ left: `${(v / MAE_AXIS) * 100}%`, background: "#E6EBF4", opacity: 0.75 }}
                      />
                    ))}
                  </div>

                  <div className="num text-[10px] text-text-muted">
                    95% CI [{m.lo.toFixed(4)}, {m.hi.toFixed(4)}]
                  </div>
                </div>
              ))}

              <div className="num flex justify-between border-t border-border-subtle pt-2 text-[10px] text-text-muted">
                <span>0</span>
                <span>{tr("MAE · lower is better", "MAE · меньше — лучше")}</span>
                <span>{MAE_AXIS.toFixed(3)}</span>
              </div>
            </div>
          </Figure>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Stat
              v="0 / 6"
              label={tr("pairwise model differences significant after Holm correction",
                        "парных различий между моделями значимы после поправки Холма")}
            />
            <Stat
              v="0.0184"
              label={tr("minimum detectable effect in MAE — the gap between models is smaller than this",
                        "минимальный детектируемый эффект в MAE — разрыв между моделями меньше него")}
            />
            <Stat
              v="0 / 6"
              label={tr("ablation deltas distinguishable from zero after Holm correction; every delta is below the detectable effect",
                        "дельт абляции отличимы от нуля после поправки Холма; каждая дельта ниже детектируемого эффекта")}
            />
          </div>
        </Section>

        {/* ── 06 ─────────────────────────────────────────────────────────── */}
        <Section
          innerRef={register(5)}
          index={5}
          id="s06"
          num="06"
          eyebrow={tr("What did we discover?", "Что мы обнаружили?")}
          sentence={tr(
            "Holding the engine, the shocks and the parameters fixed and changing only the graph, pooled spatial recall rises from 0.29 to 0.79, and the larger graph leads at every threshold tested, so the result is not an artifact of one arbitrary cutoff.",
            "При неизменных движке, шоках и параметрах, когда меняется только граф, объединённый пространственный recall растёт с 0,29 до 0,79, и больший граф лидирует на каждом проверенном пороге, так что результат не является артефактом одного произвольного порога.",
          )}
          value="0.29 → 0.79"
          valueClass="text-accent-gold"
          valueLabel={tr(
            "pooled spatial recall, v2 → v3, at the published reach threshold 0.01 (exactly: 0.286 → 0.789), over 12 comparable production events",
            "объединённый пространственный recall, v2 → v3, на опубликованном пороге охвата 0,01 (точно: 0,286 → 0,789), по 12 сопоставимым производственным событиям",
          )}
        >
          <Figure
            caption={tr(
              "Recall at seven reach thresholds. v2 is the hand-authored graph, v3 the OECD ICIO one.",
              "Recall на семи порогах охвата. v2 — граф, собранный вручную, v3 — граф из OECD ICIO.",
            )}
          >
            <div className="w-full space-y-3">
              {RECALL.map((r) => (
                <div
                  key={r.thr}
                  className={`flex items-center gap-3 ${
                    r.mark === "published"
                      ? "border-l-2 border-accent-gold pl-2"
                      : r.mark === "scaled"
                        ? "border-l-2 border-accent-violet pl-2"
                        : "border-l-2 border-transparent pl-2"
                  }`}
                >
                  <span className="num w-[52px] shrink-0 text-[11px] text-text-secondary">{r.thr}</span>
                  <div className="min-w-0 flex-1 space-y-1">
                    <RecallBar tag="v2" v={r.v2} n={r.v2n} color="#5B6473" />
                    <RecallBar tag="v3" v={r.v3} n={r.v3n} color="#4DD0E1" />
                  </div>
                </div>
              ))}

              <div className="num flex flex-wrap gap-x-4 gap-y-1 border-t border-border-subtle pt-2 text-[10px] text-text-muted">
                <span className="text-accent-gold">
                  {tr("0.01 — published threshold", "0,01 — опубликованный порог")}
                </span>
                <span className="text-accent-violet">
                  {tr("0.0388 — scale-corrected (v3 runs ~4× hot; 0.01 / k, k = 0.2578)",
                      "0,0388 — с поправкой на масштаб (v3 идёт примерно в 4× горячее; 0,01 / k, k = 0,2578)")}
                </span>
              </div>
            </div>
          </Figure>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <Note
              tone="plain"
              title={tr("The only thing that changed", "Единственное, что изменилось")}
              body={tr(
                "v2: 41 nodes (12 countries × 6 industries, plus 5 chokepoints) and 74 edges, hand-authored. v3: 405 nodes and 1,964 edges, straight from OECD ICIO 2019. Same engine, same shocks, same parameters.",
                "v2: 41 узел (12 стран × 6 отраслей плюс 5 узких мест) и 74 ребра, собрано вручную. v3: 405 узлов и 1 964 ребра, напрямую из OECD ICIO 2019. Тот же движок, те же шоки, те же параметры.",
              )}
            />
            <Note
              tone="plain"
              title={tr("Why the gap is conservative", "Почему разрыв консервативен")}
              body={tr(
                "The denominators differ by design: nodes v2 cannot represent at all are excluded from its denominator rather than counted against it. That favours v2, so the measured gap understates the difference.",
                "Знаменатели различаются намеренно: узлы, которые v2 вообще не может представить, исключаются из её знаменателя, а не засчитываются против неё. Это в пользу v2, поэтому измеренный разрыв занижает различие.",
              )}
            />
          </div>
        </Section>

        {/* ── 07 ─────────────────────────────────────────────────────────── */}
        <Section
          innerRef={register(6)}
          index={6}
          id="s07"
          num="07"
          eyebrow={tr("Where does it fail?", "Где он не работает?")}
          sentence={tr(
            "The benchmark is far too small to resolve the differences it is asked to resolve, most of the engine's parameters are not identified by it, and the model simulates a scenario rather than predicting the future.",
            "Бенчмарк слишком мал, чтобы разрешить те различия, которые от него требуются, большинство параметров движка им не идентифицируются, и модель симулирует сценарий, а не предсказывает будущее.",
          )}
          value="166"
          valueClass="text-sev-4"
          valueLabel={tr(
            "events needed to resolve the observed MAE gap — the benchmark has 27",
            "событий нужно, чтобы разрешить наблюдаемый разрыв MAE — в бенчмарке их 27",
          )}
        >
          <Figure
            caption={tr(
              "Each square is one event: gold are the 27 the benchmark actually has, grey the 166 the power analysis asks for.",
              "Каждый квадрат — одно событие: золотые — те 27, что реально есть в бенчмарке, серые — те 166, которых требует анализ мощности.",
            )}
          >
            <div className="w-full space-y-3">
              <div className="flex max-w-[560px] flex-wrap gap-[3px]" aria-hidden="true">
                {Array.from({ length: 166 }, (_, i) => (
                  <span
                    key={i}
                    className="h-[7px] w-[7px] rounded-[1px]"
                    style={{ background: i < 27 ? "#FFC34D" : "#1A1E26" }}
                  />
                ))}
              </div>
              <div className="num flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-text-muted">
                <span className="text-accent-gold">{tr("27 available", "27 доступно")}</span>
                <span>{tr("166 required", "166 требуется")}</span>
              </div>
            </div>
          </Figure>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <Note
              tone="bad"
              title={tr("Parameters are not identified", "Параметры не идентифицированы")}
              body={tr(
                "3 of 5 engine parameters sit pinned to their prior-box bounds, and for 3 of 5 the global fit lies outside the entire leave-one-out range. amplification_mu moves 34.9× its own median when a single event of the 27 is dropped. Only 33% of DE restarts converged.",
                "3 из 5 параметров движка прижаты к границам своего априорного бокса, и для 3 из 5 глобальная подгонка лежит вне всего диапазона leave-one-out. amplification_mu смещается на 34,9 своей медианы, если убрать одно событие из 27. Сошлись только 33% рестартов DE.",
              )}
            />
            <Note
              tone="bad"
              title={tr("There is less data than it looks", "Данных меньше, чем кажется")}
              body={tr(
                "30 node observations across 11 events carry the information of 21.3 independent ones (ICC 0.237, design effect 1.41) — roughly double the event count, not thirty times it.",
                "30 наблюдений на уровне узлов по 11 событиям несут информацию 21,3 независимых (ICC 0,237, дизайн-эффект 1,41) — примерно вдвое больше числа событий, а не в тридцать раз.",
              )}
            />
            <Note
              tone="bad"
              title={tr("It does not forecast", "Он не прогнозирует")}
              body={tr(
                "GEDS takes a scenario you specify and simulates it. It does not predict which shock will happen, or when. Any use of it as a forecast is a misuse.",
                "GEDS берёт заданный вами сценарий и симулирует его. Он не предсказывает, какой шок произойдёт и когда. Любое использование его как прогноза — это неправильное применение.",
              )}
            />
          </div>
        </Section>

        {/* ── footer ────────────────────────────────────────────────────── */}
        <footer className="hairline space-y-4 py-12">
          <p className="max-w-3xl text-[13px] leading-relaxed text-text-secondary">
            {tr(
              "Four bugs were found and published in this project's own engine, two of which destroyed a result that had already been announced. The full statistical report, the ablation table and the identifiability diagnostics are on the validation page.",
              "В собственном движке проекта были найдены и опубликованы четыре бага, два из которых уничтожили уже объявленный результат. Полный статистический отчёт, таблица абляции и диагностика идентифицируемости — на странице валидации.",
            )}
          </p>
          <div className="flex flex-wrap gap-2">
            <a href="/" className="btn-pill">{tr("Simulator", "Симулятор")}</a>
            <a href="/demo" className="btn-pill">{tr("Track record", "Track record")}</a>
            <a href="/validation" className="btn-pill">{tr("Full validation", "Полная валидация")}</a>
          </div>
        </footer>
      </div>
    </main>
  );
}

// ── building blocks ─────────────────────────────────────────────────────────

interface SectionProps {
  innerRef: (el: HTMLElement | null) => void;
  index: number;
  id: string;
  num: string;
  eyebrow: string;
  sentence: string;
  value: string;
  valueClass: string;
  valueLabel: string;
  children: React.ReactNode;
}

function Section({
  innerRef, index, id, num, eyebrow, sentence, value, valueClass, valueLabel, children,
}: SectionProps) {
  return (
    <section
      ref={innerRef}
      id={id}
      data-index={index}
      className="hairline relative flex min-h-[88vh] scroll-mt-24 items-center overflow-hidden py-14 sm:py-20"
    >
      <span
        aria-hidden="true"
        className="pointer-events-none absolute -right-3 top-1/2 -translate-y-1/2 select-none font-mono text-[30vw] font-bold leading-none text-text-primary/5 sm:text-[18vw] lg:text-[210px]"
      >
        {num}
      </span>

      <div className="relative w-full space-y-8">
        <div className="flex items-baseline gap-3">
          <span className="num text-[11px] tracking-[0.3em] text-accent-cyan">{num}</span>
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.22em] text-text-secondary sm:text-xs">
            {eyebrow}
          </h2>
        </div>

        <p className="max-w-3xl text-xl font-semibold leading-snug text-text-primary sm:text-3xl sm:leading-[1.25]">
          {sentence}
        </p>

        <div className="flex flex-wrap items-end gap-x-5 gap-y-2">
          <div className={`num text-5xl font-bold leading-none sm:text-7xl ${valueClass}`}>{value}</div>
          <p className="max-w-sm text-[12px] leading-snug text-text-secondary sm:text-[13px]">{valueLabel}</p>
        </div>

        {children}
      </div>
    </section>
  );
}

function Figure({ caption, children }: { caption: string; children: React.ReactNode }) {
  return (
    <figure className="panel space-y-3 p-4 sm:p-6">
      <div className="overflow-x-auto">{children}</div>
      <figcaption className="text-[11px] leading-snug text-text-muted">{caption}</figcaption>
    </figure>
  );
}

function InputChip({
  accent, kicker, body, children,
}: { accent: string; kicker: string; body: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border-subtle bg-bg-base/50 p-3">
      <div className="num text-[10px] uppercase tracking-[0.16em]" style={{ color: accent }}>{kicker}</div>
      <div className="mt-1 text-[12px] text-text-secondary">{body}</div>
      <div className="mt-2.5 flex h-3 items-center">{children}</div>
    </div>
  );
}

function WeekStrip({
  label, note, color, offset,
}: { label: string; note: string; color: string; offset: number }) {
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <span className="num text-[10px] tracking-[0.14em]" style={{ color: `rgb(${color})` }}>{label}</span>
        <span className="text-[10px] text-text-muted">{note}</span>
      </div>
      <div className="flex items-center gap-[3px]">
        {Array.from({ length: WEEK_DOTS }, (_, i) => (
          <span
            key={i}
            className="pulse-soft h-2 w-2 shrink-0 rounded-full"
            style={{
              background: `rgba(${color}, ${0.2 + (i / (WEEK_DOTS - 1)) * 0.8})`,
              animationDelay: `${offset + i * 70}ms`,
            }}
          />
        ))}
      </div>
    </div>
  );
}

function RecallBar({ tag, v, n, color }: { tag: string; v: number; n: string; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="num w-[18px] shrink-0 text-[9px] text-text-muted">{tag}</span>
      <span className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-sm bg-bg-base">
        <span className="block h-full rounded-sm" style={{ width: `${v * 100}%`, background: color }} />
      </span>
      <span className="num w-[38px] shrink-0 text-right text-[10px] text-text-secondary">{v.toFixed(3)}</span>
      <span className="num hidden w-[44px] shrink-0 text-right text-[10px] text-text-muted sm:inline">{n}</span>
    </div>
  );
}

function Stat({ v, label }: { v: string; label: string }) {
  return (
    <div className="rounded-lg border border-border-subtle bg-bg-elevated/60 p-3.5">
      <div className="num text-2xl font-bold leading-none text-text-primary">{v}</div>
      <p className="mt-2 text-[11px] leading-snug text-text-secondary">{label}</p>
    </div>
  );
}

function Note({
  tone, title, body,
}: { tone: "plain" | "good" | "bad" | "withdrawn"; title: string; body: string }) {
  const edge =
    tone === "good" ? "border-l-2 border-sev-1"
    : tone === "bad" ? "border-l-2 border-sev-4"
    : tone === "withdrawn" ? "border-l-2 border-accent-gold"
    : "border-l-2 border-border-strong";
  const head =
    tone === "good" ? "text-sev-1"
    : tone === "bad" ? "text-sev-4"
    : tone === "withdrawn" ? "text-accent-gold"
    : "text-text-secondary";

  return (
    <div className={`${edge} rounded-r-lg bg-bg-elevated/50 py-3 pl-3.5 pr-4`}>
      <div className={`num text-[10px] uppercase tracking-[0.16em] ${head}`}>{title}</div>
      <p className="mt-1.5 text-[12px] leading-relaxed text-text-secondary">{body}</p>
    </div>
  );
}
