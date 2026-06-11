"use client";

import * as d3 from "d3";
import { geoEquirectangular, geoPath } from "d3-geo";
import { useEffect, useMemo, useRef, useState } from "react";
import { feature } from "topojson-client";

import { severityColor } from "@/lib/colors";
import { useSimStore } from "@/lib/store";
import type { OverlayMode } from "@/lib/store";
import type { GraphSnapshot, NodeFrame } from "@/lib/types";

function overlayValue(nf: NodeFrame, mode: OverlayMode): number {
  switch (mode) {
    case "shock":          return nf.shock;
    case "inflation":      return Math.min(1, nf.inflation_pressure);
    case "output_loss":    return Math.min(1, nf.output_loss);
    case "unemployment":   return Math.min(1, nf.unemployment_risk);
  }
}

const OVERLAY_LABELS: Record<OverlayMode, string> = {
  shock:        "Shock intensity",
  inflation:    "Inflation pressure",
  output_loss:  "Output loss",
  unemployment: "Unemployment risk",
};

const WIDTH = 1100;
const HEIGHT = 580;
const WORLD_TOPO = "https://unpkg.com/world-atlas@2/countries-110m.json";

interface NodeWithCoords {
  id: string;
  name: string;
  kind: string;
  country?: string | null;
  industry?: string | null;
  lat: number;
  lon: number;
  gdp_usd: number;
}

