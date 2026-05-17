"use client";

import { useEffect, useState } from "react";

import { api, type CVReport } from "@/lib/api";
import { useSimStore } from "@/lib/store";
import { useUI } from "@/lib/ui-context";

export default function StatusRibbon() {
  const graph   = useSimStore((s) => s.graph);
  const running = useSimStore((s) => s.running);
  const frames  = useSimStore((s) => s.frames);
  const error   = useSimStore((s) => s.error);
  const { t, lang, toggleLang, toggleFaq } = useUI();

  // Truthful validation badge — fetched live, not hardcoded.
  const [cv, setCv] = useState<CVReport | null>(null);
  const [refresh, setRefresh] = useState<{ last_refresh_utc: string | null; age_hours: number | null; workflow_run_url?: string | null } | null>(null);
  useEffect(() => {
    api.cvReport().then(setCv).catch(() => {});
    api.lastRefresh().then(setRefresh).catch(() => {});
  }, []);

  // Build the badge text from real measured values.
  const badgeText = cv
    ? (lang === "en"
        ? `Pearson r = ${cv.pearson_loss >= 0 ? "+" : ""}${cv.pearson_loss.toFixed(2)} · pass ±25% = ${(cv.pass_rate_25pct * 100).toFixed(0)}% (n=${cv.n_events})`
        : `Пирсон r = ${cv.pearson_loss >= 0 ? "+" : ""}${cv.pearson_loss.toFixed(2)} · точность ±25% = ${(cv.pass_rate_25pct * 100).toFixed(0)}% (n=${cv.n_events})`)
    : t("loadingGraph");
  const badgeColor = cv && cv.pearson_loss >= 0.6
    ? "bg-accent-cyan/10 text-accent-cyan border-accent-cyan/20"
    : "bg-sev-4/10 text-sev-4 border-sev-4/30";

  function formatAge(hours: number | null): string {
    if (hours == null) return "—";
    if (hours < 1) return `${Math.round(hours * 60)} min`;
    if (hours < 48) return `${Math.round(hours)} h`;
    return `${Math.round(hours / 24)} d`;
  }
  function formatAgeRu(hours: number | null): string {
    if (hours == null) return "—";
    if (hours < 1) return `${Math.round(hours * 60)} мин`;
    if (hours < 48) return `${Math.round(hours)} ч`;
    return `${Math.round(hours / 24)} дн`;
  }

  return (
    <div className="space-y-2 border-b border-border-subtle pb-4 mb-2">
      <div className="flex items-start justify-between gap-4">
        {/* left: title + tagline */}
        <div className="min-w-0">
          <h1 className="text-2xl font-extrabold tracking-tight flex items-baseline gap-3 flex-wrap">
            <span className="text-accent-cyan">{t("appTitle")}</span>
            <span className="text-text-secondary font-semibold text-sm uppercase tracking-[0.2em]">
              {t("appSubtitle")}
            </span>
          </h1>
          <p className="text-xs text-text-muted mt-1 max-w-2xl leading-relaxed">
            {t("appTagline")}
          </p>
        </div>

        {/* right: controls + status */}
        <div className="flex flex-col items-end gap-1.5 shrink-0">
          {/* action buttons */}
          <div className="flex items-center gap-2">
            <a
              href="/validation"
              className="text-xs px-3 py-1 rounded border border-border-strong text-text-secondary hover:text-text-primary hover:border-accent-cyan/50 transition font-medium"
            >
              {lang === "en" ? "Validation →" : "Валидация →"}
            </a>
            <button
              onClick={toggleFaq}
              className="text-xs px-3 py-1 rounded border border-border-strong text-text-secondary hover:text-text-primary hover:border-accent-cyan/50 transition font-medium"
            >
              {t("faqBtn")}
            </button>
            <button
              onClick={toggleLang}
              className="text-xs px-3 py-1 rounded border border-border-strong text-text-secondary hover:text-text-primary hover:border-accent-violet/50 transition font-medium"
            >
              {t("langBtn")}
            </button>
          </div>

          {/* graph/simulation status */}
          <div className="text-right text-xs text-text-secondary num space-y-0.5">
            <div>
              {graph
                ? `${graph.nodes.length} ${t("nodes")} · ${graph.edges.length} ${t("edges")}`
                : t("loadingGraph")}
            </div>
            <div>
              {running
                ? `${t("streamingWeek")} ${frames.length}`
                : frames.length > 0
                ? `${frames.length} ${t("framesLoaded")}`
                : t("idle")}
            </div>
            {error && <div className="text-sev-5">{error}</div>}
          </div>
        </div>
      </div>

      {/* data provenance strip */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-[10px] text-text-muted">{t("dataStamp")}</span>
        <span className="text-text-muted/40 text-[10px]">·</span>
        <span
          title={cv ? `Live LOO cross-validation, computed ${new Date(cv.timestamp).toLocaleString()}` : ""}
          className={`text-[10px] px-2 py-0.5 rounded-full border font-semibold ${badgeColor}`}
        >
          {badgeText}
        </span>
        {refresh?.last_refresh_utc && (
          <a
            href={refresh.workflow_run_url || "#"}
            target="_blank"
            rel="noopener noreferrer"
            title={`Last UN Comtrade refresh: ${new Date(refresh.last_refresh_utc).toLocaleString()}`}
            className="text-[10px] px-2 py-0.5 rounded-full bg-accent-violet/10 text-accent-violet border border-accent-violet/30 hover:border-accent-violet/60 transition"
          >
            {lang === "en"
              ? `Data refreshed ${formatAge(refresh.age_hours)} ago`
              : `Данные обновлены ${formatAgeRu(refresh.age_hours)} назад`}
          </a>
        )}
      </div>
    </div>
  );
}
