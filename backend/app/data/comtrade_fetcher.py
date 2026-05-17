"""UN Comtrade ETL — пуллит реальные bilateral trade flows через comtradeapicall.

Работает в двух режимах:
  * FREE (по умолчанию): через `previewFinalData`, лимит 500 записей/вызов,
    без подписочного ключа.  Для одного запроса (reporter × HS-код × год)
    обычно хватает — на одну страну приходится ~50-150 партнёров.
  * PREMIUM (если задан env GROK_COMTRADE_KEY): через `getFinalData`,
    до 250k записей за вызов, для bulk-загрузок.

Все ответы кэшируются на диск в backend/data/raw/comtrade/{cache_key}.parquet.
Повторный вызов с теми же параметрами читает из кэша → ноль API-вызовов.

Используется:
  scripts/fetch_comtrade.py        CLI-сборщик для расширения графа
  app/data/comtrade_processor.py   конвертирует raw → GEDS edges
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import comtradeapicall
except ImportError as _e:
    comtradeapicall = None
    _IMPORT_ERR = _e

try:
    import pandas as pd
except ImportError:
    pd = None


log = logging.getLogger("geds.comtrade")

_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "comtrade"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Free-tier rate limit: ~500 req/day for the preview endpoints.  Conservative
# 1.5 sec between calls keeps us well under any throttling threshold.
DEFAULT_THROTTLE_SECONDS = 1.5

# HS codes most relevant to GEDS industries (basis for the expanded graph).
HS_CODES_BY_INDUSTRY: dict[str, list[str]] = {
    "semiconductors": ["8541", "8542"],            # diodes/transistors, integrated circuits
    "automotive":     ["8703", "8704", "8708"],    # cars, trucks, parts
    "electronics":    ["8517", "8528", "8471"],    # phones, TVs, computers
    "aerospace":      ["8802", "8807"],            # aircraft, parts
    "energy":         ["2709", "2710", "2711"],    # crude oil, refined, gas
    "consumer_goods": ["6203", "6204", "9504"],    # apparel + games (proxy)
    "shipping":       ["8901", "8902"],            # vessels (low priority)
}

# Comtrade numeric codes for GEDS countries.
# Canonical M.49 reporter codes (not aliases or historical predecessors).
# Verified against the official UN Comtrade reporter reference list 2024.
# `convertCountryIso3ToCode` returns multiple historical codes per ISO3 in some cases
# (e.g. USA → 842 modern + 840 legacy + 251 France(!) due to a Comtrade quirk).
# Hardcoding eliminates that ambiguity.
ISO3_TO_COMTRADE: dict[str, int] = {
    "USA": 842, "CHN": 156, "JPN": 392, "DEU": 276, "KOR": 410,
    "TWN": 490,   # 490 = "Other Asia, nes" — Comtrade's de-facto code for Taiwan
    "NLD": 528, "VNM": 704, "MYS": 458, "THA": 764, "IND": 699, "MEX": 484,
    # Expansion set
    "BRA": 76, "RUS": 643, "IDN": 360, "GBR": 826, "FRA": 251, "ITA": 380, "CAN": 124,
    # Additional often-cited graph nodes
    "SGP": 702, "PHL": 608, "AUS": 36, "ZAF": 710, "TUR": 792, "ARE": 784,
    "SAU": 682, "ARG": 32, "POL": 616, "ESP": 724, "BEL": 56, "CHE": 757,
    "IRL": 372, "ISR": 376, "EGY": 818,
}


# ─────────────────────────── data classes ──────────────────────────────────


@dataclass
class FetchResult:
    """One CSV-row equivalent of a successful fetch."""
    reporter_iso3: str
    reporter_code: int
    flow: str                  # 'M' (import) or 'X' (export)
    hs_code: str
    period: str                # 'YYYY' for annual, 'YYYYMM' for monthly
    n_rows: int
    cache_path: str
    from_cache: bool
    fetch_seconds: float | None


# ─────────────────────────── helpers ───────────────────────────────────────


def _require_library() -> None:
    if comtradeapicall is None:
        raise ImportError(
            f"comtradeapicall is required.  pip install comtradeapicall\n"
            f"Original import error: {_IMPORT_ERR}"
        )
    if pd is None:
        raise ImportError("pandas is required.  pip install pandas")


def _cache_key(reporter_code: int, hs_code: str, period: str, flow: str,
               freq: str = "A") -> str:
    """Stable filename for cached responses."""
    return f"comtrade_{freq}_{flow}_{reporter_code}_{hs_code}_{period}.parquet"


def iso3_to_comtrade_code(iso3: str) -> int | None:
    """Convert ISO3 country code to Comtrade numeric code.

    Uses the verified hardcoded ISO3_TO_COMTRADE table first.  Falls back
    to comtradeapicall.convertCountryIso3ToCode() ONLY for unknown ISO3,
    and even then takes the LAST returned code (which is the modern
    reporter code in comtradeapicall's quirky output ordering).
    """
    iso3 = iso3.upper().strip()
    if iso3 in ISO3_TO_COMTRADE:
        return ISO3_TO_COMTRADE[iso3]
    # Fallback: convertCountryIso3ToCode may return multiple codes for one ISO3.
    # We take the LAST one because that's typically the modern reporter (USA: 842,
    # which is the last in the 251,380,250,756,757,840,842,841 sequence).
    _require_library()
    try:
        result = comtradeapicall.convertCountryIso3ToCode(iso3)
        if result and result.strip():
            codes = [int(c) for c in result.strip().split(",") if c.strip().isdigit()]
            if codes:
                code = codes[-1]
                log.warning(
                    "ISO3 %s not in hardcoded table; using fallback code %d "
                    "(library returned %s). Add to ISO3_TO_COMTRADE for safety.",
                    iso3, code, result,
                )
                ISO3_TO_COMTRADE[iso3] = code
                return code
    except Exception as exc:
        log.warning("ISO3 conversion failed for %s: %s", iso3, exc)
    return None


# ─────────────────────────── core fetcher ──────────────────────────────────


def fetch_bilateral(
    reporter_iso3: str,
    hs_code: str,
    period: str = "2019",
    flow: str = "M",
    freq: str = "A",
    subscription_key: str | None = None,
    use_cache: bool = True,
    throttle_seconds: float = DEFAULT_THROTTLE_SECONDS,
) -> FetchResult:
    """Fetch bilateral trade data for one (reporter, HS-code, period, flow).

    Returns a FetchResult with cache path.  Read the parquet to get the DataFrame.
    """
    _require_library()

    reporter_code = iso3_to_comtrade_code(reporter_iso3)
    if reporter_code is None:
        raise ValueError(f"Cannot map ISO3 '{reporter_iso3}' to Comtrade code")

    cache_path = _CACHE_DIR / _cache_key(reporter_code, hs_code, period, flow, freq)

    # Cache hit ------------------------------------------------------------
    if use_cache and cache_path.exists():
        df = pd.read_parquet(cache_path)
        return FetchResult(
            reporter_iso3=reporter_iso3, reporter_code=reporter_code,
            flow=flow, hs_code=hs_code, period=period, n_rows=len(df),
            cache_path=str(cache_path), from_cache=True, fetch_seconds=None,
        )

    # Live fetch -----------------------------------------------------------
    key = subscription_key or os.environ.get("COMTRADE_KEY") or ""
    t0 = time.perf_counter()

    if key:
        # Premium path — single call up to 250k records
        df = comtradeapicall.getFinalData(
            key,
            typeCode='C', freqCode=freq, clCode='HS',
            period=period, reporterCode=str(reporter_code),
            cmdCode=hs_code, flowCode=flow, partnerCode=None,
            partner2Code=None, customsCode=None, motCode=None,
            maxRecords=250_000, format_output='JSON',
            aggregateBy=None, breakdownMode='classic', countOnly=None,
            includeDesc=True,
        )
    else:
        # Free path — 500 records/call, but enough for one reporter at HS-4 level
        df = comtradeapicall.previewFinalData(
            typeCode='C', freqCode=freq, clCode='HS',
            period=period, reporterCode=str(reporter_code),
            cmdCode=hs_code, flowCode=flow, partnerCode=None,
            partner2Code=None, customsCode=None, motCode=None,
            maxRecords=500, format_output='JSON',
            aggregateBy=None, breakdownMode='classic', countOnly=None,
            includeDesc=True,
        )

    fetch_dt = time.perf_counter() - t0

    # Empty response: still cache (as empty df) so we don't re-hit the API.
    if df is None or len(df) == 0:
        df = pd.DataFrame()

    df.to_parquet(cache_path, index=False)
    time.sleep(throttle_seconds)        # politeness

    return FetchResult(
        reporter_iso3=reporter_iso3, reporter_code=reporter_code,
        flow=flow, hs_code=hs_code, period=period, n_rows=len(df),
        cache_path=str(cache_path), from_cache=False,
        fetch_seconds=round(fetch_dt, 2),
    )


def read_fetch(result: FetchResult):
    """Load the parquet for a FetchResult.  Returns DataFrame (possibly empty)."""
    _require_library()
    return pd.read_parquet(result.cache_path)


# ─────────────────────────── batch driver ─────────────────────────────────


def fetch_batch(
    reporters: list[str],
    hs_codes: list[str],
    period: str = "2019",
    flow: str = "M",
    freq: str = "A",
    subscription_key: str | None = None,
    progress: bool = True,
) -> list[FetchResult]:
    """Fetch every (reporter × HS code) combination.

    Smart-skips already-cached entries.  Reports cache hit rate so you
    know how much real API traffic happened.
    """
    out: list[FetchResult] = []
    n_total = len(reporters) * len(hs_codes)
    i = 0
    for iso3 in reporters:
        for hs in hs_codes:
            i += 1
            try:
                r = fetch_bilateral(
                    iso3, hs, period=period, flow=flow, freq=freq,
                    subscription_key=subscription_key,
                )
                out.append(r)
                if progress:
                    src = "CACHE" if r.from_cache else f"LIVE {r.fetch_seconds}s"
                    log.info("[%d/%d] %s HS%s %s/%s → %d rows (%s)",
                             i, n_total, iso3, hs, period, flow, r.n_rows, src)
            except Exception as exc:
                log.error("[%d/%d] %s HS%s FAILED: %s", i, n_total, iso3, hs, exc)
    return out


__all__ = [
    "FetchResult", "HS_CODES_BY_INDUSTRY",
    "fetch_bilateral", "fetch_batch", "read_fetch",
    "iso3_to_comtrade_code",
]
