"use client";

import { useEffect, useState } from "react";

import { useUI } from "@/lib/ui-context";

/**
 * First-run orientation for people who have never seen GEDS.
 *
 * The dashboard is dense — eight panels, two invented metrics, a live graph.
 * Without context a newcomer can't tell the real-data simulation from a toy.
 * This guide answers, in plain language: what GEDS is, how to drive it in three
 * steps, what each panel does, and whether the numbers can be trusted. It is
 * dismissible (remembered in localStorage) and collapses to a slim re-open bar,
 * so it helps first-timers without nagging returning users.
 */

const STORAGE_KEY = "geds_guide_open";

interface Copy {
  badge: string;
  title: string;
  what: string;
  whatBody: string;
  stepsTitle: string;
  steps: { k: string; v: string }[];
  panelsTitle: string;
  panels: { name: string; desc: string }[];
  trustTitle: string;
  trustBody: string;
  openFaq: string;
  openValidation: string;
  hide: string;
  reopen: string;
}

const COPY: Record<"en" | "ru", Copy> = {
  en: {
    badge: "New here? Start with this",
    title: "What is GEDS?",
    what: "What is GEDS?",
    whatBody:
      "GEDS (Global Economic Dependency Simulator) shows how one economic shock — a chip-factory shutdown, a blocked shipping strait, a trade war — ripples outward through the world's supply-chain network, week by week. You pick a 'what if' scenario and watch which countries and industries get hit, how hard, and how long they take to recover. No economics background needed.",
    stepsTitle: "How to use it — 3 steps",
    steps: [
      { k: "1 · Choose & run", v: "In the left panel, pick a preset scenario (the flagship is 'Taiwan Semi 75%') or build your own, then press Run simulation." },
      { k: "2 · Watch it spread", v: "The centre map animates the cascade across the trade network. Drag the timeline below it to scrub through the weeks; use the overlay buttons to switch between shock, inflation, output loss and unemployment views." },
      { k: "3 · Read & analyse", v: "The right panel shows the summary metrics. Click Analyse for prioritised policy recommendations, and read the AI analysis for a plain-language briefing." },
    ],
    panelsTitle: "What each panel does",
    panels: [
      { name: "Scenario", desc: "Pick a preset shock or build a custom one (which node, how big, how long). This is your input." },
      { name: "Propagation map", desc: "The live trade network. Brighter / hotter nodes are under more stress in the selected week." },
      { name: "Timeline", desc: "Scrub through the simulated weeks and switch the colour overlay (shock / inflation / output loss / unemployment)." },
      { name: "Simulation results", desc: "Headline numbers. CSI = how severe the whole network's disruption is (0–1). ECV = how fast it's still spreading." },
      { name: "AI Policy Analysis", desc: "Turns the raw simulation into a readable briefing: what's happening, why, and what to watch." },
      { name: "Live News Signals", desc: "Real disruption headlines mapped onto graph nodes — optionally fold today's news into your next run." },
      { name: "Policy advisor", desc: "Ranked, evidence-based interventions (diversify, stockpile, negotiate) with estimated risk reduction and timing." },
    ],
    trustTitle: "Is the data real — and is the model accurate?",
    trustBody:
      "The inputs are real, primary-source data: UN Comtrade trade flows, World Bank logistics scores, OECD sector shares, IMF GDP. Every parameter traces to a published citation. The model itself is validated honestly and openly: it is good at RANKING which shocks are worse, but not yet at exact point forecasts — and we show you those limits rather than hide them.",
    openFaq: "Full FAQ",
    openValidation: "See the validation →",
    hide: "Hide guide",
    reopen: "New to GEDS?  Open the quick guide",
  },
  ru: {
    badge: "Впервые здесь? Начните с этого",
    title: "Что такое GEDS?",
    what: "Что такое GEDS?",
    whatBody:
      "GEDS (Симулятор глобальных экономических зависимостей) показывает, как одно экономическое потрясение — остановка завода чипов, блокировка морского пролива, торговая война — расходится волнами по мировой сети цепочек поставок, неделя за неделей. Вы выбираете сценарий «что если» и наблюдаете, какие страны и отрасли страдают, насколько сильно и как долго восстанавливаются. Экономическое образование не требуется.",
    stepsTitle: "Как пользоваться — 3 шага",
    steps: [
      { k: "1 · Выбрать и запустить", v: "В левой панели выберите готовый сценарий (флагман — «Taiwan Semi 75%») или создайте свой, затем нажмите «Запустить симуляцию»." },
      { k: "2 · Смотреть распространение", v: "Карта в центре анимирует каскад по торговой сети. Перетаскивайте шкалу времени под ней, чтобы переходить по неделям; кнопки наложения переключают режимы: шок, инфляция, потери выпуска, безработица." },
      { k: "3 · Читать и анализировать", v: "Правая панель показывает итоговые метрики. Нажмите «Анализировать» для приоритетных рекомендаций и прочитайте AI-анализ для понятного резюме." },
    ],
    panelsTitle: "Что делает каждая панель",
    panels: [
      { name: "Сценарий", desc: "Выберите готовый шок или создайте свой (какой узел, насколько сильно, как долго). Это ваши входные данные." },
      { name: "Карта распространения", desc: "Живая торговая сеть. Чем ярче / горячее узел, тем больше стресс в выбранную неделю." },
      { name: "Шкала времени", desc: "Переходите по смоделированным неделям и переключайте цветовое наложение (шок / инфляция / потери / безработица)." },
      { name: "Результаты симуляции", desc: "Ключевые числа. CSI = насколько серьёзно нарушена вся сеть (0–1). ECV = как быстро шок ещё распространяется." },
      { name: "AI-анализ политики", desc: "Превращает сырую симуляцию в читаемое резюме: что происходит, почему и за чем следить." },
      { name: "Live-сигналы новостей", desc: "Реальные новости о нарушениях, привязанные к узлам графа — при желании учтите сегодняшние новости в следующем запуске." },
      { name: "Советник по политике", desc: "Ранжированные меры на основе доказательств (диверсификация, запасы, переговоры) с оценкой снижения риска и сроков." },
    ],
    trustTitle: "Данные реальные — и насколько точна модель?",
    trustBody:
      "Входные данные — реальные первичные источники: торговые потоки ООН Comtrade, логистические индексы Всемирного банка, доли секторов ОЭСР, ВВП от МВФ. Каждый параметр восходит к опубликованной ссылке. Сама модель проверяется честно и открыто: она хорошо РАНЖИРУЕТ, какие шоки серьёзнее, но пока не даёт точных точечных прогнозов — и мы показываем эти ограничения, а не прячем их.",
    openFaq: "Полный FAQ",
    openValidation: "Открыть валидацию →",
    hide: "Скрыть гид",
    reopen: "Впервые в GEDS?  Открыть краткий гид",
  },
};

