"use client";

import { useState } from "react";
import { FAQ, useUI } from "@/lib/ui-context";

export default function FAQPanel() {
  const { lang, t, faqOpen, toggleFaq } = useUI();
  const [openItem, setOpenItem] = useState<string | null>(null);
  const sections = FAQ[lang];

  if (!faqOpen) return null;

  return (
    <>
      {/* backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
        onClick={toggleFaq}
      />

      {/* drawer */}
      <div className="fixed top-0 right-0 bottom-0 z-50 w-[420px] max-w-[95vw] flex flex-col bg-bg-elevated border-l border-border-strong shadow-2xl overflow-hidden">
        {/* header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border-subtle shrink-0">
          <h2 className="text-sm font-bold uppercase tracking-wider text-text-primary">
            {t("faqTitle")}
          </h2>
          <button
            onClick={toggleFaq}
            className="text-text-muted hover:text-text-primary transition text-[13px] px-2 py-1 rounded border border-border-subtle hover:border-border-strong"
          >
            {t("faqClose")} ✕
          </button>
        </div>

        {/* trust strip — points users to the live, honest validation panel */}
        <div className="px-5 py-2.5 bg-accent-cyan/5 border-b border-border-subtle shrink-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[12px] px-2 py-0.5 rounded-full bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/30 font-semibold">
              LOO-CV
            </span>
            <span className="text-[12px] text-text-muted">
              {lang === "en"
                ? "Live cross-validation in top-right badge · full report: /api/v1/cv-report"
                : "Live-кросс-валидация в значке справа сверху · полный отчёт: /api/v1/cv-report"}
            </span>
          </div>
        </div>

        {/* scrollable content */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {sections.map((section) => (
            <div key={section.title}>
              <h3 className="text-[12px] font-bold uppercase tracking-widest text-text-muted mb-2 pb-1 border-b border-border-subtle">
                {section.title}
              </h3>
              <div className="space-y-1">
                {section.items.map((item) => {
                  const id = `${section.title}::${item.q}`;
                  const isOpen = openItem === id;
                  return (
                    <div
                      key={id}
                      className="rounded border border-border-subtle overflow-hidden"
                    >
                      <button
                        onClick={() => setOpenItem(isOpen ? null : id)}
                        className="w-full text-left px-3 py-2.5 flex items-start justify-between gap-2 hover:bg-bg-base/50 transition"
                      >
                        <span className="text-[13px] font-medium text-text-primary leading-snug">
                          {item.q}
                        </span>
                        <span className="text-text-muted text-[13px] shrink-0 mt-0.5">
                          {isOpen ? "▴" : "▾"}
                        </span>
                      </button>
                      {isOpen && (
                        <div className="px-3 pb-3 pt-1 border-t border-border-subtle/50 bg-bg-base/30">
                          <p className="text-[13px] text-text-secondary leading-relaxed">
                            {item.a}
                          </p>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}

          {/* data sources footer */}
          <div className="rounded border border-border-subtle bg-bg-base/40 p-3 space-y-1.5">
            <div className="text-[12px] font-bold uppercase tracking-widest text-text-muted">
              {lang === "en" ? "Primary data sources" : "Первичные источники данных"}
            </div>
            {[
              { label: "UN Comtrade 2019", detail: lang === "en" ? "Bilateral trade flows HS 8541/8542/8703" : "Двусторонние торговые потоки HS 8541/8542/8703" },
              { label: "World Bank LPI 2018", detail: lang === "en" ? "Logistics Performance Index → resilience" : "Индекс логистики → устойчивость" },
              { label: "OECD STAN 2019", detail: lang === "en" ? "Sector GDP shares by country" : "Доли секторов в ВВП по странам" },
              { label: "IMF WEO 2020", detail: lang === "en" ? "Taiwan GDP (excluded from World Bank)" : "ВВП Тайваня (отсутствует в ВБ)" },
              { label: "IEA / IMO 2020", detail: lang === "en" ? "Chokepoint exposure & disruption probabilities" : "Зависимость от проливов и вероятности нарушений" },
            ].map((s) => (
              <div key={s.label} className="flex gap-2 text-[12px]">
                <span className="text-accent-cyan font-semibold w-36 shrink-0">{s.label}</span>
                <span className="text-text-muted">{s.detail}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
