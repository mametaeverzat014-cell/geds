"use client";

import { useState } from "react";
import CountUp from "@/components/CountUp";
import { severityColor } from "@/lib/colors";
import { countryName } from "@/lib/names";
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
        className="text-[12px] w-3.5 h-3.5 rounded-full bg-border-strong text-text-muted hover:text-text-secondary flex items-center justify-center leading-none"
      >
        ?
      </button>
      {show && (
        <div className="value-pop absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-1.5 w-52 bg-bg-elevated/95 backdrop-blur-md border border-border-strong rounded-lg p-2 text-[12px] text-text-secondary leading-relaxed shadow-[0_8px_24px_-8px_rgba(0,0,0,0.8),0_0_0_1px_rgba(77,208,225,0.08)] pointer-events-none">
          {text}
          <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-border-strong" />
        </div>
      )}
    </span>
  );
}

function Metric({
  label,
  value,
  format,
  tooltip,
  highlight,
}: {
  label: string;
  value: string | number;
  format?: (v: number) => string;
  tooltip?: string;
  highlight?: string;
}) {
  return (
    <div className="group/metric">
      <div className="text-text-muted uppercase tracking-wider text-[12px] flex items-center transition-colors group-hover/metric:text-text-secondary">
        {label}
        {tooltip && <Tooltip text={tooltip} />}
      </div>
      <div
        className="num text-text-primary text-[13px]"
        style={highlight ? { color: highlight, textShadow: `0 0 14px ${highlight}55` } : undefined}
      >
        {typeof value === "number" && format ? <CountUp value={value} format={format} /> : value}
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
        <p className="text-[13px] text-text-muted leading-relaxed">{t("noResults")}</p>
        <div className="border-t border-border-subtle pt-3 space-y-2 text-[12px] text-text-muted">
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
          className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[12px] font-bold mb-3 border value-pop"
          style={{
            color: csi.color,
            borderColor: csi.color + "55",
            background: `linear-gradient(120deg, ${csi.color}22, ${csi.color}0d)`,
            boxShadow: `0 0 18px -6px ${csi.color}aa, 0 1px 0 0 rgba(255,255,255,0.06) inset`,
          }}
        >
          <span
            className="glow-dot w-1.5 h-1.5"
            style={{ background: csi.color, color: csi.color }}
          />
          {lang === "en" ? `${csi.label} disruption` : `${csi.label === "Minimal" ? "Минимальное" : csi.label === "Moderate" ? "Умеренное" : csi.label === "Severe" ? "Серьёзное" : "Критическое"} нарушение`}
        </div>

        <div className="grid grid-cols-2 gap-x-4 gap-y-2.5 text-[13px]">
          <Metric
            label={t("peakCSI")}
            value={summary.peak_csi}
            format={(v) => v.toFixed(3)}
            tooltip={t("peakCSIDesc")}
            highlight={csi.color}
          />
          <Metric
            label={t("peakECV")}
            value={summary.peak_ecv}
            format={(v) => v.toFixed(3)}
            tooltip={t("peakECVDesc")}
          />
          <Metric
            label={t("finalCSI")}
            value={summary.final_csi}
            format={(v) => v.toFixed(3)}
            tooltip={t("finalCSIDesc")}
          />
          <Metric
            label={t("outputLoss")}
            value={summary.total_output_loss_usd}
            format={fmtUsd}
          />
          <Metric
            label={t("topInflation")}
            value={`${countryName(summary.max_inflation_country[0], lang)}  ${fmtPct(summary.max_inflation_country[1])}`}
          />
          <Metric
            label={t("topGDPImpact")}
            value={`${countryName(summary.max_gdp_impact_country[0], lang)}  ${fmtPct(summary.max_gdp_impact_country[1])}`}
          />
          <Metric
            label={t("countriesAffected")}
            value={summary.affected_country_count}
            format={(v) => String(Math.round(v))}
          />
          <Metric
            label={t("globalRecovery")}
            value={summary.global_recovery_weeks}
            format={(v) => `${v.toFixed(0)} ${lang === "en" ? "weeks" : "нед."}`}
          />
        </div>
      </div>

      {/* Country risk */}
      <div className="panel p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary mb-1">
          {t("countryRisk")}
        </h2>
        <p className="text-[12px] text-text-muted mb-3 leading-relaxed">
          {lang === "en"
            ? "Peak shock intensity weighted by GDP and network centrality."
            : "Пиковая интенсивность шока, взвешенная по ВВП и сетевой центральности."}
        </p>
        <div className="space-y-1.5">
          {summary.country_risk.slice(0, 9).map((r, i) => (
            <div key={r.iso3} className="group/row flex items-center gap-2 text-[13px]">
              <span
                title={r.iso3}
                className="w-24 shrink-0 truncate text-text-primary font-semibold transition-transform duration-200 group-hover/row:translate-x-0.5"
              >
                {countryName(r.iso3, lang)}
              </span>
              <div className="bar-track flex-1 h-2">
                <div
                  className="bar-fill"
                  style={{
                    "--i": i,
                    width: `${Math.min(100, r.risk_score * 130)}%`,
                    background: `linear-gradient(90deg, ${severityColor(r.risk_score * 0.6)}, ${severityColor(r.risk_score * 1.3)})`,
                    boxShadow: `0 0 10px -2px ${severityColor(r.risk_score * 1.3)}99`,
                  } as React.CSSProperties}
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
          <div className="flex justify-between text-[12px] text-text-muted pt-1 border-t border-border-subtle/50">
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
        <p className="text-[12px] text-text-muted mb-3 leading-relaxed">
          {lang === "en"
            ? "Which industries are structurally most exposed to cascade shocks."
            : "Какие отрасли структурно наиболее уязвимы к каскадным шокам."}
        </p>
        <div className="space-y-1.5">
          {summary.sector_fragility.slice(0, 6).map((f, i) => (
            <div key={f.industry} className="group/row flex items-center gap-2 text-[13px]">
              <span className="w-28 text-text-primary capitalize shrink-0 transition-transform duration-200 group-hover/row:translate-x-0.5">
                {f.industry.replace("_", " ")}
              </span>
              <div className="bar-track flex-1 h-2">
                <div
                  className="bar-fill"
                  style={{
                    "--i": i,
                    width: `${Math.min(100, f.fragility_score * 600)}%`,
                    background: `linear-gradient(90deg, ${severityColor(Math.min(1, f.fragility_score * 3))}, ${severityColor(Math.min(1, f.fragility_score * 6))})`,
                    boxShadow: `0 0 10px -2px ${severityColor(Math.min(1, f.fragility_score * 6))}99`,
                  } as React.CSSProperties}
                />
              </div>
              <span title={f.most_exposed_country} className="w-20 shrink-0 truncate text-right text-text-muted">{countryName(f.most_exposed_country, lang)}</span>
            </div>
          ))}
        </div>
      </div>

      {/* trust footer — live validation badge in top-right shows current LOO-CV stats */}
      <div className="text-[12px] text-text-muted text-center leading-relaxed px-1">
        {lang === "en"
          ? "Validation: see live badge (top-right) · methodology: AUDIT.md"
          : "Валидация: см. live-значок справа сверху · методика: AUDIT.md"}
      </div>
    </div>
  );
}
