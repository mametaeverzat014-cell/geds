# UI / UX Design

Design language, screen breakdowns, motion principles. GEDS is meant to feel like an instrument — dense, calm, responsive. Not a dashboard. Not a slide deck.

> Reference posture: a Bloomberg terminal cross-bred with a NASA mission control with a contemporary cinematic aesthetic. Heavy data. Real-time. Honest about uncertainty. Beautiful by precision, not by decoration.

---

## 1. Design principles

1. **Information density without clutter.** Every pixel earns its place. Margins exist; ornament does not.
2. **Motion conveys causation.** A shock pulse moves *along an edge from origin to neighbor* — not in a vacuum. If motion doesn't carry information, it doesn't ship.
3. **Always show uncertainty.** Point estimates are accompanied by their prediction intervals. We never show a forecast without its band.
4. **One source of truth on the page.** If three components show the same number, they show the *same* number. Drift is a bug.
5. **Keyboard is first-class.** Every action has a shortcut. Power users never reach for the mouse to do a routine task.
6. **The first screen ships answers.** Don't make the user click to find the most important thing — show it.

---

## 2. Design tokens

### Color

Dark-first. The light theme exists but is the secondary mode.

```
--bg-base         #07090C   (near black, slight blue)
--bg-elevated    #0E1116   (panels, cards)
--bg-glass       rgba(14, 17, 22, 0.65) + backdrop-blur(16px)
--border-subtle  #1A1E26
--border-strong  #2A3140

--text-primary   #E6EBF4
--text-secondary #99A4B5
--text-muted     #5B6473
--text-on-color  #0B0E13

--accent-cyan    #4DD0E1   (interactive, primary action)
--accent-violet  #7C6CFB   (selection, highlights)
--accent-gold    #FFC34D   (warning, attention)

# Data severity scale (5 stops, perceptually uniform)
--sev-1 #2DD4BF   (calm — low shock)
--sev-2 #67D6A4
--sev-3 #FFC34D   (elevated)
--sev-4 #F97316
--sev-5 #EF4444   (critical)

# Sequential and diverging scales: Viridis, Cividis, RdYlBu — Tailwind-compiled.
```

The severity scale is what the eye learns to read: cyan→amber→red maps directly to "fine → watch → bad."

### Typography

```
--font-display   "Manrope"            (UI, dense interface)
--font-mono      "JetBrains Mono"     (all numerics, IDs, tickers)
--font-narrative "Source Serif Pro"   (long-form explanations, policy advisor)
```

Numerics always use the mono. Mixing proportional + mono in a single value (e.g., `12.4 %`) uses the mono for the digits and proportional for the unit, with manual tracking. Tabular figures (`font-variant-numeric: tabular-nums`) everywhere we show columns of numbers.

Type scale (in rems, base 16px): 0.75, 0.875, 1, 1.125, 1.25, 1.5, 1.875, 2.25, 3, 3.75. Headings use Manrope at semi-bold. Body at regular.

### Spacing

8-pt grid, 4-pt subgrid for tight clusters. Component padding lives in {8, 12, 16, 24, 32, 48}.

### Elevation

Three layers: base (the canvas), elevated (cards and panels with `--bg-elevated`), glass (overlays and toolbars with `--bg-glass` and backdrop-blur). No drop shadows on the base + elevated boundary — borders only. Drop shadow appears only on floating glass surfaces.

### Iconography

Phosphor icons (regular weight, 1.5px stroke). Custom icons for domain primitives (chokepoint, commodity flow, sectoral graph). All icons sit on a 24×24 grid with 1.5px stroke, 2px outer padding.

---

## 3. Screens

### 3.1 Atlas — the default landing inside the app

The first thing a user sees on auth. Goal: communicate the state of the world in 5 seconds.

