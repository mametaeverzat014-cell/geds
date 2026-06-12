"use client";

import clsx from "clsx";
import { useSimStore } from "@/lib/store";
import { api } from "@/lib/api";
import type { StreamMessage } from "@/lib/types";

const PRESETS = [
  { id: "taiwan-semi-75", label: "Taiwan Semi 75%", primary: true },
  { id: "taiwan-semi-80", label: "Taiwan Semi 80%" },
  { id: "taiwan-strait",  label: "Taiwan Semi + Strait" },
  { id: "historical-suez-2021", label: "Suez 2021 (replay)" },
  { id: "historical-covid-semi", label: "COVID Semi (replay)" },
  { id: "hypothetical-hormuz", label: "Hormuz Closure" },
];

export default function ScenarioControls() {
  const selected = useSimStore((s) => s.selectedScenarioId);
  const setSelected = useSimStore((s) => s.setSelectedScenario);
  const beginRun = useSimStore((s) => s.beginRun);
  const pushFrame = useSimStore((s) => s.pushFrame);
  const completeRun = useSimStore((s) => s.completeRun);
  const failRun = useSimStore((s) => s.failRun);
  const running = useSimStore((s) => s.running);

  const run = () => {
    beginRun();
    const ws = new WebSocket(api.wsStreamUrl());
    ws.onopen = () => {
      ws.send(JSON.stringify({ scenario_id: selected }));
    };
    ws.onmessage = (ev) => {
      const msg: StreamMessage = JSON.parse(ev.data);
      if (msg.event === "frame") pushFrame(msg.frame);
      else if (msg.event === "complete") completeRun(msg.summary);
      else if (msg.event === "error") failRun(msg.message);
    };
    ws.onerror = () => failRun("WebSocket error");
    ws.onclose = (ev) => {
      if (!ev.wasClean && !useSimStore.getState().summary) {
        failRun("Connection closed before completion");
      }
    };
  };

  return (
    <div className="panel p-4 space-y-3">
      <div className="flex items-baseline justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
          Scenario
        </h2>
        <span
          className={clsx(
            "text-xs num inline-flex items-center gap-1.5",
            running ? "text-accent-gold" : "text-text-muted",
          )}
        >
          <span
            className={clsx(
              "glow-dot h-1.5 w-1.5",
              running ? "bg-accent-gold text-accent-gold" : "bg-accent-cyan/70 text-accent-cyan",
            )}
          />
          {running ? "running…" : "ready"}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-1.5">
        {PRESETS.map((p) => (
          <button
            key={p.id}
            onClick={() => setSelected(p.id)}
            className={clsx(
              "btn-option px-3 py-2",
              selected === p.id && "is-active",
            )}
          >
            <span className="flex items-center justify-between gap-2">
              <span className="truncate">{p.label}</span>
              {p.primary && (
                <span className="shrink-0 text-[9px] uppercase tracking-wider px-1.5 py-px rounded-full border border-accent-cyan/40 text-accent-cyan/90 bg-accent-cyan/10">
                  flagship
                </span>
              )}
            </span>
          </button>
        ))}
      </div>

      <button onClick={run} disabled={running} className="btn-primary w-full mt-2 px-3 py-2.5">
        {running ? (
          <span className="inline-flex items-center justify-center gap-2.5">
            <span className="inline-flex items-end gap-[3px] text-text-secondary" aria-hidden="true">
              <span className="eq-bar" style={{ animationDelay: "0ms" }} />
              <span className="eq-bar" style={{ animationDelay: "150ms" }} />
              <span className="eq-bar" style={{ animationDelay: "300ms" }} />
              <span className="eq-bar" style={{ animationDelay: "450ms" }} />
            </span>
            Simulating…
          </span>
        ) : (
          <span className="inline-flex items-center justify-center gap-2">
            <svg width="11" height="12" viewBox="0 0 11 12" fill="currentColor" aria-hidden="true">
              <path d="M0.5 1.13c0-.78.85-1.27 1.53-.88l8.4 4.87c.67.4.67 1.37 0 1.76l-8.4 4.87c-.68.4-1.53-.1-1.53-.88V1.13Z" />
            </svg>
            Run simulation
          </span>
        )}
      </button>
    </div>
  );
}
