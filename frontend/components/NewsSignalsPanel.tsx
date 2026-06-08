"use client";

import { useEffect, useState } from "react";

import { api, type NewsEvent, type NewsOverlayState } from "@/lib/api";
import { useUI } from "@/lib/ui-context";

const EVENT_STYLE: Record<string, string> = {
  strike:    "text-sev-3 border-sev-3/40 bg-sev-3/10",
  conflict:  "text-sev-5 border-sev-5/40 bg-sev-5/10",
  disaster:  "text-sev-4 border-sev-4/40 bg-sev-4/10",
  policy:    "text-accent-violet border-accent-violet/40 bg-accent-violet/10",
  logistics: "text-accent-cyan border-accent-cyan/40 bg-accent-cyan/10",
  unknown:   "text-text-muted border-border-subtle bg-bg-base/40",
};

export default function NewsSignalsPanel() {
  const { t, lang } = useUI();
  const [events, setEvents] = useState<NewsEvent[]>([]);
  const [overlay, setOverlay] = useState<NewsOverlayState | null>(null);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"live" | "stub" | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [news, ov] = await Promise.all([
        api.newsRecent(lang, /*use_stub=*/ false),
        api.newsOverlay(),
      ]);
      setEvents(news.events);
      setMode(news.mode);
      setOverlay(ov);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function apply() {
    setApplying(true);
    try {
      await api.newsApply({ use_stub: false, lang });
      const ov = await api.newsOverlay();
      setOverlay(ov);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setApplying(false);
    }
  }

  async function clear() {
    setApplying(true);
    try {
      await api.newsOverlayClear();
      const ov = await api.newsOverlay();
      setOverlay(ov);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setApplying(false);
    }
  }

  // Initial fetch + auto-refresh every 5 minutes; refetch on language change.
  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5 * 60 * 1000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);

  function eventLabel(type: string): string {
    const key =
      type === "strike" ? "newsEventStrike" :
      type === "conflict" ? "newsEventConflict" :
      type === "disaster" ? "newsEventDisaster" :
      type === "policy" ? "newsEventPolicy" :
      type === "logistics" ? "newsEventLogistics" : "newsEventUnknown";
    return t(key);
  }

  return (
    <div className="panel p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
            {t("newsTitle")}
          </h2>
          <p className="text-[10px] text-text-muted leading-relaxed mt-0.5">
            {t("newsSubtitle")}
          </p>
          {mode && (
            <div className="mt-1">
              <span
                className={`text-[9px] px-1.5 py-0.5 rounded-full border font-semibold ${
                  mode === "live"
                    ? "text-accent-cyan border-accent-cyan/40 bg-accent-cyan/10"
                    : "text-sev-4 border-sev-4/40 bg-sev-4/10"
                }`}
              >
                {mode === "live" ? t("newsLiveMode") : t("newsStubMode")}
              </span>
              {mode === "stub" && (
                <p className="text-[9px] text-text-muted leading-relaxed mt-1">
                  {lang === "en"
                    ? "Showing demo headlines. Set NEWSAPI_KEY (or GNEWS_KEY) in the backend environment for live news."
                    : "Показаны демо-заголовки. Задайте NEWSAPI_KEY (или GNEWS_KEY) в окружении backend для реальных новостей."}
                </p>
              )}
            </div>
          )}
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          className="text-[10px] px-2 py-1 rounded border border-border-strong text-text-secondary hover:text-text-primary hover:border-accent-cyan/50 transition disabled:opacity-40 shrink-0"
        >
          {loading ? t("newsLoading") : t("newsRefresh")}
        </button>
      </div>

      {/* Overlay status strip */}
      <div className="rounded border border-border-subtle bg-bg-base/30 px-3 py-2 space-y-1.5">
        <div className="flex items-center justify-between gap-2 text-[10px]">
          <span className="uppercase tracking-widest text-text-muted font-bold">
            {t("newsOverlayHeader")}
          </span>
          <div className="flex gap-1">
            <button
              onClick={apply}
              disabled={applying || events.length === 0}
              className="px-2 py-0.5 rounded border border-accent-violet/40 text-accent-violet hover:bg-accent-violet/10 transition disabled:opacity-40"
            >
              {t("newsApply")}
            </button>
            <button
              onClick={clear}
              disabled={applying || !overlay?.active}
              className="px-2 py-0.5 rounded border border-border-strong text-text-muted hover:text-text-primary transition disabled:opacity-40"
            >
              {t("newsClear")}
            </button>
          </div>
        </div>
        {overlay?.active ? (
          <div className="flex items-center gap-2 text-[10px] text-accent-violet">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-violet animate-pulse" />
            <span className="num font-semibold">{overlay.n_nodes_affected}</span>
            <span className="text-text-muted">{t("newsAffectedNodes")}</span>
            {overlay.active_until && (
              <span className="text-text-muted ml-auto">
                {t("newsOverlayActiveUntil")} {new Date(overlay.active_until).toLocaleString(lang === "ru" ? "ru-RU" : "en-US", { dateStyle: "short", timeStyle: "short" })}
              </span>
            )}
          </div>
        ) : (
          <p className="text-[10px] text-text-muted leading-relaxed">
            {t("newsOverlayNone")}
          </p>
        )}
      </div>

      {error && (
        <div className="text-xs text-sev-5 bg-sev-5/10 border border-sev-5/30 rounded px-3 py-2">
          {error}
        </div>
      )}

      {/* Event list */}
      {events.length === 0 && !loading ? (
        <p className="text-xs text-text-muted leading-relaxed">{t("newsNoEvents")}</p>
      ) : (
        <div className="space-y-2 max-h-[440px] overflow-y-auto pr-1">
          {events.map((ev, i) => (
            <div key={i} className="rounded border border-border-subtle bg-bg-base/30 p-2.5 space-y-1.5">
              <div className="flex items-start justify-between gap-2">
                <div className="text-xs text-text-primary font-medium leading-snug min-w-0">
                  {ev.headline.title}
                </div>
                <span className={`text-[9px] px-1.5 py-0.5 rounded-full border font-semibold shrink-0 ${EVENT_STYLE[ev.event_type] ?? EVENT_STYLE.unknown}`}>
                  {eventLabel(ev.event_type)}
                </span>
              </div>
              <div className="text-[10px] text-text-muted">
                {ev.headline.source}
              </div>
              {ev.matched_nodes.length > 0 && (
                <div className="flex items-center gap-1.5 flex-wrap pt-1">
                  <span className="text-[9px] uppercase tracking-widest text-text-muted font-bold">
                    {t("newsMatchedNodes")}:
                  </span>
                  {ev.matched_nodes.slice(0, 6).map((n) => (
                    <span key={n} className="text-[9px] px-1.5 py-0.5 rounded bg-bg-base/60 text-text-secondary border border-border-subtle/50 num">
                      {n}
                    </span>
                  ))}
                </div>
              )}
              {ev.deltas.length > 0 && (
                <div className="pt-1 space-y-0.5 text-[9px]">
                  {ev.deltas.slice(0, 3).map((d, j) => (
                    <div key={j} className="flex items-center gap-2 text-text-muted">
                      <span className="num">{d.node_id}</span>
                      <span className="text-sev-4">vuln +{d.vulnerability_delta.toFixed(2)}</span>
                      <span className="text-accent-cyan">D_eff ×{d.d_eff_multiplier.toFixed(2)}</span>
                      <span className="ml-auto">
                        {(d.confidence * 100).toFixed(0)}% {t("newsConfidence")}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
