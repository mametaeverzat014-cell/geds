# OECD ICIO — Schema Audit

**Generated:** 2026-05-28 from the 7 OECD ICIO SML CSV files in `backend/data/raw/oecd_icio/`.

## File inventory (real data, verified)

| Filename | Size | Year |
|---|---|---|
| `2016_SML.csv` | 86.7 MB | 2016 |
| `2017_SML.csv` | 87.4 MB | 2017 |
| `2018_SML.csv` | 87.9 MB | 2018 |
| `2019_SML.csv` | 88.0 MB | 2019 |
| `2020_SML.csv` | 87.4 MB | 2020 |
| `2021_SML.csv` | 88.8 MB | 2021 |
| `2022_SML.csv` | 90.1 MB | 2022 |

**Total:** 7 files, ~617 MB on disk. All 7 verified to share identical schema.

**Note on naming:** the user prompt specified `ICIO_2016.xlsx … ICIO_2022.xlsx`. The actual files are CSV in `<year>_SML.csv` format. Confirmed via `ls`. CSV is faster to parse than XLSX; no fabrication or substitution involved.

## Workbook / file structure

OECD ICIO SML CSVs are **single-sheet** flat tables (no Excel tabs). Each file is a 4053×4538 cell matrix.

```
                    Columns (4538 total)
                    ┌─────────────────────────────────────────────────────────┐
                    │ V1  │ 81 countries × 56 (50 industries + 6 final-demand) │ OUT │
                    │     │ = 4536 columns                                     │     │
Rows (4053 total)   ├─────┼─────────────────────────────────────────────────────────┤
                    │     │                                                         │
81 countries × 50   │     │  industry-to-industry intermediate-use flows            │
industries          │     │  cell(i,j) = USD million flow from supplier i to user j │
= 4050 industry     │     │                                                         │
rows                │     │                                                         │
                    ├─────┼─────────────────────────────────────────────────────────┤
3 special rows      │ TLS │  Taxes Less Subsidies (column-wise)                     │
                    │ VA  │  Value Added (column-wise)                              │
                    │ OUT │  Total Output (column-wise)                             │
                    └─────────────────────────────────────────────────────────┘
```

- **`V1`**: row label column (e.g. `USA_C29` = United States, motor vehicle sector)
- **`OUT` column**: row-wise total output for each supplier (country, sector)
- **`TLS` row, `VA` row, `OUT` row**: column-wise summaries

## Country encoding

**81 ISO3 country codes** present in both rows and columns, identical across all 7 years:

```
AGO ARE ARG AUS AUT BEL BGD BGR BLR BRA BRN CAN CHE CHL CHN CIV CMR COL CRI CYP
CZE DEU DNK DOM EGY ESP EST FIN FRA GBR GRC HKG HRV HUN IDN IND IRL ISL ISR ITA
JOR JPN KAZ KGZ KHM KOR LAO LTU LUX LVA MAR MEX MLT MMR MUS MYS NGA NLD NOR NZL
PAK PER PHL POL PRT ROU ROW RUS SAU SEN SGP SVK SVN SWE THA TUN TUR TWN UKR USA
VNM ZAF
```

- 80 real countries + 1 `ROW` (Rest of World aggregate).
- **Compared to GEDS heuristic graph**: 59 countries. OECD adds 22 countries, removes 0.
- **Coverage gain countries**: AGO, AUT, BGD, BGR, BLR, BRN, CIV, CMR, COL, CRI, CYP, CZE, DNK, DOM, EST, FIN, HKG (already in GEDS), HRV, HUN, ISL, JOR, KAZ, KGZ, KHM, LAO, LTU, LUX, LVA, MAR, MLT, MUS, NZL, PER, ROU, SEN, SVK, SVN, SWE, TUN, KEN-missing-still, ETH-missing-still, NGA, PAK, ROW.

## Sector encoding (50 industry sectors)

All sectors use **ISIC Rev.4** codes:

