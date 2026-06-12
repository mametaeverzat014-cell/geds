"""Seed data for the GEDS graph.

All numeric parameters are derived from real primary data sources (2019 baseline).
Derivation script: backend/data/processed.py
Full provenance:   backend/data/provenance.json
Raw API responses: backend/data/raw/

Node calibration:
  vulnerability / resilience — World Bank LPI 2018 (doi:10.1596/978-1-4648-1490-7)
    resilience_i = 0.20 + 0.60 × (LPI_i − 3.05) / 1.15  →  range [0.20, 0.80]
    vulnerability_i = 1.0 − resilience_i
  gdp_usd — World Bank GDP 2019 × OECD STAN sector share (2019 edition)
    Taiwan GDP: IMF WEO April 2020 ($611.4 B; World Bank excludes TWN)

Edge calibration:
  dependency_weight (TWN→semi edges) — UN Comtrade 2019 HS 8541+8542
    import penetration ratio × sector_exposure_factor (auto=0.55, elec=0.85, aero=0.65)
    CHN gets 1.35× multiplier for HK re-export routing and fabless dependency
  dependency_weight (automotive edges) — UN Comtrade 2019 HS 8703
    import penetration ratio: M_{importer,exporter,8703} / M_{importer,World,8703}
  dependency_weight (chokepoint links) — IEA/IMO literature exposure fractions
  flow_value_usd — UN Comtrade bilateral values, sector-allocated

Calibrated parameters (no direct empirical source):
  amplification [1.0–1.6], threshold [0.40–0.60], recovery_delay_weeks [2–18],
  substitution_difficulty [0.20–0.90], resilience_coefficient [0.10–0.32].
  Basis: provenance.json §parameters_not_from_real_data
"""

from __future__ import annotations

from ..core.types import Edge, EdgeKind, Industry, Node, NodeKind


# ──────────────────────────────── countries ────────────────────────────────
# gdp_t: World Bank GDP 2019 (current USD, trillions).
# TWN: IMF WEO April 2020. Source: backend/data/raw/wb_gdp_2019.json

COUNTRIES: dict[str, dict] = {
    "TWN": {"name": "Taiwan",         "lat": 23.7,  "lon": 121.0, "gdp_t": 0.611},
    "USA": {"name": "United States",  "lat": 37.0,  "lon": -95.7, "gdp_t": 21.381},
    "CHN": {"name": "China",          "lat": 35.0,  "lon": 104.0, "gdp_t": 14.560},
    "JPN": {"name": "Japan",          "lat": 36.2,  "lon": 138.3, "gdp_t": 5.118},
    "DEU": {"name": "Germany",        "lat": 51.2,  "lon": 10.4,  "gdp_t": 3.960},
    "KOR": {"name": "South Korea",    "lat": 35.9,  "lon": 127.8, "gdp_t": 1.751},
    "NLD": {"name": "Netherlands",    "lat": 52.1,  "lon": 5.3,   "gdp_t": 0.929},
    "VNM": {"name": "Vietnam",        "lat": 14.1,  "lon": 108.3, "gdp_t": 0.334},
    "MYS": {"name": "Malaysia",       "lat": 4.2,   "lon": 101.9, "gdp_t": 0.365},
    "THA": {"name": "Thailand",       "lat": 15.9,  "lon": 100.9, "gdp_t": 0.544},
    "IND": {"name": "India",          "lat": 20.6,  "lon": 78.9,  "gdp_t": 2.836},
    "MEX": {"name": "Mexico",         "lat": 23.6,  "lon": -102.5,"gdp_t": 1.304},
}


# ──────────────────────────────── nodes ────────────────────────────────────
# (country, industry, gdp_share, vulnerability, resilience, amplification, threshold)
#
# gdp_share: OECD STAN 2019 manufacturing value-added as fraction of national GDP.
#   Source: SECTOR_GDP_SHARE in backend/data/processed.py
#
# vulnerability = 1 − resilience_i (LPI-derived, backend/data/raw/wb_lpi_2018.json):
#   DEU=0.200 JPN=0.289 NLD=0.294 USA=0.362 CHN=0.508 KOR=0.508
#   TWN=0.539 THA=0.612 VNM=0.685 MYS=0.711 IND=0.732 MEX=0.800

NODE_SPECS: list[tuple[str, Industry, float, float, float, float, float]] = [
    # Taiwan — LPI=3.55 (est.) → resilience=0.461, vulnerability=0.539
    ("TWN", Industry.SEMICONDUCTORS, 0.152, 0.539, 0.461, 1.30, 0.40),
    ("TWN", Industry.ELECTRONICS,    0.080, 0.539, 0.461, 1.15, 0.45),
    ("TWN", Industry.SHIPPING,       0.008, 0.539, 0.461, 1.10, 0.50),

    # United States — LPI=3.89 → resilience=0.638, vulnerability=0.362
    ("USA", Industry.SEMICONDUCTORS, 0.008, 0.362, 0.638, 1.20, 0.55),
    ("USA", Industry.AUTOMOTIVE,     0.025, 0.362, 0.638, 1.20, 0.45),
    ("USA", Industry.ELECTRONICS,    0.015, 0.362, 0.638, 1.15, 0.50),
    ("USA", Industry.AEROSPACE,      0.012, 0.362, 0.638, 1.10, 0.55),
    ("USA", Industry.CONSUMER_GOODS, 0.045, 0.362, 0.638, 1.05, 0.55),
    ("USA", Industry.SHIPPING,       0.005, 0.362, 0.638, 1.05, 0.60),

    # China — LPI=3.61 → resilience=0.492, vulnerability=0.508
    ("CHN", Industry.SEMICONDUCTORS, 0.008, 0.508, 0.492, 1.20, 0.45),
    ("CHN", Industry.ELECTRONICS,    0.025, 0.508, 0.492, 1.25, 0.45),
    ("CHN", Industry.AUTOMOTIVE,     0.015, 0.508, 0.492, 1.15, 0.50),
    ("CHN", Industry.CONSUMER_GOODS, 0.065, 0.508, 0.492, 1.05, 0.55),
    ("CHN", Industry.SHIPPING,       0.012, 0.508, 0.492, 1.05, 0.55),

    # Japan — LPI=4.03 → resilience=0.711, vulnerability=0.289
    ("JPN", Industry.SEMICONDUCTORS, 0.010, 0.289, 0.711, 1.15, 0.50),
    ("JPN", Industry.AUTOMOTIVE,     0.030, 0.289, 0.711, 1.30, 0.40),
    ("JPN", Industry.ELECTRONICS,    0.020, 0.289, 0.711, 1.20, 0.45),

    # Germany — LPI=4.20 → resilience=0.800, vulnerability=0.200
    ("DEU", Industry.AUTOMOTIVE,     0.050, 0.200, 0.800, 1.40, 0.35),
    ("DEU", Industry.ELECTRONICS,    0.015, 0.200, 0.800, 1.15, 0.50),
    ("DEU", Industry.AEROSPACE,      0.008, 0.200, 0.800, 1.10, 0.55),

    # South Korea — LPI=3.61 → resilience=0.492, vulnerability=0.508
    ("KOR", Industry.SEMICONDUCTORS, 0.048, 0.508, 0.492, 1.25, 0.45),
    ("KOR", Industry.ELECTRONICS,    0.030, 0.508, 0.492, 1.20, 0.45),
    ("KOR", Industry.AUTOMOTIVE,     0.035, 0.508, 0.492, 1.20, 0.50),

    # Netherlands — LPI=4.02 → resilience=0.706, vulnerability=0.294
    # NLD semi GDP share (0.8%) reflects ASML equipment (HS 8486), not chip fabrication.
    ("NLD", Industry.SEMICONDUCTORS, 0.008, 0.294, 0.706, 1.10, 0.55),
    ("NLD", Industry.SHIPPING,       0.015, 0.294, 0.706, 1.05, 0.60),

    # Vietnam — LPI=3.27 → resilience=0.315, vulnerability=0.685
    ("VNM", Industry.ELECTRONICS,    0.200, 0.685, 0.315, 1.25, 0.45),
    ("VNM", Industry.CONSUMER_GOODS, 0.140, 0.685, 0.315, 1.10, 0.50),

    # Malaysia — LPI=3.22 → resilience=0.289, vulnerability=0.711
    ("MYS", Industry.SEMICONDUCTORS, 0.120, 0.711, 0.289, 1.15, 0.50),
    ("MYS", Industry.ELECTRONICS,    0.090, 0.711, 0.289, 1.20, 0.45),

    # Thailand — LPI=3.41 → resilience=0.388, vulnerability=0.612
    ("THA", Industry.AUTOMOTIVE,     0.080, 0.612, 0.388, 1.25, 0.40),
    ("THA", Industry.ELECTRONICS,    0.060, 0.612, 0.388, 1.15, 0.50),

    # India — LPI=3.18 → resilience=0.268, vulnerability=0.732
    ("IND", Industry.AUTOMOTIVE,     0.025, 0.732, 0.268, 1.15, 0.50),
    ("IND", Industry.ELECTRONICS,    0.015, 0.732, 0.268, 1.15, 0.50),
    ("IND", Industry.CONSUMER_GOODS, 0.055, 0.732, 0.268, 1.05, 0.55),

    # Mexico — LPI=3.05 → resilience=0.200, vulnerability=0.800
    ("MEX", Industry.AUTOMOTIVE,     0.060, 0.800, 0.200, 1.30, 0.40),
    ("MEX", Industry.ELECTRONICS,    0.025, 0.800, 0.200, 1.15, 0.45),
]


