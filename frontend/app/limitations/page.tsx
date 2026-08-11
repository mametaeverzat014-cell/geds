"use client";

import { useUI } from "@/lib/ui-context";

/**
 * The boundary page.
 *
 * Every entry is a claim this project is NOT entitled to make, the measurement
 * that establishes the boundary, and the thing that would move it. The order is
 * deliberate: the size of the benchmark comes first, because its minimum
 * detectable effect is larger than most of the differences the project would
 * otherwise like to report, and three of the six sections below are downstream
 * of that single number.
 *
 * Nothing here was found by an outside reviewer. It is published in the shape
 * it was found in.
 */

type Tone = "neutral" | "cyan" | "violet" | "gold" | "warn" | "bad" | "good";

const TONE_TEXT: Record<Tone, string> = {
  neutral: "text-text-primary",
  cyan: "text-accent-cyan",
  violet: "text-accent-violet",
  gold: "text-accent-gold",
  warn: "text-sev-4",
  bad: "text-sev-5",
  good: "text-sev-1",
};

const TONE_FILL: Record<Tone, string> = {
  neutral: "bg-text-primary",
  cyan: "bg-accent-cyan",
  violet: "bg-accent-violet",
  gold: "bg-accent-gold",
  warn: "bg-sev-4",
  bad: "bg-sev-5",
  good: "bg-sev-1",
};

