"use client";

import { useMemo } from "react";

import { useSimStore } from "@/lib/store";
import { useUI } from "@/lib/ui-context";

/**
 * The four-beat spine of the whole project, rendered as a live progress strip:
 *
 *     SHOCK → PROPAGATION → CASCADE → RECOVERY
 *
 * It is not decoration. Which beat is lit is derived from the actual frames, so
 * during a run the strip tracks the simulation and a viewer learns the vocabulary
 * by watching it advance rather than by reading a legend.
 *
 * Beat boundaries are defined from the run itself, not from fixed week numbers:
 *   SHOCK        week 0 — the origin is forced
 *   PROPAGATION  the first non-origin node has crossed the reach threshold
 *   CASCADE      the affected count is still climbing
 *   RECOVERY     past the week of peak severity (max CSI)
 *
 * Before any run it renders the four labels dimmed, which doubles as the
 * explanation of what the page is about.
 */

const REACHED = 0.01;

type BeatId = "shock" | "propagation" | "cascade" | "recovery";

const BEATS: { id: BeatId; en: string; ru: string }[] = [
  { id: "shock", en: "Shock", ru: "Удар" },
  { id: "propagation", en: "Propagation", ru: "Распространение" },
  { id: "cascade", en: "Cascade", ru: "Каскад" },
  { id: "recovery", en: "Recovery", ru: "Восстановление" },
];

export default function CascadeSpine() {
  const frames = useSimStore((s) => s.frames);
  const currentWeek = useSimStore((s) => s.currentWeek);
  const { lang } = useUI();
  const ru = lang === "ru";

  const state = useMemo(() => {
    if (!frames.length) return null;

    const origins = new Set(
      (frames[0]?.nodes ?? [])
        .filter((n) => n.output_loss >= REACHED)
        .map((n) => n.id),
    );

    // first week a node OUTSIDE the origin set is reached
    let firstSpreadWeek: number | null = null;
    // week of maximum network severity
    let peakWeek = 0;
    // cumulative affected per week, to tell "still growing" from "settling"
    const seen = new Set<string>(origins);
    const cumulative: number[] = [];

    for (const f of frames) {
      for (const n of f.nodes) {
        if (n.output_loss >= REACHED && !seen.has(n.id)) {
          seen.add(n.id);
          if (firstSpreadWeek === null) firstSpreadWeek = f.week;
        }
      }
      cumulative[f.week] = seen.size;
      if (f.csi > frames[peakWeek].csi) peakWeek = f.week;
    }

    const w = Math.min(currentWeek, frames.length - 1);
    const grew = w > 0 && (cumulative[w] ?? 0) > (cumulative[w - 1] ?? 0);

    let active: BeatId = "shock";
    if (w > peakWeek) active = "recovery";
    else if (firstSpreadWeek !== null && w > firstSpreadWeek && !grew) active = "cascade";
    else if (firstSpreadWeek !== null && w >= firstSpreadWeek) active = "propagation";

    return {
      active,
      week: w,
      peakWeek,
      firstSpreadWeek,
      affected: cumulative[w] ?? origins.size,
      total: frames[0]?.nodes.length ?? 0,
    };
  }, [frames, currentWeek]);

  const reached = (id: BeatId): boolean => {
    if (!state) return false;
    const order: BeatId[] = ["shock", "propagation", "cascade", "recovery"];
    return order.indexOf(id) <= order.indexOf(state.active);
  };

  return (
    <div className="space-y-2">
      <ol className="flex items-center gap-1 sm:gap-2 overflow-x-auto no-scrollbar -mx-1 px-1">
        {BEATS.map((b, i) => {
          const on = reached(b.id);
          const isActive = state?.active === b.id;
          return (
            <li key={b.id} className="flex items-center gap-1 sm:gap-2 shrink-0">
              {i > 0 && (
                <span
                  aria-hidden="true"
                  className={`text-[13px] transition-colors duration-500 ${
                    on ? "text-accent-cyan" : "text-text-muted/40"
                  }`}
                >
                  →
                </span>
              )}
              <span
                className={[
                  "rounded-md border px-2.5 py-1 text-[11px] sm:text-[12px] uppercase tracking-wider",
                  "transition-all duration-500",
                  isActive
                    ? "border-accent-cyan/60 bg-accent-cyan/10 text-accent-cyan"
                    : on
                      ? "border-border-strong text-text-secondary"
                      : "border-border-subtle text-text-muted/60",
                ].join(" ")}
              >
                {ru ? b.ru : b.en}
              </span>
            </li>
          );
        })}
      </ol>

      <p className="text-[12px] text-text-muted leading-snug">
        {state ? (
          ru ? (
            <>
              Неделя <span className="num text-text-secondary">{state.week}</span> · затронуто{" "}
              <span className="num text-text-secondary">{state.affected}</span> из{" "}
              <span className="num">{state.total}</span> узлов · пик тяжести на неделе{" "}
              <span className="num text-text-secondary">{state.peakWeek}</span>
            </>
          ) : (
            <>
              Week <span className="num text-text-secondary">{state.week}</span> ·{" "}
              <span className="num text-text-secondary">{state.affected}</span> of{" "}
              <span className="num">{state.total}</span> nodes affected · peak severity at week{" "}
              <span className="num text-text-secondary">{state.peakWeek}</span>
            </>
          )
        ) : ru ? (
          "Один узел мировой экономики выходит из строя — что происходит дальше и когда."
        ) : (
          "One node of the global economy breaks — what happens next, and when."
        )}
      </p>
    </div>
  );
}
