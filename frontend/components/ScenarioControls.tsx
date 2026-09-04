"use client";

import clsx from "clsx";
import { useEffect, useRef } from "react";
import { useSimStore, type GraphVersion } from "@/lib/store";
import { api } from "@/lib/api";
import type { SimulationResult, StreamMessage } from "@/lib/types";

// `v2only` presets shock a chokepoint node, which the ICIO v3 graph has no
// equivalent for — they're disabled when the 81-economy graph is selected.
const PRESETS = [
  { id: "taiwan-semi-75", label: "Taiwan Semi 75%", primary: true },
  { id: "taiwan-semi-80", label: "Taiwan Semi 80%" },
  { id: "taiwan-strait",  label: "Taiwan Semi + Strait" },
  { id: "historical-suez-2021", label: "Suez 2021 (replay)", v2only: true },
  { id: "historical-covid-semi", label: "COVID Semi (replay)" },
  { id: "hypothetical-hormuz", label: "Hormuz Closure", v2only: true },
];

/** Wall-clock budget for a snapshot replay, so any horizon reads at one speed. */
const REPLAY_MS = 2200;

const GRAPHS: { id: GraphVersion; label: string; nodes: string }[] = [
  { id: "v2", label: "12-country", nodes: "41 nodes · calibrated" },
  { id: "v3", label: "81-economy", nodes: "405 nodes · OECD ICIO" },
];

