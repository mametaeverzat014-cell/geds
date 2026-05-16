# Frontend Architecture

Next.js 14+ App Router. TypeScript everywhere. The frontend is responsible for three things: rendering the platform's data at a research-grade level of polish, orchestrating live simulation playback, and being fast enough that interactive scenario building feels instant.

---

## 1. Tech choices

| Concern | Choice | Why |
|---|---|---|
| Framework | Next.js 14 App Router | Server components for static pages, edge runtime for the lightweight read API, RSC streaming for hydration |
| Language | TypeScript (strict) | Non-negotiable for a multi-package frontend of this complexity |
| Styling | Tailwind CSS + CSS variables for theme tokens | Tailwind for velocity; tokens for dark/contrast modes and data-color scales |
| Component primitives | Radix UI (headless) + custom design system on top | Accessibility for free, total control of look-and-feel |
| Server state | TanStack Query | Caching, dedup, optimistic updates, suspense integration |
| Client state | Zustand | The simulation player needs a synchronous global store; Zustand is tiny and ergonomic |
| Forms | React Hook Form + Zod | Lightweight, schema-first, plays well with the API's Zod-derived types |
| Charts (bespoke) | D3 (selection-free, hooks-based) | We need real custom dataviz, not chart-library skinning |
| Charts (workhorse) | Visx | D3 primitives wrapped in React; covers 80% of standard cases |
| 3D & WebGL | Three.js via React Three Fiber + drei + postprocessing | The globe and shader effects need shader-level control |
| Maps | Mapbox GL + deck.gl | Mapbox for base tiles, deck.gl for high-performance overlays (arc, scatter, heatmap, hex) |
| Animations | Framer Motion (UI) + GSAP (timeline-heavy sequences) | Motion for components, GSAP for cinematic scenario intros |
| WebSocket | Native WebSocket + reconnecting wrapper + msgpack parser | One protocol, robust reconnect, binary frames |
| i18n | next-intl | First-class App Router support |
| Testing | Vitest + Testing Library + Playwright | Unit, component, E2E |

---

## 2. Routing

App Router structure:

```
frontend/app/
├── (marketing)/                 ← public landing pages, server-rendered, edge
│   ├── page.tsx
│   ├── how-it-works/page.tsx
│   └── data-sources/page.tsx
│
├── (app)/                       ← authenticated app shell
│   ├── layout.tsx               ← global chrome, theme provider, telemetry
│   ├── atlas/page.tsx           ← landing inside the app: live globe
│   ├── scenarios/
│   │   ├── page.tsx             ← scenario library
│   │   ├── new/page.tsx         ← scenario builder
│   │   └── [id]/
│   │       ├── page.tsx         ← scenario detail + simulation theater
│   │       ├── forecast/page.tsx
│   │       └── policy/page.tsx
│   ├── compare/page.tsx         ← comparative lab
│   ├── settings/page.tsx
│   └── api/                     ← BFF route handlers (proxy + auth)
│       └── …
│
└── globals.css
```

The `(marketing)` group can pre-render at the edge. The `(app)` group is all client-component-heavy and authenticated.

---

## 3. State architecture

Four kinds of state, four mechanisms:

### 3.1 Server state — TanStack Query

Every API call goes through a typed client generated from OpenAPI:

```ts
// frontend/lib/api/client.ts
export const api = createClient<paths>({
  baseUrl: process.env.NEXT_PUBLIC_API_URL!,
  fetch: authFetch,
})

// frontend/lib/api/hooks.ts
export const useCountry = (iso3: string) =>
  useQuery({ queryKey: ['country', iso3], queryFn: () => api.GET('/api/v1/countries/{iso3}', { params: { path: { iso3 } } }) })
```

Invalidation strategy: scenario edits invalidate `['scenarios', id]`; simulation completion invalidates `['simulation', runId]` and any analytics that depend on the latest run.

### 3.2 Simulation player state — Zustand

Used by every visualization that subscribes to the playback head:

