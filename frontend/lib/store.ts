import { create } from "zustand";
import type {
  AdvisorResult,
  Frame,
  GraphSnapshot,
  Scenario,
  SimulationSummary,
} from "./types";

export type OverlayMode = "shock" | "inflation" | "output_loss" | "unemployment";
export type BackendStatus = "checking" | "online" | "offline";

export type GraphVersion = "v2" | "v3";

interface SimState {
  graph: GraphSnapshot | null;
  graphVersion: GraphVersion;
  scenarios: Scenario[];
  selectedScenarioId: string;
  customMagnitude: number;
  customDuration: number;

  // run state
  running: boolean;
  startedAt: number | null;
  frames: Frame[];
  currentWeek: number;
  summary: SimulationSummary | null;
  error: string | null;

  // connectivity (drives the offline banner + status dot)
  backendStatus: BackendStatus;

  // auto-play
  autoPlay: boolean;
  playbackSpeed: number; // frames per second

  // overlay
  overlayMode: OverlayMode;

  // policy advisor
  advisor: AdvisorResult | null;
  advisorLoading: boolean;

  // actions
  setGraph: (g: GraphSnapshot) => void;
  setGraphVersion: (v: GraphVersion) => void;
  setScenarios: (s: Scenario[]) => void;
  setSelectedScenario: (id: string) => void;
  setCustom: (mag: number, dur: number) => void;
  beginRun: () => void;
  pushFrame: (f: Frame) => void;
  setCurrentWeek: (w: number) => void;
  completeRun: (s: SimulationSummary) => void;
  failRun: (msg: string) => void;
  setAutoPlay: (v: boolean) => void;
  setPlaybackSpeed: (v: number) => void;
  setOverlayMode: (m: OverlayMode) => void;
  setAdvisor: (a: AdvisorResult | null) => void;
  setAdvisorLoading: (v: boolean) => void;
  setBackendStatus: (s: BackendStatus) => void;
}

export const useSimStore = create<SimState>((set) => ({
  graph: null,
  graphVersion: "v2",
  scenarios: [],
  selectedScenarioId: "taiwan-semi-75",
  customMagnitude: 0.75,
  customDuration: 20,

  running: false,
  startedAt: null,
  frames: [],
  currentWeek: 0,
  summary: null,
  error: null,

  autoPlay: false,
  playbackSpeed: 4,

  overlayMode: "shock",

  advisor: null,
  advisorLoading: false,

  backendStatus: "checking",

  setGraph: (g) => set({ graph: g }),
  setGraphVersion: (v) => set({ graphVersion: v, frames: [], currentWeek: 0, summary: null }),
  setScenarios: (s) => set({ scenarios: s }),
  setSelectedScenario: (id) => set({ selectedScenarioId: id }),
  setCustom: (mag, dur) => set({ customMagnitude: mag, customDuration: dur }),
  beginRun: () =>
    set({
      running: true,
      startedAt: Date.now(),
      frames: [],
      currentWeek: 0,
      summary: null,
      error: null,
      autoPlay: false,
      advisor: null,
    }),
  pushFrame: (f) =>
    set((st) => ({
      frames: [...st.frames, f],
      currentWeek: f.week,
    })),
  setCurrentWeek: (w) => set({ currentWeek: w }),
  completeRun: (s) => set({ summary: s, running: false, currentWeek: 0, autoPlay: true }),
  failRun: (msg) => set({ error: msg, running: false }),
  setAutoPlay: (v) => set({ autoPlay: v }),
  setPlaybackSpeed: (v) => set({ playbackSpeed: v }),
  setOverlayMode: (m) => set({ overlayMode: m }),
  setAdvisor: (a) => set({ advisor: a }),
  setAdvisorLoading: (v) => set({ advisorLoading: v }),
  setBackendStatus: (s) => set({ backendStatus: s }),
}));
