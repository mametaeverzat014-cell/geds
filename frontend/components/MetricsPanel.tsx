"use client";

import { useState } from "react";
import { severityColor } from "@/lib/colors";
import { useSimStore } from "@/lib/store";
import { useUI } from "@/lib/ui-context";

function fmtPct(v: number) {
  return (v * 100).toFixed(1) + "%";
}
function fmtUsd(v: number) {
  if (v >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
  if (v >= 1e9)  return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6)  return `$${(v / 1e6).toFixed(1)}M`;
  return `$${v.toFixed(0)}`;
}
function csiLabel(v: number) {
  if (v < 0.10) return { label: "Minimal", color: "#2DD4BF" };
  if (v < 0.25) return { label: "Moderate", color: "#FFC34D" };
  if (v < 0.50) return { label: "Severe",   color: "#F97316" };
  return           { label: "Critical",  color: "#EF4444" };
}

function Tooltip({ text }: { text: string }) {
  const [show, setShow] = useState(false);
  return (
    <span className="relative inline-block ml-1">
      <button
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        className="text-[9px] w-3.5 h-3.5 rounded-full bg-border-strong text-text-muted hover:text-text-secondary flex items-center justify-center leading-none"
      >
        ?
      </button>
      {show && (
        <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-1.5 w-52 bg-bg-elevated border border-border-strong rounded p-2 text-[10px] text-text-secondary leading-relaxed shadow-xl pointer-events-none">
          {text}
        </div>
      )}
    </span>
  );
}

function Metric({
  label,
  value,
  tooltip,
  highlight,
}: {
  label: string;
  value: string;
  tooltip?: string;
  highlight?: string;
}) {
  return (
    <div>
      <div className="text-text-muted uppercase tracking-wider text-[10px] flex items-center">
        {label}
        {tooltip && <Tooltip text={tooltip} />}
      </div>
      <div className="num text-text-primary" style={highlight ? { color: highlight } : undefined}>
        {value}
      </div>
    </div>
  );
}