export default function ScenarioControls() {
  const selected = useSimStore((s) => s.selectedScenarioId);
  const setSelected = useSimStore((s) => s.setSelectedScenario);
  const graphVersion = useSimStore((s) => s.graphVersion);
  const setGraphVersion = useSimStore((s) => s.setGraphVersion);
  const graph = useSimStore((s) => s.graph);
  const setGraph = useSimStore((s) => s.setGraph);
  const backendStatus = useSimStore((s) => s.backendStatus);
  const beginRun = useSimStore((s) => s.beginRun);
  const pushFrame = useSimStore((s) => s.pushFrame);
  const completeRun = useSimStore((s) => s.completeRun);
  const failRun = useSimStore((s) => s.failRun);
  const running = useSimStore((s) => s.running);

  // Load the snapshot for the active graph so the map + node list reflect it.
  // Re-runs whenever graphVersion changes OR when the backend comes back online
  // (backend may have been sleeping when the page first loaded).
  //
  // Deliberately NOT gated on backendStatus any more: `api.graph` falls back to
  // the shipped snapshot, so an offline first load still gets a real graph and
  // the page can draw itself while the server wakes.
  useEffect(() => {
    api.graph(graphVersion).then(setGraph).catch(() => {});
  }, [graphVersion, backendStatus, setGraph]);

  const pickGraph = (v: GraphVersion) => {
    if (v === graphVersion) return;
    setGraphVersion(v);
    // a chokepoint-only scenario can't run on v3 → fall back to the flagship
    if (v === "v3" && PRESETS.find((p) => p.id === selected)?.v2only) {
      setSelected("taiwan-semi-75");
    }
  };

  // Cancels an in-flight snapshot replay. Held in a ref so a second run, or an
  // unmount, can stop the first one mid-cascade instead of interleaving frames.
  const replayCancel = useRef<(() => void) | null>(null);
  useEffect(() => () => replayCancel.current?.(), []);

  /**
   * Play a completed SimulationResult out frame by frame.
   *
   * The websocket streams frames as the engine produces them, and watching the
   * cascade arrive is the whole point of the map. Dumping a finished run into
   * the store in one go would show the same data and destroy the only thing that
   * makes it legible. So the fallback keeps the cadence, paced to a fixed
   * wall-clock budget so a 52-week run and a 260-week one read at the same speed.
   */
  const replay = (result: SimulationResult) => {
    replayCancel.current?.();
    beginRun();
    const total = result.frames.length;
    if (total === 0) { failRun("Snapshot contained no frames"); return; }
    const step = Math.min(40, Math.max(8, Math.round(REPLAY_MS / total)));
    const batch = Math.max(1, Math.ceil(total / (REPLAY_MS / step)));

    let i = 0;
    const id = setInterval(() => {
      for (let k = 0; k < batch && i < total; k++, i++) pushFrame(result.frames[i]);
      if (i >= total) {
        clearInterval(id);
        replayCancel.current = null;
        completeRun(result.summary);
      }
    }, step);
    replayCancel.current = () => { clearInterval(id); replayCancel.current = null; };
  };

  const run = () => {
    replayCancel.current?.();
    beginRun();

    // One flag for both failure paths: a socket that never opens fires onerror
    // AND onclose, and a socket that dies mid-stream fires onclose after frames
    // have already landed. Without this the fallback could start twice.
    let settled = false;
    const fallback = (reason: string) => {
      if (settled) return;
      settled = true;
      // Only the flagship on the v2 graph is baked, and POST /simulate has no
      // graph_version parameter — it is v2 either way. Replaying a v2 cascade
      // onto the 405-node ICIO graph would paint the wrong node ids, so v3 fails
      // loudly instead of showing something that merely looks right.
      if (graphVersion !== "v2") { failRun(reason); return; }
      api.simulate({ scenario_id: selected }).then(replay).catch(() => failRun(reason));
    };

    // Already known to be asleep: don't open a socket that will hang for the
    // browser's full connect timeout before failing. Go straight to the snapshot.
    if (useSimStore.getState().backendStatus === "offline") {
      fallback("Backend asleep");
      return;
    }

    const ws = new WebSocket(api.wsStreamUrl());
    ws.onopen = () => {
      ws.send(JSON.stringify({ scenario_id: selected, graph_version: graphVersion }));
    };
    ws.onmessage = (ev) => {
      const msg: StreamMessage = JSON.parse(ev.data);
      if (msg.event === "frame") pushFrame(msg.frame);
      else if (msg.event === "complete") { settled = true; completeRun(msg.summary); }
      else if (msg.event === "error") { settled = true; failRun(msg.message); }
    };
    ws.onerror = () => fallback("WebSocket error");
    ws.onclose = (ev) => {
      if (!ev.wasClean && !useSimStore.getState().summary) {
        fallback("Connection closed before completion");
      }
    };
  };

  // ── run the default scenario once, unprompted, as soon as we can ──
  // Half this page renders nothing until a simulation has completed: the
  // cascade map, the forecast narrative, the transmission chains and the
  // historical analogue all bail out on an empty frame list. Someone opening
  // the page cold — a visitor, or a judge handed the laptop — saw an empty
  // shell and had no way to know a button press was required. Firing the
  // flagship scenario on first load makes the page self-demonstrating.
  //
  // Guarded by a ref rather than state so it can never fire twice: the deps
  // legitimately change several times during startup (backend probe resolves,
  // then the graph arrives), and each of those must not start a second run.
  const autoRanRef = useRef(false);
  useEffect(() => {
    if (autoRanRef.current) return;
    // "checking" is the only state that blocks. "offline" no longer does: the
    // snapshot can drive a full cascade, and a cold visitor waiting 30 s for the
    // first pixel is the exact failure this is here to prevent.
    if (backendStatus === "checking" || !graph || !selected || running) return;
    if (useSimStore.getState().summary) return;   // a run already produced output
    autoRanRef.current = true;
    run();
    // `run` is intentionally omitted: it is re-created every render, and the
    // ref guard already makes this fire exactly once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backendStatus, graph, selected, running]);

  return (
    <div className="panel p-4 space-y-3">
      <div className="flex items-baseline justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
          Scenario
        </h2>
        <span
          className={clsx(
            "text-[13px] num inline-flex items-center gap-1.5",
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

      {/* ── graph selector ── */}
      <div>
        <div className="text-[12px] uppercase tracking-wider text-text-muted mb-1">Graph</div>
        <div className="grid grid-cols-2 gap-1.5">
          {GRAPHS.map((g) => (
            <button
              key={g.id}
              onClick={() => pickGraph(g.id)}
              disabled={running}
              className={clsx(
                "rounded-md border px-2.5 py-1.5 text-left transition-all duration-200 disabled:opacity-50",
                graphVersion === g.id
                  ? "border-accent-violet/55 bg-gradient-to-br from-accent-violet/15 to-accent-cyan/10 text-text-primary shadow-[0_0_14px_-5px_rgba(124,108,251,0.8)]"
                  : "border-border-subtle text-text-muted hover:text-text-secondary hover:border-border-strong",
              )}
            >
              <div className="text-[13px] font-semibold">{g.label}</div>
              <div className="text-[12px] num text-text-muted">{g.nodes}</div>
            </button>
          ))}
        </div>
        {graphVersion === "v3" && (
          <p className="text-[12px] text-text-muted mt-1 leading-snug">
            ICIO structural graph (uncalibrated priors). Cascade <em>reach</em> is far wider;
            magnitudes aren&apos;t tuned to this topology yet.
          </p>
        )}
      </div>

      <div className="grid grid-cols-1 gap-1.5">
        {PRESETS.map((p) => {
          const disabled = graphVersion === "v3" && p.v2only;
          return (
            <button
              key={p.id}
              onClick={() => setSelected(p.id)}
              disabled={disabled}
              title={disabled ? "Chokepoint scenario — 12-country graph only" : undefined}
              className={clsx(
                "btn-option px-3 py-2",
                selected === p.id && !disabled && "is-active",
                disabled && "opacity-40 cursor-not-allowed",
              )}
            >
              <span className="flex items-center justify-between gap-2">
                <span className="truncate">{p.label}</span>
                {p.primary && (
                  <span className="shrink-0 text-[12px] uppercase tracking-wider px-1.5 py-px rounded-full border border-accent-cyan/40 text-accent-cyan/90 bg-accent-cyan/10">
                    flagship
                  </span>
                )}
                {disabled && (
                  <span className="shrink-0 text-[12px] uppercase tracking-wider text-text-muted">
                    v2 only
                  </span>
                )}
              </span>
            </button>
          );
        })}
      </div>

      <button onClick={run} disabled={running || backendStatus === "offline"} className="btn-primary w-full mt-2 px-3 py-2.5">
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
        ) : backendStatus === "offline" ? (
          <span className="inline-flex items-center justify-center gap-2 opacity-60">
            <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" />
            Starting up…
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
