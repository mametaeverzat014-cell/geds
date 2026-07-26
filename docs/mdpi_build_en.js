// MDPI-style .docx generator for the GEDS paper (EN) — submission-format.
// Emulates the MDPI LAYOUT/typography only — no publisher logo/branding.
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, AlignmentType, Table, TableRow, TableCell,
  WidthType, BorderStyle, ShadingType, SectionType, PageNumber, Footer,
  TabStopType, ImageRun,
} = require("docx");

const FONT = "Palatino Linotype";
const GREEN = "0E7C3A", DARK = "1A1A1A", GREY = "595959";
const HEADSH = "E8F3EC", BOXSH = "F5F7F6", BOXBD = "D7E2DB", CODESH = "F2F2F0";
const TW = 9638;
const FIGDIR = "/home/user/geds/backend/data/calibration/figures";
const OUT = "/home/user/geds/docs/PAPER_MDPI.en.docx";
const NONE = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };

function runs(text, size = 19, extra = {}) {
  const out = [];
  for (const part of text.split(/(\*\*[^*]+\*\*)/g)) {
    if (!part) continue;
    if (/^\*\*[^*]+\*\*$/.test(part))
      out.push(new TextRun({ text: part.slice(2, -2), bold: true, font: FONT, size, ...extra }));
    else for (const it of part.split(/(\*[^*]+\*)/g)) {
      if (!it) continue;
      if (/^\*[^*]+\*$/.test(it)) out.push(new TextRun({ text: it.slice(1, -1), italics: true, font: FONT, size, ...extra }));
      else out.push(new TextRun({ text: it, font: FONT, size, ...extra }));
    }
  }
  return out;
}
function mathRuns(s, size = 18) {
  const out = []; let i = 0, buf = "";
  const push = (txt, m) => { if (!txt) return; const o = { font: FONT, size };
    if (m === "sub") o.subScript = true; if (m === "sup") o.superScript = true; if (m === "it") o.italics = true;
    out.push(new TextRun({ text: txt, ...o })); };
  while (i < s.length) { const c = s[i];
    if (c === "_" && s[i + 1] === "(") { push(buf, "r"); buf = ""; i += 2; let d = ""; while (s[i] !== ")" && i < s.length) d += s[i++]; i++; push(d, "sub"); }
    else if (c === "^" && s[i + 1] === "(") { push(buf, "r"); buf = ""; i += 2; let d = ""; while (s[i] !== ")" && i < s.length) d += s[i++]; i++; push(d, "sup"); }
    else if (c === "~") { push(buf, "r"); buf = ""; i++; let d = ""; while (s[i] !== "~" && i < s.length) d += s[i++]; i++; push(d, "it"); }
    else { buf += c; i++; } }
  push(buf, "r"); return out;
}
const P = (text, o = {}) => new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { line: 240, after: o.after ?? 20 },
  indent: o.indent === false ? undefined : { firstLine: 220 }, children: runs(text, o.size ?? 19) });
const EQ = (num, s) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 40, after: 40 },
  children: [...mathRuns(s, 18), new TextRun({ text: `    (${num})`, font: FONT, size: 18 })] });
const H1 = (t) => new Paragraph({ spacing: { before: 200, after: 70 }, keepNext: true,
  children: [new TextRun({ text: t, bold: true, font: FONT, size: 21, color: DARK })] });
const H2 = (t) => new Paragraph({ spacing: { before: 140, after: 50 }, keepNext: true,
  children: [new TextRun({ text: t, bold: true, italics: true, font: FONT, size: 19, color: DARK })] });
const LI = (n, t) => new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { line: 240, after: 20 },
  indent: { left: 300, hanging: 300 }, children: runs(`${n}. ${t}`, 19) });
const BUL = (t) => new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { line: 240, after: 20 },
  indent: { left: 300, hanging: 160 }, children: runs(`—  ${t}`, 19) });
const REF = (n, t) => new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { line: 210, after: 24 },
  indent: { left: 300, hanging: 300 }, children: runs(`${n}. ${t}`, 16) });
function table(colW, rows) {
  const border = { top: { style: BorderStyle.SINGLE, size: 12, color: DARK }, bottom: { style: BorderStyle.SINGLE, size: 12, color: DARK },
    left: NONE, right: NONE, insideHorizontal: NONE, insideVertical: NONE };
  return new Table({ columnWidths: colW, width: { size: TW, type: WidthType.DXA }, borders: border,
    rows: rows.map((cells, ri) => new TableRow({ tableHeader: ri === 0,
      children: cells.map((txt, ci) => new TableCell({ width: { size: colW[ci], type: WidthType.DXA },
        shading: ri === 0 ? { type: ShadingType.CLEAR, fill: HEADSH } : undefined,
        borders: ri === 0 ? { bottom: { style: BorderStyle.SINGLE, size: 8, color: DARK } } : undefined,
        margins: { top: 40, bottom: 40, left: 80, right: 80 },
        children: [new Paragraph({ alignment: ci === 0 ? AlignmentType.LEFT : AlignmentType.CENTER, spacing: { line: 220, after: 0 },
          children: runs(txt, 16, ri === 0 ? { bold: true } : {}) })] })) })) });
}
const CAP = (t) => new Paragraph({ spacing: { before: 60, after: 40 }, alignment: AlignmentType.LEFT,
  children: [new TextRun({ text: t.split(".")[0] + ".", bold: true, font: FONT, size: 16 }),
    new TextRun({ text: t.slice(t.indexOf(".") + 1), font: FONT, size: 16 })] });
