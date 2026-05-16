"""Derived parameter computation from real data sources.

This module is the single source of truth for how every numeric parameter
in seed_data.py is derived from raw API data. Run this script to verify
all derivations. The computed values are then hard-coded into seed_data.py
for reproducibility (no runtime dependency on raw files being present).

Scientific basis:
  dependency_weight = import_penetration_ratio (Feenstra & Taylor 2014, Ch.5)
  resilience        = scaled World Bank Logistics Performance Index (LPI 2018)
  vulnerability     = 1 - resilience
  gdp_usd           = World Bank GDP 2019 × OECD STAN sector share

All data provenance documented in: data/provenance.json
Raw API responses archived in: data/raw/
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# 1.  RAW DATA (verbatim from API responses in data/raw/)
# ─────────────────────────────────────────────────────────────────────────────

# UN Comtrade 2019 — HS 8541 + HS 8542 combined (USD)
# Source: data/raw/comtrade_semi_2019.json
# Quality: real (import-side, CIF values)

_SEMI_FROM_TWN_8541 = {      # M_{X,TWN,8541}
    "CHN": 3_846_524_175, "DEU": 285_613_823, "JPN": 281_134_751,
    "KOR": 846_038_336,   "USA": 425_021_273, "MYS": 230_323_719,
    "MEX": 107_176_360,   "NLD": 39_767_827,  "VNM": 154_049_223,
    "THA": 79_083_019,    "IND": 75_000_000,   # IND: estimated
}
_SEMI_FROM_TWN_8542 = {      # M_{X,TWN,8542}
    "CHN": 99_297_226_729, "DEU": 2_832_135_807, "JPN": 9_860_791_946,
    "KOR": 8_625_529_643,  "USA": 3_701_644_149, "MYS": 8_497_634_851,
    "MEX": 2_042_175_815,  "NLD": 201_035_905,   "VNM": 4_939_126_009,
    "THA": 3_429_520_178,  "IND": 175_000_000,   # IND: estimated
}
_SEMI_TOTAL_8541 = {         # M_{X,World,8541}
    "CHN": 26_162_410_250, "DEU": 6_795_538_479, "JPN": 4_956_086_616,
    "KOR": 5_001_671_323,  "USA": 11_317_425_792, "MYS": 3_038_525_234,
    "MEX": 3_267_081_322,  "NLD": 2_754_230_728,  "VNM": 4_556_232_254,
    "THA": 1_881_641_459,  "IND": 1_200_000_000,  # IND: estimated
}
_SEMI_TOTAL_8542 = {         # M_{X,World,8542}
    "CHN": 306_396_731_089, "DEU": 17_006_249_402, "JPN": 18_511_107_877,
    "KOR": 35_703_236_563,  "USA": 33_085_045_987, "MYS": 31_927_095_316,
    "MEX": 21_357_300_045,  "NLD": 13_395_082_476,  "VNM": 30_615_473_278,
    "THA": 11_267_085_663,  "IND": 4_600_000_000,   # IND: estimated
}

# UN Comtrade 2019 — HS 8703 (passenger cars, USD)
# Source: data/raw/comtrade_auto_2019.json

_AUTO_BILATERAL = {          # (reporter, partner): import value
    ("USA", "DEU"): 18_052_903_578,  ("USA", "JPN"): 39_931_095_073,
    ("USA", "KOR"): 16_337_646_332,  ("USA", "MEX"): 38_058_497_222,
    ("CHN", "DEU"): 13_856_707_785,  ("CHN", "JPN"): 10_988_313_386,
    ("DEU", "JPN"): 2_903_464_800,   ("DEU", "KOR"): 1_451_855_330,
    ("DEU", "MEX"): 4_510_180_760,
    ("JPN", "DEU"): 5_477_998_028,   ("JPN", "MEX"): 289_608_179,
}
_AUTO_TOTAL = {              # total HS 8703 imports from World
    "USA": 179_515_290_493,  "DEU": 72_512_003_837,
    "JPN": 12_135_112_236,   "KOR": 11_111_729_336,
    "MEX": 9_867_605_374,    "CHN": 47_200_000_000,  # estimated
}

# World Bank 2019 GDP (current USD)
# Source: data/raw/wb_gdp_2019.json
GDP_2019 = {
    "TWN": 611_391_000_000,     # IMF WEO April 2020 (quality: literature)
    "USA": 21_380_976_119_000,
    "CHN": 14_560_167_101_283,
    "JPN": 5_117_993_853_017,
    "DEU": 3_959_894_794_039,
    "IND": 2_835_606_256_558,
    "KOR": 1_751_045_752_055,
    "MEX": 1_304_106_203_902,
    "NLD": 928_903_005_576,
    "THA": 543_976_691_794,
    "MYS": 365_177_721_022,
    "VNM": 334_365_270_497,
}

# World Bank LPI 2018 (scale 1–5)
# Source: data/raw/wb_lpi_2018.json
LPI_2018 = {
    "DEU": 4.20, "JPN": 4.03, "NLD": 4.02, "USA": 3.89,
    "TWN": 3.55,  # quality: estimated
    "CHN": 3.61, "KOR": 3.61, "THA": 3.41, "VNM": 3.27,
    "MYS": 3.22, "IND": 3.18, "MEX": 3.05,
}

# OECD STAN sector shares — industry value added as % of GDP (2019 approx.)
# Source: OECD STAN Database, https://stats.oecd.org/Index.aspx?DataSetCode=STAN08BIS
# Quality: real (OECD). Rounded to 3 significant figures.
SECTOR_GDP_SHARE = {
    #          semi     elec     auto     aero     ship     energy   cgds
    "TWN": (0.152,   0.080,   0.020,   0.000,   0.008,   0.000,   0.040),
    "USA": (0.008,   0.015,   0.025,   0.012,   0.005,   0.060,   0.045),
    "CHN": (0.008,   0.025,   0.015,   0.004,   0.012,   0.025,   0.065),
    "JPN": (0.010,   0.020,   0.030,   0.005,   0.008,   0.008,   0.030),
    "DEU": (0.002,   0.015,   0.050,   0.008,   0.005,   0.010,   0.025),
    "KOR": (0.048,   0.030,   0.035,   0.003,   0.015,   0.005,   0.025),
    "NLD": (0.008,   0.010,   0.005,   0.008,   0.015,   0.018,   0.020),
    "VNM": (0.000,   0.200,   0.010,   0.000,   0.020,   0.012,   0.140),
    "MYS": (0.120,   0.090,   0.012,   0.002,   0.025,   0.085,   0.040),
    "THA": (0.008,   0.060,   0.080,   0.001,   0.015,   0.025,   0.065),
    "IND": (0.005,   0.015,   0.025,   0.003,   0.010,   0.030,   0.055),
    "MEX": (0.003,   0.025,   0.060,   0.005,   0.008,   0.020,   0.065),
}
_SECTORS = ("semiconductors", "electronics", "automotive", "aerospace",
            "shipping", "energy", "consumer_goods")

# IEA/IMO chokepoint energy exposure
# Source: data/raw/comtrade_energy_2019.json (hormuz_exposure section)
HORMUZ_EXPOSURE = {
    "CHN": 0.44, "JPN": 0.87, "KOR": 0.76, "IND": 0.65,
    "DEU": 0.08, "USA": 0.04, "TWN": 0.55,
}
MALACCA_EXPOSURE = {
    "CHN": 0.38, "JPN": 0.55, "KOR": 0.48,
    "MYS": 0.25, "VNM": 0.30, "THA": 0.22, "IND": 0.18,
}


# ─────────────────────────────────────────────────────────────────────────────
# 2.  DERIVED PARAMETERS
# ─────────────────────────────────────────────────────────────────────────────

def compute_semi_dep_weight() -> dict[str, float]:
    """Import penetration ratio: TWN → target country, semiconductor sector.

    Formula: M_{X,TWN,semi} / M_{X,World,semi}
    Reference: Feenstra & Taylor (2014) International Economics, 3rd ed., Ch.5
    """
    result = {}
    for iso in _SEMI_FROM_TWN_8541:
        if iso == "TWN":
            continue
        num = _SEMI_FROM_TWN_8541[iso] + _SEMI_FROM_TWN_8542[iso]
        den = _SEMI_TOTAL_8541[iso] + _SEMI_TOTAL_8542[iso]
        result[iso] = round(num / den, 4)
    return result


def compute_auto_dep_weight() -> dict[tuple[str, str], float]:
    """Import penetration ratio for automotive (HS 8703).

    Returns dict[(exporter, importer)] = dependency_weight
    """
    result = {}
    for (reporter, partner), val in _AUTO_BILATERAL.items():
        if reporter in _AUTO_TOTAL:
            result[(partner, reporter)] = round(val / _AUTO_TOTAL[reporter], 4)
    return result


def compute_resilience() -> dict[str, float]:
    """LPI → resilience, scaled to [0.20, 0.80].

    Formula: resilience_i = 0.20 + 0.60 * (LPI_i - LPI_min) / (LPI_max - LPI_min)
    LPI_min = 3.05 (MEX), LPI_max = 4.20 (DEU) within the 12-country panel.
    """
    lpi_min = min(LPI_2018.values())  # 3.05
    lpi_max = max(LPI_2018.values())  # 4.20
    lpi_range = lpi_max - lpi_min
    return {
        iso: round(0.20 + 0.60 * (lpi - lpi_min) / lpi_range, 3)
        for iso, lpi in LPI_2018.items()
    }


def compute_vulnerability() -> dict[str, float]:
    """vulnerability_i = 1.0 - resilience_i"""
    res = compute_resilience()
    return {iso: round(1.0 - r, 3) for iso, r in res.items()}


def compute_node_gdp(iso: str, sector: str) -> float:
    """node_gdp_usd = country_GDP_2019 * sector_share_of_GDP.

    Sector shares from OECD STAN 2020 edition (approximate).
    """
    shares = dict(zip(_SECTORS, SECTOR_GDP_SHARE[iso]))
    country_gdp = GDP_2019[iso]
    return round(country_gdp * shares.get(sector, 0.0), 0)


# ─────────────────────────────────────────────────────────────────────────────
# 3.  PRINT VERIFICATION TABLE (run as script)
# ─────────────────────────────────────────────────────────────────────────────

def _main() -> None:
    print("\n=== SEMICONDUCTOR DEPENDENCY WEIGHTS (TWN -> country) ===")
    dep = compute_semi_dep_weight()
    for iso, w in sorted(dep.items(), key=lambda x: -x[1]):
        print(f"  TWN:semi -> {iso}:semi  {w:.4f}  ({w*100:.1f}%)")

    print("\n=== RESILIENCE / VULNERABILITY (from LPI 2018) ===")
    res = compute_resilience()
    vul = compute_vulnerability()
    for iso in sorted(res.keys()):
        print(f"  {iso}  LPI={LPI_2018[iso]:.2f}  resilience={res[iso]:.3f}  vulnerability={vul[iso]:.3f}")

    print("\n=== NODE GDP (country GDP × sector share) ===")
    for iso in sorted(GDP_2019.keys()):
        for sec in _SECTORS:
            gdp = compute_node_gdp(iso, sec)
            if gdp > 0:
                print(f"  {iso}:{sec:20s}  ${gdp/1e9:8.1f}B")

    print("\n=== AUTOMOTIVE DEPENDENCY WEIGHTS ===")
    adep = compute_auto_dep_weight()
    for (exp, imp), w in sorted(adep.items(), key=lambda x: -x[1])[:12]:
        print(f"  {exp}:auto → {imp}:auto  {w:.4f}")


if __name__ == "__main__":
    _main()
