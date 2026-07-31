"use client";

import { useState } from "react";

import { useUI } from "@/lib/ui-context";

/**
 * Always-visible plain-language explainer for the numbers on screen.
 *
 * The metric tooltips are hover-only, so on touch devices they are effectively
 * unreachable — this panel carries the same explanations as tappable, readable
 * body text. Collapsed by default on repeat visits would need persistence we
 * do not have server-side, so it opens expanded: a first-time visitor should
 * not have to hunt for what CSI means.
 */

type Entry = { term: string; short: string; long: string };

const ENTRIES: Record<"en" | "ru", Entry[]> = {
  en: [
    {
      term: "The map",
      short: "Each dot is a country + industry.",
      long: "A dot is one country's one industry — “Taiwan · semiconductors”, “Germany · automotive”. Lines are real dependencies: who buys inputs from whom, derived from UN Comtrade and OECD input-output tables. Five extra dots are maritime chokepoints (Suez, Panama, Malacca, Hormuz, Taiwan Strait) — passages rather than producers.",
    },
    {
      term: "CSI",
      short: "How bad it is right now, network-wide (0–1).",
      long: "Cascade Severity Index — our own metric. Every node's damage is weighted by how central it is in the network, how dependent it is on suppliers, how fragile it is, and how slowly it recovers, then averaged. So a hit on a hub weighs more than the same hit on a peripheral node — which a plain sum of losses cannot tell apart.",
    },
    {
      term: "ECV",
      short: "How fast the cascade is spreading.",
      long: "Economic Contagion Velocity — our own metric: the share of nodes newly entering disruption each week. If CSI is the patient's temperature, ECV is how fast the infection is spreading. Rising ECV means the shock is still accelerating; falling ECV means the cascade is burning out.",
    },
    {
      term: "Output loss",
      short: "How much production a node lost, as a share.",
      long: "0.30 means that node is producing 30% less than normal. This is the quantity we validate against reality: for each historical event we found the officially reported figure (industry statistics agencies, central banks, IMF) and compare the model's prediction to it.",
    },
    {
      term: "Weeks to peak / recovery",
      short: "When it gets worst, and when it lets go.",
      long: "The shape of the disruption in time, not just its size. Peak week is when damage is deepest; recovery is when output climbs back to ~90% of normal. Recovery lags the shock — an economy carries a “scar” and does not snap back the moment the shock ends (this is called hysteresis).",
    },
    {
      term: "Inventory buffer",
      short: "Why nothing happens at first.",
      long: "A factory with stock on the shelf keeps running for a while after its supplier fails. That is why the cascade often shows a delay before damage appears — and why short disruptions can pass through almost unnoticed while long ones bite hard.",
    },
    {
      term: "Bullwhip",
      short: "Panic buying amplifies the shortage.",
      long: "A real logistics effect: once a shortage starts, buyers order extra “just in case”, so orders further up the chain swell more than the actual gap. The engine amplifies incoming pressure by 1.25× for nodes in that state.",
    },
    {
      term: "Graph v2 / v3",
      short: "Two maps: hand-built (41 dots) vs OECD data (405 dots).",
      long: "v2 is the calibrated hand-built map. v3 is built straight from OECD input-output tables — ten times more nodes, no hand-set weights. v3 reaches far more of the nodes that history actually hit (0.29 → 0.79), which is one of this project's findings: the completeness of the network matters more than tuning the model.",
    },
  ],
  ru: [
    {
      term: "Карта",
      short: "Каждая точка — страна + отрасль.",
      long: "Точка — это одна отрасль одной страны: «Тайвань · полупроводники», «Германия · автопром». Линии — реальные зависимости: кто у кого закупает комплектующие, по данным UN Comtrade и межотраслевых таблиц OECD. Ещё пять точек — морские узкие места (Суэц, Панама, Малакка, Ормуз, Тайваньский пролив): это проходы, а не производители.",
    },
    {
      term: "CSI",
      short: "Насколько всё плохо прямо сейчас по всей сети (0–1).",
      long: "Индекс тяжести каскада — наша собственная метрика. Урон каждого узла взвешивается тем, насколько узел важен в сети, насколько зависит от поставщиков, насколько хрупок и как долго восстанавливается, а потом усредняется. Поэтому удар по важному узлу весит больше, чем такой же удар по периферийному — обычная сумма потерь этого не различает.",
    },
    {
      term: "ECV",
      short: "Как быстро каскад расползается.",
      long: "Скорость экономического заражения — наша метрика: доля узлов, которые впервые попадают под нарушение за неделю. Если CSI — это температура больного, то ECV — скорость распространения заражения. ECV растёт — шок ещё разгоняется; падает — каскад выдыхается.",
    },
    {
      term: "Потеря выпуска",
      short: "Насколько просело производство узла, в долях.",
      long: "0,30 значит, что узел выпускает на 30% меньше обычного. Именно эту величину мы сверяем с реальностью: для каждого исторического события мы нашли официально опубликованную цифру (отраслевые статагентства, центробанки, МВФ) и сравниваем с ней предсказание модели.",
    },
    {
      term: "Недели до пика / восстановления",
      short: "Когда станет хуже всего и когда отпустит.",
      long: "Это форма нарушения во времени, а не только его размер. Пик — когда урон максимален; восстановление — когда выпуск возвращается к ~90% от нормы. Восстановление отстаёт от самого шока: экономика несёт «шрам» и не отскакивает мгновенно, как только удар кончился (это называется гистерезис).",
    },
    {
      term: "Запасы на складе",
      short: "Почему сначала как будто ничего не происходит.",
      long: "Завод со складским запасом продолжает работать какое-то время после того, как поставщик встал. Поэтому в каскаде часто есть задержка перед появлением урона — и поэтому короткие сбои могут пройти почти незаметно, а длинные бьют сильно.",
    },
    {
      term: "Эффект хлыста",
      short: "Паническая закупка раздувает дефицит.",
      long: "Реальный эффект из логистики: как только начинается дефицит, покупатели заказывают впрок «на всякий случай», и вверх по цепочке заказы раздуваются сильнее, чем реальная нехватка. Движок усиливает входящее давление в 1,25 раза для узлов в этом состоянии.",
    },
    {
      term: "Граф v2 / v3",
      short: "Две карты: ручная (41 точка) и по данным OECD (405 точек).",
      long: "v2 — откалиброванная карта, собранная вручную. v3 построена напрямую из межотраслевых таблиц OECD: в десять раз больше узлов и никаких вручную выставленных весов. v3 достаёт гораздо больше узлов, которые в реальности пострадали (0,29 → 0,79) — и это один из выводов проекта: полнота сети важнее подстройки модели.",
    },
  ],
};