# ──────────────────────────────── chokepoints ────────────────────────────────
# vulnerability derived from IMO/Lloyd's annual disruption probability,
# scaled to GEDS [0.38, 0.65] range.  Source: provenance.json §imo_chokepoint_disruption_prob

CHOKEPOINTS: list[dict] = [
    # reroute_cost_multiplier: ratio of alternative-route cost to strait cost.
    # Sources:
    #   TaiwanStrait 1.15 — northern Pacific arc adds ~3 days; Lloyd's Route Risk 2022.
    #   Malacca      1.10 — Sunda Strait detour adds ~1 day; IMO Circular 2019.
    #   Suez         1.35 — Cape of Good Hope adds ~14 days, +$400-600k fuel; IEA Oil 2021.
    #   Hormuz       2.00 — no viable alternative; LNG/crude spot price spike modelled as 2×.
    {"id": "CP:TaiwanStrait", "name": "Taiwan Strait",    "lat": 24.0,  "lon": 119.5, "vulnerability": 0.60, "reroute_cost_multiplier": 1.15},
    {"id": "CP:Malacca",      "name": "Strait of Malacca","lat": 2.5,   "lon": 101.5, "vulnerability": 0.40, "reroute_cost_multiplier": 1.10},
    {"id": "CP:Suez",         "name": "Suez Canal",       "lat": 30.5,  "lon": 32.3,  "vulnerability": 0.50, "reroute_cost_multiplier": 1.35},
    {"id": "CP:Hormuz",       "name": "Strait of Hormuz", "lat": 26.6,  "lon": 56.3,  "vulnerability": 0.65, "reroute_cost_multiplier": 2.00},
    # Panama (added 2026-06 with the panama-drought-2023 event): ~5% of global
    # maritime trade, ~73% of canal traffic US-linked (IMF PortWatch note Nov
    # 2023). reroute_cost_multiplier 1.30 — alternatives are Suez/Cape routing
    # (+6–14 days) or US intermodal rail; McKinsey put sustained-restriction
    # cost at ~5% of total ocean-transport cost. Vulnerability between Malacca
    # and Suez: drought-prone (2023–24 El Niño cut transits ~50%).
    {"id": "CP:Panama",       "name": "Panama Canal",     "lat": 9.1,   "lon": -79.7, "vulnerability": 0.45, "reroute_cost_multiplier": 1.30},
]


# ──────────────────────────────── edges ────────────────────────────────────
# (source_id, target_id, dependency_weight, substitution_difficulty, rerouting_capability,
#  resilience_coefficient, recovery_delay_weeks, flow_b_usd)

def _n(country: str, industry: Industry) -> str:
    return f"{country}:{industry.value}"