function figure(file, capText, targetW = 540) {
  const b = fs.readFileSync(`${FIGDIR}/${file}`);
  const w = b.readUInt32BE(16), h = b.readUInt32BE(20);
  return [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 60, after: 30 },
      children: [new ImageRun({ data: b, type: "png", transformation: { width: targetW, height: Math.round(targetW * h / w) } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
      children: [new TextRun({ text: capText.split(".")[0] + ".", bold: true, font: FONT, size: 16 }),
        new TextRun({ text: capText.slice(capText.indexOf(".") + 1), font: FONT, size: 16 })] })];
}
const CODE = (lines) => new Table({ columnWidths: [TW], width: { size: TW, type: WidthType.DXA },
  borders: { top: { style: BorderStyle.SINGLE, size: 3, color: BOXBD }, bottom: { style: BorderStyle.SINGLE, size: 3, color: BOXBD },
    left: { style: BorderStyle.SINGLE, size: 3, color: BOXBD }, right: { style: BorderStyle.SINGLE, size: 3, color: BOXBD }, insideHorizontal: NONE, insideVertical: NONE },
  rows: [new TableRow({ children: [new TableCell({ width: { size: TW, type: WidthType.DXA }, shading: { type: ShadingType.CLEAR, fill: CODESH },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: lines.map((l) => new Paragraph({ spacing: { line: 220, after: 0 }, children: [new TextRun({ text: l, font: "Consolas", size: 16 })] })) })] })] });

// ===================== FRONT MATTER =====================
const masthead = new Paragraph({ spacing: { after: 40 }, border: { bottom: { style: BorderStyle.SINGLE, size: 18, color: GREEN, space: 6 } },
  tabStops: [{ type: TabStopType.RIGHT, position: TW }],
  children: [new TextRun({ text: "[Journal Name] · working preprint", italics: true, font: FONT, size: 16, color: GREY }),
    new TextRun({ text: "\tOpen Access", bold: true, font: FONT, size: 16, color: GREEN })] });
const typeLabel = new Paragraph({ spacing: { before: 120, after: 40 }, children: [new TextRun({ text: "Article", bold: true, font: FONT, size: 24, color: GREEN })] });
const title = new Paragraph({ spacing: { after: 120 },
  children: [new TextRun({ text: "Can a Single Number Tell a Good Cascade Model from a Naive One? A Three-Axis Validation of a Global Supply-Chain Disruption Simulator on 27 Primary-Sourced Historical Events", bold: true, font: FONT, size: 32, color: DARK })] });
const authors = new Paragraph({ spacing: { after: 40 },
  children: [new TextRun({ text: "[Surname Given-name]", font: FONT, size: 22 }), new TextRun({ text: " 1,*", font: FONT, size: 22, superScript: true })] });
const affil = new Paragraph({ spacing: { after: 20 },
  children: [new TextRun({ text: "1", font: FONT, size: 16, superScript: true }), new TextRun({ text: "  [Institution], [City], [Country]", font: FONT, size: 16, color: GREY })] });
const corr = new Paragraph({ spacing: { after: 120 },
  children: [new TextRun({ text: "*", font: FONT, size: 16, superScript: true }), new TextRun({ text: "  Correspondence: mametaeverzat014@gmail.com", font: FONT, size: 16, color: GREY })] });
const ABSTRACT = "Global supply-chain disruptions — earthquakes, floods, canal blockages, financial crises — cascade across industries and countries, yet published simulation models are typically validated on one or two events and a single error metric. This work asks whether such validation can distinguish a substantive model from a naive baseline at all, and builds the infrastructure to answer it. We assemble a benchmark of 27 historical events (1999–2023, ten categories), each calibrated from primary sources under a written source-tier protocol, and a three-axis validation system scoring (1) global loss magnitude, (2) node-level cascade shape (peak, timing, recovery), and (3) spatial reach. Four models are tested: a novel SEIRS-bullwhip-hysteresis simulator (GEDS), a Leontief input–output model, linear network diffusion, and a naive mean predictor. On point magnitude no model significantly outperforms any other (all six pairwise permutation tests p ≥ 0.09 at N=27), and the result survives leave-one-out per-fold recalibration (p = 0.89): single-number validation cannot separate these models. A power analysis shows that at N=27 the minimum detectable effect (0.018 MAE) exceeds the real inter-model differences (~0.007), so the parity is resolution-limited rather than proven. Trajectory validation does separate the models: GEDS, the only model producing full trajectories, ranks recovery durations at Spearman 0.88 (95% CI 0.56–0.99) and peak timing at 0.69 (0.20–0.87). Replacing the hand-built 12-country graph with the 405-node OECD ICIO graph raises spatial reach from 0.29 to 0.79 with no parameter tuning. All results are deterministic, locked by golden tests, and reproducible from an open repository.";
const abstractBox = new Table({ columnWidths: [TW], width: { size: TW, type: WidthType.DXA },
  borders: { top: { style: BorderStyle.SINGLE, size: 4, color: BOXBD }, bottom: { style: BorderStyle.SINGLE, size: 4, color: BOXBD },
    left: { style: BorderStyle.SINGLE, size: 4, color: BOXBD }, right: { style: BorderStyle.SINGLE, size: 4, color: BOXBD }, insideHorizontal: NONE, insideVertical: NONE },
  rows: [new TableRow({ children: [new TableCell({ width: { size: TW, type: WidthType.DXA }, shading: { type: ShadingType.CLEAR, fill: BOXSH }, margins: { top: 100, bottom: 100, left: 140, right: 140 },
    children: [new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { line: 220 },
      children: [new TextRun({ text: "Abstract: ", bold: true, font: FONT, size: 18 }), ...runs(ABSTRACT, 18)] })] })] })] });
const keywords = new Paragraph({ spacing: { before: 80, after: 60 }, alignment: AlignmentType.JUSTIFIED,
  children: [new TextRun({ text: "Keywords: ", bold: true, font: FONT, size: 18 }),
    new TextRun({ text: "supply chains; shock propagation; model validation; SEIRS; bootstrap; permutation test; power analysis; OECD ICIO; cascade benchmark", font: FONT, size: 18 })] });
const HL = ["Single-number validation cannot rank four supply-chain cascade models at N=27 (all pairwise p ≥ 0.09).",
  "The null is quantified, not assumed: minimum detectable effect 0.018 MAE vs. real gaps ~0.007; ~166 events needed to resolve.",
  "Trajectory validation separates the models: recovery-duration ranking Spearman 0.88 (95% CI 0.56–0.99).",
  "Grounding the graph in OECD ICIO data lifts spatial reach 0.29 → 0.79 with zero parameter tuning."];