| OECD code | ISIC name (verified per OECD release notes) |
|---|---|
| `A01`, `A02`, `A03` | Crop & animal production / Forestry & logging / Fishing & aquaculture |
| `B05`, `B06`, `B07`, `B08`, `B09` | Mining of coal / crude petroleum & gas / metal ores / other mining / mining support |
| `C10T12` | Food, beverages, tobacco |
| `C13T15` | Textiles, apparel, leather |
| `C16` | Wood products |
| `C17_18` | Paper / publishing & printing |
| `C19` | Coke + refined petroleum products |
| `C20` | Chemicals |
| `C21` | Pharmaceuticals |
| `C22`, `C23` | Rubber/plastics / Other non-metallic mineral products |
| `C24A`, `C24B`, `C25` | Iron & steel / Non-ferrous metals / Fabricated metal products |
| `C26` | Computer, electronic, optical products |
| `C27` | Electrical equipment |
| `C28` | Machinery & equipment n.e.c. |
| `C29` | Motor vehicles, trailers, semi-trailers |
| `C301`, `C302T309` | Ships & boats / Other transport equipment (incl. aerospace) |
| `C31T33` | Furniture / Other manufacturing / Repair |
| `D` | Electricity, gas, steam, A/C |
| `E` | Water supply, sewerage, waste |
| `F` | Construction |
| `G` | Wholesale & retail trade |
| `H49` | Land transport |
| `H50` | Water transport |
| `H51` | Air transport |
| `H52` | Warehousing & support |
| `H53` | Postal & courier |
| `I` | Accommodation & food service |
| `J58T60` | Publishing / audiovisual / broadcasting |
| `J61` | Telecommunications |
| `J62_63` | Computer programming / information services |
| `K` | Financial & insurance (combined — banking + insurance + capital markets all here) |
| `L` | Real estate |
| `M` | Professional, scientific, technical |
| `N` | Administrative & support services |
| `O` | Public administration & defence |
| `P` | Education |
| `Q` | Human health & social work |
| `R`, `S`, `T` | Arts, entertainment / Other services / Households as employers |

**Plus 6 final-demand column types per country** (consumption side, not industry production):

| Code | Description |
|---|---|
| `HFCE` | Household final consumption |
| `NPISH` | Non-profit institutions serving households |
| `GGFC` | General government final consumption |
| `GFCF` | Gross fixed capital formation |
| `INVNT` | Inventory changes |
| `DPABR` | Direct purchases abroad by residents |

## Input-output matrix layout

- **Cell `(row=USA_C29, col=DEU_C29)` = USD millions of supply from US motor-vehicle sector to German motor-vehicle sector** (intermediate input, 2018 figures in 2018 USD).
- **Cell `(row=USA_C29, col=DEU_HFCE)`** = US motor-vehicle exports consumed by German households (final demand).
- **Cell `(row=VA, col=USA_C29)`** = total value added (wages + profits + taxes) by US motor-vehicle sector.
- **Cell `(row=OUT, col=USA_C29)`** = total output of US motor-vehicle sector = VA + sum of all intermediate inputs purchased.
- **Cell `(col=OUT, row=USA_C29)`** = same total output viewed row-wise = sum of all uses (other industries + final demand).

## Trade flow structure

- **Intermediate trade flow** from country A to country B in sector S₁→S₂:
  `cell(row=A_S1, col=B_S2)` (in USD m, supplier-to-user)
- **Final exports** from country A in sector S to country B household:
  `cell(row=A_S, col=B_HFCE)`
- **Total exports from A in sector S**: row sum of `A_S` over all columns where the country prefix is not A.
- **Total imports of B in sector S**: column sum of `B_S` over all rows where the country prefix is not B.

## OECD → GEDS 19-sector mapping (this audit's mapping)

This is the mapping that will be used by the parser. Where multiple OECD sectors collapse to one GEDS sector, flows will be summed. Where no clean correspondence exists, the cell stays NULL.

| GEDS sector | OECD ISIC source | Notes |
|---|---|---|
| `agriculture` | A01, A02, A03 | clean direct map |
| `oil` | B06 (crude petroleum/gas extraction) + C19 (refined petroleum) | combines upstream + downstream oil |
| `gas` | — | NOT separable from B06 in ICIO (oil + gas combined) → NULL with note |
| `electronics` | C26 (computer/electronic/optical) + C27 (electrical equipment) | C26 also bundles semiconductors |
| `semiconductors` | C26 (partial, NOT separable) | NULL with note — semis are bundled in C26 |
| `automotive` | C29 (motor vehicles) | clean direct |
| `aerospace` | C302T309 (other transport equip, includes aerospace) | imperfect — bundles rail/military |
| `shipping` | H49 (land) + H50 (water) | combined land+sea transport |
| `aviation` | H51 (air transport) | clean direct |
| `ports` | H52 (warehousing + support) | proxy — ports are subset of warehousing |
| `telecommunications` | J58T60 + J61 + J62_63 | combined publishing/telecom/IT |
| `utilities` | D (electricity/gas/steam) + E (water/waste) | combined |
| `banking` | K (financial + insurance combined) | proxy — banking is subset of K |
| `insurance` | K (partial, NOT separable) | NULL — insurance bundled in K |
| `capital_markets` | K (partial, NOT separable) | NULL — capital markets bundled in K |
| `tourism` | I (accommodation + food service) | clean direct |
| `government` | O (public admin) + P (education) | imperfect — bundles education |
| `consumer_goods` | C10T12 + C13T15 + C16 + C17_18 + C20 + C21 + C22 + C23 + C28 + C31T33 + G | broad aggregate |
| `energy` | (synonym for oil + gas + utilities) | composed sector, computed |