EDGES_RAW: list[tuple[str, str, float, float, float, float, float, float]] = [
    # ── TWN semiconductors → downstream sectors ───────────────────────────
    # dependency_weight = penetration_ratio × sector_exposure_factor
    # Penetration ratios (TWN share of country's total semi imports, UN Comtrade 2019):
    #   JPN=0.432  CHN=0.310  THA=0.267  MYS=0.250  KOR=0.233
    #   VNM=0.145  DEU=0.131  USA=0.093  MEX=0.087  IND=0.043  NLD=0.015
    # sector_exposure_factor: auto=0.55, elec=0.85, aero=0.65
    # CHN gets ×1.35 (HK re-export routing + fabless dependence, see provenance.json)
    # flow_b_usd: bilateral semi import × sector allocation (elec≈65%, auto≈15%, aero≈8%)

    # Japan (penetration=0.432)
    (_n("TWN", Industry.SEMICONDUCTORS), _n("JPN", Industry.AUTOMOTIVE),     0.24, 0.80, 0.22, 0.22, 12,  1.5),
    (_n("TWN", Industry.SEMICONDUCTORS), _n("JPN", Industry.ELECTRONICS),    0.37, 0.80, 0.20, 0.20, 12,  6.6),

    # China (penetration=0.310, ×1.35 adj.)
    (_n("TWN", Industry.SEMICONDUCTORS), _n("CHN", Industry.ELECTRONICS),    0.36, 0.85, 0.20, 0.20, 12, 67.0),

    # Thailand (penetration=0.267)
    (_n("TWN", Industry.SEMICONDUCTORS), _n("THA", Industry.AUTOMOTIVE),     0.15, 0.85, 0.18, 0.18, 14,  0.5),
    (_n("TWN", Industry.SEMICONDUCTORS), _n("THA", Industry.ELECTRONICS),    0.23, 0.82, 0.20, 0.20, 14,  2.3),

    # Malaysia (penetration=0.250)
    (_n("TWN", Industry.SEMICONDUCTORS), _n("MYS", Industry.ELECTRONICS),    0.21, 0.82, 0.22, 0.22, 12,  5.7),

    # South Korea (penetration=0.233)
    (_n("TWN", Industry.SEMICONDUCTORS), _n("KOR", Industry.ELECTRONICS),    0.20, 0.75, 0.30, 0.25, 10,  6.2),

    # Vietnam (penetration=0.145)
    (_n("TWN", Industry.SEMICONDUCTORS), _n("VNM", Industry.ELECTRONICS),    0.12, 0.85, 0.20, 0.20, 12,  3.3),

    # Germany (penetration=0.131)
    (_n("TWN", Industry.SEMICONDUCTORS), _n("DEU", Industry.AUTOMOTIVE),     0.07, 0.85, 0.18, 0.20, 14,  0.5),
    (_n("TWN", Industry.SEMICONDUCTORS), _n("DEU", Industry.ELECTRONICS),    0.11, 0.85, 0.18, 0.18, 14,  2.0),

    # United States (penetration=0.093)
    (_n("TWN", Industry.SEMICONDUCTORS), _n("USA", Industry.AUTOMOTIVE),     0.05, 0.85, 0.18, 0.18, 14,  0.6),
    (_n("TWN", Industry.SEMICONDUCTORS), _n("USA", Industry.ELECTRONICS),    0.08, 0.90, 0.12, 0.15, 18,  2.7),
    (_n("TWN", Industry.SEMICONDUCTORS), _n("USA", Industry.AEROSPACE),      0.06, 0.85, 0.15, 0.20, 16,  0.3),

    # Mexico (penetration=0.087)
    (_n("TWN", Industry.SEMICONDUCTORS), _n("MEX", Industry.AUTOMOTIVE),     0.05, 0.88, 0.15, 0.15, 16,  0.3),
    (_n("TWN", Industry.SEMICONDUCTORS), _n("MEX", Industry.ELECTRONICS),    0.07, 0.82, 0.22, 0.22, 12,  1.4),

    # India (penetration=0.043)
    (_n("TWN", Industry.SEMICONDUCTORS), _n("IND", Industry.AUTOMOTIVE),     0.02, 0.80, 0.25, 0.22, 12,  0.04),
    (_n("TWN", Industry.SEMICONDUCTORS), _n("IND", Industry.ELECTRONICS),    0.04, 0.80, 0.25, 0.22, 12,  0.16),

    # ── Alternative semiconductor sources ─────────────────────────────────
    (_n("KOR", Industry.SEMICONDUCTORS), _n("USA", Industry.ELECTRONICS),    0.22, 0.55, 0.45, 0.30,  8, 12.0),
    (_n("KOR", Industry.SEMICONDUCTORS), _n("CHN", Industry.ELECTRONICS),    0.25, 0.55, 0.40, 0.30,  8, 15.0),
    (_n("KOR", Industry.SEMICONDUCTORS), _n("DEU", Industry.AUTOMOTIVE),     0.14, 0.55, 0.45, 0.30,  8,  4.0),
    (_n("USA", Industry.SEMICONDUCTORS), _n("USA", Industry.AUTOMOTIVE),     0.18, 0.50, 0.50, 0.32,  8,  6.0),
    (_n("USA", Industry.SEMICONDUCTORS), _n("USA", Industry.AEROSPACE),      0.35, 0.55, 0.45, 0.30, 10,  8.0),
    (_n("USA", Industry.SEMICONDUCTORS), _n("MEX", Industry.AUTOMOTIVE),     0.16, 0.50, 0.55, 0.30,  8,  4.0),
    (_n("JPN", Industry.SEMICONDUCTORS), _n("JPN", Industry.AUTOMOTIVE),     0.28, 0.55, 0.45, 0.30,  8,  9.0),
    (_n("JPN", Industry.SEMICONDUCTORS), _n("DEU", Industry.AUTOMOTIVE),     0.10, 0.55, 0.50, 0.32,  8,  3.0),
    (_n("CHN", Industry.SEMICONDUCTORS), _n("CHN", Industry.ELECTRONICS),    0.15, 0.55, 0.45, 0.32,  8, 10.0),
    # NLD = ASML EUV lithography equipment; sole supplier for <7nm nodes
    (_n("NLD", Industry.SEMICONDUCTORS), _n("TWN", Industry.SEMICONDUCTORS), 0.45, 0.92, 0.08, 0.10, 24,  4.0),
    (_n("NLD", Industry.SEMICONDUCTORS), _n("KOR", Industry.SEMICONDUCTORS), 0.40, 0.92, 0.10, 0.10, 24,  3.0),
    (_n("NLD", Industry.SEMICONDUCTORS), _n("USA", Industry.SEMICONDUCTORS), 0.30, 0.85, 0.18, 0.15, 18,  2.5),

    # ── Electronics → consumer goods ──────────────────────────────────────
    (_n("CHN", Industry.ELECTRONICS),    _n("USA", Industry.CONSUMER_GOODS), 0.45, 0.65, 0.30, 0.30, 10, 50.0),
    (_n("VNM", Industry.ELECTRONICS),    _n("USA", Industry.CONSUMER_GOODS), 0.18, 0.55, 0.40, 0.32,  8, 18.0),
    (_n("KOR", Industry.ELECTRONICS),    _n("USA", Industry.CONSUMER_GOODS), 0.15, 0.55, 0.45, 0.32,  8, 14.0),
    (_n("MYS", Industry.ELECTRONICS),    _n("USA", Industry.CONSUMER_GOODS), 0.10, 0.55, 0.45, 0.32,  8,  8.0),
    (_n("MEX", Industry.ELECTRONICS),    _n("USA", Industry.CONSUMER_GOODS), 0.12, 0.50, 0.50, 0.32,  8,  9.0),
    (_n("KOR", Industry.ELECTRONICS),    _n("DEU", Industry.AUTOMOTIVE),     0.18, 0.60, 0.40, 0.28, 10,  6.0),
    (_n("JPN", Industry.ELECTRONICS),    _n("USA", Industry.AUTOMOTIVE),     0.20, 0.60, 0.40, 0.28, 10,  8.0),

    # ── Automotive cross-border supply chains ─────────────────────────────
    # dependency_weight = M_{importer,exporter,8703} / M_{importer,World,8703}  (Comtrade 2019)
    (_n("MEX", Industry.AUTOMOTIVE),     _n("USA", Industry.AUTOMOTIVE),     0.212, 0.65, 0.35, 0.28, 10, 38.1),
    (_n("DEU", Industry.AUTOMOTIVE),     _n("USA", Industry.AUTOMOTIVE),     0.101, 0.50, 0.50, 0.30,  6, 18.1),
    (_n("JPN", Industry.AUTOMOTIVE),     _n("USA", Industry.AUTOMOTIVE),     0.222, 0.55, 0.45, 0.30,  8, 39.9),
    (_n("KOR", Industry.AUTOMOTIVE),     _n("USA", Industry.AUTOMOTIVE),     0.091, 0.50, 0.50, 0.30,  6, 16.3),
    # DEU:auto → JPN:auto: 45.1% (Germany supplies 45% of Japan's car imports; JPN market is small)
    (_n("DEU", Industry.AUTOMOTIVE),     _n("JPN", Industry.AUTOMOTIVE),     0.451, 0.60, 0.40, 0.28,  8,  5.5),
    # THA:auto → JPN:auto: calibrated (no bilateral Comtrade pair)
    (_n("THA", Industry.AUTOMOTIVE),     _n("JPN", Industry.AUTOMOTIVE),     0.15, 0.60, 0.45, 0.30,  8,  7.0),

    # ── Consumer goods downstream ──────────────────────────────────────────
    (_n("VNM", Industry.CONSUMER_GOODS), _n("USA", Industry.CONSUMER_GOODS), 0.14, 0.40, 0.55, 0.30,  6, 24.0),
    (_n("IND", Industry.CONSUMER_GOODS), _n("USA", Industry.CONSUMER_GOODS), 0.10, 0.40, 0.55, 0.30,  6, 12.0),
    (_n("CHN", Industry.CONSUMER_GOODS), _n("DEU", Industry.AUTOMOTIVE),     0.08, 0.45, 0.55, 0.30,  6,  6.0),

    # ── Shipping bottlenecks ───────────────────────────────────────────────
    (_n("TWN", Industry.SHIPPING),       _n("TWN", Industry.SEMICONDUCTORS), 0.50, 0.92, 0.08, 0.10, 16,  3.0),
    (_n("USA", Industry.SHIPPING),       _n("USA", Industry.CONSUMER_GOODS), 0.30, 0.55, 0.40, 0.30,  6, 25.0),
    (_n("CHN", Industry.SHIPPING),       _n("USA", Industry.CONSUMER_GOODS), 0.40, 0.65, 0.30, 0.25,  8, 35.0),
    (_n("NLD", Industry.SHIPPING),       _n("DEU", Industry.AUTOMOTIVE),     0.22, 0.60, 0.40, 0.30,  6, 14.0),

    # ── Intra-country sectoral feedback ───────────────────────────────────
    (_n("USA", Industry.AUTOMOTIVE),     _n("USA", Industry.CONSUMER_GOODS), 0.10, 0.40, 0.55, 0.30,  6, 10.0),
    (_n("DEU", Industry.AUTOMOTIVE),     _n("DEU", Industry.ELECTRONICS),    0.12, 0.40, 0.55, 0.30,  6,  4.0),
    (_n("CHN", Industry.ELECTRONICS),    _n("CHN", Industry.CONSUMER_GOODS), 0.18, 0.45, 0.50, 0.28,  6, 22.0),

    # ── MYS semiconductor packaging/assembly → automotive (added 2026-06) ──
    # Structural fix: MYS:semiconductors previously had ZERO outbound edges
    # (a sink), so the Malaysia-2021 lockdown event could not cascade at all
    # (LOO predicted exactly 0 vs observed 1.2% global auto loss).
    # Malaysia hosts ~13% of global semiconductor assembly/test (SIA 2021;
    # McKinsey 2021) with heavy auto-MCU packaging (Infineon Melaka, NXP and
    # STMicro Penang/Muar). dependency_weight = global ATP share (0.13) ×
    # auto sector_exposure_factor (0.55) ≈ 0.07, allocated conservatively
    # across the three largest auto producers; substitution is high because
    # assembly/test requalification takes months (same convention as TWN
    # semi edges above).
    (_n("MYS", Industry.SEMICONDUCTORS), _n("USA", Industry.AUTOMOTIVE),     0.06, 0.85, 0.18, 0.18, 12,  0.8),
    (_n("MYS", Industry.SEMICONDUCTORS), _n("DEU", Industry.AUTOMOTIVE),     0.06, 0.85, 0.18, 0.18, 12,  0.6),
    (_n("MYS", Industry.SEMICONDUCTORS), _n("JPN", Industry.AUTOMOTIVE),     0.05, 0.85, 0.18, 0.18, 12,  0.5),
]


