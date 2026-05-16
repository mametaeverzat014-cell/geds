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
        <span className="text-xs text-text-muted num">
          {running ? "running…" : "ready"}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-1.5">
        {PRESETS.map((p) => (
          <button
            key={p.id}
            onClick={() => setSelected(p.id)}
            className={clsx(
              "text-left px-3 py-2 rounded text-xs border transition",
              selected === p.id
                ? "bg-accent-violet/15 border-accent-violet/40 text-text-primary"
                : "bg-bg-base/40 border-border-subtle text-text-secondary hover:border-border-strong",
              p.primary && selected !== p.id && "border-l-2 border-l-accent-cyan/70",
            )}
          >
            {p.label}
          </button>
        ))}
      </div>

      <button
        onClick={run}
        disabled={running}
        className={clsx(
          "w-full mt-2 px-3 py-2.5 rounded text-sm font-semibold transition",
          running
            ? "bg-bg-base/40 text-text-muted cursor-not-allowed"
            : "bg-accent-cyan text-bg-base hover:bg-accent-cyan/85",
        )}
      >
        {running ? "Simulating…" : "Run simulation"}
      </button>
    </div>
  );
}
