"""Extract the GEDS Dataset Registry docx into structured CSVs + planning docs.

Source: D:/GEDS Dataset Registry  Global Economic Disruption Propagation (All Categories).docx
       dumped to backend/data/raw/dataset_registry_dump.json by extract_dataset_registry_dump.py.

Outputs:
  backend/data/csv/dataset_catalog.csv     — flat catalogue of datasets
  backend/data/csv/dataset_priority.csv    — HIGH/MEDIUM/LOW + reason
  docs/API_INTEGRATION_PLAN.md             — per-API integration sheet
  docs/DATA_PIPELINE.md                    — fetch→validate→normalize→store→graph→sim
  docs/DATA_AUDIT_DATASETS.md              — dupes, dead links, paywalls, gaps
  docs/NEXT_STEPS_DATA.md                  — immediate / short / medium / long term

Rules:
  - No invented values. Every cell traces to a docx source row.
  - Missing values render as empty (NULL semantics).
  - Confidence is DERIVED from observed properties (API + provider + caveats).
    The derivation rules are documented in the audit file so the score can be
    reproduced and contested.
  - Cross-reference entries ("See entry N") get is_alias=true and are excluded
    from catalogue ID space — they appear in the audit instead.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
DUMP = REPO / "backend" / "data" / "raw" / "dataset_registry_dump.json"
CSV_DIR = REPO / "backend" / "data" / "csv"
DOCS_DIR = REPO / "docs"
CSV_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR.mkdir(parents=True, exist_ok=True)


# ── Category normalisation ───────────────────────────────────────────────────
# Maps the docx category heading → user-required category enum.

DOC_CATEGORY_TO_CANON = {
    "International Trade": "trade",
    "GDP and Macroeconomics": "macroeconomics",
    "Supply Chains": "supply_chain",
    "Logistics": "logistics",
    "Shipping Routes": "shipping",
    "Semiconductor Industry": "semiconductors",
    "Energy Markets": "energy",
    "Financial Markets": "financial",
    "Inflation": "macroeconomics",  # user enum has no 'inflation'; closest fit
    "Geopolitical Risk": "geopolitical",
    "News and Real-Time Signals": "news",
    "Historical Crises": "historical_events",
    "Transportation": "transportation",
    "Trade Dependency Networks": "supply_chain",
}


# ── parsing helpers ──────────────────────────────────────────────────────────

_YEAR_PAIR_RE = re.compile(r"(\d{4})\s*[–\-]\s*(\d{4}|present)", re.IGNORECASE)
_YEAR_SINGLE_RE = re.compile(r"\b(\d{4})\b")
_FOOTNOTE_RE = re.compile(r"\[\^?\d+\]|\[\d+\]\[\d+\]|\[\d+\]")


def strip_footnotes(s: str) -> str:
    return _FOOTNOTE_RE.sub("", s).strip()


def parse_coverage_years(raw: str) -> tuple[str, str]:
    """Extract (start_year, end_year). end_year='' when ongoing or unknown."""
    if not raw:
        return "", ""
    s = strip_footnotes(raw)
    m = _YEAR_PAIR_RE.search(s)
    if m:
        start = m.group(1)
        end_raw = m.group(2).lower()
        end = "" if end_raw == "present" else end_raw
        return start, end
    # Fallback: single year
    m1 = _YEAR_SINGLE_RE.search(s)
    if m1:
        return m1.group(1), ""
    return "", ""


def parse_api_available(raw: str) -> str:
    """'Yes', 'No', or '' from the API column text."""
    if not raw:
        return ""
    s = raw.strip().lower()
    if s.startswith("yes"):
        return "Yes"
    if s.startswith("no"):
        return "No"
    return ""


def normalize_url(raw: str) -> str:
    """Take the first https URL we can find. Empty if none."""
    if not raw:
        return ""
    m = re.search(r"https?://\S+", strip_footnotes(raw))
    if not m:
        return ""
    # Strip trailing punctuation/citation cruft.
    url = m.group(0).rstrip(".,;)")
    return url


def parse_update_frequency(raw: str) -> str:
    """Lower-case the first comma-separated token; keep raw if unrecognised."""
    if not raw:
        return ""
    s = strip_footnotes(raw)
    return s.strip()


# Confidence rubric (1-5).
# Documented in audit. Derived deterministically from these observable signals:
#  - +1 baseline
#  - +1 if provider is a major standards body (UN, IMF, World Bank, OECD,
#        Federal Reserve, EIA, BIS, WTO, ECB)
#  - +1 if a free API exists (api_available == 'Yes')
#  - +1 if a Python/R package is mentioned in the API cell
#  - +1 if coverage spans 10+ years AND updates are at least annual
# Caps at 5. Floors at 1.

MAJOR_PROVIDERS = (
    "united nations", "un statistics", "unctad",
    "international monetary fund", "imf",
    "world bank", "world trade organization", "wto",
    "oecd",
    "federal reserve", "fed",
    "european central bank", "ecb",
    "bank for international settlements", "bis",
    "us energy information", "eia",
    "fao",
    "cepii",
)


def derive_confidence(provider: str, api_text: str, coverage_start: str,
                      coverage_end: str, freq: str) -> int:
    score = 1
    plow = (provider or "").lower()
    if any(m in plow for m in MAJOR_PROVIDERS):
        score += 1
    api_low = (api_text or "").lower()
    if api_low.startswith("yes"):
        score += 1
    if any(pkg in api_low for pkg in (
        "python", "package", "comtradeapicall", "fredapi", "imfp", "wbgapi",
        "wbdata", "pandasdmx", "pymrio", "eia-python",
    )):
        score += 1
    try:
        if coverage_start:
            yr_start = int(coverage_start)
            yr_end = int(coverage_end) if coverage_end else 2026
            span = yr_end - yr_start
            freq_low = (freq or "").lower()
            if span >= 10 and any(f in freq_low for f in (
                "annual", "monthly", "daily", "weekly", "biannual", "quarterly",
                "continuous", "15-minute",
            )):
                score += 1
    except (ValueError, TypeError):
        pass
    return max(1, min(5, score))


def derive_priority(api_available: str, format_text: str, provider: str,
                    limitations: str, api_cell: str) -> tuple[str, str]:
    """Return (HIGH|MEDIUM|LOW, reason).

    Strict paywall detection: only mark LOW when basic access is actually
    blocked. "Premium for bulk" or "tiered pricing" do NOT count — free tier
    is still usable for GEDS-scale needs.
    """
    api_low = (api_cell or "").lower()
    fmt_low = (format_text or "").lower()
    lim_low = (limitations or "").lower()
    api_yes = api_low.startswith("yes")
    has_python = any(pkg in api_low for pkg in (
        "comtradeapicall", "fredapi", "imfp", "wbgapi", "wbdata",
        "pandasdmx", "pymrio", "eia-python", "weo", "python:", "python package",
        "python ", " r:", "package",
    ))
    has_free_api = api_yes and (
        "free" in api_low or "no key" in api_low or "(no key)" in api_low
        or "none" in api_low
    )
    api_key_required = api_yes and "key" in api_low and "no key" not in api_low
    # Strict paywall: only if BASIC access is blocked. "Premium for bulk" with
    # a free tier does not block GEDS.
    real_paywall_phrases = (
        "members only", "membership required", "requires sia membership",
        "requires subscription", "paid subscription only", "paid only",
        "primary data is proprietary and paid",
        "full databook requires", "for full",
    )
    paywalled = any(kw in lim_low for kw in real_paywall_phrases)
    geospatial_only = ("geoservices" in api_low or "wms" in api_low
                       or "wfs" in api_low) and "csv" not in fmt_low
    flat_file = (
        api_low.startswith("no") or "(flat" in api_low or "flat file" in api_low
        or "no dedicated api" in api_low or "no (flat" in api_low
    )

    if paywalled:
        return "LOW", "Paywalled or members-only — direct GEDS ingestion blocked."
    if geospatial_only:
        return "LOW", "API is geospatial-only (WMS/WFS/GeoServices); needs GIS pipeline."
    if has_free_api and has_python:
        return "HIGH", "Free public API + documented Python/R package."
    if has_free_api:
        return "HIGH", "Free public API (no key); REST callable directly."
    if api_key_required and has_python:
        return "HIGH", "API key required (free registration) + Python package available."
    if api_key_required:
        return "MEDIUM", "API key required (free); REST callable after registration."
    if api_yes:
        return "HIGH", "Public API documented; treat as free until provider says otherwise."
    if flat_file:
        return "MEDIUM", "Flat-file download only; needs scheduled fetch + diff."
    return "MEDIUM", "API availability unclear; assume scripted fetch needed."


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    if not DUMP.exists():
        print(f"ERROR: {DUMP} not found.", file=sys.stderr)
        return 1
    raw = json.loads(DUMP.read_text(encoding="utf-8"))
    paragraphs: list[str] = raw["paragraphs"]
    tables: list[list[list[str]]] = raw["tables"]

    # Step 1: pair each of the first 14 tables with the preceding Category heading.
    heading_re = re.compile(r"^Category\s+(\d+)\s*[—–-]\s*(.+)$")
    table_to_category: dict[int, str] = {}
    cat_order: list[tuple[int, str]] = []
    for p in paragraphs:
        m = heading_re.match(p.strip())
        if m:
            cat_order.append((int(m.group(1)), m.group(2).strip()))
    # Map by table index: tables[0..13] correspond to categories 1..14 in order.
    for idx, (_, cat_name) in enumerate(cat_order[:14]):
        table_to_category[idx] = cat_name

    # Step 2: walk every data row across tables 0..13.
    catalog_rows: list[dict] = []
    alias_rows: list[dict] = []  # cross-reference entries
    audit_notes: list[str] = []
    dead_links: list[str] = []  # urls that look truncated or malformed
    seen_urls: dict[str, list[int]] = defaultdict(list)
    seen_names: dict[str, list[int]] = defaultdict(list)

    for table_idx in range(min(14, len(tables))):
        tbl = tables[table_idx]
        if not tbl:
            continue
        doc_cat = table_to_category.get(table_idx, "")
        canon_cat = DOC_CATEGORY_TO_CANON.get(doc_cat, "")
        if not canon_cat:
            audit_notes.append(f"table {table_idx}: unmapped category '{doc_cat}'")
        # Skip header row
        for row in tbl[1:]:
            if len(row) < 13:
                continue
            # Original docx 'entry #' column.
            entry_num = row[0].strip()
            name = strip_footnotes(row[1]).strip()
            provider = strip_footnotes(row[2]).strip()
            desc = strip_footnotes(row[3]).strip()
            years_raw = row[4].strip()
            freq = parse_update_frequency(row[5])
            geo = strip_footnotes(row[6]).strip()
            variables = strip_footnotes(row[7]).strip()
            fmt = strip_footnotes(row[8]).strip()
            api_cell = strip_footnotes(row[9]).strip()
            url_cell = row[10].strip()
            limitations = strip_footnotes(row[11]).strip()
            citation = strip_footnotes(row[12]).strip()

            # Cross-reference detection — entries that say "(See Category X, entry N)"
            # or whose description begins with "(See ".
            is_alias = bool(re.search(r"\(See\b", desc) or re.search(r"\bsee entry\b", desc, re.IGNORECASE))
            if is_alias:
                alias_rows.append({
                    "alias_entry_num": entry_num, "alias_name": name,
                    "alias_category": canon_cat, "points_to": desc,
                })
                continue

            start_year, end_year = parse_coverage_years(years_raw)
            api_available = parse_api_available(api_cell)
            url = normalize_url(url_cell)
            if url_cell and not url:
                dead_links.append(f"entry {entry_num} ({name}): no parseable URL in {url_cell!r}")

            confidence = derive_confidence(
                provider, api_cell, start_year, end_year, freq,
            )
            seen_urls[url].append(int(entry_num) if entry_num.isdigit() else -1)
            seen_names[name.lower()].append(int(entry_num) if entry_num.isdigit() else -1)

            catalog_rows.append({
                "dataset_id": entry_num,
                "dataset_name": name,
                "provider": provider,
                "category": canon_cat,
                "description": desc,
                "coverage_start": start_year,
                "coverage_end": end_year,
                "update_frequency": freq,
                "geographic_scope": geo,
                "variables": variables,
                "format": fmt,
                "api_available": api_available,
                "download_url": url,
                "citation": citation,
                "limitations": limitations,
                "confidence": confidence,
                # Internal-only fields used downstream; not part of user schema:
                "_api_cell": api_cell,
                "_doc_category": doc_cat,
            })

    # ── Write dataset_catalog.csv ────────────────────────────────────────────
    cat_path = CSV_DIR / "dataset_catalog.csv"
    catalog_fields = [
        "dataset_id", "dataset_name", "provider", "category",
        "description", "coverage_start", "coverage_end", "update_frequency",
        "geographic_scope", "variables", "format", "api_available",
        "download_url", "citation", "limitations", "confidence",
    ]
    with cat_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=catalog_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(catalog_rows)
    print(f"wrote {cat_path} ({len(catalog_rows)} rows; {len(alias_rows)} alias entries excluded)")

    # ── Write dataset_priority.csv ───────────────────────────────────────────
    pri_path = CSV_DIR / "dataset_priority.csv"
    pri_rows = []
    for r in catalog_rows:
        priority, reason = derive_priority(
            r["api_available"], r["format"], r["provider"], r["limitations"], r["_api_cell"],
        )
        pri_rows.append({
            "dataset_id": r["dataset_id"],
            "priority": priority,
            "reason": reason,
        })
    with pri_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["dataset_id", "priority", "reason"])
        w.writeheader()
        w.writerows(pri_rows)
    print(f"wrote {pri_path} ({len(pri_rows)} rows)")

    # ── API_INTEGRATION_PLAN.md ──────────────────────────────────────────────
    # Use the API Quick Reference table (table 14) + augment with per-dataset
    # info from catalog_rows.
    api_ref: list[dict] = []
    if len(tables) > 14:
        qref = tables[14]
        for row in qref[1:]:
            if len(row) < 5:
                continue
            api_ref.append({
                "dataset": row[0].strip(),
                "endpoint_pattern": row[1].strip(),
                "auth": row[2].strip(),
                "rate_limit": row[3].strip(),
                "python_package": row[4].strip(),
            })
    api_path = DOCS_DIR / "API_INTEGRATION_PLAN.md"
    lines = [
        "# GEDS Data Layer — API Integration Plan",
        "",
        f"Generated from `backend/data/csv/dataset_catalog.csv` ({len(catalog_rows)} datasets)",
        f"and the Dataset Registry API Quick Reference ({len(api_ref)} APIs).",
        "",
        "Only datasets whose `api_available == 'Yes'` are listed below. Datasets",
        "lacking an API appear in the catalog with `api_available == 'No'` and are",
        "expected to be ingested via scheduled flat-file download (see DATA_PIPELINE.md).",
        "",
        "Difficulty ratings are derived from these observable signals:",
        "- **Easy** = free public API + maintained Python package + no auth.",
        "- **Medium** = free key required, OR Python package missing.",
        "- **Hard** = bulk-only, key + rate-limit constraints, OR geospatial-only.",
        "",
        "Time estimates are calendar-day estimates assuming 1 engineer with",
        "existing GEDS Python infrastructure.",
        "",
    ]
    # Build a quick-ref lookup
    qref_by_name = {a["dataset"].lower(): a for a in api_ref}
    # Curated dataset_id → qref-name map. Loose token matching was producing
    # wrong pairings (e.g. WITS getting matched to "World Bank WDI").
    qref_curated = {
        1: "un comtrade",
        4: "wto timeseries",
        8: "imf weo / ifs / pcps",
        9: "world bank wdi",
        11: "imf weo / ifs / pcps",
        13: "imf weo / ifs / pcps",
        10: "oecd", 16: "oecd", 17: "oecd", 20: "oecd",
        22: "imf portwatch", 54: "imf portwatch",
        25: "fred", 34: "fred", 38: "fred",
        29: "un comtrade", 62: "world bank wdi",
        30: "eia", 35: "bis",
        37: "imf weo / ifs / pcps",
        39: "oecd",
        40: "imf weo / ifs / pcps",
        43: "acled",
        49: "imf weo / ifs / pcps",
        50: "world bank wdi", 56: "world bank wdi",
        57: "oecd",
    }

    for r in [r for r in catalog_rows if r["api_available"] == "Yes"]:
        qref = None
        try:
            ds_id = int(r["dataset_id"])
        except ValueError:
            ds_id = -1
        if ds_id in qref_curated:
            qref = qref_by_name.get(qref_curated[ds_id])
        endpoint = qref["endpoint_pattern"] if qref else ""
        auth = qref["auth"] if qref else ""
        rate = qref["rate_limit"] if qref else ""
        pkg = qref["python_package"] if qref else ""
        # Difficulty — check expensive paths first (geospatial before easy)
        lim_low = r["limitations"].lower()
        api_low = r["_api_cell"].lower()
        endpoint_low = endpoint.lower()
        is_geospatial = any(kw in api_low or kw in endpoint_low for kw in (
            "geoservices", "wms", "wfs", "geoservices rest",
        ))
        is_manual = "manual" in (pkg or "").lower()
        if is_geospatial:
            diff = "Hard"
            eta = "2–3 weeks (GIS plumbing)"
        elif is_manual:
            diff = "Medium"
            eta = "1 week (manual scheduled download)"
        elif pkg and pkg != "none documented" and ("free" in api_low or "none" in auth.lower() or "(no key)" in auth.lower()):
            diff = "Easy"
            eta = "1–2 days"
        elif "key" in auth.lower() or "key" in api_low:
            diff = "Medium"
            eta = "3–5 days (incl. key request)"
        else:
            diff = "Medium"
            eta = "1 week"

        lines += [
            f"## {r['dataset_name']}",
            "",
            f"- **Dataset ID:** {r['dataset_id']}",
            f"- **Provider:** {r['provider']}",
            f"- **Category:** `{r['category']}`",
            f"- **Authentication:** {auth or 'see source — not in quick reference'}",
            f"- **Rate limits:** {rate or 'see source — not in quick reference'}",
            f"- **Required keys:** {'Yes — register at provider' if 'key' in (auth or '').lower() else 'None stated'}",
            f"- **Endpoint pattern:** `{endpoint or 'not in API quick reference — see download_url'}`",
            f"- **Python package:** `{pkg or 'none documented'}`",
            f"- **Expected response:** {r['format']}",
            f"- **Implementation difficulty:** {diff}",
            f"- **Estimated implementation time:** {eta}",
            f"- **Source URL:** {r['download_url'] or 'see catalog'}",
            f"- **Known limitations:** {r['limitations'] or '—'}",
            "",
        ]

    # Trailing reference table of any APIs in qref that did not match a catalog row.
    unmatched = []
    for a in api_ref:
        matched = False
        for r in catalog_rows:
            if r["api_available"] == "Yes" and any(
                tok in r["dataset_name"].lower() for tok in a["dataset"].lower().split() if len(tok) > 3
            ):
                matched = True
                break
        if not matched:
            unmatched.append(a)
    if unmatched:
        lines += [
            "## Unmatched entries in API Quick Reference",
            "",
            "The following appear in the docx API quick-reference table but did not",
            "match a dataset catalog name — record kept for audit:",
            "",
            "| Dataset | Endpoint | Auth | Rate limit | Package |",
            "|---|---|---|---|---|",
        ]
        for a in unmatched:
            lines.append(
                f"| {a['dataset']} | `{a['endpoint_pattern']}` | {a['auth']} | "
                f"{a['rate_limit']} | {a['python_package']} |",
            )

    api_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {api_path}")

    # ── DATA_PIPELINE.md ─────────────────────────────────────────────────────
    pipe_path = DOCS_DIR / "DATA_PIPELINE.md"
    high = [r for r, p in zip(catalog_rows, pri_rows) if p["priority"] == "HIGH"]
    med = [r for r, p in zip(catalog_rows, pri_rows) if p["priority"] == "MEDIUM"]
    low = [r for r, p in zip(catalog_rows, pri_rows) if p["priority"] == "LOW"]
    pipe_lines = [
        "# GEDS Data Pipeline — Architecture",
        "",
        "End-to-end ingestion design for the dataset catalog.",
        "",
        "```",
        "Source  →  Fetch  →  Validate  →  Normalize  →  Store  →  Graph Builder  →  Simulation Engine",
        "```",
        "",
        "## Layer 1 — Source",
        "",
        f"- **{len(catalog_rows)} datasets** catalogued in",
        "  `backend/data/csv/dataset_catalog.csv`.",
        f"- **{len(high)} HIGH-priority** datasets are the target for the first",
        "  automated pipeline (free API + Python package available).",
        f"- **{len(med)} MEDIUM** require scheduled download or key registration.",
        f"- **{len(low)} LOW** are paywalled or require GIS infrastructure",
        "  and are deferred until the data layer matures.",
        "",
        "## Layer 2 — Fetch",
        "",
        "Two fetch modes coexist:",
        "",
        "1. **API mode** (HIGH priority datasets): a thin wrapper around each",
        "   provider's REST endpoint, plus its Python package where available",
        "   (e.g. `comtradeapicall`, `fredapi`, `wbgapi`, `imfp`, `pandasdmx`).",
        "   Implementation lives in `backend/app/data/fetchers/` (one module per",
        "   provider). Existing example: `backend/app/data/comtrade_fetcher.py`.",
        "2. **Flat-file mode** (MEDIUM priority): scheduled HTTP GET of XLSX/CSV",
        "   bulk dumps. Files land in `backend/data/raw/<provider>/<dataset_id>/`",
        "   with the date in the filename. Existing example: the daily Comtrade",
        "   cron in `.github/workflows/refresh-data.yml`.",
        "",
        "## Layer 3 — Validate",
        "",
        "Each fetch is followed by a per-dataset validator that checks:",
        "",
        "- file is non-empty and parseable as its declared `format`",
        "- expected variables (from catalog `variables` column) are present",
        "- coverage_end has not regressed vs. the previous successful fetch",
        "- counts are within ±50% of the last 4-week median (anomaly guard)",
        "",
        "Failure mode: validator writes an `.error` file alongside the fetched",
        "artefact and the cron job exits non-zero. The previous successful",
        "artefact remains the active one (no silent overwrite).",
        "",
        "## Layer 4 — Normalize",
        "",
        "All sources are normalised into the GEDS canonical schema before",
        "they touch the graph:",
        "",
        "- **Countries**: ISO3 (see `historical_events_expanded.csv` for the",
        "  reference mapping table, including region expansions).",
        "- **Sectors**: GEDS fixed taxonomy (see `extract_events_from_docx.py`",
        "  `SECTOR_TAXONOMY`).",
        "- **Time**: ISO weekly bucket (Sunday-start), since the propagation",
        "  engine runs in weekly time steps.",
        "- **Units**: USD nominal for value, TEUs for shipping, % for indices.",
        "",
        "Normalisation modules live in `backend/app/data/normalize/`.",
        "",
        "## Layer 5 — Store",
        "",
        "Raw and normalised artefacts both go to disk; no DB required for v1.",
        "",
        "```",
        "backend/data/",
        "├── raw/                    # provider-formatted dumps",
        "│   └── <provider>/<dataset_id>/YYYY-MM-DD.<ext>",
        "├── csv/                    # canonical CSVs for the engine",
        "│   ├── dataset_catalog.csv",
        "│   ├── historical_events_expanded.csv",
        "│   └── comtrade_edges.csv",
        "├── parquet/                # parquet mirrors for ML",
        "└── manifests/              # provenance records",
        "    └── <dataset_id>.json   # last_fetch, sha256, source_url",
        "```",
        "",
        "## Layer 6 — Graph Builder",
        "",
        "`backend/app/data/edge_merger.py` already merges Comtrade edges into",
        "the engine graph; the same module pattern will extend to other",
        "bilateral-trade and supply-chain datasets (BACI, OECD ICIO, OECD TiVA).",
        "Macroeconomic datasets (IMF WEO, World Bank WDI, FRED) feed node",
        "attributes, not edges, and update the per-node baseline shock vector",
        "rather than the topology.",
        "",
        "## Layer 7 — Simulation Engine",
        "",
        "The engine consumes the canonical CSVs at boot via `seed.load_graph()`",
        "and never reads raw provider files directly. This isolates engine",
        "correctness from data-source churn.",
        "",
        "## Daily refresh logic",
        "",
        "GitHub Actions (`.github/workflows/refresh-data.yml`) runs a cron daily.",
        "Per dataset:",
        "",
        "1. Read last-fetch timestamp from `manifests/<dataset_id>.json`.",
        "2. If older than `update_frequency` (catalog column), fetch.",
        "3. Run the validator. On failure, leave previous artefact in place.",
        "4. On success, write artefact + updated manifest, sha256 the file,",
        "   and commit the manifest (but NOT the raw artefact — too large).",
        "5. Open a PR labelled `data-refresh` for the manifest commits.",
        "",
        "## Failure handling",
        "",
        "- **Network failure during fetch**: retry 3× with exponential backoff,",
        "  then skip the dataset for the day and log an `.error` file. Cron",
        "  continues with remaining datasets.",
        "- **Validator failure**: emit a Sentry-style alert (post to a dedicated",
        "  channel; not yet wired). Previous artefact remains active.",
        "- **Schema drift** (variable disappeared upstream): validator flags it;",
        "  human triage required. The catalog `confidence` may need downgrade.",
        "",
        "## Caching strategy",
        "",
        "- Raw dumps are kept indefinitely on disk (gitignored).",
        "- The engine reads from `backend/data/csv/*.csv`. These are committed.",
        "- API responses are NOT cached in-memory at request time; the engine",
        "  reloads from CSV on cold boot only.",
        "",
        "## Versioning",
        "",
        "- Each dataset artefact has a fetch date in the filename.",
        "- The manifest tracks `coverage_start`, `coverage_end`, `sha256`, and",
        "  `provider_release_date` so we can pin a model to a specific data",
        "  vintage (important for IMF WEO comparisons across vintages).",
        "",
        "## Deduplication",
        "",
        "Cross-reference entries flagged in `DATA_AUDIT_DATASETS.md` are",
        "**not** fetched twice — the alias points to the canonical entry's",
        "dataset_id and shares its artefacts.",
        "",
        "## Monitoring",
        "",
        "- `/api/v1/data/last-refresh` already exposes the manifest layer over HTTP.",
        "- `/api/v1/data/provenance` returns per-dataset citation + last-fetch sha.",
        "- A weekly summary email of refresh successes/failures is **not yet built**",
        "  — listed in NEXT_STEPS_DATA.md.",
        "",
    ]
    pipe_path.write_text("\n".join(pipe_lines), encoding="utf-8")
    print(f"wrote {pipe_path}")

    # ── DATA_AUDIT_DATASETS.md ───────────────────────────────────────────────
    # (NOT named DATA_AUDIT.md because that file already exists for historical
    # events; see audit_notes section for the rename rationale.)
    audit_path = DOCS_DIR / "DATA_AUDIT_DATASETS.md"
    dupes_by_url = {u: ids for u, ids in seen_urls.items() if u and len(ids) > 1}
    dupes_by_name = {n: ids for n, ids in seen_names.items() if len(ids) > 1}
    paywalled = [
        r for r in catalog_rows if any(kw in r["limitations"].lower() for kw in (
            "members only", "subscription", "paid", "paywall", "premium", "membership required",
        ))
    ]
    low_conf = [r for r in catalog_rows if r["confidence"] <= 2]
    no_url = [r for r in catalog_rows if not r["download_url"]]
    no_coverage = [r for r in catalog_rows if not r["coverage_start"]]

    audit_lines = [
        "# GEDS Dataset Registry — Audit",
        "",
        f"Source: `D:/GEDS Dataset Registry  Global Economic Disruption Propagation (All Categories).docx`",
        f"Catalogue: `backend/data/csv/dataset_catalog.csv` ({len(catalog_rows)} datasets)",
        "",
        "## Confidence score — derivation rules",
        "",
        "Confidence is **derived**, not extracted. Score in [1, 5]:",
        "- baseline 1",
        "- +1 if provider is a major standards body (UN, IMF, World Bank, OECD, Fed, ECB, BIS, WTO, EIA, FAO, CEPII)",
        "- +1 if a free API exists (`api_available == 'Yes'`)",
        "- +1 if a Python/R package is documented",
        "- +1 if coverage span ≥10y AND update frequency at least annual",
        "",
        "## Cross-reference / alias entries",
        "",
        f"{len(alias_rows)} entries reference other entries rather than carrying",
        "their own data. These were **excluded from the catalog** to avoid",
        "duplicate `dataset_id` rows. Track them here:",
        "",
        "| Entry # | Name | Category | Points to |",
        "|---|---|---|---|",
    ]
    for a in alias_rows:
        audit_lines.append(
            f"| {a['alias_entry_num']} | {a['alias_name']} | {a['alias_category']} | {a['points_to'][:140]} |",
        )
    if not alias_rows:
        audit_lines.append("| (none) | | | |")

    audit_lines += [
        "",
        "## Duplicate datasets",
        "",
        f"- Duplicate URLs: **{len(dupes_by_url)}**",
    ]
    for u, ids in dupes_by_url.items():
        audit_lines.append(f"  - `{u}` → dataset_ids {ids}")
    audit_lines += [
        f"- Duplicate names (case-insensitive): **{len(dupes_by_name)}**",
    ]
    for n, ids in dupes_by_name.items():
        audit_lines.append(f"  - `{n}` → dataset_ids {ids}")

    audit_lines += [
        "",
        "## Possibly dead / unparseable URLs",
        "",
        f"Datasets with no parseable HTTPS URL: **{len(no_url)}**",
    ]
    for r in no_url:
        audit_lines.append(f"- {r['dataset_id']} ({r['dataset_name']}): provider={r['provider']}")
    audit_lines += [""]
    if dead_links:
        audit_lines.append("URL strings present but unparseable:")
        for d in dead_links:
            audit_lines.append(f"- {d}")
        audit_lines.append("")

    audit_lines += [
        "## Paywalled / restricted-access sources",
        "",
        f"Count: **{len(paywalled)}**",
        "",
    ]
    for r in paywalled:
        audit_lines.append(
            f"- {r['dataset_id']} ({r['dataset_name']}): {r['limitations'][:160]}",
        )

    audit_lines += [
        "",
        "## Low-confidence datasets (score ≤ 2)",
        "",
        f"Count: **{len(low_conf)}**",
        "",
    ]
    for r in low_conf:
        audit_lines.append(
            f"- {r['dataset_id']} ({r['dataset_name']}): conf={r['confidence']}, provider={r['provider']}",
        )

    audit_lines += [
        "",
        "## Missing variables / fields",
        "",
        "Per-field missing-value counts:",
        "",
        "| Field | Missing |",
        "|---|---|",
    ]
    for fld in catalog_fields:
        miss = sum(1 for r in catalog_rows if not r.get(fld))
        audit_lines.append(f"| {fld} | {miss} |")

    audit_lines += [
        "",
        "## Coverage gaps",
        "",
        f"Datasets with no parseable `coverage_start`: **{len(no_coverage)}**",
    ]
    for r in no_coverage:
        audit_lines.append(f"- {r['dataset_id']} ({r['dataset_name']})")
    audit_lines += [""]

    cat_counts = Counter(r["category"] for r in catalog_rows)
    audit_lines += [
        "## Coverage by category",
        "",
        "| Category | Dataset count |",
        "|---|---|",
    ]
    for cat, c in cat_counts.most_common():
        audit_lines.append(f"| {cat or '(unmapped)'} | {c} |")

    audit_lines += [
        "",
        "## Note on file naming",
        "",
        "The requested filename `docs/DATA_AUDIT.md` was already in use by the",
        "historical-events extraction. To avoid overwriting that output, this",
        "audit was written to `docs/DATA_AUDIT_DATASETS.md`. The event-level",
        "audit is preserved at `docs/DATA_AUDIT.md`.",
        "",
    ]
    if audit_notes:
        audit_lines += [
            "## Extraction notes",
            "",
        ]
        for n in audit_notes:
            audit_lines.append(f"- {n}")
        audit_lines.append("")

    audit_path.write_text("\n".join(audit_lines), encoding="utf-8")
    print(f"wrote {audit_path}")

    # ── NEXT_STEPS_DATA.md ───────────────────────────────────────────────────
    next_path = DOCS_DIR / "NEXT_STEPS_DATA.md"
    high_priority = [r for r, p in zip(catalog_rows, pri_rows) if p["priority"] == "HIGH"]
    med_priority = [r for r, p in zip(catalog_rows, pri_rows) if p["priority"] == "MEDIUM"]
    low_priority = [r for r, p in zip(catalog_rows, pri_rows) if p["priority"] == "LOW"]

    nxt = [
        "# GEDS Data Layer — Implementation Roadmap",
        "",
        f"Derived from `dataset_catalog.csv` ({len(catalog_rows)} datasets) and",
        f"`dataset_priority.csv` ({len(high_priority)} HIGH / {len(med_priority)} MEDIUM /",
        f"{len(low_priority)} LOW).",
        "",
        "Effort estimates assume 1 engineer working in the existing GEDS",
        "Python codebase. Times are calendar days, not pure-coding days.",
        "",
        "## Immediate (1–3 days)",
        "",
        "Goal: bootstrap the fetcher infrastructure on the 5 highest-leverage",
        "HIGH-priority datasets — the ones GEDS already needs but does not yet",
        "ingest. Everything else mechanical-scales from this foundation.",
        "",
        "1. **Stand up the fetcher registry**: `backend/app/data/fetchers/__init__.py`",
        "   with the `comtrade_fetcher.py` pattern. _0.5 day._",
        "2. **Manifest schema**: per-dataset JSON with `sha256`, `last_fetch`,",
        "   `coverage_end`, `source_url`. _0.5 day._",
        "3. **`/api/v1/data/sources` rewrite**: enumerate catalog rows live",
        "   instead of the hardcoded stub. _0.5 day._",
        "",
        "Then wire these 5 fetchers (one per major API family):",
        "",
    ]
    # Pick 5 anchors covering distinct API families: Comtrade (trade), IMF WEO
    # (macro), World Bank WDI (panel), FRED (financial/inflation), GDELT (events).
    immediate_ids = {1, 8, 9, 34, 44}
    immediate_rows = [r for r in high_priority if int(r["dataset_id"]) in immediate_ids]
    for r in immediate_rows:
        nxt.append(
            f"- **{r['dataset_id']}. {r['dataset_name']}** ({r['provider']}) — "
            f"wire fetcher + validator. _Effort: 0.5 day._"
        )
    nxt += [
        "",
        "## Short-term (1–2 weeks)",
        "",
        "Goal: complete HIGH-priority ingestion (the remaining free-API datasets)",
        "and start on MEDIUM (key-required + flat-file). Once the fetcher pattern",
        "exists, each new dataset is mostly mechanical.",
        "",
        "### Remaining HIGH-priority free-API datasets",
        "",
    ]
    remaining_high = [r for r in high_priority if int(r["dataset_id"]) not in immediate_ids and r["download_url"]]
    for r in remaining_high:
        nxt.append(
            f"- **{r['dataset_id']}. {r['dataset_name']}** ({r['provider']}) — "
            f"_~0.5 day each, parallelisable._"
        )
    nxt += [
        "",
        "### MEDIUM-priority datasets (top 10 by confidence)",
        "",
    ]
    med_sorted = sorted(
        [r for r in med_priority if r["download_url"]],
        key=lambda r: (-r["confidence"], r["dataset_id"]),
    )[:10]
    for r in med_sorted:
        nxt.append(
            f"- **{r['dataset_id']}. {r['dataset_name']}** "
            f"({r['provider']}, conf={r['confidence']}) — "
            f"{'API key fetcher' if 'key' in r['_api_cell'].lower() else 'scheduled HTTP download'}, "
            f"validator, normalizer. _1–2 days each._"
        )
    nxt += [
        "",
        "Cross-cutting:",
        "- Implement schema-drift detection in the validator layer.",
        "- Wire the existing GitHub Actions cron to call each new fetcher.",
        "- Add `backend/scripts/refresh_all.py` as the local equivalent.",
        "",
        "## Medium-term (1 month)",
        "",
        "Goal: edge-merger expansion. The current engine uses 64 hardcoded",
        "edges + 137 Comtrade edges (opt-in). With CEPII BACI and OECD ICIO",
        "ingested, the graph can grow to thousands of bilateral edges, and the",
        "Sobol / MCMC calibration must be re-run on the larger topology.",
        "",
        "- BACI bilateral trade ingestion + merge into `edge_merger.py`.",
        "- OECD ICIO 2023 edition ingest → derive industry-to-industry weights.",
        "- OECD TiVA layer for value-added (vs gross) trade dependencies.",
        "- Re-run MCMC (production: 100 walkers × 2000 steps) on expanded graph.",
        "- Re-run Sobol; check if `propagation_decay` / `amplification_mu` are",
        "  still non-identifiable with more edges.",
        "- Re-run benchmark vs Leontief / Linear Diffusion / Naive.",
        "",
        "_Depends on: short-term ingestion infrastructure being stable._",
        "_Effort: ~3 weeks (data 1w + calibration 1w + benchmark 1w)._",
        "",
        "## Long-term (multi-month)",
        "",
        "- **Real-time event detection layer**: GDELT + ACLED + GTA streams,",
        "  with a debounced event-clustering step before triggering simulation",
        "  re-runs. Requires a small Kafka/Redis-like buffer (not yet built).",
        "- **Geospatial layer**: IMF PortWatch + Kiel Trade Indicator integration",
        "  for daily port-level signals. Needs GIS plumbing (GeoServices/WMS).",
        "- **Vintage-pinned IMF WEO archive**: backtesting against historical",
        "  WEO forecasts requires download of every vintage since 2007 and a",
        "  schema-versioning layer (TSV pre-2023 → SDMX post-2023).",
        "- **News stream → shock signal pipeline**: GDELT + Grok narrative",
        "  classifier with confidence scoring. Already partially exists",
        "  (`narrative` endpoint with Grok stub).",
        "",
        "_Depends on: medium-term graph expansion + calibration._",
        "_Effort: 2–3 months each._",
        "",
        "## Datasets explicitly NOT in scope for first 6 months",
        "",
        "These are LOW priority by the derivation rules — paywalled, members-only,",
        "or requiring GIS-only access:",
        "",
    ]
    for r in low_priority:
        nxt.append(
            f"- {r['dataset_id']} ({r['dataset_name']}): {r['limitations'][:120] or '—'}"
        )
    nxt += [""]

    next_path.write_text("\n".join(nxt), encoding="utf-8")
    print(f"wrote {next_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
