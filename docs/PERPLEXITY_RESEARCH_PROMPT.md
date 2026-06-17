# Perplexity research prompt (event-database expansion loop)

This is the standing prompt used to research one candidate historical
disruption event at a time for `backend/app/data/seed_data.py`'s
`HISTORICAL_EVENTS` (Track A, the global LOO-backtest list) and the
node-level CSVs (Track B: `standardized_targets.csv`, `cascade_timing.csv`,
`cascade_spatial.csv`). Versioned here (not just pasted in chat) so it can be
diffed and recovered — v1/v2 were never saved to disk and had to be
reconstructed from memory once, which this file exists to prevent happening
again.

Workflow: copy the block below, fill in `CANDIDATE EVENT`, run it in
Perplexity, paste the full output back unedited. It gets audited against the
engine's actual validation architecture before anything is wired in — a
well-sourced event can still get rejected (see PRECEDENT below); that is the
expected, healthy outcome of Step 0, not a failure of the research.

---

## v3 prompt

```
ROLE: You are a research assistant gathering primary-sourced, quantitative data on
a historical economic disruption event, to calibrate a supply-chain disruption
simulator (GEDS). Precision and source quality matter more than completeness —
an honest "no clean source exists" is a valid and useful answer.

CANDIDATE EVENT: {{event name, approximate dates, and your best guess at the
primary shocked node — e.g. "Renesas Naka fire, March 2021, JPN:semiconductors"}}

============================================================
STEP 0 — TARGET VIABILITY PRE-CHECK (do this FIRST, before researching)
============================================================

The simulator graph has exactly 41 nodes: a country paired with one of 6 populated
industries. NOT every country x industry combination exists. The valid node list is:

  CHN: automotive, consumer_goods, electronics, semiconductors, shipping
  DEU: aerospace, automotive, electronics
  IND: automotive, consumer_goods, electronics
  JPN: automotive, electronics, semiconductors
  KOR: automotive, electronics, semiconductors
  MEX: automotive, electronics
  MYS: electronics, semiconductors
  NLD: semiconductors, shipping
  THA: automotive, electronics
  TWN: electronics, semiconductors, shipping
  USA: aerospace, automotive, consumer_goods, electronics, semiconductors, shipping
  VNM: consumer_goods, electronics
  Chokepoints (separate category, see (d) below): CP:Hormuz, CP:Malacca, CP:Panama,
  CP:Suez, CP:TaiwanStrait

If the event's shocked entity does not map cleanly onto one of these 41 nodes,
say so explicitly and STOP — do not force a mapping onto the nearest available
node (this has caused real errors before: a factory got mis-mapped to the wrong
country because no node existed for its actual country).

(a) GDP-share triage — is this node's signal big enough to matter?
Each industry node's GDP share of its OWN industry total in the graph (this is
NOT global market share — it's share within our 41-node world; total industry
size in USD shown for scale):

  consumer_goods ($2111B): USA 45.6%, CHN 44.8%, IND 7.4%, VNM 2.2%
  automotive     ($1358B): USA 39.3%, CHN 16.1%, DEU 14.6%, JPN 11.3%, MEX 5.8%,
                           IND 5.2%, KOR 4.5%, THA 3.2%
  electronics    ($1155B): CHN 31.5%, USA 27.8%, JPN 8.9%, VNM 5.8%, DEU 5.1%,
                           KOR 4.5%, TWN 4.2%, IND 3.7%, MYS 2.8%, THA 2.8%, MEX 2.8%
  semiconductors ($567B):  USA 30.2%, CHN 20.5%, TWN 16.4%, KOR 14.8%, JPN 9.0%,
                           MYS 7.7%, NLD 1.3%
  shipping       ($300B):  CHN 58.2%, USA 35.6%, NLD 4.6%, TWN 1.6%
  aerospace      ($288B):  USA 89.0%, DEU 11.0%

  GOOD target  (>=10% share): proceed with confidence.
  CAUTION      (5-10% share): proceed, but flag that even a real shock may be
               hard to distinguish from noise in the global aggregate.
  AVOID        (<5% share, e.g. NLD:semiconductors at 1.3%): a real, well-sourced
               shock at this node will still read as near-zero against any
               global/industry-wide baseline. Don't spend a research cycle here
               unless the event is ALSO a chokepoint event or has an unusually
               clean node-level-only source.

(b) Missing-competitor structural trap — is the in-graph share even meaningful?
A node's in-graph share can be misleadingly high if a real-world competitor is
simply absent from the graph. Known case: aerospace shows USA at 89%, but
France/Airbus has no node — so USA's TRUE global commercial-aircraft share is
roughly 45-50%, not 89%. Any aerospace event involving competitive substitution
(customers switching from the shocked producer to a rival) will be invisible to
the model and the magnitude will look artificially total. Before proceeding,
ask: "is there a major real-world producer in this industry that this graph has
no node for?" If yes, flag it explicitly even if the share number looks good.

(c) The share table is a TRIAGE heuristic, not a substitute for checking sources.
A high-share node with NO genuine tier-1/tier-2 global industry-wide percentage
is still a dead end (see Source Tiers below) — Track A needs an actual published
number, not just a plausible node.

(d) Chokepoint events bypass (a) and (b) entirely. CP:Hormuz, CP:Malacca,
CP:Panama, CP:Suez, CP:TaiwanStrait are scored against measured transit/
throughput data (e.g. IMF PortWatch daily transit deficits), not GDP-weighted
industry share — there is no dilution problem. If you don't have a strong
industry-event candidate in mind, a chokepoint disruption (canal blockage,
strait closure/tension, port congestion) is the highest-yield category to
research by default. The viability question for these is simply: "does
PortWatch (or an equivalent AIS-based transit-volume source) cover this
chokepoint for this date range?"

PRECEDENT (for calibration — what a Step 0 verdict should look like):
  - Boeing 737 MAX grounding (2019-20): mapped to USA:aerospace, 89% share —
    looked great on share alone, but aerospace is missing France/Airbus
    (missing-competitor trap, see (b)) AND no tier-1 global commercial-aircraft
    production index exists. BLOCKED at Step 0 reasoning, confirmed in Step 1.
  - Philips Albuquerque fire (2000): mapped to USA:electronics — no tier-1
    global semiconductor-output index existed for this date, and the only
    number found was a 6-month residual mistaken for the 3-week peak. BLOCKED.
  - GFC automotive collapse (2008-09): USA:automotive, 39.3% share, OICA -13.1%
    YoY global figure + Fed G.17 SAAR data, both tier 1. CLEARED -> wired in as
    event #27.

VERDICT: before doing Step 1, write 2-4 sentences: which node, what share tier,
any missing-competitor flag, and whether you can already tell this will lack a
Track A global figure. If this event looks like a dead end, say so plainly and
stop — a clear "this won't work because X" is more valuable than a half-
researched event that gets rejected later.

============================================================
STEP 1 — FULL RESEARCH (only if Step 0 passes, or you're told to proceed anyway)
============================================================

SOURCE TIERS (cite tier explicitly for every number):
  Tier 1 (preferred): industry statistical bodies (OICA, JAMA, VDA, SIA, SEMI,
    S&P Global Mobility/IHS Markit) and macro/official bodies (central banks,
    IMF, World Bank, OECD, national statistics agencies).
  Tier 2: company filings, investor calls, official press releases.
  Tier 3 (only when directly quoting/citing a tier 1 or 2 source — never as a
    standalone source for a headline number): Reuters, Bloomberg, Nikkei, WSJ, FT.
  BANNED for any headline number: Wikipedia, blogs, Studocu/Scribd/Course Hero
  and other aggregators/student-paper sites. They may appear only as a pointer
  to where a primary source might exist, never as the citation itself.

RULES:
  - PEAK vs RESIDUAL: every magnitude must say explicitly whether it is the PEAK
    value during the disruption, or a later, still-recovering RESIDUAL value.
    Always report the peak for the magnitude fields below. A 6-months-later
    "still down 50%" is not the same as a 3-week peak of "down ~100%" —
    conflating these has caused real errors before.
  - [DERIVED]: if a number is not stated directly by a source but computed by you
    via arithmetic from numbers that are (e.g. (X-Y)/X from two raw cited
    figures), tag it [DERIVED] and show the formula and the raw inputs.
  - decay_curve consistency: if weeks_to_peak >= 2, the shock ramps up rather
    than hitting instantly — say so explicitly (this maps to decay_curve=linear
    in the engine, vs step/exp which assume peak at week 0).
  - Node mapping must follow WHERE PRODUCTION ACTUALLY OCCURRED, never company
    headquarters or nationality.

REPORT IN THIS FORMAT:

PRIMARY SHOCK NODE(S): <one or more of the 41 valid nodes>

TRACK A — GLOBAL MAGNITUDE (industry-wide, not just the node):
  value: <% change, PEAK>, tier: <1/2/3>, source: <full citation>
  (if genuinely unavailable, say "not available" — do not approximate)

TRACK B — NODE-LEVEL (the node's own trajectory):
  magnitude: <% peak output loss at this specific node>, source + tier
  weeks_to_peak: <int>, source + tier
  recovery_weeks: <weeks to return to ~90% of pre-shock baseline>, source + tier

TIMING: <short prose: onset date, peak date, recovery date>

DOWNSTREAM SPATIAL CASCADE (one row per other affected node you can source):
  | node | onset_week (relative to shock start) | effect | magnitude_hint | source_url |

loss_usd_billions: <total estimated economic loss, with source>

SOURCES: <numbered list, full citations, tier marked for each>

METADATA:
  track: <NODE_LEVEL | GLOBAL_AND_NODE>
  usability: <CALIBRATION_GRADE | NATIONAL_PROXY | NOT_USABLE>
  confidence: <high | medium | low>
  derived_flags: <list any [DERIVED] numbers used above>
  notes: <anything that affects whether this is engine-ready: missing
    competitors, mapping ambiguity, conflicting sources, etc.>
```