# ──────────────────────────────── chokepoint links ────────────────────────────
# (chokepoint_id, target_node_id, dependency_weight)
# dependency_weight sourced from IEA/IMO exposure fractions (provenance.json §iea_chokepoint_exposure)

CHOKEPOINT_LINKS: list[tuple[str, str, float]] = [
    # Taiwan Strait: ~75-80% of Taiwan maritime exports transit the strait; rest air-freight
    ("CP:TaiwanStrait", _n("TWN", Industry.SEMICONDUCTORS), 0.75),
    ("CP:TaiwanStrait", _n("TWN", Industry.ELECTRONICS),    0.70),
    ("CP:TaiwanStrait", _n("KOR", Industry.ELECTRONICS),    0.15),
    ("CP:TaiwanStrait", _n("JPN", Industry.ELECTRONICS),    0.12),

    # Malacca: exposure fractions from IEA (CHN=0.38, VNM=0.30, THA=0.22, MYS=0.25)
    ("CP:Malacca",      _n("CHN", Industry.ELECTRONICS),    0.25),
    ("CP:Malacca",      _n("VNM", Industry.ELECTRONICS),    0.28),
    ("CP:Malacca",      _n("THA", Industry.AUTOMOTIVE),     0.18),
    ("CP:Malacca",      _n("MYS", Industry.ELECTRONICS),    0.20),

    # Suez: European imports from Asia and energy
    ("CP:Suez",         _n("DEU", Industry.AUTOMOTIVE),     0.20),
    ("CP:Suez",         _n("DEU", Industry.ELECTRONICS),    0.18),

    # Hormuz: energy price channel (JPN=0.87, CHN=0.44 energy exposure via Hormuz → indirect)
    ("CP:Hormuz",       _n("JPN", Industry.AUTOMOTIVE),     0.12),
    ("CP:Hormuz",       _n("CHN", Industry.ELECTRONICS),    0.08),

    # ── Chokepoint → shipping exposure (added 2026-06) ─────────────────────
    # Structural fix: shipping nodes previously had NO inbound edges at all,
    # so a Suez blockage predicted exactly zero shipping-industry impact
    # (Suez-2021 and Red-Sea-2023 events: LOO predicted 0.000 vs observed
    # 0.8–1.0%).
    #
    # Carriers — unlike cargo — keep operating through a blockage by taking
    # the longer alternative route, so the carrier's output loss is NOT its
    # traffic share through the strait. It is:
    #
    #   weight = traffic_share × (cost_c − 1) / cost_c
    #
    # where (cost_c − 1)/cost_c is the fraction of fleet capacity consumed by
    # the longer route (a voyage that costs 1.35× delivers 1/1.35 of the
    # throughput per ship-day). cost_c is the SAME literature-sourced
    # reroute_cost_multiplier already defined in CHOKEPOINTS above — no new
    # free parameter is introduced. Cross-check: Red Sea 2023–24 saw Suez
    # transits fall >50% while delivered global trade dipped only ~1–2%
    # (UNCTAD Feb 2024) — consistent with the ~26% capacity factor for Suez,
    # not with a naive 100% traffic-share loss.
    #
    # traffic_share sources: Suez→NLD 0.30 (Asia–Europe leg ≈ 30–40% of
    # Rotterdam throughput, UNCTAD 2024 / Port of Rotterdam 2023);
    # Suez→CHN 0.10 (Europe-bound ≈ 10–15% of China container exports,
    # UN Comtrade); Malacca→CHN 0.30, Malacca→TWN 0.15 (IEA Malacca
    # exposure, §iea_chokepoint_exposure); TaiwanStrait→TWN 0.70 (same
    # strait exposure as TWN semi/electronics above).
    #
    #   Suez (1.35):   NLD 0.30×0.26 = 0.08   CHN 0.10×0.26 = 0.03
    #   Malacca (1.10): CHN 0.30×0.09 = 0.03  TWN 0.15×0.09 = 0.015
    #   TaiwanStrait (1.15): TWN 0.70×0.13 = 0.09
    ("CP:Suez",         _n("NLD", Industry.SHIPPING),       0.08),
    ("CP:Suez",         _n("CHN", Industry.SHIPPING),       0.03),
    ("CP:Malacca",      _n("CHN", Industry.SHIPPING),       0.03),
    ("CP:Malacca",      _n("TWN", Industry.SHIPPING),       0.015),
    ("CP:TaiwanStrait", _n("TWN", Industry.SHIPPING),       0.09),

    # Panama (added 2026-06). Cargo side: ~12% of US containerized imports
    # transit the canal (BTS / IMF PortWatch 2023). Carrier side uses the same
    # capacity-factor convention as above: US-carrier traffic share via the
    # canal ≈ 0.16 × (0.30/1.30) ≈ 0.04.
    ("CP:Panama",       _n("USA", Industry.CONSUMER_GOODS), 0.12),
    ("CP:Panama",       _n("USA", Industry.SHIPPING),       0.04),
]


# ──────────────────────────────── historical events ────────────────────────────
# Validation targets for the simulation engine (core/validation.py).
# Observed magnitudes are public estimates over the N weeks following shock onset.
# Sources cited per event. Tolerances: ±25% (Phase 2 target), currently ±60%.

