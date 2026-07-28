"use client";

import clsx from "clsx";
import { useState } from "react";
import { api } from "@/lib/api";
import { useSimStore } from "@/lib/store";
import { useUI } from "@/lib/ui-context";
import type { PolicyCategory, PolicyPriority, PolicyRecommendation } from "@/lib/types";

const PRIORITY_STYLE: Record<PolicyPriority, { bar: string; badge: string; label_en: string; label_ru: string }> = {
  critical: { bar: "bg-sev-5", badge: "bg-sev-5/20 text-sev-5 border border-sev-5/40", label_en: "Critical", label_ru: "Критический" },
  high:     { bar: "bg-sev-4", badge: "bg-sev-4/20 text-sev-4 border border-sev-4/40", label_en: "High",     label_ru: "Высокий"     },
  medium:   { bar: "bg-sev-3", badge: "bg-sev-3/20 text-sev-3 border border-sev-3/40", label_en: "Medium",   label_ru: "Средний"     },
  low:      { bar: "bg-sev-1", badge: "bg-sev-1/20 text-sev-1 border border-sev-1/40", label_en: "Low",      label_ru: "Низкий"      },
};

const CATEGORY_ICON: Record<PolicyCategory, string> = {
  emergency:       "🚨",
  diversification: "🔀",
  stockpiling:     "📦",
  diplomatic:      "🤝",
  infrastructure:  "🏗",
  monetary:        "🏦",
};

const CATEGORY_LABEL: Record<PolicyCategory, { en: string; ru: string }> = {
  emergency:       { en: "Emergency response",     ru: "Экстренное реагирование"   },
  diversification: { en: "Supply diversification", ru: "Диверсификация поставок"   },
  stockpiling:     { en: "Strategic reserves",     ru: "Стратегические резервы"    },
  diplomatic:      { en: "Diplomatic action",      ru: "Дипломатические меры"      },
  infrastructure:  { en: "Infrastructure invest.", ru: "Инфраструктурные инвест."  },
  monetary:        { en: "Monetary / fiscal",      ru: "Монетарная / бюджетная"    },
};

