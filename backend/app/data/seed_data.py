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