---

## v2 -> v3 changelog (2026-06-17)

v2 had no machine-checkable target-selection step: Step 1's research template
(source tiers, peak/residual, `[DERIVED]` tagging, decay-curve consistency,
node-mapping integrity) was sound, but nothing stopped a research cycle from
being spent on a node that was always going to fail the audit. Two out of the
three events run through v2 (Philips Albuquerque 2000, Boeing 737 MAX 2019-20)
were fully researched, well-sourced, and still blocked — only the GFC
automotive collapse cleared and became event #27.

v3 adds Step 0, a pre-check derived from the actual GDP shares in the live
12-country graph (`compile_graph(load_graph())`, recomputed and verified
2026-06-17 — see the table above): a triage heuristic for whether a node's
signal can even be visible against a global/industry aggregate (a), an
explicit named trap for industries missing a real-world competitor node (b),
an explicit reminder that share is not a substitute for a real tier-1 source
existing (c), and a callout that chokepoint events sidestep the whole problem
by construction (d). The PRECEDENT block exists so the model calibrates
against the real Philips/Boeing/GFC outcomes instead of guessing what "good"
looks like.

The architecture fact this all rests on: there is no way to wire an event
into Track B only. `backtest_event()` and the LOO cross-validators
unconditionally iterate the full `HISTORICAL_EVENTS` list, so anything added
there is automatically scored on Track A too — an event without a genuine
global figure cannot be partially adopted. The fallback for a well-researched
event that fails Step 0 (or fails Step 1 despite passing Step 0) is a fully
documented `in_geds_graph=no` row in `backend/data/csv/historical_events.csv`,
not silent deletion — see the Philips and Boeing rows for the format.