HISTORICAL_EVENTS: list[dict] = [
    {
        "slug": "covid-semiconductor-2020-2021",
        "name": "COVID semiconductor shortage (2020–21)",
        "shocks": [
            {"target_node_id": _n("TWN", Industry.SEMICONDUCTORS), "magnitude": 0.30,
             "start_week": 0, "duration_weeks": 26, "decay_curve": "exp"},
            {"target_node_id": _n("CHN", Industry.ELECTRONICS),    "magnitude": 0.45,
             "start_week": 0, "duration_weeks": 14, "decay_curve": "linear"},
        ],
        "horizon_weeks": 52,
        "observed": {
            "auto_production_loss_pct":   0.115,
            "peak_chip_lead_time_weeks":  26.0,
            "us_inflation_contribution":  0.025,
            "expected_recovery_weeks":    32.0,
            "most_impacted_industry":     Industry.AUTOMOTIVE.value,
        },
        "sources": ["SIA Global Semiconductor Sales 2021", "S&P Global Mobility vehicle production 2021",
                    "Federal Reserve FEDS Notes 2021-06"],
        "notes": "Shutdowns rippled through electronics, then autos. Primary cascade validator.",
    },
    {
        "slug": "suez-canal-2021",
        "name": "Suez Canal blockage (Mar 2021)",
        "shocks": [
            {"target_node_id": "CP:Suez", "magnitude": 0.90,
             "start_week": 0, "duration_weeks": 2, "decay_curve": "step"},
        ],
        "horizon_weeks": 16,
        "observed": {
            "global_trade_disruption_pct": 0.012,
            "auto_production_loss_pct":    0.008,
            "us_inflation_contribution":   0.0015,
            "expected_recovery_weeks":     6.0,
            "most_impacted_industry":      Industry.SHIPPING.value,
        },
        "sources": ["Suez Canal Authority 2021 Annual Report", "IMF Working Paper WP/21/179"],
        "notes": "Short sharp shock; 369 ships delayed, ~$9.6B/day trade impact.",
    },
    {
        "slug": "auto-chip-shortage-2021",
        "name": "Automotive chip shortage (2021)",
        "shocks": [
            {"target_node_id": _n("TWN", Industry.SEMICONDUCTORS), "magnitude": 0.18,
             "start_week": 0, "duration_weeks": 30, "decay_curve": "linear"},
        ],
        "horizon_weeks": 52,
        "observed": {
            "auto_production_loss_pct":   0.077,
            "peak_chip_lead_time_weeks":  21.0,
            "us_inflation_contribution":  0.012,
            "expected_recovery_weeks":    24.0,
            "most_impacted_industry":     Industry.AUTOMOTIVE.value,
        },
        "sources": ["S&P Global Mobility 2021", "AlixPartners Global Automotive Outlook 2021",
                    "FRB FEDS Notes 2021 — semiconductor shortage impact on autos"],
        "notes": "Validates sectoral cascade depth without full pandemic context.",
    },
    {
        "slug": "japan-triple-disaster-2011",
        "name": "Japan earthquake / tsunami / Fukushima (Mar 2011)",
        "shocks": [
            {"target_node_id": _n("JPN", Industry.AUTOMOTIVE),     "magnitude": 0.40,
             "start_week": 0, "duration_weeks": 12, "decay_curve": "exp"},
            {"target_node_id": _n("JPN", Industry.ELECTRONICS),    "magnitude": 0.30,
             "start_week": 0, "duration_weeks": 10, "decay_curve": "exp"},
            {"target_node_id": _n("JPN", Industry.SEMICONDUCTORS), "magnitude": 0.20,
             "start_week": 0, "duration_weeks": 8,  "decay_curve": "exp"},
        ],
        "horizon_weeks": 24,
        "observed": {
            "auto_production_loss_pct":  0.039,
            "us_inflation_contribution": 0.002,
            "expected_recovery_weeks":   16.0,
            "most_impacted_industry":    Industry.AUTOMOTIVE.value,
        },
        "sources": ["IHS Markit Automotive Q2 2011 report",
                    "Bank of Japan Quarterly Survey 2011 Q2",
                    "World Bank 2011 Disaster Assessment"],
        "notes": "M9.0 quake + Fukushima. Toyota/Honda ~80% production loss in Q2. "
                 "IHS estimates 3.9% global auto production loss in 2011.",
    },
    {
        "slug": "us-china-tariffs-2019",
        "name": "US–China tariff escalation, List 4A (Sep 2019)",
        "shocks": [
            {"target_node_id": _n("CHN", Industry.ELECTRONICS),    "magnitude": 0.12,
             "start_week": 0, "duration_weeks": 52, "decay_curve": "step"},
            {"target_node_id": _n("CHN", Industry.CONSUMER_GOODS), "magnitude": 0.15,
             "start_week": 0, "duration_weeks": 52, "decay_curve": "step"},
        ],
        "horizon_weeks": 52,
        "observed": {
            "auto_production_loss_pct":    0.020,
            "bilateral_trade_change_pct":  -0.15,
            "us_inflation_contribution":    0.005,
            "expected_recovery_weeks":     52.0,
            "most_impacted_industry":      Industry.CONSUMER_GOODS.value,
        },
        "sources": ["US Census Bureau Trade in Goods with China 2019–2020",
                    "Federal Reserve FEDS Note 2019-067",
                    "IMF World Economic Outlook Update Jan 2020"],
        "notes": "15% tariff on List 4A consumer electronics and apparel. "
                 "US-China bilateral trade fell ~15%. Diversion to VNM, MEX.",
    },
    {
        "slug": "texas-winter-storm-2021",
        "name": "Texas winter storm Uri — chip fab outages (Feb 2021)",
        "shocks": [
            {"target_node_id": _n("USA", Industry.SEMICONDUCTORS), "magnitude": 0.15,
             "start_week": 0, "duration_weeks": 6, "decay_curve": "step"},
        ],
        "horizon_weeks": 24,
        "observed": {
            "chip_fab_offline_weeks":    5.0,
            "auto_production_loss_pct": 0.005,
            "us_inflation_contribution": 0.001,
            "expected_recovery_weeks":  12.0,
            "most_impacted_industry":   Industry.AUTOMOTIVE.value,
        },
        "sources": ["IHS Markit Vehicle Production Tracking Feb–Mar 2021",
                    "NXP Semiconductors Q1 2021 earnings call",
                    "Samsung Austin fab press release Mar 2021"],
        "notes": "NXP Austin + Samsung Austin offline ~4–6 weeks. Primarily auto-grade MCUs. "
                 "~114K vehicle production units lost (IHS Markit direct attribution).",
    },
    {
        "slug": "eu-energy-crisis-2021",
        "name": "EU natural gas shortage (Sep 2021 – Feb 2022)",
        "shocks": [
            {"target_node_id": _n("DEU", Industry.AUTOMOTIVE),     "magnitude": 0.08,
             "start_week": 0, "duration_weeks": 24, "decay_curve": "linear"},
            {"target_node_id": _n("DEU", Industry.ELECTRONICS),    "magnitude": 0.06,
             "start_week": 0, "duration_weeks": 24, "decay_curve": "linear"},
            {"target_node_id": _n("NLD", Industry.SEMICONDUCTORS), "magnitude": 0.05,
             "start_week": 0, "duration_weeks": 20, "decay_curve": "linear"},
        ],
        "horizon_weeks": 36,
        "observed": {
            "auto_production_loss_pct":            0.015,
            "german_industrial_output_change_pct": -0.043,
            "eu_gas_price_multiplier":              4.0,
            "us_inflation_contribution":            0.003,
            "expected_recovery_weeks":             40.0,
            "most_impacted_industry":              Industry.AUTOMOTIVE.value,
        },
        "sources": ["Destatis Industrieproduktion Dec 2021",
                    "IEA Natural Gas Market Report Q4 2021",
                    "ECB Economic Bulletin 2022/01"],
        "notes": "TTF gas prices +400% by Oct 2021. German industrial output -4.3% (Destatis). "
                 "BASF reduced ammonia output by 40%. Worsened into 2022.",
    },
    {
        "slug": "malaysia-semiconductor-2021",
        "name": "Malaysia COVID lockdown — semiconductor assembly disruption (Aug–Oct 2021)",
        "shocks": [
            {"target_node_id": _n("MYS", Industry.SEMICONDUCTORS), "magnitude": 0.30,
             "start_week": 0, "duration_weeks": 10, "decay_curve": "step"},
            {"target_node_id": _n("MYS", Industry.ELECTRONICS),    "magnitude": 0.20,
             "start_week": 0, "duration_weeks": 8,  "decay_curve": "step"},
        ],
        "horizon_weeks": 20,
        "observed": {
            "auto_production_loss_pct":       0.012,
            "chip_lead_time_increase_weeks":  3.0,
            "us_inflation_contribution":      0.002,
            "expected_recovery_weeks":        12.0,
            "most_impacted_industry":         Industry.AUTOMOTIVE.value,
        },
        "sources": ["SIA Global Semiconductor Sales Forecast Q3 2021",
                    "McKinsey semiconductor shortage 2021 report",
                    "Malaysian Investment Development Authority"],
        "notes": "Malaysia hosts ~13% of global semiconductor packaging/assembly "
                 "(Infineon, STMicro, NXP Penang plants). COVID MCO lockdowns Aug 2021. "
                 "McKinsey estimated 500K–1M vehicles affected.",
    },

    # ── Expansion batch (2026-06) — events 9–21 ────────────────────────────
    # Added to address the N=8 sample-size limitation (AUDIT.md): with 8 events
    # the calibrated parameters are not identifiable and significance tests are
    # underpowered. Same authoring convention as events 1–8: shock magnitudes
    # describe the SOURCE-side capacity offline (from public reporting at the
    # time of the event), never derived from the observed targets. Observed
    # magnitudes are point estimates from the cited public sources.
    # The set deliberately includes "near-miss" events (japan-korea-export-
    # controls, taiwan-drought) where a feared disruption did NOT cascade, so
    # the benchmark also penalises false positives.
    {
        "slug": "thailand-floods-2011",
        "name": "Thailand floods — auto & HDD supply (Oct 2011 – Jan 2012)",
        "shocks": [
            {"target_node_id": _n("THA", Industry.AUTOMOTIVE),  "magnitude": 0.65,
             "start_week": 0, "duration_weeks": 10, "decay_curve": "exp"},
            {"target_node_id": _n("THA", Industry.ELECTRONICS), "magnitude": 0.45,
             "start_week": 0, "duration_weeks": 12, "decay_curve": "exp"},
        ],
        "horizon_weeks": 28,
        "observed": {
            "auto_production_loss_pct":  0.025,
            "us_inflation_contribution": 0.001,
            "expected_recovery_weeks":   24.0,
            "most_impacted_industry":    Industry.AUTOMOTIVE.value,
        },
        "sources": ["World Bank Thai Flood 2011 Rapid Assessment",
                    "IHS Automotive production tracking Q4 2011",
                    "Toyota/Honda Q4 FY2011 production releases"],
        "notes": "Chao Phraya basin floods submerged 7 industrial estates. Thai auto "
                 "assembly fell ~60–80% in Nov 2011; ~25% of global HDD capacity offline. "
                 "Toyota+Honda lost ~290K units incl. overseas knock-on.",
    },
    {
        "slug": "kumamoto-earthquake-2016",
        "name": "Kumamoto earthquakes — Kyushu supply base (Apr 2016)",
        "shocks": [
            {"target_node_id": _n("JPN", Industry.SEMICONDUCTORS), "magnitude": 0.20,
             "start_week": 0, "duration_weeks": 6, "decay_curve": "exp"},
            {"target_node_id": _n("JPN", Industry.AUTOMOTIVE),     "magnitude": 0.30,
             "start_week": 0, "duration_weeks": 4, "decay_curve": "exp"},
        ],
        "horizon_weeks": 16,
        "observed": {
            "auto_production_loss_pct":  0.006,
            "us_inflation_contribution": 0.0005,
            "expected_recovery_weeks":   8.0,
            "most_impacted_industry":    Industry.AUTOMOTIVE.value,
        },
        "sources": ["Toyota production suspension notices Apr 2016",
                    "Sony Kumamoto Technology Center recovery updates 2016",
                    "JAMA monthly production statistics 2016"],
        "notes": "M7.0 quake hit Aisin and Renesas/Sony plants in Kyushu. Toyota halted "
                 "most domestic lines ~1–2 weeks (JIT parts shortage). Sony image-sensor "
                 "fab down ~3 months but with buffer stock; global effect modest.",
    },
    {
        "slug": "renesas-naka-fire-2021",
        "name": "Renesas Naka fab fire — auto MCU supply (Mar 2021)",
        "shocks": [
            {"target_node_id": _n("JPN", Industry.SEMICONDUCTORS), "magnitude": 0.28,
             "start_week": 0, "duration_weeks": 13, "decay_curve": "linear"},
        ],
        "horizon_weeks": 26,
        "observed": {
            "auto_production_loss_pct":  0.016,
            "us_inflation_contribution": 0.001,
            "expected_recovery_weeks":   17.0,
            "most_impacted_industry":    Industry.AUTOMOTIVE.value,
        },
        "sources": ["Renesas Electronics press releases Mar–Jun 2021",
                    "IHS Markit auto production impact note Apr 2021"],
        "notes": "Fire in the N3 300mm line (~30% of Renesas auto MCU output). Shipments "
                 "back to pre-fire levels in ~100 days. IHS attributed ~1.4M vehicles of "
                 "Q2 2021 loss to the fire on top of the baseline chip shortage.",
    },
    {
        "slug": "japan-korea-export-controls-2019",
        "name": "Japan–Korea export controls on chip materials (Jul 2019)",
        "shocks": [
            {"target_node_id": _n("KOR", Industry.SEMICONDUCTORS), "magnitude": 0.06,
             "start_week": 0, "duration_weeks": 12, "decay_curve": "step"},
        ],
        "horizon_weeks": 24,
        "observed": {
            "auto_production_loss_pct":  0.002,
            "us_inflation_contribution": 0.0,
            "expected_recovery_weeks":   6.0,
            "most_impacted_industry":    Industry.ELECTRONICS.value,
        },
        "sources": ["METI export licensing notices Jul 2019",
                    "Samsung/SK Hynix Q3 2019 earnings calls",
                    "Bank of Korea Economic Bulletin Q4 2019"],
        "notes": "NEAR-MISS validator. Japan restricted photoresist/HF/fluorinated "
                 "polyimide exports to Korea. Feared DRAM/NAND disruption did not "
                 "materialise — inventories + expedited licensing kept fabs running.",
    },
    {
        "slug": "vietnam-covid-lockdown-2021",
        "name": "Vietnam COVID lockdowns — electronics & apparel (Jul–Oct 2021)",
        "shocks": [
            {"target_node_id": _n("VNM", Industry.ELECTRONICS),    "magnitude": 0.30,
             "start_week": 0, "duration_weeks": 10, "decay_curve": "step"},
            {"target_node_id": _n("VNM", Industry.CONSUMER_GOODS), "magnitude": 0.45,
             "start_week": 0, "duration_weeks": 12, "decay_curve": "step"},
        ],
        "horizon_weeks": 24,
        "observed": {
            "auto_production_loss_pct":  0.012,
            "us_inflation_contribution": 0.001,
            "expected_recovery_weeks":   16.0,
            "most_impacted_industry":    Industry.CONSUMER_GOODS.value,
        },
        "sources": ["Nike FY2022 Q1 earnings call (Sep 2021)",
                    "Vietnam GSO industrial production index Aug–Sep 2021",
                    "Samsung Vietnam operations statements 2021"],
        "notes": "Directive-16 lockdowns in HCMC/Binh Duong. Nike: ~50% of footwear "
                 "capacity offline for ~10 weeks. Samsung phone output curtailed. "
                 "Vietnam IIP fell ~7% y/y in Sep 2021.",
    },
    {
        "slug": "shanghai-lockdown-2022",
        "name": "Shanghai zero-COVID lockdown (Apr–May 2022)",
        "shocks": [
            {"target_node_id": _n("CHN", Industry.AUTOMOTIVE),  "magnitude": 0.45,
             "start_week": 0, "duration_weeks": 8, "decay_curve": "exp"},
            {"target_node_id": _n("CHN", Industry.ELECTRONICS), "magnitude": 0.25,
             "start_week": 0, "duration_weeks": 8, "decay_curve": "exp"},
            {"target_node_id": _n("CHN", Industry.SHIPPING),    "magnitude": 0.20,
             "start_week": 0, "duration_weeks": 9, "decay_curve": "step"},
        ],
        "horizon_weeks": 24,
        "observed": {
            "auto_production_loss_pct":  0.018,
            "us_inflation_contribution": 0.002,
            "expected_recovery_weeks":   12.0,
            "most_impacted_industry":    Industry.AUTOMOTIVE.value,
        },
        "sources": ["CAAM production statistics Apr–May 2022",
                    "CPCA retail/wholesale data Apr 2022",
                    "Drewry port congestion tracker Q2 2022"],
        "notes": "SAIC and Tesla Shanghai halted; China auto output -41% y/y in April. "
                 "Port of Shanghai operated under closed-loop with deep trucking "
                 "shortages; recovery was fast once the city reopened (Jun 2022).",
    },
    {
        "slug": "ukraine-war-harness-2022",
        "name": "Ukraine war — wire-harness shortage hits EU autos (Mar 2022)",
        "shocks": [
            {"target_node_id": _n("DEU", Industry.AUTOMOTIVE), "magnitude": 0.16,
             "start_week": 0, "duration_weeks": 10, "decay_curve": "exp"},
        ],
        "horizon_weeks": 28,
        "observed": {
            "auto_production_loss_pct":  0.012,
            "us_inflation_contribution": 0.002,
            "expected_recovery_weeks":   20.0,
            "most_impacted_industry":    Industry.AUTOMOTIVE.value,
        },
        "sources": ["ACEA EU production data H1 2022",
                    "S&P Global Mobility forecast cut Mar 2022 (−2.6M units)",
                    "VW/BMW production suspension notices Mar 2022"],
        "notes": "Leoni/Fujikura harness plants in western Ukraine stopped; VW Zwickau "
                 "and BMW lines halted within 2 weeks (JIT). Suppliers dual-sourced to "
                 "Romania/Tunisia/Mexico within ~2 months.",
    },
    {
        "slug": "china-power-crunch-2021",
        "name": "China dual-control power rationing (Sep–Oct 2021)",
        "shocks": [
            {"target_node_id": _n("CHN", Industry.ELECTRONICS),    "magnitude": 0.12,
             "start_week": 0, "duration_weeks": 6, "decay_curve": "step"},
            {"target_node_id": _n("CHN", Industry.CONSUMER_GOODS), "magnitude": 0.10,
             "start_week": 0, "duration_weeks": 6, "decay_curve": "step"},
        ],
        "horizon_weeks": 16,
        "observed": {
            "auto_production_loss_pct":  0.005,
            "us_inflation_contribution": 0.001,
            "expected_recovery_weeks":   8.0,
            "most_impacted_industry":    Industry.CONSUMER_GOODS.value,
        },
        "sources": ["NBS China industrial production Sep 2021",
                    "Goldman Sachs China note Sep 2021 (~44% of industry affected)",
                    "provincial Jiangsu/Guangdong rationing orders Sep 2021"],
        "notes": "Energy-intensity targets + coal price spike forced 2–3-day factory "
                 "weeks across Jiangsu, Zhejiang, Guangdong. Short, broad, shallow "
                 "shock; mostly recovered by Nov 2021.",
    },
    {
        "slug": "yantian-port-closure-2021",
        "name": "Yantian port COVID closure (May–Jun 2021)",
        "shocks": [
            # Node-level magnitude (convention fix 2026-06): the node is ALL
            # of China shipping, not the Yantian terminal. Yantian ≈ 10% of
            # China container exports; it ran at ~30% capacity ⇒ node-level
            # shock ≈ 0.10 × 0.70 = 0.07. The original 0.35 mistakenly used
            # the facility-level capacity loss.
            {"target_node_id": _n("CHN", Industry.SHIPPING), "magnitude": 0.07,
             "start_week": 0, "duration_weeks": 4, "decay_curve": "step"},
        ],
        "horizon_weeks": 12,
        "observed": {
            "auto_production_loss_pct":  0.006,
            "us_inflation_contribution": 0.0005,
            "expected_recovery_weeks":   6.0,
            "most_impacted_industry":    Industry.SHIPPING.value,
        },
        "sources": ["Maersk customer advisories Jun 2021",
                    "Drewry container capacity analysis Jun 2021"],
        "notes": "Yantian (≈10% of China container exports) ran at ~30% capacity for "
                 "~3.5 weeks; carriers omitted calls. Backlog cleared in ~6 weeks but "
                 "added to the 2021 container-rate spiral.",
    },
    {
        "slug": "us-west-coast-ports-2021",
        "name": "US West Coast port congestion (Aug 2021 – Feb 2022)",
        "shocks": [
            {"target_node_id": _n("USA", Industry.SHIPPING), "magnitude": 0.30,
             "start_week": 0, "duration_weeks": 20, "decay_curve": "linear"},
        ],
        "horizon_weeks": 36,
        "observed": {
            "auto_production_loss_pct":  0.008,
            "us_inflation_contribution": 0.004,
            "expected_recovery_weeks":   28.0,
            "most_impacted_industry":    Industry.CONSUMER_GOODS.value,
        },
        "sources": ["Marine Exchange of Southern California queue data 2021–22",
                    "NY Fed Global Supply Chain Pressure Index 2021–22",
                    "BLS CPI goods decomposition 2021"],
        "notes": "LA/Long Beach anchor queue peaked >100 ships (Jan 2022). Slow-moving "
                 "congestion shock: goods availability + freight costs fed into US "
                 "goods inflation more than into production loss.",
    },
    {
        "slug": "red-sea-crisis-2023",
        "name": "Red Sea attacks — Suez diversions (Dec 2023 – 2024)",
        "shocks": [
            # Magnitude AND duration are PortWatch-verified (2026-06): daily
            # Suez transit deficit peaked at 0.76, weekly at 0.55, and stayed
            # above 0.28 for 57+ weeks (still elevated at end of data) — so
            # the shock runs step-wise through the full study horizon rather
            # than the 26 weeks originally assumed. See
            # data/calibration/portwatch_validation.json.
            {"target_node_id": "CP:Suez", "magnitude": 0.55,
             "start_week": 0, "duration_weeks": 40, "decay_curve": "step"},
        ],
        "horizon_weeks": 40,
        "observed": {
            "auto_production_loss_pct":  0.010,
            "us_inflation_contribution": 0.001,
            "expected_recovery_weeks":   40.0,
            "most_impacted_industry":    Industry.SHIPPING.value,
        },
        "sources": ["IMF PortWatch Suez transit data 2024",
                    "UNCTAD Red Sea shipping note Feb 2024",
                    "Tesla Berlin / Volvo Gent suspension notices Jan 2024"],
        "notes": "Suez transits fell ~50–66%; Cape routing added ~10–14 days. Unlike "
                 "the 2021 blockage this was a long partial closure — rerouting worked, "
                 "so production impact stayed small relative to the headline severity.",
    },
    {
        "slug": "taiwan-drought-2021",
        "name": "Taiwan drought — fab water risk (Feb–Jun 2021)",
        "shocks": [
            {"target_node_id": _n("TWN", Industry.SEMICONDUCTORS), "magnitude": 0.04,
             "start_week": 0, "duration_weeks": 16, "decay_curve": "step"},
        ],
        "horizon_weeks": 28,
        "observed": {
            "auto_production_loss_pct":  0.002,
            "us_inflation_contribution": 0.0,
            "expected_recovery_weeks":   6.0,
            "most_impacted_industry":    Industry.SEMICONDUCTORS.value,
        },
        "sources": ["TSMC Q1–Q2 2021 earnings calls (water trucking costs)",
                    "Taiwan Water Resources Agency reservoir data 2021"],
        "notes": "NEAR-MISS validator. Worst drought in 56 years; reservoirs <5%. "
                 "Fabs trucked water and cut municipal allocation — no reported wafer "
                 "output loss. Tests that small persistent stress doesn't cascade.",
    },
    {
        "slug": "india-covid-wave-2021",
        "name": "India COVID second wave — auto shutdowns (Apr–Jun 2021)",
        "shocks": [
            {"target_node_id": _n("IND", Industry.AUTOMOTIVE),     "magnitude": 0.35,
             "start_week": 0, "duration_weeks": 6, "decay_curve": "exp"},
            {"target_node_id": _n("IND", Industry.CONSUMER_GOODS), "magnitude": 0.15,
             "start_week": 0, "duration_weeks": 6, "decay_curve": "exp"},
        ],
        "horizon_weeks": 16,
        "observed": {
            "auto_production_loss_pct":  0.004,
            "us_inflation_contribution": 0.0005,
            "expected_recovery_weeks":   10.0,
            "most_impacted_industry":    Industry.AUTOMOTIVE.value,
        },
        "sources": ["SIAM monthly production statistics Apr–Jun 2021",
                    "Maruti Suzuki plant maintenance advancement notice May 2021"],
        "notes": "Delta-wave lockdowns + industrial oxygen diverted to hospitals. "
                 "Indian auto output roughly halved for ~6 weeks; India ≈5% of global "
                 "production and weakly coupled, so the global cascade stayed small.",
    },

    # ── Expansion batch 2 (2026-06, events 22–26) ──────────────────────────
    # Researched via structured literature queries (raw findings with full
    # citations committed under data/raw/external/perplexity_events/). Same
    # authoring convention: source-side magnitudes from published reporting,
    # never derived from targets; derivations shown where a facility-level
    # figure had to be converted to node level. Six further researched events
    # (SARS 2003, Kobe 1995, Eyjafjallajökull 2010, UK fuel 2021, Germany
    # floods 2021, China Ga/Ge controls 2023) could not be mapped onto the
    # current 12-country × 6-industry graph and are recorded as out-of-graph
    # near-misses in data/csv/historical_events.csv instead.
    {
        "slug": "taiwan-chichi-earthquake-1999",
        "name": "Taiwan Chi-Chi earthquake — DRAM/foundry outage (Sep 1999)",
        "shocks": [
            # Near-total knockout of Taiwan fab output for ~1 week, ~85–90%
            # restored by day 8 (TSMC full power day 5; wafer output 20% day 5
            # → 90% day 8) ⇒ magnitude 0.90 with fast exponential decay.
            {"target_node_id": _n("TWN", Industry.SEMICONDUCTORS), "magnitude": 0.90,
             "start_week": 0, "duration_weeks": 2, "decay_curve": "exp"},
        ],
        "horizon_weeks": 12,
        "observed": {
            # "~15% of world RAM production lost, at least for a week" +
            # Taiwan Q4 PC output cut −7% ⇒ global electronics output loss
            # over the quarter ≈ 0.5% (derived; the feared sustained shortage
            # did NOT materialise — DRAM oversupply absorbed it).
            "auto_production_loss_pct":  0.005,
            "us_inflation_contribution": 0.0,
            "expected_recovery_weeks":   2.0,
            "most_impacted_industry":    Industry.ELECTRONICS.value,
        },
        "sources": ["Semico Research / Deseret News 1999", "Taipei Times 1999",
                    "EE Times 1999", "Semiconductor Digest 1999"],
        "notes": "NEAR-MISS validator. M7.6 quake knocked out 41% of Taiwan's power; "
                 "fabs got priority restoration and seismic design held. Brief DRAM "
                 "spot-price spike (~5× July), no sustained global chip shortage.",
    },
    {
        "slug": "hurricane-harvey-2017",
        "name": "Hurricane Harvey — US petrochemical complex (Aug 2017)",
        "shocks": [
            # Fed plant-level month-averaged national-output hit: petrochemicals
            # −8%, plastic resins −7.5% of August output (peak: ethylene >50%
            # offline ~1–2 weeks). Mapped to USA consumer goods as the resin-fed
            # node; fast restart ⇒ exponential decay.
            {"target_node_id": _n("USA", Industry.CONSUMER_GOODS), "magnitude": 0.075,
             "start_week": 0, "duration_weeks": 4, "decay_curve": "exp"},
        ],
        "horizon_weeks": 16,
        "observed": {
            # No published global downstream production loss (partial near-miss);
            # measured US drag: −0.65pp August IP growth, reversed by September.
            "auto_production_loss_pct":  0.002,
            "us_inflation_contribution": 0.001,
            "expected_recovery_weeks":   6.0,
            "most_impacted_industry":    Industry.AUTOMOTIVE.value,
        },
        "sources": ["Federal Reserve G.17 special note 2017", "White House CEA 2017",
                    "Chemistry World 2017", "US DOE/EIA 2017"],
        "notes": "PARTIAL NEAR-MISS. Sharp, well-measured source shock (refining "
                 "working capacity 76% on Aug 31 → 95% by Sep 28) absorbed by rapid "
                 "restart, resin inventories, imports and force-majeure rationing. "
                 "Gasoline drove ~3/4 of the +0.5% Sep CPI print (transitory).",
    },
    {
        "slug": "us-west-coast-ports-2015",
        "name": "US West Coast port slowdown — ILWU dispute (Oct 2014 – Feb 2015)",
        "shocks": [
            # Productivity slowdown, not closure: WC ports ≈ 43% of US container
            # trade; Q1-2015 exports via WC −20.5%, imports −9% ⇒ throughput-
            # weighted slowdown ~13–15% of WC volume ⇒ node-level shock
            # ≈ 0.43 × 0.14 ≈ 0.06, deepening toward the Feb settlement.
            {"target_node_id": _n("USA", Industry.SHIPPING), "magnitude": 0.06,
             "start_week": 0, "duration_weeks": 18, "decay_curve": "linear"},
        ],
        "horizon_weeks": 30,
        "observed": {
            # No global production-loss % published; measured US drag −0.2pp
            # Q1-2015 GDP (Fed IFDP). US ≈ 12% of global container traffic ⇒
            # global shipping output dip ≈ 0.7% at peak quarter (derived).
            "auto_production_loss_pct":  0.007,
            "us_inflation_contribution": 0.0,
            "expected_recovery_weeks":   20.0,
            "most_impacted_industry":    Industry.SHIPPING.value,
        },
        "sources": ["Federal Reserve IFDP Notes 2015", "WCIT 2015",
                    "Sumner et al., UC ARE / Lodi Growers 2015", "BTS port statistics"],
        "notes": "PARTIAL NEAR-MISS: feared full-shutdown ($2bn/day scenarios) never "
                 "happened. Absorbed by airfreight substitution and East/Gulf-coast "
                 "diversion. Recovery weeks not precisely published; congestion "
                 "cleared into spring 2015 (~20w estimate flagged as imprecise).",
    },
    {
        "slug": "korea-trucker-strikes-2022",
        "name": "South Korea trucker strikes (Jun + Nov–Dec 2022)",
        "shocks": [
            # June strike: Hyundai's Ulsan complex (largest plant) ran at ~50%
            # for ~1 week. November strike: "no reported impact on automotive
            # production" ⇒ only the June shock is modelled.
            {"target_node_id": _n("KOR", Industry.AUTOMOTIVE), "magnitude": 0.50,
             "start_week": 0, "duration_weeks": 1, "decay_curve": "step"},
        ],
        "horizon_weeks": 12,
        "observed": {
            # No published global figure; Korea ≈ 5% of global auto output,
            # halved for ~1 week ⇒ global quarterly dip ≈ 0.2% (derived).
            # Korea's trade ministry: ~$1.2bn shipment delays in week one
            # (≈2% of one month's exports) — delays, not lost output.
            "auto_production_loss_pct":  0.002,
            "us_inflation_contribution": 0.0,
            "expected_recovery_weeks":   2.0,
            "most_impacted_industry":    Industry.AUTOMOTIVE.value,
        },
        "sources": ["Reuters Jun/Nov 2022", "Flexport 2022", "CNBC 2022", "DW 2022"],
        "notes": "NEAR-MISS validator. Freight blockade (capacity intact): steel/cement "
                 "shipments collapsed domestically, chips insulated (fabs ship by air, "
                 "~2 weeks of materials on hand). Strikes ended abruptly; backlog "
                 "cleared in days. Feared global cascade never materialised.",
    },
    {
        "slug": "panama-canal-drought-2023",
        "name": "Panama Canal drought restrictions (Nov 2023 – Aug 2024)",
        "shocks": [
            # Press-reported transit counts (36–38/day → 18) suggest ~0.45–0.50,
            # but the MEASURED IMF PortWatch mean weekly transit deficit over the
            # restriction window is 0.28–0.30 (peak weeks deeper) — the published
            # counts overstate the throughput hit. Magnitude follows the
            # measurement: see data/calibration/portwatch_validation.json.
            {"target_node_id": "CP:Panama", "magnitude": 0.30,
             "start_week": 0, "duration_weeks": 30, "decay_curve": "step"},
        ],
        "horizon_weeks": 40,
        "observed": {
            # Canal ≈ 5% of global maritime trade; canal trade −32% (IMF,
            # Jan–Feb 2024) ⇒ global shipping output dip ≈ 0.5% (derived);
            # rerouting + booking priority kept container flows largely whole
            # (LNG/dry-bulk absorbed the cuts).
            "auto_production_loss_pct":  0.005,
            "us_inflation_contribution": 0.0,
            "expected_recovery_weeks":   26.0,
            "most_impacted_industry":    Industry.SHIPPING.value,
        },
        "sources": ["IMF PortWatch note Nov 2023", "UNCTAD 2024", "Project44 2025",
                    "Xeneta 2024", "McKinsey 2024"],
        "notes": "NEAR-MISS for downstream production, real shock for shipping. "
                 "Recovery 26w is published (peak restriction Feb 2024 → full "
                 "capacity Aug 2024). LNG transits never returned to trend — "
                 "structural shift to Cape routing.",
    },
]