```
┌───────────────────────────────────────────────────────────────────────────────┐
│  GEDS · Atlas               2026-05-12 Tue 14:23 UTC          🔍  ⌨  👤        │
│                                                                                │
│  Global Fragility Index   ▮▮▮▮▮▮▮▯▯▯  0.62  ↑0.04 7d   (above 6mo avg)       │
│  ────────────────────────────────────────────────────────────────────────     │
│                                                                                │
│                         ┌─────────────────────────┐                            │
│                         │                         │                            │
│                         │       [ 3D GLOBE        │      Top vulnerable today  │
│                         │         WITH TRADE      │      1.  KAZ × natural gas │
│                         │         FLOW ARCS,      │      2.  PRT × semiconductr│
│                         │         SHOCK PULSES,   │      3.  EGY × wheat       │
│                         │         CHOKEPOINTS ]   │      4.  …                 │
│                         │                         │                            │
│                         │                         │      Anomaly feed (live)   │
│                         │                         │      • +3σ price spike on  │
│                         │                         │        cobalt, 7d…         │
│                         └─────────────────────────┘      • AIS density at      │
│                                                            Bab-el-Mandeb -42% │
│  Chokepoint criticality                                                        │
│  Suez ━━━━━━━━━━━━━━ 12.3%   Hormuz ━━━━━━━━━ 9.1%   Malacca ━━━━━━━━ 7.6%    │
└───────────────────────────────────────────────────────────────────────────────┘
```

Components:

- **Top bar** — clock (UTC + local), command palette (Ctrl/Cmd+K), help, account.
- **Fragility Index ribbon** — single number, 7-day delta, comparison to 6-month average. Click expands a sparkline.
- **Globe** — interactive, rotates idly. Arcs animate with subtle dashed pulse in the direction of flow. Chokepoints are gold beacons. A real-time-detected anomaly pulses red.
- **Right rail** — Top vulnerable nodes (computed by the GNN, updated nightly), and a live anomaly feed.
- **Bottom strip** — top-3 chokepoints by current criticality.

### 3.2 Scenario Builder

Step-by-step but doesn't feel like a wizard. Three panels:

- **Left** — Scenario library (templates: COVID Supply 2020, Suez 2021, Ukraine 2022, Hormuz Closure, Taiwan Strait Disruption, Custom).
- **Center** — Map. Click a country, commodity, or chokepoint to add it as a shock target. Drag a magnitude slider; pick a duration.
- **Right** — Shock list (you can have multiple), config (horizon, ensemble size, rerouting strategy), and a "Run simulation" CTA with an estimated cost in compute time.

The center map shows live previews: as you raise a magnitude slider, arcs around the targeted node thicken. This is a *teaching* affordance — users learn how big "0.5 magnitude" actually is.

### 3.3 Simulation Theater

Full-screen playback. The most cinematic surface.

```
                    [ FULL-BLEED GLOBE OR MAP, USER CHOICE ]

                    Shock fronts expand from origin nodes,
                    colored on the severity scale, pulsing
                    along edges to neighbors.

  ┌─────────────────────────────────────────────────────────────────┐
  │ ◀◀  ⏸  ▶  ▶▶    Week  ▮▮▮▮▮▮▮▯▯▯▯▯▯▯▯▯  11 / 52    1x  2x  4x  │
  └─────────────────────────────────────────────────────────────────┘

  Inflation deviation (top 8)        GDP impact (top 8)
  EGY ▮▮▮▮▮▮▮ +8.7%                 GBR ▮▮▮▮▮ -2.1%
  TUR ▮▮▮▮▮ +6.3%                   DEU ▮▮▮▮ -1.9%
  …                                  …

  Reroute share 18%   ·   Active chokepoints 2   ·   Models: GNN+TFT
```

Floating panels can be dragged, collapsed, pinned. A "tour" mode auto-zooms to the most significant change at each tick, with a brief annotation ("Week 4: Suez closure begins; 12% of global container traffic seeks alternates").

### 3.4 Forecast Dashboard

Per-country / per-sector deep dive after a run. Four quadrants:

- **Top-left** — Inflation trajectory with prediction intervals. Annotations for known events.
- **Top-right** — GDP impact, decomposed by sector.
- **Bottom-left** — Shortage probability by commodity (top 10).
- **Bottom-right** — Unemployment risk with confidence band.

Every chart has a tiny "why" button that opens the attribution panel (SHAP top features + the GNN edges that carried the signal).

### 3.5 Policy Advisor

The most narrative screen. Recommendations are presented as cards in priority order. Each card has:

- The recommended action ("Diversify semiconductor imports: shift 28pts from TWN to KOR+JPN").
- Expected impact ("Peak GDP loss -2.1% → -0.9% under the modeled scenario class").
- Confidence and counterfactual chart (with vs. without).
- A "Simulate this intervention" button that runs the counterfactual scenario in-place.
- The model's own caveats ("Substitution constrained by 4–6q lead time. Confidence: moderate; based on N=4 historical analogues.")

