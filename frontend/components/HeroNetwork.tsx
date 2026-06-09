"use client";

import { useMemo, useState } from "react";

/**
 * Hero backdrop: a Higgsfield-generated "global trade network" artwork layered
 * over a deterministic procedural SVG of the same concept. The SVG renders
 * instantly and stays as the base if the CDN image is unavailable, so the
 * header never shows a broken or empty backdrop.
 */

const HERO_IMG =
  "https://d8j0ntlcm91z4.cloudfront.net/user_3EgDe1sjfLi9Puo452GwUtlGbt8/hf_20260609_202528_2ba1f66e-99c9-43bd-8e0c-a729f1c43d78.png";

// Deterministic PRNG so the dot field is identical on server and client.
function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const PALETTE = ["#4DD0E1", "#7C6CFB", "#4DD0E1", "#4DD0E1", "#FFC34D"];

export default function HeroNetwork() {
  const [imgOk, setImgOk] = useState(true);

  const { dots, arcs } = useMemo(() => {
    const rnd = mulberry32(20260609);
    const dots = Array.from({ length: 110 }, () => {
      // bias the field toward the upper-right, where the title isn't
      const x = 25 + rnd() * 75;
      const y = rnd() * 60;
      return {
        x, y,
        r: 0.25 + rnd() * 0.9,
        c: PALETTE[Math.floor(rnd() * PALETTE.length)],
        o: 0.25 + rnd() * 0.6,
      };
    });
    const hubs = dots.filter((d) => d.r > 0.8).slice(0, 14);
    const arcs = hubs.slice(1).map((d, i) => {
      const s = hubs[Math.floor(rnd() * (i + 1))];
      const mx = (s.x + d.x) / 2;
      const my = Math.min(s.y, d.y) - 6 - rnd() * 8;
      return { d: `M ${s.x} ${s.y} Q ${mx} ${my} ${d.x} ${d.y}`, o: 0.10 + rnd() * 0.16 };
    });
    return { dots, arcs };
  }, []);

  return (
    <div className="hero-backdrop" aria-hidden="true">
      {/* procedural base layer */}
      <svg
        viewBox="0 0 100 56"
        preserveAspectRatio="xMidYMid slice"
        className="absolute inset-0 w-full h-full"
      >
        <defs>
          <radialGradient id="hero-glow-a" cx="78%" cy="18%" r="55%">
            <stop offset="0%" stopColor="#4DD0E1" stopOpacity="0.14" />
            <stop offset="100%" stopColor="#4DD0E1" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="hero-glow-b" cx="45%" cy="55%" r="50%">
            <stop offset="0%" stopColor="#7C6CFB" stopOpacity="0.10" />
            <stop offset="100%" stopColor="#7C6CFB" stopOpacity="0" />
          </radialGradient>
        </defs>
        <rect width="100" height="56" fill="url(#hero-glow-a)" />
        <rect width="100" height="56" fill="url(#hero-glow-b)" />
        {arcs.map((a, i) => (
          <g key={i}>
            <path d={a.d} fill="none" stroke="#4DD0E1" strokeWidth="0.08" opacity={a.o} />
            {/* traveling light pulse over the static arc */}
            <path
              d={a.d}
              fill="none"
              stroke={i % 3 === 2 ? "#7C6CFB" : "#4DD0E1"}
              strokeWidth="0.16"
              strokeLinecap="round"
              pathLength={100}
              className="hero-arc"
              style={{ animationDelay: `${(i * 1.7) % 7}s`, opacity: Math.min(0.7, a.o * 3) }}
            />
          </g>
        ))}
        {dots.map((d, i) => (
          <circle key={i} cx={d.x} cy={d.y} r={d.r * 0.32} fill={d.c} opacity={d.o} />
        ))}
      </svg>

      {/* Higgsfield artwork on top, hidden if the CDN is unreachable */}
      {imgOk && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={HERO_IMG}
          alt=""
          loading="eager"
          decoding="async"
          onError={() => setImgOk(false)}
        />
      )}
    </div>
  );
}