```ts
// frontend/lib/store/sim.ts
type SimStore = {
  runId: string | null
  currentWeek: number
  isPlaying: boolean
  playbackSpeed: number
  selectedEntity: EntityRef | null
  hoveredEntity: EntityRef | null
  frameBuffer: Map<number, Frame>        // week → frame
  setRun: (id: string) => void
  play: () => void
  pause: () => void
  scrubTo: (week: number) => void
  ingestFrame: (frame: Frame) => void    // called by the WS handler
}
```

Visualizations read `currentWeek` and the appropriate slice of `frameBuffer`. Multiple components share one render schedule via requestAnimationFrame so the globe and the timeline scrub in lockstep.

### 3.3 UI state — local component

Camera position, panel open/closed, drawer state, form field state — never lifted, never serialized.

### 3.4 Persisted user prefs — `localStorage` + Zustand `persist` middleware

Theme, last-viewed scenario, default playback speed, color-blind scale.

---

## 4. Live simulation pipeline

The most performance-sensitive subsystem.

```
                 ┌──────────────────────────┐
                 │      Backend gateway     │
                 │   WS: msgpack frames     │
                 └────────────┬─────────────┘
                              │
              ┌───────────────▼───────────────┐
              │   useSimulationStream(runId)  │
              │   - reconnecting WS client    │
              │   - msgpack decode            │
              │   - backpressure: drop frame  │
              │     if buffer > N             │
              └───────────────┬───────────────┘
                              │
              ┌───────────────▼───────────────┐
              │    Zustand: ingestFrame()     │
              │    - merges into frameBuffer  │
              │    - advances playback head   │
              │      if "follow live" is on   │
              └───────────────┬───────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            │                 │                 │
   ┌────────▼─────┐  ┌────────▼──────┐ ┌────────▼─────┐
   │   Globe      │  │ Heatmap layer │ │  Timeline    │
   │   (R3F)      │  │ (deck.gl)     │ │  (D3)        │
   └──────────────┘  └───────────────┘ └──────────────┘
```

Key performance moves:

- **Binary frames.** The WS payload is msgpack, decoded incrementally with a streaming parser.
- **Frame budget.** Each render frame at 60fps is 16.7ms. The globe shader path takes ~6–8ms; everything else has to fit in the rest. Heavy work (path computations, color scaling) is memoized aggressively and re-runs only when `currentWeek` changes.
- **Web Workers.** Anything CPU-heavy that can be offloaded — d3-geo projection of large arc sets, recomputation of choropleth color scales, JSON normalization — runs in a Worker. Communicated to the main thread via SharedArrayBuffer where supported.
- **GPU-side state.** For the globe, the shock-state vector is uploaded to a 1D texture; the fragment shader reads from it to color nodes and animate arc pulses. We re-upload on `currentWeek` change, not on every frame.
- **Selective rerendering.** Subscriptions to Zustand are sliced per-component; a panel that only cares about `currentWeek` does not re-render on `frameBuffer` updates.

---

## 5. Rendering subsystems

### 5.1 Globe

React Three Fiber scene. Components:

- `<EarthMesh />` — high-res world geometry + day/night shader.
- `<Atmosphere />` — outer glow with a radial falloff shader.
- `<TradeFlows arcs={...} />` — instanced great-circle arcs; one draw call for thousands of flows. Color = commodity category, opacity = log(value), animated dash for pulse direction.
- `<NodeMarkers nodes={...} />` — instanced spheres; size = GDP, color = current vulnerability score.
- `<ShockPulses />` — additive blending shader that animates expanding rings from shocked nodes, colored by severity.
- `<ChokepointMarkers />` — distinct iconography for canals/straits; pulse when active.

The scene uses postprocessing chains for bloom (the shock pulses get an additive bloom) and FXAA. We run at 60fps on a mid-tier laptop; the 3D path degrades gracefully on low-DPI displays.

### 5.2 Map

Mapbox GL base + deck.gl overlays:

