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
      <div className="panel p-4 text-[13px] text-text-muted">
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
        <span className="num text-[13px] text-text-secondary">
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
              className="flex-1 cursor-pointer rounded-t-[2px] origin-bottom transition-[opacity,transform,box-shadow] duration-150 hover:opacity-100 hover:scale-y-[1.05]"
              style={{
                height: `${Math.max(6, v * 100)}%`,
                background: isCurrent
                  ? `linear-gradient(180deg, rgba(230,235,244,0.9), ${severityColor(v)} 45%)`
                  : severityColor(v),
                opacity: isCurrent ? 1 : 0.7,
                boxShadow: isCurrent ? `0 0 12px ${severityColor(v)}` : undefined,
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
        className="scrubber"
        style={{ "--fill": `${maxWeek > 0 ? (currentWeek / maxWeek) * 100 : 0}%` } as React.CSSProperties}
      />

      {/* ── playback controls ── */}
      <div className="flex items-center gap-3">
        {/* rewind */}
        <button
          onClick={() => { setAutoPlay(false); setWeek(0); }}
          className="h-8 w-8 grid place-items-center rounded-full border border-border-subtle text-text-muted transition-all duration-200 hover:text-text-primary hover:border-border-strong hover:shadow-[0_0_14px_-4px_rgba(77,208,225,0.5)] active:scale-90"
          title="Go to start"
        >
          <svg width="11" height="11" viewBox="0 0 12 12" fill="currentColor" aria-hidden="true">
            <path d="M1.5 1.25c.41 0 .75.34.75.75v3.1L9.9 1.18c.67-.4 1.52.09 1.52.87v7.9c0 .78-.85 1.27-1.52.87L2.25 6.9V10a.75.75 0 0 1-1.5 0V2c0-.41.34-.75.75-.75Z" />
          </svg>
        </button>

        {/* play / pause */}
        <button
          onClick={() => {
            if (currentWeek >= maxWeek) setWeek(0);
            setAutoPlay(!autoPlay);
          }}
          disabled={running}
          className={clsx(
            "px-3.5 py-1.5 rounded-full text-[13px] font-semibold border inline-flex items-center gap-1.5 transition-all duration-200 active:scale-95",
            autoPlay
              ? "bg-accent-gold/15 text-accent-gold border-accent-gold/45 shadow-[0_0_18px_-6px_rgba(255,195,77,0.6)]"
              : "bg-accent-cyan/12 text-accent-cyan border-accent-cyan/45 hover:bg-accent-cyan/20 hover:shadow-[0_0_18px_-6px_rgba(77,208,225,0.7)] hover:-translate-y-px",
          )}
        >
          {autoPlay ? (
            <svg width="9" height="11" viewBox="0 0 10 12" fill="currentColor" aria-hidden="true">
              <rect x="0.5" width="3.2" height="12" rx="1" />
              <rect x="6.3" width="3.2" height="12" rx="1" />
            </svg>
          ) : (
            <svg width="9" height="11" viewBox="0 0 11 12" fill="currentColor" aria-hidden="true">
              <path d="M0.5 1.13c0-.78.85-1.27 1.53-.88l8.4 4.87c.67.4.67 1.37 0 1.76l-8.4 4.87c-.68.4-1.53-.1-1.53-.88V1.13Z" />
            </svg>
          )}
          {autoPlay ? "Pause" : "Play"}
        </button>

        {/* speed selector — segmented pill */}
        <div className="flex items-center gap-0.5 ml-1 p-0.5 rounded-full border border-border-subtle bg-bg-base/50">
          {SPEED_OPTIONS.map((s) => (
            <button
              key={s}
              onClick={() => setSpeed(s)}
              className={clsx(
                "px-2 py-0.5 rounded-full text-[12px] num transition-all duration-200",
                speed === s
                  ? "bg-gradient-to-r from-accent-cyan/25 to-accent-violet/25 text-text-primary shadow-[0_0_10px_-3px_rgba(124,108,251,0.7)]"
                  : "text-text-muted hover:text-text-secondary",
              )}
            >
              {s}×
            </button>
          ))}
        </div>

        <span className="ml-auto text-text-muted text-[12px] uppercase tracking-wider">speed</span>
      </div>

      {/* ── live metrics row ── */}
      <div className="grid grid-cols-4 gap-3 pt-1 text-[13px]">
        <div>
          <div className="text-text-muted uppercase tracking-wider text-[12px]">CSI</div>
          <div className="num text-text-primary">{curFrame?.csi.toFixed(3) ?? "—"}</div>
        </div>
        <div>
          <div className="text-text-muted uppercase tracking-wider text-[12px]">ECV</div>
          <div className="num text-text-primary">{curFrame?.ecv.toFixed(3) ?? "—"}</div>
        </div>
        <div>
          <div className="text-text-muted uppercase tracking-wider text-[12px]">ECV-geo</div>
          <div className="num text-text-primary">{curFrame?.ecv_geo.toFixed(2) ?? "—"}</div>
        </div>
        <div>
          <div className="text-text-muted uppercase tracking-wider text-[12px]">Affected</div>
          <div className="num text-text-primary">{curFrame?.affected_count ?? 0}</div>
        </div>
      </div>

      {/* ── overlay selector ── */}
      <div className="hairline pt-2 flex items-center gap-2 flex-wrap">
        <span className="text-[12px] text-text-muted uppercase tracking-wider mr-1">Overlay</span>
        {OVERLAY_OPTIONS.map((o) => (
          <button
            key={o.value}
            onClick={() => setOverlay(o.value)}
            className={clsx(
              "px-2.5 py-0.5 rounded-full text-[12px] border transition-all duration-200 active:scale-95",
              overlayMode === o.value
                ? "bg-gradient-to-r from-accent-violet/25 to-accent-cyan/15 border-accent-violet/55 text-text-primary shadow-[0_0_14px_-5px_rgba(124,108,251,0.8)]"
                : "border-border-subtle text-text-muted hover:text-text-secondary hover:border-border-strong hover:-translate-y-px",
            )}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}