const highlightsBox = new Table({ columnWidths: [TW], width: { size: TW, type: WidthType.DXA },
  borders: { top: NONE, bottom: NONE, left: { style: BorderStyle.SINGLE, size: 18, color: GREEN }, right: NONE, insideHorizontal: NONE, insideVertical: NONE },
  rows: [new TableRow({ children: [new TableCell({ width: { size: TW, type: WidthType.DXA }, margins: { top: 60, bottom: 60, left: 160, right: 60 },
    children: [new Paragraph({ spacing: { after: 40 }, children: [new TextRun({ text: "Highlights", bold: true, font: FONT, size: 17, color: GREEN })] }),
      ...HL.map((h) => new Paragraph({ spacing: { line: 220, after: 20 }, indent: { left: 200, hanging: 160 }, children: runs("•  " + h, 16) }))] })] })] });
const metaBlock = new Paragraph({ spacing: { before: 40, after: 100 }, border: { left: { style: BorderStyle.SINGLE, size: 18, color: GREEN, space: 10 } }, indent: { left: 160 },
  children: [new TextRun({ text: "Type: working preprint (ISEF project).  ", font: FONT, size: 15, color: GREY }),
    new TextRun({ text: "Received / Accepted / Published: —.  ", font: FONT, size: 15, color: GREY }),
    new TextRun({ text: "Copyright: © 2026 the author(s). CC BY 4.0.  ", font: FONT, size: 15, color: GREY }),
    new TextRun({ text: "All numbers are generated from repository artifacts and reproducible under fixed seeds.", font: FONT, size: 15, color: GREY })] });
const front = [masthead, typeLabel, title, authors, affil, corr, abstractBox, keywords, highlightsBox, metaBlock];

// ===================== BODY =====================
const flow = [];
const col = (el) => flow.push({ full: false, el });
const full = (children) => flow.push({ full: true, children });

col(H1("1. Introduction"));
col(H2("1.1. Motivation"));
col(P("The 2021 blockage of the Suez Canal by the container ship Ever Given halted roughly 12% of world trade for six days; the 2011 Thai floods cut national vehicle output by 87.5% at their monthly peak; the 2020–2021 chip shortage cost the global auto industry 9.5 million unbuilt vehicles. Policymakers and firms need models that predict how a local shock will propagate across the global production network. The literature offers dozens of such models — yet almost every one is validated on one or two events, most often against a single scalar."));
col(P("This work began as building yet another model. It ended with a different conclusion: the standard way of validating such models cannot tell a complex model from a naive one, and so a validation instrument that can was built instead."));
col(H2("1.2. Research question"));
col(P("**Can single-number validation (peak loss magnitude) distinguish a substantive shock-propagation model from trivial baselines — and if not, which validation axes do separate the models?**"));
col(H2("1.3. Contributions"));
col(LI(1, "**Benchmark**: 27 historical disruption events (1999–2023) with calibration targets from primary sources under a written source-tier protocol, plus a library of 17+ documented near-misses as a negative control."));
col(LI(2, "**Three-axis validation system**: global magnitude (Track A), shocked-node trajectory shape (Track B), spatial reach and onset order."));
col(LI(3, "**Statistical layer**: event-level bootstrap, paired bootstrap with shared indices, sign-flip permutation tests, and a power analysis — every “better/worse” comes with a confidence interval and a p-value."));
col(LI(4, "**An honest headline result**: magnitude parity of all four models at N=27 (in- and out-of-sample, and this is a power limit, not equivalence) and significant separation on the trajectory axes, where only GEDS competes."));
col(LI(5, "**A mechanistic finding**: peak timing was at chance because the engine lacked a rising forcing shape; the defect was localized and the fix adopted through a pre-registered gated experiment."));

col(H1("2. Related Work and Positioning"));
col(P("The work sits at the intersection of four literatures; full references are in the References section."));
col(P("**Shock propagation in production networks.** The theoretical foundation was laid by Acemoglu et al. [1] on the network origins of aggregate fluctuations, with continuations on micro-origins and distortions (Acemoglu et al. [2]; Baqaee [3]; Bigio & La'O [4]). The empirical side was established by Carvalho et al. [5], who traced the Tōhoku earthquake cascade through real supplier chains, Barrot & Sauvagnat [6] via input specificity, and Boehm et al. [7]. Granularity as a source of aggregate fluctuations: Gabaix [8], di Giovanni & Levchenko [9], Oberfield et al. [10]. Our work adds no theory here — it uses this structure as a substrate and asks how well dynamic models on it predict real cascades."));
col(P("**Simulation and agent-based models.** Inoue & Todo [11] built a firm-level agent-based model of supply-chain propagation; Otto et al. [12] (Acclimate) model climate shocks on international trade. These are typically validated on a single event class; our contribution is orthogonal — a comparative-validation system in which such models can be placed side by side on a common benchmark."));
col(P("**Financial contagion.** Network propagation is well studied in finance: Allen & Gale [13], Gai & Kapadia [14], Battiston et al. [15], Elliott et al. [16], Haldane & May [17], Acemoglu et al. [20]. We borrow the threshold-cascade idea (a node enters “distress” when losses exceed an endogenous threshold) but apply it to production output."));
col(P("**Epidemic dynamics and forecast validation.** Transferring SEIR schemes to economics accelerated after COVID (Eichenbaum et al. [18]; Coquidé et al. [19]; Starnini et al. [21]). A separate relevant thread is comparative-validation methodology — forecasting competitions and temporal-graph benchmarks have repeatedly found simple methods indistinguishable from complex ones; our result reproduces this pattern in a new domain."));
col(P("**Niche.** To the best of our knowledge, no published work combines SEIRS dynamics, the bullwhip effect and hysteresis in one engine and, more importantly, validates a cascade model simultaneously on magnitude, trajectory shape and spatial reach across dozens of heterogeneous events with a full statistical layer. The gap this work closes is not “yet another model” but “how to compare such models honestly.”"));