- **Choropleth layer** — country-level shock_state or vulnerability.
- **ArcLayer** — bilateral flows, colored by commodity.
- **HexagonLayer** — port density aggregation.
- **HeatmapLayer** — contagion heatmap mode.
- **IconLayer** — chokepoints.

deck.gl handles 100k+ arcs at 60fps via GPU instancing. We pre-aggregate to top-N flows by value so the layer cap is well under that.

### 5.3 Charts

- **Sectoral propagation graph** — D3 force-directed layout of sector nodes with edges weighted by I-O coefficients; bespoke component because library forces wouldn't match the design.
- **Timeline / playback bar** — Visx; annotated with shock events and forecast intervals.
- **Comparative trajectory chart** — Visx line + area for prediction intervals; supports overlaying up to 6 scenarios.
- **Contagion heatmap** — D3 with a custom matrix renderer for 200×200 country × country exposure.

### 5.4 Cinematic mode

The "Simulation Theater" supports a cinematic playback: full-screen, narrative title cards (powered by GSAP), camera orbits the globe, shock fronts animate in sync with the audio cue (optional). Built with GSAP timeline + R3F camera controls.

---

## 6. Component conventions

- **Server components by default** for pages and layouts; **client components** explicitly opt in with `'use client'`.
- **Suspense boundaries** around data-fetching client components for streaming hydration.
- **Error boundaries** at the route segment level; errors degrade to inline messages, never blank screens.
- **No prop drilling beyond 2 levels.** Pull from Zustand or use composition.
- **Naming**: `<Globe />`, `<TradeFlows />`, `<ScenarioBuilder />`. Verbs only for actions (`<RunSimulation />`).
- **One file per component** for non-trivial components. Co-locate styles and stories.

---

## 7. Performance budgets

| Metric | Budget |
|---|---|
| LCP (Atlas page) | < 2.5s |
| TTI (Atlas page) | < 3.5s |
| Initial JS bundle | < 250KB gzipped |
| Globe frame time | < 12ms on a mid-tier laptop |
| Scenario builder TTI | < 1.5s |
| WS frame ingest | < 3ms per frame |

Bundle splits: the marketing pages do not pull in Three.js / deck.gl / D3 — that lives in the `(app)` group. Heavy components (`<Globe />`, `<Map />`) are dynamically imported with `next/dynamic` and a skeleton fallback.

---

## 8. Accessibility

- All visualizations have a parallel tabular view reachable via the keyboard (`?` opens the help overlay listing shortcuts).
- Color scales are color-blind safe by default (Viridis / Cividis); user can switch to a high-contrast scheme.
- Motion respects `prefers-reduced-motion`: cinematic intros become static; pulses become subtle fades.
- Focus management on modal open/close; trap focus inside dialogs.
- Semantic landmarks: every page has `<main>`, `<nav>`, properly labeled regions.

---

## 9. Telemetry

OpenTelemetry web SDK. We track:

- Core Web Vitals (CLS, LCP, INP) per route.
- API call latency from client perspective.
- Scenario builder funnel (view → start → submit → simulation watched).
- Performance counters: frame drop rate, frame buffer underrun rate.

Sensitive PII is never sent. Telemetry endpoint is our own backend; no third-party analytics.

---

## 10. Testing

- **Vitest + Testing Library** — every non-trivial component has at least the "renders without crashing with mock data" test, plus interaction tests for forms and state stores.
- **Storybook** — components in isolation; visual regression via Chromatic for the core viz components.
- **Playwright** — end-to-end happy paths: create scenario → run → watch → see policy recommendations. One smoke test per major route.
- **Lighthouse CI** — per-PR performance budgets enforced.

---

## 11. Local dev

```
make dev
```

starts the Next.js dev server pointed at the backend running via Docker Compose. Hot reload everywhere. Mock data fixtures available via `NEXT_PUBLIC_USE_FIXTURES=1` so frontend work doesn't require a running backend.
