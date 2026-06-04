# WIOD — Schema Audit

**Generated:** 2026-05-28 from the 15 WIOT *.xlsb files in `backend/data/raw/wiod/`.

## File inventory (real data, verified)

| Filename | Size | Year |
|---|---|---|
| `WIOT2000_Nov16_ROW.xlsb` … `WIOT2014_Nov16_ROW.xlsb` | 62 MB each | 2000–2014 |

15 files, ~930 MB total. All same format. **`.xlsb` (Excel binary), not `.xlsx`** as user spec said. Parsing requires `pyxlsb` reader (installed: 1.0.10).

**`WIOT2014_Nov16_ROW.xlsb`** is the latest year and the one the user spec referenced. Used as primary in this audit.

## Sheet structure (single sheet per file)

| Element | Location | Notes |
|---|---|---|
| Sheet name | `2014` | one sheet per workbook, named for the year |
| Title rows | 0–3 | denomination ("millions of US$"), structure tag ("industry-by-industry") |
| Sector codes header | **row 2**, cols 4+ | e.g. `A01`, `A02`, `A03`, `B`, `C10-C12` ... |
| Sector names header | **row 3**, cols 4+ | e.g. "Crop and animal production, hunting and related service activities" |
| Country code header | **row 4**, cols 4+ | e.g. `AUS`, `AUS`, ..., `USA`, `USA`, ..., `TOT` |
| Column shorthand | **row 5**, cols 4+ | `c1`, `c2`, ..., `c2685` |
| Data rows | **row 6 through ~2470** | (sector_code, sector_name, country_code, row_shorthand, *flows*) |
| Special rows (bottom) | **rows 2470–2477** | II_fob, TXSP, EXP_adj, PURR, PURNR, VA, GO |

## Country encoding

**44 distinct country codes** (43 real countries + `ROW` "Rest of World") + special `TOT`:

```
AUS AUT BEL BGR BRA CAN CHE CHN CYP CZE
DEU DNK ESP EST FIN FRA GBR GRC HRV HUN
IDN IND IRL ITA JPN KOR LTU LUX LVA MEX
MLT NLD NOR POL PRT ROU ROW RUS SVK SVN
SWE TUR TWN USA
```

Plus `TOT` as a totals-only column (1 col).

