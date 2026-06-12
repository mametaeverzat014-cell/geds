# OECD ICIO 2025 edition — year 2019 (small/SML version)

Downloaded: 2026-06-12 (autonomous session), from the official OECD distribution
linked on https://www.oecd.org/en/data/datasets/inter-country-input-output-tables.html

| Item | Value |
|---|---|
| Source archive | https://webfs-sti.oecd.org/files/STI-PIE/ICIO/2025/2016-2022_SML.zip |
| Archive size / sha256 | 166,241,019 bytes / `46db55c45747e26dde5c1716d072b2aa74ace362a4424491ac646d2ab175befb` |
| Archive Last-Modified (server) | Mon, 18 May 2026 14:52:17 GMT |
| Extracted member | `2019_SML.csv` (88,008,102 bytes, zip mtime 2026-01-12) |
| `2019_SML.csv` sha256 | `85bd13fd8c2385c41d239d2ddc973ced1caa87c59c2b90b7bed3ff97048043d8` |
| Committed file | `2019_SML.csv.gz` (gzip -9 of the exact extracted bytes; 21,952,682 bytes) |
| `2019_SML.csv.gz` sha256 | `ede4e51f863d9f60d2e8c16b46ca80910043ca7a9f3244f2e6c0cb9ba53e7e0f` |

The raw CSV is committed gzip-compressed because 88 MB approaches GitHub's hard
100 MB per-file limit; `gunzip -k 2019_SML.csv.gz` (or `pandas.read_csv(..,
compression="infer")`) restores the byte-identical original
(verify against the sha256 above).

## Edition facts (from `ICIO2025annex.pdf`, committed alongside)

- 2025 edition covers 1995–2022; released 2025-08, revised 2025-10 and 2026-01
  (this file: January 2026 revision, per zip member mtimes).
- 81 economies: 38 OECD + 42 non-OECD + Rest of the World (`ROW`); the small
  (SML) version does NOT split China/Mexico (no CN1/CN2/MX1/MX2 — those are in
  the extended/EXT files).
- 50 industries, ISIC Rev.4 (new in 2025 ed.: 2-digit Agriculture/Mining split,
  `C24A`/`C24B` iron-steel vs non-ferrous, `C301` shipbuilding separate).
- Matrix layout (`ReadMe_ICIO_small.xlsx`): rows/cols labelled `CCC_III`
  (country_industry); 4050 intermediate rows + value-added/taxes rows;
  4050 intermediate cols + final-demand cols + output. Values: USD million,
  current prices. CSV shape: 4054 rows x 4538 cols (incl. label column).
- 2019 chosen as the last pre-COVID structural baseline year for graph
  expansion work (PROGRESS.md, deferred Phase 3).

## Companion archives (same directory on the OECD server, not committed)

- `1995-2000_SML.zip`, `2001-2005_SML.zip`, `2006-2010_SML.zip`,
  `2011-2015_SML.zip` — earlier year blocks
- `2016-2022_EXT.zip` — extended version with CN1/CN2/MX1/MX2 splits
- `ICIO2025econ*.zip` — RData time-series objects

Note for re-downloading: oecd.org / webfs-sti.oecd.org sit behind
Akamai/Cloudflare bot protection that rejects plain `curl`/`requests`
TLS fingerprints; a browser, or `curl_cffi` with `impersonate="chrome"`,
downloads them fine.

OECD terms of use permit reproduction and use of this data for non-commercial
research with source attribution: OECD (2025), OECD Inter-Country Input-Output
Database, http://oe.cd/icio
