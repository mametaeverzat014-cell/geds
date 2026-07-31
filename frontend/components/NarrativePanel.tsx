"use client";

import { useEffect, useState } from "react";

import { api, type GrokNarrative } from "@/lib/api";
import { useSimStore } from "@/lib/store";
import { useUI } from "@/lib/ui-context";

const CONFIDENCE_STYLE: Record<string, string> = {
  low:    "text-sev-4 border-sev-4/30 bg-sev-4/10",
  medium: "text-sev-2 border-sev-2/30 bg-sev-2/10",
  high:   "text-accent-cyan border-accent-cyan/30 bg-accent-cyan/10",
};

export default function NarrativePanel() {
  const summary = useSimStore((s) => s.summary);
  const selectedId = useSimStore((s) => s.selectedScenarioId);
  const { t, lang } = useUI();

  const [data, setData] = useState<GrokNarrative | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function fetchNarrative(force = false) {
    if (!selectedId) return;
    setLoading(true);
    setError(null);
    try {
      const r = await api.narrative({ scenario_id: selectedId, lang, force_refresh: force });
      setData(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  // Auto-fetch when a simulation completes, when language flips, or when scenario changes.
  useEffect(() => {
    if (summary && selectedId) {
      fetchNarrative(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [summary, lang, selectedId]);

  if (!summary) {
    return (
      <div className="panel p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary mb-1">
          {t("narrativeTitle")}
        </h2>
        <p className="text-[12px] text-text-muted mb-3 leading-relaxed">{t("narrativeSubtitle")}</p>
        <p className="text-[13px] text-text-muted leading-relaxed">{t("narrativeRunFirst")}</p>
      </div>
    );
  }

  const isStub = data?.model?.endsWith("-stub");
  const confKey =
    data?.confidence === "high" ? "narrativeConfHigh" :
    data?.confidence === "medium" ? "narrativeConfMedium" : "narrativeConfLow";
  const confStyle = CONFIDENCE_STYLE[data?.confidence ?? "low"];

  return (
    <div className="panel p-4 space-y-3">
      {/* header */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
            {t("narrativeTitle")}
          </h2>
          <p className="text-[12px] text-text-muted leading-relaxed mt-0.5">
            {t("narrativeSubtitle")}
          </p>
        </div>
        <button
          onClick={() => fetchNarrative(true)}
          disabled={loading}
          className="text-[12px] px-2 py-1 rounded border border-border-strong text-text-secondary hover:text-text-primary hover:border-accent-violet/50 transition disabled:opacity-40"
        >
          {loading ? t("narrativeLoading") : t("narrativeRefresh")}
        </button>
      </div>

      {/* badges */}
      <div className="flex items-center gap-2 flex-wrap text-[12px]">
        {data && (
          <span className={`px-2 py-0.5 rounded-full border font-semibold ${confStyle}`}>
            {t("narrativeConfidence")}: {t(confKey)}
          </span>
        )}
        {data && (
          <span className="px-2 py-0.5 rounded-full bg-bg-base/60 text-text-muted border border-border-subtle">
            {data.model}
          </span>
        )}
        {data?.cached && (
          <span className="px-2 py-0.5 rounded-full bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/30">
            {t("narrativeCached")}
          </span>
        )}
        {isStub && (
          <span className="px-2 py-0.5 rounded-full bg-sev-4/10 text-sev-4 border border-sev-4/30">
            {t("narrativeStub")}
          </span>
        )}
        {data?.overlay_active && (
          <span className="px-2 py-0.5 rounded-full bg-accent-violet/10 text-accent-violet border border-accent-violet/30">
            {t("narrativeOverlayActive")} ({data.overlay_node_count})
          </span>
        )}
      </div>

      {error && (
        <div className="text-[13px] text-sev-5 bg-sev-5/10 border border-sev-5/30 rounded px-3 py-2">
          {t("narrativeError")}: {error}
        </div>
      )}

      {loading && !data && (
        <div className="flex items-center gap-2 text-[13px] text-text-muted">
          <span className="w-2 h-2 rounded-full bg-accent-cyan animate-pulse" />
          {t("narrativeLoading")}
        </div>
      )}

      {data && (
        <div className="space-y-3 text-[13px] leading-relaxed">
          {/* Executive summary */}
          <Section title={t("narrativeExecutiveSummary")} accent="cyan">
            <p className="text-text-primary">{data.executive_summary}</p>
          </Section>

          {/* Cascade mechanism */}
          <Section title={t("narrativeCascadeMechanism")} accent="violet">
            <p className="text-text-secondary">{data.cascade_mechanism}</p>
          </Section>

          {/* Immediate risks */}
          {data.immediate_risks.length > 0 && (
            <Section title={t("narrativeImmediateRisks")} accent="orange">
              <ul className="space-y-1">
                {data.immediate_risks.map((r, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-text-secondary">
                    <span className="text-sev-4 mt-0.5 shrink-0">▸</span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {/* Structural */}
          {data.structural_vulnerabilities.length > 0 && (
            <Section title={t("narrativeStructural")} accent="muted">
              <ul className="space-y-1">
                {data.structural_vulnerabilities.map((r, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-text-muted">
                    <span className="text-text-muted mt-0.5 shrink-0">▸</span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {/* Policy recommendations */}
          {data.policy_recommendations.length > 0 && (
            <Section title={t("narrativePolicyRecs")} accent="cyan">
              <div className="space-y-2">
                {data.policy_recommendations.map((p, i) => (
                  <div
                    key={i}
                    className="rounded border border-border-subtle bg-bg-base/40 p-2.5 space-y-1"
                  >
                    <div className="text-text-primary font-medium">{p.action}</div>
                    <div className="flex items-center gap-3 text-[12px] text-text-muted">
                      <span>
                        <span className="uppercase tracking-wider">{t("narrativeTarget")}:</span>{" "}
                        <span className="text-text-secondary">{p.target}</span>
                      </span>
                      <span className="num text-accent-cyan">
                        {p.time_horizon_weeks} {t("narrativeHorizon")}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          )}
        </div>
      )}
    </div>
  );
}

function Section({
  title,
  accent,
  children,
}: {
  title: string;
  accent: "cyan" | "violet" | "orange" | "muted";
  children: React.ReactNode;
}) {
  const accentMap: Record<string, string> = {
    cyan: "border-accent-cyan/40",
    violet: "border-accent-violet/40",
    orange: "border-sev-4/40",
    muted: "border-border-subtle",
  };
  return (
    <div className={`border-l-2 pl-3 ${accentMap[accent]}`}>
      <div className="text-[12px] uppercase tracking-widest text-text-muted font-bold mb-1">
        {title}
      </div>
      {children}
    </div>
  );
}