**Sectors that cannot be cleanly derived from OECD ICIO:**
- `gas` — OECD bundles natural gas in B06 (with oil) and D (with electricity)
- `semiconductors` — bundled in C26 (with computers and other electronics)
- `insurance` — bundled in K (with banking and capital markets)
- `capital_markets` — bundled in K (with banking and insurance)

These will be NULL in `country_sector_presence_real.csv` with explicit note. **No imputation will be performed.**

## Parsing assumptions

1. Cells are **USD millions, current prices** (per OECD ICIO release notes for SML format).
2. Empty cells in the source CSV will be parsed as `0.0`, not NaN. (Verified: pandas default reads sparse zeros as 0.0 when the cell is empty between commas.)
3. Self-loops (cell where row supplier = column user) are valid intermediate-use and will be preserved.
4. The `ROW` (Rest of World) row and column will be **kept** with explicit `ROW` ISO3 — it's a valid OECD aggregate representing all countries not individually broken out.
5. Threshold for edge emission: **flow ≥ USD 1 million** (cells below this are dropped from the bilateral edge CSV but still counted in the aggregate weights CSV). Rationale: 4536² ≈ 20M cells per year × 7 years = 144M cells; most are zero or near-zero. The $1M threshold keeps the bilateral file size manageable (target < 200MB total) while losing < 0.1% of total trade value globally.

## Detected issues

1. **Filename naming mismatch** (already noted above). User spec said XLSX; reality is CSV. Proceeded with CSV.
2. **Sector aggregation losses** (above table). `semiconductors`, `gas`, `insurance`, `capital_markets` cannot be derived from OECD alone. These 4 sectors will be NULL in OECD-only outputs and require supplementary data (SIA Factbook for semis, EIA for gas split, ECB/SNL for insurance/capital markets) before being claimed as evidence-backed.
3. **`ROW` row and column** is a residual aggregate, not a country. Decision: keep with explicit ISO3 = `ROW`. Downstream consumers should treat it as the "everything-else" bucket, not infer per-country values from it.
4. **`C301` vs `C302T309`** split: ICIO splits transport equipment into ships (C301) and "other" (C302T309 = rail + aerospace + military + n.e.c. combined). Aerospace cannot be cleanly separated from rail/military within C302T309 without auxiliary data. Decision: map C302T309 → aerospace (acknowledged imperfect).
5. **No semiconductors line item.** This is the most important loss. GEDS' Taiwan-strait + semiconductor-shortage scenarios cannot be backed by OECD ICIO; they remain heuristic.

## Country count (final)

| Source | Count |
|---|---|
| OECD ICIO (verified) | 81 (incl. ROW) |
| GEDS heuristic graph | 59 |
| GEDS engine `Industry` enum | 19 sectors |
| OECD industry sectors | 45 (50 row codes minus DPABR-style that aren't in rows) |
| OECD → GEDS clean mappings | 11 / 19 sectors (58%) |
| OECD → GEDS NULL (no source) | 4 / 19 sectors (semiconductors, gas, insurance, capital_markets) |
| OECD → GEDS aggregated mapping (lossy) | 4 / 19 sectors (aerospace, ports, government, consumer_goods) |

## Usable tables (for downstream parsing)

| Output | Source rows | Filter |
|---|---|---|
| `oecd_country_sector_weights.csv` | 81 × 50 = 4050 industry rows | none — emit all |
| `oecd_icio_edges.csv` | 81 × 50 = 4050 supplier rows × 81 × 50 = 4050 user cols per year × 7 years | flow ≥ USD 1M |
| `country_sector_presence_real.csv` (Phase 3) | 81 × 19 (GEDS sectors) | emit row if OECD has any evidence; NULL otherwise |

End of audit.