This is where the design language softens. Source Serif Pro for the explanations. More whitespace. Less density. The platform earns the right to recommend by being explicit about its uncertainty.

### 3.6 Comparative Lab

Side-by-side simulation comparison. Up to 4 scenarios overlaid:

- A small-multiples grid (or shared axes, user choice) of trajectories.
- Diff highlighting: when scenarios differ by >X, the divergence is marked on the timeline.
- A "synthesize" button that uses the AI advisor to write a one-paragraph comparison.

---

## 4. Motion

GEDS uses motion as a language, not as decoration. Four principles:

1. **Causation > delight.** Animate transitions that imply causation; don't animate things that should feel instant.
2. **Match speed to magnitude.** A small change animates fast (120ms); a big change animates slower (320ms). Easing: `cubic-bezier(0.22, 1, 0.36, 1)` is the default.
3. **Never lie about latency.** If a server call is in flight, the affordance shows a real progress indicator. We do not animate optimistic states for actions that have any real failure mode.
4. **Respect reduced motion.** All non-causal motion becomes a fade or static under `prefers-reduced-motion`.

### Specific motion patterns

- **Shock pulse along an edge:** a brightened segment travels from source to target. Speed scales with `1 / decay`, so high-decay edges look slow and high-throughput edges look fast.
- **Severity tweens:** color changes on the severity scale are interpolated in OKLCH, not RGB, to avoid muddy intermediates.
- **Camera moves:** GSAP timelines, ease-in-out, max 1.2s for orbital moves. Never abrupt unless user-initiated.
- **Panel mounts:** 180ms slide + fade. The mount eases out; the unmount eases in.

---

## 5. Information density

GEDS is content-dense by design. To prevent visual fatigue we use:

- **Generous line-height** on bodies (1.55 minimum), tight (1.1) on numerics.
- **Hairlines** for table rules (1px, `--border-subtle`); no full-bleed dividers.
- **Sparklines instead of paragraphs** where a trend can replace a sentence.
- **Glanceable badges** (one short word + numeral) for categorical states.
- **Whitespace at the *page* level**, density at the *component* level. The Atlas page breathes; the Forecast Dashboard does not — and that's correct.

---

## 6. Empty and loading states

- **Empty**: never blank. Always include an explanation of what would be here, plus a "try this" CTA.
- **Loading**: skeletons that match the final layout (no spinners except for indeterminate WS waits).
- **Streaming**: when a simulation is mid-flight, the chart fills in left-to-right as frames arrive. Past frames are solid; the leading edge is dashed.

---

## 7. Microcopy

Tone: technical, terse, never cute. Confidence is shown in numbers, not in adverbs. The platform never says "unfortunately" or "oops." When it fails it says what failed and why.

- Status: `Idle · Running · Finished · Failed · Cancelled`.
- Error: `Could not run simulation: graph version mismatch (expected 2026-04-01-…, got 2026-03-15-…). Try refreshing the dataset.`
- Empty scenario list: `No scenarios yet. Start from a template or build one from scratch.`

---

## 8. Accessibility

- WCAG 2.2 AA contrast minimum. AAA on body text.
- All visualizations have a tabular dual: press `T` on any chart to open the data table.
- Keyboard map (Ctrl/Cmd+K opens the command palette listing everything):
  - `G` then `A` → Go to Atlas
  - `G` then `S` → Go to Scenarios
  - `N` → New scenario
  - `Space` → Pause / play current sim
  - `[` / `]` → Step back / forward one week
  - `?` → Open shortcut help
- Screen-reader announcements for live simulation: "Week 4 of 52. Top inflation impact: Egypt, +8.7%." Throttled to avoid spam.

---

## 9. Brand language (light touch)

- **Wordmark**: `GEDS` set in Manrope Extra-Bold, optical kerning, slightly extended tracking. Avoid acronyms in subheads.
- **Tagline (working)**: "Modeling fragility before it cascades."
- The mark itself is unobtrusive. The platform's identity is the *interface*, not the logo.

---

## 10. What we won't do

- No skeuomorphic globes that don't carry data.
- No gradient explosions.
- No "AI sparkle" iconography. Recommendations are labeled "AI-generated" in plain text.
- No emoji in product chrome.
- No three-color heatmaps without a colorblind alternative.
- No autoplay of full audio.
- No dark patterns. The "delete scenario" button is the same weight as "cancel" — destructive actions are confirmed but never hidden.