col(H1("3. Data"));
col(H2("3.1. Event benchmark (N=27)"));
col(P("Each event specifies: the shocked node (country:industry or chokepoint), source-side shock magnitude, duration, forcing shape, horizon; and an observed target — the global/industry output loss from a primary source. The full list is Appendix A. Categories: earthquakes, floods, fires, lockdowns, energy crises, port congestion, chokepoint blockages, trade controls, strikes, financial crisis."));
col(P("**Source-tier protocol** (written): tier 1 — industry statistical agencies (OICA, JAMA, VDA, SIA) and official macro data (central banks, IMF, IMF PortWatch [26]); tier 2 — company filings; tier 3 (Reuters/Bloomberg/Nikkei) only when quoting tier 1/2. Rules: peak is distinguished from residual; derived numbers are tagged [DERIVED]; the node is assigned by where production occurred."));
col(P("**Negative control**: events without a clean primary number (Philips 2000 fire) or with structural graph gaps (Boeing 737 MAX) are documented as not-wired with the reason, not fitted. The base contains 17+ near-misses — events with little actual cascade: the model is penalized for false positives."));
col(H2("3.2. Trajectory targets and graph"));
col(P("For Track B we collect: peak output loss of the shocked sector in the source country (measured targets only, status “null” with a reason where no source exists); weeks-to-peak and weeks-to-90%-recovery; 62 rows of “event → affected node → onset week” each primary-sourced. Graph v2: 41 nodes (12 countries × 6 industries + 5 chokepoints), weights cross-checked against OECD ICIO [25] (Spearman 0.79–0.84). Graph v3: 405 nodes (81 economies × 5 sectors) directly from the ICIO 2019 tables."));

col(H1("4. Models"));
col(P("**GEDS (SEIRS-Bullwhip-Hysteresis)** — the proposed engine: each node moves through Susceptible → Exposed (an inventory buffer absorbs incoming shortfall) → Infected (output loss with nonlinear amplification) → Recovered (hysteresis). **Baselines** (zero fitted parameters): a Leontief input–output model, linear network diffusion, a naive mean predictor. The configuration is deterministic (stochastic_sigma = 0, seed = 0) and pinned by a golden test."));
col(H2("4.1. Formal engine specification"));
col(P("Let s_i(t) ∈ [0, 1] be the shock level of node i in week t and D_eff the effective-dependency matrix. The per-step update (vectorized over nodes). Incoming pressure with the bullwhip effect, where β_i = bullwhip factor (1.25 in state E):"));
col(EQ(1, "in_(i)(t) = ~β~_(i) · Σ_(j) D_(eff)[i,j] · s_(j)(t)"));
col(P("Impact impulse (δ — propagation decay, V — vulnerability, A — nonlinear amplification, ρ — resilience, the (1−s) factor giving saturation):"));
col(EQ(2, "Δ_(i)(t) = ~δ~ · in_(i)(t) · V_(i) · A_(i) · (1−~ρ~_(i)) · (1−s_(i)(t))"));
col(P("Weekly recovery rate tied to the node delay delay_i (8 weeks reference):"));
col(EQ(3, "~γ~_(i) = clip( recovery_rate · (8 / max(delay_(i), 0.5)), 0, 0.95 )"));
col(P("State transition, where x_i is the event's external forcing (shape step/linear/exp/ramp), r_i = γ_i·s_i for unforced nodes, ε — noise (ε ≡ 0 in the benchmark):"));
col(EQ(4, "s_(i)(t+1) = clip( max( x_(i)(t+1), s_(i)(t) + Δ_(i)(t) − r_(i)(t) + ~ε~_(i)(t) ), 0, 1 )"));
col(P("Observed node output loss (η — elasticity, f_i — the R-state hysteresis floor, ≥ 0.30 while recovering):"));
col(EQ(5, "L_(i)(t) = max( s_(i)(t) · ~η~_(i) · (1−~ρ~_(i)), f_(i)(t) )"));
col(P("Scalar cascade-severity index (c_i — node centrality, d_i — input exposure):"));
col(EQ(6, "CSI(t) = (1/N) · Σ_(i) s_(i)(t) · c_(i) · d_(i)"));
col(P("**SEIRS states.** A node moves S→E when incoming pressure crosses a trigger (an inventory buffer of depth inventory_scale absorbs the shortfall), E→I, I→R as the shock recedes; in R it holds for delay_i weeks with output floor f_i, then returns to S — this is the hysteresis. **Five calibrated parameters** θ = (amplification_mu, bullwhip_factor, recovery_rate, inventory_scale, distress_base); all other quantities are structural or fixed. Baselines formally: Leontief solves an (I−A)^{-1}-type loss equilibrium; linear diffusion iterates s(t+1)=s(t)+δ·(W·s(t)) with no saturation or recovery; the naive predictor returns the sample mean."));

col(H1("5. Validation Methods"));
col(H2("5.1. Three axes"));
col(BUL("**Track A (magnitude)**: predicted vs. observed global/industry loss, N=27; MAE, RMSE, Spearman."));
col(BUL("**Track B (shape)**: the shocked node's own trajectory: peak magnitude (n=5), weeks-to-peak (n=15), weeks-to-90%-recovery (n=11)."));
col(BUL("**Spatial**: the share of historically-hit nodes the cascade reaches (recall), and the rank correlation of onset order."));
col(H2("5.2. Statistical layer"));
col(P("At N=27 the question “is the difference significant?” comes first. All procedures are deterministic (seed 20260718) and resample whole events."));
col(BUL("**Bootstrap CIs** per metric: 10,000 resamples, percentile 95% intervals."));
col(BUL("**Paired bootstrap of differences**: shared resample indices for both models."));
col(P("**Sign-flip permutation test** for a pair (A, B) with per-event absolute errors e_A, e_B: statistic T = |mean(|e_A|−|e_B|)|; under H0 each difference's sign is flipped independently (20,000 permutations); two-sided p:"));
col(EQ(7, "p = (1 + #{ T* ≥ T }) / (20000 + 1)"));
col(P("**Power analysis / minimum detectable effect**: for paired differences d_i, the smallest mean MAE difference detectable at 80% power and α=0.05, and the N required for the observed difference:"));
col(EQ(8, "MDE = (z_(0.975) + z_(0.80)) · sd(d) / √N ,   N_(req) = ( 2.80 · sd(d) / |mean(d)| )^(2)"));
col(P("**Out-of-sample check**: leave-one-out cross-validation with per-fold differential-evolution recalibration of the five parameters — the held-out event never influences its own parameters; the baselines have no parameters."));
col(H2("5.3. Pre-registration of mechanism changes"));
col(P("Every engine change passes a pre-declared gate. Negative outcomes are preserved in the project record: inventory absorption, per-node recovery, hysteresis-floor removal — all three improved in-sample metrics and were rejected by the out-of-sample gate. The adopted change (ramp, §6.3) passed the same protocol."));