# ──────────────────────────────── builders ────────────────────────────────────


def build_nodes() -> list[Node]:
    nodes: list[Node] = []

    for country, ind, gdp_share, vuln, res, amp, thresh in NODE_SPECS:
        c = COUNTRIES[country]
        gdp_b = c["gdp_t"] * 1000.0 * gdp_share
        nodes.append(
            Node(
                id=_n(country, ind),
                name=f"{c['name']} · {ind.value.replace('_', ' ').title()}",
                kind=NodeKind.COUNTRY_INDUSTRY,
                country=country,
                industry=ind,
                lat=c["lat"],
                lon=c["lon"],
                gdp_usd=gdp_b * 1e9,
                vulnerability=vuln,
                resilience=res,
                amplification=amp,
                threshold=thresh,
                recovery_delay_weeks=8.0,
                meta={"gdp_share_of_country": gdp_share},
            )
        )

    for cp in CHOKEPOINTS:
        vuln = cp["vulnerability"]
        nodes.append(
            Node(
                id=cp["id"],
                name=cp["name"],
                kind=NodeKind.CHOKEPOINT,
                lat=cp["lat"],
                lon=cp["lon"],
                gdp_usd=0.0,
                vulnerability=vuln,
                resilience=round(1.0 - vuln, 2),
                amplification=1.0,
                threshold=0.5,
                recovery_delay_weeks=4.0,
                inventory_weeks=0,  # chokepoints propagate immediately
                meta={"reroute_cost_multiplier": cp.get("reroute_cost_multiplier", 1.0)},
            )
        )

    return nodes


def build_edges() -> list[Edge]:
    edges: list[Edge] = []

    for src, tgt, dep, sub, route, res, recov, flow_b in EDGES_RAW:
        edges.append(
            Edge(
                source=src,
                target=tgt,
                kind=EdgeKind.PRODUCTION_INPUT,
                dependency_weight=dep,
                substitution_difficulty=sub,
                rerouting_capability=route,
                resilience_coefficient=res,
                recovery_delay_weeks=recov,
                flow_value_usd=flow_b * 1e9,
            )
        )

    for cp_id, tgt, dep in CHOKEPOINT_LINKS:
        edges.append(
            Edge(
                source=cp_id,
                target=tgt,
                kind=EdgeKind.ROUTES_THROUGH,
                dependency_weight=dep,
                substitution_difficulty=0.90,
                rerouting_capability=0.10,
                resilience_coefficient=0.10,
                recovery_delay_weeks=6.0,
                flow_value_usd=0.0,
            )
        )

    return edges
