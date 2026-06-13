"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useSimStore } from "@/lib/store";
import type { StreamMessage } from "@/lib/types";

interface ShockRow {
  node_id: string;
  magnitude: number;
  start_week: number;
  duration_weeks: number;
  decay: "step" | "linear" | "exp";
}

const PRESET_NODES = [
  { id: "TWN:semiconductors",  label: "Taiwan — Semiconductors" },
  { id: "TWN:electronics",     label: "Taiwan — Electronics" },
  { id: "CHN:electronics",     label: "China — Electronics" },
  { id: "KOR:semiconductors",  label: "South Korea — Semiconductors" },
  { id: "DEU:automotive",      label: "Germany — Automotive" },
  { id: "USA:semiconductors",  label: "USA — Semiconductors" },
  { id: "USA:electronics",     label: "USA — Electronics" },
  { id: "JPN:automotive",      label: "Japan — Automotive" },
  { id: "JPN:electronics",     label: "Japan — Electronics" },
  { id: "CP:TaiwanStrait",     label: "Chokepoint — Taiwan Strait" },
  { id: "CP:Malacca",          label: "Chokepoint — Strait of Malacca" },
  { id: "CP:Suez",             label: "Chokepoint — Suez Canal" },
  { id: "CP:Hormuz",           label: "Chokepoint — Strait of Hormuz" },
];

const EMPTY_SHOCK: ShockRow = {
  node_id: "TWN:semiconductors",
  magnitude: 0.75,
  start_week: 0,
  duration_weeks: 12,
  decay: "step",
};

export default function ScenarioBuilder() {
  const [open, setOpen] = useState(false);
  const [scenarioName, setScenarioName] = useState("Custom scenario");
  const [horizonWeeks, setHorizonWeeks] = useState(52);
  const [shocks, setShocks] = useState<ShockRow[]>([{ ...EMPTY_SHOCK }]);

  const beginRun    = useSimStore((s) => s.beginRun);
  const pushFrame   = useSimStore((s) => s.pushFrame);
  const completeRun = useSimStore((s) => s.completeRun);
  const failRun     = useSimStore((s) => s.failRun);
  const running     = useSimStore((s) => s.running);

  function addShock() {
    setShocks((prev) => [...prev, { ...EMPTY_SHOCK }]);
  }

  function removeShock(idx: number) {
    setShocks((prev) => prev.filter((_, i) => i !== idx));
  }

  function updateShock<K extends keyof ShockRow>(idx: number, key: K, value: ShockRow[K]) {
    setShocks((prev) => prev.map((s, i) => (i === idx ? { ...s, [key]: value } : s)));
  }

  function run() {
    beginRun();
    const ws = new WebSocket(api.wsStreamUrl());
    ws.onopen = () => {
      ws.send(
        JSON.stringify({
          custom: {
            name: scenarioName,
            horizon_weeks: horizonWeeks,
            shocks: shocks.map((s) => ({
              target_node_id: s.node_id,
              magnitude: s.magnitude,
              start_week: s.start_week,
              duration_weeks: s.duration_weeks,
              decay_curve: s.decay,
            })),
          },
        }),
      );
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
  }

  return (
    <div className="panel overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-semibold text-text-secondary uppercase tracking-wider hover:text-text-primary transition"
      >
        <span>Custom scenario</span>
        <span className="text-text-muted">{open ? "▴" : "▾"}</span>
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-4 border-t border-border-subtle pt-3">
          {/* name + horizon */}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1">
                Name
              </label>
              <input
                value={scenarioName}
                onChange={(e) => setScenarioName(e.target.value)}
                className="w-full bg-bg-base/60 border border-border-subtle rounded px-2 py-1 text-xs text-text-primary focus:outline-none focus:border-accent-cyan"
              />
            </div>
            <div>
              <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1">
                Horizon (weeks)
              </label>
              <input
                type="number"
                min={4}
                max={520}
                value={horizonWeeks}
                onChange={(e) => setHorizonWeeks(Number(e.target.value))}
                className="w-full bg-bg-base/60 border border-border-subtle rounded px-2 py-1 text-xs text-text-primary focus:outline-none focus:border-accent-cyan num"
              />
            </div>
          </div>

          {/* shock rows */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-text-muted uppercase tracking-wider">Shocks</span>
              <button
                onClick={addShock}
                className="text-xs text-accent-cyan hover:text-accent-cyan/70 transition"
              >
                + Add shock
              </button>
            </div>

            {shocks.map((shock, idx) => (
              <div key={idx} className="bg-bg-base/40 border border-border-subtle rounded p-2 space-y-2">
                {/* node selector */}
                <select
                  value={shock.node_id}
                  onChange={(e) => updateShock(idx, "node_id", e.target.value)}
                  className="w-full bg-bg-elevated border border-border-subtle rounded px-2 py-1 text-xs text-text-primary focus:outline-none focus:border-accent-cyan"
                >
                  {PRESET_NODES.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.label}
                    </option>
                  ))}
                </select>

                <div className="grid grid-cols-4 gap-2">
                  {/* magnitude */}
                  <div>
                    <label className="block text-[9px] text-text-muted uppercase tracking-wider mb-0.5">
                      Mag. {(shock.magnitude * 100).toFixed(0)}%
                    </label>
                    <input
                      type="range"
                      min={0.05}
                      max={1}
                      step={0.05}
                      value={shock.magnitude}
                      onChange={(e) => updateShock(idx, "magnitude", Number(e.target.value))}
                      className="w-full accent-sev-5"
                    />
                  </div>

                  {/* start */}
                  <div>
                    <label className="block text-[9px] text-text-muted uppercase tracking-wider mb-0.5">
                      Start w
                    </label>
                    <input
                      type="number"
                      min={0}
                      max={horizonWeeks - 1}
                      value={shock.start_week}
                      onChange={(e) => updateShock(idx, "start_week", Number(e.target.value))}
                      className="w-full bg-bg-base border border-border-subtle rounded px-1.5 py-0.5 text-xs num text-text-primary focus:outline-none"
                    />
                  </div>

                  {/* duration */}
                  <div>
                    <label className="block text-[9px] text-text-muted uppercase tracking-wider mb-0.5">
                      Dur. w
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={horizonWeeks}
                      value={shock.duration_weeks}
                      onChange={(e) => updateShock(idx, "duration_weeks", Number(e.target.value))}
                      className="w-full bg-bg-base border border-border-subtle rounded px-1.5 py-0.5 text-xs num text-text-primary focus:outline-none"
                    />
                  </div>

                  {/* decay */}
                  <div>
                    <label className="block text-[9px] text-text-muted uppercase tracking-wider mb-0.5">
                      Decay
                    </label>
                    <select
                      value={shock.decay}
                      onChange={(e) =>
                        updateShock(idx, "decay", e.target.value as "step" | "linear" | "exp")
                      }
                      className="w-full bg-bg-base border border-border-subtle rounded px-1 py-0.5 text-xs text-text-primary focus:outline-none"
                    >
                      <option value="step">Step</option>
                      <option value="linear">Linear</option>
                      <option value="exp">Exp</option>
                    </select>
                  </div>
                </div>

                {shocks.length > 1 && (
                  <button
                    onClick={() => removeShock(idx)}
                    className="text-[10px] text-text-muted hover:text-sev-5 transition"
                  >
                    Remove
                  </button>
                )}
              </div>
            ))}
          </div>

          <button
            onClick={run}
            disabled={running || shocks.length === 0}
            className="btn-primary w-full px-3 py-2"
          >
            {running ? "Simulating…" : "Run custom scenario"}
          </button>
        </div>
      )}
    </div>
  );
}
