"use client";

import { useSimStore } from "@/lib/store";
import { useUI } from "@/lib/ui-context";

export default function StatusRibbon() {
  const graph   = useSimStore((s) => s.graph);
  const running = useSimStore((s) => s.running);
  const frames  = useSimStore((s) => s.frames);
  const error   = useSimStore((s) => s.error);
  const { t, toggleLang, toggleFaq } = useUI();

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
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/20 font-semibold">
          {t("validationBadge")}
        </span>
      </div>
    </div>
  );
}