export default function MetricsPanel() {
  const summary = useSimStore((s) => s.summary);
  const { t, lang } = useUI();

  if (!summary) {
    return (
      <div className="panel p-5 space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
          {t("simulationResults")}
        </h2>
        <p className="text-xs text-text-muted leading-relaxed">{t("noResults")}</p>
        <div className="border-t border-border-subtle pt-3 space-y-2 text-[10px] text-text-muted">
          <div className="font-semibold uppercase tracking-wider mb-1">
            {lang === "en" ? "What you'll see here" : "Что вы увидите здесь"}
          </div>
          {[
            lang === "en"
              ? "Peak Cascade Severity Index (CSI) — how bad the shock gets"
              : "Пик CSI — насколько серьёзным стал шок",
            lang === "en"
              ? "Total economic output loss in USD"
              : "Общие потери экономического выпуска в долларах",
            lang === "en"
              ? "Country-by-country risk scores"
              : "Оценки риска по каждой стране",
            lang === "en"
              ? "Sector fragility rankings"
              : "Рейтинги хрупкости секторов",
          ].map((s) => (
            <div key={s} className="flex items-start gap-1.5">
              <span className="text-accent-cyan mt-0.5">›</span>
              <span>{s}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  const csi = csiLabel(summary.peak_csi);

  return (
    <div className="space-y-3">
      {/* Summary */}
      <div className="panel p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary mb-1">
          {t("summary")}
        </h2>
        {/* severity badge */}
        <div
          className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold mb-3 border"
          style={{
            color: csi.color,
            borderColor: csi.color + "40",
            background: csi.color + "15",
          }}
        >
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: csi.color }} />
          {lang === "en" ? `${csi.label} disruption` : `${csi.label === "Minimal" ? "Минимальное" : csi.label === "Moderate" ? "Умеренное" : csi.label === "Severe" ? "Серьёзное" : "Критическое"} нарушение`}
        </div>

        <div className="grid grid-cols-2 gap-x-4 gap-y-2.5 text-xs">
          <Metric
            label={t("peakCSI")}
            value={summary.peak_csi.toFixed(3)}
            tooltip={t("peakCSIDesc")}
            highlight={csi.color}
          />
          <Metric
            label={t("peakECV")}
            value={summary.peak_ecv.toFixed(3)}
            tooltip={t("peakECVDesc")}
          />
          <Metric
            label={t("finalCSI")}
            value={summary.final_csi.toFixed(3)}
            tooltip={t("finalCSIDesc")}
          />
          <Metric
            label={t("outputLoss")}
            value={fmtUsd(summary.total_output_loss_usd)}
          />
          <Metric
            label={t("topInflation")}
            value={`${summary.max_inflation_country[0]}  ${fmtPct(summary.max_inflation_country[1])}`}
          />
          <Metric
            label={t("topGDPImpact")}
            value={`${summary.max_gdp_impact_country[0]}  ${fmtPct(summary.max_gdp_impact_country[1])}`}
          />
          <Metric label={t("countriesAffected")} value={String(summary.affected_country_count)} />
          <Metric
            label={t("globalRecovery")}
            value={`${summary.global_recovery_weeks.toFixed(0)} ${lang === "en" ? "weeks" : "нед."}`}
          />
        </div>
      </div>

      {/* Country risk */}
      <div className="panel p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary mb-1">
          {t("countryRisk")}
        </h2>
        <p className="text-[10px] text-text-muted mb-3 leading-relaxed">
          {lang === "en"
            ? "Peak shock intensity weighted by GDP and network centrality."
            : "Пиковая интенсивность шока, взвешенная по ВВП и сетевой центральности."}
        </p>
        <div className="space-y-1.5">
          {summary.country_risk.slice(0, 9).map((r) => (
            <div key={r.iso3} className="flex items-center gap-2 text-xs">
              <span className="num w-10 text-text-primary font-semibold">{r.iso3}</span>
              <div className="flex-1 bg-bg-base/60 rounded-sm h-2 overflow-hidden">
                <div
                  className="h-full transition-all"
                  style={{
                    width: `${Math.min(100, r.risk_score * 130)}%`,
                    background: severityColor(r.risk_score * 1.3),
                  }}
                />
              </div>
              <span className="num w-10 text-right text-text-secondary">
                {r.risk_score.toFixed(2)}
              </span>
              <span className="num w-14 text-right text-text-muted">
                {r.expected_recovery_weeks.toFixed(0)}{lang === "en" ? "w" : "н."}
              </span>
            </div>
          ))}
          <div className="flex justify-between text-[10px] text-text-muted pt-1 border-t border-border-subtle/50">
            <span>{lang === "en" ? "← risk score" : "← оценка риска"}</span>
            <span>{lang === "en" ? "recovery →" : "восстановление →"}</span>
          </div>
        </div>
      </div>

      {/* Sector fragility */}
      <div className="panel p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary mb-1">
          {t("sectorFragility")}
        </h2>
        <p className="text-[10px] text-text-muted mb-3 leading-relaxed">
          {lang === "en"
            ? "Which industries are structurally most exposed to cascade shocks."
            : "Какие отрасли структурно наиболее уязвимы к каскадным шокам."}
        </p>
        <div className="space-y-1.5">
          {summary.sector_fragility.slice(0, 6).map((f) => (
            <div key={f.industry} className="flex items-center gap-2 text-xs">
              <span className="w-28 text-text-primary capitalize shrink-0">
                {f.industry.replace("_", " ")}
              </span>
              <div className="flex-1 bg-bg-base/60 rounded-sm h-2 overflow-hidden">
                <div
                  className="h-full transition-all"
                  style={{
                    width: `${Math.min(100, f.fragility_score * 600)}%`,
                    background: severityColor(Math.min(1, f.fragility_score * 6)),
                  }}
                />
              </div>
              <span className="num w-10 text-right text-text-muted">{f.most_exposed_country}</span>
            </div>
          ))}
        </div>
      </div>

      {/* trust footer — live validation badge in top-right shows current LOO-CV stats */}
      <div className="text-[10px] text-text-muted text-center leading-relaxed px-1">
        {lang === "en"
          ? "Validation: see live badge (top-right) · methodology: AUDIT.md"
          : "Валидация: см. live-значок справа сверху · методика: AUDIT.md"}
      </div>
    </div>
  );
}
