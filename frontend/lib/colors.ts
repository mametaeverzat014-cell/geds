// 5-stop severity ramp.
const SEVERITY = ["#2DD4BF", "#67D6A4", "#FFC34D", "#F97316", "#EF4444"];

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

function hex(n: number) {
  return Math.round(Math.max(0, Math.min(255, n))).toString(16).padStart(2, "0");
}

function parseHex(c: string): [number, number, number] {
  const v = c.replace("#", "");
  return [parseInt(v.slice(0, 2), 16), parseInt(v.slice(2, 4), 16), parseInt(v.slice(4, 6), 16)];
}

export function severityColor(value: number): string {
  // value ∈ [0, 1] → ramp through 5 stops.
  const clamped = Math.max(0, Math.min(1, value));
  if (clamped <= 0.0001) return "#1A1E26"; // neutral background
  const idx = clamped * (SEVERITY.length - 1);
  const i = Math.floor(idx);
  const t = idx - i;
  const a = parseHex(SEVERITY[i]);
  const b = parseHex(SEVERITY[Math.min(i + 1, SEVERITY.length - 1)]);
  return "#" + hex(lerp(a[0], b[0], t)) + hex(lerp(a[1], b[1], t)) + hex(lerp(a[2], b[2], t));
}

export function severityGlow(value: number): string {
  const clamped = Math.max(0, Math.min(1, value));
  const a = Math.round(clamped * 80);
  return `0 0 ${8 + clamped * 28}px rgba(239, 68, 68, ${0.15 + clamped * 0.45})`;
}
