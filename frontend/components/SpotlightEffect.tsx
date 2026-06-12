"use client";

import { useEffect } from "react";

/**
 * Cursor spotlight for every `.panel`: one delegated, rAF-throttled
 * mousemove listener writes --mx/--my custom properties that the
 * `.panel::after` radial gradient reads. Renders nothing.
 */
export default function SpotlightEffect() {
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (window.matchMedia("(hover: none)").matches) return; // touch devices

    let raf = 0;
    let lastEvent: MouseEvent | null = null;

    const apply = () => {
      raf = 0;
      const e = lastEvent;
      if (!e) return;
      const el = (e.target as Element | null)?.closest?.(".panel") as HTMLElement | null;
      if (!el) return;
      const r = el.getBoundingClientRect();
      el.style.setProperty("--mx", `${(((e.clientX - r.left) / r.width) * 100).toFixed(2)}%`);
      el.style.setProperty("--my", `${(((e.clientY - r.top) / r.height) * 100).toFixed(2)}%`);
    };

    const onMove = (e: MouseEvent) => {
      lastEvent = e;
      if (!raf) raf = requestAnimationFrame(apply);
    };

    document.addEventListener("mousemove", onMove, { passive: true });
    return () => {
      document.removeEventListener("mousemove", onMove);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  return null;
}