col(H1("6. Results"));
col(H2("6.1. Track A: magnitude parity"));
col(P("The four models at default parameters are in Table 1. Point estimates suggest a hierarchy, but none of the six pairwise MAE differences is significant (Figure 1): GEDS−Leontief ΔMAE +0.0074 [−0.0031; +0.0218], p=0.42; Leontief−naive −0.0040 [−0.0083; +0.0005], p=0.09; the rest p=0.21–0.97. **At N=27 single-number validation does not rank these models.** The only significant Track-A signals are rank-based: linear diffusion (0.72 [0.40; 0.91]) and GEDS (0.45 [0.06; 0.73])."));
full([CAP("Table 1. Four models at default parameters; MAE / RMSE / Spearman with 95% bootstrap CIs (N=27)."),
  table([3400, 2079, 2079, 2080], [
    ["Model", "MAE [95% CI]", "RMSE [95% CI]", "Spearman [95% CI]"],
    ["GEDS (SEIRS-b.-h.)", "0.0242 [0.011; 0.040]", "0.0464 [0.021; 0.067]", "0.45 [0.06; 0.73]"],
    ["Leontief", "0.0168 [0.008; 0.028]", "0.0313 [0.011; 0.046]", "0.34 [−0.10; 0.67]"],
    ["Linear diffusion", "0.0171 [0.009; 0.029]", "0.0317 [0.012; 0.049]", "0.72 [0.40; 0.91]"],
    ["Naive mean", "0.0208 [0.013; 0.031]", "0.0324 [0.014; 0.047]", "— (constant)"]])]);
full(figure("parity_forest.png", "Figure 1. Pairwise MAE differences (first minus second) with 95% paired-bootstrap CIs and two-sided permutation p. All six pairs cross zero."));
full(figure("pred_vs_obs.png", "Figure 2. Predicted vs. observed per model, N=27; the dashed line is perfect agreement."));
col(H2("6.2. Track B: the trajectory axes separate the models"));
col(P("Neither Leontief nor the naive mean produces trajectories; linear diffusion gives a curve with no recovery. Only GEDS produces the full “peak → decay → recovery” shape — and on these axes the result is significant (Table 2). Recovery-duration ranking (0.88) is the strongest result; both timing CIs exclude zero. The magnitude axis at n=5 is statistically empty and is stated only as a limitation."));
full([CAP("Table 2. Track B: node-level trajectory-shape axes (the only axes that only GEDS produces)."),
  table([3600, 900, 3138, 2000], [
    ["Axis", "n", "Spearman [95% CI]", "MAE"],
    ["Node peak magnitude", "5", "0.60 [−1.00; 1.00] — not claimed", "0.42"],
    ["Weeks to peak", "15", "0.69 [0.20; 0.87]", "7.1 wk"],
    ["Weeks to 90% recovery", "11", "0.88 [0.56; 0.99]", "8.5 wk"]])]);
col(P("**Robustness to single points (jackknife).** A leave-one-out test (drop each event and recompute Spearman) refutes the concern that a correlation rests on one point: for weeks-to-peak the full estimate is 0.691, LOO range [0.619; 0.790]; for recovery the full estimate is 0.883, LOO range [0.843; 0.917]. No single event drops the correlation below 0.62 and 0.84 respectively."));
col(H2("6.3. Mechanistic finding: why timing was at chance"));
col(P("Before this work weeks-to-peak scored Spearman 0.07 [−0.43; +0.53] — chance level. Forensics localized the cause: all three implemented forcing shapes (step, linear, exp) peak at onset, and the ratchet state update renders a declining forcing as a rectangular pulse — 12 of 15 predicted peaks fell on week 0. The engine lacked a “slowly rising shock” shape, which droughts, congestion and demand collapses require."));
col(P("The fix: a ramp shape (linear rise) was added and four events were moved to it **by real-world mechanism, declared before running**. The pre-registered four-criterion gate passed: weeks-to-peak Spearman 0.07 → 0.69; other axes drop 0.00; benchmark cost +0.0001 MAE; untouched events bit-identical (Figure 3)."));
full(figure("timing_ramp.png", "Figure 3. Weeks to peak: predicted vs. observed before (open) and after (filled) adopting the ramp shape; Spearman 0.07 → 0.69."));
col(H2("6.4. Out-of-sample check and power analysis"));
col(P("27-fold LOO with per-fold DE recalibration: MAE 0.0192, RMSE 0.0422, Pearson 0.25, Spearman 0.56, R² −0.70. Paired vs. Leontief: ΔMAE +0.0024 [−0.0073; +0.0167], p=0.89 — parity holds out-of-sample too. Two systematic misses are stated honestly: Chi-Chi 1999 (0.19 vs. 0.005 — the source node does not heal within the horizon) and the 2008–09 crisis (0.051 vs. 0.130 — a demand collapse is structurally unlike the supply cascades the engine models)."));
col(P("**Parity is a power limit, not a proven equivalence** (Table 3). At N=27 the minimum detectable effect for GEDS/Leontief is 0.0184, whereas the observed differences ~0.004–0.007 lie below resolution. Resolving the observed difference would require ≈166 events. This turns the null into a bounded, actionable statement and a target for the dataset."));
full([CAP("Table 3. Power analysis: minimum detectable effect at N=27 and the N required for the observed difference."),
  table([4238, 1800, 1800, 1800], [
    ["Pair", "obs. ΔMAE", "MDE at N=27", "N to detect"],
    ["GEDS vs Leontief", "+0.0074", "0.0184", "≈166"],
    ["GEDS vs linear diffusion", "+0.0071", "0.0149", "≈119"],
    ["Leontief vs naive", "−0.0040", "0.0064", "≈69"]])]);
