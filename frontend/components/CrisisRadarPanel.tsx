"use client";

import { useState } from "react";

import { api, type CrisisRadarResult, type CrisisScenario } from "@/lib/api";
import { useUI } from "@/lib/ui-context";

const SEVERITY_STYLE: Record<string, string> = {
  high:   "text-sev-5 border-sev-5/40 bg-sev-5/10",
  medium: "text-sev-4 border-sev-4/40 bg-sev-4/10",
  low:    "text-text-muted border-border-subtle bg-bg-base/40",
};

const L = {
  en: {
    title: "Crisis Radar",
    subtitle: "Claude-analyzed danger scenarios — grounded in GEDS's own risk signals",
    generate: "Generate analysis",
    analyzing: "Analyzing…",
    refresh: "Refresh",
    overview: "Risk overview",
    trigger: "Trigger",
    mechanism: "Mechanism",
    watch: "What to watch",
    basis: "Grounded in",
    severity: "severity",
    hint: "Click “Generate analysis” for a Claude read of the current danger scenarios. Each run is one API call (a few cents).",
    live: "Live",
    demo: "Demo — no API key",
    cached: "cached",
    error: "Failed to generate analysis.",
    demoNote:
      "This is demo output. Set ANTHROPIC_API_KEY on the backend for live Claude analysis — the scenarios below are grounded in real GEDS signals but are placeholders.",
    sev: { low: "low", medium: "medium", high: "high" } as Record<string, string>,
  },
  ru: {
    title: "Радар кризисов",
    subtitle: "Сценарии угроз от Claude — на основе собственных сигналов риска GEDS",
    generate: "Сгенерировать анализ",
    analyzing: "Анализ…",
    refresh: "Обновить",
    overview: "Обзор рисков",
    trigger: "Триггер",
    mechanism: "Механизм",
    watch: "За чем следить",
    basis: "Основано на",
    severity: "серьёзность",
    hint: "Нажмите «Сгенерировать анализ» для оценки текущих сценариев угроз от Claude. Каждый запуск — один вызов API (несколько центов).",
    live: "Live",
    demo: "Демо — нет API-ключа",
    cached: "из кэша",
    error: "Не удалось сгенерировать анализ.",
    demoNote:
      "Это демо-вывод. Задайте ANTHROPIC_API_KEY на backend для live-анализа Claude — сценарии ниже основаны на реальных сигналах GEDS, но являются заглушками.",
    sev: { low: "низкая", medium: "средняя", high: "высокая" } as Record<string, string>,
  },
};

export default function CrisisRadarPanel() {
  const { lang } = useUI();
  const c = L[lang];

  const [data, setData] = useState<CrisisRadarResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generate(force = true) {
    setLoading(true);
    setError(null);
    try {
      const r = await api.crisisRadar({ force_refresh: force });
      setData(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  const pick = (s: CrisisScenario, field: "title" | "trigger" | "mechanism" | "watch") => {
    const rec = s as unknown as Record<string, string>;
    return lang === "ru" ? rec[`${field}_ru`] : rec[`${field}_en`];
  };

  return (
    <div className="panel p-4 space-y-3">
      {/* header */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
            {c.title}
          </h2>
          <p className="text-[12px] text-text-muted leading-relaxed mt-0.5">{c.subtitle}</p>
        </div>
        <button
          onClick={() => generate(true)}
          disabled={loading}
          className="text-[12px] px-2.5 py-1 rounded-full border border-accent-violet/40 text-accent-violet hover:bg-accent-violet/10 hover:shadow-[0_0_16px_-6px_rgba(124,108,251,0.8)] hover:-translate-y-px active:scale-95 transition-all duration-200 disabled:opacity-40 shrink-0 font-medium"
        >
          {loading ? c.analyzing : data ? c.refresh : c.generate}
        </button>
      </div>

      {/* badges */}
      {data && (
        <div className="flex items-center gap-2 flex-wrap text-[12px]">
          <span
            className={`px-2 py-0.5 rounded-full border font-semibold ${
              data.mode === "live"
                ? "text-accent-cyan border-accent-cyan/30 bg-accent-cyan/10"
                : "text-sev-4 border-sev-4/40 bg-sev-4/10"
            }`}
          >
            {data.mode === "live" ? c.live : c.demo}
          </span>
          <span className="px-2 py-0.5 rounded-full bg-bg-base/60 text-text-muted border border-border-subtle">
            {data.model}
          </span>
          {data.cached && (
            <span className="px-2 py-0.5 rounded-full bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/30">
              {c.cached}
            </span>
          )}
          {data.active_news_count > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-accent-violet/10 text-accent-violet border border-accent-violet/30">
              {data.active_news_count} news
            </span>
          )}
        </div>
      )}

      {/* empty state */}
      {!data && !loading && !error && (
        <p className="text-[13px] text-text-muted leading-relaxed">{c.hint}</p>
      )}

      {error && (
        <div className="text-[13px] text-sev-5 bg-sev-5/10 border border-sev-5/30 rounded px-3 py-2">
          {c.error} {error}
        </div>
      )}

      {loading && !data && (
        <div className="flex items-center gap-2 text-[13px] text-text-muted">
          <span className="w-2 h-2 rounded-full bg-accent-violet animate-pulse" />
          {c.analyzing}
        </div>
      )}

      {data && (
        <div className="space-y-3">
          {data.mode === "stub" && (
            <p className="text-[12px] text-sev-4 bg-sev-4/10 border border-sev-4/30 rounded px-3 py-2 leading-relaxed">
              {c.demoNote}
            </p>
          )}

          {/* overview */}
          <div className="border-l-2 border-accent-violet/40 pl-3">
            <div className="text-[12px] uppercase tracking-widest text-text-muted font-bold mb-1">
              {c.overview}
            </div>
            <p className="text-[13px] text-text-primary leading-relaxed">
              {lang === "ru" ? data.overview_ru : data.overview_en}
            </p>
          </div>

          {/* scenarios */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {data.scenarios.map((s, i) => (
              <div key={i} className="rounded border border-border-subtle bg-bg-base/30 p-3 space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="text-[13px] font-semibold text-text-primary leading-snug">
                    {pick(s, "title")}
                  </div>
                  <span
                    className={`text-[12px] px-1.5 py-0.5 rounded-full border font-semibold shrink-0 ${
                      SEVERITY_STYLE[s.severity] ?? SEVERITY_STYLE.low
                    }`}
                  >
                    {c.sev[s.severity] ?? s.severity} {c.severity}
                  </span>
                </div>

                <Field label={c.trigger} value={pick(s, "trigger")} />
                <Field label={c.mechanism} value={pick(s, "mechanism")} />
                <Field label={c.watch} value={pick(s, "watch")} />

                {s.basis && (
                  <div className="text-[12px] text-text-muted pt-1 border-t border-border-subtle/40">
                    <span className="uppercase tracking-widest font-bold">{c.basis}:</span>{" "}
                    <span className="num text-text-secondary">{s.basis}</span>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* disclaimer — always shown, honest framing */}
          <p className="text-[12px] text-text-muted italic leading-relaxed pt-1">
            {lang === "ru" ? data.disclaimer_ru : data.disclaimer_en}
          </p>
        </div>
      )}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  if (!value) return null;
  return (
    <div className="text-[12px] leading-relaxed">
      <span className="text-[12px] uppercase tracking-widest text-text-muted font-bold">{label}: </span>
      <span className="text-text-secondary">{value}</span>
    </div>
  );
}