export default function OnboardingGuide() {
  const { lang, toggleFaq } = useUI();
  const [open, setOpen] = useState(true);
  const c = COPY[lang];

  // Read the saved preference after mount (SSR renders the default open state,
  // so the first client render matches and there's no hydration mismatch).
  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved === "0") setOpen(false);
  }, []);

  const setOpenPersist = (v: boolean) => {
    setOpen(v);
    try {
      window.localStorage.setItem(STORAGE_KEY, v ? "1" : "0");
    } catch {
      /* private mode / storage disabled — non-fatal */
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpenPersist(true)}
        className="w-full flex items-center gap-2 rounded-md border border-border-subtle bg-bg-base/40 px-4 py-2 text-xs text-text-secondary hover:text-text-primary hover:border-accent-cyan/40 transition"
      >
        <span className="text-accent-cyan">▸</span>
        <span className="font-medium">{c.reopen}</span>
      </button>
    );
  }

  return (
    <section
      aria-label={c.badge}
      className="rounded-md border border-accent-cyan/25 bg-accent-cyan/5 px-5 py-4 space-y-4"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-accent-cyan">
            {c.badge}
          </div>
          <h2 className="text-base font-bold text-text-primary mt-0.5">{c.title}</h2>
        </div>
        <button
          onClick={() => setOpenPersist(false)}
          className="shrink-0 rounded px-2 py-1 text-[11px] text-text-muted hover:text-text-primary border border-border-subtle hover:border-border-strong transition"
        >
          {c.hide} ×
        </button>
      </div>

      <p className="text-xs text-text-secondary leading-relaxed max-w-4xl">{c.whatBody}</p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {/* steps */}
        <div className="md:col-span-1 space-y-2">
          <div className="text-[10px] font-bold uppercase tracking-widest text-text-muted">
            {c.stepsTitle}
          </div>
          {c.steps.map((s) => (
            <div key={s.k} className="text-xs leading-relaxed">
              <span className="text-accent-cyan font-semibold">{s.k}</span>
              <span className="text-text-secondary"> — {s.v}</span>
            </div>
          ))}
        </div>

        {/* panel legend */}
        <div className="md:col-span-2 space-y-1.5">
          <div className="text-[10px] font-bold uppercase tracking-widest text-text-muted">
            {c.panelsTitle}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1.5">
            {c.panels.map((p) => (
              <div key={p.name} className="text-xs leading-snug">
                <span className="text-text-primary font-semibold">{p.name}</span>
                <span className="text-text-muted"> — {p.desc}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="hairline pt-3 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
        <p className="text-xs text-text-secondary leading-relaxed flex-1">
          <span className="font-semibold text-text-primary">{c.trustTitle}</span>{" "}
          {c.trustBody}
        </p>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={toggleFaq}
            className="text-xs px-3 py-1 rounded border border-border-strong text-text-secondary hover:text-text-primary hover:border-accent-cyan/50 transition font-medium"
          >
            {c.openFaq}
          </button>
          <a
            href="/validation"
            className="text-xs px-3 py-1 rounded border border-accent-cyan/40 text-accent-cyan hover:bg-accent-cyan/10 transition font-medium"
          >
            {c.openValidation}
          </a>
        </div>
      </div>
    </section>
  );
}