col(H2("6.5. Spatial: network completeness, not tuning"));
col(P("Same engine, same shocks — only the graph changes (Table 4). The dense graph closes exactly the gaps the hand-built one could not express (the Renesas-fire cascade into foreign automotive: 0/4 → 3/4). Onset order on reached nodes ranks well (Spearman 0.79). No parameter changed: **the binding constraint is network completeness, not the fineness of the dynamics** (Figure 4)."));
full([CAP("Table 4. Cascade spatial reach: hand-built graph v2 vs. the ICIO graph v3."),
  table([3838, 2000, 3800], [
    ["Graph", "Nodes", "Spatial recall"],
    ["v2, hand-built", "36", "0.29 (10/35)"],
    ["v3, OECD ICIO 2019", "405", "0.79 (30/38)"]])]);
full(figure("spatial_recall.png", "Figure 4. Cascade spatial reach per event: share of historically-hit nodes reached on the hand-built graph v2 (open) and the ICIO graph v3 (filled)."));
col(H2("6.6. Component ablation: what of the complex model actually works"));
col(P("The standard question of a multi-component model is which parts carry weight. A component ablation (N=27, each component disabled in turn — Table 5) gives an uncomfortable but honest answer. Two components — the SEIS state machine and adaptive rerouting — contribute exactly zero on this set; the only component whose removal *hurts* is the bullwhip effect (+0.0023). Removing the R-state floor improves in-sample error (−0.0074), but that removal already failed the pre-registered out-of-sample gate (§5.3) and is rejected. Conclusion: at N=27 the engine's complexity largely does not pay off on the magnitude axis — consistent with §6.1 and pointing to growing N and the trajectory axes rather than adding mechanisms."));
full([CAP("Table 5. Component ablation of the engine (N=27): each component's contribution to MAE."),
  table([5638, 2000, 2000], [
    ["Variant", "MAE", "ΔMAE vs. full"],
    ["Full engine", "0.0242", "0"],
    ["−SEIS (no state machine)", "0.0242", "0.0000"],
    ["−adaptive rerouting", "0.0242", "0.0000"],
    ["−bullwhip (β = 1)", "0.0266", "+0.0023"],
    ["−R-state floor", "0.0169", "−0.0074"],
    ["+per-node recovery", "0.0233", "−0.0009"],
    ["pure linear diffusion", "0.0171", "−0.0071"]])]);
col(H2("6.7. Parameter sensitivity and identifiability"));
col(P("A variance-based Sobol sensitivity analysis (1536 engine runs, output mean_industry_loss_MAE — Table 6) asks whether the five parameters are identifiable; the ranking is stable across event-set size. Of the five, only one is truly identifiable — recovery_rate, carrying ~91% of output variance; inventory_scale acts only through interactions and two parameters are negligible and can be fixed. This independently corroborates §6.6 (the model is over-complex relative to what the N=27 data can constrain) and explains why per-fold recalibration (§6.4) so easily masks structural edits: almost all fitting freedom lives in one parameter. (MCMC at 350 steps did not converge, r̂=2.03; Bayesian intervals are left to a longer future run.)"));
full([CAP("Table 6. Sobol sensitivity indices: total effect ST and first-order S1 for the five parameters."),
  table([3238, 1600, 1600, 3200], [
    ["Parameter", "ST", "S1", "Reading"],
    ["recovery_rate", "0.913", "0.771", "dominates"],
    ["inventory_scale", "0.270", "≈0", "interactions only"],
    ["bullwhip_factor", "0.039", "≈0", "moderate"],
    ["amplification_mu", "0.005", "0.003", "negligible — can be fixed"],
    ["distress_base", "0.000", "0.000", "negligible — can be fixed"]])]);

col(H1("7. Discussion"));
col(P("Three results combine into one conclusion. (1) On the axis almost every paper reports — point magnitude — four fundamentally different models are statistically indistinguishable, and this is not an artifact of weak tuning: the parity survives per-fold recalibration and is quantitatively power-limited. (2) The axes that do separate the models are temporal and spatial: where only a full dynamic model can even compete, its results are significant (0.69 and 0.88). (3) The largest measured quality gain came not from dynamics but from network-structure data (recall 0.29 → 0.79, free in parameters)."));
col(P("Practical takeaway: cascade models should be validated by “predict the pattern, not one number,” or leaderboards compare noise. Methodological takeaway: pre-registering gates turns negative results into publishable assets."));
col(H1("8. Limitations"));
col(BUL("**N=27** for Track A and n=5/15/11 for Track B — power is limited; absence of significance is not equivalence (§6.4)."));
col(BUL("**The node-magnitude axis is empty** (n=5, CI [−1; 1]): monthly fab-output indices are seldom published."));
col(BUL("**Two structural misses** (Chi-Chi, the 2008–09 crisis) are described but not solved; three fix attempts were rejected by the out-of-sample gate."));
col(BUL("**Baselines are canonical rather than published implementations**: comparison against published cascade models [11,12] is the next step."));
col(BUL("**Graph completeness**: v2 omits several real producers; v3 (405 nodes) is not yet calibrated on magnitudes."));
col(H1("9. Reproducibility"));
col(P("The engine configuration is pinned (fixed seeds, stochasticity off); results are frozen by golden tests, and any numeric change is an explicit diff in the same commit. The statistical layer is deterministic (seed 20260718). The headline-numbers document and all figures are generated by scripts from artifacts; each figure ships with its numeric table. 157 automated tests. Exact commands are in Appendix B."));
col(H1("10. Conclusion and Future Work"));
col(P("The benchmark and three-axis validation give a way to tell cascade models apart in a statistically honest manner. Next: grow N via chokepoint events (IMF PortWatch transit data sidesteps the aggregate-dilution problem); calibrate magnitudes on the 405-node ICIO graph; a demand-side mechanism for 2008–09-type events; and releasing the benchmark as an open standard for third-party models."));
col(new Paragraph({ spacing: { before: 100, after: 40 }, children: [new TextRun({ text: "AI-use disclosure and acknowledgements", bold: true, font: FONT, size: 18, color: DARK })] }));
col(P("Engineering implementation, statistical processing and documentation drafting used an AI assistant (Claude Code, Anthropic) under the author's direction; problem framing, data-inclusion decisions, mechanism accept/reject calls at the gates, and the final text are the author's. All data come from open primary sources listed line-by-line in the repository CSVs.", { indent: false }));
col(new Paragraph({ spacing: { before: 100, after: 40 }, children: [new TextRun({ text: "Back matter", bold: true, font: FONT, size: 18, color: DARK })] }));
col(P("**Data and code availability.** All data, engine code, validation scripts and artifacts are open in the project repository; every calibration target carries a primary source. Numbers reproduce via the Appendix B commands.", { indent: false }));
col(P("**Author contributions.** [Complete per CRediT: conceptualization, methodology, software, validation, formal analysis, writing — original draft / review & editing, visualization.]", { indent: false }));
col(P("**Funding.** [This research received no external funding / state the grant.]", { indent: false }));
col(P("**Institutional review.** Not applicable (no human or animal subjects; only aggregate open economic data).", { indent: false }));
col(P("**Conflicts of interest.** The author(s) declare no conflict of interest.", { indent: false }));