**Comparison vs OECD ICIO (81 countries):**
- WIOD has **44 countries** (vs OECD's 81)
- WIOD's 44 are a near-subset of OECD's 81
- Notable WIOD-absent (vs OECD): AGO, ARE, BLR, BRN, CHL, CIV, CMR, COL, COD, CRI, EGY, HKG, ISR, KAZ, KGZ, KHM, LAO, MAR, MMR, MUS, NGA, NZL, PAK, PER, SAU, SEN, SGP, THA, TUN, UKR, VNM, ZAF + others
- Notable WIOD-present (also in OECD): all major economies

## Sector encoding

WIOD uses **NACE Rev.2 (≈ ISIC Rev.4)** codes. 56 industries + 5 final-demand columns per country = 61 cols/country.

**56 industries (NACE Rev.2):**

| WIOD code | Industry |
|---|---|
| A01, A02, A03 | agriculture (crop, forestry, fishing) |
| B | mining and quarrying (bundled coal + oil + gas + metals) |
| C10-C12, C13-C15 | food/beverages, textiles |
| C16, C17, C18 | wood, paper, printing |
| C19 | coke + refined petroleum |
| C20, C21 | chemicals, pharmaceuticals |
| C22, C23 | rubber/plastics, non-metallic minerals |
| C24, C25 | basic metals, fabricated metals |
| C26, C27 | computer/electronic/optical, electrical equipment |
| C28, C29, C30 | machinery, motor vehicles, other transport equipment |
| C31_C32, C33 | furniture/other manufacturing, repair |
| D35 | electricity, gas, steam |
| E36, E37-E39 | water, sewerage/waste |
| F | construction |
| G45, G46, G47 | wholesale/retail (motor, wholesale, retail) |
| H49, H50, H51, H52, H53 | land transport, water, air, warehousing, postal |
| I | accommodation + food service |
| J58, J59_J60, J61, J62_J63 | publishing, audiovisual, telecom, IT services |
| **K64, K65, K66** | **banking, insurance, capital_markets** (separately, unlike OECD which bundles into K) |
| L68 | real estate |
| M69_M70, M71, M72, M73, M74_M75 | legal/accounting, architecture, R&D, advertising, other professional |
| N | administrative & support |
| O84 | public administration & defence |
| P85 | education |
| Q | human health & social work |
| R_S | arts/entertainment/other services |
| T | household activities |
| U | extraterritorial organisations |

**Critical finding:** WIOD separates **K64 (banking), K65 (insurance), K66 (capital markets)** — exactly the 3 sectors that OECD ICIO bundled into K. **This unblocks 3 of the 5 GEDS sectors that were NULL in OECD-only data.**

WIOD also does NOT split mining (B is still bundled), so:
- `gas` separation: still impossible from WIOD alone (B + D35 mixed)
- `semiconductors` separation: still impossible (C26 = all computer/electronic/optical)
- `energy` (composite): can be derived as B + C19 + D35

## Labor / value-added fields

WIOT has these special **row** labels for aggregate metrics (per (country, sector) **column**):

| Row label | Meaning | Use for GEDS |
|---|---|---|
| `II_fob` | Intermediate consumption FOB | total intermediate input use |
| `TXSP` | Net taxes on products | not used |
| `EXP_adj` | Direct exports adjustment | small adjustment factor |
| `PURR` | Purchases by residents abroad | not used |
| `PURNR` | Purchases by non-residents in country | not used |
| `VA` | **Total value added** | proxy for labor compensation (combines labor + capital + taxes) |
| `GO` | **Gross output** | total output |

**NO direct employment field in WIOT.** The WIOD release publishes **Socio-Economic Accounts (SEA)** separately for employment, hours, capital, etc. **SEA files are NOT in the repo.**

Implication for `employment_share`:
- **Cannot be derived** from WIOT alone.
- **Will stay NULL** in `country_sector_presence_wiod.csv` with explicit note.
- A `value_added_share` field WILL be populated as a labour-cost proxy (with explicit relabelling — NOT presented as employment_share).

## Mapping difficulties to GEDS sectors

| GEDS sector | WIOD source | Status vs OECD-only |
|---|---|---|
| `agriculture` | A01+A02+A03 | identical |
| `automotive` | C29 | identical |
| `electronics` | C26+C27 | identical |
| `aerospace` | C30 (incl. ships+aerospace+military, same bundling as OECD) | identical |
| `shipping` | H49+H50 | identical |
| `oil` | B + C19 (still bundled with gas in B) | identical bundling |
| `gas` | **STILL NULL** (B+D35 bundles) | unchanged from OECD |
| `utilities` | D35 + E36 + E37-E39 | identical |
| `aviation` | H51 | identical |
| `ports` | H52 | identical |
| `telecommunications` | J58+J59_J60+J61+J62_J63 | identical |
| `tourism` | I | identical |
| `consumer_goods` | C10-C15 + C16-C18 + C20-C23 + C28 + C31-C33 + G | identical |
| `government` | O84 + P85 | identical |
| **`banking`** | **K64 ONLY** | **NEW — narrower than OECD K** |
| **`insurance`** | **K65** | **NEW — unblocked from OECD NULL** |
| **`capital_markets`** | **K66** | **NEW — unblocked from OECD NULL** |
| **`semiconductors`** | NOT separable (C26 bundles all electronics) | still NULL |
| **`energy`** (composite) | B + C19 + D35 | NEW — computable |

**Net WIOD gain over OECD:** 3 new sectors (insurance, capital_markets, energy-composite) become evidence-backed.

## Detected issues

1. **`.xlsb` not `.xlsx`** — pyxlsb required. 0.7s to open, ~27s to iterate all 2478 rows.
2. **44 countries vs OECD's 81** — WIOD has narrower geographic coverage. Some GEDS-relevant countries (SAU, ARE, HKG, SGP, VNM, THA, EGY) are in OECD but NOT in WIOD.
3. **No SEA files** — true employment_share unobtainable. Substituting value_added_share is the honest approximation.
4. **Old vintage (2014 latest)** — WIOD stopped at 2014 (Nov 2016 release). For 2015+ events, the structure must be assumed stable. OECD data is up to 2022.
5. **B (mining) bundles** coal + oil + metals — cannot split gas from oil even with both WIOD and OECD.
6. **C26 bundles** all computer/electronic/optical — semiconductors stays NULL.

## Country count (final)

| Source | Country count |
|---|---|
| WIOD WIOT 2014 | 44 (43 real + ROW) |
| OECD ICIO 2022 | 81 |
| Heuristic graph | 59 |
| Intersection WIOD ∩ OECD | ~40 |
| WIOD-only (not in OECD) | 0 (WIOD ⊂ OECD) |
| OECD-only (not in WIOD) | ~37 |

## Usable tables (for parser)

| Output | Source | Filter |
|---|---|---|
| `wiod_country_sector_weights.csv` | per (country, NACE sector): VA, GO, II_fob | all 44 × 56 = 2,464 rows |
| `wiod_edges.csv` | industry-to-industry intermediate use flows | flow ≥ USD 1M threshold |
| `country_sector_presence_wiod.csv` | 44 × 19 GEDS sectors (NULL where not derivable) | always emit, mark NULL |

## Honest scope of this audit

- Inspected WIOT2014 only (latest year; all 15 years share format per WIOD release notes).
- Did NOT verify byte-for-byte across all 15 files; trusting consistency claim.
- Did NOT inspect WIOD-SEA Socio-Economic Accounts (not in repo). If they were present we'd get true employment_share.
- Parser will support `--year` flag to parse other years.
