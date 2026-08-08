"use client";

import ConnectionBanner from "@/components/ConnectionBanner";
import PredictionReveal from "@/components/PredictionReveal";
import { useUI } from "@/lib/ui-context";

/**
 * A presentation page — one screen to hand a judge, with nothing to configure.
 *
 * The simulator page is an instrument: it has controls, and it assumes you know
 * what you want to run. This page assumes the opposite. It answers, in order,
 * the two questions a sceptical stranger actually asks — "does it predict
 * anything?" and "where does it fail?" — and it answers the second one without
 * being asked, because that is the only way an answer to the first is worth
 * anything.
 */
export default function DemoPage() {
  const { lang, toggleLang, t } = useUI();
  const ru = lang === "ru";
  const tr = (en: string, r: string) => (ru ? r : en);

  return (
    <main className="max-w-[1100px] mx-auto px-5 sm:px-6 py-6 space-y-5">
      <div className="border-b border-border-subtle pb-3">
        <div className="flex items-start justify-between gap-3">
          <h1 className="text-xl sm:text-2xl font-extrabold tracking-tight min-w-0">
            <a href="/" className="title-gradient hover:opacity-80 transition">GEDS</a>
            <span className="text-text-secondary font-semibold text-[12px] sm:text-sm uppercase tracking-[0.12em] sm:tracking-[0.2em] ml-2 sm:ml-3">
              {tr("Track record", "Track record")}
            </span>
          </h1>
          <div className="flex items-center gap-2 shrink-0">
            <a href="/" className="btn-pill">{tr("← Simulator", "← Симулятор")}</a>
            <a href="/validation" className="btn-pill">{tr("Validation →", "Валидация →")}</a>
            <button onClick={toggleLang} className="btn-pill">{t("langBtn")}</button>
          </div>
        </div>
      </div>

      <ConnectionBanner />

      <PredictionReveal />

      {/* ── the bugs. real ones, with the numbers they actually moved ── */}
      <section className="panel p-5 sm:p-7 space-y-4">
        <header className="space-y-1.5">
          <h2 className="text-lg sm:text-xl font-semibold text-text-primary">
            {tr("Four bugs found in our own engine", "Четыре бага, найденных в собственном движке")}
          </h2>
          <p className="text-[13px] sm:text-[14px] text-text-secondary leading-relaxed max-w-3xl">
            {tr(
              "Two of these destroyed a result we had already published. They are listed because a model nobody has attacked is not a validated model — and because the only way to know whether a number is real is to try to break it.",
              "Два из них уничтожили результат, который мы уже опубликовали. Они здесь потому, что модель, которую никто не атаковал, не является проверенной — и потому, что единственный способ узнать, настоящее ли число, это попробовать его сломать.",
            )}
          </p>
        </header>

        <ol className="space-y-3">
          <Bug
            n={1}
            title={tr(
              "Ranking code gave different ranks to identical values",
              "Код ранжирования давал разные ранги одинаковым значениям",
            )}
            body={tr(
              "Twelve of fifteen peak-timing predictions were exactly 0.0. A double-argsort ranked those ties in array order, manufacturing correlation out of nothing but the order events happened to be listed in.",
              "Двенадцать из пятнадцати предсказаний тайминга пика были ровно 0,0. Двойной argsort ранжировал эти совпадения в порядке массива, производя корреляцию буквально из порядка перечисления событий.",
            )}
            effect={tr("peak timing 0.61 → 0.07 — the result collapsed to chance", "тайминг пика 0,61 → 0,07 — результат обрушился до случайности")}
            tone="bad"
          />
          <Bug
            n={2}
            title={tr(
              "Then we found why it was at chance, and fixed it properly",
              "Затем нашли, почему он на уровне случайности, и починили по-настоящему",
            )}
            body={tr(
              "Every forcing shape in the engine peaked at week zero, so slow-building events — port congestion, drought, demand collapse — could not be represented at all. A rising shape was added, with the acceptance criteria written down BEFORE the experiment was run.",
              "Все формы шока в движке имели максимум в нулевой неделе, поэтому медленно нарастающие события — портовые заторы, засухи, коллапс спроса — не могли быть представлены вообще. Добавлена нарастающая форма, причём критерии приёмки были записаны ДО прогона эксперимента.",
            )}
            effect={tr("peak timing 0.07 → 0.69, at a cost of +0.0001 MAE", "тайминг пика 0,07 → 0,69 ценой +0,0001 MAE")}
            tone="good"
          />
          <Bug
            n={3}
            title={tr(
              "A switch that turned nothing off",
              "Переключатель, который ничего не выключал",
            )}
            body={tr(
              "The flag disabling the SEIRS state machine neutralised its three modifiers at startup — but the update ran unconditionally every step and re-armed them immediately. The ablation row for 'state machine off' had been silently duplicating the row above it.",
              "Флаг, отключающий машину состояний SEIRS, обнулял три её модификатора при инициализации — но обновление выполнялось безусловно на каждом шаге и немедленно возвращало их. Строка абляции «машина состояний выключена» молча дублировала строку выше.",
            )}
            effect={tr("that ablation was 0.0242, in truth it is 0.0166", "эта абляция показывала 0,0242, на деле 0,0166")}
            tone="bad"
          />
          <Bug
            n={4}
            title={tr(
              "One axis was being starved by another",
              "Одна ось голодала из-за другой",
            )}
            body={tr(
              "The harness discarded an event entirely if it had no timing research — before ever checking whether it had a magnitude measurement. Six magnitude targets existed; five were being scored.",
              "Харнесс выбрасывал событие целиком, если по нему нет исследования тайминга — не проверив, есть ли измерение магнитуды. Целей магнитуды было шесть, скорилось пять.",
            )}
            effect={tr("magnitude n 5 → 6, CI [−1.00, 1.00] → [−0.09, 1.00]", "магнитуда n 5 → 6, ДИ [−1,00; 1,00] → [−0,09; 1,00]")}
            tone="good"
          />
        </ol>

        <p className="text-[12px] text-text-muted leading-relaxed border-t border-border-subtle pt-3">
          {tr(
            "Every number above is reproducible from the public repository with one command, and every change is a reviewed diff against a frozen snapshot — a numeric result cannot move without the test suite failing first.",
            "Любое число выше воспроизводится из открытого репозитория одной командой, а каждое изменение — отрецензированный диф против замороженного снимка: численный результат не может сдвинуться, не уронив тесты.",
          )}
        </p>
      </section>
    </main>
  );
}

function Bug({
  n,
  title,
  body,
  effect,
  tone,
}: {
  n: number;
  title: string;
  body: string;
  effect: string;
  tone: "good" | "bad";
}) {
  return (
    <li className="rounded-lg border border-border-subtle bg-bg-base/40 p-3.5 space-y-1.5">
      <div className="flex items-start gap-2.5">
        <span className="shrink-0 mt-0.5 w-6 h-6 grid place-items-center rounded-md text-[12px] font-bold
                         bg-accent-violet/15 text-accent-violet border border-accent-violet/30">
          {n}
        </span>
        <div className="min-w-0 space-y-1.5">
          <div className="text-[14px] font-semibold text-text-primary leading-snug">{title}</div>
          <p className="text-[13px] text-text-secondary leading-relaxed">{body}</p>
          <div
            className={`num text-[13px] font-semibold ${
              tone === "good" ? "text-accent-cyan" : "text-red-400"
            }`}
          >
            {effect}
          </div>
        </div>
      </div>
    </li>
  );
}