col(H1("References"));
const REFS = [
  "Acemoglu, D.; Carvalho, V.M.; Ozdaglar, A.; Tahbaz-Salehi, A. The Network Origins of Aggregate Fluctuations. *Econometrica* 2012, 80, 1977–2016. doi:10.3982/ECTA9623.",
  "Acemoglu, D.; Ozdaglar, A.; Tahbaz-Salehi, A. Microeconomic Origins of Macroeconomic Tail Risks. *American Economic Review* 2017, 107, 54–108. doi:10.1257/aer.20151086.",
  "Baqaee, D.R. Cascading Failures in Production Networks. *Working Paper* 2016.",
  "Bigio, S.; La'O, J. Distortions in Production Networks. *Quarterly Journal of Economics* 2020, 135, 2187–2253. doi:10.1093/qjecon/qjaa002.",
  "Carvalho, V.M.; Nirei, M.; Saito, Y.U.; Tahbaz-Salehi, A. Supply Chain Disruptions: Evidence from the Great East Japan Earthquake. *Quarterly Journal of Economics* 2021, 136, 1255–1321. doi:10.1093/qje/qjaa044.",
  "Barrot, J.-N.; Sauvagnat, J. Input Specificity and the Propagation of Idiosyncratic Shocks in Production Networks. *Quarterly Journal of Economics* 2016, 131, 1543–1592. doi:10.1093/qje/qjw018.",
  "Boehm, C.E.; Flaaen, A.; Pandalai-Nayar, N. Input Linkages and the Transmission of Shocks: Firm-Level Evidence from the 2011 Tōhoku Earthquake. *Review of Economics and Statistics* 2019, 101, 60–75. doi:10.1162/rest_a_00750.",
  "Gabaix, X. The Granular Origins of Aggregate Fluctuations. *Econometrica* 2011, 79, 733–772. doi:10.3982/ECTA8769.",
  "di Giovanni, J.; Levchenko, A.A. Country Size, International Trade, and Aggregate Fluctuations in Granular Economies. *Journal of Political Economy* 2012, 120, 1083–1132. doi:10.1086/669161.",
  "Oberfield, E.; et al. Aggregate Fluctuations in Adaptive Production Networks. *PNAS* 2022, 119, e2203730119. doi:10.1073/pnas.2203730119.",
  "Inoue, H.; Todo, Y. Firm-Level Propagation of Shocks Through Supply-Chain Networks. *Nature Sustainability* 2019, 2, 841–847. doi:10.1038/s41893-019-0357-z.",
  "Otto, C.; Willner, S.N.; Wenz, L.; Frieler, K.; Levermann, A. Modeling Loss-Propagation in the Global Supply Network: The Dynamic Agent-Based Model Acclimate. *Journal of Economic Dynamics & Control* 2017, 83, 232–269. doi:10.1016/j.jedc.2017.08.001.",
  "Allen, F.; Gale, D. Financial Contagion. *Journal of Political Economy* 2000, 108, 1–33. doi:10.1086/262109.",
  "Gai, P.; Kapadia, S. Contagion in Financial Networks. *Proceedings of the Royal Society A* 2010, 466, 2401–2423. doi:10.1098/rspa.2009.0410.",
  "Battiston, S.; Delli Gatti, D.; Gallegati, M.; Greenwald, B.; Stiglitz, J.E. Liaisons Dangereuses: Increasing Connectivity, Risk Sharing, and Systemic Risk. *Journal of Economic Dynamics & Control* 2012, 36, 1121–1141. doi:10.1016/j.jedc.2012.04.001.",
  "Elliott, M.; Golub, B.; Jackson, M.O. Financial Networks and Contagion. *American Economic Review* 2014, 104, 3115–3153. doi:10.1257/aer.104.10.3115.",
  "Haldane, A.G.; May, R.M. Systemic Risk in Banking Ecosystems. *Nature* 2011, 469, 351–355. doi:10.1038/nature09659.",
  "Eichenbaum, M.S.; Rebelo, S.; Trabandt, M. The Macroeconomics of Epidemics. *Review of Financial Studies* 2021, 34, 5149–5187. doi:10.1093/rfs/hhab040.",
  "Coquidé, C.; Lages, J.; Shepelyansky, D.L. Crisis Contagion in the World Trade Network. *Applied Network Science* 2020, 5, 67. doi:10.1007/s41109-020-00304-z.",
  "Acemoglu, D.; Ozdaglar, A.; Tahbaz-Salehi, A. Systemic Risk and Stability in Financial Networks. *American Economic Review* 2015, 105, 564–608. doi:10.1257/aer.20130456.",
  "Starnini, M.; Boguñá, M.; Serrano, M.Á. Shock Propagation on Global Trade-Investment Multiplex Networks. *Scientific Reports* 2019, 9, 13079. doi:10.1038/s41598-019-49173-2.",
  "Hidalgo, C.A.; Hausmann, R. The Building Blocks of Economic Complexity. *PNAS* 2009, 106, 10570–10575. doi:10.1073/pnas.0900943106.",
  "Caliendo, L.; Parro, F.; Rossi-Hansberg, E.; Sarte, P.-D. The Impact of Regional and Sectoral Productivity Changes on the U.S. Economy. *Review of Economic Studies* 2018, 85, 2042–2096. doi:10.1093/restud/rdx082.",
  "Eaton, J.; Kortum, S. Technology, Geography, and Trade. *Econometrica* 2002, 70, 1741–1779. doi:10.1111/1468-0262.00352.",
  "OECD. Inter-Country Input-Output (ICIO) Tables, 2025 Edition (Year 2019); OECD: Paris, 2025.",
  "International Monetary Fund. PortWatch: Daily Chokepoint Transit Data; IMF: Washington, DC, 2021–2024.",
  "OICA; JAMA; VDA; SIA. Industry Motor-Vehicle and Semiconductor Production Statistics, 1999–2023.",
];
REFS.forEach((r, i) => col(REF(i + 1, r)));

