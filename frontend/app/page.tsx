"use client";

import { useEffect } from "react";

import dynamic from "next/dynamic";

import ConnectionBanner from "@/components/ConnectionBanner";
import HeroNetwork from "@/components/HeroNetwork";
import FAQPanel from "@/components/FAQPanel";
import ForecastNarrative from "@/components/ForecastNarrative";
import HistoricalAnalogue from "@/components/HistoricalAnalogue";
import MetricsPanel from "@/components/MetricsPanel";
import ModelComparisonPanel from "@/components/ModelComparisonPanel";
import NarrativePanel from "@/components/NarrativePanel";
import NewsSignalsPanel from "@/components/NewsSignalsPanel";
import OnboardingGuide from "@/components/OnboardingGuide";
import PropagationMap from "@/components/PropagationMap";
import ReadingGuide from "@/components/ReadingGuide";
import ScenarioBuilder from "@/components/ScenarioBuilder";
import ScenarioControls from "@/components/ScenarioControls";
import StatusRibbon from "@/components/StatusRibbon";
import TimelineBar from "@/components/TimelineBar";

// Below-the-fold panels: split out of the first-load bundle.
const panelFallback = () => <div className="panel h-24 shimmer" aria-hidden="true" />;
const PolicyAdvisorPanel = dynamic(() => import("@/components/PolicyAdvisorPanel"), { loading: panelFallback });
const CrisisRadarPanel = dynamic(() => import("@/components/CrisisRadarPanel"), { loading: panelFallback });
import { api } from "@/lib/api";
import { nodeName } from "@/lib/names";
import { useSimStore } from "@/lib/store";
import { useUI } from "@/lib/ui-context";

export default function Home() {
  const setScenarios = useSimStore((s) => s.setScenarios);
  const { lang } = useUI();

  // Graph snapshot is owned by ScenarioControls (it tracks the v2/v3 selector);
  // here we only load the scenario list.
  useEffect(() => {
    api.scenarios().then(setScenarios).catch(() => {});
  }, [setScenarios]);

  return (
    <main className="max-w-[1600px] mx-auto px-6 pb-6 space-y-4">
      <FAQPanel />

      {/* ── hero header with ambient network backdrop ── */}
      <header className="relative -mx-6 px-6 pt-6 mb-2">
        <HeroNetwork />
        <div className="relative z-10">
          <StatusRibbon />
        </div>
      </header>

      <ConnectionBanner />
      <OnboardingGuide />
      <ReadingGuide />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* ── left column (scenario input — first on mobile too) ── */}
        <div className="lg:col-span-3 space-y-3 fade-up fade-up-1">
          <ScenarioControls />
          <ScenarioInfo />
          <ScenarioBuilder />
          <NewsSignalsPanel />
        </div>

        {/* ── centre column ── */}
        <div className="lg:col-span-6 space-y-3 fade-up fade-up-2">
          <div className="panel p-2 overflow-hidden">
            <PropagationMap />
          </div>
          <TimelineBar />
        </div>

        {/* ── right column ── */}
        <div className="lg:col-span-3 space-y-3 fade-up fade-up-3">
          <MetricsPanel />
          <ForecastNarrative />
          <HistoricalAnalogue />
          <ModelComparisonPanel />
          <NarrativePanel />
        </div>
      </div>

      {/* ── full-width policy advisor ── */}
      <PolicyAdvisorPanel />

      {/* ── full-width Claude crisis radar ── */}
      <CrisisRadarPanel />

      <footer className="pt-6 border-t border-border-subtle text-[13px] text-text-muted leading-relaxed space-y-2">
        <div>
          {lang === "en"
            ? <>Flagship scenario: Taiwan semiconductor exports fall 70–80%. Watch the cascade ripple through automotive, electronics, and consumer goods across 12 economies. Two novel metrics: <span className="text-text-secondary">Cascade Severity Index (CSI)</span> and <span className="text-text-secondary">Economic Contagion Velocity (ECV)</span>.</>
            : <>Ключевой сценарий: экспорт полупроводников из Тайваня падает на 70–80%. Наблюдайте, как каскад распространяется на автомобильную промышленность, электронику и потребительские товары в 12 экономиках. Два новых метрики: <span className="text-text-secondary">Индекс каскадной серьёзности (CSI)</span> и <span className="text-text-secondary">Скорость экономического распространения (ECV)</span>.</>
          }
        </div>
        <div className="flex items-center gap-4 flex-wrap">
          <a href="/demo" className="btn-pill text-[12px]">
            {lang === "en" ? "Track record — what it predicted vs what happened →" : "Track record — что предсказала и что произошло →"}
          </a>
          <span className="text-[12px] px-2 py-0.5 rounded-full bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/20">
            {lang === "en" ? "Live LOO cross-validation · top-right badge" : "Live кросс-валидация · значок справа сверху"}
          </span>
          <span className="text-[12px] text-text-muted">
            {lang === "en"
              ? "Data: UN Comtrade 2019 · World Bank LPI 2018 · OECD STAN · IMF WEO 2020"
              : "Данные: UN Comtrade 2019 · World Bank LPI 2018 · OECD STAN · IMF WEO 2020"}
          </span>
        </div>
      </footer>
    </main>
  );
}

function ScenarioInfo() {
  const scenarios   = useSimStore((s) => s.scenarios);
  const selectedId  = useSimStore((s) => s.selectedScenarioId);
  const scenario    = scenarios.find((s) => s.id === selectedId);
  const { lang } = useUI();

  if (!scenario) return null;

  return (
    <div className="panel p-4 text-[13px] space-y-2">
      <div>
        <div className="text-text-muted uppercase tracking-wider text-[12px]">
          {lang === "en" ? "Selected scenario" : "Выбранный сценарий"}
        </div>
        <div className="text-text-primary font-semibold">{scenario.name}</div>
      </div>
      {scenario.description && (
        <p className="text-text-secondary leading-relaxed">{scenario.description}</p>
      )}
      <div className="hairline pt-2 space-y-1">
        <div className="text-text-muted uppercase tracking-wider text-[12px]">
          {lang === "en" ? `Shocks (${scenario.shocks.length})` : `Шоки (${scenario.shocks.length})`}
        </div>
        {scenario.shocks.map((sh, i) => (
          <div key={i} className="flex justify-between text-text-secondary num">
            <span className="truncate mr-2" title={sh.target_node_id}>{nodeName(sh.target_node_id, lang)}</span>
            <span>
              {(sh.magnitude * 100).toFixed(0)}% · {sh.duration_weeks}{lang === "en" ? "w" : "н"}
            </span>
          </div>
        ))}
      </div>
      <div className="hairline pt-2 flex justify-between text-text-muted">
        <span>{lang === "en" ? "Horizon" : "Горизонт"}</span>
        <span className="num text-text-secondary">
          {scenario.horizon_weeks} {lang === "en" ? "weeks" : "нед."}
        </span>
      </div>
    </div>
  );
}
