"use client";

import clsx from "clsx";
import { useEffect, useRef } from "react";
import { severityColor } from "@/lib/colors";
import { useSimStore } from "@/lib/store";
import type { OverlayMode } from "@/lib/store";

const OVERLAY_OPTIONS: { value: OverlayMode; label: string }[] = [
  { value: "shock",          label: "Shock" },
  { value: "inflation",      label: "Inflation" },
  { value: "output_loss",    label: "Output loss" },
  { value: "unemployment",   label: "Unemployment" },
];

const SPEED_OPTIONS = [1, 2, 4, 8, 16];

export default function TimelineBar() {
  const frames       = useSimStore((s) => s.frames);
  const currentWeek  = useSimStore((s) => s.currentWeek);
  const setWeek      = useSimStore((s) => s.setCurrentWeek);
  const autoPlay     = useSimStore((s) => s.autoPlay);
  const setAutoPlay  = useSimStore((s) => s.setAutoPlay);
  const speed        = useSimStore((s) => s.playbackSpeed);
  const setSpeed     = useSimStore((s) => s.setPlaybackSpeed);
  const overlayMode  = useSimStore((s) => s.overlayMode);
  const setOverlay   = useSimStore((s) => s.setOverlayMode);
  const running      = useSimStore((s) => s.running);

  // ── auto-play ticker ─────────────────────────────────────
  const rafRef = useRef<number | null>(null);
  const lastRef = useRef<number>(0);

  useEffect(() => {
    if (!autoPlay || frames.length === 0) {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      return;
    }

    const maxWeek = frames[frames.length - 1].week;
    const msPerStep = 1000 / speed;

    function tick(now: number) {
      if (now - lastRef.current >= msPerStep) {
        lastRef.current = now;
        useSimStore.setState((st) => {
          const next = st.currentWeek + 1;
          if (next > maxWeek) {
            return { autoPlay: false };
          }
          return { currentWeek: next };
        });
      }
      rafRef.current = requestAnimationFrame(tick);
    }

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [autoPlay, speed, frames]);

  if (frames.length === 0) {
    return (
      <div className="panel p-4 text-xs text-text-muted">
        Run a scenario to view the propagation timeline.
      </div>
    );
  }

  const maxWeek = frames[frames.length - 1].week;
  const peakCsi = Math.max(...frames.map((f) => f.csi), 0.001);
  const curFrame = frames.find((f) => f.week === currentWeek) ?? frames[currentWeek] ?? frames[0];

  return (
    <div className="panel p-4 space-y-3">
      {/* ── header row ── */}
      <div className="flex items-baseline justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
          Cascade timeline
        </h2>
        <span className="num text-xs text-text-secondary">
          Week {currentWeek} / {maxWeek}
        </span>
      </div>

      {/* ── CSI heat-bar ── */}
      <div className="flex items-end gap-[2px] h-12">
        {frames.map((f) => {
          const v = f.csi / peakCsi;
          const isCurrent = f.week === currentWeek;
          return (
            <button
              key={f.week}
              onClick={() => { setAutoPlay(false); setWeek(f.week); }}
              title={`Week ${f.week}: CSI ${f.csi.toFixed(3)}, affected ${f.affected_count}`}
              className="flex-1 cursor-pointer"
              style={{
                height: `${Math.max(6, v * 100)}%`,
                background: severityColor(v),
                opacity: isCurrent ? 1 : 0.75,
                outline: isCurrent ? "1px solid rgba(230,235,244,0.6)" : undefined,
              }}
            />
          );
        })}
      </div>

      {/* ── scrubber ── */}
      <input
        type="range"
        min={0}
        max={maxWeek}
        value={currentWeek}
        onChange={(e) => { setAutoPlay(false); setWeek(Number(e.target.value)); }}
        className="w-full accent-accent-cyan"
      />

      {/* ── playback controls ── */}
      <div className="flex items-center gap-3">
        {/* rewind */}
        <button
          onClick={() => { setAutoPlay(false); setWeek(0); }}
          className="text-text-muted hover:text-text-primary transition text-lg leading-none"
          title="Go to start"
        >
          ⏮
        </button>

        {/* play / pause */}
        <button
          onClick={() => {
            if (currentWeek >= maxWeek) setWeek(0);
            setAutoPlay(!autoPlay);
          }}
          disabled={running}
          className={clsx(
            "px-3 py-1 rounded text-xs font-semibold transition",
            autoPlay
              ? "bg-accent-gold/20 text-accent-gold border border-accent-gold/40"
              : "bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/40 hover:bg-accent-cyan/25",
          )}
        >
          {autoPlay ? "⏸ Pause" : "▶ Play"}
        </button>

        {/* speed selector */}
        <div className="flex items-center gap-1 ml-1">
          {SPEED_OPTIONS.map((s) => (
            <button
              key={s}
              onClick={() => setSpeed(s)}
              className={clsx(
                "px-1.5 py-0.5 rounded text-[11px] num transition",
                speed === s
                  ? "bg-border-strong text-text-primary"
                  : "text-text-muted hover:text-text-secondary",
              )}
            >
              {s}×
            </button>
          ))}
        </div>

        <span className="ml-auto text-text-muted text-[10px] uppercase tracking-wider">speed</span>
      </div>

      {/* ── live metrics row ── */}
      <div className="grid grid-cols-4 gap-3 pt-1 text-xs">
        <div>
          <div className="text-text-muted uppercase tracking-wider text-[10px]">CSI</div>
          <div className="num text-text-primary">{curFrame?.csi.toFixed(3) ?? "—"}</div>
        </div>
        <div>
          <div className="text-text-muted uppercase tracking-wider text-[10px]">ECV</div>
          <div className="num text-text-primary">{curFrame?.ecv.toFixed(3) ?? "—"}</div>
        </div>
        <div>
          <div className="text-text-muted uppercase tracking-wider text-[10px]">ECV-geo</div>
          <div className="num text-text-primary">{curFrame?.ecv_geo.toFixed(2) ?? "—"}</div>
        </div>
        <div>
          <div className="text-text-muted uppercase tracking-wider text-[10px]">Affected</div>
          <div className="num text-text-primary">{curFrame?.affected_count ?? 0}</div>
        </div>
      </div>

      {/* ── overlay selector ── */}
      <div className="hairline pt-2 flex items-center gap-2 flex-wrap">
        <span className="text-[10px] text-text-muted uppercase tracking-wider mr-1">Overlay</span>
        {OVERLAY_OPTIONS.map((o) => (
          <button
            key={o.value}
            onClick={() => setOverlay(o.value)}
            className={clsx(
              "px-2 py-0.5 rounded text-[11px] border transition",
              overlayMode === o.value
                ? "bg-accent-violet/20 border-accent-violet/50 text-text-primary"
                : "border-border-subtle text-text-muted hover:text-text-secondary hover:border-border-strong",
            )}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}
