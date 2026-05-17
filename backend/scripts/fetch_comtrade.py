"""CLI для пуллинга UN Comtrade данных под расширение GEDS-графа.

Usage:
    python -m scripts.fetch_comtrade --smoke                # 3 страны x2 HS-кода ≈ 30 сек
    python -m scripts.fetch_comtrade --geds-mvp             # 12 стран x9 HS-кодов ≈ 3-5 мин
    python -m scripts.fetch_comtrade --geds-expansion       # 19 стран x15 HS-кодов ≈ 10-15 мин
    python -m scripts.fetch_comtrade --year 2022            # переключить год
    python -m scripts.fetch_comtrade --key xxx              # явный subscription key

При наличии env COMTRADE_KEY премиум API используется автоматически.
Без ключа — free-тариф (500 записей/запрос, политеса 1.5 сек/запрос).
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

THIS = Path(__file__).resolve()
sys.path.insert(0, str(THIS.parent.parent))

from app.data.comtrade_fetcher import HS_CODES_BY_INDUSTRY, fetch_batch
from app.data.comtrade_processor import (
    aggregate_to_industry_edges, fetch_to_edges, save_edges_csv,
)


GEDS_MVP_COUNTRIES = [
    "USA", "CHN", "JPN", "DEU", "KOR", "TWN", "NLD",
    "VNM", "MYS", "THA", "IND", "MEX",
]

GEDS_EXPANSION_COUNTRIES = GEDS_MVP_COUNTRIES + [
    "BRA", "RUS", "IDN", "GBR", "FRA", "ITA", "CAN",
]


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="GEDS Comtrade ETL")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--smoke",          action="store_true", help="3-country x2-HS quick test")
    g.add_argument("--geds-mvp",       action="store_true", help="12 MVP countries x9 HS codes")
    g.add_argument("--geds-expansion", action="store_true", help="19 countries xall HS codes")
    g.add_argument("--countries",      help="comma-separated ISO3 list")
    ap.add_argument("--industries",    help="comma-separated industry list",
                    default=",".join(HS_CODES_BY_INDUSTRY.keys()))
    ap.add_argument("--year",          default="2019", help="period (YYYY for annual)")
    ap.add_argument("--key",           help="Comtrade subscription key (or env COMTRADE_KEY)")
    ap.add_argument("--min-penetration", type=float, default=0.02,
                    help="drop edges below this dep_weight (default 2%)")
    ap.add_argument("--output",        default="backend/data/csv/comtrade_edges.csv")
    args = ap.parse_args()

    configure_logging()

    if args.smoke:
        countries = ["USA", "CHN", "JPN"]
        industries = ["semiconductors"]
    elif args.geds_mvp:
        countries = GEDS_MVP_COUNTRIES
        industries = ["semiconductors", "automotive", "electronics"]
    elif args.geds_expansion:
        countries = GEDS_EXPANSION_COUNTRIES
        industries = list(HS_CODES_BY_INDUSTRY.keys())
    elif args.countries:
        countries = [c.strip().upper() for c in args.countries.split(",")]
        industries = [i.strip() for i in args.industries.split(",")]
    else:
        countries = ["USA"]
        industries = ["semiconductors"]

    print(f"Fetching Comtrade for {len(countries)} countries x{len(industries)} industries"
          f" ({sum(len(HS_CODES_BY_INDUSTRY[i]) for i in industries)} HS codes) for year {args.year}")

    t0 = time.perf_counter()
    edge_rows = fetch_to_edges(
        importers=countries,
        industries=industries,
        period=args.year,
        subscription_key=args.key,
        min_penetration=args.min_penetration,
    )
    fetch_dt = time.perf_counter() - t0

    print()
    print(f"Fetched {len(edge_rows)} (importer xexporter xHS) rows in {fetch_dt:.1f}s")

    edges = aggregate_to_industry_edges(edge_rows)
    print(f"Aggregated to {len(edges)} (importer xexporter xindustry) edges")

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = Path(__file__).resolve().parent.parent.parent / args.output
    save_edges_csv(edges, output_path)
    print(f"Wrote {output_path}")

    # Top-15 edges by dependency weight — for sanity check
    print()
    print("Top-15 edges by dependency_weight:")
    print(f"  {'exporter->importer':<26s}  {'industry':<14s}  {'dep_w':>6s}  {'value (USD)':>15s}")
    for e in edges[:15]:
        src = f"{e['source_iso3']}:{e['source_industry']}"
        tgt = f"{e['target_iso3']}:{e['target_industry']}"
        edge_label = f"{src} -> {tgt}"
        print(f"  {edge_label[:26]:<26s}  {e['industry']:<14s}  {e['dependency_weight']:6.3f}"
              f"  {e['flow_value_usd']/1e9:12.2f}B")
    return 0


if __name__ == "__main__":
    sys.exit(main())