col(H1("Appendix A. Full event benchmark (N=27)"));
col(P("Generated from seed_data.py; per-event primary sources are line-by-line in historical_events.csv. “Magn.” is the source-side shock magnitude (model input), “Target” is the observed loss (validation output).", { indent: false }));
const EVENTS = [
  ["1", "covid-semiconductor-2020-2021", "TWN:semiconductors", "0.30", "26", "0.115"],
  ["2", "suez-canal-2021", "CP:Suez", "0.90", "2", "0.008"],
  ["3", "auto-chip-shortage-2021", "TWN:semiconductors", "0.18", "30", "0.077"],
  ["4", "japan-triple-disaster-2011", "JPN:automotive", "0.40", "12", "0.039"],
  ["5", "us-china-tariffs-2019", "CHN:electronics", "0.12", "52", "0.020"],
  ["6", "texas-winter-storm-2021", "USA:semiconductors", "0.15", "6", "0.005"],
  ["7", "eu-energy-crisis-2021", "DEU:automotive", "0.08", "24", "0.015"],
  ["8", "malaysia-semiconductor-2021", "MYS:semiconductors", "0.30", "10", "0.012"],
  ["9", "thailand-floods-2011", "THA:automotive", "0.65", "10", "0.025"],
  ["10", "kumamoto-earthquake-2016", "JPN:semiconductors", "0.20", "6", "0.006"],
  ["11", "renesas-naka-fire-2021", "JPN:semiconductors", "0.28", "13", "0.016"],
  ["12", "japan-korea-export-controls-2019", "KOR:semiconductors", "0.06", "12", "0.002"],
  ["13", "vietnam-covid-lockdown-2021", "VNM:electronics", "0.30", "10", "0.012"],
  ["14", "shanghai-lockdown-2022", "CHN:automotive", "0.45", "8", "0.018"],
  ["15", "ukraine-war-harness-2022", "DEU:automotive", "0.16", "10", "0.012"],
  ["16", "china-power-crunch-2021", "CHN:electronics", "0.12", "6", "0.005"],
  ["17", "yantian-port-closure-2021", "CHN:shipping", "0.07", "4", "0.006"],
  ["18", "us-west-coast-ports-2021", "USA:shipping", "0.30", "20", "0.008"],
  ["19", "red-sea-crisis-2023", "CP:Suez", "0.55", "40", "0.010"],
  ["20", "taiwan-drought-2021", "TWN:semiconductors", "0.04", "16", "0.002"],
  ["21", "india-covid-wave-2021", "IND:automotive", "0.35", "6", "0.004"],
  ["22", "taiwan-chichi-earthquake-1999", "TWN:semiconductors", "0.90", "2", "0.005"],
  ["23", "hurricane-harvey-2017", "USA:consumer_goods", "0.07", "4", "0.002"],
  ["24", "us-west-coast-ports-2015", "USA:shipping", "0.06", "18", "0.007"],
  ["25", "korea-trucker-strikes-2022", "KOR:automotive", "0.50", "1", "0.002"],
  ["26", "panama-canal-drought-2023", "CP:Panama", "0.30", "30", "0.005"],
  ["27", "gfc-auto-collapse-2008-2009", "USA:automotive", "0.47", "39", "0.130"],
];
full([table([560, 3778, 2600, 900, 900, 900], [["#", "Event", "Node", "Magn.", "Dur.", "Target"], ...EVENTS])]);
col(H1("Appendix B. Reproducibility"));
col(P("All numbers in the paper regenerate from the repository:", { indent: false }));
col(CODE([
  "cd backend",
  "python -m scripts.significance_analysis   # significance.json (6.1, 6.2)",
  "python -m scripts.power_analysis          # power_analysis.json (6.4)",
  "python -m scripts.isef_figures            # 4 figures + CSVs",
  "python -m scripts.results_onepager        # docs/RESULTS.md",
  "python -c 'from app.core.ablation import run_ablation_study,save_ablation;",
  "          save_ablation(run_ablation_study())'   # ablation (6.6)",
  "python -c 'from app.core.sensitivity import run_sobol,save_sobol;",
  "          save_sobol(run_sobol())'   # Sobol (6.7)",
  "python -m pytest --ignore=tests/test_portwatch.py   # 157 tests",
]));

// ===================== ASSEMBLE =====================
const pageProps = { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } };
const footer = () => new Footer({ children: [new Paragraph({ border: { top: { style: BorderStyle.SINGLE, size: 6, color: GREEN, space: 6 } },
  tabStops: [{ type: TabStopType.RIGHT, position: TW }],
  children: [new TextRun({ text: "[Journal Name] 2026, working preprint", italics: true, font: FONT, size: 14, color: GREY }),
    new TextRun({ children: ["\tGEDS · ", PageNumber.CURRENT, " of ", PageNumber.TOTAL_PAGES], font: FONT, size: 14, color: GREY })] })] });
const sections = [{ properties: { ...pageProps, column: { count: 1 }, footers: { default: footer() } }, children: front }];
let buf = [];
const flushCol = () => { if (buf.length) { sections.push({ properties: { ...pageProps, type: SectionType.CONTINUOUS, column: { count: 2, space: 454, equalWidth: true }, footers: { default: footer() } }, children: buf }); buf = []; } };
for (const item of flow) {
  if (item.full) { flushCol(); sections.push({ properties: { ...pageProps, type: SectionType.CONTINUOUS, column: { count: 1 }, footers: { default: footer() } }, children: item.children }); }
  else buf.push(item.el);
}
flushCol();
const doc = new Document({ creator: "GEDS", title: "GEDS — three-axis validation (preprint)",
  styles: { default: { document: { run: { font: FONT, size: 19, color: DARK }, paragraph: { spacing: { line: 240 } } } } }, sections });
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(OUT, b); console.log("wrote", OUT, b.length, "bytes"); });