export default function LimitationsPage() {
  const { lang, toggleLang, t } = useUI();
  const ru = lang === "ru";
  const tr = (en: string, r: string) => (ru ? r : en);

  const EVIDENCE = tr("Measurement", "Измерение");
  const FIX = tr("What would fix it", "Что это исправило бы");

  return (
    <main className="max-w-[1100px] mx-auto px-5 sm:px-6 py-6 space-y-5">
      {/* ── header ─────────────────────────────────────────────────────── */}
      <div className="border-b border-border-subtle pb-3">
        <div className="flex items-start justify-between gap-3">
          <h1 className="text-xl sm:text-2xl font-extrabold tracking-tight min-w-0">
            <a href="/" className="title-gradient hover:opacity-80 transition">GEDS</a>
            <span className="text-text-secondary font-semibold text-[12px] sm:text-sm uppercase tracking-[0.12em] sm:tracking-[0.2em] ml-2 sm:ml-3">
              {tr("Limitations", "Ограничения")}
            </span>
          </h1>
          <div className="flex items-center gap-2 shrink-0">
            <a href="/" className="btn-pill">{tr("← Simulator", "← Симулятор")}</a>
            <button onClick={toggleLang} className="btn-pill">{t("langBtn")}</button>
          </div>
        </div>
      </div>

      {/* ── hero ───────────────────────────────────────────────────────── */}
      <section className="panel p-5 sm:p-8 space-y-5 fade-up">
        <div className="flex items-center gap-2.5">
          <span className="glow-dot h-1.5 w-1.5 bg-sev-4 text-sev-4 inline-block" aria-hidden="true" />
          <span className="text-[11px] uppercase tracking-[0.28em] text-text-muted">
            {tr("Measured bounds", "Измеренные границы")}
          </span>
        </div>

        <h2 className="text-[26px] sm:text-[44px] font-extrabold tracking-tight leading-[1.05]">
          <span className="title-gradient">
            {tr("What GEDS cannot claim", "Чего GEDS не может утверждать")}
          </span>
        </h2>

        <div className="space-y-3 max-w-3xl">
          <p className="text-[14px] sm:text-[16px] text-text-secondary leading-relaxed">
            {tr(
              "Each entry below is a claim this project is not entitled to make, the measurement that establishes the boundary, and the thing that would move it. None of it was found by an outside reviewer. It is published in the shape it was found in.",
              "Каждый пункт ниже — утверждение, на которое проект не имеет права, измерение, устанавливающее границу, и то, что сдвинуло бы её. Ничего из этого не нашёл внешний рецензент. Всё опубликовано в том виде, в каком было найдено.",
            )}
          </p>
          <p className="text-[13px] sm:text-[15px] text-text-secondary leading-relaxed">
            {tr(
              "Read (01) first. The benchmark's minimum detectable effect is larger than most of the differences this project would like to report, and three of the sections that follow are downstream of that one number.",
              "Начните с (01). Минимально детектируемый эффект бенчмарка больше, чем большинство различий, о которых проект хотел бы сообщить, и три следующих раздела — следствие этого одного числа.",
            )}
          </p>
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5 sm:gap-3 fade-up fade-up-2">
          <Stat
            value="27"
            tone="neutral"
            label={tr(
              "primary-sourced historical events in the benchmark, 1999–2023",
              "исторических событий с первичными источниками в бенчмарке, 1999–2023",
            )}
          />
          <Stat
            value="≈166"
            tone="gold"
            label={tr(
              "events the observed magnitude gap would need to be resolvable",
              "событий нужно, чтобы наблюдаемый разрыв по величине стал различим",
            )}
          />
          <Stat
            value="0 / 6"
            tone="bad"
            label={tr(
              "pairwise magnitude comparisons surviving Holm correction",
              "попарных сравнений величины проходят поправку Холма",
            )}
          />
          <Stat
            value="1 / 3"
            tone="warn"
            label={tr(
              "trajectory axes surviving family-wise correction",
              "осей траектории проходят поправку на семейство гипотез",
            )}
          />
        </div>
      </section>

      {/* ── 01 · magnitude ─────────────────────────────────────────────── */}
      <Limitation
        index="01"
        kicker={tr("Magnitude", "Величина")}
        title={tr(
          "The benchmark is too small to resolve magnitude",
          "Бенчмарк слишком мал, чтобы различать величину",
        )}
        claim={tr(
          "We cannot claim GEDS predicts the size of a shock better than a parameter-free baseline. On point magnitude it is the worst of the four models we ran — and the benchmark is not large enough to establish even that ordering.",
          "Мы не можем утверждать, что GEDS предсказывает размер шока лучше, чем безпараметрический бейзлайн. По точечной величине это худшая из четырёх запущенных моделей — и бенчмарк недостаточно велик, чтобы установить даже такой порядок.",
        )}
        evidenceLabel={EVIDENCE}
        fixLabel={FIX}
        fix={tr(
          "About 166 primary-sourced events at the gap size actually observed — more than six times the benchmark that exists. Or a model whose margin over the baselines exceeds 0.0184 MAE, which no version of this engine has produced.",
          "Около 166 событий с первичными источниками при фактически наблюдаемом разрыве — более чем вшестеро больше существующего бенчмарка. Либо модель, чьё преимущество над бейзлайнами превышает 0,0184 MAE: ни одна версия этого движка такого не давала.",
        )}
      >
        <div className="overflow-x-auto -mx-1 px-1">
          <table className="w-full min-w-[470px] text-[13px]">
            <thead>
              <tr className="text-text-muted uppercase text-[11px] tracking-widest">
                <th className="text-left py-1.5 font-bold">{tr("model", "модель")}</th>
                <th className="text-right py-1.5 font-bold">{tr("params", "парам.")}</th>
                <th className="text-right py-1.5 font-bold">MAE</th>
                <th className="text-right py-1.5 font-bold">{tr("95% bootstrap CI", "95% бутстреп-ДИ")}</th>
              </tr>
            </thead>
            <tbody>
              {[
                { m: "Leontief", p: "0", mae: "0.0168", ci: "[0.0079, 0.0278]", worst: false },
                { m: "Linear Diffusion", p: "0", mae: "0.0171", ci: "[0.0089, 0.0286]", worst: false },
                { m: tr("Naive mean", "Наивное среднее"), p: "0", mae: "0.0208", ci: "[0.0126, 0.0311]", worst: false },
                { m: "GEDS", p: "5", mae: "0.0242", ci: "[0.0110, 0.0402]", worst: true },
              ].map((r) => (
                <tr
                  key={r.mae}
                  className={`border-t border-border-subtle/40 ${r.worst ? "bg-sev-5/[0.07]" : ""}`}
                >
                  <td className={`py-1.5 pr-3 ${r.worst ? "text-sev-5 font-bold" : "text-text-primary"}`}>
                    {r.m}
                    {r.worst && (
                      <span className="ml-2 text-[11px] uppercase tracking-wider font-semibold text-sev-5/80">
                        {tr("worst of four", "худшая из четырёх")}
                      </span>
                    )}
                  </td>
                  <td className="py-1.5 num text-right text-text-muted">{r.p}</td>
                  <td className={`py-1.5 num text-right ${r.worst ? "text-sev-5 font-bold" : "text-text-primary"}`}>
                    {r.mae}
                  </td>
                  <td className="py-1.5 num text-right text-text-muted whitespace-nowrap">{r.ci}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-[12px] text-text-muted leading-snug">
          {tr(
            "Lower MAE is better. The confidence intervals of all four models overlap.",
            "Меньший MAE — лучше. Доверительные интервалы всех четырёх моделей перекрываются.",
          )}
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
          <Stat value="0.0184" tone="gold" small
                label={tr("minimum detectable effect, MAE", "минимально детектируемый эффект, MAE")} />
          <Stat value="≈0.007" tone="neutral" small
                label={tr("largest gap actually observed, MAE", "крупнейший фактически наблюдаемый разрыв, MAE")} />
          <Stat value="0 / 6" tone="bad" small
                label={tr("pairwise differences surviving Holm", "попарных различий проходят Холма")} />
        </div>

        <div className="space-y-1.5 pt-1">
          <div className="flex items-baseline justify-between text-[12px]">
            <span className="text-text-secondary">
              {tr("benchmark size vs. size required", "размер бенчмарка против требуемого")}
            </span>
            <span className="num text-text-muted">
              27 <span className="text-text-muted/60">/</span> ≈166
            </span>
          </div>
          {/* the bar is the argument: the shortfall is not marginal */}
          <div className="bar-track h-2 w-full">
            <div
              className="bar-fill"
              style={{
                width: `${(27 / 166) * 100}%`,
                background: "linear-gradient(90deg, #F97316, #EF4444)",
              }}
            />
          </div>
        </div>
      </Limitation>

      {/* ── 02 · identifiability ───────────────────────────────────────── */}
      <Limitation
        index="02"
        kicker={tr("Parameters", "Параметры")}
        title={tr(
          "The parameters are not identified",
          "Параметры не идентифицированы",
        )}
        claim={tr(
          "The five engine parameters do not have single well-determined values. The published fit is a point the optimiser reached, not a point the data pins down.",
          "Пять параметров движка не имеют единственных определённых значений. Опубликованная подгонка — точка, куда пришёл оптимизатор, а не точка, которую фиксируют данные.",
        )}
        evidenceLabel={EVIDENCE}
        fixLabel={FIX}
        fix={tr(
          "Fewer free parameters; or parameters measured outside the benchmark; or enough events that dropping one cannot move a parameter by 34.9 medians. Until then the fitted values should be read as ranges the data failed to exclude, not as estimates.",
          "Меньше свободных параметров; либо параметры, измеренные вне бенчмарка; либо столько событий, чтобы исключение одного не двигало параметр на 34,9 медианы. До тех пор подогнанные значения следует читать как диапазоны, которые данные не смогли исключить, а не как оценки.",
        )}
      >
        <div className="space-y-3">
          <Finding
            value="3 / 5"
            tone="warn"
            total={5}
            filled={3}
            text={tr(
              "engine parameters sit pinned against their prior-box bounds — the optimiser pushed them to the edge of the space it was allowed to search.",
              "параметров движка упираются в границы априорного бокса — оптимизатор прижал их к краю разрешённого пространства поиска.",
            )}
          />
          <Finding
            value="3 / 5"
            tone="warn"
            total={5}
            filled={3}
            text={tr(
              "have a global fit lying outside the entire leave-one-out range — the value fitted on all 27 events is not contained in any of the fits made without one of them.",
              "имеют глобальную подгонку вне всего диапазона leave-one-out — значение, подогнанное на всех 27 событиях, не содержится ни в одной из подгонок без одного из них.",
            )}
          />
          <Finding
            value="34.9×"
            tone="bad"
            text={tr(
              "is how far amplification_mu moves — measured in its own medians — when a single event of 27 is dropped.",
              "настолько сдвигается amplification_mu, измеренный в его собственных медианах, при исключении одного события из 27.",
            )}
          />
          <Finding
            value="33%"
            tone="bad"
            text={tr(
              "of differential-evolution restarts converged. The optimisation surface does not deliver the same answer from a different starting point.",
              "рестартов дифференциальной эволюции сошлись. Поверхность оптимизации не выдаёт тот же ответ из другой стартовой точки.",
            )}
          />
        </div>
      </Limitation>

      {/* ── 03 · ablation ──────────────────────────────────────────────── */}
      <Limitation
        index="03"
        kicker={tr("Ablation", "Абляция")}
        title={tr(
          "The ablation cannot resolve any component",
          "Абляция не различает ни одного компонента",
        )}
        claim={tr(
          "We cannot say which parts of the engine are doing work. Not that they do none — that this test cannot tell the difference.",
          "Мы не можем сказать, какие части движка выполняют работу. Не то чтобы они её не выполняли — этот тест не способен различить.",
        )}
        evidenceLabel={EVIDENCE}
        fixLabel={FIX}
        fix={tr(
          "The same thing (01) needs: a benchmark whose minimum detectable effect is smaller than the component effects. Until that exists, no component in this engine has earned its place on evidence.",
          "То же, что нужно (01): бенчмарк, чей минимально детектируемый эффект меньше эффектов компонентов. Пока его нет, ни один компонент этого движка не заслужил своё место по данным.",
        )}
      >
        <div className="space-y-3">
          <Finding
            value="0 / 6"
            tone="bad"
            total={6}
            filled={0}
            text={tr(
              "component deltas are distinguishable from zero after Holm correction.",
              "дельт компонентов отличимы от нуля после поправки Холма.",
            )}
          />
          <Finding
            value="0.0184"
            tone="gold"
            text={tr(
              "MAE is the benchmark's own minimum detectable effect. Every ablation delta is smaller than it — the components are being measured with an instrument too coarse to read them.",
              "MAE — собственный минимально детектируемый эффект бенчмарка. Каждая дельта абляции меньше него: компоненты измеряются инструментом, слишком грубым для них.",
            )}
          />
        </div>
      </Limitation>

      {/* ── 04 · trajectory axes ───────────────────────────────────────── */}
      <Limitation
        index="04"
        kicker={tr("Trajectory", "Траектория")}
        title={tr(
          "Two of three trajectory axes fail family-wise correction",
          "Две из трёх осей траектории не проходят поправку на семейство гипотез",
        )}
        claim={tr(
          "Rank agreement on cascade shape holds on one axis of three. Peak magnitude and weeks-to-peak do not survive correcting for the fact that three axes were tested at once.",
          "Ранговое согласие по форме каскада держится на одной оси из трёх. Пиковая величина и недели до пика не переживают поправку на то, что три оси проверялись одновременно.",
        )}
        evidenceLabel={EVIDENCE}
        fixLabel={FIX}
        fix={tr(
          "More scored nodes per axis — n=6 on peak magnitude is the binding constraint. The recovery result also has to hold as the benchmark grows: a family-wise lower bound of +0.044 is not a margin to build on.",
          "Больше оценённых узлов на ось — n=6 по пиковой величине является связывающим ограничением. Результату по восстановлению также предстоит устоять при росте бенчмарка: нижняя граница по семейству +0,044 — не тот запас, на котором строят.",
        )}
      >
        <div className="overflow-x-auto -mx-1 px-1">
          <table className="w-full min-w-[560px] text-[13px]">
            <thead>
              <tr className="text-text-muted uppercase text-[11px] tracking-widest">
                <th className="text-left py-1.5 font-bold">{tr("axis", "ось")}</th>
                <th className="text-right py-1.5 font-bold">n</th>
                <th className="text-right py-1.5 font-bold">ρ</th>
                <th className="text-right py-1.5 font-bold">{tr("95% CI", "95% ДИ")}</th>
                <th className="text-right py-1.5 font-bold">{tr("family-wise", "по семейству")}</th>
                <th className="text-right py-1.5 font-bold">{tr("survives", "проходит")}</th>
              </tr>
            </thead>
            <tbody>
              {[
                {
                  axis: tr("peak magnitude", "пиковая величина"),
                  n: "6", rho: "+0.714",
                  ci: "[−0.091, +1.000]", fw: "[−1.00, +1.00]", ok: false,
                },
                {
                  axis: tr("weeks to peak", "недели до пика"),
                  n: "15", rho: "+0.691",
                  ci: "[+0.201, +0.869]", fw: "[+0.000, +0.904]", ok: false,
                },
                {
                  axis: tr("recovery weeks", "недели восстановления"),
                  n: "11", rho: "+0.711",
                  ci: "[+0.215, +0.917]", fw: "[+0.044, +0.962]", ok: true,
                },
              ].map((r) => (
                <tr key={r.n} className={`border-t border-border-subtle/40 ${r.ok ? "bg-sev-1/[0.06]" : ""}`}>
                  <td className="py-1.5 pr-3 text-text-primary">{r.axis}</td>
                  <td className="py-1.5 num text-right text-text-muted">{r.n}</td>
                  <td className="py-1.5 num text-right text-text-primary">{r.rho}</td>
                  <td className="py-1.5 num text-right text-text-muted whitespace-nowrap">{r.ci}</td>
                  <td className={`py-1.5 num text-right whitespace-nowrap ${r.ok ? "text-sev-1" : "text-sev-4"}`}>
                    {r.fw}
                  </td>
                  <td className={`py-1.5 text-right font-bold text-[12px] uppercase tracking-wider ${r.ok ? "text-sev-1" : "text-sev-5"}`}>
                    {r.ok ? tr("yes", "да") : tr("no", "нет")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          <Stat value="+0.044" tone="warn" small
                label={tr(
                  "family-wise lower bound of the only surviving axis",
                  "нижняя граница по семейству у единственной прошедшей оси",
                )} />
          <Stat value="21.3" tone="neutral" small
                label={tr(
                  "independent observations carried by 30 node observations across 11 events (ICC 0.237, design effect 1.41)",
                  "независимых наблюдений несут 30 наблюдений по узлам в 11 событиях (ICC 0.237, design effect 1.41)",
                )} />
        </div>

        <p className="text-[12px] text-text-muted leading-relaxed">
          {tr(
            "These are orderings, never magnitudes. A surviving rank correlation says the engine puts nodes in roughly the right sequence; it says nothing about how large the values are — that is (01). Node-level scoring is also not 30 independent observations: it carries roughly double the information of a single event, not thirty times.",
            "Это упорядочивания, а не величины. Прошедшая ранговая корреляция говорит, что движок расставляет узлы примерно в правильной последовательности; она ничего не говорит о размере значений — это (01). Оценка на уровне узлов — это также не 30 независимых наблюдений: она несёт примерно вдвое больше информации, чем одно событие, а не в тридцать раз.",
          )}
        </p>
      </Limitation>

      {/* ── 05 · scope ─────────────────────────────────────────────────── */}
      <Limitation
        index="05"
        kicker={tr("Scope", "Область применения")}
        title={tr(
          "This is scenario simulation, not forecasting",
          "Это симуляция сценариев, а не прогнозирование",
        )}
        claim={tr(
          "The site simulates a shock you specify. It does not predict that any shock will occur, when it would occur, or with what probability.",
          "Сайт симулирует шок, который задаёте вы. Он не предсказывает, что какой-либо шок произойдёт, когда он произойдёт и с какой вероятностью.",
        )}
        evidenceLabel={tr("The boundary", "Где проходит граница")}
        fixLabel={tr("What would change it", "Что это изменило бы")}
        fix={tr(
          "An event-arrival model: hazard rates over shock types, estimated from data this project does not have and has not tried to assemble. That is a different project, and no number on this site should be read as one of its results.",
          "Модель появления событий: интенсивности по типам шоков, оценённые на данных, которых у проекта нет и которые он не пытался собрать. Это другой проект, и ни одно число на сайте не следует читать как его результат.",
        )}
      >
        <div className="space-y-3">
          <Finding
            value="→"
            tone="cyan"
            text={tr(
              "Every run is conditional on inputs you supply: which node is shocked, how hard, when it starts, how long it lasts, and how it decays. Change any of them and every output changes with it.",
              "Каждый прогон обусловлен вашими вводными: какой узел получает шок, насколько сильный, когда он начинается, сколько длится и как затухает. Измените любую из них — изменится каждый выход.",
            )}
          />
          <Finding
            value="0"
            tone="bad"
            text={tr(
              "components of this system estimate how often shocks arrive. The engine answers what-if, and only what-if.",
              "компонентов этой системы оценивают, как часто приходят шоки. Движок отвечает на «что если» — и только на него.",
            )}
          />
        </div>
      </Limitation>

      {/* ── 06 · project-defined metrics ───────────────────────────────── */}
      <Limitation
        index="06"
        kicker={tr("Metrics", "Метрики")}
        title={tr(
          "The project's own metrics are not externally validated",
          "Собственные метрики проекта не проверены против внешнего стандарта",
        )}
        claim={tr(
          "CSI and ECV are definitions this project wrote. Neither has been scored against an external standard, so a CSI value has no meaning outside this engine.",
          "CSI и ECV — определения, написанные этим проектом. Ни одна из метрик не оценивалась против внешнего стандарта, поэтому значение CSI не имеет смысла за пределами этого движка.",
        )}
        evidenceLabel={tr("Status", "Статус")}
        fixLabel={FIX}
        fix={tr(
          "Score them against an independently maintained index, with the comparison and the acceptance criteria written down before the run — the same procedure used for the rising-shape fix in the bug list below. Until that exists, read CSI and ECV as engine-internal: comparable between runs of this engine and to nothing else.",
          "Сравнить их с независимо поддерживаемым индексом, записав сравнение и критерии приёмки до прогона — та же процедура, что применена к нарастающей форме шока в списке багов ниже. Пока этого нет, читайте CSI и ECV как внутренние для движка: они сопоставимы между прогонами этого движка и больше ни с чем.",
        )}
      >
        <div className="space-y-3">
          <Finding
            value="CSI"
            tone="violet"
            text={tr(
              "Cascade Severity Index — defined by this project, computed by this engine, deterministic, and unanchored to any external scale.",
              "Индекс серьёзности каскада — определён этим проектом, вычисляется этим движком, детерминирован и не привязан ни к какой внешней шкале.",
            )}
          />
          <Finding
            value="ECV"
            tone="violet"
            text={tr(
              "Economic Contagion Velocity — same status. Internal consistency is a property of the code, not evidence about the world.",
              "Скорость экономического заражения — тот же статус. Внутренняя согласованность — свойство кода, а не свидетельство о мире.",
            )}
          />
          <Finding
            value={tr("none", "нет")}
            tone="bad"
            text={tr(
              "external standards either metric has been validated against.",
              "внешних стандартов, против которых проверялась хотя бы одна из метрик.",
            )}
          />
        </div>
      </Limitation>

      {/* ── 07 · benchmark composition ─────────────────────────────────── */}
      <Limitation
        index="07"
        kicker={tr("Benchmark", "Бенчмарк")}
        title={tr(
          "Benchmark composition is skewed toward well-documented events",
          "Состав бенчмарка смещён в сторону хорошо задокументированных событий",
        )}
        claim={tr(
          "The 27 events are the events documented well enough to score. Well-covered crises are over-represented, and that is a selection this project made and could not undo — three independent routes to grow the benchmark were tried, and all three closed.",
          "27 событий — это те события, что задокументированы достаточно хорошо, чтобы их можно было оценить. Хорошо освещённые кризисы представлены избыточно; это отбор, который проект совершил и не смог отменить — три независимых маршрута расширения бенчмарка были испробованы, и все три закрылись.",
        )}
        evidenceLabel={EVIDENCE}
        fixLabel={FIX}
        fix={tr(
          "A class of sources that yields scoreable events without lowering the primary-source bar. Lowering that bar would raise N and lower the quality of every number on this page — the trade this project declined to make.",
          "Класс источников, дающий оцениваемые события без снижения планки первичных источников. Снижение этой планки подняло бы N и опустило качество каждого числа на этой странице — сделка, от которой проект отказался.",
        )}
      >
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
          <Stat value="27" tone="neutral" small
                label={tr("events, 1999–2023, all primary-sourced", "событий, 1999–2023, все с первичными источниками")} />
          <Stat value="3" tone="gold" small
                label={tr("independent routes to grow the benchmark tried", "независимых маршрута расширения бенчмарка испробовано")} />
          <Stat value="3" tone="bad" small
                label={tr("of those routes closed", "из этих маршрутов закрылись")} />
        </div>
        <p className="text-[12px] text-text-muted leading-relaxed">
          {tr(
            "This limitation compounds every one above it: N is the term in the denominator of the power calculation in (01), the leave-one-out instability in (02), and the per-axis sample sizes in (04).",
            "Это ограничение усиливает все предыдущие: N — член в знаменателе расчёта мощности в (01), нестабильности leave-one-out в (02) и размеров выборок по осям в (04).",
          )}
        </p>
      </Limitation>

      {/* ── why this page exists ───────────────────────────────────────── */}
      <section className="panel p-5 sm:p-8 space-y-5">
        <header className="space-y-2.5">
          <div className="flex items-center gap-2.5">
            <span className="glow-dot h-1.5 w-1.5 bg-accent-cyan text-accent-cyan inline-block" aria-hidden="true" />
            <span className="text-[11px] uppercase tracking-[0.28em] text-text-muted">
              {tr("Closing", "В заключение")}
            </span>
          </div>
          <h2 className="text-xl sm:text-3xl font-bold text-text-primary tracking-tight leading-tight">
            {tr("Why this page exists", "Зачем эта страница")}
          </h2>
        </header>

        <div className="space-y-3 max-w-3xl">
          <p className="text-[14px] sm:text-[16px] text-text-secondary leading-relaxed">
            {tr(
              "A model nobody has attacked is not a validated model. It is an untested claim with a confidence interval printed next to it. The bounds above exist because this project spent its time trying to break its own engine rather than trying to make it look finished — and the attacks landed.",
              "Модель, которую никто не атаковал, — не проверенная модель. Это непроверенное утверждение с напечатанным рядом доверительным интервалом. Границы выше существуют потому, что проект тратил время на попытки сломать собственный движок, а не на попытки придать ему законченный вид — и атаки достигли цели.",
            )}
          </p>
          <p className="text-[13px] sm:text-[15px] text-text-secondary leading-relaxed">
            {tr(
              "Four bugs were found in the engine by the people who wrote it. Two destroyed results that had already been published. All four are fixed, and the numbers they moved are printed here rather than quietly corrected.",
              "Четыре бага в движке нашли те, кто его написал. Два уничтожили уже опубликованные результаты. Все четыре исправлены, и числа, которые они сдвинули, напечатаны здесь, а не исправлены молча.",
            )}
          </p>
        </div>

        <ol className="space-y-2.5">
          <Bug
            n={1}
            tone="bad"
            title={tr(
              "Ranking gave different ranks to identical values",
              "Ранжирование давало разные ранги одинаковым значениям",
            )}
            body={tr(
              "Twelve of fifteen peak-timing predictions were exactly 0.0, and a double-argsort ranked those ties by array order.",
              "Двенадцать из пятнадцати предсказаний тайминга пика были ровно 0,0, а двойной argsort ранжировал эти совпадения по порядку в массиве.",
            )}
            effect={tr(
              "peak timing 0.61 → 0.07 — a published result destroyed",
              "тайминг пика 0,61 → 0,07 — опубликованный результат уничтожен",
            )}
          />
          <Bug
            n={2}
            tone="good"
            title={tr(
              "The pre-registered fix for why it sat at chance",
              "Пред-зарегистрированное исправление того, почему он был на уровне случайности",
            )}
            body={tr(
              "Every forcing shape peaked at week zero, so slow-building events could not be represented at all. A rising shape was added, with the acceptance criteria written down before the run.",
              "Все формы шока имели максимум в нулевой неделе, поэтому медленно нарастающие события не могли быть представлены вообще. Добавлена нарастающая форма, а критерии приёмки записаны до прогона.",
            )}
            effect={tr(
              "peak timing 0.07 → 0.69, at a cost of +0.0001 MAE",
              "тайминг пика 0,07 → 0,69 ценой +0,0001 MAE",
            )}
          />
          <Bug
            n={3}
            tone="bad"
            title={tr(
              "A flag that turned nothing off",
              "Флаг, который ничего не выключал",
            )}
            body={tr(
              "seis_enabled=False neutralised the SEIRS modifiers at init, but update_seis ran unconditionally and re-armed them — so the state-machine-off ablation silently duplicated the full-engine row.",
              "seis_enabled=False обнулял модификаторы SEIRS при инициализации, но update_seis выполнялся безусловно и возвращал их — поэтому строка абляции «машина состояний выключена» молча дублировала строку полного движка.",
            )}
            effect={tr(
              "true ablation 0.0242 → 0.0166",
              "истинная абляция 0,0242 → 0,0166",
            )}
          />
          <Bug
            n={4}
            tone="bad"
            title={tr(
              "Recovery ordering was reading a hand-typed field",
              "Порядок восстановления считывал вручную вписанное поле",
            )}
            body={tr(
              "Recovery was scored against each event's own hand-set horizon, and when a node never recovered in-window the harness returned the window length — so 7 of 11 predictions were lower bounds equal to that field. Ranking by the field alone scored 0.8717 with no engine at all. Every event now runs on one fixed 260-week window; censored cases 7 → 0.",
              "Восстановление оценивалось против собственного, вручную заданного горизонта каждого события, и если узел не восстанавливался в окне, харнесс возвращал длину окна — поэтому 7 из 11 «прогнозов» были нижними границами, равными этому полю. Ранжирование по одному этому полю давало 0,8717 вообще без движка. Теперь каждое событие прогоняется на одном фиксированном окне в 260 недель; цензурированных случаев 7 → 0.",
            )}
            effect={tr(
              "withdrawn 0.8828 → corrected 0.7107",
              "отозвано 0,8828 → исправлено 0,7107",
            )}
          />
        </ol>

        <div className="border-t border-border-subtle pt-4 space-y-3">
          <p className="text-[13px] text-text-secondary leading-relaxed max-w-3xl">
            {tr(
              "149 automated tests pass. Runs are deterministic — seed 0, stochastic_sigma 0 — and results are frozen by golden-snapshot tests, so no number on this site can drift without the suite failing first.",
              "149 автоматических тестов проходят. Прогоны детерминированы — seed 0, stochastic_sigma 0 — а результаты заморожены снапшот-тестами: ни одно число на сайте не может сдвинуться, не уронив сначала тесты.",
            )}
          </p>
          <p className="text-[14px] sm:text-[15px] text-text-primary font-semibold leading-relaxed max-w-3xl">
            {tr(
              "None of this makes the model better than its measurements. It makes the measurements worth reading.",
              "Ничто из этого не делает модель лучше её измерений. Оно делает эти измерения достойными прочтения.",
            )}
          </p>
        </div>
      </section>
    </main>
  );
}

/* ── building blocks ──────────────────────────────────────────────────── */

function Limitation({
  index,
  kicker,
  title,
  claim,
  evidenceLabel,
  fixLabel,
  fix,
  children,
}: {
  index: string;
  kicker: string;
  title: string;
  claim: string;
  evidenceLabel: string;
  fixLabel: string;
  fix: string;
  children: React.ReactNode;
}) {
  return (
    <section className="panel p-5 sm:p-7 space-y-4">
      <header className="space-y-2.5">
        <div className="flex items-baseline gap-3">
          <span className="num text-[13px] font-bold text-accent-violet">{index}</span>
          <span className="text-[11px] uppercase tracking-[0.24em] text-text-muted">{kicker}</span>
        </div>
        <h2 className="text-lg sm:text-2xl font-semibold text-text-primary leading-snug">{title}</h2>
        <p className="text-[13px] sm:text-[15px] text-text-secondary leading-relaxed max-w-3xl">{claim}</p>
      </header>

      <div className="space-y-3">
        <div className="text-[11px] uppercase tracking-[0.24em] text-accent-cyan font-bold">
          {evidenceLabel}
        </div>
        {children}
      </div>

      <div className="border-t border-border-subtle pt-3.5 space-y-1.5">
        <div className="text-[11px] uppercase tracking-[0.24em] text-accent-gold font-bold">
          {fixLabel}
        </div>
        <p className="text-[13px] text-text-secondary leading-relaxed max-w-3xl">{fix}</p>
      </div>
    </section>
  );
}

function Stat({
  value,
  label,
  tone = "neutral",
  small = false,
}: {
  value: string;
  label: string;
  tone?: Tone;
  small?: boolean;
}) {
  return (
    <div className="rounded-lg border border-border-subtle bg-bg-base/40 p-3 sm:p-3.5">
      <div
        className={`num font-extrabold leading-none ${TONE_TEXT[tone]} ${
          small ? "text-xl sm:text-2xl" : "text-2xl sm:text-[32px]"
        }`}
      >
        {value}
      </div>
      <div className="text-[12px] text-text-muted leading-snug mt-2">{label}</div>
    </div>
  );
}

/**
 * A measured fact: the number first, at size, then the sentence it supports.
 * The optional pip row encodes "k of n" so the ratio is legible before the
 * text is read — and it is never the only carrier of the value.
 */
function Finding({
  value,
  text,
  tone,
  total,
  filled,
}: {
  value: string;
  text: string;
  tone: Tone;
  total?: number;
  filled?: number;
}) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-start gap-1.5 sm:gap-4 rounded-lg border border-border-subtle bg-bg-base/40 p-3 sm:p-3.5">
      <div className="sm:w-[120px] sm:shrink-0 space-y-1.5">
        <div className={`num text-xl sm:text-2xl font-extrabold leading-none ${TONE_TEXT[tone]}`}>
          {value}
        </div>
        {typeof total === "number" && typeof filled === "number" && (
          <div className="flex gap-1" aria-hidden="true">
            {Array.from({ length: total }, (_, i) => (
              <span
                key={i}
                className={`h-1.5 w-4 rounded-full ${i < filled ? TONE_FILL[tone] : "bg-border-strong"}`}
              />
            ))}
          </div>
        )}
      </div>
      <p className="text-[13px] text-text-secondary leading-relaxed min-w-0">{text}</p>
    </div>
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
                         bg-accent-violet/15 text-accent-violet border border-accent-violet/30 num">
          {n}
        </span>
        <div className="min-w-0 space-y-1.5">
          <div className="text-[14px] font-semibold text-text-primary leading-snug">{title}</div>
          <p className="text-[13px] text-text-secondary leading-relaxed">{body}</p>
          <div className={`num text-[13px] font-semibold ${tone === "good" ? "text-accent-cyan" : "text-sev-5"}`}>
            {effect}
          </div>
        </div>
      </div>
    </li>
  );
}