function RecommendationCard({
  rec,
  expanded,
  onToggle,
  lang,
  t,
}: {
  rec: PolicyRecommendation;
  expanded: boolean;
  onToggle: () => void;
  lang: string;
  t: (k: string) => string;
}) {
  const ps = PRIORITY_STYLE[rec.priority];
  const catLabel = CATEGORY_LABEL[rec.category];
  return (
    <div className="border border-border-subtle rounded bg-bg-base/30 overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full text-left px-3 py-2.5 flex items-start gap-2.5 hover:bg-bg-elevated/40 transition"
      >
        <div className={clsx("w-0.5 self-stretch rounded-full shrink-0 mt-0.5", ps.bar)} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={clsx("text-[12px] px-1.5 py-0.5 rounded font-semibold uppercase tracking-wider", ps.badge)}>
              {lang === "en" ? ps.label_en : ps.label_ru}
            </span>
            <span className="text-[12px] text-text-muted">
              {CATEGORY_ICON[rec.category]} {lang === "en" ? catLabel.en : catLabel.ru}
            </span>
            <span className="text-[12px] text-text-muted ml-auto num">
              {rec.horizon_weeks} {t("weeksToEffect")}
            </span>
          </div>
          <p className="text-[13px] text-text-primary mt-1 font-medium leading-snug">{rec.title}</p>
        </div>
        <span className="text-text-muted text-[13px] shrink-0">{expanded ? "▴" : "▾"}</span>
      </button>

      {expanded && (
        <div className="px-3 pb-3 border-t border-border-subtle/60 pt-2 space-y-3">
          <p className="text-[13px] text-text-secondary leading-relaxed">{rec.description}</p>

          <div className="grid grid-cols-2 gap-3 text-[12px]">
            <div>
              <div className="text-text-muted uppercase tracking-wider mb-1">{t("estimatedImpact")}</div>
              <div className="flex items-center gap-2">
                <div className="flex-1 bg-bg-elevated h-1.5 rounded-full overflow-hidden">
                  <div className="h-full bg-sev-1 rounded-full" style={{ width: `${rec.estimated_impact * 100}%` }} />
                </div>
                <span className="num text-text-primary font-semibold">{(rec.estimated_impact * 100).toFixed(0)}%</span>
              </div>
            </div>
            <div>
              <div className="text-text-muted uppercase tracking-wider mb-1">{t("implDifficulty")}</div>
              <div className="flex items-center gap-2">
                <div className="flex-1 bg-bg-elevated h-1.5 rounded-full overflow-hidden">
                  <div className="h-full bg-sev-4 rounded-full" style={{ width: `${rec.implementation_difficulty * 100}%` }} />
                </div>
                <span className="num text-text-primary font-semibold">{(rec.implementation_difficulty * 100).toFixed(0)}%</span>
              </div>
            </div>
          </div>

          {(rec.target_countries.length > 0 || rec.target_industries.length > 0) && (
            <div className="flex gap-3 text-[12px] text-text-muted flex-wrap border-t border-border-subtle/40 pt-2">
              {rec.target_countries.length > 0 && (
                <span>
                  <span className="text-text-muted/60">{t("targetCountries")}:</span>{" "}
                  <span className="text-text-secondary">{rec.target_countries.slice(0, 6).join(", ")}</span>
                </span>
              )}
              {rec.target_industries.length > 0 && (
                <span>
                  <span className="text-text-muted/60">{t("targetIndustries")}:</span>{" "}
                  <span className="text-text-secondary">{rec.target_industries.join(", ")}</span>
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function PolicyAdvisorPanel() {
  const advisor           = useSimStore((s) => s.advisor);
  const advisorLoading    = useSimStore((s) => s.advisorLoading);
  const setAdvisor        = useSimStore((s) => s.setAdvisor);
  const setAdvisorLoading = useSimStore((s) => s.setAdvisorLoading);
  const selectedId        = useSimStore((s) => s.selectedScenarioId);
  const summary           = useSimStore((s) => s.summary);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [open, setOpen]         = useState(false);
  const [showMethod, setShowMethod] = useState(false);
  const { t, lang } = useUI();

  async function fetchAdvice() {
    setAdvisorLoading(true);
    setAdvisor(null);
    try {
      const result = await api.policy({ scenario_id: selectedId });
      setAdvisor(result);
      setOpen(true);
      if (result.recommendations.length > 0) {
        setExpanded(new Set([result.recommendations[0].id]));
      }
    } catch (e) {
      console.error("Policy advisor error:", e);
    } finally {
      setAdvisorLoading(false);
    }
  }

  const hasResult = !!advisor;
  const criticalRecs = advisor?.recommendations.filter((r) => r.priority === "critical") ?? [];
  const otherRecs    = advisor?.recommendations.filter((r) => r.priority !== "critical") ?? [];

  return (
    <div className="panel overflow-hidden">
      {/* ── header ── */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border-subtle">
        <button
          onClick={() => setOpen((o) => !o && hasResult)}
          className="text-sm font-semibold uppercase tracking-wider text-text-secondary hover:text-text-primary transition flex items-center gap-2"
        >
          <span>🧠 {t("policyAdvisor")}</span>
          {hasResult && <span className="text-text-muted text-[13px]">{open ? "▴" : "▾"}</span>}
        </button>
        <div className="flex items-center gap-2">
          {hasResult && (
            <span className="text-[12px] px-2 py-0.5 rounded-full bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/20">
              {advisor!.recommendations.length} {lang === "en" ? "recommendations" : "рекомендаций"}
            </span>
          )}
          <button
            onClick={fetchAdvice}
            disabled={advisorLoading || !summary}
            title={!summary ? t("runFirstHint") : undefined}
            className={clsx(
              "text-[13px] px-3 py-1 rounded font-semibold border transition",
              advisorLoading
                ? "border-border-subtle text-text-muted cursor-not-allowed"
                : !summary
                ? "border-border-subtle text-text-muted cursor-not-allowed opacity-50"
                : "border-accent-violet/50 text-accent-violet hover:bg-accent-violet/10",
            )}
          >
            {advisorLoading ? t("analysingBtn") : t("analyseBtn")}
          </button>
        </div>
      </div>

      {/* ── no result hint ── */}
      {!hasResult && !advisorLoading && (
        <div className="px-4 py-4">
          <p className="text-[13px] text-text-muted">{t("noResultsHint")}</p>
          <div className="mt-3 grid grid-cols-3 gap-2 text-[12px]">
            {[
              { icon: "1️⃣", en: "Select a scenario on the left", ru: "Выберите сценарий слева" },
              { icon: "2️⃣", en: "Click 'Run simulation'",        ru: "Нажмите «Запустить»" },
              { icon: "3️⃣", en: "Click 'Analyse' here",          ru: "Нажмите «Анализировать»" },
            ].map((s) => (
              <div key={s.icon} className="flex flex-col items-center text-center gap-1 p-2 rounded border border-border-subtle bg-bg-base/30">
                <span className="text-base">{s.icon}</span>
                <span className="text-text-muted">{lang === "en" ? s.en : s.ru}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── results body ── */}
      {open && hasResult && advisor && (
        <div className="px-4 py-4 space-y-4">

          {/* Executive summary */}
          <div className="bg-bg-base/50 rounded border border-border-subtle p-3 space-y-2.5">
            <div className="text-[12px] font-bold uppercase tracking-widest text-text-muted">
              {t("executiveSummary")}
            </div>
            <div className="grid grid-cols-3 gap-3">
              <SummaryChip
                icon="⏱"
                value={`${advisor.intervention_window_weeks}w`}
                label={lang === "en" ? "intervention window" : "окно вмешательства"}
              />
              <SummaryChip
                icon="🔴"
                value={String(advisor.critical_nodes.length)}
                label={lang === "en" ? "critical nodes" : "критических узлов"}
              />
              <SummaryChip
                icon="⚠️"
                value={String(advisor.chokepoint_alerts.length)}
                label={lang === "en" ? "chokepoint alerts" : "предупреждений о проливах"}
              />
            </div>

            {/* critical nodes list */}
            {advisor.critical_nodes.length > 0 && (
              <div>
                <div className="text-[12px] text-text-muted mb-1">
                  {lang === "en" ? "Most critically disrupted nodes:" : "Наиболее критически нарушенные узлы:"}
                </div>
                <div className="flex flex-wrap gap-1">
                  {advisor.critical_nodes.slice(0, 8).map((n) => (
                    <span key={n} className="text-[12px] px-1.5 py-0.5 rounded bg-sev-5/10 border border-sev-5/25 text-sev-4 num">
                      {n}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* chokepoint alerts */}
            {advisor.chokepoint_alerts.length > 0 && (
              <div className="flex gap-1.5 flex-wrap">
                {advisor.chokepoint_alerts.map((cp) => (
                  <span key={cp} className="text-[12px] px-2 py-0.5 rounded bg-accent-gold/10 border border-accent-gold/30 text-accent-gold">
                    ⚠ {cp.replace("CP:", "")}
                  </span>
                ))}
              </div>
            )}

            {/* what this means */}
            <p className="text-[12px] text-text-muted leading-relaxed border-t border-border-subtle/50 pt-2">
              {lang === "en"
                ? `You have approximately ${advisor.intervention_window_weeks} weeks before the cascade reaches its peak. ${advisor.critical_nodes.length} nodes are experiencing significant disruption. ${advisor.recommendations.length} policy actions are recommended below, ordered by priority.`
                : `У вас примерно ${advisor.intervention_window_weeks} недель до достижения пика каскада. ${advisor.critical_nodes.length} узлов испытывают значительные нарушения. Ниже приведены ${advisor.recommendations.length} приоритетных рекомендации по политике.`}
            </p>
          </div>

          {/* Recommendations */}
          {advisor.recommendations.length > 0 && (
            <div className="space-y-2">
              <div className="text-[12px] font-bold uppercase tracking-widest text-text-muted">
                {t("recommendations")}
              </div>

              {/* Critical first */}
              {criticalRecs.length > 0 && (
                <div className="space-y-1.5">
                  <div className="text-[12px] text-sev-5 uppercase tracking-wider font-semibold flex items-center gap-1">
                    <span className="w-4 h-px bg-sev-5/50" />
                    {lang === "en" ? "Immediate action required" : "Требуется немедленное действие"}
                    <span className="flex-1 h-px bg-sev-5/50" />
                  </div>
                  {criticalRecs.map((rec) => (
                    <RecommendationCard
                      key={rec.id}
                      rec={rec}
                      expanded={expanded.has(rec.id)}
                      onToggle={() => {
                        setExpanded((prev) => {
                          const next = new Set(prev);
                          next.has(rec.id) ? next.delete(rec.id) : next.add(rec.id);
                          return next;
                        });
                      }}
                      lang={lang}
                      t={t as (k: string) => string}
                    />
                  ))}
                </div>
              )}

              {/* Other priorities */}
              {otherRecs.length > 0 && (
                <div className="space-y-1.5">
                  {criticalRecs.length > 0 && (
                    <div className="text-[12px] text-text-muted uppercase tracking-wider font-semibold flex items-center gap-1 mt-1">
                      <span className="w-4 h-px bg-border-subtle" />
                      {lang === "en" ? "Additional recommendations" : "Дополнительные рекомендации"}
                      <span className="flex-1 h-px bg-border-subtle" />
                    </div>
                  )}
                  {otherRecs.map((rec) => (
                    <RecommendationCard
                      key={rec.id}
                      rec={rec}
                      expanded={expanded.has(rec.id)}
                      onToggle={() => {
                        setExpanded((prev) => {
                          const next = new Set(prev);
                          next.has(rec.id) ? next.delete(rec.id) : next.add(rec.id);
                          return next;
                        });
                      }}
                      lang={lang}
                      t={t as (k: string) => string}
                    />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Methodology collapsible */}
          <div className="border-t border-border-subtle pt-3">
            <button
              onClick={() => setShowMethod((s) => !s)}
              className="w-full flex items-center justify-between text-[12px] text-text-muted hover:text-text-secondary transition"
            >
              <span className="uppercase tracking-wider font-semibold">{t("methodologyTitle")}</span>
              <span>{showMethod ? "▴" : "▾"}</span>
            </button>

            {showMethod && (
              <div className="mt-2 space-y-2.5">
                <p className="text-[12px] text-text-secondary leading-relaxed">
                  {t("methodologyText")}
                </p>

                {/* confidence badge */}
                <div className="flex items-center gap-2">
                  <span className="text-[12px] text-text-muted uppercase tracking-wider">{t("confidenceLabel")}:</span>
                  <span className="text-[12px] px-2 py-0.5 rounded-full bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/20 font-semibold">
                    {t("confidenceValue")}
                  </span>
                </div>

                {/* sources */}
                <div>
                  <div className="text-[12px] text-text-muted uppercase tracking-wider mb-1">{t("sourcesLabel")}</div>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-[12px] text-text-muted">
                    {[
                      "UN Comtrade 2019 (HS 8541/8542/8703)",
                      "World Bank LPI 2018",
                      "OECD STAN 2019",
                      "IMF WEO April 2020",
                      "IEA World Energy Outlook 2020",
                      "IMO / Lloyd's List",
                    ].map((s) => (
                      <div key={s} className="flex items-center gap-1">
                        <span className="text-accent-cyan">›</span> {s}
                      </div>
                    ))}
                  </div>
                </div>

                {/* validated events */}
                <div>
                  <div className="text-[12px] text-text-muted uppercase tracking-wider mb-1">
                    {lang === "en" ? "Validated against" : "Проверено на"}
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {[
                      lang === "en" ? "COVID chips 2020–21" : "COVID чипы 2020–21",
                      lang === "en" ? "Suez 2021" : "Суэц 2021",
                      lang === "en" ? "Auto chip 2021" : "Авто чипы 2021",
                      lang === "en" ? "Japan 2011" : "Япония 2011",
                      lang === "en" ? "US-China tariffs 2019" : "Пошлины США-Китай 2019",
                      lang === "en" ? "Texas storm 2021" : "Техасский шторм 2021",
                      lang === "en" ? "EU energy 2021" : "Энергокризис ЕС 2021",
                      lang === "en" ? "Malaysia 2021" : "Малайзия 2021",
                    ].map((e) => (
                      <span key={e} className="text-[12px] px-1.5 py-0.5 rounded bg-bg-base border border-border-subtle text-text-muted">
                        {e}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function SummaryChip({ icon, value, label }: { icon: string; value: string; label: string }) {
  return (
    <div className="flex flex-col items-center text-center p-2 rounded border border-border-subtle bg-bg-base/40">
      <span className="text-lg">{icon}</span>
      <span className="num text-text-primary font-bold text-sm">{value}</span>
      <span className="text-[12px] text-text-muted leading-tight mt-0.5">{label}</span>
    </div>
  );
}