export default function ReadingGuide() {
  const { lang } = useUI();
  const [open, setOpen] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const entries = ENTRIES[lang];

  return (
    <section className="panel p-4">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-3 text-left group"
        aria-expanded={open}
      >
        <span className="flex items-center gap-2.5 min-w-0">
          <span
            className="w-6 h-6 shrink-0 rounded-md grid place-items-center text-[12px] font-bold
                       bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/30"
            aria-hidden="true"
          >
            ?
          </span>
          <span className="min-w-0">
            <span className="block text-sm font-semibold text-text-primary">
              {lang === "en" ? "How to read this" : "Как это читать"}
            </span>
            <span className="block text-[12px] text-text-muted truncate">
              {lang === "en"
                ? "Plain-language guide to every number on screen"
                : "Простое объяснение каждого числа на экране"}
            </span>
          </span>
        </span>
        <span className="text-text-muted group-hover:text-text-primary transition text-[13px] shrink-0">
          {open ? "▴" : "▾"}
        </span>
      </button>

      {open && (
        <div className="mt-3 pt-3 hairline grid gap-2 sm:grid-cols-2">
          {entries.map((e) => {
            const isOpen = expanded === e.term;
            return (
              <div
                key={e.term}
                className="rounded-lg border border-border-subtle bg-bg-base/40 overflow-hidden"
              >
                <button
                  onClick={() => setExpanded(isOpen ? null : e.term)}
                  className="w-full text-left px-3 py-2.5 hover:bg-bg-base/70 transition"
                  aria-expanded={isOpen}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-[13px] font-semibold text-accent-cyan">
                        {e.term}
                      </div>
                      <div className="text-[13px] text-text-secondary leading-snug mt-0.5">
                        {e.short}
                      </div>
                    </div>
                    <span className="text-text-muted text-[12px] shrink-0 mt-0.5">
                      {isOpen ? "−" : "+"}
                    </span>
                  </div>
                </button>
                {isOpen && (
                  <p className="px-3 pb-3 text-[13px] text-text-secondary leading-relaxed border-t border-border-subtle/50">
                    <span className="block pt-2">{e.long}</span>
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