export default function PropagationMap() {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const graph = useSimStore((s) => s.graph);
  const frames = useSimStore((s) => s.frames);
  const currentWeek = useSimStore((s) => s.currentWeek);
  const overlayMode = useSimStore((s) => s.overlayMode);
  const [land, setLand] = useState<GeoJSON.FeatureCollection | null>(null);

  // Load world TopoJSON once
  useEffect(() => {
    fetch(WORLD_TOPO)
      .then((r) => r.json())
      .then((topo: any) => {
        const fc = feature(topo, topo.objects.countries) as unknown as GeoJSON.FeatureCollection;
        setLand(fc);
      })
      .catch(() => setLand(null));
  }, []);

  const projection = useMemo(
    () =>
      geoEquirectangular()
        .scale(170)
        .translate([WIDTH / 2, HEIGHT / 2 + 20]),
    [],
  );

  const path = useMemo(() => geoPath(projection), [projection]);

  // Project node coordinates
  const nodes = useMemo<NodeWithCoords[]>(() => {
    if (!graph) return [];
    return graph.nodes
      .filter((n) => n.lat != null && n.lon != null)
      .map((n) => ({
        id: n.id,
        name: n.name,
        kind: n.kind,
        country: n.country,
        industry: n.industry,
        lat: n.lat as number,
        lon: n.lon as number,
        gdp_usd: n.gdp_usd,
      }));
  }, [graph]);

  // Frame lookup: shock state by node id at the current week
  const shockById = useMemo<Map<string, NodeFrame>>(() => {
    const map = new Map<string, NodeFrame>();
    const frame = frames.find((f) => f.week === currentWeek) ?? frames[frames.length - 1];
    if (frame) {
      for (const nf of frame.nodes) map.set(nf.id, nf);
    }
    return map;
  }, [frames, currentWeek]);

  // Origin node (the most-shocked node at peak; usually Taiwan semi)
  const originId = "TWN:semiconductors";
  const origin = nodes.find((n) => n.id === originId);

  const originProj = origin ? projection([origin.lon, origin.lat]) : null;

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      className="w-full h-auto select-none"
      style={{ background: "linear-gradient(180deg, #07090C 0%, #0B0F16 100%)" }}
    >
      <defs>
        <radialGradient id="atmo" cx="50%" cy="50%" r="60%">
          <stop offset="60%" stopColor="#0B1424" stopOpacity="0" />
          <stop offset="100%" stopColor="#1B2840" stopOpacity="0.55" />
        </radialGradient>
        <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="3" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <linearGradient id="arc-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%"  stopColor="#EF4444" stopOpacity="0.8" />
          <stop offset="100%" stopColor="#FFC34D" stopOpacity="0.3" />
        </linearGradient>
      </defs>

      {/* Atmosphere */}
      <rect width={WIDTH} height={HEIGHT} fill="url(#atmo)" />

      {/* World map background */}
      {land && (
        <g>
          {(land.features as GeoJSON.Feature[]).map((f, i) => (
            <path
              key={i}
              d={path(f) || undefined}
              fill="#0E1116"
              stroke="#1F2937"
              strokeWidth={0.4}
            />
          ))}
        </g>
      )}

      {/* Graticule */}
      {Array.from({ length: 7 }).map((_, i) => {
        const y = (HEIGHT / 7) * i;
        return <line key={`h-${i}`} x1={0} y1={y} x2={WIDTH} y2={y} stroke="#13202F" strokeWidth={0.3} />;
      })}

      {/* Cascade arcs from origin → currently-affected importer nodes */}
      {originProj &&
        nodes
          .filter((n) => n.id !== originId)
          .map((n) => {
            const nf = shockById.get(n.id);
            if (!nf || nf.shock < 0.05) return null;
            const intensity = overlayValue(nf, overlayMode);
            const target = projection([n.lon, n.lat]);
            if (!target) return null;
            const mid: [number, number] = [
              (originProj[0] + target[0]) / 2,
              Math.min(originProj[1], target[1]) - 120 * Math.min(1, Math.abs(target[0] - originProj[0]) / 600),
            ];
            const d = `M ${originProj[0]} ${originProj[1]} Q ${mid[0]} ${mid[1]} ${target[0]} ${target[1]}`;
            return (
              <g key={`arc-${n.id}`}>
                <path
                  d={d}
                  fill="none"
                  stroke={severityColor(intensity)}
                  strokeOpacity={0.35 + 0.55 * intensity}
                  strokeWidth={0.8 + 2.4 * intensity}
                  strokeLinecap="round"
                  filter="url(#glow)"
                />
                {/* traveling pulse: the shock visibly flows along the route */}
                <path
                  d={d}
                  fill="none"
                  stroke="#FFFFFF"
                  strokeOpacity={0.25 + 0.6 * intensity}
                  strokeWidth={1.2 + 1.6 * intensity}
                  strokeLinecap="round"
                  pathLength={100}
                  className="map-arc-pulse"
                  style={{ animationDelay: `${(n.id.charCodeAt(0) * 7 + n.id.length * 13) % 26 / 10}s` }}
                />
              </g>
            );
          })}

      {/* Chokepoint markers */}
      {nodes
        .filter((n) => n.kind === "chokepoint")
        .map((n) => {
          const p = projection([n.lon, n.lat]);
          if (!p) return null;
          const nf = shockById.get(n.id);
          const intensity = nf ? nf.shock : 0;
          return (
            <g key={n.id} transform={`translate(${p[0]}, ${p[1]})`}>
              <title>{`${n.name} (chokepoint)\nshock: ${(intensity * 100).toFixed(0)}%`}</title>
              <polygon
                points="0,-7 6,0 0,7 -6,0"
                fill="none"
                stroke="#FFC34D"
                strokeWidth={1.3}
                opacity={0.85}
              />
              {intensity > 0.05 && (
                <polygon
                  points="0,-7 6,0 0,7 -6,0"
                  fill={severityColor(intensity)}
                  opacity={0.4 + 0.5 * intensity}
                  className="pulse-soft"
                />
              )}
            </g>
          );
        })}

      {/* Country-industry nodes */}
      {nodes
        .filter((n) => n.kind === "country_industry")
        .map((n) => {
          const p = projection([n.lon, n.lat]);
          if (!p) return null;
          const nf = shockById.get(n.id);
          const shock = nf?.shock ?? 0;
          const value = nf ? overlayValue(nf, overlayMode) : 0;
          const r = 3 + Math.log10(1 + n.gdp_usd / 1e10) * 0.8;
          const color = severityColor(value);
          return (
            <g key={n.id} transform={`translate(${p[0]}, ${p[1]})`}>
              <title>
                {nf
                  ? `${n.name}\nshock: ${(nf.shock * 100).toFixed(0)}% · output loss: ${(nf.output_loss * 100).toFixed(0)}%\ninflation: ${(nf.inflation_pressure * 100).toFixed(1)}% · unemployment risk: ${(nf.unemployment_risk * 100).toFixed(0)}%`
                  : n.name}
              </title>
              {value > 0.15 && (
                <circle
                  r={r + 4 + 10 * value}
                  fill={color}
                  opacity={0.15 * value}
                  className="pulse-soft"
                />
              )}
              <circle
                r={r}
                fill={color}
                stroke={shock > 0.4 ? "#FFFFFF" : "#2A3140"}
                strokeOpacity={shock > 0.4 ? 0.4 : 1}
                strokeWidth={0.8}
                filter={value > 0.5 ? "url(#glow)" : undefined}
              />
            </g>
          );
        })}

      {/* Legend */}
      <g transform={`translate(${WIDTH - 220}, ${HEIGHT - 50})`}>
        <text x={0} y={0} fill="#99A4B5" fontSize={11}>
          {OVERLAY_LABELS[overlayMode]}
        </text>
        {[0, 0.25, 0.5, 0.75, 1].map((v, i) => (
          <rect
            key={i}
            x={i * 36}
            y={8}
            width={36}
            height={6}
            fill={severityColor(v)}
          />
        ))}
        <text x={0} y={28} fill="#5B6473" fontSize={10}>0</text>
        <text x={180} y={28} fill="#5B6473" fontSize={10}>1.0</text>
      </g>
    </svg>
  );
}
